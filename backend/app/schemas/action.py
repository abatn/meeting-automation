from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ActionBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "pending"
    assignee_id: Optional[int] = None
    pv_id: int

class ActionCreate(ActionBase):
    pass

class ActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None

class ActionRead(ActionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)