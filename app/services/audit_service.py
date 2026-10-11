"""Audit service for the append-only audit log.

Endpoints served:
    GET /audit-events         - Append-only log, newest first, filterable
    GET /audit-events/summary - Counts for the header tiles

Reads: audit_log (no PUT, PATCH or DELETE exists)
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import response_error


class AuditService:
    """
    Service for audit events.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AuditService with a DB session."""
        self.db = db

    async def get_events(
        self,
        event_type: Optional[str] = None,
        actor: Optional[str] = None,
        run_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List audit events newest first; audit_id is `AUD-` + zero-padded id."""
        return response_error("Not implemented", code=501)

    async def get_summary(self, run_id: Optional[str] = None) -> JSONResponse:
        """Return {complete_records_pct, events, blocked_by_judge, refused}."""
        return response_error("Not implemented", code=501)
