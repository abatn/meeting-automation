from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base

class TranscriptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EDITED = "EDITED"

class Transcription(Base):
    __tablename__ = "transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    transcribed_text = Column(Text, nullable=True) # Changed from 'content' to 'transcribed_text'
    language = Column(String, nullable=True)  # ar, fr, en, mixed
    speaker_segments = Column(JSON, nullable=True)  # Array of {speaker: text, start, end}
    word_timestamps = Column(JSON, nullable=True)  # Array of {word, start, end}
    status = Column(Enum(TranscriptionStatus), default=TranscriptionStatus.PENDING)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False) # Add created_by_id
    started_at = Column(DateTime(timezone=True), nullable=True) # Add started_at
    completed_at = Column(DateTime(timezone=True), nullable=True) # Add completed_at
    failed_reason = Column(String, nullable=True) # Add failed_reason
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Beziehungen
    meeting = relationship("Meeting", back_populates="transcriptions")
    recording = relationship("Recording", back_populates="transcription")
    created_by = relationship("User", back_populates="transcriptions") # Add created_by relationship