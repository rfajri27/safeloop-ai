"""Evaluation API routes.

Endpoints:
    POST /eval-runs          - Start an evaluation run in the background
    GET  /eval-runs/latest   - Latest (frozen) run with PO-1 to PO-5
    GET  /eval-runs/{run_id} - One run with per-item results

Route order matters: /latest is declared before /{run_id}.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query
from config.ratelimit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import EVAL_ROLES, get_current_user, require_role
from app.services.eval_service import EvalService
from app.schemas.auth_schema import CurrentUser
from app.schemas.eval_schema import EvalRunCreate

router = APIRouter(
    prefix="/eval-runs",
    tags=["Evaluation"],
    dependencies=[Depends(get_current_user)],
)


def get_eval_service(db: AsyncSession = Depends(get_db)) -> EvalService:
    """Dependency: Create EvalService."""
    return EvalService(db)


@router.post(
    "",
    summary="Start an evaluation run",
    dependencies=[Depends(RateLimiter(times=2, seconds=600))],
)
async def start_run(
    request: EvalRunCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_role(*EVAL_ROLES, action="start an evaluation run")),
    service: EvalService = Depends(get_eval_service)
):
    """Start an evaluation run. 409 if one is already running."""
    return await service.start_run(
        freeze=request.freeze,
        sets=request.sets,
        user=user,
        idempotency_key=idempotency_key
    )


@router.get("/latest", summary="Get the latest evaluation run")
async def get_latest(
    frozen: bool = Query(True, description="Only frozen runs"),
    service: EvalService = Depends(get_eval_service)
):
    """Latest run with PO-1 to PO-5 results."""
    return await service.get_latest(frozen)


@router.get("/{run_id}", summary="Get an evaluation run")
async def get_run(
    run_id: str,
    service: EvalService = Depends(get_eval_service)
):
    """One run with per-item results."""
    return await service.get_run(run_id)
