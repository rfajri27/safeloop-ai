"""Route configuration for FastAPI application."""
from pathlib import Path
from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from config.ratelimit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from routes import api
from config.databases.postgresql import get_db
from config.databases.redis import redis_client
from app.utils.response import response_success, response_error


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def setup_routes(app, env):
    """Configure all application routes."""
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def web_ui():
        """Serve the SafeLoop web UI (single page, hash-routed)."""
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/info")
    def read_info():
        """App name and version."""
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
