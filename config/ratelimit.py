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
from app.utils.response import CustomHTTPException

# Alias for backward compatibility
redis_connection = redis_client


async def service_name_identifier(request: Request):
    """Identify client by IP address for rate limiting."""
    return request.client.host


async def custom_callback(request: Request, response: Response, pexpire: int):
    """
    Custom callback when rate limit is exceeded.

    Raises:
        CustomHTTPException: 400 with retry information
    """
    expire = ceil(pexpire / 1000)
    raise CustomHTTPException(
        status_code=400,
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
