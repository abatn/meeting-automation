from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class SpeakerBase(BaseModel):
    name: Optional[str] = None
    user_id: Optional[str] = None

class Speaker(SpeakerBase):
    id: str
    meeting_id: str

    class Config:
        from_attributes = True

class SegmentBase(BaseModel):
    speaker_id: Optional[str] = None
    text: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None
    language_code: Optional[str] = None

class Segment(SegmentBase):
    id: str
    transcription_id: str

    class Config:
        from_attributes = True

class TranscriptionBase(BaseModel):
    meeting_id: str
    recording_id: str
    full_text: Optional[str] = None
    language: Optional[str] = None
    status: Optional[str] = "pending"

class TranscriptionCreate(TranscriptionBase):
    pass

class Transcription(TranscriptionBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    segments: Optional[List[dict]] = None

    class Config:
        from_attributes = True