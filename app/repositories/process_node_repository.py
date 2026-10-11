"""Repository for ProcessNode entity."""
from typing import Optional, Sequence
from sqlalchemy import select
from app.repositories.base import BaseRepository
from app.models.process_node_model import ProcessNode


class ProcessNodeRepository(BaseRepository[ProcessNode]):
    """Repository for ProcessNode queries."""
    model_class = ProcessNode

    async def get_by_code(self, unit_id: str, code: str) -> Optional[ProcessNode]:
        """Get a node by unit and code, e.g. N1."""
        result = await self.session.execute(
            select(ProcessNode).where(ProcessNode.unit_id == unit_id, ProcessNode.code == code)
        )
        return result.scalar_one_or_none()

    async def list_by_unit(self, unit_id: str) -> Sequence[ProcessNode]:
        """List a unit's nodes ordered by code."""
        result = await self.session.execute(
            select(ProcessNode).where(ProcessNode.unit_id == unit_id).order_by(ProcessNode.code)
        )
        return result.scalars().all()

    async def list_by_ids(self, node_ids: Sequence[str]) -> Sequence[ProcessNode]:
        """List nodes by id."""
        if not node_ids:
            return []
        result = await self.session.execute(
            select(ProcessNode).where(ProcessNode.id.in_(node_ids))
        )
        return result.scalars().all()
