from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, ForeignKey, DateTime, Float, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.client import Client

class FactureStatus(str, enum.Enum):
    PAID = "paid"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Facture(Base):
    __tablename__ = "factures"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False)
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    status: Mapped[FactureStatus] = mapped_column(
        SQLEnum(FactureStatus), default=FactureStatus.PENDING
    )
    
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    invoice_pdf_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="factures")
