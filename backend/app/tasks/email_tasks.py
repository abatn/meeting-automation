import httpx
import logging
from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.action_service import ActionService

logger = logging.getLogger(__name__)

@celery_app.task(name="send_reminder_via_n8n")
async def send_reminder_via_n8n(payload: dict):
    """Ruft n8n-Webhook auf"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info("Reminder sent via n8n")
    except Exception as e:
        logger.error(f"Failed to send reminder via n8n: {e}")

@celery_app.task(name="daily_reminder_task")
async def daily_reminder_task():
    """Cron-Job -> n8n 'daily-reminders' triggern"""
    async with SessionLocal() as db:
        action_service = ActionService(db)
        due_actions = await action_service.get_due_actions()
        
        if not due_actions:
            return "No actions due"

        payload = {
            "event": "daily_reminders",
            "actions": [
                {
                    "id": a.id,
                    "title": a.title,
                    "assignee_id": a.assignee_id,
                    "due_date": a.due_date.isoformat()
                } for a in due_actions
            ]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.N8N_WEBHOOK_DAILY_REMINDER, json=payload, timeout=10.0)
                logger.info(f"Daily reminders triggered for {len(due_actions)} actions")
        except Exception as e:
            logger.error(f"Failed to trigger daily reminders: {e}")