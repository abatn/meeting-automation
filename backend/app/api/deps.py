import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
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
from sqlalchemy import select

logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.PROJECT_NAME}/api/v1/auth/login"
)

api_key_header = APIKeyHeader(name="X-Internal-API-Key", auto_error=False)


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


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
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
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except (JWTError, ValidationError) as e:
        logger.warning(f"JWT Validation Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Inactive user")
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
