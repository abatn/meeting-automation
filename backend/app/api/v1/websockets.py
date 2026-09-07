from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket import manager
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/transcription/{recording_id}")
async def websocket_transcription_endpoint(websocket: WebSocket, recording_id: str):
    """
    WebSocket Route für die Fortschrittsanzeige der Transkription.
    Frontend verbindet sich hier mit ws://.../api/v1/websockets/transcription/{recording_id}
    """
    await manager.connect(websocket, recording_id)
    try:
        # Bestätigung an den Client senden
        await manager.send_personal_message(
            '{"status": "connected", "progress": 0, "message": "Connection established"}',
            websocket,
        )

        # Verbindung offen halten und auf Client-Nachrichten (Ping) warten
        while True:
            # Wir warten hier nur passiv, da Updates über Redis reinkommen
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message("pong", websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket, recording_id)
    except Exception as e:
        logger.error(f"WebSocket Error for recording {recording_id}: {e}")
        manager.disconnect(websocket, recording_id)


@router.websocket("/speaking-timeline/{meeting_id}")
async def speaking_timeline_endpoint(websocket: WebSocket, meeting_id: str):
    """Receive speaking timeline from frontend for server-side speaker identification.

    Frontend sends ActiveSpeakersChanged events as JSON:
    {
        "type": "speaker_timeline",
        "meeting_id": "...",
        "data": [
            {"participant_id": "user1_abc", "participant_name": "Alice", "started_speaking_at": 1234567890},
            ...
        ]
    }

    Timeline data is stored in Redis with a TTL matching the pipeline processing window.
    The pipeline reads this data to match Gladia segments to known participant identities.
    """
    await websocket.accept()
    logger.info(f"Speaking timeline WebSocket connected for meeting {meeting_id}")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"Speaking timeline: invalid JSON from meeting {meeting_id}")
                continue

            msg_type = msg.get("type")
            if msg_type == "ping":
                await websocket.send_text('{"type": "pong"}')
                continue

            if msg_type != "speaker_timeline":
                continue

            timeline_data = msg.get("data", [])
            if not timeline_data:
                continue

            # Store in Redis with 2-hour TTL (pipeline processing window)
            import redis
            from app.core.config import settings

            try:
                r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
                key = f"speaking_timeline:{meeting_id}"
                # Append to existing timeline (list of events)
                for event in timeline_data:
                    r.rpush(key, json.dumps(event))
                r.expire(key, 7200)  # 2-hour TTL
                logger.info(
                    f"Speaking timeline: stored {len(timeline_data)} events "
                    f"for meeting {meeting_id}"
                )
            except Exception as e:
                logger.error(f"Speaking timeline: Redis store failed: {e}")

    except WebSocketDisconnect:
        logger.info(f"Speaking timeline WebSocket disconnected for meeting {meeting_id}")
    except Exception as e:
        logger.error(f"Speaking timeline WebSocket error for meeting {meeting_id}: {e}")
