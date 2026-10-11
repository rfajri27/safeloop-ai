"""Approval service for the human-in-the-loop approval queue.

Endpoints served:
    GET  /approval-items                    - Queue, filter by decision and type
    GET  /approval-items/{item_id}          - Item with draft, Judge checks and audit record
    POST /approval-items/{item_id}/decision - Approve, or reject with a reason

Writes (one transaction): approval_items, hazop_rows, hazop_recommendations, audit_log
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class ApprovalService:
    """
    Service for approval items.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ApprovalService with a DB session."""
        self.db = db

    async def get_items(
        self,
        decision: Optional[str] = None,
        artifact_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List approval items newest first."""
        return response_error("Not implemented", code=501)

    async def get_item(self, item_id: str) -> JSONResponse:
        """Return the item with full draft, Judge checks, citations and audit block."""
        return response_error("Not implemented", code=501)

    async def decide(
        self,
        item_id: str,
        decision: str,
        reason: Optional[str],
        edited_body: Optional[dict[str, Any]],
        user: CurrentUser
    ) -> JSONResponse:
        """Decide once (409 if not pending); approving a proposal creates a new hazop_rows version."""
        return response_error("Not implemented", code=501)
