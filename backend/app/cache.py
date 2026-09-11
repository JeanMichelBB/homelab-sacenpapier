import json
import time
from typing import Any
import redis.asyncio as aioredis
from .config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    val = await r.get(key)
    return json.loads(val) if val else None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    r = get_redis()
    await r.set(key, json.dumps(value), ex=ttl)


async def cache_get_stale(key: str, ttl: int) -> tuple[Any | None, bool]:
    """Returns (value, is_fresh). Value has no Redis TTL; freshness is tracked separately
    so a stale value can still be served instantly while a refresh happens in the background."""
    r = get_redis()
    val, ts = await r.get(key), await r.get(f"{key}:ts")
    if val is None:
        return None, False
    is_fresh = ts is not None and (time.time() - float(ts)) < ttl
    return json.loads(val), is_fresh


async def cache_set_stale(key: str, value: Any) -> None:
    r = get_redis()
    await r.set(key, json.dumps(value))
    await r.set(f"{key}:ts", str(time.time()))
