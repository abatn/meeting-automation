from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict, computed_field
from backend.app.schemas.user import UserResponse

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
    title: str
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
    updated_at: Optional[datetime] = None
    validator: Optional[UserResponse] = Field(default=None, alias='validator_user')
    generator: Optional[UserResponse] = Field(default=None, alias='generator_user')

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)



from backend.app.models.pv import PVStatus

class PVValidationResponse(BaseModel):
    validationComment: Optional[str] = None
    status: PVStatus
    validated_at: Optional[datetime] = None
    validator: Optional[UserResponse] = None

    @computed_field
    @property
    def isValidated(self) -> bool:
        return self.status == PVStatus.VALIDATED

    model_config = ConfigDict(from_attributes=True)

