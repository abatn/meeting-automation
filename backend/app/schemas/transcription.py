from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class TranscriptionStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EDITED = "EDITED"

class SpeakerSegment(BaseModel):
    speaker: Optional[str] = Field(None, description="Identified speaker for the segment")
    text: str = Field(..., description="Transcribed text for the segment")
    start: float = Field(..., description="Start time of the segment in seconds")
    end: float = Field(..., description="End time of the segment in seconds")

class WordTimestamp(BaseModel):
    word: str = Field(..., description="The transcribed word")
    start: float = Field(..., description="Start time of the word in seconds")
    end: float = Field(..., description="End time of the word in seconds")
    confidence: Optional[float] = Field(None, description="Confidence score for the word transcription")

class TranscriptionBase(BaseModel):
    recording_id: int = Field(..., description="ID of the associated recording")
    language: Optional[str] = Field(None, max_length=10, description="Detected or specified language of the transcription (e.g., 'en', 'de')")
    status: TranscriptionStatus = Field(TranscriptionStatus.PENDING, description="Current status of the transcription job")
    transcribed_text: Optional[str] = Field(None, description="The full transcribed text")
    speaker_segments: Optional[List[SpeakerSegment]] = Field(None, description="List of speaker segments if diarization is enabled")
    word_timestamps: Optional[List[WordTimestamp]] = Field(None, description="List of word-level timestamps")
    duration: Optional[float] = Field(None, description="Duration of the transcribed audio in seconds")
    started_at: Optional[datetime] = Field(None, description="Timestamp when the transcription job started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the transcription job completed")
    failed_reason: Optional[str] = Field(None, description="Reason for failure if status is FAILED")

class TranscriptionCreate(BaseModel):
    recording_id: int = Field(..., description="ID of the associated recording")
    language: Optional[str] = Field(None, max_length=10, description="Optional: Language to use for transcription (e.g., 'en', 'de')")
    enable_diarization: bool = Field(False, description="Optional: Whether to enable speaker diarization")

class TranscriptionUpdate(BaseModel):
    language: Optional[str] = Field(None, max_length=10, description="Detected or specified language of the transcription (e.g., 'en', 'de')")
    status: Optional[TranscriptionStatus] = Field(None, description="Current status of the transcription job")
    transcribed_text: Optional[str] = Field(None, description="The full transcribed text")
    speaker_segments: Optional[List[SpeakerSegment]] = Field(None, description="List of speaker segments if diarization is enabled")
    word_timestamps: Optional[List[WordTimestamp]] = Field(None, description="List of word-level timestamps")
    duration: Optional[float] = Field(None, description="Duration of the transcribed audio in seconds")
    started_at: Optional[datetime] = Field(None, description="Timestamp when the transcription job started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the transcription job completed")
    failed_reason: Optional[str] = Field(None, description="Reason for failure if status is FAILED")

class TranscriptionResponse(TranscriptionBase):
    id: int = Field(..., description="Unique ID of the transcription")
    created_at: datetime = Field(..., description="Timestamp when the transcription entry was created")
    updated_at: datetime = Field(..., description="Timestamp when the transcription entry was last updated")

    class Config:
        orm_mode = True

class TranscriptionStatusResponse(BaseModel):
    id: int = Field(..., description="Unique ID of the transcription")
    status: TranscriptionStatus = Field(..., description="Current status of the transcription job")
    progress: Optional[float] = Field(None, description="Progress percentage (0-100) if available")
    message: Optional[str] = Field(None, description="Status message")
    failed_reason: Optional[str] = Field(None, description="Reason for failure if status is FAILED")