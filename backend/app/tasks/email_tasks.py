import httpx
import logging
import asyncio
from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.action_service import ActionService

logger = logging.getLogger(__name__)


async def _send_reminder_via_n8n(payload: dict):
    """Ruft n8n-Webhook auf"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_WEBHOOK_URL, json=payload, timeout=5.0
            )
            response.raise_for_status()
            logger.info("Reminder sent via n8n")
    except Exception as e:
        logger.error(f"Failed to send reminder via n8n: {e}")


@celery_app.task(name="send_reminder_via_n8n")
def send_reminder_via_n8n(payload: dict):
    """Celery task wrapper for the async n8n call"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not loop.is_running():
        loop.run_until_complete(_send_reminder_via_n8n(payload))
    else:
        asyncio.ensure_future(_send_reminder_via_n8n(payload), loop=loop)


async def _daily_reminder_task():
    """Cron-Job -> n8n 'daily-reminders' triggern"""
    async with AsyncSessionLocal() as db:
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
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                }
                for a in due_actions
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    settings.N8N_WEBHOOK_DAILY_REMINDER, json=payload, timeout=10.0
                )
                logger.info(f"Daily reminders triggered for {len(due_actions)}")
        except Exception as e:
            logger.error(f"Failed to trigger daily reminders: {e}")


@celery_app.task(name="daily_reminder_task")
def daily_reminder_task():
    """Celery task wrapper for the async cron job"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not loop.is_running():
        loop.run_until_complete(_daily_reminder_task())
    else:
        asyncio.ensure_future(_daily_reminder_task(), loop=loop)


async def _send_invitation_email(email: str, full_name: str, company_name: str, activation_link: str):
    """Send invitation email via n8n webhook"""
    try:
        payload = {
            "event": "user_invitation",
            "email": email,
            "full_name": full_name,
            "company_name": company_name,
            "activation_link": activation_link,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_WEBHOOK_URL, json=payload, timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Invitation email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {e}")


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3)
def send_invitation_email(self, email: str, full_name: str, company_name: str, activation_link: str):
    """Celery task to send invitation email"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not loop.is_running():
        loop.run_until_complete(_send_invitation_email(email, full_name, company_name, activation_link))
    else:
        asyncio.ensure_future(_send_invitation_email(email, full_name, company_name, activation_link), loop=loop)
