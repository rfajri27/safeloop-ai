"""Repository for HazopRecommendation entity."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.hazop_recommendation_model import HazopRecommendation


class HazopRecommendationRepository(BaseRepository[HazopRecommendation]):
    """Repository for HazopRecommendation queries."""
    model_class = HazopRecommendation

    async def list_by_row(self, hazop_row_id: str) -> Sequence[HazopRecommendation]:
        """Recommendations of one row version."""
        result = await self.session.execute(
            select(HazopRecommendation).where(HazopRecommendation.hazop_row_id == hazop_row_id)
        )
        return result.scalars().all()
