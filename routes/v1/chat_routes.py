"""Chat API routes for the knowledge assistant.

Endpoints:
    POST /chat-sessions                              - Open a chat session
    GET  /chat-sessions/{session_id}/messages        - Session history with citations
    POST /chat-sessions/{session_id}/messages        - Ask, wait for the full answer
    POST /chat-sessions/{session_id}/messages/stream - Ask, stream the answer (SSE)
"""
from fastapi import APIRouter, Depends
from config.ratelimit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import CHAT_ROLES, get_current_user, require_role
from app.services.chat_service import ChatService
from app.schemas.auth_schema import CurrentUser
from app.schemas.chat_schema import ChatMessageCreate

router = APIRouter(prefix="/chat-sessions", tags=["Knowledge"])

# LLM endpoints: 10 requests per minute
llm_rate_limit = [Depends(RateLimiter(times=10, seconds=60))]
chat_user = require_role(*CHAT_ROLES, action="ask the knowledge assistant")


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """Dependency: Create ChatService."""
    return ChatService(db)


@router.post("", summary="Open a chat session")
async def create_session(
    user: CurrentUser = Depends(chat_user),
    service: ChatService = Depends(get_chat_service)
):
    """Create a session; its id is also the LangGraph thread_id."""
    return await service.create_session(user)


@router.get("/{session_id}/messages", summary="Get session history")
async def get_messages(
    session_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    """Session history, oldest first. Owner or auditor only."""
    return await service.get_messages(session_id, user)


@router.post(
    "/{session_id}/messages",
    summary="Ask the assistant",
    dependencies=llm_rate_limit,
)
async def send_message(
    session_id: str,
    request: ChatMessageCreate,
    user: CurrentUser = Depends(chat_user),
    service: ChatService = Depends(get_chat_service)
):
    """Ask and wait for the full CitedAnswer."""
    return await service.send_message(
        session_id=session_id,
        content=request.content,
        asset_tag=request.asset_tag,
        user=user
    )


@router.post(
    "/{session_id}/messages/stream",
    summary="Ask the assistant (SSE)",
    dependencies=llm_rate_limit,
)
async def stream_message(
    session_id: str,
    request: ChatMessageCreate,
    user: CurrentUser = Depends(chat_user),
    service: ChatService = Depends(get_chat_service)
):
    """Ask and stream the answer as AG-UI events."""
    return await service.stream_message(
        session_id=session_id,
        content=request.content,
        asset_tag=request.asset_tag,
        user=user
    )
