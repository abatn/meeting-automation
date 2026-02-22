import httpx
import logging
import boto3
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.models.recording import Recording
from app.core.config import settings

logger = logging.getLogger(__name__)

class RecordingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY
        )

    async def upload_recording(self, meeting_id: str, file: UploadFile) -> Recording:
        """Audio zu Minio/S3 hochladen"""
        file_key = f"recordings/{meeting_id}/{uuid.uuid4()}_{file.filename}"
        
        # S3 Upload
        try:
            self.s3_client.upload_fileobj(
                file.file,
                settings.S3_BUCKET_NAME,
                file_key
            )
            logger.info(f"File {file.filename} uploaded to S3: {file_key}")
        except Exception as e:
            logger.error(f"S3 Upload failed: {e}")
            raise

        # Save to DB
        db_recording = Recording(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            file_path=file_key,
            status="uploaded",
            format=file.content_type
        )
        self.db.add(db_recording)
        await self.db.commit()
        await self.db.refresh(db_recording)

        # Trigger n8n Webhook
        await self.after_upload(db_recording)

        # Trigger Celery Pipeline
        from app.tasks.transcription_tasks import process_recording
        process_recording.delay(db_recording.id)
        
        return db_recording

    async def after_upload(self, recording: Recording):
        """n8n-Webhook 'audio-uploaded' mit file_id triggern"""
        payload = {
            "event": "audio.uploaded",
            "recording_id": recording.id,
            "meeting_id": recording.meeting_id,
            "file_path": recording.file_path,
            "callback_url": f"{settings.BACKEND_CALLBACK_URL}/transcription-complete"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.N8N_WEBHOOK_AUDIO_UPLOADED, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(f"n8n audio-uploaded triggered for recording {recording.id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n audio-uploaded: {e}")

    async def get_recording_status(self, recording_id: int) -> Optional[str]:
        """Status von n8n/Whisper abfragen (simplified)"""
        # Status usually comes via webhook or we check DB
        pass

    async def handle_transcription_callback(self, recording_id: int, transcription_text: str):
        """Webhook von n8n empfangen"""
        # Logic to save transcription and update recording status
        pass