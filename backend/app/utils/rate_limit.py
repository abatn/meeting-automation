"""Rate limiting utilities for FastAPI."""

import logging
from typing import Optional
import redis.asyncio as redis
from fastapi import HTTPException, Request, Depends, status

from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


async def check_rate_limit(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis_client),
    endpoint_name: str = "endpoint",
    max_requests: int = 10,
    time_window_seconds: int = 60,
) -> None:
    """
    Rate limiting dependency for FastAPI endpoints.

    Args:
        request: FastAPI request object
        redis_client: Redis client (injected via Depends)
        endpoint_name: Name of the endpoint (for logging and redis key)
        max_requests: Maximum number of requests allowed
        time_window_seconds: Time window in seconds

    Raises:
        HTTPException: 429 Too Many Requests if limit exceeded

    Example usage in endpoint:
        @router.post("/login")
        async def login(
            _: None = Depends(
                lambda r, rc: check_rate_limit(
                    r, rc, "login", max_requests=10, time_window_seconds=60
                )
            ),
            ...
        ):
            ...
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Create rate limit key
    rate_limit_key = f"rate_limit:{endpoint_name}:{client_ip}"

    try:
        # Increment counter and set expiry
        current_count = await redis_client.incr(rate_limit_key)

        # Set TTL on first request
        if current_count == 1:
            await redis_client.expire(rate_limit_key, time_window_seconds)

        # Check if limit exceeded
        if current_count > max_requests:
            logger.warning(
                f"Rate limit exceeded for {endpoint_name} from IP {client_ip}. "
                f"Limit: {max_requests}/{time_window_seconds}s, Current: {current_count}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Maximum {max_requests} requests per {time_window_seconds} seconds.",
            )

        logger.debug(f"Rate limit: {endpoint_name} from {client_ip}: {current_count}/{max_requests}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate limit check error for {endpoint_name}: {e}")
        # On error, allow request (fail-open for availability)
        pass


def create_rate_limiter(
    endpoint_name: str, max_requests: int = 10, time_window_seconds: int = 60
):
    """
    Factory function to create a rate limiter dependency.

    Args:
        endpoint_name: Name of the endpoint (for logging and redis key)
        max_requests: Maximum number of requests allowed
        time_window_seconds: Time window in seconds

    Returns:
        A dependency function for use with Depends()

    Example:
        login_limiter = create_rate_limiter("login", max_requests=10, time_window_seconds=60)

        @router.post("/login")
        async def login(
            _: None = Depends(login_limiter),
            ...
        ):
            ...
    """
    async def rate_limit_dependency(
        request: Request,
        redis_client: redis.Redis = Depends(get_redis_client),
    ) -> None:
        await check_rate_limit(request, redis_client, endpoint_name, max_requests, time_window_seconds)

    return rate_limit_dependency
