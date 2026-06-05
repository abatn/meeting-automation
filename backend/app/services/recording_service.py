import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
import boto3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile

from app.models.recording import Recording
from app.models.meeting import Meeting
from app.core.config import settings

logger = logging.getLogger(__name__)


class RecordingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )

    async def upload_recording(
        self, meeting_id: str, client_id: str, file: UploadFile, recording_id: Optional[str] = None
    ) -> Recording:
        """Audio zu Minio/S3 hochladen und DB aktualisieren/erstellen

        Multi-Tenant Isolation: file_key = "{client_id}/recordings/{meeting_id}/{uuid}_{filename}"
        Backward-Compatible: Alte recordings/{meeting_id}/... keys bleiben lesbar, aber Uploads
        verwenden neuen Prefix.
        """
        file_key = f"{client_id}/recordings/{meeting_id}/{uuid.uuid4()}_{file.filename}"

        # S3 Upload
        try:
            self.s3_client.upload_fileobj(file.file, settings.S3_BUCKET_NAME, file_key)
            logger.info(f"File {file.filename} uploaded to S3: {file_key}")
        except Exception as e:
            logger.error(f"S3 Upload failed: {e}")
            raise

        db_recording = None

        if recording_id:
            result = await self.db.execute(
                select(Recording).where(Recording.id == recording_id).where(Recording.client_id == client_id)
            )
            db_recording = result.scalar_one_or_none()

        if db_recording:
            # Update existing record
            db_recording.file_path = file_key
            db_recording.status = "uploaded"
            db_recording.format = file.content_type or "unknown"
        else:
            # Save new to DB
            db_recording = Recording(
                id=recording_id or str(uuid.uuid4()),
                client_id=client_id,
                meeting_id=meeting_id,
                file_path=file_key,
                status="uploaded",  # Ensure status is always a string
                format=file.content_type,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(db_recording)

        await self.db.commit()
        await self.db.refresh(db_recording)

        # Trigger n8n audio-uploaded webhook (P1-11: after_upload hook aufrufen)
        await self.after_upload(db_recording)

        # Trigger Celery Pipeline
        from app.tasks.transcription_tasks import process_recording

        process_recording.delay(db_recording.id, str(db_recording.client_id))

        return db_recording

    async def start_stream(
        self, meeting_id: str, client_id: str, content_type: str = "audio/webm"
    ) -> dict:
        """
        Start a recording session by using a local temporary file to
        bypass S3 5MB limits.

        Multi-Tenant Isolation: file_key = "{client_id}/recordings/{meeting_id}/..."
        """
        file_key = f"{client_id}/recordings/{meeting_id}/{uuid.uuid4()}_stream.webm"
        upload_id = str(uuid.uuid4())  # Use UUID as local temp file identifier
        try:
            # Update Meeting start_time to the exact moment recording starts
            meeting_result = await self.db.execute(
                select(Meeting).where(Meeting.id == meeting_id)
            )
            meeting = meeting_result.scalar_one_or_none()
            if meeting:
                meeting.start_time = datetime.now(timezone.utc)
                logger.info(f"Updated meeting {meeting.id} start_time to {meeting.start_time}")

            # Save placeholder to DB
            db_recording = Recording(
                id=str(uuid.uuid4()),
                client_id=client_id,
                meeting_id=meeting_id,
                file_path=file_key,
                status="streaming",
                format=content_type,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(db_recording)
            await self.db.commit()

            # Ensure temp directory exists
            os.makedirs("/tmp/recordings", exist_ok=True)

            # Create the empty temp file
            open(f"/tmp/recordings/{upload_id}.webm", "wb").close()

            return {
                "recording_id": db_recording.id,
                "upload_id": upload_id,
                "file_key": file_key,
            }
        except Exception as e:
            logger.error(f"Failed to start recording session: {e}")
            raise

    async def upload_chunk(
        self, file_key: str, upload_id: str, part_number: int, file_bytes: bytes
    ) -> str:
        """Append the incoming chunk to the local temporary file."""
        try:
            temp_path = f"/tmp/recordings/{upload_id}.webm"
            with open(temp_path, "ab") as f:
                f.write(file_bytes)
            return f"local-chunk-{part_number}"
        except Exception as e:
            logger.error(f"Local chunk append failed: {e}")
            raise

    async def stop_stream(
        self, recording_id: str, client_id: str, file_key: str, upload_id: str, parts: list
    ) -> Recording:
        """Upload the fully assembled local file to S3 and trigger processing."""
        temp_path = f"/tmp/recordings/{upload_id}.webm"
        try:
            if not os.path.exists(temp_path):
                raise Exception(f"Temporary file {temp_path} not found.")

            # Upload the complete file to MinIO
            with open(temp_path, "rb") as f:
                self.s3_client.upload_fileobj(f, settings.S3_BUCKET_NAME, file_key)
            logger.info(f"Successfully uploaded assembled file to {file_key}")

            # Clean up local temp file
            os.remove(temp_path)

        except Exception as e:
            logger.error(f"Failed to upload assembled file to S3: {e}")
            raise

        result = await self.db.execute(
            select(Recording).where(Recording.id == recording_id).where(Recording.client_id == client_id)
        )
        db_recording = result.scalar_one_or_none()

        if not db_recording:
            raise Exception("Recording not found in DB")

        db_recording.status = "uploaded"

        # Update Meeting end_time (with client_id check for multi-tenant isolation)
        meeting_result = await self.db.execute(
            select(Meeting).where(Meeting.id == db_recording.meeting_id).where(Meeting.client_id == client_id)
        )
        meeting = meeting_result.scalar_one_or_none()
        if meeting:
            meeting.end_time = datetime.now(timezone.utc)
            logger.info(f"Updated meeting {meeting.id} end_time to {meeting.end_time}")

        await self.db.commit()

        # Trigger Celery Pipeline
        from app.tasks.transcription_tasks import process_recording

        process_recording.delay(db_recording.id, str(db_recording.client_id))

        return db_recording

    async def after_upload(self, recording: Recording):
        """n8n-Webhook 'audio-uploaded' mit file_id triggern"""
        payload = {
            "event": "audio.uploaded",
            "recording_id": recording.id,
            "meeting_id": recording.meeting_id,
            "file_path": recording.file_path,
            "callback_url": f"{settings.BACKEND_CALLBACK_URL}/transcription-complete",
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.N8N_WEBHOOK_AUDIO_UPLOADED, json=payload, timeout=5.0
                )
                response.raise_for_status()
                logger.info(
                    f"n8n audio-uploaded triggered for recording {recording.id}"
                )
        except Exception as e:
            logger.error(f"Failed to trigger n8n audio-uploaded: {e}")

    def get_presigned_upload_url(
        self, file_key: str, expires_in: int = 3600
    ) -> str:
        """Generate presigned URL for direct frontend-to-MinIO upload
        
        Args:
            file_key: S3/MinIO file key (includes client_id prefix)
            expires_in: URL expiry time in seconds (default: 1 hour)
        
        Returns:
            Presigned URL for direct upload
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_key},
                ExpiresIn=expires_in,
            )
            logger.info(f"Generated presigned upload URL for {file_key}")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def get_presigned_download_url(
        self, file_key: str, expires_in: int = 3600
    ) -> str:
        """Generate presigned URL for direct frontend-from-MinIO download
        
        Args:
            file_key: S3/MinIO file key
            expires_in: URL expiry time in seconds (default: 1 hour)
        
        Returns:
            Presigned URL for direct download
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_key},
                ExpiresIn=expires_in,
            )
            logger.info(f"Generated presigned download URL for {file_key}")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def get_recording_status(self, recording_id: str) -> Optional[str]:
        """Status von n8n/Whisper abfragen (simplified)"""
        # Status usually comes via webhook or we check DB
        return None

    async def handle_transcription_callback(
        self, recording_id: str, transcription_text: str
    ):
        """Webhook von n8n empfangen"""
        # Logic to save transcription and update recording status (TBD)
        pass
