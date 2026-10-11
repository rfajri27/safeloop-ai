"""Admin API routes.

Endpoints:
    POST /admin/ingest              - Re-ingest the synthetic corpus into Qdrant
    POST /admin/seed                - Load asset model, HAZOP and users from data/
    GET  /agents/{agent_name}/graph - Mermaid view of a LangGraph graph (development only)
"""
from typing import Literal
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import ADMIN_ROLES, require_role
from app.services.admin_service import AdminService
from app.schemas.auth_schema import CurrentUser

router = APIRouter(tags=["Admin"])
admin_user = require_role(*ADMIN_ROLES, action="run admin operations")


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    """Dependency: Create AdminService."""
    return AdminService(db)


@router.post("/admin/ingest", summary="Re-ingest the corpus into Qdrant")
async def ingest(
    user: CurrentUser = Depends(admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Re-chunk, embed and upsert the synthetic corpus."""
    return await service.ingest(user)


@router.post("/admin/seed", summary="Seed the demo data")
async def seed(
    user: CurrentUser = Depends(admin_user),
    service: AdminService = Depends(get_admin_service)
):
    """Load asset model, HAZOP, rule set and demo users."""
    return await service.seed(user)


@router.get(
    "/agents/{agent_name}/graph",
    summary="View an agent graph",
    dependencies=[Depends(admin_user)],
)
async def get_agent_graph(
    agent_name: Literal["knowledge", "red_team"],
    service: AdminService = Depends(get_admin_service)
):
    """Mermaid view of a LangGraph graph (development only)."""
    return await service.get_agent_graph(agent_name)
