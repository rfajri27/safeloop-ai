"""Repository for Unit entity."""
from typing import Optional
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.unit_model import Unit


class UnitRepository(BaseRepository[Unit]):
    """Repository for Unit queries."""
    model_class = Unit

    async def get_by_code(self, code: str, site_id: Optional[str] = None) -> Optional[Unit]:
        """Get a unit by code, e.g. U100. site_id is optional while the MVP has one site."""
        query = select(Unit).where(Unit.code == code)
        if site_id:
            query = query.where(Unit.site_id == site_id)
        result = await self.session.execute(query)
        return result.scalars().first()
