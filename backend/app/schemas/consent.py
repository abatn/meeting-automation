from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ConsentGrant(BaseModel):
    consent_type: str
    consented: bool
    consent_version: str = "1.0"


class ConsentResponse(BaseModel):
    id: str
    consent_type: str
    consented: bool
    consent_version: str
    timestamp: datetime
    withdrawn_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ConsentStatusResponse(BaseModel):
    audio_recording: bool
    voice_profiling: bool
    third_party_sharing: bool
    transcript_storage: bool
