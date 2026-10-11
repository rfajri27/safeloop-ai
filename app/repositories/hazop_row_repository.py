"""Repository for HazopRow entity (versioned HAZOP register)."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.enums import RecordStatus
from app.models.hazop_row_model import HazopRow
from app.models.process_node_model import ProcessNode

# Versions that are no longer (or never were) the live row
_INACTIVE_STATUSES = (RecordStatus.SUPERSEDED, RecordStatus.REJECTED)


class HazopRowRepository(BaseRepository[HazopRow]):
    """Repository for HazopRow queries.

    "Current" = highest version of a row_code that is not superseded or rejected.
    """
    model_class = HazopRow

    def _current_query(self):
        return (
            select(HazopRow, ProcessNode)
            .join(ProcessNode, ProcessNode.id == HazopRow.node_id)
            .where(HazopRow.status.not_in(_INACTIVE_STATUSES))
            .distinct(HazopRow.row_code)
            .order_by(HazopRow.row_code, HazopRow.version.desc())
        )

    async def get_current_by_code(self, row_code: str) -> Optional[HazopRow]:
        """Current version of a row, e.g. HZ-N1-003."""
        result = await self.session.execute(
            select(HazopRow)
            .where(HazopRow.row_code == row_code, HazopRow.status.not_in(_INACTIVE_STATUSES))
            .order_by(HazopRow.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_current(
        self,
        node_code: Optional[str] = None,
        unit_id: Optional[str] = None
    ) -> Sequence[tuple[HazopRow, ProcessNode]]:
        """(row, node) for every current row, sorted by row code (register screen)."""
        query = self._current_query()
        if node_code:
            query = query.where(ProcessNode.code == node_code)
        if unit_id:
            query = query.where(ProcessNode.unit_id == unit_id)
        result = await self.session.execute(query)
        return result.tuples().all()

    async def list_current_by_cause_asset(self, asset_id: str) -> Sequence[tuple[HazopRow, ProcessNode]]:
        """Current rows whose cause asset is the given asset (rows an asset feeds)."""
        result = await self.session.execute(
            self._current_query().where(HazopRow.cause_asset_id == asset_id)
        )
        return result.tuples().all()

    async def list_current_by_ids(self, row_ids: Sequence[str]) -> Sequence[HazopRow]:
        """Rows by id (used with safeguard -> row lookups)."""
        if not row_ids:
            return []
        result = await self.session.execute(
            select(HazopRow).where(
                HazopRow.id.in_(row_ids), HazopRow.status.not_in(_INACTIVE_STATUSES)
            )
        )
        return result.scalars().all()

    async def list_versions(self, row_code: str) -> Sequence[HazopRow]:
        """Every version of a row, newest first."""
        result = await self.session.execute(
            select(HazopRow).where(HazopRow.row_code == row_code).order_by(HazopRow.version.desc())
        )
        return result.scalars().all()

    async def get_next_version(self, row_code: str) -> int:
        """Version number for a new version of row_code (1 for a new row)."""
        result = await self.session.execute(
            select(func.max(HazopRow.version)).where(HazopRow.row_code == row_code)
        )
        return (result.scalar() or 0) + 1

    async def count_current(self, unit_id: Optional[str] = None) -> int:
        """Number of current rows."""
        subquery = self._current_query()
        if unit_id:
            subquery = subquery.where(ProcessNode.unit_id == unit_id)
        result = await self.session.execute(
            select(func.count()).select_from(subquery.subquery())
        )
        return result.scalar() or 0

    async def supersede(self, row: HazopRow) -> HazopRow:
        """Mark a row version superseded (flush only; part of the approval transaction)."""
        row.status = RecordStatus.SUPERSEDED
        await self.session.flush()
        return row
