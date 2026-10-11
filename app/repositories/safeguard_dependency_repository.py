"""Repository for SafeguardDependency entity (safeguard -> asset)."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.asset_model import Asset
from app.models.safeguard_dependency_model import SafeguardDependency


class SafeguardDependencyRepository(BaseRepository[SafeguardDependency]):
    """Repository for SafeguardDependency queries. Composite key: no get_by_id."""
    model_class = SafeguardDependency

    async def list_for_safeguards(self, safeguard_ids: Sequence[str]) -> Sequence[tuple[SafeguardDependency, Asset]]:
        """(dependency, asset) for the given safeguards ("depends_on" in the Why panel)."""
        if not safeguard_ids:
            return []
        result = await self.session.execute(
            select(SafeguardDependency, Asset)
            .join(Asset, Asset.id == SafeguardDependency.asset_id)
            .where(SafeguardDependency.safeguard_id.in_(safeguard_ids))
            .order_by(Asset.tag)
        )
        return result.tuples().all()

    async def list_safeguard_ids_for_asset(self, asset_id: str) -> Sequence[str]:
        """Safeguards that depend on an asset (rule R-S-01 trigger)."""
        result = await self.session.execute(
            select(SafeguardDependency.safeguard_id).where(SafeguardDependency.asset_id == asset_id)
        )
        return result.scalars().all()
