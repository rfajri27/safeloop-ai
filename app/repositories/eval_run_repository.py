"""Repository for EvalRun entity."""
from typing import Optional
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.eval_run_model import EvalRun


class EvalRunRepository(BaseRepository[EvalRun]):
    """Repository for EvalRun queries."""
    model_class = EvalRun

    async def get_running(self) -> Optional[EvalRun]:
        """The run in progress (finished_at IS NULL), if any."""
        result = await self.session.execute(
            select(EvalRun).where(EvalRun.finished_at.is_(None)).order_by(EvalRun.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_finished(self, frozen_only: bool = True) -> Optional[EvalRun]:
        """Latest finished run, frozen only by default."""
        query = select(EvalRun).where(EvalRun.finished_at.is_not(None))
        if frozen_only:
            query = query.where(EvalRun.is_frozen.is_(True))
        result = await self.session.execute(query.order_by(EvalRun.finished_at.desc()).limit(1))
        return result.scalar_one_or_none()
