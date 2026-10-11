"""Audit API routes (read-only).

Endpoints:
    GET /audit-events         - Append-only log, newest first, filterable
    GET /audit-events/summary - Counts for the header tiles
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.audit_service import AuditService
from app.schemas.common_schema import DEFAULT_LIMIT, MAX_LIMIT, AuditActor, AuditEventType

router = APIRouter(
    prefix="/audit-events",
    tags=["Audit"],
    dependencies=[Depends(get_current_user)],
)


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    """Dependency: Create AuditService."""
    return AuditService(db)


@router.get("", summary="List audit events")
async def get_events(
    type: Optional[AuditEventType] = Query(None, description="Event type filter"),
    actor: Optional[AuditActor] = Query(None, description="Actor filter"),
    run_id: Optional[str] = Query(None, description="Replay run id"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum records to return"),
    service: AuditService = Depends(get_audit_service)
):
    """Append-only audit log, newest first."""
    return await service.get_events(type, actor, run_id, skip, limit)


@router.get("/summary", summary="Get audit summary counts")
async def get_summary(
    run_id: Optional[str] = Query(None, description="Replay run id"),
    service: AuditService = Depends(get_audit_service)
):
    """Counts for the Audit header tiles."""
    return await service.get_summary(run_id)
