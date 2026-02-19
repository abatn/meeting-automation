from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from backend.app.models.recording import RecordingStatus # Import RecordingStatus enum

class RecordingBase(BaseModel):
    meeting_id: int
    uploader_id: int # Add uploader_id to base schema
    file_path: str # Made non-optional
    duration: float  # in Sekunden, made non-optional
    file_size: int # in Bytes, made non-optional
    status: RecordingStatus = RecordingStatus.UPLOADING
    transcription_id: Optional[int] = None

class RecordingCreate(RecordingBase): # Inherit from RecordingBase
    pass # All fields are now defined in RecordingBase

class RecordingUpdate(BaseModel):
    file_path: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    status: Optional[RecordingStatus] = None # Added status for updates
    transcription_id: Optional[int] = None

class RecordingResponse(RecordingBase):
    id: int
    uploader_id: int
    uploaded_at: datetime
    transcribed_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class RecordingUploadResponse(BaseModel):
    id: int
    status: RecordingStatus
    message: str