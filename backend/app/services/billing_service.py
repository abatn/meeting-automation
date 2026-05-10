import uuid
import logging
import stripe
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.client import Client, SubscriptionPlan, SubscriptionStatus
from app.models.facture import Facture, FactureStatus
from app.models.usage_minute import UsageMinute
from app.models.cms import PricingPlan
from app.services.pdf_service import PDFService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_API_KEY

# Fallback values if CMS pricing_plans not found
DEFAULT_PLAN_CONFIG = {
    "GRATUIT": {"minutes": 600, "price": 0.0},
    "PRO": {"minutes": 3000, "price": 99.0},
    "ENTREPRISE": {"minutes": 12000, "price": 499.0}
}


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pdf_service = PDFService()

    async def _get_plan_details_from_cms(self, plan_code: str) -> tuple:
        """
        Get minutes_included and price from CMS pricing_plans.
        Returns (minutes_included, price_monthly) tuple.
        Falls back to hardcoded defaults if not found.
        """
        try:
            stmt = select(PricingPlan).where(
                PricingPlan.plan_code == plan_code,
                PricingPlan.is_active == True
            )
            result = await self.db.execute(stmt)
            pricing_plan = result.scalar_one_or_none()
            
            if pricing_plan:
                mins = pricing_plan.minutes_included or DEFAULT_PLAN_CONFIG.get(plan_code, {}).get("minutes", 0)
                price = float(pricing_plan.price_monthly)
                logger.info(f"Using CMS pricing for {plan_code}: {mins} minutes, ${price}")
                return mins, price
        except Exception as e:
            logger.warning(f"Failed to get plan details from CMS for {plan_code}: {e}")
        
        # Fallback to defaults
        config = DEFAULT_PLAN_CONFIG.get(plan_code, {"minutes": 0, "price": 0.0})
        return config["minutes"], config["price"]

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
        Creates a real Stripe Checkout Session.
        Falls back to mock if API Key is not set.
        """
        price_id = settings.STRIPE_PRICE_ID_PRO if plan_name == "PRO" else settings.STRIPE_PRICE_ID_ENTREPRISE
        
        if not settings.STRIPE_API_KEY or "price_" not in price_id:
            logger.warning("Stripe API Key or Price ID missing. Falling back to Mock.")
            session_id = f"mock_{uuid.uuid4().hex[:12]}"
            return {
                "checkout_url": f"{success_url}?session_id={session_id}",
                "session_id": session_id
            }

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=cancel_url,
                client_reference_id=client_id,
                metadata={
                    "client_id": client_id,
                    "plan": plan_name
                }
            )
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
        except Exception as e:
            logger.error(f"Stripe Session Creation failed: {e}")
            raise e

    async def handle_stripe_webhook_success(self, stripe_session_id: str, client_id: str, plan: str):
        """Processes successful payment, activates subscription, and generates PDF."""
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
        
        # Get minute quota and price from CMS pricing_plans
        mins_inc, amount = await self._get_plan_details_from_cms(plan)
        client.minutes_included = mins_inc
            
        self.db.add(client)
        
        # Create initial invoice record
        facture_id = str(uuid.uuid4())
        invoice_num = f"INV-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"
        
        facture = Facture(
            id=facture_id,
            client_id=client_id,
            amount=amount,
            currency="USD",
            status=FactureStatus.PAID,
            paid_at=datetime.now(timezone.utc),
            stripe_invoice_id=stripe_session_id # Or real invoice ID if available
        )
        self.db.add(facture)
        
        # Generate PDF Facture
        try:
            invoice_data = {
                "invoice_id": facture_id,
                "invoice_number": invoice_num,
                "date": datetime.now().strftime("%d/%m/%Y"),
                "company_name": client.company_name,
                "client_id": client_id,
                "plan_name": plan,
                "period": datetime.now().strftime("%B %Y"),
                "amount": amount,
                "currency": "USD",
                "minutes_included": mins_inc
            }
            pdf_url = self.pdf_service.generate_invoice_pdf(invoice_data)
            facture.invoice_pdf_url = pdf_url
        except Exception as e:
            logger.error(f"Failed to attach PDF to invoice: {e}")

        await self.db.commit()
        
        # Log to Audit Trail
        await AuditService.log_action(
            db=self.db,
            client_id=client_id,
            action="PAYMENT_SUCCESS",
            table_name="factures",
            record_id=facture_id,
            new_values={"plan": plan, "amount": amount, "stripe_session": stripe_session_id}
        )
        
        logger.info(f"Subscription activated and Facture generated for {client.company_name}")

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
        
        # Calculate next billing date
        next_billing = None
        if client and client.subscription_start_date:
            # Simple approximation: start_date + 30 days
            from datetime import timedelta
            next_billing = (client.subscription_start_date + timedelta(days=30)).strftime("%B %d, %Y")
        else:
            # Fallback for new accounts
            from datetime import timedelta
            next_billing = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%B %d, %Y")

        return {
            "period": period,
            "minutes_used": minutes_this_period,
            "minutes_included": client.minutes_included if client else 0,
            "remaining": (client.minutes_included or 0) - minutes_this_period if client else 0,
            "next_billing_date": next_billing
        }
