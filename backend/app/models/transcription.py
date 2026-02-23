from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Float, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from app.core.database import Base

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    recording_id = Column(String, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False)
    
    full_text = Column(Text)
    language = Column(String) # Detected language
    
    status = Column(String, default="pending") # pending, processing, completed, failed
    
    # Store diarization segments as JSON
    segments = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    meeting = relationship("Meeting", back_populates="transcriptions")
    recording = relationship("Recording", back_populates="transcriptions")

class Segment(Base):
    __tablename__ = "transcription_segments"

    id = Column(String, primary_key=True, index=True)
    transcription_id = Column(String, ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    
    speaker_id = Column(String, ForeignKey("speakers.id"), nullable=True)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    confidence = Column(Float)
    
    # Metadata for code-switching (AR/FR/EN)
    language_code = Column(String)

    speaker = relationship("Speaker", back_populates="segments")

class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    name = Column(String) # e.g., "Speaker 1" or real name if identified
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    segments = relationship("Segment", back_populates="speaker")