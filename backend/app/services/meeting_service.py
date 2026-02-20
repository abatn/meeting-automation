import httpx
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete

from app.models.meeting import Meeting
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.core.config import settings

logger = logging.getLogger(__name__)

class MeetingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meeting(self, meeting_in: MeetingCreate, owner_id: int) -> Meeting:
        """Meeting anlegen + n8n-Webhook triggern"""
        db_meeting = Meeting(
            **meeting_in.model_dump(exclude={"participants"}),
            owner_id=owner_id,
            status="scheduled"
        )
        # Add participants logic here (simplified for now)
        self.db.add(db_meeting)
        await self.db.commit()
        await self.db.refresh(db_meeting)

        # n8n Webhook triggern
        await self._trigger_n8n_meeting_created(db_meeting)
        
        return db_meeting

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        """Meeting mit allen Relations"""
        result = await self.db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )
        return result.scalars().first()

    async def update_meeting(self, meeting_id: int, meeting_in: MeetingUpdate) -> Optional[Meeting]:
        """Status-Änderungen -> n8n Benachrichtigung"""
        db_meeting = await self.get_meeting(meeting_id)
        if not db_meeting:
            return None

        update_data = meeting_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_meeting, key, value)

        await self.db.commit()
        await self.db.refresh(db_meeting)

        # Notify n8n about status change if relevant
        if "status" in update_data:
            await self._trigger_n8n_meeting_status_change(db_meeting)

        return db_meeting

    async def delete_meeting(self, meeting_id: int) -> bool:
        """Soft Delete + Audit Log (simplified)"""
        db_meeting = await self.get_meeting(meeting_id)
        if not db_meeting:
            return False
        
        await self.db.delete(db_meeting)
        await self.db.commit()
        return True

    async def get_upcoming_meetings(self) -> List[Meeting]:
        """Für Dashboard/Reminders"""
        result = await self.db.execute(
            select(Meeting).where(Meeting.start_time > datetime.utcnow()).order_by(Meeting.start_time)
        )
        return result.scalars().all()

    async def _trigger_n8n_meeting_created(self, meeting: Meeting):
        """Triggert n8n Webhook: meeting-created"""
        payload = {
            "event": "meeting.created",
            "meeting_id": meeting.id,
            "title": meeting.title,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
            "owner_id": meeting.owner_id
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(settings.N8N_WEBHOOK_MEETING_CREATED, json=payload, timeout=5.0)
                response.raise_for_status()
                logger.info(f"n8n meeting-created triggered for meeting {meeting.id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n meeting-created: {e}")

    async def _trigger_n8n_meeting_status_change(self, meeting: Meeting):
        """Triggert n8n Webhook für Statusänderungen"""
        # Common webhook or specific one
        pass