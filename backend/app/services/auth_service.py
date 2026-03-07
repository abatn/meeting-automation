import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from jose import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client

    async def add_token_to_blacklist(self, token: str):
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            jti = payload.get("jti", token)
            expires_at_timestamp = payload.get("exp")

            logger.debug(f"AuthService JWT Payload: {payload}")
            logger.debug(f"AuthService JWT SECRET_KEY: {settings.SECRET_KEY}")
            logger.debug(f"AuthService JWT ALGORITHM: {settings.ALGORITHM}")

            if not expires_at_timestamp:
                logger.warning(
                    "Token has no expiration claim. Blacklisting with default TTL."
                )
                # Standard-TTL, z.B. 24 Stunden
                expires_in_seconds = 24 * 60 * 60
            else:
                expires_at = datetime.fromtimestamp(
                    expires_at_timestamp, tz=timezone.utc
                )
                expires_in_seconds = int(
                    (expires_at - datetime.now(timezone.utc)).total_seconds()
                )

            if expires_in_seconds > 0:
                await self.redis.setex(
                    f"blacklist:{jti}", expires_in_seconds, "blacklisted"
                )
                logger.info(
                    f"Token JTI {jti} blacklisted for {expires_in_seconds} seconds."
                )
            else:
                logger.warning(f"Token JTI {jti} already expired. Not blacklisting.")

        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")

    async def is_token_blacklisted(self, token: str) -> bool:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            jti = payload.get("jti", token)
            is_blacklisted = await self.redis.exists(f"blacklist:{jti}")
            return bool(is_blacklisted)
        except Exception as e:
            logger.warning(f"Error checking token blacklist (likely expired): {e}")
            return False
