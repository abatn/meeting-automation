import logging
import httpx
import asyncio
import json
import redis
import uuid
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import tempfile # Neu hinzugefügt
import os # Neu hinzugefügt

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.models.action import Action
from app.models.meeting import Meeting
from app.models.pv import PV
from app.services.transcription_service import transcribe_audio
from app.services.pv_service import PVService
from app.services.diarization_service import DiarizationService
from app.services.pdf_service import PDFService
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

redis_client = redis.Redis.from_url(settings.REDIS_URL)

def publish_status(recording_id: str, status: str, progress: int, message: str = ""):
    """Hilfsfunktion, um Status-Updates an Redis zu senden (für WebSockets)"""
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

def match_timestamps(words: List[Dict[str, Any]], segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Match Whisper words with Pyannote segments based on time midpoint.
    Groups matched words into text blocks by speaker.
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
    publish_status(recording_id, "uploaded", 0, "Audio hochgeladen, starte Verarbeitung...")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            publish_status(recording_id, "failed", 0, "Recording in DB nicht gefunden")
            return

        recording.status = "transcribing"
        await db.commit()

        try:
            # 1. Download Audio from S3 (Minio)
            publish_status(recording_id, "transcribing", 10, "Lade Audio-Datei herunter...")
            s3_client = boto3.client(
                's3',
                endpoint_url=getattr(settings, 'S3_ENDPOINT', 'http://minio:9000'),
                aws_access_key_id=getattr(settings, 'S3_ACCESS_KEY', 'minio_user'),
                aws_secret_access_key=getattr(settings, 'S3_SECRET_KEY', 'minio_password')
            )
            bucket = getattr(settings, 'S3_BUCKET_NAME', 'meeting-recordings')
            file_key = recording.file_path
            
            try:
                response = s3_client.get_object(Bucket=bucket, Key=file_key)
                # Schreibe den Stream direkt in eine temporäre Datei
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
                    for chunk in response['Body'].iter_chunks(chunk_size=1024 * 1024): # 1MB chunks
                        temp_audio_file.write(chunk)
                    temp_audio_file_path = temp_audio_file.name
            except ClientError as e:
                error_msg = f"S3-Download fehlgeschlagen für {file_key}: {e}"
                logger.critical(error_msg)
                recording.status = "failed"
                await db.commit()
                publish_status(recording_id, "failed", 0, error_msg)
                return

            # 2. Speaker Diarization (Pyannote)
            publish_status(recording_id, "transcribing", 25, "Sprechererkennung läuft...")
            logger.info("Running Diarization...")
            speaker_segments = await DiarizationService.diarize(temp_audio_file_path)

            # 3. Whisper Transcription with word timestamps
            publish_status(recording_id, "transcribing", 50, "Audio wird in Text umgewandelt...")
            logger.info("Running Whisper...")
            
            transcription_result = await transcribe_audio(temp_audio_file_path, word_timestamps=True)

            if not speaker_segments:
                words = transcription_result.get("words", [])
                end_time = words[-1].get("end", 0.0) if words else 0.0
                speaker_segments = [{"speaker": "SPEAKER_00", "start": 0.0, "end": end_time}]
                logger.warning(f"Diarization returned no segments. Using fallback single speaker up to {end_time}s.")

            publish_status(recording_id, "transcribing", 75, "Kombiniere Text und Sprecher...")
            
            # 4. Match Timestamps
            matched_blocks = match_timestamps(transcription_result.get("words", []), speaker_segments)
            
            # Format for Mistral
            if matched_blocks:
                mistral_input_text = "\n".join([f"{block['speaker']}: {block['text']}" for block in matched_blocks])
            else:
                mistral_input_text = transcription_result.get("text", "")
            
            # Fallback for DB segments if matching failed
            db_segments = matched_blocks if matched_blocks else None

            # 5. Save Transcription
            db_transcription = Transcription(
                id=str(uuid.uuid4()),
                recording_id=recording_id,
                meeting_id=recording.meeting_id,
                full_text=transcription_result.get("text", ""),
                language="de",
                segments=db_segments
            )
            db.add(db_transcription)
            recording.status = "analyzing"
            await db.commit()
            await db.refresh(db_transcription)

            # 6. Call Mistral for Analysis (PV & Actions)
            publish_status(recording_id, "analyzing", 90, "KI analysiert das Protokoll (Mistral)...")
            logger.info(f"Starting analysis for transcription {db_transcription.id}")
            
            pv_data = await PVService.generate_pv(mistral_input_text)
            
            # Format PV content as HTML and save to DB
            summary = pv_data.get('summary', '')
            decisions = '<br/>'.join([f'- {d}' for d in pv_data.get('decisions', [])])
            html_content = f"<h3>Résumé</h3><p>{summary}</p><h3>Décisions</h3><p>{decisions}</p>"

            # Check if PV already exists to prevent UniqueViolationError
            existing_pv_result = await db.execute(select(PV).where(PV.meeting_id == recording.meeting_id))
            existing_pv = existing_pv_result.scalar_one_or_none()

            if existing_pv:
                existing_pv.title = pv_data.get('title', 'Meeting PV')
                existing_pv.content_html = html_content
                existing_pv.status = 'draft'
                logger.info(f"Updated existing PV for meeting {recording.meeting_id}")
            else:
                db_pv = PV(
                    id=str(uuid.uuid4()),
                    meeting_id=recording.meeting_id,
                    title=pv_data.get('title', 'Meeting PV'),
                    content_html=html_content,
                    status='draft'
                )
                db.add(db_pv)
                logger.info(f"Created new PV for meeting {recording.meeting_id}")
            
            actions_data = pv_data.get("actions", [])

            # Save Actions
            for action_item in actions_data:
                db_action = Action(
                    id=str(uuid.uuid4()),
                    meeting_id=recording.meeting_id,
                    title=action_item["description"],
                    description=action_item.get("priority_reason", ""),
                    status="pending"
                )
                db.add(db_action)

            recording.status = "completed"
            await db.commit()
            logger.info(f"Pipeline completed for recording {recording_id}")

            publish_status(recording_id, "completed", 100, "Verarbeitung erfolgreich abgeschlossen!")

            # Final Notification to n8n
            await _notify_n8n_completion(recording_id, recording.meeting_id)

        except Exception as e:
            logger.error(f"Error in transcription pipeline: {e}")
            recording.status = "failed"
            await db.commit()
            publish_status(recording_id, "failed", 0, f"Fehler aufgetreten: {str(e)}")
        finally:
            # Clean up temporary audio file
            if 'temp_audio_file_path' in locals() and os.path.exists(temp_audio_file_path):
                os.remove(temp_audio_file_path)
                logger.info(f"Temporäre Datei gelöscht: {temp_audio_file_path}")

async def _notify_n8n_completion(recording_id: str, meeting_id: str):
    payload = {
        "event": "transcription.completed",
        "recording_id": recording_id,
        "meeting_id": meeting_id
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json=payload)
    except Exception as e:
        logger.error(f"Failed to notify n8n: {e}")

@celery_app.task(name="process_recording")
def process_recording(recording_id: str):
    """Celery task wrapper for the async pipeline"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_process_recording_pipeline(recording_id))
