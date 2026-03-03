import redis.asyncio as redis
from app.core.config import settings

_redis_client: redis.Redis = None

async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis_client

async def close_redis_client():
    global _redis_client
    if _redis_client:
        await _redis_client.close()

