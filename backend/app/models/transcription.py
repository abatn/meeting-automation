from sqlalchemy import Column, String, ForeignKey, DateTime, Float, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON
from app.core.database import Base
from app.utils.db_encryption import EncryptedText


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(String, primary_key=True, index=True)
    client_id = Column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    meeting_id = Column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    recording_id = Column(
        String, ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False
    )

    full_text = Column(EncryptedText)
    language = Column(String)  # Detected language

    status = Column(String, default="pending")  # pending, processing, completed, failed

    # Store diarization segments as JSON
    segments = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    client = relationship("Client")
    meeting = relationship("Meeting", back_populates="transcriptions")
    recording = relationship("Recording", back_populates="transcriptions")


class Segment(Base):
    __tablename__ = "transcription_segments"

    id = Column(String, primary_key=True, index=True)
    transcription_id = Column(
        String, ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False
    )

    speaker_id = Column(String, ForeignKey("speakers.id"), nullable=True)
    text = Column(EncryptedText, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    confidence = Column(Float)

    # Metadata for code-switching (AR/FR/EN)
    language_code = Column(String)

    speaker = relationship("Speaker", back_populates="segments")


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(
        String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=True
    )
    client_id = Column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    name = Column(String)  # Gladia speaker label (e.g., "Speaker 0")
    resolved_name = Column(String, nullable=True)  # Resolved real name from ONNX+Mistral fusion
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    # Speaker profile fields for identification
    embedding = Column(JSON, nullable=True)  # 192-dim float array
    sample_count = Column(Integer, default=0)  # Number of samples averaged into embedding
    mapping_confidence = Column(Float, nullable=True)  # 0.0-1.0 confidence score
    mapping_method = Column(String, nullable=True)  # "embedding", "text_inference", "manual", "hybrid"
    source = Column(String, default="auto_enrolled")  # "auto_enrolled", "manual", "auto_confirmed"

    # Relationships
    segments = relationship("Segment", back_populates="speaker")
