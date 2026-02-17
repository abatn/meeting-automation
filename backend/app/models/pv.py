from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base
from ..utils.json_encoded_text import JSONEncodedText # Import from utility

class PVStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_VALIDATION = "pending_validation"
    VALIDATED = "validated"
    REJECTED = "rejected"

class PV(Base):
    __tablename__ = "pvs"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, unique=True)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False) # Added generated_by_id
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    decisions = Column(JSONEncodedText, nullable=True) # Using imported JSONEncodedText
    action_points = Column(JSONEncodedText, nullable=True)
    next_meeting_date = Column(DateTime(timezone=True), nullable=True)
    validated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_comment = Column(Text, nullable=True)
    status = Column(Enum(PVStatus), default=PVStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Beziehungen
    meeting = relationship("Meeting", back_populates="pv")
    generator = relationship("User", foreign_keys=[generated_by_id], back_populates="generated_pvs") # Added generator relationship
    validator = relationship("User", foreign_keys=[validated_by_id], back_populates="pvs")

    @property
    def is_validated(self) -> bool:
        return self.status == PVStatus.VALIDATED
