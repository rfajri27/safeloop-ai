"""HAZOP API routes.

Endpoints:
    GET /hazop-rows                - Register grouped by node, live risk
    GET /hazop-rows/matrix         - Design-basis and live cells for every row
    GET /hazop-rows/{row_code}     - One row, versions, safeguards, proposals
    GET /hazop-rows/{row_code}/why - Trigger, rules, safeguards and citations for the last re-score

Route order matters: /matrix is declared before /{row_code}.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.hazop_service import HazopService
from app.schemas.common_schema import RiskBand

router = APIRouter(
    prefix="/hazop-rows",
    tags=["HAZOP"],
    dependencies=[Depends(get_current_user)],
)


def get_hazop_service(db: AsyncSession = Depends(get_db)) -> HazopService:
    """Dependency: Create HazopService."""
    return HazopService(db)


@router.get("", summary="List the HAZOP register")
async def get_rows(
    node: Optional[str] = Query(None, description="Process node code, e.g. N1"),
    band: Optional[RiskBand] = Query(None, description="Live risk band filter"),
    rescored: Optional[bool] = Query(None, description="Only rows re-scored in this run"),
    service: HazopService = Depends(get_hazop_service)
):
    """Register grouped by node with live risk, sorted by row code."""
    return await service.get_rows(node, band, rescored)


@router.get("/matrix", summary="Get the live risk matrix")
async def get_matrix(service: HazopService = Depends(get_hazop_service)):
    """All 25 cells with design-basis and live rows."""
    return await service.get_matrix()


@router.get("/{row_code}", summary="Get a HAZOP row")
async def get_row(
    row_code: str,
    service: HazopService = Depends(get_hazop_service)
):
    """One row with versions, safeguards and proposals."""
    return await service.get_row(row_code)


@router.get("/{row_code}/why", summary="Explain why a row moved")
async def get_why(
    row_code: str,
    service: HazopService = Depends(get_hazop_service)
):
    """Trigger, rules, safeguards and citations for the last re-score."""
    return await service.get_why(row_code)
