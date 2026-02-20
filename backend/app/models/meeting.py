from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class MeetingStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(Text)
    location = Column(String)
    status = Column(SQLEnum(MeetingStatus), default=MeetingStatus.PLANNED)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    
    creator_id = Column(String, ForeignKey("users.id"))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True) # Soft Delete

    # Relationships
    creator = relationship("User", back_populates="created_meetings")
    participants = relationship("Participant", back_populates="meeting", cascade="all, delete-orphan")
    agendas = relationship("Agenda", back_populates="meeting", cascade="all, delete-orphan")
    recordings = relationship("Recording", back_populates="meeting")
    transcriptions = relationship("Transcription", back_populates="meeting")
    actions = relationship("Action", back_populates="meeting")
    pv = relationship("PV", back_populates="meeting", uselist=False)

class Participant(Base):
    __tablename__ = "participants"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    user_id = Column(String, ForeignKey("users.id"), nullable=True) # Optional link to registered user
    email = Column(String, nullable=False)
    name = Column(String)
    role = Column(String) # e.g., "Moderator", "Secretary", "Participant"

    meeting = relationship("Meeting", back_populates="participants")

class Agenda(Base):
    __tablename__ = "agendas"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id"))
    title = Column(String)
    description = Column(String, nullable=True)
    order = Column(Integer, default=0)

    meeting = relationship("Meeting", back_populates="agendas")
