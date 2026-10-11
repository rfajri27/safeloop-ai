"""Repository for ChatSession entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.chat_session_model import ChatSession


class ChatSessionRepository(BaseRepository[ChatSession]):
    """Repository for ChatSession queries."""
    model_class = ChatSession

    async def list_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> Sequence[ChatSession]:
        """A user's sessions, newest first."""
        result = await self.session.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.started_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
