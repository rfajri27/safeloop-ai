"""Repository for HazopRowSafeguard entity (row <-> safeguard credit)."""
from typing import Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.hazop_row_safeguard_model import HazopRowSafeguard
from app.models.safeguard_model import Safeguard


class HazopRowSafeguardRepository(BaseRepository[HazopRowSafeguard]):
    """Repository for HazopRowSafeguard queries. Composite key: no get_by_id."""
    model_class = HazopRowSafeguard

    async def list_for_row(self, hazop_row_id: str) -> Sequence[tuple[HazopRowSafeguard, Safeguard]]:
        """(link, safeguard) for one row, ordered by ref code."""
        result = await self.session.execute(
            select(HazopRowSafeguard, Safeguard)
            .join(Safeguard, Safeguard.id == HazopRowSafeguard.safeguard_id)
            .where(HazopRowSafeguard.hazop_row_id == hazop_row_id)
            .order_by(Safeguard.ref_code)
        )
        return result.tuples().all()

    async def list_for_rows(self, hazop_row_ids: Sequence[str]) -> Sequence[tuple[HazopRowSafeguard, Safeguard]]:
        """(link, safeguard) for several rows (register and matrix screens)."""
        if not hazop_row_ids:
            return []
        result = await self.session.execute(
            select(HazopRowSafeguard, Safeguard)
            .join(Safeguard, Safeguard.id == HazopRowSafeguard.safeguard_id)
            .where(HazopRowSafeguard.hazop_row_id.in_(hazop_row_ids))
            .order_by(HazopRowSafeguard.hazop_row_id, Safeguard.ref_code)
        )
        return result.tuples().all()

    async def list_row_ids_for_safeguards(self, safeguard_ids: Sequence[str]) -> Sequence[str]:
        """Rows that credit any of the given safeguards (rule R-S-01 fan-out)."""
        if not safeguard_ids:
            return []
        result = await self.session.execute(
            select(HazopRowSafeguard.hazop_row_id)
            .where(
                HazopRowSafeguard.safeguard_id.in_(safeguard_ids),
                HazopRowSafeguard.credited.is_(True),
            )
            .distinct()
        )
        return result.scalars().all()
