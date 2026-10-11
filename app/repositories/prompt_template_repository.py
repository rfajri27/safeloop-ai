"""Repository for PromptTemplate entity."""
from typing import Optional
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.enums import AgentName
from app.models.prompt_template_model import PromptTemplate


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    """Repository for PromptTemplate queries."""
    model_class = PromptTemplate

    async def get_by_version(self, agent: AgentName, version: str) -> Optional[PromptTemplate]:
        """Get a template by agent and version, e.g. (red_team, redteam.v1)."""
        result = await self.session.execute(
            select(PromptTemplate).where(PromptTemplate.agent == agent, PromptTemplate.version == version)
        )
        return result.scalar_one_or_none()

    async def get_latest(self, agent: AgentName) -> Optional[PromptTemplate]:
        """Newest template for an agent."""
        result = await self.session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.agent == agent)
            .order_by(PromptTemplate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
