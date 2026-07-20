"""Consent API schemas (Phase 163)."""
from typing import Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConsentType(str, Enum):
    C1_AUDIO = "C1_AUDIO"
    C2_VOICE = "C2_VOICE"
    C3_SHARING = "C3_SHARING"
    C4_STORAGE = "C4_STORAGE"


class ConsentGrant(BaseModel):
    """A single consent being granted (or denied) by the user."""
    consent_type: ConsentType
    consented: bool = True


class ConsentRequest(BaseModel):
    """Payload sent by the registration form / settings page."""
    consents: list[ConsentGrant]
    consent_version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ConsentWithdrawRequest(BaseModel):
    consent_type: ConsentType


class ConsentRecord(BaseModel):
    consent_type: ConsentType
    consented: bool
    consent_version: str
    created_at: datetime
    withdrawn_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConsentStatusResponse(BaseModel):
    """Aggregated consent state for the current user."""
    consents: list[ConsentRecord]
    all_required_granted: bool
