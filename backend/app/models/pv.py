from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.utils.db_encryption import EncryptedText

if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.user import User


class PV(Base):
    __tablename__ = "pvs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    meeting_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(EncryptedText, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="draft"
    )  # draft, pending_review, published
    language: Mapped[str] = mapped_column(String, default="fr") # ar, fr, en

    is_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_by_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    validated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="pv")
    sections: Mapped[List["Section"]] = relationship(
        "Section", back_populates="pv", cascade="all, delete-orphan"
    )
    versions: Mapped[List["PVVersion"]] = relationship(
        "PVVersion", back_populates="pv", cascade="all, delete-orphan"
    )
    validated_by: Mapped[Optional["User"]] = relationship("User")


class PVVersion(Base):
    __tablename__ = "pv_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    pv_id: Mapped[str] = mapped_column(
        String, ForeignKey("pvs.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Stores a serialized JSON snapshot of the PV and its Sections
    snapshot_data: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    pv: Mapped["PV"] = relationship("PV", back_populates="versions")
    created_by: Mapped[Optional["User"]] = relationship("User")


class Section(Base):
    __tablename__ = "pv_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    pv_id: Mapped[str] = mapped_column(
        String, ForeignKey("pvs.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(EncryptedText, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # e.g., "intro", "discussion", "decision", "conclusion"

    pv: Mapped["PV"] = relationship("PV", back_populates="sections")
