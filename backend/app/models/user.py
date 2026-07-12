from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Column, String, Boolean, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
import enum
from datetime import datetime
from app.core.database import Base
from sqlalchemy_utils import EncryptedType
from app.core.config import settings

# TYPE_CHECKING imports
if TYPE_CHECKING:
    from app.models.meeting import Meeting
    from app.models.audit_log import AuditLog
    from app.models.client import Client


class UserRole(str, enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    PARTICIPANT = "participant"
    DG = "dg"
    TECH_ADMIN = "tech_admin"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    DISABLED = "DISABLED"


# Association table for User-Role (Many-to-Many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id", String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
)

# Association table for Role-Permission (Many-to-Many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permission_id",
        String,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    client_id: Mapped[str] = mapped_column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=UserStatus.ACTIVE.value, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # MFA
    totp_secret: Mapped[Optional[str]] = mapped_column(
        EncryptedType(String, settings.SECRET_KEY), nullable=True
    )
    is_mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Manager relationship
    manager_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    reports: Mapped[List["User"]] = relationship(back_populates="manager")
    manager: Mapped["User"] = relationship(back_populates="reports", remote_side=[id])
    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="users")
    roles: Mapped[List["Role"]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )
    activation_token: Mapped[Optional["ActivationToken"]] = relationship(
        "ActivationToken", back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    @property
    def role(self) -> str:
        return self.roles[0].name if self.roles else "participant"
    created_meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting", back_populates="creator"
    )
    consents: Mapped[List["ConsentLog"]] = relationship("ConsentLog", back_populates="user")

    @property
    def department(self) -> Optional[str]:
        """Placeholder for department logic"""
        return None


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="activation_token")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    users: Mapped[List["User"]] = relationship(
        secondary=user_roles, back_populates="roles"
    )
    permissions: Mapped[List["Permission"]] = relationship(
        secondary=role_permissions, back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )
