from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.client import SubscriptionPlan, SubscriptionStatus, BillingCycle, PaymentMethod

class ClientBase(BaseModel):
    company_name: str
    subscription_plan: Optional[SubscriptionPlan] = SubscriptionPlan.GRATUIT
    subscription_status: Optional[SubscriptionStatus] = SubscriptionStatus.PENDING
    billing_cycle: Optional[BillingCycle] = BillingCycle.MONTHLY
    minutes_included: Optional[int] = 0
    minutes_used: Optional[int] = 0
    payment_method: Optional[PaymentMethod] = None
    observations: Optional[str] = None

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    company_name: Optional[str] = None
    subscription_plan: Optional[SubscriptionPlan] = None
    subscription_status: Optional[SubscriptionStatus] = None
    subscription_start_date: Optional[datetime] = None
    subscription_end_date: Optional[datetime] = None
    billing_cycle: Optional[BillingCycle] = None
    minutes_included: Optional[int] = None
    minutes_used: Optional[int] = None
    payment_method: Optional[PaymentMethod] = None
    observations: Optional[str] = None

class ClientInDBBase(ClientBase):
    id: str
    subscription_start_date: Optional[datetime]
    subscription_end_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class Client(ClientInDBBase):
    pass

class ClientInDB(ClientInDBBase):
    pass
