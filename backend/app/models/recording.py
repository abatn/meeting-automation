from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    file_path = Column(String, nullable=False)
    status = Column(
        String, default="uploaded"
    )  # uploaded, transcribing, analyzing, completed, failed
    file_size = Column(Integer)  # in bytes
    duration = Column(Float)     # in seconds
    format = Column(String)      # e.g., "wav", "mp3"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    meeting = relationship("Meeting", back_populates="recordings")
    chunks = relationship(
        "Chunk", back_populates="recording", cascade="all, delete-orphan"
    )
    transcriptions = relationship("Transcription", back_populates="recording")


class Chunk(Base):
    __tablename__ = "recording_chunks"

    id = Column(String, primary_key=True, index=True)
    recording_id = Column(
        String, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)

    recording = relationship("Recording", back_populates="chunks")
