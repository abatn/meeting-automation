from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from backend.app.models.meeting import MeetingStatus

class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: datetime
    duration: int  # in Minuten
    location: Optional[str] = None

class MeetingCreate(MeetingBase):
    pass

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[datetime] = None
    duration: Optional[int] = None
    location: Optional[str] = None
    status: Optional[MeetingStatus] = None

class MeetingResponse(MeetingBase):
    id: int
    organizer_id: int
    status: MeetingStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True
