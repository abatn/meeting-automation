from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import re

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

CONTACT_EMAIL = "mohamedlarbinakti@gmail.com"


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str


def _is_valid_input(text: str) -> bool:
    if len(text) > 500:
        return False
    if re.search(r'<script|javascript:|on\w+=', text, re.IGNORECASE):
        return False
    return True


@router.post("/contact")
async def send_contact_message(payload: ContactRequest):
    if not _is_valid_input(payload.name):
        raise HTTPException(status_code=400, detail="Invalid name")
    if not _is_valid_input(payload.message):
        raise HTTPException(status_code=400, detail="Invalid message")

    subject = f"[Contact] {payload.name} — Meeting Automation"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #333; border-bottom: 2px solid #000; padding-bottom: 10px;">
            New Contact Request
        </h2>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #555; width: 120px;">Name:</td>
                <td style="padding: 8px 0; color: #333;">{payload.name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #555;">Email:</td>
                <td style="padding: 8px 0; color: #333;">
                    <a href="mailto:{payload.email}">{payload.email}</a>
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: bold; color: #555; vertical-align: top;">Message:</td>
                <td style="padding: 8px 0; color: #333; white-space: pre-wrap;">{payload.message}</td>
            </tr>
        </table>
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #eee;" />
        <p style="font-size: 12px; color: #999;">
            Sent from Meeting Automation Landing Page
        </p>
    </div>
    """

    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = CONTACT_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            logger.info(f"Contact email sent to {CONTACT_EMAIL} from {payload.email}")
            return {"status": "sent", "message": "Email sent successfully"}
        except Exception as e:
            logger.error(f"SMTP failed for contact form: {e}")
            raise HTTPException(status_code=500, detail="Failed to send email. Please try again later.")
    else:
        logger.warning("SMTP not configured — contact form email not sent")
        raise HTTPException(status_code=503, detail="Email service not configured. Please contact us directly.")
