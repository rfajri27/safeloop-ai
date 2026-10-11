"""Replay API routes.

Endpoints:
    POST /replay-runs                  - Start S1 or S2 at 1x, 3x or 8x
    GET  /replay-runs/current          - Current run, state, hour, speed
    POST /replay-runs/{run_id}/actions - Pause, resume, change speed, reset
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import REPLAY_ROLES, get_current_user, require_role
from app.services.replay_service import ReplayService
from app.schemas.auth_schema import CurrentUser
from app.schemas.replay_schema import ReplayRunAction, ReplayRunCreate

router = APIRouter(
    prefix="/replay-runs",
    tags=["Replay"],
    dependencies=[Depends(get_current_user)],
)


def get_replay_service(db: AsyncSession = Depends(get_db)) -> ReplayService:
    """Dependency: Create ReplayService."""
    return ReplayService(db)


@router.post("", summary="Start a replay run")
async def start_run(
    request: ReplayRunCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_role(*REPLAY_ROLES, action="start the replay")),
    service: ReplayService = Depends(get_replay_service)
):
    """Start a scenario replay. 409 if a run is already active."""
    return await service.start_run(
        scenario=request.scenario,
        speed=request.speed,
        from_reset=request.from_reset,
        user=user,
        idempotency_key=idempotency_key
    )


@router.get("/current", summary="Get the current replay run")
async def get_current_run(service: ReplayService = Depends(get_replay_service)):
    """Return the active run, state, replay hour and speed."""
    return await service.get_current_run()


@router.post("/{run_id}/actions", summary="Control a replay run")
async def apply_action(
    run_id: str,
    request: ReplayRunAction,
    user: CurrentUser = Depends(require_role(*REPLAY_ROLES, action="control the replay")),
    service: ReplayService = Depends(get_replay_service)
):
    """Pause, resume, set_speed or reset."""
    return await service.apply_action(
        run_id=run_id,
        action=request.action,
        speed=request.speed,
        user=user
    )
