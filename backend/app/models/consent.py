import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ConsentType(str, enum.Enum):
    AUDIO_RECORDING = "audio_recording"
    VOICE_PROFILING = "voice_profiling"
    THIRD_PARTY_SHARING = "third_party_sharing"
    TRANSCRIPT_STORAGE = "transcript_storage"


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    consent_type: Mapped[str] = mapped_column(String, nullable=False)
    consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_version: Mapped[str] = mapped_column(String, nullable=False, default="1.0")
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="consents")
    client = relationship("Client")

    __table_args__ = (
        Index("ix_consent_logs_client_id", "client_id"),
        Index("ix_consent_logs_user_type", "user_id", "consent_type", unique=True),
    )
