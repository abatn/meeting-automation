from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Enum, DateTime, Integer, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.meeting import Meeting
    from app.models.audit_log import AuditLog
    from app.models.setting import BrandingSettings
    from app.models.facture import Facture
    from app.models.usage_minute import UsageMinute

class SubscriptionPlan(str, enum.Enum):
    GRATUIT = "GRATUIT"
    PRO = "PRO"
    ENTREPRISE = "ENTREPRISE"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    PENDING = "PENDING"

class BackupFrequency(str, enum.Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class BackupStorageClass(str, enum.Enum):
    STANDARD = "standard"
    COLD = "cold"
    ARCHIVE = "archive"

class BackupStorageClass(str, enum.Enum):
    STANDARD = "standard"
    COLD = "cold"
    ARCHIVE = "archive"

class BillingCycle(str, enum.Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class PaymentMethod(str, enum.Enum):
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    CASH = "CASH"

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    subscription_plan: Mapped[Optional[SubscriptionPlan]] = mapped_column(
        Enum(SubscriptionPlan), nullable=True
    )
    subscription_status: Mapped[Optional[SubscriptionStatus]] = mapped_column(
        Enum(SubscriptionStatus), nullable=True
    )
    subscription_start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    subscription_end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    billing_cycle: Mapped[Optional[BillingCycle]] = mapped_column(
        Enum(BillingCycle), nullable=True
    )
    minutes_included: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minutes_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_method: Mapped[Optional[PaymentMethod]] = mapped_column(
        Enum(PaymentMethod), nullable=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="client", cascade="all, delete-orphan")
    meetings: Mapped[List["Meeting"]] = relationship("Meeting", back_populates="client", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="client", cascade="all, delete-orphan")
    branding_settings: Mapped[Optional["BrandingSettings"]] = relationship(
        "BrandingSettings", back_populates="client", uselist=False, cascade="all, delete-orphan"
    )
    factures: Mapped[List["Facture"]] = relationship("Facture", back_populates="client", cascade="all, delete-orphan")
    usage_history: Mapped[List["UsageMinute"]] = relationship("UsageMinute", back_populates="client", cascade="all, delete-orphan")
    backup_settings: Mapped[Optional["ClientBackupSettings"]] = relationship(
        "ClientBackupSettings", back_populates="client", uselist=False, cascade="all, delete-orphan"
    )


class ClientBackupSettings(Base):
    __tablename__ = "client_backup_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id"), nullable=False)
    backup_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    backup_frequency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    backup_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    backup_storage_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    include_recordings: Mapped[bool] = mapped_column(default=True, nullable=False)
    include_pv: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=5120)
    last_backup_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    client: Mapped["Client"] = relationship("Client", back_populates="backup_settings")
