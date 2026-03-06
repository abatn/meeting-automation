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
    from app.models.role import Role


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    PARTICIPANT = "participant"
    DG = "dg"


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
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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

    # Manager relationship
    manager_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey('users.id'), nullable=True)
    reports: Mapped[List["User"]] = relationship(back_populates="manager")
    manager: Mapped["User"] = relationship(back_populates="reports", remote_side=[id])


    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")
    created_meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting", back_populates="creator"
    )

    @property
    def role(self) -> str:
        """Compatibility property for legacy code expecting a single role string"""
        if self.roles:
            return self.roles[0].name
        return "participant"

    @property
    def department(self) -> Optional[str]:
        """Placeholder for department logic"""
        return None


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    users: Mapped[List["User"]] = relationship(secondary=user_roles, back_populates="roles")
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
