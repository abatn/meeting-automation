from __future__ import annotations
from typing import Optional, TYPE_CHECKING, Any, Dict
from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.client import Client


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )

    # ISO 27001 requirements
    action: Mapped[str] = mapped_column(
        String, nullable=False
    )  # e.g., "CREATE", "UPDATE", "DELETE"
    table_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="audit_logs")
    user: Mapped["User"] = relationship("User", back_populates="audit_logs")
