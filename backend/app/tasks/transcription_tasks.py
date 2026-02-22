import logging
import httpx
import asyncio
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.recording import Recording
from app.models.transcription import Transcription
from app.models.action import Action
from app.models.meeting import Meeting

logger = logging.getLogger(__name__)

async def _process_recording_pipeline(recording_id: str):
    """
    Internal async function to handle the full pipeline:
    Whisper (Transcription) -> Mistral (Analysis) -> DB (Save) -> n8n (Notify)
    """
    async with SessionLocal() as db:
        # 1. Get recording details
        result = await db.execute(select(Recording).where(Recording.id == recording_id))
        recording = result.scalar_one_or_none()
        
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            return

        # Update status
        recording.status = "transcribing"
        await db.commit()

        try:
            # 2. Call Whisper API
            async with httpx.AsyncClient() as client:
                # In a real scenario, we'd download from S3 first or pass S3 URL
                # For now, we assume Whisper can access the same storage or we stream it
                # Mocking the call for now
                logger.info(f"Starting transcription for recording {recording_id}")
                
                # Update: Real call to Whisper
                # files = {'file': open(recording.file_path, 'rb')} # Simplified
                # response = await client.post(f"{settings.WHISPER_API_URL}/transcribe", files=files)
                
                await asyncio.sleep(2) # Simulate work
                transcription_text = "Dies ist ein Test-Protokoll der Sitzung. Teilnehmer: Herr Schmidt, Frau Müller. Beschluss: Das Budget wird erhöht. Aufgabe: Herr Schmidt kontaktiert die Bank bis Freitag."
                
                # 3. Save Transcription
                db_transcription = Transcription(
                    recording_id=recording_id,
                    text=transcription_text,
                    language="de"
                )
                db.add(db_transcription)
                recording.status = "analyzing"
                await db.commit()
                await db.refresh(db_transcription)

                # 4. Call Mistral for Analysis (Actions)
                logger.info(f"Starting analysis for transcription {db_transcription.id}")
                analysis_payload = {
                    "text": transcription_text,
                    "task": "extract_actions",
                    "context": {"meeting_id": recording.meeting_id}
                }
                
                # Mocking Mistral call
                # mistral_res = await client.post(f"{settings.MISTRAL_API_URL}/analyze", json=analysis_payload)
                # actions_data = mistral_res.json()["actions"]
                
                await asyncio.sleep(1) # Simulate work
                actions_data = [
                    {
                        "description": "Bank kontaktieren",
                        "assignee_name": "Schmidt",
                        "due_date": "2024-03-01"
                    }
                ]

                # 5. Save Actions
                for action_item in actions_data:
                    db_action = Action(
                        meeting_id=recording.meeting_id,
                        description=action_item["description"],
                        status="pending"
                    )
                    db.add(db_action)

                recording.status = "completed"
                await db.commit()
                logger.info(f"Pipeline completed for recording {recording_id}")

                # 6. Final Notification to n8n
                await _notify_n8n_completion(recording_id, recording.meeting_id)

        except Exception as e:
            logger.error(f"Error in transcription pipeline: {e}")
            recording.status = "failed"
            await db.commit()

async def _notify_n8n_completion(recording_id: str, meeting_id: str):
    payload = {
        "event": "transcription.completed",
        "recording_id": recording_id,
        "meeting_id": meeting_id
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(settings.N8N_WEBHOOK_URL, json=payload)
    except Exception as e:
        logger.error(f"Failed to notify n8n: {e}")

@celery_app.task(name="process_recording")
def process_recording(recording_id: str):
    """Celery task wrapper for the async pipeline"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_process_recording_pipeline(recording_id))