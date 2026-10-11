"""Chat service for the knowledge assistant.

Endpoints served:
    POST /chat-sessions                               - Open a chat session (201)
    GET  /chat-sessions/{session_id}/messages         - Session history with citations
    POST /chat-sessions/{session_id}/messages         - Ask, wait for the full answer
    POST /chat-sessions/{session_id}/messages/stream  - Ask, stream the answer (SSE)

Writes (one transaction per answer): chat_messages, citations, agent_runs, audit_log
"""
from typing import Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth_schema import CurrentUser
from app.utils.response import response_error


class ChatService:
    """
    Service for chat sessions and cited answers.

    REQUEST-SCOPED: Created per request with injected session.
    Pre-stream checks: session exists (404), session belongs to the caller (403).
    """

    def __init__(self, db: AsyncSession):
        """Initialize ChatService with a DB session."""
        self.db = db

    async def create_session(self, user: CurrentUser) -> JSONResponse:
        """Create a session; its id is also the LangGraph thread_id."""
        return response_error("Not implemented", code=501)

    async def get_messages(self, session_id: str, user: CurrentUser) -> JSONResponse:
        """Return the thread oldest first; assistant messages in CitedAnswer shape."""
        return response_error("Not implemented", code=501)

    async def send_message(
        self,
        session_id: str,
        content: str,
        asset_tag: Optional[str],
        user: CurrentUser
    ) -> JSONResponse:
        """Run the knowledge graph to completion and return the CitedAnswer."""
        return response_error("Not implemented", code=501)

    async def stream_message(
        self,
        session_id: str,
        content: str,
        asset_tag: Optional[str],
        user: CurrentUser
    ) -> StreamingResponse:
        """Stream the knowledge graph as AG-UI events; RUN_FINISHED carries the CitedAnswer."""
        return response_error("Not implemented", code=501)
