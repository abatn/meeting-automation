import httpx
import logging
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta

from app.models.action import Action, Assignment
from app.models.pv import PV
from app.core.config import settings


logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_actions_from_pv(self, pv_id: str, actions_data: List[dict]) -> List[Action]:
        """n8n-Callback von Mistral verarbeiten"""
        # Lookup meeting_id from PV
        pv_res = await self.db.execute(select(PV).where(PV.id == pv_id))
        pv = pv_res.scalar_one_or_none()
        if not pv:
            logger.error(f"PV {pv_id} not found. Cannot extract actions.")
            return []

        meeting_id = pv.meeting_id
        new_actions = []

        for item in actions_data:
            action_id = str(uuid.uuid4())
            action = Action(
                id=action_id,
                meeting_id=meeting_id,
                title=item.get("title", "Untitled Action"),
                description=item.get("description", ""),
                due_date=datetime.fromisoformat(item["due_date"])
                if item.get("due_date") else None,
                status="pending"
            )
            self.db.add(action)
            new_actions.append(action)

            assignee_id = item.get("assignee_id")
            if assignee_id:
                assignment = Assignment(
                    id=str(uuid.uuid4()),
                    action_id=action_id,
                    user_id=assignee_id
                )
                self.db.add(assignment)

        await self.db.commit()

        # Trigger notifications for each assigned action
        for action in new_actions:
            if action.assignments and action.assignments[0].user_id:
                await self.assign_action(str(action.id), str(action.assignments[0].user_id))

        return new_actions

    async def assign_action(self, action_id: str, user_id: str) -> Optional[Action]:
        """Verantwortlichen zuweisen -> WhatsApp Reminder via n8n"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            return None

        # Check if assignment already exists
        assignment_result = await self.db.execute(
            select(Assignment).where(Assignment.action_id == action_id, Assignment.user_id == user_id)
        )
        existing_assignment = assignment_result.scalar_one_or_none()

        if not existing_assignment:
            assignment = Assignment(
                id=str(uuid.uuid4()),
                action_id=action_id,
                user_id=user_id
            )
            self.db.add(assignment)
            await self.db.commit()

        # WhatsApp Reminder via n8n
        payload = {
            "event": "action.assigned",
            "action_id": action.id,
            "title": str(action.title),
            "assignee_id": user_id,
            "due_date": action.due_date.isoformat() if action.due_date else None
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
                logger.info(f"n8n notification triggered for action {action_id}")
        except Exception as e:
            logger.error(f"Failed to trigger n8n notification: {e}")

        return action

    async def update_action_status(self, action_id: str, status: str) -> Optional[Action]:
        """Status-Änderung -> n8n Notification"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            return None

        # Hack for enum
        action.status = status  # type: ignore
        await self.db.commit()

        # n8n Notification (e.g., to Manager)
        payload = {
            "event": "action.status_updated",
            "action_id": action.id,
            "status": status,
            "title": str(action.title)
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to trigger n8n status notification: {e}")

        return action

    async def get_due_actions(self) -> List[Action]:
        """Für tägliche Reminder (via Celery)"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        result = await self.db.execute(
            select(Action).where(
                Action.due_date <= tomorrow, Action.status != "completed"
            )
        )
        return list(result.scalars().all())

    async def escalate_overdue(self, action_id: str) -> None:
        """Eskalation an Manager"""
        payload = {
            "event": "action.escalate",
            "action_id": action_id
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to trigger n8n escalate notification: {e}")
