import logging
import os
import time
from typing import Optional
from fastapi import Request
import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limits: (calls_per_minute, recordings_per_day, transcriptions_per_month)
RATE_LIMITS = {
    "GRATUIT":     (30,   5,   10),
    "PRO":         (120,  50,  200),
    "ENTREPRISE":  (600, -1,   -1),  # -1 = unbegrenzt
}


class RateLimitExceededError(Exception):
    """Raised when a tenant exceeds their rate limit."""
    pass


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def check_api_rate_limit(client_id: str, plan: str) -> dict:
    """Prüft API-Aufrufe pro Minute (Sliding Window)."""
    r = _get_redis()
    limit, _, _ = RATE_LIMITS.get(plan, RATE_LIMITS["GRATUIT"])
    if limit <= 0:
        return {"allowed": True, "remaining": -1, "limit": limit}

    key = f"rate:api:{client_id}:{int(time.time()) // 60}"
    current = r.incr(key)
    r.expire(key, 120)

    return {
        "allowed": current <= limit,
        "remaining": max(0, limit - current),
        "limit": limit,
        "retry_after": 60 - (int(time.time()) % 60) if current > limit else 0,
    }


def check_recording_rate_limit(client_id: str, plan: str) -> dict:
    """Prüft Recordings pro Tag."""
    # Skip rate limiting in E2E tests or staging (without triggering Celery eager mode)
    if os.getenv("E2E_TEST", "").lower() == "true" or os.getenv("SKIP_RECORDING_RATE_LIMIT", "").lower() == "true":
        return {"allowed": True, "remaining": -1, "limit": -1}

    r = _get_redis()
    _, limit, _ = RATE_LIMITS.get(plan, RATE_LIMITS["GRATUIT"])
    if limit <= 0:
        return {"allowed": True, "remaining": -1, "limit": limit}

    day = time.strftime("%Y-%m-%d")
    key = f"rate:recording:{client_id}:{day}"
    current = r.incr(key)
    r.expire(key, 172800)  # 48h Aufbewahrung

    return {
        "allowed": current <= limit,
        "remaining": max(0, limit - current),
        "limit": limit,
    }


def check_transcription_rate_limit(client_id: str, plan: str) -> dict:
    """Prüft Transkriptionen pro Monat."""
    r = _get_redis()
    _, _, limit = RATE_LIMITS.get(plan, RATE_LIMITS["GRATUIT"])
    if limit <= 0:
        return {"allowed": True, "remaining": -1, "limit": limit}

    month = time.strftime("%Y-%m")
    key = f"rate:transcription:{client_id}:{month}"
    current = r.incr(key)
    r.expire(key, 2678400)  # 31 Tage

    return {
        "allowed": current <= limit,
        "remaining": max(0, limit - current),
        "limit": limit,
    }
