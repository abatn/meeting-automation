from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base

class TranscriptionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Transcription(Base):
    __tablename__ = "transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    content = Column(Text, nullable=True)
    language = Column(String, nullable=True)  # ar, fr, en, mixed
    speaker_diarization = Column(JSON, nullable=True)  # Array von {speaker: text, start, end}
    word_timestamps = Column(JSON, nullable=True)  # Array von {word, start, end}
    status = Column(Enum(TranscriptionStatus), default=TranscriptionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Beziehungen
    meeting = relationship("Meeting", back_populates="transcriptions")
    recording = relationship("Recording", back_populates="transcription")