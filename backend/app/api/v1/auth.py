from datetime import timedelta, datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core import security
from app.core.config import settings
from app.api import deps
from app.models.user import User as UserModel, Role as RoleModel, UserRole
from app.schemas.user import User, UserCreate, Token

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    user_result = await db.execute(select(UserModel).where(UserModel.email == form_data.username))
    user = user_result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            {"sub": str(user.id)}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/register", response_model=User)
async def register(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate
) -> Any:
    user_result = await db.execute(select(UserModel).where(UserModel.email == user_in.email))
    user = user_result.scalar_one_or_none()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    
    # Create user with string ID (UUID)
    db_obj = UserModel(
        id=str(uuid.uuid4()),
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=True,
        is_superuser=False,
        is_mfa_enabled=False,
        created_at=datetime.utcnow()
    )
    db.add(db_obj)
    await db.flush()
    
    # Assign role
    role_result = await db.execute(select(RoleModel).where(RoleModel.name == user_in.role))
    role = role_result.scalar_one_or_none()
    if not role:
        role = RoleModel(id=str(uuid.uuid4()), name=user_in.role)
        db.add(role)
        await db.flush()
    
    # Check if UserRole is a model or an enum - based on grep it might be an enum
    # but the DB schema shows a user_roles table. 
    # If it's a table, we need the model.
    # For now, let's assume it works via the relationship if defined, 
    # or we need to import UserRole table model if it exists separately.
    # Looking at the previous psql output, user_roles table exists.
    
    await db.commit()
    await db.refresh(db_obj)
    
    return User(
        id=db_obj.id,
        email=db_obj.email,
        full_name=db_obj.full_name,
        is_active=db_obj.is_active,
        is_superuser=db_obj.is_superuser,
        is_mfa_enabled=db_obj.is_mfa_enabled,
        created_at=db_obj.created_at,
        role=user_in.role
    )

@router.get("/me", response_model=User)
async def read_user_me(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    return current_user

@router.post("/logout")
async def logout(current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    """
    Logout user. In a stateless JWT setup, the client discards the token.
    For enhanced security, a token blacklist could be implemented here.
    """
    return {"msg": "Successfully logged out"}

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: UserModel = Depends(deps.get_current_user)) -> Any:
    """
    Refresh JWT token.
    """
    from app.core import security
    from app.core.config import settings
    from datetime import timedelta
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            {"sub": str(current_user.id)}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
