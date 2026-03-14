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
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.action import Action
from app.models.pv import PV, Section
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.services.diarization_service import DiarizationService
from app.services.pv_service import PVService
from app.services.transcription_service import transcribe_audio
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return client  # type: ignore


def publish_status(
    recording_id: str, status: str, progress: int, message: str = ""
) -> None:
    """Helper to publish status updates to Redis for WebSockets."""
    try:
        redis_client = get_redis_client()
        channel = f"transcription_status_{recording_id}"
        payload = {"status": status, "progress": progress, "message": message}
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.error(f"Redis publish failed for {recording_id}: {e}")


def match_timestamps(
    words: List[Dict[str, Any]], segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Match Whisper words with Pyannote segments."""
    if not segments or not words:
        return []

    segments.sort(key=lambda x: x["start"])
    matched_blocks: List[Dict[str, Any]] = []
    current_block: Optional[Dict[str, Any]] = None

    for word_info in words:
        word = word_info.get("word", "")
        start = word_info.get("start", 0.0)
        end = word_info.get("end", 0.0)
        midpoint = (start + end) / 2

        closest_segment = next(
            (seg for seg in segments if seg["start"] <= midpoint <= seg["end"]),
            min(
                segments,
                key=lambda s: min(abs(s["start"] - midpoint), abs(s["end"] - midpoint)),
            ),
        )

        speaker = str(closest_segment["speaker"])

        if current_block is None or current_block["speaker"] != speaker:
            if current_block:
                matched_blocks.append(current_block)
            current_block = {
                "speaker": speaker,
                "text": word.strip(),
                "start": start,
                "end": end,
            }
        else:
            current_block["text"] += " " + word.strip()
            current_block["end"] = end

    if current_block:
        matched_blocks.append(current_block)
    return matched_blocks


async def _process_recording_pipeline(recording_id: str) -> None:
    publish_status(
        recording_id, "uploaded", 0, "Audio uploaded, starting processing..."
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()

        if not recording:
            logger.error(f"Recording {recording_id} not found")
            publish_status(recording_id, "failed", 0, "Recording not found in DB")
            return

        recording.status = "transcribing"
        await db.commit()

        temp_path: Optional[str] = None
        try:
            temp_path = await _download_audio(str(recording.file_path))
            if not temp_path:
                raise Exception("S3 Download failed")

            publish_status(recording_id, "transcribing", 25, "Speaker diarization...")
            speaker_segments = await DiarizationService.diarize(temp_path)

            publish_status(recording_id, "transcribing", 50, "Transcription...")
            trans_res = await transcribe_audio(temp_path, word_timestamps=True)

            publish_status(recording_id, "transcribing", 75, "Matching results...")
            await _handle_ai_results(db, recording, speaker_segments, trans_res)

            publish_status(recording_id, "completed", 100, "Processing complete!")
            await _notify_n8n_completion(str(recording.id), str(recording.meeting_id))

        except Exception as e:
            logger.error(f"Error in transcription pipeline: {e}")
            if recording:
                recording.status = "failed"
                await db.commit()
            publish_status(recording_id, "failed", 0, f"Error: {str(e)}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


async def _download_audio(file_key: str) -> Optional[str]:
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            s3_client.download_fileobj(settings.S3_BUCKET_NAME, file_key, tmp)
            return tmp.name
    except ClientError as e:
        logger.critical(f"S3 Download failed: {e}")
        return None


async def _handle_ai_results(
    db: AsyncSession,
    recording: Recording,
    speaker_segments: List[Dict[str, Any]],
    trans_res: Dict[str, Any],
) -> None:
    if not speaker_segments:
        words = trans_res.get("words", [])
        end_time = words[-1].get("end", 0.0) if words else 0.0
        speaker_segments = [{"speaker": "SPEAKER_00", "start": 0.0, "end": end_time}]

    matched = match_timestamps(trans_res.get("words", []), speaker_segments)
    mistral_text = (
        "\n".join([f"{b['speaker']}: {b['text']}" for b in matched])
        if matched
        else trans_res.get("text", "")
    )
    logger.info(f"Text sent to Mistral (first 500 chars): {mistral_text[:500]}")

    db_trans = Transcription(
        id=str(uuid.uuid4()),
        recording_id=str(recording.id),
        meeting_id=str(recording.meeting_id),
        full_text=trans_res.get("text", ""),
        language=trans_res.get("language", "auto"),
        segments=matched or None,
    )
    db.add(db_trans)
    recording.status = "analyzing"
    await db.commit()

    # Use the detected or requested language for PV generation
    target_lang = trans_res.get("language", "fr")
    if target_lang == "auto": target_lang = "fr"
    
    pv_data = await PVService.generate_pv(mistral_text, target_language=target_lang)
    await _save_pv_and_actions(db, recording, pv_data, language=target_lang)
    recording.status = "completed"
    await db.commit()


async def _save_pv_and_actions(
    db: AsyncSession, recording: Recording, pv_data: Dict[str, Any], language: str = "fr"
) -> None:
    summary = pv_data.get("summary", "")
    decisions_list = pv_data.get("decisions", [])
    decisions_html = "<br/>".join([f"- {d}" for d in decisions_list])
    html = f"<h3>Résumé</h3><p>{summary}</p><h3>Décisions</h3><p>{decisions_html}</p>"

    existing_pv_res = await db.execute(
        select(PV).where(PV.meeting_id == recording.meeting_id)
    )
    existing_pv = existing_pv_res.scalar_one_or_none()

    pv_id = None
    if existing_pv:
        pv_id = existing_pv.id
        await db.execute(
            update(PV)
            .where(PV.id == pv_id)
            .values(
                title=pv_data.get("title", "Meeting PV"),
                content_html=html,
                language=language,
                updated_at=datetime.utcnow()
            )
        )
        # Clear existing sections to avoid duplicates on re-run
        await db.execute(delete(Section).where(Section.pv_id == pv_id))
    else:
        pv_id = str(uuid.uuid4())
        await db.execute(
            insert(PV).values(
                id=pv_id,
                meeting_id=str(recording.meeting_id),
                title=pv_data.get("title", "Meeting PV"),
                content_html=html,
                language=language,
                status="draft"
            )
        )

    # Save summary as a section for the PDF
    db.add(Section(
        id=str(uuid.uuid4()),
        pv_id=pv_id,
        title="Summary",
        content=summary,
        type="discussion",
        order=0
    ))

    # Save decisions as individual sections for PDF generation
    for idx, decision in enumerate(decisions_list):
        db.add(Section(
            id=str(uuid.uuid4()),
            pv_id=pv_id,
            title=f"Decision {idx+1}",
            content=decision,
            type="decision",
            order=idx + 1
        ))

    for action_item in pv_data.get("actions", []):
        db.add(
            Action(
                id=str(uuid.uuid4()),
                meeting_id=str(recording.meeting_id),
                title=action_item.get("description", "N/A"),
                description=action_item.get("priority_reason", ""),
                status="pending",
            )
        )
    
    await db.flush()

    # Automatically generate ML Action Suggestions
    try:
        from app.services.action_service import ActionService
        logger.info(f"Triggering ML action suggestions for meeting {recording.meeting_id}")
        action_service = ActionService(db)
        await action_service.generate_suggestions_from_transcription(str(recording.meeting_id))
    except Exception as e:
        logger.error(f"Failed to generate action suggestions: {e}")
        pass


async def _notify_n8n_completion(recording_id: str, meeting_id: str) -> None:
    payload = {
        "event": "transcription.completed",
        "recording_id": recording_id,
        "meeting_id": meeting_id,
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json=payload
            )
    except Exception as e:
        logger.error(f"Failed to notify n8n: {e}")


@celery_app.task(name="process_recording")
def process_recording(recording_id: str) -> None:
    """Celery task wrapper for the async pipeline"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not loop.is_running():
        loop.run_until_complete(_process_recording_pipeline(recording_id))
    else:
        asyncio.ensure_future(_process_recording_pipeline(recording_id), loop=loop)
