"""Repository for HealthAssessment entity."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.health_assessment_model import HealthAssessment


class HealthAssessmentRepository(BaseRepository[HealthAssessment]):
    """Repository for HealthAssessment queries."""
    model_class = HealthAssessment

    async def get_latest_for_asset(self, replay_run_id: str, asset_id: str) -> Optional[HealthAssessment]:
        """Latest assessment of one asset in a run."""
        result = await self.session.execute(
            select(HealthAssessment)
            .where(
                HealthAssessment.replay_run_id == replay_run_id,
                HealthAssessment.asset_id == asset_id,
            )
            .order_by(HealthAssessment.replay_hour.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_per_asset(
        self,
        replay_run_id: str,
        asset_ids: Optional[Sequence[str]] = None
    ) -> Sequence[HealthAssessment]:
        """Latest assessment per asset in a run (health tiles, asset list)."""
        query = (
            select(HealthAssessment)
            .where(HealthAssessment.replay_run_id == replay_run_id)
            .distinct(HealthAssessment.asset_id)
            .order_by(HealthAssessment.asset_id, HealthAssessment.replay_hour.desc())
        )
        if asset_ids is not None:
            query = query.where(HealthAssessment.asset_id.in_(asset_ids))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_history(self, replay_run_id: str, asset_id: str) -> Sequence[HealthAssessment]:
        """Health index per replay hour for one asset, oldest first."""
        result = await self.session.execute(
            select(HealthAssessment)
            .where(
                HealthAssessment.replay_run_id == replay_run_id,
                HealthAssessment.asset_id == asset_id,
            )
            .order_by(HealthAssessment.replay_hour)
        )
        return result.scalars().all()

    async def get_last_band_change(self, replay_run_id: str, asset_id: str) -> Optional[HealthAssessment]:
        """Latest row where the band changed (previous_band is set)."""
        result = await self.session.execute(
            select(HealthAssessment)
            .where(
                HealthAssessment.replay_run_id == replay_run_id,
                HealthAssessment.asset_id == asset_id,
                HealthAssessment.previous_band.is_not(None),
            )
            .order_by(HealthAssessment.replay_hour.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_band_changes(self, replay_run_id: str) -> Sequence[HealthAssessment]:
        """All band changes in a run, oldest first."""
        result = await self.session.execute(
            select(HealthAssessment)
            .where(
                HealthAssessment.replay_run_id == replay_run_id,
                HealthAssessment.previous_band.is_not(None),
            )
            .order_by(HealthAssessment.replay_hour)
        )
        return result.scalars().all()
