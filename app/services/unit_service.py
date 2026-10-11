"""Unit service for the Unit 100 overview screen and live events.

Endpoints served:
    GET /units/{unit_code}/overview      - Headline, health tiles, matrix summary, loop stages, activity
    GET /units/{unit_code}/events/stream - Live replay, health, risk and approval events (SSE)

Reads: units, assets, health_assessments, hazop_rows, risk_rescores, approval_items, audit_log
"""
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import response_error


class UnitService:
    """
    Service for unit-level views.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize UnitService with a DB session."""
        self.db = db

    async def get_overview(self, unit_code: str) -> JSONResponse:
        """Build the one-call Overview payload. Headline text comes from code templates, never the LLM."""
        return response_error("Not implemented", code=501)

    async def stream_events(
        self,
        unit_code: str,
        last_event_id: Optional[str] = None
    ) -> StreamingResponse:
        """Stream the Redis stream `unit:{code}:events`, replaying entries after Last-Event-ID."""
        return response_error("Not implemented", code=501)
