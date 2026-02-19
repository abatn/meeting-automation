from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base
from .pv import PV # Import PV model
from .recording import Recording # Import Recording model

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DG = "dg"
    MANAGER = "manager"
    PARTICIPANT = "participant"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.PARTICIPANT)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False) # Added is_superuser column
    is_mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Beziehungen
    organized_meetings = relationship("Meeting", back_populates="organizer", foreign_keys="Meeting.organizer_id")
    assigned_actions = relationship("Action", back_populates="assignee", foreign_keys="Action.assigned_to")
    audit_logs = relationship("AuditLog", back_populates="user")
    pvs = relationship("PV", back_populates="validator", foreign_keys=[PV.validated_by_id])
    generated_pvs = relationship("PV", back_populates="generator", foreign_keys=[PV.generated_by_id])
    recordings = relationship("Recording", back_populates="uploader") # Add recordings relationship
    transcriptions = relationship("Transcription", back_populates="created_by") # Add transcriptions relationship
