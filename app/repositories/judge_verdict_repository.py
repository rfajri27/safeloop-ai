"""Repository for JudgeVerdict entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.enums import Verdict
from app.models.judge_verdict_model import JudgeVerdict


class JudgeVerdictRepository(BaseRepository[JudgeVerdict]):
    """Repository for JudgeVerdict queries."""
    model_class = JudgeVerdict

    async def get_by_proposal(self, proposal_id: str) -> Optional[JudgeVerdict]:
        """Latest verdict for a proposal."""
        result = await self.session.execute(
            select(JudgeVerdict)
            .where(JudgeVerdict.proposal_id == proposal_id)
            .order_by(JudgeVerdict.checked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_proposals(self, proposal_ids: Sequence[str]) -> Sequence[JudgeVerdict]:
        """Verdicts for several proposals (a Red Team run)."""
        if not proposal_ids:
            return []
        result = await self.session.execute(
            select(JudgeVerdict).where(JudgeVerdict.proposal_id.in_(proposal_ids))
        )
        return result.scalars().all()

    async def count_by_verdict(self, verdict: Verdict) -> int:
        """Number of verdicts of one kind, e.g. block."""
        result = await self.session.execute(
            select(func.count()).select_from(JudgeVerdict).where(JudgeVerdict.verdict == verdict)
        )
        return result.scalar() or 0
