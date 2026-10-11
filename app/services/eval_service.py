"""Evaluation service for PO-1 to PO-5 evaluation runs.

Endpoints served:
    POST /eval-runs         - Start `make eval` in the background (202)
    GET  /eval-runs/latest  - Latest (frozen) run with PO-1 to PO-5
    GET  /eval-runs/{run_id} - One run with per-item results

Writes (one transaction on finish): eval_runs, eval_results, eval_item_results
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class EvalService:
    """
    Service for evaluation runs.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize EvalService with a DB session."""
        self.db = db

    async def start_run(
        self,
        freeze: bool,
        sets: list[str],
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> JSONResponse:
        """Start an eval run as a background task; 409 if one is already running."""
        return response_error("Not implemented", code=501)

    async def get_latest(self, frozen: bool = True) -> JSONResponse:
        """Return the latest run with gate, objectives, non-functional checks and stretch items."""
        return response_error("Not implemented", code=501)

    async def get_run(self, run_id: str) -> JSONResponse:
        """Return one run with per-item results."""
        return response_error("Not implemented", code=501)
