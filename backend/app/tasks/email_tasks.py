import httpx
import smtplib
import asyncio
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.tasks.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.action_service import ActionService
from app.services.audit_service import AuditService
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run async coroutine from sync context (Celery worker)."""
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.run_until_complete(coro)
    else:
        asyncio.ensure_future(coro)


async def _send_reminder_via_n8n(payload: dict):
    """Ruft n8n-Webhook auf"""
    # TODO: This function sends to base N8N_WEBHOOK_URL (no path suffix).
    # No matching n8n workflow exists — daily-reminders is cron-triggered, not webhook-triggered.
    # The Celery task 'send_reminder_via_n8n' is registered but never called in the codebase.
    # Re-enable when an n8n webhook workflow for ad-hoc reminders is created.
    logger.warning("send_reminder_via_n8n called but disabled — no matching n8n webhook workflow")
    # try:
    #     async with httpx.AsyncClient() as client:
    #         response = await client.post(
    #             f"{settings.N8N_WEBHOOK_URL}/reminder", json=payload, timeout=5.0
    #         )
    #         response.raise_for_status()
    #         logger.info("Reminder sent via n8n")
    # except Exception as e:
    #     logger.error(f"Failed to send reminder via n8n: {e}")


@celery_app.task(name="send_reminder_via_n8n")
def send_reminder_via_n8n(payload: dict):
    """Celery task wrapper for the async n8n call"""
    _run_async(_send_reminder_via_n8n(payload))


async def _daily_reminder_task():
    """Cron-Job -> n8n 'daily-reminders' triggern"""
    # TODO: daily-reminders n8n workflow is cron-triggered (hour 8), not webhook-triggered.
    # It queries the backend API directly. This Celery beat task is redundant AND
    # N8N_WEBHOOK_DAILY_REMINDER has no matching n8n webhook endpoint → 404.
    # Either remove this Celery beat schedule or create a webhook-triggered n8n workflow.
    logger.info("daily_reminder_task skipped — n8n daily-reminders runs on its own cron schedule")
    return "Skipped — n8n handles daily reminders via cron trigger"


@celery_app.task(name="daily_reminder_task")
def daily_reminder_task():
    """Celery task wrapper for the async cron job"""
    _run_async(_daily_reminder_task())


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
            response = await client.post(f"{settings.N8N_WEBHOOK_URL}/user-invited", json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Invitation email sent via n8n to {email}")
            await _log_email_audit(client_id, email, "SUCCESS_N8N")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {e}")
        await _log_email_audit(client_id, email, "FAILED", str(e))


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3)
def send_invitation_email(self, client_id: str, email: str, full_name: str, company_name: str, activation_link: str):
    """Celery task to send invitation email (Multi-Tenant compliant with client_id)"""
    _run_async(_send_invitation_email(client_id, email, full_name, company_name, activation_link))


# Phase 188: Manual Tenant Activation
async def _send_admin_new_tenant_notification(client_id: str, company_name: str, plan: str, email: str):
    """Notify admin via n8n webhook when a new tenant registers."""
    try:
        payload = {
            "event": "admin_new_tenant",
            "client_id": client_id,
            "company_name": company_name,
            "plan": plan,
            "email": email,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_WEBHOOK_ADMIN_NEW_TENANT,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Admin notification sent for new tenant: {company_name} ({plan})")
            await _log_email_audit(client_id, email, "SUCCESS_ADMIN_N8N")
    except Exception as e:
        logger.error(f"Failed to send admin new tenant notification: {e}")
        await _log_email_audit(client_id, email, "FAILED_ADMIN", str(e))


@celery_app.task(name="send_admin_new_tenant_notification", bind=True, max_retries=3)
def send_admin_new_tenant_notification(self, client_id: str, company_name: str, plan: str, email: str):
    """Celery task to notify admin about new tenant registration."""
    _run_async(_send_admin_new_tenant_notification(client_id, company_name, plan, email))


async def _send_customer_activated_email(email: str, full_name: str, company_name: str):
    """Notify customer that their subscription has been activated."""
    login_url = f"{settings.FRONTEND_URL}/login"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #22c55e; color: white; padding: 20px; text-align: center;">
            <h1>Ihr Abo wurde aktiviert!</h1>
        </div>
        <div style="padding: 20px;">
            <h2>Hallo {full_name},</h2>
            <p>Wir freuen uns, Ihnen mitzuteilen, dass Ihr Abo bei <strong>{company_name}</strong> erfolgreich aktiviert wurde.</p>
            <p>Sie können sich jetzt einloggen und die App nutzen:</p>
            <div style="margin: 30px 0; text-align: center;">
                <a href="{login_url}" style="background: #22c55e; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Jetzt einloggen
                </a>
            </div>
            <p style="font-size: 12px; color: #888;">Meeting Automation Team</p>
        </div>
    </body>
    </html>
    """
    subject = "Ihr Abo wurde aktiviert - Meeting Automation"
    smtp_success = await asyncio.get_event_loop().run_in_executor(
        None, _send_via_smtp, email, subject, html_body
    )
    if smtp_success:
        logger.info(f"Customer activation email sent via SMTP to {email}")
        return
    # Fallback to n8n
    try:
        payload = {
            "event": "customer_activated",
            "email": email,
            "full_name": full_name,
            "company_name": company_name,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.N8N_WEBHOOK_CUSTOMER_ACTIVATED,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Customer activation email sent via n8n to {email}")
    except Exception as e:
        logger.error(f"Failed to send customer activation email: {e}")


@celery_app.task(name="send_customer_activated_email", bind=True, max_retries=3)
def send_customer_activated_email(self, email: str, full_name: str, company_name: str):
    """Celery task to notify customer about subscription activation."""
    _run_async(_send_customer_activated_email(email, full_name, company_name))
