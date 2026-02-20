import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.meeting import Meeting
from app.schemas.meeting import MeetingCreate
import logging

logger = logging.getLogger(__name__)

class MeetingService:
    @staticmethod
    async def create_meeting(db: AsyncSession, meeting_in: MeetingCreate):
        # Implementation to save meeting to DB (omitted for brevity)
        meeting = Meeting(**meeting_in.model_dump())
        # db.add(meeting)
        # await db.commit()
        
        # Trigger n8n Workflow
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.N8N_WEBHOOK_URL}/meeting-created",
                    json=meeting_in.model_dump()
                )
        except Exception as e:
            logger.error(f"Failed to trigger n8n meeting-created: {e}")
            
        return meeting

    @staticmethod
    async def handle_audio_upload(meeting_id: int, file_id: str):
        # Trigger n8n for transcription
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.N8N_WEBHOOK_URL}/audio-uploaded",
                    json={"meeting_id": meeting_id, "file_id": file_id}
                )
        except Exception as e:
            logger.error(f"Failed to trigger n8n audio-uploaded: {e}")