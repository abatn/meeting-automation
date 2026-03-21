import logging
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.services.billing_service import BillingService
from app.core.config import settings

# Potential for actual Stripe integration
# import stripe

logger = logging.getLogger(__name__)
router = APIRouter()

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
    
    # In production, verify signature:
    # try:
    #     event = stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    # except Exception as e:
    #     raise HTTPException(status_code=400, detail=str(e))
    
    # For now, we allow manual triggering for testing (Mock mode)
    import json
    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    service = BillingService(db)

    # Handle the event
    event_type = event.get("type")
    
    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        client_id = session.get("client_reference_id") or session.get("metadata", {}).get("client_id")
        plan = session.get("metadata", {}).get("plan")
        session_id = session.get("id")
        
        if client_id and plan:
            await service.handle_stripe_webhook_success(session_id, client_id, plan)
            logger.info(f"Stripe Webhook: Checkout completed for client {client_id}")
            
    elif event_type == "invoice.paid":
        # Handle recurring payments
        pass
        
    return {"status": "success"}
