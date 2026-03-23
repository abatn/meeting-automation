import logging
import stripe
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services.billing_service import BillingService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Configure Stripe
stripe.api_key = settings.STRIPE_API_KEY

@router.post("/")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(deps.get_db)
):
    """
    Endpoint for Stripe Webhooks.
    Securely handles payment events like invoice.paid or checkout.session.completed.
    """
    payload = await request.body()
    
    # 1. Verify Signature (Only if secret is configured)
    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            logger.error(f"Stripe Webhook Signature Verification failed: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        # Fallback for dev/testing without webhook secret
        import json
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")

    service = BillingService(db)
    event_type = event.get("type")
    
    logger.info(f"Received Stripe Webhook: {event_type}")

    # 2. Handle the event
    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        client_id = session.get("client_reference_id") or session.get("metadata", {}).get("client_id")
        plan = session.get("metadata", {}).get("plan")
        session_id = session.get("id")
        
        if client_id and plan:
            await service.handle_stripe_webhook_success(session_id, client_id, plan)
            logger.info(f"Stripe Webhook: Subscription activated for client {client_id}")
        else:
            logger.warning(f"Stripe Webhook: Missing client_id or plan in session {session_id}")
            
    elif event_type == "invoice.paid":
        # This can be used for recurring subscription payments
        # We can implement invoice PDF generation here too for monthly renewals
        pass
        
    return {"status": "success"}
