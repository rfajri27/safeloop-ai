"""Repository for Safeguard entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.safeguard_model import Safeguard

_normalized_ref = func.upper(func.replace(Safeguard.ref_code, "-", ""))


class SafeguardRepository(BaseRepository[Safeguard]):
    """Repository for Safeguard queries."""
    model_class = Safeguard

    async def get_by_ref_code(self, ref_code: str, unit_id: Optional[str] = None) -> Optional[Safeguard]:
        """Get a safeguard by exact ref code, e.g. PSV-201."""
        query = select(Safeguard).where(Safeguard.ref_code == ref_code)
        if unit_id:
            query = query.where(Safeguard.unit_id == unit_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_by_unit(self, unit_id: str) -> Sequence[Safeguard]:
        """List a unit's safeguards ordered by ref code."""
        result = await self.session.execute(
            select(Safeguard).where(Safeguard.unit_id == unit_id).order_by(Safeguard.ref_code)
        )
        return result.scalars().all()

    async def list_by_ref_codes(self, ref_codes: Sequence[str], unit_id: Optional[str] = None) -> Sequence[Safeguard]:
        """Resolve ref codes with Judge matching rules (case-insensitive, hyphens ignored)."""
        if not ref_codes:
            return []
        keys = [code.replace("-", "").upper() for code in ref_codes]
        query = select(Safeguard).where(_normalized_ref.in_(keys))
        if unit_id:
            query = query.where(Safeguard.unit_id == unit_id)
        result = await self.session.execute(query)
        return result.scalars().all()
