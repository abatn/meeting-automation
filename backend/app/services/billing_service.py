import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.client import Client, SubscriptionPlan, SubscriptionStatus
from app.models.facture import Facture, FactureStatus
from app.models.usage_minute import UsageMinute

# Potential for actual Stripe integration
# import stripe
# stripe.api_key = settings.STRIPE_API_KEY

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_usage(self, client_id: str, minutes: int, meeting_id: Optional[str] = None):
        """Records minutes used by a client for a specific meeting."""
        period = datetime.now(timezone.utc).strftime("%Y-%m")
        
        usage = UsageMinute(
            id=str(uuid.uuid4()),
            client_id=client_id,
            minutes=minutes,
            period=period,
            meeting_id=meeting_id
        )
        self.db.add(usage)
        
        # Increment client's aggregate minutes_used
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if client:
            client.minutes_used = (client.minutes_used or 0) + minutes
            self.db.add(client)
            
        await self.db.commit()
        return usage

    async def create_checkout_session(self, client_id: str, plan_name: str, success_url: str, cancel_url: str) -> Dict[str, str]:
        """
        Mocks Stripe Checkout Session creation.
        In production, this would use stripe.checkout.Session.create().
        """
        session_id = f"mock_session_{uuid.uuid4().hex[:12]}"
        
        # Determine Price ID from config
        price_id = settings.STRIPE_PRICE_ID_PRO if plan_name == "PRO" else settings.STRIPE_PRICE_ID_ENTREPRISE
        
        logger.info(f"Creating mock checkout session for client {client_id}, plan {plan_name}")
        
        return {
            "checkout_url": f"{success_url}?session_id={session_id}",
            "session_id": session_id
        }

    async def handle_stripe_webhook_success(self, stripe_session_id: str, client_id: str, plan: str):
        """Processes successful payment and activates subscription."""
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if not client:
            logger.error(f"Client {client_id} not found during payment webhook processing")
            return
            
        # Update client
        client.subscription_plan = SubscriptionPlan[plan]
        client.subscription_status = SubscriptionStatus.ACTIVE
        client.subscription_start_date = datetime.now(timezone.utc)
        
        # Set minute quota based on plan
        if plan == "PRO":
            client.minutes_included = 3000 # 50h
        elif plan == "ENTREPRISE":
            client.minutes_included = 12000 # 200h
            
        self.db.add(client)
        
        # Create initial invoice record
        facture = Facture(
            id=str(uuid.uuid4()),
            client_id=client_id,
            amount=99.0 if plan == "PRO" else 499.0,
            currency="USD",
            status=FactureStatus.PAID,
            paid_at=datetime.now(timezone.utc),
            stripe_invoice_id=f"mock_inv_{uuid.uuid4().hex[:8]}"
        )
        self.db.add(facture)
        
        await self.db.commit()
        logger.info(f"Subscription activated for client {client.company_name} (Plan: {plan})")

    async def get_client_invoices(self, client_id: str) -> List[Facture]:
        """Returns all invoices for a client."""
        stmt = select(Facture).where(Facture.client_id == client_id).order_by(Facture.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_usage_summary(self, client_id: str, period: Optional[str] = None) -> Dict[str, Any]:
        """Returns usage stats for a client."""
        if not period:
            period = datetime.now(timezone.utc).strftime("%Y-%m")
            
        stmt = select(func.sum(UsageMinute.minutes)).where(
            UsageMinute.client_id == client_id,
            UsageMinute.period == period
        )
        result = await self.db.execute(stmt)
        minutes_this_period = result.scalar() or 0
        
        client_stmt = select(Client).where(Client.id == client_id)
        client_res = await self.db.execute(client_stmt)
        client = client_res.scalar_one_or_none()
        
        return {
            "period": period,
            "minutes_used": minutes_this_period,
            "minutes_included": client.minutes_included if client else 0,
            "remaining": (client.minutes_included or 0) - minutes_this_period if client else 0
        }
