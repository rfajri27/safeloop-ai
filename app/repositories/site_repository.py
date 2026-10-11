"""Repository for Site entity."""
from typing import Optional
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.site_model import Site


class SiteRepository(BaseRepository[Site]):
    """Repository for Site queries."""
    model_class = Site

    async def get_by_code(self, code: str) -> Optional[Site]:
        """Get a site by its code, e.g. DEMO-SITE."""
        result = await self.session.execute(select(Site).where(Site.code == code))
        return result.scalar_one_or_none()
