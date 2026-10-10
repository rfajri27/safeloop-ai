"""Route configuration for FastAPI application."""
from fastapi import Depends
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from routes import api
from config.databases.postgresql import get_db
from config.databases.redis import redis_client
from app.utils.response import response_success, response_error


def setup_routes(app, env):
    """Configure all application routes."""
    @app.get("/")
    def read_root():
        """Root endpoint returning app info."""
        return {"app_name": env.app_name, "app_version": env.app_version}

    @app.get("/health")
    async def health_check(db: AsyncSession = Depends(get_db)):
        """Health check - verifies application and dependencies status."""
        checks = {"database": "unknown", "redis": "unknown"}
        is_healthy = True

        try:
            await db.execute(text("SELECT 1"))
            checks["database"] = "connected"
        except Exception:
            checks["database"] = "disconnected"
            is_healthy = False

        try:
            await redis_client.ping()
            checks["redis"] = "connected"
        except Exception:
            checks["redis"] = "disconnected"
            is_healthy = False

        if is_healthy:
            return response_success(checks, msg="All systems operational")
        return response_error("Some systems unavailable", code=500, data=checks)

    app.include_router(
        api.router,
        prefix="/api",
        dependencies=[Depends(RateLimiter(times=60, seconds=60))],
    )
