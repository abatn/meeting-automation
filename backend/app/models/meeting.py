from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import enum
from datetime import datetime
from app.core.database import Base

# TYPE_CHECKING imports
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.recording import Recording
    from app.models.transcription import Transcription
    from app.models.action import Action
    from app.models.pv import PV
    from app.models.participant import Participant
    from app.models.agenda import Agenda


class MeetingStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        SQLEnum(MeetingStatus), default=MeetingStatus.PLANNED
    )

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    creator_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_meetings")
    participants: Mapped[List["Participant"]] = relationship(
        "Participant", back_populates="meeting", cascade="all, delete-orphan"
    )
    agendas: Mapped[List["Agenda"]] = relationship(
        "Agenda", back_populates="meeting", cascade="all, delete-orphan"
    )
    recordings: Mapped[List["Recording"]] = relationship("Recording", back_populates="meeting")
    transcriptions: Mapped[List["Transcription"]] = relationship(
        "Transcription", back_populates="meeting"
    )
    actions: Mapped[List["Action"]] = relationship("Action", back_populates="meeting")
    pv: Mapped[Optional["PV"]] = relationship("PV", back_populates="meeting", uselist=False)


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id", ondelete="CASCADE"))
    user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="participants")


class Agenda(Base):
    __tablename__ = "agendas"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    meeting_id: Mapped[str] = mapped_column(String, ForeignKey("meetings.id"))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="agendas")
