"""Replay service for starting and controlling scenario replays.

Endpoints served:
    POST /replay-runs                  - Start S1 or S2 at 1x, 3x or 8x (202)
    GET  /replay-runs/current          - Current run, state, hour, speed
    POST /replay-runs/{run_id}/actions - Pause, resume, change speed, reset

Writes: replay_runs, sensor_readings, health_assessments, risk_rescores, approval_items, audit_log
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class ReplayService:
    """
    Service for replay runs.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ReplayService with a DB session."""
        self.db = db

    async def start_run(
        self,
        scenario: str,
        speed: int,
        from_reset: bool,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> JSONResponse:
        """Start a replay run; 409 if one is already active for the unit."""
        return response_error("Not implemented", code=501)

    async def get_current_run(self) -> JSONResponse:
        """Return the active run with state, replay_hour and speed."""
        return response_error("Not implemented", code=501)

    async def apply_action(
        self,
        run_id: str,
        action: str,
        speed: Optional[int],
        user: CurrentUser
    ) -> JSONResponse:
        """Pause, resume, set_speed or reset; writes an audit event and a `replay_state` SSE event."""
        return response_error("Not implemented", code=501)
