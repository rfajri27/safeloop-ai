"""Repository for Asset entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.asset_model import Asset
from app.models.process_node_model import ProcessNode


def normalize_tag(tag: str) -> str:
    """Tag key used for matching: case-insensitive, hyphens ignored (P101B == P-101B)."""
    return tag.replace("-", "").upper()


_normalized_tag = func.upper(func.replace(Asset.tag, "-", ""))


class AssetRepository(BaseRepository[Asset]):
    """Repository for Asset queries."""
    model_class = Asset

    async def get_by_tag(self, tag: str, unit_id: Optional[str] = None) -> Optional[Asset]:
        """Get an asset by exact tag, e.g. P-101."""
        query = select(Asset).where(Asset.tag == tag)
        if unit_id:
            query = query.where(Asset.unit_id == unit_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_by_unit(
        self,
        unit_id: Optional[str] = None,
        node_code: Optional[str] = None,
        monitored_only: bool = False,
        skip: int = 0,
        limit: int = 200
    ) -> Sequence[Asset]:
        """List assets ordered by tag, optionally by node code or monitored flag."""
        query = select(Asset)
        if unit_id:
            query = query.where(Asset.unit_id == unit_id)
        if node_code:
            query = query.join(ProcessNode, ProcessNode.id == Asset.node_id).where(
                ProcessNode.code == node_code
            )
        if monitored_only:
            query = query.where(Asset.is_monitored.is_(True))
        result = await self.session.execute(query.order_by(Asset.tag).offset(skip).limit(limit))
        return result.scalars().all()

    async def count_by_unit(self, unit_id: str) -> int:
        """Count assets in a unit."""
        result = await self.session.execute(
            select(func.count()).select_from(Asset).where(Asset.unit_id == unit_id)
        )
        return result.scalar() or 0

    async def list_by_ids(self, asset_ids: Sequence[str]) -> Sequence[Asset]:
        """List assets by id."""
        if not asset_ids:
            return []
        result = await self.session.execute(select(Asset).where(Asset.id.in_(asset_ids)))
        return result.scalars().all()

    async def list_by_tags(self, tags: Sequence[str], unit_id: Optional[str] = None) -> Sequence[Asset]:
        """Resolve tags with Judge matching rules (case-insensitive, hyphens ignored)."""
        if not tags:
            return []
        query = select(Asset).where(_normalized_tag.in_([normalize_tag(t) for t in tags]))
        if unit_id:
            query = query.where(Asset.unit_id == unit_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_standby_for(self, asset_id: str) -> Optional[Asset]:
        """Get the standby asset of a duty asset (P-101B for P-101)."""
        result = await self.session.execute(select(Asset).where(Asset.standby_of_id == asset_id))
        return result.scalars().first()
