from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, Integer, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base

# TYPE_CHECKING imports
if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.transcription import Transcription
    from app.models.client import Client


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE")
    )
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, default="uploaded"
    )  # uploaded, transcribing, analyzing, completed, failed
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client")
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="recordings")
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="recording", cascade="all, delete-orphan"
    )
    transcriptions: Mapped[List["Transcription"]] = relationship(
        "Transcription", back_populates="recording"
    )


class Chunk(Base):
    __tablename__ = "recording_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    recording_id: Mapped[str] = mapped_column(
        String, ForeignKey("recordings.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)

    recording: Mapped["Recording"] = relationship("Recording", back_populates="chunks")
