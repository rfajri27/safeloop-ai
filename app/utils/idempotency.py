"""Idempotency-Key support for POST endpoints that create work (spec Section 4).

A repeated key from the same user within 10 minutes returns the first response.
Redis stores the status code and body; Redis errors never block the request.
"""
import json
from typing import Optional
from fastapi.responses import JSONResponse
from config.databases.redis import redis_client

IDEMPOTENCY_TTL_SECONDS = 600


def _key(scope: str, user_id: str, key: str) -> str:
    return f"idem:{scope}:{user_id}:{key}"


async def get_replayed(scope: str, user_id: str, key: Optional[str]) -> Optional[JSONResponse]:
    """The stored response for this key, or None."""
    if not key:
        return None
    try:
        stored = await redis_client.get(_key(scope, user_id, key))
    except Exception:
        return None
    if not stored:
        return None
    data = json.loads(stored)
    return JSONResponse(status_code=data["status_code"], content=data["body"], headers={"Idempotent-Replayed": "true"})


async def remember(scope: str, user_id: str, key: Optional[str], response: JSONResponse) -> JSONResponse:
    """Store a successful response under the key and return it unchanged."""
    if key:
        try:
            body = json.loads(response.body)
            await redis_client.setex(
                _key(scope, user_id, key),
                IDEMPOTENCY_TTL_SECONDS,
                json.dumps({"status_code": response.status_code, "body": body}),
            )
        except Exception:
            pass
    return response
