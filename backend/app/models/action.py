from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, Text, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import enum
from datetime import datetime
from app.core.database import Base

# TYPE_CHECKING imports to resolve F821 errors without creating circular imports at runtime
if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.user import User
    from app.models.client import Client


class ActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OVERDUE = "OVERDUE"

class SuggestionStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"

class ActionSuggestion(Base):
    __tablename__ = "action_suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[SuggestionStatus] = mapped_column(
        SQLEnum(SuggestionStatus), default=SuggestionStatus.SUGGESTED
    )
    language: Mapped[str] = mapped_column(String, default="en")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    
    meeting: Mapped["Meeting"] = relationship("Meeting")


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    meeting_id: Mapped[str] = mapped_column(
        String, ForeignKey("meetings.id", ondelete="CASCADE")
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ActionStatus] = mapped_column(
        SQLEnum(ActionStatus), default=ActionStatus.PENDING
    )
    priority: Mapped[str] = mapped_column(String, default="medium")

    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client")
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="actions")
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment", back_populates="action", cascade="all, delete-orphan"
    )

    @property
    def assignee_id(self) -> Optional[str]:
        if self.assignments:
            return self.assignments[0].user_id
        return None

    @property
    def assigned_to(self) -> Optional[str]:
        if self.assignments:
            assign = self.assignments[0]
            if assign.user:
                return assign.user.full_name or assign.user.email
            return assign.external_name or assign.external_email
        return None


class Assignment(Base):
    __tablename__ = "action_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    action_id: Mapped[str] = mapped_column(
        String, ForeignKey("actions.id", ondelete="CASCADE")
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )

    # In case user is not in system yet
    external_email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    external_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    action: Mapped["Action"] = relationship("Action", back_populates="assignments")
    user: Mapped["User"] = relationship("User")
