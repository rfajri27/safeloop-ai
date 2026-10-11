"""Approval API routes.

Endpoints:
    GET  /approval-items                    - Queue, filter by decision and type
    GET  /approval-items/{item_id}          - Item with draft, Judge checks and audit record
    POST /approval-items/{item_id}/decision - Approve, or reject with a reason
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import APPROVAL_ROLES, get_current_user, require_role
from app.services.approval_service import ApprovalService
from app.schemas.approval_schema import ApprovalDecisionRequest
from app.schemas.auth_schema import CurrentUser
from app.schemas.common_schema import DEFAULT_LIMIT, MAX_LIMIT, ApprovalDecision, ArtifactType

router = APIRouter(
    prefix="/approval-items",
    tags=["Approvals"],
    dependencies=[Depends(get_current_user)],
)


def get_approval_service(db: AsyncSession = Depends(get_db)) -> ApprovalService:
    """Dependency: Create ApprovalService."""
    return ApprovalService(db)


@router.get("", summary="List approval items")
async def get_items(
    decision: Optional[ApprovalDecision] = Query(None, description="Decision filter"),
    type: Optional[ArtifactType] = Query(None, description="Artifact type filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum records to return"),
    service: ApprovalService = Depends(get_approval_service)
):
    """Approval queue, newest first."""
    return await service.get_items(decision, type, skip, limit)


@router.get("/{item_id}", summary="Get an approval item")
async def get_item(
    item_id: str,
    service: ApprovalService = Depends(get_approval_service)
):
    """Item with full draft, Judge checks, citations and audit block."""
    return await service.get_item(item_id)


@router.post("/{item_id}/decision", summary="Approve or reject an item")
async def decide(
    item_id: str,
    request: ApprovalDecisionRequest,
    user: CurrentUser = Depends(require_role(*APPROVAL_ROLES, action="decide approvals")),
    service: ApprovalService = Depends(get_approval_service)
):
    """Approve, or reject with a reason. 409 if already decided."""
    return await service.decide(
        item_id=item_id,
        decision=request.decision,
        reason=request.reason,
        edited_body=request.edited_body,
        user=user
    )
