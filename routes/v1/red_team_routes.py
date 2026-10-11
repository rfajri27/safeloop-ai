"""Red Team API routes.

Endpoints:
    POST /hazop-rows/{row_code}/red-team        - Run Red Team + Judge, return the result
    POST /hazop-rows/{row_code}/red-team/stream - Same, streamed (SSE)
    GET  /red-team-runs/{run_id}                - A finished run with proposals and verdicts
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header
from config.ratelimit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import RED_TEAM_ROLES, get_current_user, require_role
from app.services.red_team_service import RedTeamService
from app.schemas.auth_schema import CurrentUser
from app.schemas.red_team_schema import RedTeamRunRequest

router = APIRouter(tags=["Red Team"], dependencies=[Depends(get_current_user)])

# LLM endpoints: 10 requests per minute
llm_rate_limit = [Depends(RateLimiter(times=10, seconds=60))]


def get_red_team_service(db: AsyncSession = Depends(get_db)) -> RedTeamService:
    """Dependency: Create RedTeamService."""
    return RedTeamService(db)


@router.post(
    "/hazop-rows/{row_code}/red-team",
    summary="Run the Red Team on a HAZOP row",
    dependencies=llm_rate_limit,
)
async def run_red_team(
    row_code: str,
    request: RedTeamRunRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_role(*RED_TEAM_ROLES, action="run the Red Team")),
    service: RedTeamService = Depends(get_red_team_service)
):
    """Run Red Team + Judge and return proposals with verdicts."""
    return await service.run(
        row_code=row_code,
        max_proposals=request.max_proposals,
        focus=request.focus,
        user=user,
        idempotency_key=idempotency_key
    )


@router.post(
    "/hazop-rows/{row_code}/red-team/stream",
    summary="Run the Red Team on a HAZOP row (SSE)",
    dependencies=llm_rate_limit,
)
async def run_red_team_stream(
    row_code: str,
    request: RedTeamRunRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(require_role(*RED_TEAM_ROLES, action="run the Red Team")),
    service: RedTeamService = Depends(get_red_team_service)
):
    """Stream the Red Team run as AG-UI events."""
    return await service.run_stream(
        row_code=row_code,
        max_proposals=request.max_proposals,
        focus=request.focus,
        user=user,
        idempotency_key=idempotency_key
    )


@router.get("/red-team-runs/{run_id}", summary="Get a Red Team run")
async def get_run(
    run_id: str,
    service: RedTeamService = Depends(get_red_team_service)
):
    """A finished run with proposals and verdicts."""
    return await service.get_run(run_id)
