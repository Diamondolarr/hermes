import json
from typing import Any

import redis

from app.core.config import settings


def _get_client(url: str | None = None) -> redis.Redis:
    target_url = (url or settings.cache_redis_url).strip()
    if not target_url:
        raise ValueError("CACHE_REDIS_URL is not configured.")
    return redis.Redis.from_url(target_url, decode_responses=True)


def cache_get_json(key: str) -> Any | None:
    try:
        value = _get_client().get(key)
    except Exception:
        return None
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    try:
        payload = json.dumps(value, default=str)
        _get_client().setex(key, max(1, int(ttl_seconds)), payload)
    except Exception:
        return


def cache_delete(key: str) -> None:
    try:
        _get_client().delete(key)
    except Exception:
        return


def ping_redis(url: str | None = None) -> bool:
    try:
        return bool(_get_client(url).ping())
    except Exception:
        return False
