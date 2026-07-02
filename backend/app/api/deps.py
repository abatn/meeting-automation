import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError
import redis.asyncio as redis

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis_client
from app.models.user import User, UserRole, UserStatus
from app.services.meeting_service import MeetingService
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.client_service import ClientService
from sqlalchemy import select

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.PROJECT_NAME}/api/v1/auth/login",
    auto_error=False,  # Don't auto-error; we'll handle cookie extraction manually
)

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


async def get_token_from_request(
    request: Request,
    token_from_header: Optional[str] = Depends(reusable_oauth2),
) -> str:
    """
    Extract JWT token from either:
    1. Authorization header (Bearer token)
    2. httpOnly cookie (accessToken)
    """
    # Try header first (for API clients, swagger docs, etc.)
    if token_from_header:
        return token_from_header
    
    # Try cookie (for browser-based clients)
    token_from_cookie = request.cookies.get("accessToken")
    if token_from_cookie:
        return token_from_cookie
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_internal_api_key(
    api_key: Optional[str] = Depends(api_key_header),
) -> bool:
    if not api_key or api_key != settings.INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing Internal API Key",
        )
    return True


async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> AuthService:
    return AuthService(db, redis_client)


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


async def get_client_service(db: AsyncSession = Depends(get_db)) -> ClientService:
    return ClientService(db)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_token_from_request),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """
    Enhanced token validation with comprehensive security checks:
    1. Token blacklist check
    2. JWT signature and expiration validation
    3. Cross-tenant validation (client_id match)
    4. User existence and soft-delete check
    5. User status validation
    """
    token_preview = token[:50] + "..." if len(token) > 50 else token
    logger.warning(f"[VERIFY_TOKEN] Starting validation. Token preview: {token_preview}")
    logger.warning(f"[VERIFY_TOKEN] Request path: {request.url.path}, Remote: {request.client}")
    
    if await auth_service.is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been blacklisted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        logger.debug(f"JWT Payload: {payload}")
        logger.debug(f"JWT Decode SECRET_KEY: {settings.SECRET_KEY}")
        logger.debug(f"JWT Decode ALGORITHM: {settings.ALGORITHM}")

        user_id: str = payload.get("sub")
        client_id_from_jwt: str = payload.get("client_id")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (JWTError, ValidationError) as e:
        logger.warning(f"JWT Validation Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    # SECURITY: Validate X-Client-ID header matches JWT client_id (Multi-Tenancy)
    header_client_id = request.headers.get("X-Client-ID")
    if header_client_id and client_id_from_jwt:
        if header_client_id != client_id_from_jwt:
            logger.warning(
                f"Client ID mismatch: Header={header_client_id}, JWT={client_id_from_jwt}, User={user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Client ID in header does not match token",
            )

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(
            User.id == user_id,
            User.client_id == client_id_from_jwt  # SECURITY: Ensure user belongs to this tenant
        )
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found, inactive, or does not belong to this tenant"
        )
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


async def get_meeting_service(db: AsyncSession = Depends(get_db)) -> MeetingService:
    return MeetingService(db)


def check_permissions(allowed_roles: list[UserRole]):
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )
        return current_user

    return permission_checker


async def get_current_system_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency for system_admin and tech_admin endpoints.
    Used for platform-wide operations (CMS, tenant management, monitoring, etc.)
    Multi-Tenant: system_admin and tech_admin are the only roles that can access cross-tenant data.
    """
    if (current_user.role != UserRole.SYSTEM_ADMIN and 
        current_user.role != UserRole.TECH_ADMIN and
        not current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System administrator or tech admin privileges required",
        )
    return current_user
