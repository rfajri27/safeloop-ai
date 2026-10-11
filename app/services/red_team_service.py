"""Red Team service for running the Red Team agent and Judge on a HAZOP row.

Endpoints served:
    POST /hazop-rows/{row_code}/red-team        - Run Red Team + Judge, return the result
    POST /hazop-rows/{row_code}/red-team/stream - Same, streamed (SSE)
    GET  /red-team-runs/{run_id}                - A finished run with proposals and verdicts

Writes (one transaction): agent_runs, hazop_proposals, judge_verdicts, citations,
                          approval_items (pass only), audit_log
"""
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class RedTeamService:
    """
    Service for Red Team runs.

    REQUEST-SCOPED: Created per request with injected session.
    Pre-stream checks: row exists (404), no run in progress on the row (409),
    LLM enabled (503 "AI service disabled").
    """

    def __init__(self, db: AsyncSession):
        """Initialize RedTeamService with a DB session."""
        self.db = db

    async def run(
        self,
        row_code: str,
        max_proposals: int,
        focus: str,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> JSONResponse:
        """Run the Red Team graph to completion and return the RUN_FINISHED result."""
        return response_error("Not implemented", code=501)

    async def run_stream(
        self,
        row_code: str,
        max_proposals: int,
        focus: str,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> StreamingResponse:
        """Stream the Red Team graph as AG-UI events (proposal, judge_verdict, approval_queued)."""
        return response_error("Not implemented", code=501)

    async def get_run(self, run_id: str) -> JSONResponse:
        """Return a finished run in the same shape as RUN_FINISHED.result."""
        return response_error("Not implemented", code=501)
