from datetime import timedelta, datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.core import security
from app.core.config import settings
from app.api import deps
from app.models.user import User as UserModel, Role as RoleModel, UserStatus, ActivationToken
from app.schemas.user import User, UserCreate, Token, ActivationConfirm
from app.services.auth_service import AuthService
from datetime import timezone

router = APIRouter()

@router.get("/activate/verify")
async def verify_activation_token(
    token: str,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Verifies an activation token."""
    stmt = select(ActivationToken).where(ActivationToken.token == token).options(selectinload(ActivationToken.user))
    res = await db.execute(stmt)
    token_obj = res.scalar_one_or_none()
    
    if not token_obj:
        raise HTTPException(status_code=400, detail="Invalid activation token")
    
    # Python 3.11 datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    # Ensure timezone awareness comparison
    expires_at = token_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < now:
        raise HTTPException(status_code=400, detail="Activation token expired")
        
    return {"email": token_obj.user.email}

@router.post("/activate/confirm")
async def confirm_activation(
    body: ActivationConfirm,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Confirms user activation by setting a password and changing status to ACTIVE."""
    stmt = select(ActivationToken).where(ActivationToken.token == body.token).options(selectinload(ActivationToken.user))
    res = await db.execute(stmt)
    token_obj = res.scalar_one_or_none()
    
    if not token_obj:
        raise HTTPException(status_code=400, detail="Invalid activation token")
        
    now = datetime.now(timezone.utc)
    expires_at = token_obj.expires_at
    if expires_at.tzinfo is None:
         expires_at = expires_at.replace(tzinfo=timezone.utc)
         
    if expires_at < now:
        raise HTTPException(status_code=400, detail="Activation token expired")

    user = token_obj.user
    user.hashed_password = security.get_password_hash(body.new_password)
    user.status = UserStatus.ACTIVE.value
    
    # Delete token
    await db.delete(token_obj)
    await db.commit()
    
    return {"message": "User activated successfully"}


import logging

logger = logging.getLogger(__name__)

@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    logger.error(f"DIAGNOSE LOGIN: Received Username='{form_data.username}' | Password Length={len(form_data.password)} | Password='{form_data.password}'")
    
    user_result = await db.execute(
        select(UserModel).where(UserModel.email == form_data.username)
    )
    user = user_result.scalar_one_or_none()

    is_valid = security.verify_password(form_data.password, user.hashed_password) if user else False
    logger.error(f"DIAGNOSE LOGIN: verify_password result: {is_valid}")

    if not user or not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Generate token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            {"sub": str(user.id), "client_id": str(user.client_id), "role": user.role}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "client_id": user.client_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at,
        },
    }


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    *, db: AsyncSession = Depends(deps.get_db), user_in: UserCreate
) -> Any:
    user_result = await db.execute(
        select(UserModel).where(UserModel.email == user_in.email)
    )
    user = user_result.scalar_one_or_none()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    from app.models.client import Client, SubscriptionStatus, SubscriptionPlan
    
    client_id = user_in.client_id
    if not client_id:
        client_id = str(uuid.uuid4())
        # Determine plan from schema
        plan_enum = SubscriptionPlan.GRATUIT
        minutes = 600
        
        if user_in.plan == "PRO":
            plan_enum = SubscriptionPlan.PRO
            minutes = 3000
        elif user_in.plan == "ENTREPRISE":
            plan_enum = SubscriptionPlan.ENTREPRISE
            minutes = 12000
            
        new_client = Client(
            id=client_id,
            company_name=user_in.company_name or f"{user_in.full_name or user_in.email}'s Company",
            subscription_plan=plan_enum,
            subscription_status=SubscriptionStatus.ACTIVE,
            minutes_included=minutes
        )
        db.add(new_client)
        await db.flush()

    # Create user with string ID (UUID)
    db_obj = UserModel(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        status=UserStatus.ACTIVE.value,
        is_superuser=False,
        is_mfa_enabled=False,
        created_at=datetime.now(datetime.timezone.utc) if hasattr(datetime, "UTC") else datetime.utcnow(),
    )
    db.add(db_obj)
    await db.flush()

    # Assign role
    role_result = await db.execute(
        select(RoleModel).where(RoleModel.name == user_in.role)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        role = RoleModel(id=str(uuid.uuid4()), name=user_in.role)
        db.add(role)
        await db.flush()

    await db.commit()
    await db.refresh(db_obj)

    return User(
        id=db_obj.id,
        email=db_obj.email,
        full_name=db_obj.full_name,
        status=db_obj.status,
        is_superuser=db_obj.is_superuser,
        is_mfa_enabled=db_obj.is_mfa_enabled,
        created_at=db_obj.created_at,
        role=user_in.role,
    )


@router.get("/me", response_model=User)
async def read_user_me(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    return current_user


@router.get("/validate")
async def validate_token(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Validate the current JWT token and return user details.
    Used for initial App load to prevent redirect loops.
    """
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
        },
    }


@router.post("/logout")
async def logout(
    current_user: UserModel = Depends(deps.get_current_user),
    auth_service: AuthService = Depends(deps.get_auth_service),
    token: str = Depends(deps.reusable_oauth2),
) -> Any:
    """
    Logout user. In a stateless JWT setup, the client discards the token.
    For enhanced security, a token blacklist could be implemented here.
    """
    await auth_service.add_token_to_blacklist(token)
    return {"msg": "Successfully logged out"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Refresh JWT token.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            {"sub": str(current_user.id), "client_id": str(current_user.client_id), "role": current_user.role}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
