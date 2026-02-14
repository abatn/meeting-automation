from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class RecordingBase(BaseModel):
    meeting_id: int
    file_url: HttpUrl
    duration: int  # in Sekunden
    file_size: int # in Bytes
    transcription_id: Optional[int] = None

class RecordingCreate(RecordingBase):
    pass

class RecordingUpdate(BaseModel):
    file_url: Optional[HttpUrl] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    transcription_id: Optional[int] = None

class RecordingResponse(RecordingBase):
    id: int
    uploader_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True