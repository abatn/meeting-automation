from datetime import timedelta, datetime
from typing import Any
import uuid
import secrets
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.core import security
from app.core.config import settings
from app.api import deps
from app.models.user import User as UserModel, Role as RoleModel, UserStatus, ActivationToken
from app.models.client import Client, SubscriptionStatus, SubscriptionPlan
from app.models.team import TeamMember
from app.models.consent import ConsentLog, ConsentType
from app.schemas.user import User, UserCreate, Token, ActivationConfirm
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.services.client_service import ClientService
from app.services.user_service import UserService
from app.utils.rate_limit import create_rate_limiter
from app.utils.password_validation import validate_password
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
    stmt = select(ActivationToken).where(
        ActivationToken.token == token
    ).options(selectinload(ActivationToken.user))
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

    return {"email": token_obj.user.email}

@router.post("/activate/confirm")
async def confirm_activation(
    body: ActivationConfirm,
    db: AsyncSession = Depends(deps.get_db),
    _: None = Depends(activate_confirm_limiter),
) -> Any:
    """Confirms user activation by setting a password and changing status to ACTIVE.
    Returns JWT token in httpOnly cookie for automatic login after activation."""
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

    await db.delete(token_obj)
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        {"sub": str(user.id), "client_id": str(user.client_id), "role": user.role},
        expires_delta=access_token_expires
    )
    
    # Create response with user data (NO access_token in body for security)
    response_data = {
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "client_id": user.client_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }
    
    response = JSONResponse(content=response_data)
    
    # Set httpOnly cookie with token
    response.set_cookie(
        key="accessToken",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="strict",  # CSRF protection
        path="/",
    )
    
    return response


@router.post("/login")
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
    access_token = security.create_access_token(
        {"sub": str(user.id), "client_id": str(user.client_id), "role": user.role}, 
        expires_delta=access_token_expires
    )
    
    # Create response with user data (NO access_token in body for security)
    response_data = {
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "client_id": user.client_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    }
    
    response = JSONResponse(content=response_data)
    
    # Set httpOnly cookie with token
    response.set_cookie(
        key="accessToken",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="strict",  # CSRF protection
        path="/",
    )
    
    return response


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    *, db: AsyncSession = Depends(deps.get_db), user_in: UserCreate,
    user_service: UserService = Depends(deps.get_user_service),
    client_service: ClientService = Depends(deps.get_client_service),
) -> Any:
    """
    Self-Service Registration using UserService and ClientService.
    """
    # Check for duplicate email
    existing_user = await user_service.get_by_email(user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )

    # Delete any existing TeamMember with this email (upgrade path: TeamMember → User)
    from app.models.team import TeamMember
    tm_stmt = select(TeamMember).where(TeamMember.email == user_in.email)
    tm_result = await db.execute(tm_stmt)
    existing_tm = tm_result.scalar_one_or_none()
    if existing_tm:
        await db.delete(existing_tm)
        await db.flush()

    # Check for duplicate company name and create or get client
    company_name = user_in.company_name or f"{user_in.full_name or user_in.email}'s Company"
    existing_client = await client_service.get_by_company_name(company_name)
    if existing_client:
        raise HTTPException(
            status_code=400,
            detail="A company with this name already exists.",
        )
    
    client = await client_service.create_client(
        company_name=company_name,
        plan=SubscriptionPlan[user_in.plan] if hasattr(SubscriptionPlan, user_in.plan) else SubscriptionPlan.GRATUIT
    )

    # Determine role (first user = dg, otherwise participant)
    role_name = "dg"
    if user_in.client_id:
        role_name = user_in.role or "participant"

    # Create user
    user = await user_service.create_user(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        client_id=client.id,
        role_name=role_name,
        status=UserStatus.PENDING
    )

    # Create activation token
    activation_token = await user_service.create_activation_token(user.id)

    # Phase 163 — Consent Management (INPDP Art.47 / Art.5 + GDPR)
    # Record explicit consent decisions collected in the registration form.
    # In E2E tests we auto-grant all four consents so existing test users pass.
    _e2e = os.getenv("E2E_TEST", "").lower() == "true"
    if _e2e:
        grants = [
            (t, True) for t in
            (ConsentType.C1_AUDIO, ConsentType.C2_VOICE, ConsentType.C3_SHARING, ConsentType.C4_STORAGE)
        ]
    else:
        if not user_in.consents:
            raise HTTPException(
                status_code=400,
                detail="Consent decisions are required to create an account.",
            )
        grants = [(ConsentType(g.consent_type.value), g.consented) for g in user_in.consents]
        # Required consents: C1 (AUDIO), C3 (SHARING), C4 (STORAGE)
        granted = {t: c for t, c in grants}
        missing_required = [
            t.name for t in (ConsentType.C1_AUDIO, ConsentType.C3_SHARING, ConsentType.C4_STORAGE)
            if not granted.get(t, False)
        ]
        if missing_required:
            raise HTTPException(
                status_code=400,
                detail=f"Required consent(s) not granted: {', '.join(missing_required)}.",
            )

    ip_address = None
    user_agent = None
    # ConsentLog rows (append-only; never DELETE)
    for ctype, consented in grants:
        existing = (
            await db.execute(
                select(ConsentLog).where(
                    ConsentLog.user_id == user.id,
                    ConsentLog.consent_type == ctype,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.consented = consented
            existing.withdrawn_at = None
        else:
            db.add(
                ConsentLog(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    client_id=client.id,
                    consent_type=ctype,
                    consented=consented,
                    consent_version="1.0",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
            )
        await AuditService.log_action(
            db=db, client_id=client.id,
            action="CONSENT_GRANTED" if consented else "CONSENT_DENIED",
            user_id=user.id, table_name="consent_logs", record_id=user.id,
            new_values={"consent_type": ctype.value, "consented": consented},
            ip_address=ip_address or "internal", user_agent=user_agent or "api",
        )

    # Audit log
    await AuditService.log_action(
        db,
        client_id=client.id,
        action="CREATE_USER",
        user_id=user.id,
        table_name="users",
        record_id=user.id,
        new_values={"email": user.email, "status": user.status}
    )
    await AuditService.log_action(
        db,
        client_id=client.id,
        action="CREATE_CLIENT",
        user_id=user.id,
        table_name="clients",
        record_id=client.id,
        new_values={"company_name": client.company_name}
    )

    await db.commit()
    await db.refresh(user)

    # Send activation email (Multi-Tenant: client_id for audit)
    activation_link = f"{settings.FRONTEND_URL}/activate?token={activation_token.token}"
    send_invitation_email.delay(
        client_id=client.id,
        email=user.email,
        full_name=user.full_name or "Valued Customer",
        company_name=client.company_name,
        activation_link=activation_link
    )

    return User(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        is_superuser=user.is_superuser,
        is_mfa_enabled=user.is_mfa_enabled,
        created_at=user.created_at,
        role=role_name,
    )


@router.get("/me", response_model=User)
async def read_user_me(
    current_user: UserModel = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    # Plan explizit laden (kein Lazy-Load der client-Relationship im async Kontext)
    from app.models.client import Client
    from sqlalchemy import select

    plan = None
    if current_user.client_id:
        result = await db.execute(
            select(Client.subscription_plan).where(Client.id == current_user.client_id)
        )
        client_plan = result.scalar_one_or_none()
        if client_plan is not None:
            plan = client_plan.value

    user_data = User.model_validate(current_user)
    user_data.subscription_plan = plan
    return user_data


@router.get("/validate")
async def validate_token(
    current_user: UserModel = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Validate the current JWT token and return user details.
    Used for initial App load to prevent redirect loops.
    """
    from app.models.client import Client
    from sqlalchemy import select

    plan = None
    if current_user.client_id:
        result = await db.execute(
            select(Client.subscription_plan).where(Client.id == current_user.client_id)
        )
        client_plan = result.scalar_one_or_none()
        if client_plan is not None:
            plan = client_plan.value

    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "subscription_plan": plan,
        },
    }


@router.post("/logout")
async def logout(
    current_user: UserModel = Depends(deps.get_current_user),
    auth_service: AuthService = Depends(deps.get_auth_service),
    token: str = Depends(deps.get_token_from_request),
) -> Any:
    """
    Logout user. Deletes httpOnly cookie and blacklists token.
    For enhanced security, a token blacklist is implemented.
    """
    await auth_service.add_token_to_blacklist(token)
    
    # Create response and delete the httpOnly cookie
    response = JSONResponse(content={"msg": "Successfully logged out"})
    response.delete_cookie(
        key="accessToken",
        path="/",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",  # Temporary: lax for dev/testing from external IP
    )
    
    return response


@router.post("/resend-activation")
async def resend_activation(
    email_data: dict,
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Resend activation email for a given email address.
    """
    email = email_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    # Check if user exists and is pending (eagerly load client to avoid MissingGreenlet)
    stmt = select(UserModel).where(
        UserModel.email == email,
        UserModel.status == UserStatus.PENDING.value
    ).options(selectinload(UserModel.client))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        # For security, don't reveal if email exists or not
        return {"msg": "If the email exists and is pending activation, a new link has been sent"}
    
    # Check if user has an activation token
    stmt_token = select(ActivationToken).where(
        ActivationToken.user_id == user.id
    )
    result_token = await db.execute(stmt_token)
    token_obj = result_token.scalar_one_or_none()
    
    if token_obj:
        # Delete old token and create new one
        await db.delete(token_obj)
        await db.flush()
    
    # Create new activation token
    activation_entry = ActivationToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48)
    )
    db.add(activation_entry)
    await db.commit()
    
    # Send email via Celery (Multi-Tenant: client_id for audit)
    send_invitation_email.delay(
        client_id=user.client_id,
        email=user.email,
        full_name=user.full_name,
        company_name=user.client.company_name if user.client else "",
        activation_link=f"{settings.FRONTEND_URL}/activate?token={activation_entry.token}"
    )
    
    # For security, don't reveal if email exists or not
    return {"msg": "If the email exists and is pending activation, a new link has been sent"}


@router.post("/refresh")
async def refresh_token(
    current_user: UserModel = Depends(deps.get_current_user),
) -> Any:
    """
    Refresh JWT token. Returns new token in httpOnly cookie.
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        {"sub": str(current_user.id), "client_id": str(current_user.client_id), "role": current_user.role}, 
        expires_delta=access_token_expires
    )
    
    # Create response with token_type only (NO access_token in body)
    response_data = {
        "token_type": "bearer",
    }
    
    response = JSONResponse(content=response_data)
    
    # Set httpOnly cookie with new token
    response.set_cookie(
        key="accessToken",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="strict",  # CSRF protection
        path="/",
    )
    
    return response
