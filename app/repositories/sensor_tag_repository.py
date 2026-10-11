"""Repository for SensorTag entity."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.asset_model import Asset
from app.models.sensor_tag_model import SensorTag


class SensorTagRepository(BaseRepository[SensorTag]):
    """Repository for SensorTag queries."""
    model_class = SensorTag

    async def get_by_tag(self, tag: str) -> Optional[SensorTag]:
        """Get a sensor tag, e.g. P101_DE_VIB_RMS."""
        result = await self.session.execute(select(SensorTag).where(SensorTag.tag == tag))
        return result.scalar_one_or_none()

    async def list_by_asset(self, asset_id: str) -> Sequence[SensorTag]:
        """List an asset's sensor tags ordered by tag."""
        result = await self.session.execute(
            select(SensorTag).where(SensorTag.asset_id == asset_id).order_by(SensorTag.tag)
        )
        return result.scalars().all()

    async def list_by_assets(self, asset_ids: Sequence[str]) -> Sequence[SensorTag]:
        """List sensor tags for several assets."""
        if not asset_ids:
            return []
        result = await self.session.execute(
            select(SensorTag).where(SensorTag.asset_id.in_(asset_ids)).order_by(SensorTag.tag)
        )
        return result.scalars().all()

    async def list_monitored(self, unit_id: Optional[str] = None) -> Sequence[tuple[SensorTag, Asset]]:
        """List (sensor tag, asset) for monitored assets; the replay engine writes these."""
        query = (
            select(SensorTag, Asset)
            .join(Asset, Asset.id == SensorTag.asset_id)
            .where(Asset.is_monitored.is_(True))
        )
        if unit_id:
            query = query.where(Asset.unit_id == unit_id)
        result = await self.session.execute(query.order_by(SensorTag.tag))
        return result.tuples().all()
