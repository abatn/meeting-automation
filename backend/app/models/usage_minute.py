from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, ForeignKey, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client

class UsageMinute(Base):
    __tablename__ = "usage_minutes"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period: Mapped[str] = mapped_column(String, index=True)  # e.g., "2026-03"
    
    meeting_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="usage_history")
