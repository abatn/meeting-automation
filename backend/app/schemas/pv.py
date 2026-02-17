from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

from backend.app.schemas.user import UserResponse # Import UserResponse

class PVCreate(BaseModel):
    title: str
    content: Optional[str] = None
    meeting_id: int


class PVGenerate(BaseModel):
    transcription_id: Optional[int] = None
    template: Optional[str] = None


class PVUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    decisions: Optional[List[str]] = None
    action_points: Optional[List[str]] = None


class PVValidate(BaseModel):
    comment: Optional[str] = None


class PVResponse(BaseModel):
    id: int
    meeting_id: int
    generated_by_id: int
    content: str
    summary: Optional[str] = None
    decisions: Optional[List[str]] = None
    action_points: Optional[List[str]] = None
    next_meeting_date: Optional[datetime] = None
    validated_by_id: Optional[int] = None
    validated_at: Optional[datetime] = None
    validation_comment: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    validator: Optional[UserResponse] = None
    generator: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PVValidationResponse(BaseModel):
    id: int
    is_validated: bool
    validated_at: Optional[datetime] = None
    validated_by_id: Optional[int] = None
    validation_comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
