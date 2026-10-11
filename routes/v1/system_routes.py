"""System API routes.

Endpoints:
    GET /health - DB, Redis, Qdrant reachable; LLM gateway flag (public)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.services.system_service import SystemService

router = APIRouter(tags=["System"])


def get_system_service(db: AsyncSession = Depends(get_db)) -> SystemService:
    """Dependency: Create SystemService."""
    return SystemService(db)


@router.get("/health", summary="Dependency health and LLM flag")
async def health_check(service: SystemService = Depends(get_system_service)):
    """Check DB, Redis and Qdrant. Never calls Gemini."""
    return await service.health_check()
