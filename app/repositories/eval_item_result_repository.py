"""Repository for EvalItemResult entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.eval_item_result_model import EvalItemResult
from app.models.golden_item_model import GoldenItem


class EvalItemResultRepository(BaseRepository[EvalItemResult]):
    """Repository for EvalItemResult queries. Composite key: no get_by_id."""
    model_class = EvalItemResult

    async def list_by_run(
        self,
        eval_run_id: str,
        set_name: Optional[str] = None
    ) -> Sequence[tuple[EvalItemResult, GoldenItem]]:
        """(result, golden item) for a run, optionally one golden set."""
        query = (
            select(EvalItemResult, GoldenItem)
            .join(GoldenItem, GoldenItem.id == EvalItemResult.golden_item_id)
            .where(EvalItemResult.eval_run_id == eval_run_id)
        )
        if set_name:
            query = query.where(GoldenItem.set_name == set_name)
        result = await self.session.execute(query.order_by(GoldenItem.set_name, GoldenItem.created_at))
        return result.tuples().all()

    async def pass_counts_by_set(self, eval_run_id: str) -> dict[str, tuple[int, int]]:
        """{set_name: (passed, total)} for a run."""
        result = await self.session.execute(
            select(
                GoldenItem.set_name,
                func.count().filter(EvalItemResult.passed.is_(True)),
                func.count(),
            )
            .join(GoldenItem, GoldenItem.id == EvalItemResult.golden_item_id)
            .where(EvalItemResult.eval_run_id == eval_run_id)
            .group_by(GoldenItem.set_name)
        )
        return {name: (passed, total) for name, passed, total in result.tuples().all()}
