<<<<<<< HEAD
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
=======
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ActionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)

class ActionBase(BaseModel):
    title: str
    description: Optional[str] = None
<<<<<<< HEAD
    due_date: Optional[datetime] = None
    status: str = "pending"
    assignee_id: Optional[int] = None
    pv_id: int
=======
    status: ActionStatus = ActionStatus.PENDING
    due_date: Optional[datetime] = None
    priority: str = "medium"
    meeting_id: str
    assigned_to: Optional[str] = None
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)

class ActionCreate(ActionBase):
    pass

class ActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
<<<<<<< HEAD
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None

class ActionRead(ActionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
=======
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
>>>>>>> b4b03e9 (feat: implement missing API routes for actions, reports, transcriptions and pv)
