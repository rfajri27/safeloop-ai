"""Repository for GoldenItem entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.golden_item_model import GoldenItem


class GoldenItemRepository(BaseRepository[GoldenItem]):
    """Repository for GoldenItem queries."""
    model_class = GoldenItem

    async def list_by_sets(self, set_names: Sequence[str], split: str = "test") -> Sequence[GoldenItem]:
        """Golden items of the given sets and split, ordered for a stable dataset hash."""
        result = await self.session.execute(
            select(GoldenItem)
            .where(GoldenItem.set_name.in_(set_names), GoldenItem.split == split)
            .order_by(GoldenItem.set_name, GoldenItem.created_at, GoldenItem.id)
        )
        return result.scalars().all()
