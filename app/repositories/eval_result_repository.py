"""Repository for EvalResult entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.eval_result_model import EvalResult


class EvalResultRepository(BaseRepository[EvalResult]):
    """Repository for EvalResult queries."""
    model_class = EvalResult

    async def list_by_run(self, eval_run_id: str) -> Sequence[EvalResult]:
        """Metrics of a run ordered by objective (PO-1 ... PO-5)."""
        result = await self.session.execute(
            select(EvalResult)
            .where(EvalResult.eval_run_id == eval_run_id)
            .order_by(EvalResult.objective_code, EvalResult.metric)
        )
        return result.scalars().all()
