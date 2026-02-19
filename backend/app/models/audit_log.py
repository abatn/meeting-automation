from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False)  # CREATE, READ, UPDATE, DELETE, LOGIN, etc.
    method = Column(String, nullable=False)  # GET, POST, PUT, DELETE
    path = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True) # Dauer der Anfrage in Sekunden
    resource_type = Column(String, nullable=False, index=True)  # meeting, user, action, etc.
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Zusätzliche Details als JSON
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Beziehungen
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_audit_logs_user_id_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_logs_resource_type_timestamp', 'resource_type', 'timestamp'),
    )