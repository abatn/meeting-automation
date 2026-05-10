import httpx
import smtplib
import logging
import asyncio
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.action_service import ActionService
from app.services.audit_service import AuditService

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


def _send_via_smtp(email: str, subject: str, html_body: str) -> bool:
    """Send email directly via SMTP (TLS)"""
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured, trying n8n fallback")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = subject
        part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part)
        
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent via SMTP to {email}")
        return True
    except Exception as e:
        logger.error(f"SMTP failed for {email}: {e}")
        return False


async def _log_email_audit(client_id: str, email: str, status: str, error: str = None):
    """ISO 27001: Audit logging for email sending (Multi-Tenant compliant)"""
    try:
        async with AsyncSessionLocal() as db:
            await AuditService.log_action(
                db=db,
                client_id=client_id,
                action="SEND_EMAIL",
                table_name="notifications",
                record_id=email,
                new_values={"recipient": email, "status": status, "error": error},
                ip_address="internal",
                user_agent="celery"
            )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


async def _send_invitation_email(client_id: str, email: str, full_name: str, company_name: str, activation_link: str):
    """Send invitation email - try SMTP first, then n8n fallback (Multi-Tenant compliant)"""
    
    # HTML body (multilingual support can be added via config)
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1976d2; color: white; padding: 20px; text-align: center;">
            <h1>Willkommen bei Meeting Automation</h1>
        </div>
        <div style="padding: 20px;">
            <h2>Hallo {full_name},</h2>
            <p>Vielen Dank für Ihre Registrierung bei <strong>{company_name}</strong>.</p>
            <p>Um Ihr Konto zu aktivieren, klicken Sie auf den folgenden Link:</p>
            <div style="margin: 30px 0; text-align: center;">
                <a href="{activation_link}" style="background: #1976d2; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Konto aktivieren
                </a>
            </div>
            <p style="font-size: 12px; color: #888;">Dieser Link ist 48 Stunden gültig.</p>
        </div>
    </body>
    </html>
    """
    subject = "Aktivieren Sie Ihr Konto - Meeting Automation"
    
    # Try SMTP first
    smtp_success = await asyncio.get_event_loop().run_in_executor(
        None, _send_via_smtp, email, subject, html_body
    )
    
    if smtp_success:
        await _log_email_audit(client_id, email, "SUCCESS")
        return
    
    # Fallback to n8n
    try:
        payload = {
            "event": "user_invitation",
            "email": email,
            "full_name": full_name,
            "company_name": company_name,
            "activation_link": activation_link,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Invitation email sent via n8n to {email}")
            await _log_email_audit(client_id, email, "SUCCESS_N8N")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {e}")
        await _log_email_audit(client_id, email, "FAILED", str(e))


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3)
def send_invitation_email(self, client_id: str, email: str, full_name: str, company_name: str, activation_link: str):
    """Celery task to send invitation email (Multi-Tenant compliant with client_id)"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if not loop.is_running():
        loop.run_until_complete(_send_invitation_email(client_id, email, full_name, company_name, activation_link))
    else:
        asyncio.ensure_future(_send_invitation_email(client_id, email, full_name, company_name, activation_link), loop=loop)
