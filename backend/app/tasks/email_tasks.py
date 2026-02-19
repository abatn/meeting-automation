import logging
from typing import List
from datetime import datetime

from backend.app.tasks.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models.action import ActionStatus
from datetime import timedelta
from backend.app.models.user import User
from backend.app.models.meeting import Meeting
from backend.app.models.action import Action
from backend.app.models.pv import PV
from backend.app.services.notification_service import notification_service # Assuming this service handles actual email sending
from backend.app.services.action_service import action_service
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

# Email Templates (simplified for demonstration)
EMAIL_TEMPLATES = {
    "welcome": {
        "subject": "Willkommen bei Meeting Automation!",
        "body": "Hallo {user_name},\n\nWillkommen bei Meeting Automation! Wir freuen uns, Sie an Bord zu haben.\n\nIhr Team von Meeting Automation."
    },
    "meeting_invitation": {
        "subject": "Einladung zum Meeting: {meeting_title}",
        "body": "Hallo {user_name},\n\nSie wurden zu einem Meeting eingeladen:\n\nTitel: {meeting_title}\nBeschreibung: {meeting_description}\nDatum: {meeting_date}\nUhrzeit: {meeting_time}\nOrt: {meeting_location}\n\nWir freuen uns auf Ihre Teilnahme!\n\nIhr Team von Meeting Automation."
    },
    "action_reminder": {
        "subject": "Erinnerung: Aktionspunkt '{action_description}' ist fällig!",
        "body": "Hallo {user_name},\n\nDies ist eine Erinnerung für Ihren Aktionspunkt:\n\nBeschreibung: {action_description}\nFällig am: {due_date}\nMeeting: {meeting_title}\n\nBitte kümmern Sie sich zeitnah darum.\n\nIhr Team von Meeting Automation."
    },
    "pv_ready_notification": {
        "subject": "Protokoll-Vorlage (PV) für Meeting '{meeting_title}' ist bereit",
        "body": "Hallo {user_name},\n\nDie Protokoll-Vorlage für das Meeting '{meeting_title}' ist jetzt verfügbar.\n\nSie können sie hier einsehen: [Link zur PV]\n\nIhr Team von Meeting Automation."
    },
    "daily_digest": {
        "subject": "Ihr täglicher Meeting Automation Digest",
        "body": "Hallo {user_name},\n\nHier ist Ihr täglicher Überblick von Meeting Automation:\n\nÜberfällige Aktionspunkte:\n{overdue_actions}\n\nAnstehende Aktionspunkte:\n{upcoming_actions}\n\nIhr Team von Meeting Automation."
    }
}

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def send_welcome_email(self, user_id: int):
    try:
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            if user:
                subject = EMAIL_TEMPLATES["welcome"]["subject"]
                body = EMAIL_TEMPLATES["welcome"]["body"].format(user_name=user.full_name or user.email)
                await notification_service.send_email(user.email, subject, body)
                logger.info(f"Welcome email sent to {user.email}")
            else:
                logger.warning(f"User with ID {user_id} not found for welcome email.")
    except Exception as exc:
        logger.error(f"Error sending welcome email to user {user_id}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def send_meeting_invitation(self, meeting_id: int, user_ids: List[int]):
    try:
        async with SessionLocal() as db:
            meeting = await db.get(Meeting, meeting_id)
            if not meeting:
                logger.warning(f"Meeting with ID {meeting_id} not found for invitation.")
                return

            users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            
            for user in users:
                subject = EMAIL_TEMPLATES["meeting_invitation"]["subject"].format(meeting_title=meeting.title)
                body = EMAIL_TEMPLATES["meeting_invitation"]["body"].format(
                    user_name=user.full_name or user.email,
                    meeting_title=meeting.title,
                    meeting_description=meeting.description,
                    meeting_date=meeting.date.strftime("%Y-%m-%d"),
                    meeting_time=meeting.start_time.strftime("%H:%M") if meeting.start_time else "N/A",
                    meeting_location=meeting.location
                )
                await notification_service.send_email(user.email, subject, body)
                logger.info(f"Meeting invitation for '{meeting.title}' sent to {user.email}")
    except Exception as exc:
        logger.error(f"Error sending meeting invitation for meeting {meeting_id}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def send_action_reminder(self, action_id: int):
    try:
        async with SessionLocal() as db:
            action = await action_service.get_action_by_id(db, action_id)
            if not action or not action.assignee or not action.meeting:
                logger.warning(f"Action with ID {action_id} not found or missing assignee/meeting for reminder.")
                return

            user = action.assignee
            meeting = action.meeting

            subject = EMAIL_TEMPLATES["action_reminder"]["subject"].format(action_description=action.description)
            body = EMAIL_TEMPLATES["action_reminder"]["body"].format(
                user_name=user.full_name or user.email,
                action_description=action.description,
                due_date=action.due_date.strftime("%Y-%m-%d %H:%M") if action.due_date else "N/A",
                meeting_title=meeting.title
            )
            await notification_service.send_email(user.email, subject, body)
            logger.info(f"Action reminder for '{action.description}' sent to {user.email}")
    except Exception as exc:
        logger.error(f"Error sending action reminder for action {action_id}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def send_pv_ready_notification(self, pv_id: int, user_ids: List[int]):
    try:
        async with SessionLocal() as db:
            pv = await db.get(PV, pv_id)
            if not pv or not pv.meeting:
                logger.warning(f"PV with ID {pv_id} not found or missing meeting for notification.")
                return

            users = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
            
            for user in users:
                subject = EMAIL_TEMPLATES["pv_ready_notification"]["subject"].format(meeting_title=pv.meeting.title)
                # TODO: Replace [Link zur PV] with actual link
                body = EMAIL_TEMPLATES["pv_ready_notification"]["body"].format(
                    user_name=user.full_name or user.email,
                    meeting_title=pv.meeting.title
                )
                await notification_service.send_email(user.email, subject, body)
                logger.info(f"PV ready notification for '{pv.meeting.title}' sent to {user.email}")
    except Exception as exc:
        logger.error(f"Error sending PV ready notification for PV {pv_id}: {exc}")
        raise self.retry(exc=exc)

@celery_app.task(bind=True, default_retry_delay=settings.CELERY_TASK_DEFAULT_RETRY_DELAY, max_retries=settings.CELERY_TASK_MAX_RETRIES)
async def send_daily_digest(self):
    try:
        async with SessionLocal() as db:
            users = (await db.execute(select(User))).scalars().all()
            now = datetime.utcnow()

            for user in users:
                overdue_actions = await action_service.get_actions_by_user(
                    db, user.id, status=ActionStatus.OPEN, due_date_before=now
                )
                upcoming_actions = await action_service.get_actions_by_user(
                    db, user.id, status=ActionStatus.OPEN, due_date_after=now, due_date_before=now + timedelta(days=7)
                )

                overdue_str = "\n".join([f"- {a.description} (Fällig: {a.due_date.strftime('%Y-%m-%d')})" for a in overdue_actions]) if overdue_actions else "Keine"
                upcoming_str = "\n".join([f"- {a.description} (Fällig: {a.due_date.strftime('%Y-%m-%d')})" for a in upcoming_actions]) if upcoming_actions else "Keine"

                subject = EMAIL_TEMPLATES["daily_digest"]["subject"]
                body = EMAIL_TEMPLATES["daily_digest"]["body"].format(
                    user_name=user.full_name or user.email,
                    overdue_actions=overdue_str,
                    upcoming_actions=upcoming_str
                )
                await notification_service.send_email(user.email, subject, body)
                logger.info(f"Daily digest sent to {user.email}")
    except Exception as exc:
        logger.error(f"Error sending daily digest: {exc}")
        raise self.retry(exc=exc)
