"""Repository for AssetLink entity (asset graph edges)."""
from typing import Optional, Sequence
from sqlalchemy import or_, select
from app.repositories.base import BaseRepository
from app.models.asset_link_model import AssetLink


class AssetLinkRepository(BaseRepository[AssetLink]):
    """Repository for AssetLink queries. Composite key: no get_by_id."""
    model_class = AssetLink

    async def list_for_asset(self, asset_id: str, relation: Optional[str] = None) -> Sequence[AssetLink]:
        """List edges touching an asset in either direction."""
        query = select(AssetLink).where(
            or_(AssetLink.from_asset_id == asset_id, AssetLink.to_asset_id == asset_id)
        )
        if relation:
            query = query.where(AssetLink.relation == relation)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_for_assets(self, asset_ids: Sequence[str]) -> Sequence[AssetLink]:
        """List edges touching any of the given assets (Red Team context)."""
        if not asset_ids:
            return []
        result = await self.session.execute(
            select(AssetLink).where(
                or_(AssetLink.from_asset_id.in_(asset_ids), AssetLink.to_asset_id.in_(asset_ids))
            )
        )
        return result.scalars().all()

    async def exists(self, from_asset_id: str, to_asset_id: str, relation: Optional[str] = None) -> bool:
        """Check an edge exists (Judge `asset_model:` citations)."""
        query = select(AssetLink).where(
            AssetLink.from_asset_id == from_asset_id,
            AssetLink.to_asset_id == to_asset_id,
        )
        if relation:
            query = query.where(AssetLink.relation == relation)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def list_all(self) -> Sequence[AssetLink]:
        """Every edge, ordered by link code (Red Team asset model, Judge)."""
        result = await self.session.execute(select(AssetLink).order_by(AssetLink.code))
        return result.scalars().all()

    async def get_by_code(self, code: str) -> Optional[AssetLink]:
        """An edge by its citation code, e.g. L-104."""
        result = await self.session.execute(select(AssetLink).where(AssetLink.code == code))
        return result.scalar_one_or_none()
