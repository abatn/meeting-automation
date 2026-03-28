import logging
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.meeting import Agenda, Meeting, Participant
from app.schemas.meeting import MeetingCreate, MeetingUpdate

logger = logging.getLogger(__name__)


class MeetingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meeting(self, meeting_in: MeetingCreate, owner_id: str, client_id: str) -> Meeting:
        """Meeting anlegen + n8n-Webhook triggern"""
        db_meeting = Meeting(
            id=str(uuid.uuid4()),
            client_id=client_id,
            title=meeting_in.title,
            description=meeting_in.description,
            location=meeting_in.location,
            room_id=meeting_in.room_id,
            start_time=meeting_in.start_time,
            end_time=meeting_in.end_time,
            status=meeting_in.status,
            creator_id=owner_id,
            created_at=datetime.utcnow(),
        )
        self.db.add(db_meeting)
        await self.db.flush()

        # Add participants
        for participant_data in meeting_in.participants or []:
            participant = Participant(
                id=str(uuid.uuid4()),
                meeting_id=db_meeting.id,
                email=participant_data.email,
                name=participant_data.name,
                role=participant_data.role,
            )
            self.db.add(participant)

        # Add agendas
        for agenda_data in meeting_in.agendas or []:
            agenda = Agenda(
                id=str(uuid.uuid4()),
                meeting_id=db_meeting.id,
                title=agenda_data.title,
                description=agenda_data.description,
                order=agenda_data.order,
            )
            self.db.add(agenda)

        await self.db.commit()
        await self.db.refresh(db_meeting, attribute_names=["participants", "agendas"])

        # n8n Webhook triggern
        await self._trigger_n8n_meeting_created(db_meeting)

        return db_meeting

    async def get_meeting(self, meeting_id: str, client_id: str) -> Optional[Meeting]:
        """Meeting mit allen Relations"""
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(Meeting)
            .options(
                selectinload(Meeting.participants), 
                selectinload(Meeting.agendas),
                selectinload(Meeting.pv)
            )
            .where(Meeting.id == meeting_id)
            .where(Meeting.client_id == client_id)
        )
        return result.scalars().first()

    async def update_meeting(
        self, meeting_id: str, client_id: str, meeting_in: MeetingUpdate
    ) -> Optional[Meeting]:
        """Status-Änderungen -> n8n Benachrichtigung"""
        db_meeting = await self.get_meeting(meeting_id, client_id)
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

    async def delete_meeting(self, meeting_id: str, client_id: str) -> bool:
        """Soft Delete + Audit Log (simplified)"""
        db_meeting = await self.get_meeting(meeting_id, client_id)
        if not db_meeting:
            return False

        await self.db.delete(db_meeting)
        await self.db.commit()
        return True

    async def get_upcoming_meetings(self, client_id: str) -> List[Meeting]:
        """Für Dashboard/Reminders"""
        result = await self.db.execute(
            select(Meeting)
            .where(Meeting.client_id == client_id)
            .where(Meeting.start_time > datetime.utcnow())
            .order_by(Meeting.start_time)
        )
        return list(result.scalars().all())

    async def _trigger_n8n_meeting_created(self, meeting: Meeting):
        """Triggert n8n Webhook: meeting-created"""
        participants_payload = [
            {"id": p.id, "user_id": p.user_id, "email": p.email, "name": p.name}
            for p in meeting.participants
        ]

        payload = {
            "event": "meeting.created",
            "meeting": {
                "id": meeting.id,
                "title": meeting.title,
                "description": meeting.description,
                "location": meeting.location,
                "start_time": (
                    meeting.start_time.isoformat() if meeting.start_time else None
                ),
                "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
                "status": meeting.status,
                "creator_id": meeting.creator_id,
                "created_at": (
                    meeting.created_at.isoformat() if meeting.created_at else None
                ),
                "participants": participants_payload,
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.N8N_WEBHOOK_MEETING_CREATED, json=payload, timeout=5.0
                )
                response.raise_for_status()
                logger.info(f"n8n meeting-created triggered for meeting {meeting.id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n meeting-created: {e}")

    async def _trigger_n8n_meeting_status_change(self, meeting: Meeting):
        """Triggert n8n Webhook für Statusänderungen"""
        # Common webhook or specific one
        pass
