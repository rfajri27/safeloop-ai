"""Repository for HazopProposal entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.hazop_proposal_model import HazopProposal


class HazopProposalRepository(BaseRepository[HazopProposal]):
    """Repository for HazopProposal queries."""
    model_class = HazopProposal

    async def list_by_agent_run(self, agent_run_id: str) -> Sequence[HazopProposal]:
        """Proposals of one Red Team run (insertion order = proposal index)."""
        result = await self.session.execute(
            select(HazopProposal).where(HazopProposal.agent_run_id == agent_run_id)
        )
        return result.scalars().all()

    async def list_by_target_row(self, target_row_id: str) -> Sequence[HazopProposal]:
        """Proposals made against a row version."""
        result = await self.session.execute(
            select(HazopProposal).where(HazopProposal.target_row_id == target_row_id)
        )
        return result.scalars().all()

    async def list_by_target_rows(self, target_row_ids: Sequence[str]) -> Sequence[HazopProposal]:
        """Proposals made against any version of a row."""
        if not target_row_ids:
            return []
        result = await self.session.execute(
            select(HazopProposal).where(HazopProposal.target_row_id.in_(target_row_ids))
        )
        return result.scalars().all()
