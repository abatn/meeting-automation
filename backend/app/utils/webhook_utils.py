import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

async def trigger_user_invited_webhook(email: str, full_name: str, company_name: str, activation_link: str) -> bool:
    """
    Triggers the n8n webhook for inviting a new user.
    """
    webhook_url = f"{settings.N8N_WEBHOOK_URL}/user-invited"
    payload = {
        "email": email,
        "full_name": full_name,
        "company_name": company_name,
        "activation_link": activation_link
    }
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_SECRET}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Successfully triggered user-invited webhook for {email}")
            return True
    except httpx.HTTPError as e:
        logger.error(f"Failed to trigger user-invited webhook for {email}: {str(e)}")
        return False
