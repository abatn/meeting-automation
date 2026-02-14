from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class RecordingStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Recording(Base):
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # in Bytes
    duration = Column(Float, nullable=True)  # in Sekunden
    status = Column(Enum(RecordingStatus), default=RecordingStatus.UPLOADING)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    transcribed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Beziehungen
    meeting = relationship("Meeting", back_populates="recordings")
    transcription = relationship("Transcription", back_populates="recording", uselist=False, cascade="all, delete-orphan")