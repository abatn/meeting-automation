from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import timedelta

from backend.app.api import deps
from backend.app.core.database import get_db
from backend.app.core.security import create_access_token, create_refresh_token, verify_token
from backend.app.models.user import User # Import the User model
from backend.app.schemas.user import UserCreate, UserResponse, TokenResponse, MFASetupResponse, MFACode
from backend.app.services.security_service import security_service
from backend.app.services.audit_service import AuditService
from backend.app.schemas.audit import AuditLogCreate

router = APIRouter()
audit_service = AuditService()

@router.post("/register", response_model=UserResponse)
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Registriert einen neuen Benutzer."""
    # Prüfen ob Email bereits existiert
    if await security_service.get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    if await security_service.get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    user = await security_service.create_user(db, user_data)

    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=user.id,
            action="REGISTER",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=user.id,
            details={"email": user.email},
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )

    return user

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Authentifiziert einen Benutzer und gibt Tokens zurück."""
    user = await security_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # Audit-Log für fehlgeschlagenen Login
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=None,
                action="LOGIN_FAILED",
                method=request.method,
                path=request.url.path,
                resource_type="auth",
                details={"username": form_data.username},
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Prüfe MFA wenn aktiviert
    if user.is_mfa_enabled:
        return TokenResponse(
            access_token="",
            refresh_token="",
            token_type="bearer",
            requires_mfa=True,
            user_id=user.id
        )
    
    # Tokens erstellen
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=user.id,
            action="LOGIN",
            method=request.method,
            path=request.url.path,
            resource_type="auth",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_mfa=False,
        user_id=user.id
    )

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    request: Request,
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Richtet MFA für einen Benutzer ein."""
    if current_user.is_mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA already enabled"
        )
    
    # MFA-Secret generieren
    secret = security_service.generate_mfa_secret()
    current_user.mfa_secret = secret
    await db.commit()
    
    # QR-Code generieren
    uri = security_service.get_mfa_provisioning_uri(secret, current_user.email)
    qr_code = security_service.generate_qr_code_base64(uri)
    
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="MFA_SETUP",
            method=request.method,
            path=request.url.path,
            resource_type="user",
            resource_id=current_user.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )
    
    return MFASetupResponse(
        secret=secret,
        qr_code=qr_code,
        uri=uri
    )

@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    request: Request,
    mfa_data: MFACode,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Verifiziert einen MFA-Code und gibt Tokens zurück."""
    user = await security_service.get_user_by_id(db, mfa_data.user_id)
    if not user or not user.is_mfa_enabled or not user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA not enabled for this user"
        )

    if not security_service.verify_mfa_code(user.mfa_secret, mfa_data.code):
        # Audit-Log für fehlgeschlagenen MFA
        await audit_service.log_action(
            db=db,
            log_data=AuditLogCreate(
                user_id=user.id,
                action="MFA_FAILED",
                method=request.method,
                path=request.url.path,
                resource_type="auth",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent")
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code"
        )

    # Tokens erstellen
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=user.id,
            action="MFA_VERIFIED",
            method=request.method,
            path=request.url.path,
            resource_type="auth",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        requires_mfa=False,
        user_id=user.id
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    refresh_token: str,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Erneuert den Access Token mit einem Refresh Token."""
    payload = verify_token(refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = int(payload.get("sub"))
    user = await security_service.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Neue Tokens erstellen
    access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        requires_mfa=False,
        user_id=user.id
    )

@router.post("/logout")
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(deps.get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Meldet den Benutzer ab."""
    # Audit-Log
    await audit_service.log_action(
        db=db,
        log_data=AuditLogCreate(
            user_id=current_user.id,
            action="LOGOUT",
            method=request.method,
            path=request.url.path,
            resource_type="auth",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
    )

    return {"message": "Successfully logged out"}
