from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"

class Action(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(ActionStatus), default=ActionStatus.PENDING)
    priority = Column(String, default="medium") # low, medium, high, urgent
    
    due_date = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    meeting = relationship("Meeting", back_populates="actions")
    assignments = relationship("Assignment", back_populates="action", cascade="all, delete-orphan")

class Assignment(Base):
    __tablename__ = "action_assignments"

    id = Column(String, primary_key=True, index=True)
    action_id = Column(String, ForeignKey("actions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # In case user is not in system yet
    external_email = Column(String)
    external_name = Column(String)
    
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    action = relationship("Action", back_populates="assignments")
    user = relationship("User")