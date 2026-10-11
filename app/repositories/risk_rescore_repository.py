"""Repository for RiskRescore entity (append-only Risk Engine output)."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import AppendOnlyRepository
from app.models.risk_rescore_model import RiskRescore


class RiskRescoreRepository(AppendOnlyRepository[RiskRescore]):
    """Repository for RiskRescore queries."""
    model_class = RiskRescore

    async def get_latest_for_row(
        self,
        hazop_row_id: str,
        replay_run_id: Optional[str] = None
    ) -> Optional[RiskRescore]:
        """Latest re-score of a row, optionally within one run ("Why it moved")."""
        query = select(RiskRescore).where(RiskRescore.hazop_row_id == hazop_row_id)
        if replay_run_id:
            query = query.where(RiskRescore.replay_run_id == replay_run_id)
        result = await self.session.execute(query.order_by(RiskRescore.computed_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def get_latest_per_row(self, replay_run_id: str) -> Sequence[RiskRescore]:
        """Latest re-score per row in a run (live likelihoods for register and matrix)."""
        result = await self.session.execute(
            select(RiskRescore)
            .where(RiskRescore.replay_run_id == replay_run_id)
            .distinct(RiskRescore.hazop_row_id)
            .order_by(RiskRescore.hazop_row_id, RiskRescore.computed_at.desc())
        )
        return result.scalars().all()

    async def list_by_run(self, replay_run_id: str) -> Sequence[RiskRescore]:
        """Every re-score in a run, oldest first (reproducibility check, NFR-05)."""
        result = await self.session.execute(
            select(RiskRescore)
            .where(RiskRescore.replay_run_id == replay_run_id)
            .order_by(RiskRescore.computed_at, RiskRescore.hazop_row_id)
        )
        return result.scalars().all()

    async def list_by_trigger(self, trigger_health_id: str) -> Sequence[RiskRescore]:
        """Re-scores caused by one band change."""
        result = await self.session.execute(
            select(RiskRescore).where(RiskRescore.trigger_health_id == trigger_health_id)
        )
        return result.scalars().all()
