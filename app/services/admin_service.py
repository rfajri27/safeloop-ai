"""Admin service for corpus ingestion, seeding and agent graph views.

Endpoints served:
    POST /admin/ingest            - Re-ingest the synthetic corpus into Qdrant (202)
    POST /admin/seed              - Load asset model, HAZOP and users from data/
    GET  /agents/{agent_name}/graph - Mermaid view of a LangGraph graph (development only)
"""
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class AdminService:
    """
    Service for admin operations.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AdminService with a DB session."""
        self.db = db

    async def ingest(self, user: CurrentUser) -> JSONResponse:
        """Re-chunk data/corpus/*.md, embed, upsert into Qdrant; idempotent by content hash."""
        return response_error("Not implemented", code=501)

    async def seed(self, user: CurrentUser) -> JSONResponse:
        """Load asset model, HAZOP, rule set and demo users; 409 if a replay is running."""
        return response_error("Not implemented", code=501)

    async def get_agent_graph(self, agent_name: str) -> HTMLResponse:
        """Render the agent graph with render_graph_html; 404 unless APP_ENV=development."""
        return response_error("Not implemented", code=501)
