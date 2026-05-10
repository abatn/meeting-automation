import asyncio
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import httpx
import redis
from botocore.exceptions import ClientError
from sqlalchemy import select, insert, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.action import Action, Assignment
from app.models.pv import PV, Section
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.models.user import User
from app.services.gladia_service import gladia_service
from app.services.pv_service import PVService
from app.services.sentinel_service import sentinel
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def publish_status(recording_id: str, status: str, progress: int, message: str = "") -> None:
    try:
        redis_client = get_redis_client()
        channel = f"transcription_status_{recording_id}"
        payload = {"status": status, "progress": progress, "message": message}
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.error(f"Redis publish failed: {e}")


def match_timestamps(words: List[Dict], segments: List[Dict]) -> List[Dict]:
    """
    Assign word-level timestamps to speaker segments.

    For each word, find the segment with the closest boundary (start or end).
    Uses point-to-interval distance: if word_mid is within segment, distance=0;
    if left of segment, distance = segment.start - word_mid; if right, distance = word_mid - segment.end.

    Args:
        words: List of word dicts with 'word', 'start', 'end'
        segments: List of segment dicts with 'speaker', 'start', 'end'

    Returns:
        List of dicts with 'speaker', 'text' (concatenated words for each segment).
        Only returns segments that have at least one word assigned.
    """
    if not words or not segments:
        return []

    # Group words by closest segment
    segmented_words = {seg["speaker"]: [] for seg in segments}

    for word in words:
        word_mid = (word["start"] + word["end"]) / 2
        closest_seg = None
        min_dist = float('inf')

        for seg in segments:
            seg_start = seg["start"]
            seg_end = seg["end"]
            # Distance from point to interval
            if word_mid < seg_start:
                dist = seg_start - word_mid
            elif word_mid > seg_end:
                dist = word_mid - seg_end
            else:
                dist = 0.0
            if dist < min_dist:
                min_dist = dist
                closest_seg = seg["speaker"]

        if closest_seg:
            segmented_words[closest_seg].append(word["word"])

    # Build result: only include segments that have words
    result = []
    for seg in segments:
        speaker = seg["speaker"]
        words_list = segmented_words.get(speaker, [])
        if words_list:  # Only add if there are words
            result.append({
                "speaker": speaker,
                "text": " ".join(words_list),
                "start": seg["start"],
                "end": seg["end"]
            })

    return result

async def _process_recording_pipeline(recording_id: str) -> None:
    temp_path = None
    try:
        publish_status(recording_id, "uploaded", 5, "Initializing Map-Reduce Pipeline...")

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Recording).where(Recording.id == recording_id))
            recording = result.scalar_one_or_none()
            if not recording:
                logger.warning(f"Recording {recording_id} not found, aborting.")
                return

            recording.status = "transcribing"
            await db.commit()

            # Download audio from S3
            temp_path = await _download_audio(str(recording.file_path))
            if not temp_path:
                raise Exception("S3 Error: Failed to download audio from MinIO")

            # 1. GLADIA PHASE (Diarization)
            publish_status(recording_id, "transcribing", 20, "Extracting Voices (Gladia V2)...")
            gladia_result = await gladia_service.transcribe_and_diarize(temp_path)

            # 2. MAP PHASE (Local SLM Sentinel)
            publish_status(recording_id, "analyzing", 45, "Local Semantic Synthesis (Qwen-1.5B)...")
            transcript_text = gladia_result.get("full_text", "")

            # Chunking: split by time or length
            chunks = [transcript_text[i:i+3000] for i in range(0, len(transcript_text), 3000)]

            # Parallel Map execution
            map_tasks = [sentinel.summarize_chunk(chunk) for chunk in chunks]
            partial_summaries = await asyncio.gather(*map_tasks)

            enriched_context = "\n---\n".join(partial_summaries)

            # 3. REDUCE PHASE (Mistral Small)
            publish_status(recording_id, "analyzing", 75, "Final Protocol Refinement (Mistral)...")

            from app.models.meeting import Meeting
            from sqlalchemy.orm import selectinload
            stmt = select(Meeting).options(selectinload(Meeting.participants)).where(Meeting.id == recording.meeting_id)
            meeting_res = await db.execute(stmt)
            meeting = meeting_res.scalar_one_or_none()
            participant_names = [p.name for p in meeting.participants if p.name] if meeting else []

            pv_data = await PVService.generate_pv(enriched_context, target_language="fr", participant_names=participant_names)

            # 4. Persistence
            await _save_transcription(db, recording, gladia_result)
            await _save_pv_and_actions(db, recording, pv_data, language="fr")

            recording.status = "completed"
            await db.commit()

            publish_status(recording_id, "completed", 100, "ISS Synthesis Successful (33.3s target).")
            await _notify_n8n_completion(str(recording.id), str(recording.meeting_id))

    except Exception as e:
        logger.error(f"Pipeline failed for recording {recording_id}: {str(e)}", exc_info=True)
        # Rollback: Set recording.status to "failed"
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Recording).where(Recording.id == recording_id))
            recording = result.scalar_one_or_none()
            if recording:
                recording.status = "failed"
                await db.commit()
                publish_status(recording_id, "failed", 0, f"Processing failed: {str(e)}")
        # Re-raise untuk Celery retry
        raise
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_path}: {e}")

async def _record_minutes_usage(db, recording, gladia_result):
    """Calculate and record minutes used from transcription segments."""
    segments = gladia_result.get("segments", [])
    if not segments:
        logger.warning(f"No segments found for recording {recording.id}, cannot calculate minutes")
        return

    max_end_time = max(seg.get("end", 0) for seg in segments)
    minutes_used = int(max_end_time / 60) + (1 if max_end_time % 60 > 0 else 0)

    if minutes_used > 0:
        try:
            from app.services.billing_service import BillingService
            billing_service = BillingService(db)
            await billing_service.record_usage(
                client_id=str(recording.client_id),
                minutes=minutes_used,
                meeting_id=str(recording.meeting_id)
            )
            logger.info(f"Recorded {minutes_used} minutes usage for client {recording.client_id}")
        except Exception as e:
            logger.error(f"Failed to record minutes usage: {e}")


async def _save_transcription(db, recording, gladia_result):
    db_trans = Transcription(
        id=str(uuid.uuid4()),
        client_id=str(recording.client_id),
        recording_id=str(recording.id),
        meeting_id=str(recording.meeting_id),
        full_text=gladia_result.get("full_text", ""),
        language="auto",
        segments=gladia_result.get("segments", []),
    )
    db.add(db_trans)
    await db.flush()

    await _record_minutes_usage(db, recording, gladia_result)

async def _download_audio(file_key: str) -> Optional[str]:
    s3_client = boto3.client("s3", endpoint_url=settings.S3_ENDPOINT, aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            s3_client.download_fileobj(settings.S3_BUCKET_NAME, file_key, tmp)
            return tmp.name
    except: return None

async def _save_pv_and_actions(db, recording, pv_data, language="fr"):
    """Save PV and Actions with fuzzy-matching assignments.

    Creates Assignment records by matching assignee names (from Mistral) to Users in the same client.
    Uses ilike substring matching for simplicity and consistency with team_service.search_members.
    If no User found, creates external assignment (external_name or external_email).
    """
    summary = pv_data.get("summary", "")
    decisions_list = pv_data.get("decisions", [])
    html = f"<h3>Résumé</h3><p>{summary}</p><h3>Décisions</h3><ul>" + "".join([f"<li>{d}</li>" for d in decisions_list]) + "</ul>"

    pv_id = str(uuid.uuid4())
    await db.execute(insert(PV).values(
        id=pv_id, client_id=str(recording.client_id), meeting_id=str(recording.meeting_id),
        title=pv_data.get("title", "Meeting PV"),
        tags=pv_data.get("tags"),
        content_html=html, language=language, status="draft", is_validated=False
    ))

    created_actions = []  # List of (action, assignee_name) tuples
    for act in pv_data.get("actions", []):
        due_date = None
        if act.get("deadline"):
            try:
                due_date = datetime.fromisoformat(act["deadline"])
            except (ValueError, TypeError):
                pass
        description = act.get("description", "")
        action = Action(
            id=str(uuid.uuid4()),
            client_id=str(recording.client_id),
            meeting_id=str(recording.meeting_id),
            title=description[:200] if description else "Action",
            description=description,
            due_date=due_date,
            status="PENDING",
            priority=act.get("priority", "medium"),
        )
        db.add(action)
        created_actions.append((action, act.get("assignee")))

    await db.flush()

    # Create assignments with fuzzy matching (Option A: ilike substring)
    for action, assignee_name in created_actions:
        if not assignee_name:
            continue

        # Search for user in the same client where full_name or email contains assignee_name (case-insensitive)
        stmt = select(User).where(
            User.client_id == recording.client_id
        ).where(
            or_(
                User.full_name.ilike(f"%{assignee_name}%"),
                User.email.ilike(f"%{assignee_name}%")
            )
        ).limit(1)

        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Internal user found
            assignment = Assignment(
                id=str(uuid.uuid4()),
                action_id=action.id,
                user_id=user.id
            )
        else:
            # No user found, treat as external contact
            if '@' in assignee_name:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=action.id,
                    external_email=assignee_name
                )
            else:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=action.id,
                    external_name=assignee_name
                )
        db.add(assignment)

    await db.flush()

async def _notify_n8n_completion(recording_id, meeting_id):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json={"event": "transcription.completed", "recording_id": recording_id, "meeting_id": meeting_id})
    except: pass

@celery_app.task(
    name="process_recording",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # 10 minutes max backoff
    retry_jitter=True,
    max_retries=3,
)
def process_recording(self, recording_id: str) -> None:
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.run_until_complete(_process_recording_pipeline(recording_id))
    else:
        asyncio.ensure_future(_process_recording_pipeline(recording_id), loop=loop)


# Expose DiarizationService for backward compatibility with tests
from app.services.diarization_service import DiarizationService  # noqa
