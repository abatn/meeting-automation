from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.app.models.action import ActionStatus

class ActionBase(BaseModel):
    description: str
    meeting_id: int
    assigned_to: int
    due_date: datetime
    priority: Optional[int] = Field(None, ge=1, le=5) # 1 (highest) to 5 (lowest)

class ActionCreate(ActionBase):
    pass

class ActionUpdate(BaseModel):
    description: Optional[str] = None
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    status: Optional[ActionStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=5)

class ActionResponse(ActionBase):
    id: int
    status: ActionStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True