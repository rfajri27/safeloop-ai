"""System service for health checks.

Endpoints served:
    GET /health - DB, Redis, Qdrant reachable; LLM gateway flag (never calls Gemini)
"""
import httpx
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.redis import redis_client
from config.settings import env
from app.utils.response import response_error, response_success

QDRANT_TIMEOUT_SECONDS = 3.0


class SystemService:
    """
    Service for system health.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize SystemService with a DB session."""
        self.db = db

    async def health_check(self) -> JSONResponse:
        """Return {db, redis, qdrant, llm_enabled}.

        Each store is "ok" or "unavailable"; Qdrant is "not_configured" until
        QDRANT_URL is set. 500 when the DB or Redis is down. `llm_enabled`
        reflects LLM_ENABLED and drives the "LLM gateway online" pill.
        """
        checks = {
            "db": await self._check_db(),
            "redis": await self._check_redis(),
            "qdrant": await self._check_qdrant(),
            "llm_enabled": env.llm_enabled,
        }

        if checks["db"] == "ok" and checks["redis"] == "ok" and checks["qdrant"] != "unavailable":
            return response_success(checks, msg="All systems operational")
        return response_error("Some systems unavailable", code=500, data=checks)

    async def _check_db(self) -> str:
        try:
            await self.db.execute(text("SELECT 1"))
            return "ok"
        except Exception:
            return "unavailable"

    async def _check_redis(self) -> str:
        try:
            await redis_client.ping()
            return "ok"
        except Exception:
            return "unavailable"

    async def _check_qdrant(self) -> str:
        if not env.qdrant_url:
            return "not_configured"
        try:
            async with httpx.AsyncClient(timeout=QDRANT_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{env.qdrant_url.rstrip('/')}/readyz")
            return "ok" if response.status_code == 200 else "unavailable"
        except httpx.HTTPError:
            return "unavailable"
