"""Rate limiting configuration using Redis and FastAPI-Limiter.

Use `RateLimiter` from this module, not `fastapi_limiter.depends.RateLimiter`:

    from config.ratelimit import RateLimiter
    @router.post("/x", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
"""
from math import ceil
import redis as pyredis
from fastapi import Request, Response
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter as _FastAPILimiterRateLimiter
from config.databases.redis import redis_client
from app.utils.jwt_utils import JwtUtils
from app.utils.response import CustomHTTPException

# Alias for backward compatibility
redis_connection = redis_client


async def service_name_identifier(request: Request):
    """Identify the caller for rate limiting: the JWT user (spec: limits are per user), else the IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        payload = JwtUtils.decode_access_token(auth[7:].strip())
        if payload and payload.get("sub"):
            return f"user:{payload['sub']}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


async def custom_callback(request: Request, response: Response, pexpire: int):
    """
    Custom callback when rate limit is exceeded.

    Raises:
        CustomHTTPException: 429 with retry information
    """
    expire = ceil(pexpire / 1000)
    raise CustomHTTPException(
        status_code=429,
        message=f"Too many requests. Retry after {expire} seconds.",
        data={"retry_after": expire}
    )


class RateLimiter(_FastAPILimiterRateLimiter):
    """fastapi-limiter RateLimiter that works with FastAPI >= 0.141.

    The upstream __call__ scans `request.app.routes` and reads `route.path`,
    but FastAPI now keeps included routers as `_IncludedRouter` objects
    (no `.path`), so every request raised AttributeError. This version keys
    the counter on the route FastAPI matched for this request instead.

    Key: <prefix>:<client>:<METHOD>:<route path template>:<times>/<ms>
    The limit is part of the key, so the global limit and a stricter
    per-route limit on the same endpoint keep separate counters.
    """

    async def __call__(self, request: Request, response: Response):
        if not FastAPILimiter.redis:
            raise Exception("You must call FastAPILimiter.init in startup event of fastapi!")

        route = request.scope.get("route")
        route_path = getattr(route, "path_format", None) or request.scope["path"]

        identifier = self.identifier or FastAPILimiter.identifier
        callback = self.callback or FastAPILimiter.http_callback
        rate_key = await identifier(request)
        key = (
            f"{FastAPILimiter.prefix}:{rate_key}:{request.method}:{route_path}"
            f":{self.times}/{self.milliseconds}"
        )
        try:
            pexpire = await self._check(key)
        except pyredis.exceptions.NoScriptError:
            FastAPILimiter.lua_sha = await FastAPILimiter.redis.script_load(
                FastAPILimiter.lua_script
            )
            pexpire = await self._check(key)
        if pexpire != 0:
            return await callback(request, response, pexpire)
