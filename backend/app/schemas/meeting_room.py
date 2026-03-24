from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class MeetingRoomBase(BaseModel):
    name: str
    location_description: Optional[str] = None
    capacity: Optional[int] = None

class MeetingRoomCreate(MeetingRoomBase):
    pass

class MeetingRoomUpdate(BaseModel):
    name: Optional[str] = None
    location_description: Optional[str] = None
    capacity: Optional[int] = None

class MeetingRoom(MeetingRoomBase):
    id: str
    client_id: str
    created_at: datetime

    class Config:
        from_attributes = True
