"""Risk rule set API routes.

Endpoints:
    GET /risk-rule-sets/active - Active rule set and version
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.hazop_service import HazopService

router = APIRouter(
    prefix="/risk-rule-sets",
    tags=["HAZOP"],
    dependencies=[Depends(get_current_user)],
)


def get_hazop_service(db: AsyncSession = Depends(get_db)) -> HazopService:
    """Dependency: Create HazopService."""
    return HazopService(db)


@router.get("/active", summary="Get the active risk rule set")
async def get_active_rule_set(service: HazopService = Depends(get_hazop_service)):
    """Active rule set, its version and rules."""
    return await service.get_active_rule_set()
