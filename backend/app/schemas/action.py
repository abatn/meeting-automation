from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class ActionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionBase(BaseModel):
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

    class Config:
        from_attributes = True
