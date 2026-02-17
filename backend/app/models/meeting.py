from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base

class MeetingStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Meeting(Base):
    __tablename__ = "meetings"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    date = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Integer, nullable=False)  # in Minuten
    location = Column(String, nullable=True)
    organizer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(MeetingStatus), default=MeetingStatus.PLANNED)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Beziehungen
    organizer = relationship("User", back_populates="organized_meetings", foreign_keys=[organizer_id])
    recordings = relationship("Recording", back_populates="meeting", cascade="all, delete-orphan")
    transcriptions = relationship("Transcription", back_populates="meeting", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="meeting", cascade="all, delete-orphan")
    pv = relationship("PV", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
