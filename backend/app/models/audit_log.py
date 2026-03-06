from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    # ISO 27001 requirements
    action = Column(String, nullable=False)  # e.g., "CREATE", "UPDATE", "DELETE"
    table_name = Column(String)
    record_id = Column(String)

    old_values = Column(JSON)
    new_values = Column(JSON)

    ip_address = Column(String)
    user_agent = Column(String)

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="audit_logs")
