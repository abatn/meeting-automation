from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime

from backend.app.models.action import Action, ActionStatus
from backend.app.schemas.action import ActionCreate, ActionUpdate
from backend.app.models.user import User, UserRole
from backend.app.models.meeting import Meeting

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
        due_date_after: Optional[datetime] = None
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
        
        if filters:
            query = query.where(and_(*filters))
        
        query = query.order_by(Action.due_date.asc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_actions_for_user(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Action]:
        """Holt alle Aktionspunkte, die einem bestimmten Benutzer zugewiesen sind, mit eager loading für zugehörige Beziehungen."""
        query = select(Action).where(Action.assigned_to == user_id).options(
            selectinload(Action.assignee),
            selectinload(Action.meeting)
        ).offset(skip).limit(limit)
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
        meeting = await db.execute(select(Meeting).where(Meeting.id == action_data.meeting_id)).scalar_one_or_none()
        if not meeting or (meeting.organizer_id != current_user.id and current_user.role != UserRole.ADMIN):
            raise ValueError("Not authorized to create action for this meeting.")

        try:
            db_action = Action(
                **action_data.model_dump(),
                status=ActionStatus.OPEN
            )
            db.add(db_action)
            await db.commit()
            await db.refresh(db_action)
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
        meeting = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id)).scalar_one_or_none()
        is_organizer_or_admin = (meeting and meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)

        if action.assigned_to != current_user.id and not is_organizer_or_admin:
            raise ValueError("Not authorized to update this action.")
        
        update_data = action_data.model_dump(exclude_unset=True)
        try:
            for field, value in update_data.items():
                setattr(action, field, value)
            
            await db.commit()
            await db.refresh(action)
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
        meeting = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id)).scalar_one_or_none()
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

    async def change_action_status(
        self,
        db: AsyncSession,
        action_id: int,
        status: ActionStatus,
        current_user: User
    ) -> Optional[Action]:
        """Ändert den Status eines Aktionspunkts (nur Beauftragter, Meeting-Organisator oder Admin)."""
        action = await self.get_action_by_id(db, action_id)
        if not action:
            return None
        
        # Check authorization
        meeting = await db.execute(select(Meeting).where(Meeting.id == action.meeting_id)).scalar_one_or_none()
        is_organizer_or_admin = (meeting and meeting.organizer_id == current_user.id) or (current_user.role == UserRole.ADMIN)

        if action.assigned_to != current_user.id and not is_organizer_or_admin:
            raise ValueError("Not authorized to change the status of this action.")
        
        try:
            action.status = status
            await db.commit()
            await db.refresh(action)
            return action
        except Exception as e:
            await db.rollback()
            raise e

action_service = ActionService()
