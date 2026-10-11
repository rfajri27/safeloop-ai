"""Repository for RiskRuleSet entity."""
from typing import Optional
from sqlalchemy import case, select
from app.repositories.base import BaseRepository
from app.models.enums import RecordStatus
from app.models.risk_rule_set_model import RiskRuleSet


class RiskRuleSetRepository(BaseRepository[RiskRuleSet]):
    """Repository for RiskRuleSet queries."""
    model_class = RiskRuleSet

    async def get_by_version(self, version: str) -> Optional[RiskRuleSet]:
        """Get a rule set by version, e.g. v1."""
        result = await self.session.execute(select(RiskRuleSet).where(RiskRuleSet.version == version))
        return result.scalar_one_or_none()

    async def get_active(self) -> Optional[RiskRuleSet]:
        """Active rule set: newest approved one, else newest draft / under review.

        The MVP ships v1 as "pending engineer approval", so a draft is used
        until an approved set exists. Superseded and rejected sets never are.
        """
        approved_first = case((RiskRuleSet.status == RecordStatus.APPROVED, 0), else_=1)
        result = await self.session.execute(
            select(RiskRuleSet)
            .where(RiskRuleSet.status.not_in((RecordStatus.SUPERSEDED, RecordStatus.REJECTED)))
            .order_by(approved_first, RiskRuleSet.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
