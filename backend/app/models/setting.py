from datetime import datetime
from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client

class BrandingSettings(Base):
    __tablename__ = "branding_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False, unique=True)
    organization_name: Mapped[str] = mapped_column(String, nullable=True)
    logo_url: Mapped[str] = mapped_column(String, nullable=True) # S3 Key, URL, or Base64
    header_text: Mapped[str] = mapped_column(String, nullable=True)
    footer_text: Mapped[str] = mapped_column(String, nullable=True)
    default_watermark: Mapped[bool] = mapped_column(Boolean, default=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    client: Mapped["Client"] = relationship("Client", back_populates="branding_settings")
