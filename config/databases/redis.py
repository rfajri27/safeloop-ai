"""Redis client for caching and rate limiting.

This module provides:
- SINGLETON: Redis async client for caching and rate limiting
"""
import redis.asyncio as redis
from config.settings import env


# SINGLETON: Redis connection (created once at module import)
# Used for rate limiting and caching operations
redis_client = redis.Redis(
    host=env.redis_host,
    port=env.redis_port,
    db=env.ratelimit_redis_db,
    password=env.redis_password,
    username=env.redis_username,
    encoding="utf-8",
    decode_responses=True,
    socket_timeout=5,           # Socket timeout in seconds
    socket_connect_timeout=5,   # Connection timeout
    retry_on_timeout=True,      # Retry on timeout
)
