"""Repository for ChatMessage entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.chat_message_model import ChatMessage


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """Repository for ChatMessage queries."""
    model_class = ChatMessage

    async def list_by_session(self, session_id: str) -> Sequence[ChatMessage]:
        """Session thread, oldest first."""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        return result.scalars().all()

    async def list_last(self, session_id: str, n: int = 12) -> Sequence[ChatMessage]:
        """Last n messages, oldest first (follow-up context: 6 turns = 12 messages)."""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(n)
        )
        return list(reversed(result.scalars().all()))
