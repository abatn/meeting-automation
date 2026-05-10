from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User as UserModel, Role as RoleModel, UserStatus, ActivationToken
from app.models.client import Client
from app.core import security
from app.schemas.user import UserCreate
import secrets


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[UserModel]:
        """Get user by email address."""
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> Optional[UserModel]:
        """Get user by ID."""
        stmt = select(UserModel).where(UserModel.id == user_id).options(
            selectinload(UserModel.roles)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        client_id: str,
        role_name: str = "participant",
        status: UserStatus = UserStatus.PENDING,
        is_superuser: bool = False,
        is_mfa_enabled: bool = False
    ) -> UserModel:
        """Create a new user with hashed password."""
        # Get role
        role_stmt = select(RoleModel).where(RoleModel.name == role_name)
        role_result = await self.db.execute(role_stmt)
        role = role_result.scalar_one_or_none()
        
        if not role:
            # Default to participant role if specified role not found
            role_stmt = select(RoleModel).where(RoleModel.name == "participant")
            role_result = await self.db.execute(role_stmt)
            role = role_result.scalar_one_or_none()
            
        # Create user instance
        user = UserModel(
            id=str(uuid4()),
            email=email,
            hashed_password=security.get_password_hash(password),
            full_name=full_name,
            client_id=client_id,
            status=status.value,
            is_superuser=is_superuser,
            is_mfa_enabled=is_mfa_enabled
        )
        
        # Add role to user's roles list (many-to-many relationship)
        if role:
            user.roles = [role]
        
        self.db.add(user)
        await self.db.flush()
        
        return user

    async def activate_user(self, user_id: str, new_password: str) -> UserModel:
        """Activate a user by setting password and changing status to ACTIVE."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
            
        user.hashed_password = security.get_password_hash(new_password)
        user.status = UserStatus.ACTIVE.value
        user.is_mfa_enabled = False  # Reset MFA on activation
        
        await self.db.flush()
        return user

    async def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user's password."""
        user = await self.get_by_id(user_id)
        if not user:
            return False
            
        user.hashed_password = security.get_password_hash(new_password)
        await self.db.flush()
        return True

    async def create_activation_token(self, user_id: str) -> ActivationToken:
        """Create an activation token for a user."""
        # Delete any existing activation tokens for this user
        stmt = select(ActivationToken).where(ActivationToken.user_id == user_id)
        result = await self.db.execute(stmt)
        existing_tokens = result.scalars().all()
        
        for token in existing_tokens:
            await self.db.delete(token)
            
        # Create new token
        activation_token = ActivationToken(
            id=str(uuid4()),
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48)
        )
        
        self.db.add(activation_token)
        await self.db.flush()
        return activation_token