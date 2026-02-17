from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta
from backend.app.models.meeting import Meeting, MeetingStatus
from backend.app.schemas.meeting import MeetingCreate, MeetingUpdate
from backend.app.models.user import User # Added import for User model

class MeetingService:
    async def get_meeting_by_id(self, db: AsyncSession, meeting_id: int) -> Optional[Meeting]:
        """Holt ein Meeting anhand der ID."""
        result = await db.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(
                selectinload(Meeting.organizer),
                selectinload(Meeting.recordings),
                selectinload(Meeting.transcriptions),
                selectinload(Meeting.pvs),
                selectinload(Meeting.actions)
            )
        )
        return result.scalar_one_or_none()

    async def get_meetings(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[MeetingStatus] = None,
        user_id: Optional[int] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Meeting]:
        """Holt eine Liste von Meetings mit optionalen Filtern."""
        query = select(Meeting).options(
            selectinload(Meeting.organizer),
            selectinload(Meeting.recordings),
            selectinload(Meeting.transcriptions),
            selectinload(Meeting.pvs),
            selectinload(Meeting.actions)
        )
        
        filters = []
        if status:
            filters.append(Meeting.status == status)
        if user_id:
            filters.append(Meeting.organizer_id == user_id)
        if from_date:
            filters.append(Meeting.date >= from_date)
        if to_date:
            filters.append(Meeting.date <= to_date)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.order_by(Meeting.date.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_meeting(
        self,
        db: AsyncSession,
        meeting_data: MeetingCreate,
        organizer_id: int
    ) -> Meeting:
        """Erstellt ein neues Meeting."""
        try:
            db_meeting = Meeting(
                **meeting_data.model_dump(),
                organizer_id=organizer_id,
                status=MeetingStatus.PLANNED
            )
            db.add(db_meeting)
            await db.commit()
            await db.refresh(db_meeting)
            db.expunge(db_meeting) # Detach the object from the session
            return db_meeting
        except Exception as e:
            await db.rollback()
            raise e

    async def update_meeting(
        self,
        db: AsyncSession,
        meeting_id: int,
        meeting_data: MeetingUpdate,
        user_id: int
    ) -> Optional[Meeting]:
        """Aktualisiert ein Meeting (nur Organizer oder Admin)."""
        meeting = await self.get_meeting_by_id(db, meeting_id)
        if not meeting:
            return None
        
        # Prüfe Berechtigung
        from backend.app.models.user import UserRole
        if meeting.organizer_id != user_id:
            # Prüfe ob User Admin ist
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user or user.role != UserRole.ADMIN:
                return None
        
        update_data = meeting_data.model_dump(exclude_unset=True)
        try:
            for field, value in update_data.items():
                setattr(meeting, field, value)
            
            await db.commit()
            await db.refresh(meeting)
            return meeting
        except Exception as e:
            await db.rollback()
            raise e

    async def delete_meeting(self, db: AsyncSession, meeting_id: int, user_id: int) -> bool:
        """Löscht ein Meeting (nur Organizer oder Admin)."""
        meeting = await self.get_meeting_by_id(db, meeting_id)
        if not meeting:
            return False
        
        # Prüfe Berechtigung
        from backend.app.models.user import UserRole
        if meeting.organizer_id != user_id:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user or user.role != UserRole.ADMIN:
                return False
        
        try:
            await db.delete(meeting)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise e

    async def change_meeting_status(
        self,
        db: AsyncSession,
        meeting_id: int,
        status: MeetingStatus,
        user_id: int
    ) -> Optional[Meeting]:
        """Ändert den Status eines Meetings."""
        meeting = await self.get_meeting_by_id(db, meeting_id)
        if not meeting:
            return None
        
        # Prüfe Berechtigung
        if meeting.organizer_id != user_id:
            return None
        
        try:
            meeting.status = status
            await db.commit()
            await db.refresh(meeting)
            return meeting
        except Exception as e:
            await db.rollback()
            raise e

meeting_service = MeetingService()
