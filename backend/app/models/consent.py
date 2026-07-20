"""Consent management model (Phase 163 — INPDP Art.47 / Art.5 + GDPR).

Stores explicit user consent for each processing category:
  C1 = AUDIO (recording + transcription)        — required for core service
  C2 = VOICE (biometric voiceprint enrollment)  — optional
  C3 = SHARING (AI sub-processors Gladia/Mistral) — required
  C4 = STORAGE (CNPG + S3 retention)            — required

"Löschen ist verboten": consents are never deleted, only marked withdrawn
(withdrawn_at set) to keep a full audit trail.
"""
from __future__ import annotations

import enum
from typing import Optional
from datetime import datetime

from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.config import settings


class ConsentType(str, enum.Enum):
    C1_AUDIO = "C1_AUDIO"
    C2_VOICE = "C2_VOICE"
    C3_SHARING = "C3_SHARING"
    C4_STORAGE = "C4_STORAGE"

    @property
    def is_required(self) -> bool:
        # C2 (VOICE) is the only optional consent
        return self is not ConsentType.C2_VOICE


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[str] = mapped_column(
        String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(ConsentType, name="consent_type"), nullable=False, index=True
    )
    consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consent_version: Mapped[str] = mapped_column(String, nullable=False, default="1.0")
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ConsentLog user={self.user_id} type={self.consent_type.value} "
            f"consented={self.consented}>"
        )
