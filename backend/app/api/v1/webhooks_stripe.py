import logging
import stripe
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select
from app.api import deps
from app.models.client import Client
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
        stripe_customer_id = session.get("customer")
        stripe_subscription_id = session.get("subscription")

        if client_id and plan:
            await service.handle_stripe_webhook_success(
                session_id, client_id, plan,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id
            )
            logger.info(f"Stripe Webhook: Subscription activated for client {client_id}")
        else:
            logger.warning(f"Stripe Webhook: Missing client_id or plan in session {session_id}")

    elif event_type == "invoice.paid":
        invoice = event.get("data", {}).get("object", {})
        stripe_invoice_id = invoice.get("id")
        amount_paid = invoice.get("amount_paid", 0) / 100  # cents → dollars
        stripe_sub_id = invoice.get("subscription")
        customer_id = invoice.get("customer")

        if stripe_sub_id:
            stmt = select(Client).where(Client.stripe_subscription_id == stripe_sub_id)
            res = await db.execute(stmt)
            client = res.scalar_one_or_none()
        elif customer_id:
            stmt = select(Client).where(Client.stripe_customer_id == customer_id)
            res = await db.execute(stmt)
            client = res.scalar_one_or_none()
        else:
            client = None

        if client:
            import uuid as _uuid
            from app.models.facture import Facture, FactureStatus
            from datetime import datetime, timezone

            facture = Facture(
                id=str(_uuid.uuid4()),
                client_id=client.id,
                amount=amount_paid,
                currency="USD",
                status=FactureStatus.PAID,
                paid_at=datetime.now(timezone.utc),
                stripe_invoice_id=stripe_invoice_id
            )
            db.add(facture)
            await db.commit()
            logger.info(f"Stripe Webhook: invoice.paid recorded for client {client.id} — ${amount_paid}")
        else:
            logger.warning(f"Stripe Webhook: invoice.paid — no client matched subscription {stripe_sub_id}")

    elif event_type in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        subscription = event.get("data", {}).get("object", {})
        stripe_sub_id = subscription.get("id")
        sub_status = subscription.get("status")  # active, past_due, canceled, unpaid, trialing
        current_period_end = subscription.get("current_period_end")  # unix timestamp
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)

        stmt = select(Client).where(Client.stripe_subscription_id == stripe_sub_id)
        res = await db.execute(stmt)
        client = res.scalar_one_or_none()

        if client:
            from app.models.client import SubscriptionStatus
            from datetime import datetime, timezone

            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "trialing": SubscriptionStatus.ACTIVE,
                "past_due": SubscriptionStatus.ACTIVE,
                "canceled": SubscriptionStatus.DISABLED,
                "unpaid": SubscriptionStatus.DISABLED,
                "incomplete_expired": SubscriptionStatus.DISABLED,
                "incomplete": SubscriptionStatus.PENDING,
            }
            new_status = status_map.get(sub_status, SubscriptionStatus.ACTIVE)
            client.subscription_status = new_status

            if current_period_end:
                client.subscription_end_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)

            await db.commit()
            logger.info(f"Stripe Webhook: subscription {event_type} → status={sub_status}, client={client.id}")
        else:
            logger.warning(f"Stripe Webhook: subscription {event_type} — no client matched subscription {stripe_sub_id}")

    return {"status": "success"}
