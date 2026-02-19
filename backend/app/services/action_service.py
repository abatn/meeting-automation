from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timedelta

from backend.app.models.action import Action, ActionStatus
from backend.app.schemas.action import ActionCreate, ActionUpdate, ActionComplete
from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting
from backend.app.services.notification_service import notification_service # Assuming this service will be created

class ActionService:
    async def get_action_by_id(self, db: AsyncSession, action_id: int) -> Optional[Action]:
        """Holt einen Aktionspunkt anhand der ID."""
        result = await db.execute(
            select(Action)
            .where(Action.id == action_id)
            .options(selectinload(Action.assignee), selectinload(Action.meeting))
        )
        return result.scalar_one_or_none()

    async def get_actions(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        meeting_id: Optional[int] = None,
        assignee_id: Optional[int] = None,
        status: Optional[ActionStatus] = None,
        due_date_before: Optional[datetime] = None,
        due_date_after: Optional[datetime] = None,
        priority: Optional[int] = None
    ) -> List[Action]:
        """Holt eine Liste von Aktionspunkten mit optionalen Filtern."""
        query = select(Action).options(selectinload(Action.assignee), selectinload(Action.meeting))
        
        filters = []
        if meeting_id:
            filters.append(Action.meeting_id == meeting_id)
        if assignee_id:
            filters.append(Action.assigned_to == assignee_id)
        if status:
            filters.append(Action.status == status)
        if due_date_before:
            filters.append(Action.due_date <= due_date_before)
        if due_date_after:
            filters.append(Action.due_date >= due_date_after)
        if priority:
            filters.append(Action.priority == priority)
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.order_by(Action.due_date.asc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_actions_by_user(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ActionStatus] = None
    ) -> List[Action]:
        """Holt alle Aktionspunkte, die einem bestimmten Benutzer zugewiesen sind, mit eager loading für zugehörige Beziehungen."""
        query = select(Action).where(Action.assigned_to == user_id).options(
            selectinload(Action.assignee),
            selectinload(Action.meeting)
        )
        if status:
            query = query.where(Action.status == status)
        query = query.order_by(Action.due_date.asc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_actions_by_meeting(
        self,
        db: AsyncSession,
        meeting_id: int,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ActionStatus] = None
    ) -> List[Action]:
        """Holt alle Aktionspunkte, die einem bestimmten Meeting zugeordnet sind."""
        query = select(Action).where(Action.meeting_id == meeting_id).options(
            selectinload(Action.assignee),
            selectinload(Action.meeting)
        )
        if status:
            query = query.where(Action.status == status)
        query = query.order_by(Action.due_date.asc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def create_action(
        self,
        db: AsyncSession,
        action_data: ActionCreate,
        current_user: User
    ) -> Action:
        """Erstellt einen neuen Aktionspunkt."""
        # Check if current_user is the organizer of the meeting or an admin
        meeting_result = await db.execute(select(Meeting).where(Meeting.id == action_data.meeting_id))
        meeting = meeting_result.scalar_one_or_none()
        if not meeting or (meeting.organizer_id != current_user.id and current_user.role != UserRole.ADMIN):
            raise ValueError("Not authorized to create action for this meeting.")

        try:
            db_action = Action(
                **action_data.dict(),
                status=ActionStatus.PENDING
            )
            db.add(db_action)
            await db.commit()
            await db.refresh(db_action)
            
            # Eager load relationships for notification
            # Re-fetch with relationships
            result = await db.execute(
                select(Action)
                .where(Action.id == db_action.id)
                .options(selectinload(Action.assignee), selectinload(Action.meeting))
            )
            db_action = result.scalar_one()

            await notification_service.send_new_action_notification(db_action)
            return db_action
        except Exception as e:
            await db.rollback()
            raise e

    async def update_action(
        self,
        db: AsyncSession,
        action_id: int,
        action_data: ActionUpdate,
        current_user: User
    ) -> Optional[Action]:
        """Aktualisiert einen Aktionspunkt (nur Beauftragter, Meeting-Organisator oder Admin)."""
        action = await self.get_action_by_id(db, action_id)
        if not action:
            return None
        
        # Check authorization
        meeting_result = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id))
        meeting = meeting_result.scalar_one_or_none()
        is_organizer_or_admin = (meeting and meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)

        if action.assigned_to != current_user.id and not is_organizer_or_admin:
            raise ValueError("Not authorized to update this action.")
        
        update_data = action_data.dict(exclude_unset=True)
        try:
            for field, value in update_data.items():
                setattr(action, field, value)
            
            await db.commit()
            await db.refresh(action)
            
            # Re-fetch with relationships (though they might be loaded from get_action_by_id, refresh might unload them)
            # get_action_by_id uses selectinload, so action has them. 
            # But refresh might clear them? No, refresh updates columns.
            # However, to be safe and ensure latest state:
            result = await db.execute(
                select(Action)
                .where(Action.id == action.id)
                .options(selectinload(Action.assignee), selectinload(Action.meeting))
            )
            action = result.scalar_one()

            await notification_service.send_action_update_notification(action)
            return action
        except Exception as e:
            await db.rollback()
            raise e

    async def delete_action(self, db: AsyncSession, action_id: int, current_user: User) -> bool:
        """Löscht einen Aktionspunkt (nur Meeting-Organisator oder Admin)."""
        action = await self.get_action_by_id(db, action_id)
        if not action:
            return False
        
        # Check authorization
        meeting_result = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id))
        meeting = meeting_result.scalar_one_or_none()
        is_organizer_or_admin = (meeting and meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)

        if not is_organizer_or_admin:
            raise ValueError("Not authorized to delete this action.")
        
        try:
            await db.delete(action)
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise e

    async def complete_action(
        self,
        db: AsyncSession,
        action_id: int,
        completion_data: ActionComplete,
        current_user: User
    ) -> Optional[Action]:
        """Markiert einen Aktionspunkt als erledigt (nur Beauftragter, Meeting-Organisator oder Admin)."""
        action = await self.get_action_by_id(db, action_id)
        if not action:
            return None
        
        # Check authorization
        meeting_result = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id))
        meeting = meeting_result.scalar_one_or_none()
        is_organizer_or_admin = (meeting and meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)

        if action.assigned_to != current_user.id and not is_organizer_or_admin:
            raise ValueError("Not authorized to complete this action.")
        
        try:
            action.status = ActionStatus.COMPLETED
            # action.completion_comment = completion_data.comment # Model doesn't have this field, storing in memory for notification
            setattr(action, 'completion_comment', completion_data.comment) 
            action.completed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(action)
            
            # Re-fetch for notification
            result = await db.execute(
                select(Action)
                .where(Action.id == action.id)
                .options(selectinload(Action.assignee), selectinload(Action.meeting).selectinload(Meeting.organizer))
            )
            action = result.scalar_one()
            # Restore temporary attribute for notification
            setattr(action, 'completion_comment', completion_data.comment)

            await notification_service.send_action_completion_notification(action)
            return action
        except Exception as e:
            await db.rollback()
            raise e

    async def check_overdue_actions(self, db: AsyncSession) -> List[Action]:
        """Prüft und gibt überfällige Aktionspunkte zurück."""
        now = datetime.utcnow()
        result = await db.execute(
            select(Action)
            .where(and_(Action.due_date < now, Action.status == ActionStatus.PENDING))
            .options(selectinload(Action.assignee), selectinload(Action.meeting))
        )
        return result.scalars().all()

    async def send_action_reminders(self, db: AsyncSession) -> List[Action]:
        """Versendet Erinnerungen für überfällige Aktionspunkte."""
        overdue_actions = await self.check_overdue_actions(db)
        sent_reminders = []
        for action in overdue_actions:
            # In a real application, you'd check if a reminder has already been sent recently
            # For now, we'll just send it.
            await notification_service.send_action_reminder_notification(action)
            sent_reminders.append(action)
        return sent_reminders

action_service = ActionService()
