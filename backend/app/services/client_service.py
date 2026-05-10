from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.client import Client, SubscriptionPlan, SubscriptionStatus
from app.models.cms import PricingPlan
from app.core.config import settings

logger = logging.getLogger(__name__)

# Fallback values if CMS pricing_plans not found
DEFAULT_PLAN_MINUTES = {
    SubscriptionPlan.GRATUIT: 600,    # 10 hours
    SubscriptionPlan.PRO: 3000,       # 50 hours
    SubscriptionPlan.ENTREPRISE: 12000  # 200 hours
}


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, client_id: str) -> Optional[Client]:
        """Get client by ID."""
        stmt = select(Client).where(Client.id == client_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_company_name(self, company_name: str) -> Optional[Client]:
        """Get client by company name."""
        stmt = select(Client).where(Client.company_name == company_name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_client(
        self,
        company_name: str,
        plan: SubscriptionPlan = SubscriptionPlan.GRATUIT,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    ) -> Client:
        """Create a new client (tenant)."""
        # Get minutes from CMS pricing_plans or use default
        minutes_included = await self._get_minutes_for_plan(plan)
        
        client = Client(
            id=str(uuid4()),
            company_name=company_name,
            subscription_plan=plan,
            subscription_status=status,
            subscription_start_date=datetime.now(timezone.utc),
            minutes_included=minutes_included,
            minutes_used=0
        )
        
        self.db.add(client)
        await self.db.flush()
        return client

    async def _get_minutes_for_plan(self, plan: SubscriptionPlan) -> int:
        """
        Get included minutes from CMS pricing_plans table.
        Falls back to hardcoded defaults if not found in CMS.
        """
        try:
            stmt = select(PricingPlan).where(
                PricingPlan.plan_code == plan.value,
                PricingPlan.is_active == True
            )
            result = await self.db.execute(stmt)
            pricing_plan = result.scalar_one_or_none()
            
            if pricing_plan and pricing_plan.minutes_included:
                logger.debug(f"Using CMS minutes for {plan.value}: {pricing_plan.minutes_included}")
                return pricing_plan.minutes_included
        except Exception as e:
            logger.warning(f"Failed to get minutes from CMS for {plan.value}: {e}")
        
        # Fallback to default
        return DEFAULT_PLAN_MINUTES.get(plan, 0)

    async def get_pricing_plan_by_code(self, plan_code: str) -> Optional[PricingPlan]:
        """Get pricing plan details from CMS by plan_code."""
        stmt = select(PricingPlan).where(
            PricingPlan.plan_code == plan_code,
            PricingPlan.is_active == True
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()