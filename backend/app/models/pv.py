from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class PV(Base):
    __tablename__ = "pvs"

    id = Column(String, primary_key=True, index=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    title = Column(String, nullable=False)
    content_html = Column(Text)
    status = Column(String, default="draft") # draft, pending_review, validated, published
    
    is_validated = Column(Boolean, default=False)
    validated_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    meeting = relationship("Meeting", back_populates="pv")
    sections = relationship("Section", back_populates="pv", cascade="all, delete-orphan")
    validated_by = relationship("User")

class Section(Base):
    __tablename__ = "pv_sections"

    id = Column(String, primary_key=True, index=True)
    pv_id = Column(String, ForeignKey("pvs.id", ondelete="CASCADE"), nullable=False)
    
    title = Column(String, nullable=False)
    content = Column(Text)
    order = Column(Integer, default=0)
    
    # Metadata
    type = Column(String) # e.g., "intro", "discussion", "decision", "conclusion"

    pv = relationship("PV", back_populates="sections")