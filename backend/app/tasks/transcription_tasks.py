import logging
from typing import Optional
from datetime import datetime

from backend.app.tasks.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal # Corrected import
from backend.app.models.recording import Recording, RecordingStatus
from backend.app.models.transcription import Transcription, TranscriptionStatus
from backend.app.models.action import Action, ActionStatus
from backend.app.services.whisper_client import whisper_client
from backend.app.services.mistral_client import mistral_client
from backend.app.services.notification_service import notification_service
from backend.app.services.action_service import action_service
from backend.app.utils.storage import storage_service
from sqlalchemy.future import select
import json
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta # Added timedelta import

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def process_audio_recording(self, recording_id: int):
    logger.info(f"Starting process_audio_recording for recording ID: {recording_id}")
    async with SessionLocal() as db: # Corrected to SessionLocal
        recording = await db.get(Recording, recording_id)
        if not recording:
            logger.error(f"Recording with ID {recording_id} not found.")
            return

        try:
            recording.status = RecordingStatus.PROCESSING
            db.add(recording)
            await db.commit()
            await db.refresh(recording)

            audio_path = await storage_service.get_s3_download_url(recording.file_path)
            if not audio_path:
                raise ValueError(f"Audio file URL not found for recording ID {recording_id}")

            # Step 1: Run Whisper Transcription
            transcription_content = await run_whisper_transcription.delay(audio_path, recording.language)
            if not transcription_content:
                raise ValueError("Whisper transcription failed.")

            # Create Transcription entry
            transcription = Transcription(
                meeting_id=recording.meeting_id,
                recording_id=recording.id,
                content=transcription_content,
                language=recording.language,
                status=TranscriptionStatus.COMPLETED
            )
            db.add(transcription)
            await db.commit()
            await db.refresh(transcription)
            logger.info(f"Transcription created for recording {recording_id}, transcription ID: {transcription.id}")

            # Step 2: Generate Speaker Diarization (if enabled)
            if settings.ENABLE_SPEAKER_DIARIZATION:
                await generate_speaker_diarization.delay(transcription.id)

            # Step 3: Detect Code-Switching (if enabled)
            if settings.ENABLE_CODE_SWITCHING_DETECTION:
                await detect_code_switching.delay(transcription.id)

            # Step 4: Extract Actions from Transcription
            await extract_actions_from_transcription.delay(transcription.id)

            recording.status = RecordingStatus.TRANSCRIBED
            await db.commit()
            await db.refresh(recording)
            logger.info(f"Finished process_audio_recording for recording ID: {recording_id}")

        except Exception as exc:
            logger.error(f"Error processing audio recording {recording_id}: {exc}")
            recording.status = RecordingStatus.FAILED
            db.add(recording) # Add recording to session before commit
            await db.commit()
            await db.refresh(recording)
            await notification_service.send_error_notification(
                f"Transcription failed for recording {recording_id}", str(exc)
            )
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def run_whisper_transcription(self, audio_path: str, language: str) -> Optional[str]:
    logger.info(f"Starting run_whisper_transcription for audio: {audio_path}")
    try:
        transcription_content = await whisper_client.transcribe_audio(audio_path, language)
        logger.info(f"Whisper transcription completed for audio: {audio_path}")
        return transcription_content
    except Exception as exc:
        logger.error(f"Error running Whisper transcription for {audio_path}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def generate_speaker_diarization(self, transcription_id: int):
    logger.info(f"Starting generate_speaker_diarization for transcription ID: {transcription_id}")
    async with SessionLocal() as db:
        transcription = await db.get(Transcription, transcription_id)
        if not transcription:
            logger.warning(f"Transcription with ID {transcription_id} not found for diarization.")
            return

        try:
            # Placeholder for actual diarization logic
            # This would typically involve calling another AI service or a local model
            diarization_result = {"speakers": [{"id": 1, "name": "Speaker 1"}, {"id": 2, "name": "Speaker 2"}]}
            transcription.speaker_diarization = json.dumps(diarization_result)
            db.add(transcription) # Add transcription to session before commit
            await db.commit()
            await db.refresh(transcription)
            logger.info(f"Speaker diarization generated for transcription ID: {transcription_id}")
        except Exception as exc:
            logger.error(f"Error generating speaker diarization for transcription {transcription_id}: {exc}")
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def detect_code_switching(self, transcription_id: int):
    logger.info(f"Starting detect_code_switching for transcription ID: {transcription_id}")
    async with SessionLocal() as db:
        transcription = await db.get(Transcription, transcription_id)
        if not transcription:
            logger.warning(f"Transcription with ID {transcription_id} not found for code-switching detection.")
            return

        try:
            # Placeholder for actual code-switching detection logic
            # This would typically involve calling another AI service
            code_switching_result = {"detected": True, "segments": [{"start": 10, "end": 15, "language": "de"}]}
            transcription.code_switching_detection = json.dumps(code_switching_result)
            db.add(transcription) # Add transcription to session before commit
            await db.commit()
            await db.refresh(transcription)
            logger.info(f"Code-switching detection completed for transcription ID: {transcription_id}")
        except Exception as exc:
            logger.error(f"Error detecting code-switching for transcription {transcription_id}: {exc}")
            raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def extract_actions_from_transcription(self, transcription_id: int):
    logger.info(f"Starting extract_actions_from_transcription for transcription ID: {transcription_id}")
    async with SessionLocal() as db:
        transcription = await db.get(Transcription, transcription_id)
        if not transcription:
            logger.warning(f"Transcription with ID {transcription_id} not found for action extraction.")
            return

        try:
            # Use Mistral client to extract action points
            action_points_json_str = await mistral_client.extract_action_points(transcription.content)
            if action_points_json_str:
                action_points = json.loads(action_points_json_str)
                for ap_description in action_points:
                    # Simplified action creation - in a real scenario, parsing assignee/deadline would be more complex
                    action_data = {
                        "description": ap_description,
                        "meeting_id": transcription.meeting_id,
                        "assigned_to": None, # Needs to be determined, perhaps from diarization or meeting participants
                        "due_date": datetime.utcnow() + timedelta(days=7), # Default due date
                        "priority": 3
                    }
                    # For now, we'll just log the action point. Actual creation would involve action_service.create_action
                    logger.info(f"Extracted action point for meeting {transcription.meeting_id}: {ap_description}")
            else:
                logger.info(f"No action points extracted from transcription {transcription_id}.")
            
            transcription.actions_extracted = True # Assuming a field to mark this
            db.add(transcription) # Add transcription to session before commit
            await db.commit()
            await db.refresh(transcription)
            logger.info(f"Action extraction completed for transcription ID: {transcription_id}")
        except Exception as exc:
            logger.error(f"Error extracting actions from transcription {transcription_id}: {exc}")
            raise self.retry(exc=exc)
