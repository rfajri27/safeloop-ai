"""Rate limiting configuration using Redis and FastAPI-Limiter."""
from math import ceil
from fastapi import Request, Response
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
