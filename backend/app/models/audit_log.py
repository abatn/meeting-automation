from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)  # CREATE, READ, UPDATE, DELETE, LOGIN, etc.
    resource_type = Column(String, nullable=False)  # meeting, user, action, etc.
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Zusätzliche Details als JSON
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Beziehungen
    user = relationship("User", back_populates="audit_logs")