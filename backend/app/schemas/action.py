from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OVERDUE = "OVERDUE"


class ActionBase(BaseModel):
    client_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: ActionStatus = ActionStatus.PENDING
    due_date: Optional[datetime] = None
    priority: str = "medium"
    meeting_id: str
    assigned_to: Optional[str] = None


class ActionCreate(ActionBase):
    pass


class ActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ActionStatus] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None
    assigned_to: Optional[str] = None


class Action(ActionBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ActionAutomation(BaseModel):
    id: str
    title: str
    due_date: Optional[datetime]
    assignee_name: Optional[str]
    assignee_phone: Optional[str]
    manager_email: Optional[str]

    class Config:
        from_attributes = True

class SuggestionStatus(str, Enum):
    SUGGESTED = "SUGGESTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class ActionSuggestionBase(BaseModel):
    client_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    suggested_assignee: Optional[str] = None
    confidence_score: Optional[float] = None
    status: SuggestionStatus = SuggestionStatus.SUGGESTED

class ActionSuggestionCreate(ActionSuggestionBase):
    meeting_id: str

class ActionSuggestion(ActionSuggestionBase):
    id: str
    meeting_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Analytics Schemas ---

class ActionPattern(BaseModel):
    title: str
    count: int

class ActionStatistics(BaseModel):
    suggested_assignee: Optional[str]
    total_suggestions: int
    accepted_count: int
    rejected_count: int

