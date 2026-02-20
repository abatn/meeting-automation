from sqlalchemy import Column, String, Boolean, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    PARTICIPANT = "participant"
    DG = "dg"

# Association table for User-Role (Many-to-Many)
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Role-Permission (Many-to-Many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # MFA
    totp_secret = Column(String, nullable=True)
    is_mfa_enabled = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
    created_meetings = relationship("Meeting", back_populates="creator")

class Role(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")