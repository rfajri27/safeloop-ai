"""Repository for AgentRun entity."""
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.agent_run_model import AgentRun
from app.models.enums import AgentName


class AgentRunRepository(BaseRepository[AgentRun]):
    """Repository for AgentRun queries."""
    model_class = AgentRun

    async def list_by_row(self, hazop_row_id: str, agent: Optional[AgentName] = None) -> Sequence[AgentRun]:
        """Runs on a HAZOP row, newest first (Red Team history)."""
        query = select(AgentRun).where(AgentRun.hazop_row_id == hazop_row_id)
        if agent:
            query = query.where(AgentRun.agent == agent)
        result = await self.session.execute(query.order_by(AgentRun.started_at.desc()))
        return result.scalars().all()

    async def get_by_chat_message(self, chat_message_id: str) -> Optional[AgentRun]:
        """The run that produced a chat answer."""
        result = await self.session.execute(
            select(AgentRun)
            .where(AgentRun.chat_message_id == chat_message_id)
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_chat_messages(self, chat_message_ids: Sequence[str]) -> Sequence[AgentRun]:
        """Runs for several chat answers (session history)."""
        if not chat_message_ids:
            return []
        result = await self.session.execute(
            select(AgentRun).where(AgentRun.chat_message_id.in_(chat_message_ids))
        )
        return result.scalars().all()

    async def list_latencies(self, agent: AgentName, since: Optional[datetime] = None) -> Sequence[int]:
        """latency_ms of successful runs (p95 check, NFR-03)."""
        query = select(AgentRun.latency_ms).where(
            AgentRun.agent == agent,
            AgentRun.latency_ms.is_not(None),
            AgentRun.error.is_(None),
        )
        if since:
            query = query.where(AgentRun.started_at >= since)
        result = await self.session.execute(query)
        return result.scalars().all()
