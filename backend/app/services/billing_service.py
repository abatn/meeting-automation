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
    "GRATUIT": {"minutes": 120, "price": 0.0},
    "PRO": {"minutes": 1800, "price": 99.0},
    "ENTREPRISE": {"minutes": 3600, "price": 499.0}
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

    async def create_checkout_session(
        self, client_id: str, plan_name: str, success_url: str, cancel_url: str,
        customer_email: Optional[str] = None
    ) -> Dict[str, str]:
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

        # Retrieve existing Stripe customer if available
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()
        stripe_customer_id = getattr(client, "stripe_customer_id", None) if client else None

        try:
            session_params = dict(
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
                },
                subscription_data={
                    "metadata": {
                        "client_id": client_id,
                        "plan": plan_name
                    }
                }
            )

            if stripe_customer_id:
                session_params["customer"] = stripe_customer_id
            elif customer_email:
                session_params["customer_email"] = customer_email

            session = stripe.checkout.Session.create(**session_params)
            return {
                "checkout_url": session.url,
                "session_id": session.id
            }
        except Exception as e:
            logger.error(f"Stripe Session Creation failed: {e}")
            raise e

    async def handle_stripe_webhook_success(
        self, stripe_session_id: str, client_id: str, plan: str,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None
    ):
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
        if stripe_customer_id:
            client.stripe_customer_id = stripe_customer_id
        if stripe_subscription_id:
            client.stripe_subscription_id = stripe_subscription_id
        
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
        if client and client.subscription_end_date:
            next_billing = client.subscription_end_date.strftime("%B %d, %Y")
        elif client and client.subscription_start_date:
            from datetime import timedelta
            next_billing = (client.subscription_start_date + timedelta(days=30)).strftime("%B %d, %Y")
        else:
            from datetime import timedelta
            next_billing = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%B %d, %Y")

        return {
            "period": period,
            "minutes_used": minutes_this_period,
            "minutes_included": client.minutes_included if client else 0,
            "remaining": (client.minutes_included or 0) - minutes_this_period if client else 0,
            "next_billing_date": next_billing
        }

    async def switch_plan(self, client_id: str, new_plan: str, proration: str = "create_prorations") -> Dict[str, Any]:
        """
        Switch subscription plan (upgrade/downgrade).
        proration: "create_prorations" (default), "none", or "always_invoice"
        """
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            raise ValueError("Client not found")

        # Bei echter Stripe-Verbindung: Doppel-Switch verhindern (Stripe würde
        # sonst unnötig belastet). Für den Admin-Fallback (kein Stripe-Sub) ist
        # Idempotenz erlaubt — der Switch bleibt einfach ein Mock-Switch.
        if client.stripe_subscription_id and client.subscription_plan and client.subscription_plan.value == new_plan:
            raise ValueError(f"Already on {new_plan} plan")

        new_price_id = settings.STRIPE_PRICE_ID_PRO if new_plan == "PRO" else settings.STRIPE_PRICE_ID_ENTREPRISE

        if not settings.STRIPE_API_KEY or not new_price_id or not new_price_id.startswith("price_"):
            # Mock mode — update DB directly
            mins_inc, _ = await self._get_plan_details_from_cms(new_plan)
            client.subscription_plan = SubscriptionPlan[new_plan]
            client.minutes_included = mins_inc
            self.db.add(client)
            await self.db.commit()
            await AuditService.log_action(
                db=self.db, client_id=client_id,
                action="PLAN_SWITCH_MOCK", table_name="clients",
                record_id=client_id,
                new_values={"new_plan": new_plan, "mode": "mock"}
            )
            return {"status": "mock_switched", "new_plan": new_plan}

        try:
            # Get current subscription to find the price item
            subscription = stripe.Subscription.retrieve(client.stripe_subscription_id)
            if not subscription.get("items", {}).get("data"):
                raise ValueError("No subscription items found")

            current_item_id = subscription["items"]["data"][0]["id"]

            # Update subscription in Stripe
            updated_sub = stripe.Subscription.modify(
                client.stripe_subscription_id,
                items=[{
                    "id": current_item_id,
                    "price": new_price_id,
                }],
                proration_behavior=proration,
                metadata={
                    "client_id": client_id,
                    "plan": new_plan
                }
            )

            # Update client in DB
            mins_inc, _ = await self._get_plan_details_from_cms(new_plan)
            client.subscription_plan = SubscriptionPlan[new_plan]
            client.minutes_included = mins_inc
            self.db.add(client)
            await self.db.commit()

            await AuditService.log_action(
                db=self.db, client_id=client_id,
                action="PLAN_SWITCH", table_name="clients",
                record_id=client_id,
                new_values={
                    "new_plan": new_plan,
                    "stripe_subscription_id": client.stripe_subscription_id,
                    "proration": proration
                }
            )

            logger.info(f"Plan switched for {client_id}: → {new_plan}")
            return {"status": "switched", "new_plan": new_plan, "subscription_id": updated_sub.id}

        except stripe.error.StripeError as e:
            logger.error(f"Stripe plan switch failed: {e}")
            raise ValueError(f"Stripe error: {str(e)}")

    async def cancel_subscription(self, client_id: str, at_period_end: bool = True) -> Dict[str, Any]:
        """
        Cancel subscription.
        at_period_end=True: cancel at end of billing period (default)
        at_period_end=False: cancel immediately
        """
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            raise ValueError("Client not found")

        if not client.stripe_subscription_id:
            raise ValueError("No active Stripe subscription")

        if not settings.STRIPE_API_KEY:
            # Mock mode
            client.subscription_status = SubscriptionStatus.DISABLED
            self.db.add(client)
            await self.db.commit()
            await AuditService.log_action(
                db=self.db, client_id=client_id,
                action="SUBSCRIPTION_CANCELLED_MOCK", table_name="clients",
                record_id=client_id,
                new_values={"at_period_end": at_period_end, "mode": "mock"}
            )
            return {"status": "mock_cancelled", "at_period_end": at_period_end}

        try:
            if at_period_end:
                # Cancel at period end — subscription stays active until then
                updated_sub = stripe.Subscription.modify(
                    client.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                # Don't change status yet — it stays ACTIVE until period end
            else:
                # Cancel immediately
                stripe.Subscription.delete(client.stripe_subscription_id)
                client.subscription_status = SubscriptionStatus.DISABLED
                client.subscription_end_date = datetime.now(timezone.utc)
                self.db.add(client)

            await self.db.commit()

            await AuditService.log_action(
                db=self.db, client_id=client_id,
                action="SUBSCRIPTION_CANCELLED", table_name="clients",
                record_id=client_id,
                new_values={
                    "at_period_end": at_period_end,
                    "stripe_subscription_id": client.stripe_subscription_id
                }
            )

            logger.info(f"Subscription cancelled for {client_id} (at_period_end={at_period_end})")
            return {"status": "cancelled", "at_period_end": at_period_end}

        except stripe.error.StripeError as e:
            logger.error(f"Stripe cancellation failed: {e}")
            raise ValueError(f"Stripe error: {str(e)}")

    async def create_billing_portal_session(self, client_id: str, return_url: str) -> Dict[str, str]:
        """
        Create Stripe Customer Portal session for self-service.
        Customer can: update payment method, view invoices, cancel subscription.
        """
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            raise ValueError("Client not found")

        if not client.stripe_customer_id:
            raise ValueError("No Stripe customer. Subscribe first via checkout.")

        if not settings.STRIPE_API_KEY:
            return {
                "portal_url": f"{return_url}?portal=mock",
                "status": "mock"
            }

        try:
            session = stripe.billing_portal.Session.create(
                customer=client.stripe_customer_id,
                return_url=return_url
            )
            return {"portal_url": session.url, "status": "active"}

        except stripe.error.StripeError as e:
            logger.error(f"Stripe portal session failed: {e}")
            raise ValueError(f"Stripe error: {str(e)}")

    async def check_usage_limit(self, client_id: str) -> Dict[str, Any]:
        """
        Check if client has exceeded usage limit.
        Returns {"allowed": bool, "usage_percent": float, "remaining": int, "reason": str}
        """
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            return {"allowed": False, "usage_percent": 0, "remaining": 0, "reason": "Client not found"}

        minutes_included = client.minutes_included or 0
        minutes_used = client.minutes_used or 0

        # GRATUIT plan: no limit enforcement (free tier)
        if not client.subscription_plan or client.subscription_plan.value == "GRATUIT":
            return {"allowed": True, "usage_percent": 0, "remaining": 999999, "reason": "GRATUIT plan"}

        if minutes_included <= 0:
            return {"allowed": True, "usage_percent": 0, "remaining": 999999, "reason": "No limit set"}

        usage_percent = (minutes_used / minutes_included) * 100
        remaining = max(0, minutes_included - minutes_used)

        # Hard limit: 100% — block new meetings
        if usage_percent >= 100:
            return {
                "allowed": False,
                "usage_percent": round(usage_percent, 1),
                "remaining": 0,
                "reason": f"Usage limit reached ({minutes_used}/{minutes_included} minutes). Upgrade your plan."
            }

        return {
            "allowed": True,
            "usage_percent": round(usage_percent, 1),
            "remaining": remaining,
            "reason": "OK"
        }

    async def get_usage_status(self, client_id: str) -> Dict[str, Any]:
        """
        Get detailed usage status for frontend display.
        Returns usage info with alert levels.
        """
        period = datetime.now(timezone.utc).strftime("%Y-%m")

        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            return {"error": "Client not found"}

        minutes_included = client.minutes_included or 0
        minutes_used = client.minutes_used or 0

        # Calculate from usage_minutes table for current period
        usage_stmt = select(func.sum(UsageMinute.minutes)).where(
            UsageMinute.client_id == client_id,
            UsageMinute.period == period
        )
        usage_result = await self.db.execute(usage_stmt)
        period_minutes = usage_result.scalar() or 0

        usage_percent = 0
        if minutes_included > 0:
            usage_percent = round((period_minutes / minutes_included) * 100, 1)

        # Determine alert level
        if usage_percent >= 100:
            alert_level = "exceeded"
            alert_message = f"Usage limit reached ({period_minutes}/{minutes_included} min). Create new meetings blocked."
        elif usage_percent >= 80:
            alert_level = "warning"
            alert_message = f"Usage at {usage_percent}% ({period_minutes}/{minutes_included} min). Consider upgrading."
        elif usage_percent >= 60:
            alert_level = "info"
            alert_message = f"Usage at {usage_percent}% ({period_minutes}/{minutes_included} min)."
        else:
            alert_level = "ok"
            alert_message = f"Usage at {usage_percent}% ({period_minutes}/{minutes_included} min)."

        return {
            "period": period,
            "minutes_used": period_minutes,
            "minutes_included": minutes_included,
            "remaining": max(0, minutes_included - period_minutes),
            "usage_percent": usage_percent,
            "alert_level": alert_level,
            "alert_message": alert_message,
            "plan": client.subscription_plan.value if client.subscription_plan else "GRATUIT",
            "stripe_subscription_id": client.stripe_subscription_id,
            "can_create_meeting": usage_percent < 100 or (not client.subscription_plan or client.subscription_plan.value == "GRATUIT")
        }
