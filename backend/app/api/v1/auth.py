from datetime import timedelta, datetime
from typing import Any
import uuid
import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.core import security
from app.core.config import settings
from app.api import deps
from app.models.user import User as UserModel, Role as RoleModel, UserStatus, ActivationToken
from app.models.client import Client, SubscriptionStatus, SubscriptionPlan
from app.models.team import TeamMember
from app.schemas.user import User, UserCreate, Token, ActivationConfirm
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.utils.token_utils import hash_token, verify_token
from app.utils.rate_limit import create_rate_limiter
from app.tasks.email_tasks import send_invitation_email
from datetime import timezone

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiters for auth endpoints
activate_verify_limiter = create_rate_limiter("activate_verify", max_requests=5, time_window_seconds=60)
activate_confirm_limiter = create_rate_limiter("activate_confirm", max_requests=5, time_window_seconds=60)
login_limiter = create_rate_limiter("login", max_requests=10, time_window_seconds=60)

@router.get("/activate/verify")
async def verify_activation_token(
    token: str,
    db: AsyncSession = Depends(deps.get_db),
    _: None = Depends(activate_verify_limiter),
) -> Any:
    """Verifies an activation token."""
    # First try to find by token_hash (new tokens stored as hash)
    token_hash = hash_token(token)
    stmt = select(ActivationToken).where(
        ActivationToken.token_hash == token_hash
    ).options(selectinload(ActivationToken.user))
    res = await db.execute(stmt)
    token_obj = res.scalar_one_or_none()

    # Fallback to plaintext token for backward compatibility with old tokens
    if not token_obj:
        stmt = select(ActivationToken).where(
            ActivationToken.token == token
        ).options(selectinload(ActivationToken.user))
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

@router.post("/activate/confirm", response_model=Token)
async def confirm_activation(
    body: ActivationConfirm,
    db: AsyncSession = Depends(deps.get_db),
    _: None = Depends(activate_confirm_limiter),
) -> Any:
    """Confirms user activation by setting a password and changing status to ACTIVE.
    Returns JWT token for automatic login after activation."""
    # First try to find by token_hash (new tokens stored as hash)
    token_hash = hash_token(body.token)
    stmt = select(ActivationToken).where(
        ActivationToken.token_hash == token_hash
    ).options(selectinload(ActivationToken.user).selectinload(UserModel.roles))
    res = await db.execute(stmt)
    token_obj = res.scalar_one_or_none()

    # Fallback to plaintext token for backward compatibility with old tokens
    if not token_obj:
        stmt = select(ActivationToken).where(
            ActivationToken.token == body.token
        ).options(selectinload(ActivationToken.user).selectinload(UserModel.roles))
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

    # Generate JWT token for automatic login
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            {"sub": str(user.id), "client_id": str(user.client_id), "role": user.role},
            expires_delta=access_token_expires
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


import logging

logger = logging.getLogger(__name__)

@router.post("/login", response_model=Token)
async def login(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    _: None = Depends(login_limiter),
) -> Any:
    # Debug logging without sensitive data
    logger.debug(f"Login attempt for user: {form_data.username}")

    user_result = await db.execute(
        select(UserModel).where(UserModel.email == form_data.username)
    )
    user = user_result.scalar_one_or_none()

    is_valid = security.verify_password(form_data.password, user.hashed_password) if user else False
    logger.debug(f"Password verification result: {is_valid}")

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
    """
    Self-Service Registration.

    Flow:
    1. Check if email already exists in users (ACTIVE or PENDING) → Error
    2. Check if email exists in team_members → delete (upgrade to registered user)
    3. Create Client if not provided
    4. Create User with status=PENDING (not ACTIVE!)
    5. Create ActivationToken (expires in 7 days)
    6. Trigger user-invited webhook (sends email with activation link)
    7. AuditLog for Client creation and User creation
    8. Single transaction (commit at end)
    """
    # 1. Prüfe Duplicate in users (ACTIVE oder PENDING)
    stmt = select(UserModel).where(UserModel.email == user_in.email)
    res = await db.execute(stmt)
    existing_user = res.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )

    # 2. Prüfe team_members und lösche falls vorhanden (upgrade)
    stmt_tm = select(TeamMember).where(TeamMember.email == user_in.email)
    res_tm = await db.execute(stmt_tm)
    existing_tm = res_tm.scalar_one_or_none()
    if existing_tm:
        await db.delete(existing_tm)
        await db.flush()

    # 3. Client Handling
    client_id = user_in.client_id
    if not client_id:
        client_id = str(uuid.uuid4())

        # Determine plan
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
        await db.flush()  # Get client_id for user FK

        # AuditLog für Client-Erstellung
        await AuditService.log_action(
            db,
            client_id=client_id,
            action="CREATE_CLIENT",
            user_id=None,  # Self-Service, kein User-ID verfügbar
            table_name="clients",
            record_id=new_client.id,
            new_values={
                "company_name": new_client.company_name,
                "subscription_plan": new_client.subscription_plan.value,
                "minutes_included": new_client.minutes_included
            }
        )

    # 4. Determine Role
    if not user_in.client_id:
        target_role = "dg"  # First user of tenant becomes 'dg'
    else:
        target_role = user_in.role or "participant"

    role_result = await db.execute(
        select(RoleModel).where(RoleModel.name == target_role)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {target_role}. Please contact administrator."
        )

    # 5. Create User mit status=PENDING (nicht ACTIVE!)
    db_obj = UserModel(
        id=str(uuid.uuid4()),
        client_id=client_id,
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        status=UserStatus.PENDING.value,  # ✅ PENDING för E-Mail-Verifikation
        is_superuser=False,
        is_mfa_enabled=False,
        created_at=datetime.now(timezone.utc) if hasattr(datetime, "UTC") else datetime.utcnow(),
    )

    db_obj.roles = [role]
    db.add(db_obj)
    await db.flush()

    # 6. ActivationToken erstellen
    token = secrets.token_urlsafe(32)
    # Token expires after 48 hours (Best Practice: 24-72 hours maximum for one-time-use tokens)
    expiration = datetime.now(timezone.utc) + timedelta(hours=48)
    # Store token hash instead of plaintext for security
    token_hash = hash_token(token)
    activation_entry = ActivationToken(
        id=str(uuid.uuid4()),
        user_id=db_obj.id,
        token_hash=token_hash,
        expires_at=expiration
    )
    db.add(activation_entry)
    await db.flush()

    # 7. Client laden für Company Name im Webhook
    client_stmt = select(Client).where(Client.id == client_id)
    client_res = await db.execute(client_stmt)
    client_obj = client_res.scalar_one()

    # 8. AuditLog für User-Erstellung
    await AuditService.log_action(
        db,
        client_id=client_id,
        action="CREATE_USER",
        user_id=db_obj.id,  # Self-Service: User erstellt sich selbst
        table_name="users",
        record_id=db_obj.id,
        new_values={
            "email": db_obj.email,
            "status": db_obj.status,
            "role": target_role
        }
    )

    # 9. Commit ALLES atomar (Client + User + Token + AuditLogs)
    await db.commit()
    await db.refresh(db_obj)

    # 10. Enqueue invitation email task with automatic retries
    activation_link = f"{settings.FRONTEND_URL}/activate?token={token}"
    send_invitation_email.delay(
        email=db_obj.email,
        full_name=db_obj.full_name or "Valued Customer",
        company_name=client_obj.company_name,
        activation_link=activation_link
    )
    logger.info(f"Enqueued invitation email task for {db_obj.email}")

    return User(
        id=db_obj.id,
        email=db_obj.email,
        full_name=db_obj.full_name,
        status=db_obj.status,
        is_superuser=db_obj.is_superuser,
        is_mfa_enabled=db_obj.is_mfa_enabled,
        created_at=db_obj.created_at,
        role=target_role,
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
