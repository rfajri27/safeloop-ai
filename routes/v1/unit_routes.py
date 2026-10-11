"""Unit API routes.

Endpoints:
    GET /units/{unit_code}/overview      - Overview screen in one call
    GET /units/{unit_code}/events/stream - Live unit events (SSE, resumable with Last-Event-ID)
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.unit_service import UnitService

router = APIRouter(
    prefix="/units",
    tags=["Unit"],
    dependencies=[Depends(get_current_user)],
)


def get_unit_service(db: AsyncSession = Depends(get_db)) -> UnitService:
    """Dependency: Create UnitService."""
    return UnitService(db)


@router.get("/{unit_code}/overview", summary="Get the unit overview")
async def get_overview(
    unit_code: str,
    service: UnitService = Depends(get_unit_service)
):
    """Headline, health tiles, matrix summary, loop stages and recent activity."""
    return await service.get_overview(unit_code)


@router.get("/{unit_code}/events/stream", summary="Stream live unit events (SSE)")
async def stream_events(
    unit_code: str,
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    service: UnitService = Depends(get_unit_service)
):
    """Replay ticks, health band changes, re-scores, approval changes and replay state."""
    return await service.stream_events(unit_code, last_event_id)
