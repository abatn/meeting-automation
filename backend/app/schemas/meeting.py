from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class MeetingStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ParticipantBase(BaseModel):
    email: str
    name: Optional[str] = None
    role: Optional[str] = "Participant"

class ParticipantCreate(ParticipantBase):
    pass

class Participant(ParticipantBase):
    id: str
    meeting_id: str

    class Config:
        from_attributes = True

class AgendaBase(BaseModel):
    title: str
    description: Optional[str] = None
    order: Optional[int] = 0

class AgendaCreate(AgendaBase):
    pass

class Agenda(AgendaBase):
    id: str
    meeting_id: str

    class Config:
        from_attributes = True

class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    status: Optional[MeetingStatus] = MeetingStatus.PLANNED
    start_time: datetime
    end_time: Optional[datetime] = None

class MeetingCreate(MeetingBase):
    participants: Optional[List[ParticipantCreate]] = []
    agendas: Optional[List[AgendaCreate]] = []

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    status: Optional[MeetingStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class Meeting(MeetingBase):
    id: str
    creator_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    participants: List[Participant] = []
    agendas: List[Agenda] = []

    class Config:
        from_attributes = True