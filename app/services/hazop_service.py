"""HAZOP service for the register, live risk matrix and rule sets.

Endpoints served:
    GET /hazop-rows                - Register grouped by node, live risk
    GET /hazop-rows/matrix         - Design-basis and live cells for every row
    GET /hazop-rows/{row_code}     - One row, versions, safeguards, proposals
    GET /hazop-rows/{row_code}/why - Trigger, rules, safeguards and citations for the last re-score
    GET /risk-rule-sets/active     - Active rule set and version

Reads: hazop_rows, hazop_row_safeguards, safeguards, safeguard_dependencies,
       risk_rescores, risk_rule_sets, citations
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.response import response_error


class HazopService:
    """
    Service for HAZOP rows and risk.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize HazopService with a DB session."""
        self.db = db

    async def get_rows(
        self,
        node: Optional[str] = None,
        band: Optional[str] = None,
        rescored: Optional[bool] = None
    ) -> JSONResponse:
        """Return {nodes: [{code, name, rows: [HazopRowSummary]}]} sorted by row code."""
        return response_error("Not implemented", code=501)

    async def get_matrix(self) -> JSONResponse:
        """Return all 25 cells with live and design-basis rows, moved rows and rule set version."""
        return response_error("Not implemented", code=501)

    async def get_row(self, row_code: str) -> JSONResponse:
        """Return one row with versions, safeguards and proposals; 404 if unknown."""
        return response_error("Not implemented", code=501)

    async def get_why(self, row_code: str) -> JSONResponse:
        """Return the "Why it moved" panel; unmoved rows return live = design_basis and trigger = null."""
        return response_error("Not implemented", code=501)

    async def get_active_rule_set(self) -> JSONResponse:
        """Return the active risk rule set and its version."""
        return response_error("Not implemented", code=501)
