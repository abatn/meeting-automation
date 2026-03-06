import httpx
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta

from app.models.action import Action
from app.core.config import settings


logger = logging.getLogger(__name__)


class ActionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_actions_from_pv(self, pv_id: int, actions_data: List[dict]):
        """n8n-Callback von Mistral verarbeiten"""
        new_actions = []
        for item in actions_data:
            action = Action(
                pv_id=pv_id,
                title=item.get("title"),
                description=item.get("description"),
                assignee_id=item.get("assignee_id"),
                due_date=datetime.fromisoformat(item["due_date"])
                if item.get("due_date") else None,
                status="pending"
            )
            self.db.add(action)
            new_actions.append(action)

        await self.db.commit()

        # Trigger notifications for each assigned action
        for action in new_actions:
            if action.assignee_id:
                await self.assign_action(action.id, action.assignee_id)

        return new_actions

    async def assign_action(self, action_id: int, user_id: int):
        """Verantwortlichen zuweisen -> WhatsApp Reminder via n8n"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalars().first()

        if not action:
            return None

        action.assignee_id = user_id
        await self.db.commit()

        # WhatsApp Reminder via n8n
        payload = {
            "event": "action.assigned",
            "action_id": action.id,
            "title": action.title,
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

    async def update_action_status(self, action_id: int, status: str):
        """Status-Änderung -> n8n Notification"""
        result = await self.db.execute(select(Action).where(Action.id == action_id))
        action = result.scalars().first()

        if not action:
            return None

        action.status = status
        await self.db.commit()

        # n8n Notification (e.g., to Manager)
        payload = {
            "event": "action.status_updated",
            "action_id": action.id,
            "status": status,
            "title": action.title
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
        return result.scalars().all()

    async def escalate_overdue(self, action_id: int):
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
