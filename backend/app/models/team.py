from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base

class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (
        Index('ix_team_members_client_email', 'client_id', 'email', unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Useful for WhatsApp
    
    position: Mapped[Optional[str]] = mapped_column(String, nullable=True) 
    department: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationship to the tenant
    client = relationship("Client", backref="team_members")

    def __repr__(self):
        return f"<TeamMember(full_name={self.full_name}, email={self.email})>"
