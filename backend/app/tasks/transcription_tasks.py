import logging
import asyncio
import json
import uuid
import os
import tempfile
from typing import Dict, Any, List, Optional
import httpx
import redis
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.models.action import Action
from app.models.pv import PV
from app.services.transcription_service import transcribe_audio
from app.services.pv_service import PVService
from app.services.diarization_service import DiarizationService


logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.REDIS_URL)


def publish_status(recording_id: str, status: str, progress: int, message: str = ""):
    """Hilfsfunktion, um Status-Updates an Redis zu senden"""
    try:
        channel = f"transcription_status_{recording_id}"
        payload = {
            "status": status,
            "progress": progress,
            "message": message
        }
        redis_client.publish(channel, json.dumps(payload))
    except Exception as e:
        logger.error(f"Redis publish failed for {recording_id}: {e}")


def match_timestamps(
    words: List[Dict[str, Any]], segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Match Whisper words with Pyannote segments based on time midpoint.
    """
    if not segments or not words:
        return []

    segments.sort(key=lambda x: x['start'])
    matched_blocks = []
    current_block = None

    for word_info in words:
        word = word_info.get("word", "")
        start = word_info.get("start", 0.0)
        end = word_info.get("end", 0.0)
        midpoint = (start + end) / 2

        closest_segment = None
        for seg in segments:
            if seg['start'] <= midpoint <= seg['end']:
                closest_segment = seg
                break

        if not closest_segment:
            closest_segment = min(
                segments,
                key=lambda s: min(abs(s['start'] - midpoint), abs(s['end'] - midpoint))
            )

        speaker = closest_segment['speaker']

        if current_block is None or current_block['speaker'] != speaker:
            if current_block:
                matched_blocks.append(current_block)
            current_block = {
                "speaker": speaker,
                "text": word.strip(),
                "start": start,
                "end": end
            }
        else:
            current_block['text'] += " " + word.strip()
            current_block['end'] = end

    if current_block:
        matched_blocks.append(current_block)
    return matched_blocks


async def _process_recording_pipeline(recording_id: str):
    publish_status(recording_id, "uploaded", 0, "Audio hochgeladen...")

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()

        if not recording:
            logger.error(f"Recording {recording_id} not found")
            publish_status(recording_id, "failed", 0, "Recording nicht gefunden")
            return

        recording.status = "transcribing"
        await db.commit()

        try:
            # 1. Download
            temp_path = await _download_audio(recording.file_path)
            if not temp_path:
                publish_status(recording_id, "failed", 0, "S3-Download Fehler")
                return

            # 2. Diarization
            publish_status(recording_id, "transcribing", 25, "Sprechererkennung...")
            speaker_segments = await DiarizationService.diarize(temp_path)

            # 3. Whisper
            publish_status(recording_id, "transcribing", 50, "Transkription...")
            trans_res = await transcribe_audio(temp_path, word_timestamps=True)

            # 4. Processing
            publish_status(recording_id, "transcribing", 75, "Verarbeitung...")
            await _handle_ai_results(db, recording, speaker_segments, trans_res)

            publish_status(recording_id, "completed", 100, "Erfolgreich!")
            await _notify_n8n_completion(recording_id, recording.meeting_id)

        except Exception as e:
            logger.error(f"Error in transcription pipeline: {e}")
            recording.status = "failed"
            await db.commit()
            publish_status(recording_id, "failed", 0, "Fehler aufgetreten")
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)


async def _download_audio(file_key: str) -> Optional[str]:
    s3_client = boto3.client(
        's3',
        endpoint_url=getattr(settings, 'S3_ENDPOINT', 'http://minio:9000'),
        aws_access_key_id=getattr(settings, 'S3_ACCESS_KEY', 'minio_user'),
        aws_secret_access_key=getattr(settings, 'S3_SECRET_KEY', 'minio_password')
    )
    bucket = getattr(settings, 'S3_BUCKET_NAME', 'meeting-recordings')
    try:
        response = s3_client.get_object(Bucket=bucket, Key=file_key)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            for chunk in response['Body'].iter_chunks(1024 * 1024):
                tmp.write(chunk)
            return tmp.name
    except ClientError as e:
        logger.critical(f"S3-Download fehlgeschlagen: {e}")
        return None


async def _handle_ai_results(db, recording, speaker_segments, trans_res):
    if not speaker_segments:
        words = trans_res.get("words", [])
        end_time = words[-1].get("end", 0.0) if words else 0.0
        speaker_segments = [{"speaker": "SPEAKER_00", "start": 0.0, "end": end_time}]

    matched = match_timestamps(trans_res.get("words", []), speaker_segments)
    mistral_text = "\n".join([f"{b['speaker']}: {b['text']}" for b in matched]) \
        if matched else trans_res.get("text", "")

    db_trans = Transcription(
        id=str(uuid.uuid4()),
        recording_id=recording.id,
        meeting_id=recording.meeting_id,
        full_text=trans_res.get("text", ""),
        language="de",
        segments=matched if matched else None
    )
    db.add(db_trans)
    recording.status = "analyzing"
    await db.commit()

    pv_data = await PVService.generate_pv(mistral_text)
    await _save_pv_and_actions(db, recording, pv_data)
    recording.status = "completed"
    await db.commit()


async def _save_pv_and_actions(db, recording, pv_data):
    summary = pv_data.get('summary', '')
    decisions = '<br/>'.join([f'- {d}' for d in pv_data.get('decisions', [])])
    html = f"<h3>Résumé</h3><p>{summary}</p><h3>Décisions</h3><p>{decisions}</p>"

    existing_pv_res = await db.execute(
        select(PV).where(PV.meeting_id == recording.meeting_id)
    )
    existing_pv = existing_pv_res.scalar_one_or_none()

    if existing_pv:
        existing_pv.title = pv_data.get('title', 'Meeting PV')
        existing_pv.content_html = html
    else:
        db_pv = PV(
            id=str(uuid.uuid4()),
            meeting_id=recording.meeting_id,
            title=pv_data.get('title', 'Meeting PV'),
            content_html=html,
            status='draft'
        )
        db.add(db_pv)

    for action_item in pv_data.get("actions", []):
        db.add(Action(
            id=str(uuid.uuid4()),
            meeting_id=recording.meeting_id,
            title=action_item["description"],
            description=action_item.get("priority_reason", ""),
            status="pending"
        ))


async def _notify_n8n_completion(recording_id: str, meeting_id: str):
    payload = {
        "event": "transcription.completed",
        "recording_id": recording_id,
        "meeting_id": meeting_id
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json=payload
            )
    except Exception as e:
        logger.error(f"Failed to notify n8n: {e}")


@celery_app.task(name="process_recording")
def process_recording(recording_id: str):
    """Celery task wrapper for the async pipeline"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_process_recording_pipeline(recording_id))
