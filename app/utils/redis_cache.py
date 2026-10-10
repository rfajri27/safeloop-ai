"""Reusable Redis cache helpers."""

import json
from datetime import date
from typing import Any

from config.databases.redis import redis_client

CACHE_TTL_SECONDS = 86400 # 1 day

def _normalize_cache_value(value: Any) -> Any:
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


def build_cache_key(prefix: str, payload: dict[str, Any], namespace: str = "cache") -> str:
    normalized_payload = {
        key: _normalize_cache_value(value) for key, value in payload.items()
    }
    serialized_payload = json.dumps(normalized_payload, sort_keys=True, default=str)
    return f"{namespace}:{prefix}:{serialized_payload}"


async def get_cached_result(cache_key: str):
    try:
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return json.loads(cached_result)
    except Exception:
        return None
    return None


async def set_cached_result(cache_key: str, value: Any, ttl_seconds: int = 300) -> None:
    try:
        await redis_client.setex(cache_key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        pass
