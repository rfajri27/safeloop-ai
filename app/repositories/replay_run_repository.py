"""Repository for ReplayRun entity."""
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.columns import utcnow
from app.models.replay_run_model import ReplayRun


class ReplayRunRepository(BaseRepository[ReplayRun]):
    """Repository for ReplayRun queries."""
    model_class = ReplayRun

    async def get_active(self) -> Optional[ReplayRun]:
        """Get the active run (ended_at IS NULL); at most one exists."""
        result = await self.session.execute(
            select(ReplayRun).where(ReplayRun.ended_at.is_(None)).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest(self, scenario_code: Optional[str] = None) -> Optional[ReplayRun]:
        """Get the most recently started run, active or not."""
        query = select(ReplayRun)
        if scenario_code:
            query = query.where(ReplayRun.scenario_code == scenario_code)
        result = await self.session.execute(query.order_by(ReplayRun.started_at.desc()).limit(1))
        return result.scalar_one_or_none()

    async def list_recent(self, skip: int = 0, limit: int = 50) -> Sequence[ReplayRun]:
        """List runs newest first."""
        result = await self.session.execute(
            select(ReplayRun).order_by(ReplayRun.started_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def end_run(
        self,
        run: ReplayRun,
        final_hour: Optional[int],
        ended_at: Optional[datetime] = None
    ) -> ReplayRun:
        """Close a run (flush only; the caller commits with its audit record)."""
        run.ended_at = ended_at or utcnow()
        run.final_hour = final_hour
        await self.session.flush()
        return run
