from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.facture import FactureStatus

class FactureBase(BaseModel):
    amount: float
    currency: str = "USD"
    status: FactureStatus = FactureStatus.PENDING
    due_date: Optional[datetime] = None

class FactureCreate(FactureBase):
    client_id: str
    stripe_invoice_id: Optional[str] = None

class FactureUpdate(BaseModel):
    status: Optional[FactureStatus] = None
    paid_at: Optional[datetime] = None
    invoice_pdf_url: Optional[str] = None

class Facture(FactureBase):
    id: str
    client_id: str
    stripe_invoice_id: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class UsageMinuteBase(BaseModel):
    minutes: int
    period: str

class UsageMinuteCreate(UsageMinuteBase):
    client_id: str
    meeting_id: Optional[str] = None

class UsageMinute(UsageMinuteBase):
    id: str
    client_id: str
    meeting_id: Optional[str] = None
    recorded_at: datetime

    class Config:
        from_attributes = True

class CheckoutSessionCreate(BaseModel):
    plan: str # "PRO" or "ENTREPRISE"
    success_url: str
    cancel_url: str

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
