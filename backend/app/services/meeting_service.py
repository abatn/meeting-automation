import logging
import uuid
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.meeting import Agenda, Meeting, Participant
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class MeetingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meeting(self, meeting_in: MeetingCreate, owner_id: str, client_id: str) -> Meeting:
        """Meeting anlegen + n8n-Webhook triggern"""
        if meeting_in.end_time and meeting_in.start_time and meeting_in.end_time <= meeting_in.start_time:
            raise HTTPException(status_code=400, detail="Meeting end time must be after start time")

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
        self, meeting_id: str, client_id: str, meeting_in: MeetingUpdate, current_user_id: str = None
    ) -> Optional[Meeting]:
        """Status-Änderungen -> n8n Benachrichtigung
        
        P2-3: Authorization check - only creator, admin, or dg can update meeting
        """
        db_meeting = await self.get_meeting(meeting_id, client_id)
        if not db_meeting:
            return None

        # P2-3: Authorization check - verify user owns the meeting or is admin/dg
        if current_user_id and current_user_id != db_meeting.creator_id:
            # Import current_user to get role
            from app.models.user import User
            user_result = await self.db.execute(
                select(User).where(User.id == current_user_id)
            )
            current_user = user_result.scalar_one_or_none()
            if not current_user or current_user.role not in ["admin", "dg"]:
                raise HTTPException(
                    status_code=403,
                    detail="Only meeting creator, admin, or dg can update meeting"
                )

        update_data = meeting_in.model_dump(exclude_unset=True)

        # Store previous status for webhook
        previous_status = db_meeting.status

        for key, value in update_data.items():
            setattr(db_meeting, key, value)

        await self.db.commit()
        await self.db.refresh(db_meeting, attribute_names=["participants"])

        # Notify n8n about status change if relevant
        if "status" in update_data:
            await self._trigger_n8n_meeting_status_change(db_meeting, previous_status)

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
        """Triggert n8n Webhook: meeting-created (ISO 27001 A.12.4.1 Audit-Log)"""
        attendees = [p.email for p in meeting.participants]

        payload = {
            "id": meeting.id,
            "title": meeting.title,
            "description": meeting.description,
            "location": meeting.location,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
            "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
            "status": meeting.status,
            "attendees": attendees,
            "participants": [
                {"id": p.id, "email": p.email, "name": p.name}
                for p in meeting.participants
            ]
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.N8N_WEBHOOK_MEETING_CREATED, json=payload, timeout=10.0
                )
                response.raise_for_status()
                logger.info(
                    f"n8n meeting-created triggered for meeting {meeting.id} "
                    f"(status={response.status_code}, attendees={len(attendees)})"
                )
                # Audit-Log für erfolgreichen n8n-Call (ISO 27001 A.12.4.1)
                await AuditService.log_action(
                    self.db,
                    client_id=meeting.client_id,
                    action="N8N_MEETING_CREATED_TRIGGERED",
                    user_id=meeting.creator_id,
                    table_name="meetings",
                    record_id=meeting.id,
                    new_values={
                        "n8n_webhook_url": settings.N8N_WEBHOOK_MEETING_CREATED,
                        "attendee_count": len(attendees),
                        "http_status": response.status_code,
                    },
                )
        except httpx.HTTPStatusError as e:
            logger.error(
                f"n8n meeting-created failed for meeting {meeting.id}: "
                f"HTTP {e.response.status_code} — {e.response.text[:200]}"
            )
        except httpx.RequestError as e:
            logger.error(f"n8n meeting-created connection error for meeting {meeting.id}: {e}")

    async def _trigger_n8n_meeting_status_change(self, meeting: Meeting, previous_status: str):
        """Triggert n8n Webhook für Statusänderungen"""
        payload = {
            "meeting_id": meeting.id,
            "status": meeting.status,
            "previous_status": previous_status,
            "attendees": [p.email for p in meeting.participants],
            "title": meeting.title,
            "start_time": meeting.start_time.isoformat() if meeting.start_time else None,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.N8N_WEBHOOK_MEETING_STATUS_CHANGED,
                    json=payload,
                    timeout=5.0
                )
                response.raise_for_status()
                logger.info(f"n8n meeting-status-changed triggered for meeting {meeting.id}: {previous_status} -> {meeting.status}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n meeting-status-changed: {e}")
