from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.app.models.action import ActionStatus, ActionPriority

class ActionBase(BaseModel):
    description: str
    meeting_id: int
    assigned_to: int
    due_date: datetime
    priority: Optional[ActionPriority] = ActionPriority.MEDIUM

class ActionCreate(ActionBase):
    pass

class ActionUpdate(BaseModel):
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    status: Optional[ActionStatus] = None
    priority: Optional[ActionPriority] = None

class ActionResponse(ActionBase):
    id: int
    status: ActionStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class ActionComplete(BaseModel):
    comment: Optional[str] = None

class ActionReminderResponse(BaseModel):
    message: str
    action_id: int
    user_id: int
    timestamp: datetime
