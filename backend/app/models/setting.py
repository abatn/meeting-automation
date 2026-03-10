from datetime import datetime
from sqlalchemy import Boolean, Column, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class BrandingSettings(Base):
    __tablename__ = "branding_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
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
