from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime
from backend.app.models.recording import RecordingStatus # Import RecordingStatus enum

class RecordingBase(BaseModel):
    meeting_id: int
    file_path: Optional[str] = None # Changed from file_url to file_path, made optional
    duration: Optional[float] = None  # in Sekunden, made optional
    file_size: Optional[int] = None # in Bytes, made optional
    status: RecordingStatus = RecordingStatus.UPLOADING # Added status field
    transcription_id: Optional[int] = None

class RecordingCreate(BaseModel):
    meeting_id: int
    # file_path, duration, file_size, and status will be set by the service during upload
    # uploader_id will be set by the service from the authenticated user
    # transcription_id is optional and set later

class RecordingUpdate(BaseModel):
    file_path: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    status: Optional[RecordingStatus] = None # Added status for updates
    transcription_id: Optional[int] = None

class RecordingResponse(RecordingBase):
    id: int
    uploader_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    uploaded_at: datetime # Added uploaded_at
    transcribed_at: Optional[datetime] = None # Added transcribed_at

    class Config:
        orm_mode = True

class RecordingUploadResponse(BaseModel):
    id: int
    status: RecordingStatus
    message: str