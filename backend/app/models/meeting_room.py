from typing import Optional
from sqlalchemy import String, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base

class MeetingRoom(Base):
    __tablename__ = "meeting_rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    
    name: Mapped[str] = mapped_column(String, nullable=False)
    location_description: Mapped[Optional[str]] = mapped_column(String, nullable=True) # e.g. "Floor 2, Left wing"
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship to the tenant
    client = relationship("Client", backref="meeting_rooms")

    def __repr__(self):
        return f"<MeetingRoom(name={self.name}, client_id={self.client_id})>"
