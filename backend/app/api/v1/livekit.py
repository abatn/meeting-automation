import json
import logging
import uuid
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from livekit.api.access_token import TokenVerifier
from livekit.api.webhook import WebhookReceiver
from livekit.protocol.egress import EgressStatus

from app.api.deps import get_current_user
from app.models.user import User
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.services.livekit_service import LiveKitService
from app.services.audit_service import AuditService
from app.core.config import settings
from app.core.database import AsyncSessionLocal

_webhook_receiver = WebhookReceiver(
    TokenVerifier(api_key=settings.LIVEKIT_API_KEY, api_secret=settings.LIVEKIT_API_SECRET)
)

_DEDUP_TTL_SECONDS = 86_400  # 24h — LiveKit retries webhooks up to ~1h, 24h is safe headroom

logger = logging.getLogger(__name__)

router = APIRouter()


def _webhook_dedup_key(egress_id: str, event_name: str) -> str:
    return f"livekit:webhook:dedup:{egress_id}:{event_name}"


def _claim_webhook_event(egress_id: str, event_name: str) -> bool:
    """Tier 2.4: Atomic SETNX via Redis to prevent duplicate processing.

    Returns True if this is the first time we see this (egress_id, event_name),
    False if a previous webhook already processed the same event.
    """
    if not egress_id or not event_name:
        return True
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        key = _webhook_dedup_key(egress_id, event_name)
        return bool(r.set(key, "1", nx=True, ex=_DEDUP_TTL_SECONDS))
    except Exception as e:
        logger.warning(f"Tier 2.4: Redis dedup claim failed (fail-open): {e}")
        return True


@router.post("/meetings/{meeting_id}/livekit/token")
async def get_livekit_token(
    meeting_id: str,
    request: Request,  # Required for ngrok detection
    current_user: User = Depends(get_current_user),
):
    """Generates a LiveKit token for any authenticated meeting participant.
    
    TEST-ONLY: Auto-detects ngrok clients and returns appropriate LiveKit URL.
    Remove LIVEKIT_NGROK_URL from .env for production deployment.
    """
    """Generates a LiveKit token for any authenticated meeting participant.
    
    LiveKit Best Practice: Any authenticated user can join a room with a valid token.
    Security is maintained through multi-tenant client_id validation in deps.py.
    Reference: https://github.com/livekit-examples/meet/blob/main/app/api/connection-details/route.ts
    """
    from app.models.meeting import Participant
    
    async with AsyncSessionLocal() as db:
        # Verify meeting exists and belongs to this tenant
        result = await db.execute(
            select(Meeting).where(Meeting.id == meeting_id, Meeting.client_id == current_user.client_id)
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # SECURITY: Verify user is creator OR a registered participant
        is_creator = meeting.creator_id == current_user.id
        participant_result = await db.execute(
            select(Participant).where(
                Participant.meeting_id == meeting_id,
                # Check by user_id OR by email (participants may not have user_id linked)
                (Participant.user_id == current_user.id) | (Participant.email == current_user.email)
            )
        )
        is_participant = participant_result.scalar_one_or_none() is not None

        if not is_creator and not is_participant:
            raise HTTPException(status_code=403, detail="Not authorized to join this meeting")

    service = LiveKitService()
    user_name = current_user.full_name or current_user.email
    token = await service.generate_token(meeting_id, current_user.id, user_name)
    # Use an explicit public URL when configured; otherwise derive the
    # LiveKit WebSocket URL from the incoming Host header. This avoids
    # hard-coded IPs and keeps localhost and external deployments consistent.
    request_host = request.headers.get("host", "")
    if settings.LIVEKIT_NGROK_URL and "ngrok" in request_host:
        server_url = settings.LIVEKIT_NGROK_URL
    elif settings.LIVEKIT_PUBLIC_URL:
        server_url = settings.LIVEKIT_PUBLIC_URL
    else:
        hostname = request_host.split(":")[0]
        server_url = f"ws://{hostname}:7880" if hostname else settings.LIVEKIT_URL
    if not server_url or not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=503,
            detail="LiveKit configuration is incomplete. Check LIVEKIT_URL, LIVEKIT_PUBLIC_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.",
        )
    
    # LiveKit Meet ConnectionDetails pattern
    return {
        "serverUrl": server_url,
        "roomName": meeting_id,
        "participantName": user_name,
        "participantToken": token,
    }


@router.post("/meetings/{meeting_id}/livekit/start-recording")
async def start_livekit_recording(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Starts LiveKit Egress recording for the meeting. Creator/admin only."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Meeting).where(
                Meeting.id == meeting_id,
                Meeting.client_id == current_user.client_id,
            )
        )
        meeting = result.scalar_one_or_none()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        if meeting.creator_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only meeting creator can start recording.")

    service = LiveKitService()
    file_key = f"{current_user.client_id}/recordings/{meeting_id}/{uuid.uuid4()}_livekit.ogg"

    async with AsyncSessionLocal() as db:
        db_recording = Recording(
            id=str(uuid.uuid4()),
            client_id=current_user.client_id,
            meeting_id=meeting_id,
            file_path=file_key,
            status="streaming",
            format="audio/ogg",
            created_at=datetime.now(timezone.utc),
        )
        db.add(db_recording)
        await db.commit()
        await db.refresh(db_recording)

        try:
            egress_id = await service.start_egress(meeting_id, file_key)
            db_recording.egress_id = egress_id
            await db.commit()
        except Exception as e:
            logger.warning(f"LiveKit Egress unavailable: {e}")
            await db.delete(db_recording)
            await db.commit()
            raise HTTPException(
                status_code=503,
                detail="LiveKit recording service unavailable. The meeting room is active but recording could not start."
            )

        await AuditService.log_action(
            db,
            client_id=current_user.client_id,
            action="LIVEKIT_RECORDING_STARTED",
            user_id=current_user.id,
            table_name="recordings",
            record_id=db_recording.id,
            new_values={
                "meeting_id": meeting_id,
                "egress_id": egress_id,
                "file_key": file_key,
            },
        )

    return {
        "recording_id": db_recording.id,
        "egress_id": egress_id,
        "status": "recording",
    }


@router.post("/meetings/{meeting_id}/livekit/stop-recording")
async def stop_livekit_recording(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Stops the active LiveKit Egress recording for the meeting.

    Note: Recording status update to 'uploaded' is intentionally NOT done here.
    The status is set by the egress.completed webhook handler once the file
    is actually in MinIO. This prevents DB/state drift when S3 uploads fail.
    See docs/LIVEKIT_PRODUCTION_HARDENING_ROADMAP.md Tier 1.2
    """
    service = LiveKitService()

    async with AsyncSessionLocal() as db:
        # Find the active streaming recording for this meeting + tenant
        result = await db.execute(
            select(Recording).where(
                Recording.meeting_id == meeting_id,
                Recording.client_id == current_user.client_id,
                Recording.status == "streaming",
            ).order_by(Recording.created_at.desc()).limit(1)
        )
        recording = result.scalar_one_or_none()
        if not recording:
            raise HTTPException(status_code=404, detail="No active recording found for this meeting.")

        # Get egress_id from active egress sessions via LiveKit API
        try:
            active_egresses = await service.list_egress(meeting_id)
            if not active_egresses:
                raise HTTPException(status_code=404, detail="No active egress found for this meeting.")
            egress_id = active_egresses[0].egress_id
            await service.stop_egress(egress_id)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"LiveKit stop egress failed: {e}")
            raise HTTPException(status_code=503, detail=f"Failed to stop recording: {str(e)}")

        await AuditService.log_action(
            db,
            client_id=current_user.client_id,
            action="LIVEKIT_RECORDING_STOPPED",
            user_id=current_user.id,
            table_name="recordings",
            record_id=recording.id,
            new_values={"meeting_id": meeting_id, "egress_id": egress_id},
        )

    return {"recording_id": recording.id, "egress_id": egress_id, "status": "stopped"}


@router.get("/meetings/{meeting_id}/livekit/recording-status")
async def get_recording_status(
    meeting_id: str,
    current_user: User = Depends(get_current_user),
):
    """Returns current recording status for the meeting."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Recording).where(
                Recording.meeting_id == meeting_id,
                Recording.client_id == current_user.client_id,
            ).order_by(Recording.created_at.desc()).limit(1)
        )
        recording = result.scalar_one_or_none()
        if not recording:
            return {"status": "idle", "recording_id": None, "egress_id": None}

        return {
            "status": recording.status,
            "recording_id": recording.id,
            "created_at": recording.created_at.isoformat() if recording.created_at else None,
        }


@router.post("/livekit/webhooks")
async def livekit_webhook(request: Request):
    """Handles LiveKit webhook events (egress started/ended/failed).

    Two auth paths:
      1. LiveKit Server sends JWT in Authorization header (no Bearer prefix).
         Validated via livekit.api.WebhookReceiver (HMAC + timestamp leeway).
      2. Fallback: ``Bearer {INTERNAL_API_SECRET}`` for manual curl/script tests.

    Tier 1.3: egress_failed → recording.status = "failed" + LIVEKIT_EGRESS_FAILED audit
    Tier 1.2: status only set by webhook (not by stop-recording) to prevent
              DB/state drift when S3 uploads fail.
    """
    auth_header = request.headers.get("Authorization", "")
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8") if body_bytes else ""

    logger.info(
        "LiveKit webhook received: auth_header_present=%s body_prefix=%s",
        bool(auth_header),
        body_str[:200],
    )

    event_name = ""
    meeting_id = ""
    egress_id = ""
    file_location = ""
    error_message = ""
    egress_status = None

    if auth_header and not auth_header.startswith("Bearer "):
        try:
            webhook_event = _webhook_receiver.receive(body_str, auth_header)
            event_name = webhook_event.event
            logger.info(f"LiveKit webhook (JWT-auth): event={event_name}")

            egress_info = webhook_event.egress_info
            if egress_info:
                meeting_id = egress_info.room_name or ""
                egress_id = egress_info.egress_id or ""
                if egress_info.file and egress_info.file.filename:
                    file_location = egress_info.file.filename
                if egress_info.error:
                    error_message = egress_info.error
                egress_status = egress_info.status
        except Exception as e:
            logger.warning(f"LiveKit webhook JWT validation failed: {e}")
            raise HTTPException(status_code=403, detail="Invalid webhook signature")
    elif auth_header == f"Bearer {settings.INTERNAL_API_SECRET}":
        try:
            data = json.loads(body_str) if body_str else {}
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        event_name = data.get("event", "")
        meeting_id = data.get("room_name", "")
        egress_id = data.get("egress_id", "")
        file_location = data.get("file_location", "")
        err = data.get("egress", {}) or {}
        error_message = (err.get("error", {}) or {}).get("message", "") if isinstance(err.get("error"), dict) else str(err.get("error", ""))
        logger.info(f"LiveKit webhook (manual/Bearer): event={event_name}")
    else:
         raise HTTPException(status_code=403, detail="Invalid webhook auth")

    # Handle participant connection aborted events (non-fatal, logging only)
    if event_name == "participant_connection_aborted" and meeting_id:
        logger.warning(
            "LiveKit participant connection aborted: meeting_id=%s "
            "Participant is attempting to reconnect. This is normal for network instability.",
            meeting_id,
        )
        # No recording status change, no audit log, no DB operation
        # ICE failures and reconnects are expected in WebRTC
        return {"ok": True, "event": event_name, "handled": "log_only"}

    if event_name == "egress_ended" and meeting_id and egress_id:
        if not _claim_webhook_event(egress_id, event_name):
            logger.info(
                f"Tier 2.4: Duplicate egress_ended webhook ignored for "
                f"egress_id={egress_id} (already processed)"
            )
            return {"ok": True, "event": event_name, "deduplicated": True}

        if _egress_status_is_failure(egress_status):
            logger.warning(
                f"egress_ended with failure status for meeting={meeting_id} "
                f"egress_id={egress_id}: {error_message or 'aborted'}"
            )
            await _mark_recording_failed(
                meeting_id=meeting_id,
                egress_id=egress_id,
                error_message=error_message or "Egress aborted (no publisher)",
            )
        else:
            from app.tasks.transcription_tasks import process_recording

            async with AsyncSessionLocal() as db:
                meeting_client_id = await _get_meeting_client_id(db, meeting_id)
                if not meeting_client_id:
                    logger.warning(
                        f"LiveKit webhook ignored: meeting_id={meeting_id} not found"
                    )
                    return {"ok": True, "event": event_name}

                recording = await _get_active_recording_for_meeting(
                    db,
                    meeting_id=meeting_id,
                    client_id=meeting_client_id,
                )
                if recording:
                    recording.egress_id = egress_id
                    if file_location:
                        recording.file_path = file_location
                    recording.status = "uploaded"
                    await db.commit()

                    process_recording.delay(recording.id, str(recording.client_id))

                    await AuditService.log_action(
                        db,
                        client_id=recording.client_id,
                        action="LIVEKIT_EGRESS_COMPLETED",
                        user_id=None,
                        table_name="recordings",
                        record_id=recording.id,
                        new_values={"egress_id": egress_id, "file_path": file_location},
                    )

    elif event_name == "egress_failed" and meeting_id and egress_id:
        if not _claim_webhook_event(egress_id, event_name):
            logger.info(
                f"Tier 2.4: Duplicate egress_failed webhook ignored for "
                f"egress_id={egress_id} (already processed)"
            )
            return {"ok": True, "event": event_name, "deduplicated": True}
        await _mark_recording_failed(
            meeting_id=meeting_id,
            egress_id=egress_id,
            error_message=error_message or "Egress failed (no message)",
        )

    return {"ok": True, "event": event_name}


async def _get_meeting_client_id(db, meeting_id: str) -> str | None:
    result = await db.execute(
        select(Meeting.client_id).where(Meeting.id == meeting_id)
    )
    return result.scalar_one_or_none()


async def _get_active_recording_for_meeting(db, meeting_id: str, client_id: str) -> Recording | None:
    result = await db.execute(
        select(Recording)
        .join(Meeting, Meeting.id == Recording.meeting_id)
        .where(
            Recording.meeting_id == meeting_id,
            Meeting.client_id == client_id,
            Recording.status == "streaming",
        )
        .order_by(Recording.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _egress_status_is_failure(status) -> bool:
    """Treat EGRESS_FAILED, EGRESS_ABORTED, and EGRESS_LIMIT_REACHED as failure."""
    if status is None:
        return False
    return status in (
        EgressStatus.EGRESS_FAILED,
        EgressStatus.EGRESS_ABORTED,
        EgressStatus.EGRESS_LIMIT_REACHED,
    )


async def _mark_recording_failed(meeting_id: str, egress_id: str, error_message: str) -> None:
    """Set the active recording for ``meeting_id`` to status='failed' and audit it."""
    async with AsyncSessionLocal() as db:
        meeting_client_id = await _get_meeting_client_id(db, meeting_id)
        if not meeting_client_id:
            logger.warning(
                f"LiveKit Egress FAILED webhook ignored: meeting_id={meeting_id} not found"
            )
            return

        recording = await _get_active_recording_for_meeting(
            db,
            meeting_id=meeting_id,
            client_id=meeting_client_id,
        )
        if recording:
            recording.status = "failed"
            recording.egress_id = egress_id
            recording.error_message = error_message
            await db.commit()

            await AuditService.log_action(
                db,
                client_id=recording.client_id,
                action="LIVEKIT_EGRESS_FAILED",
                user_id=None,
                table_name="recordings",
                record_id=recording.id,
                new_values={
                    "egress_id": egress_id,
                    "error": error_message,
                },
            )
            logger.error(
                f"LiveKit Egress FAILED for meeting={meeting_id} "
                f"egress_id={egress_id}: {error_message}"
            )
