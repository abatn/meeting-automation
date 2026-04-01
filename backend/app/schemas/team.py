from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

class TeamMemberBase(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = "participant"

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None

class TeamMember(TeamMemberBase):
    id: str
    client_id: str
    status: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TeamSearchResult(BaseModel):
    id: Optional[str] = None
    full_name: str
    email: str
    source: str # "user" or "team_member"
    position: Optional[str] = None
    department: Optional[str] = None
