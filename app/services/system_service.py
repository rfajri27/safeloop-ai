"""System service for health checks.

Endpoints served:
    GET /health - DB, Redis, Chroma reachable; LLM gateway flag (never calls Gemini)
"""
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.redis import redis_client
from config.settings import env
from app.services import chroma_store
from app.utils.response import response_error, response_success


class SystemService:
    """
    Service for system health.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize SystemService with a DB session."""
        self.db = db

    async def health_check(self) -> JSONResponse:
        """Return {db, redis, vector_store, llm_enabled}.

        Each store is "ok" or "unavailable". 500 when the DB or Redis is down;
        an unavailable Chroma only degrades retrieval to in-process vectors.
        `llm_enabled` reflects LLM_ENABLED and drives the "LLM gateway online" pill.
        """
        checks = {
            "db": await self._check_db(),
            "redis": await self._check_redis(),
            "vector_store": "ok" if await chroma_store.heartbeat() else "unavailable",
            "llm_enabled": env.llm_enabled,
        }

        if checks["db"] == "ok" and checks["redis"] == "ok":
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
