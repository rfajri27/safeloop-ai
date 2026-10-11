"""Repository for ApprovalItem entity."""
from typing import Any, Optional, Sequence
from sqlalchemy import func, select, union, update
from app.repositories.base import BaseRepository
from app.models.approval_item_model import ApprovalItem
from app.models.columns import utcnow
from app.models.enums import ApprovalDecision, ArtifactType
from app.models.hazop_proposal_model import HazopProposal
from app.models.risk_rescore_model import RiskRescore


class ApprovalItemRepository(BaseRepository[ApprovalItem]):
    """Repository for ApprovalItem queries."""
    model_class = ApprovalItem

    def _filtered(self, query, decision: Optional[ApprovalDecision], artifact_type: Optional[ArtifactType]):
        if decision:
            query = query.where(ApprovalItem.decision == decision)
        if artifact_type:
            query = query.where(ApprovalItem.artifact_type == artifact_type)
        return query

    async def list_filtered(
        self,
        decision: Optional[ApprovalDecision] = None,
        artifact_type: Optional[ArtifactType] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Sequence[ApprovalItem]:
        """Approval queue, newest first."""
        query = self._filtered(select(ApprovalItem), decision, artifact_type)
        result = await self.session.execute(
            query.order_by(ApprovalItem.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_filtered(
        self,
        decision: Optional[ApprovalDecision] = None,
        artifact_type: Optional[ArtifactType] = None
    ) -> int:
        """Count with the same filters as list_filtered()."""
        query = self._filtered(select(func.count()).select_from(ApprovalItem), decision, artifact_type)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_pending(self) -> int:
        """Pending items (sidebar badge)."""
        return await self.count_filtered(decision=ApprovalDecision.PENDING)

    async def get_by_proposal(self, proposal_id: str) -> Optional[ApprovalItem]:
        """Item queued for a Red Team proposal."""
        result = await self.session.execute(
            select(ApprovalItem).where(ApprovalItem.proposal_id == proposal_id)
        )
        return result.scalars().first()

    async def list_pending_row_ids(self) -> Sequence[str]:
        """HAZOP row ids with a pending item (shown as status `under_review`)."""
        from_proposals = (
            select(HazopProposal.target_row_id.label("row_id"))
            .join(ApprovalItem, ApprovalItem.proposal_id == HazopProposal.id)
            .where(ApprovalItem.decision == ApprovalDecision.PENDING)
        )
        from_rescores = (
            select(RiskRescore.hazop_row_id.label("row_id"))
            .join(ApprovalItem, ApprovalItem.rescore_id == RiskRescore.id)
            .where(ApprovalItem.decision == ApprovalDecision.PENDING)
        )
        result = await self.session.execute(union(from_proposals, from_rescores))
        return result.scalars().all()

    async def decide(
        self,
        item_id: str,
        decision: ApprovalDecision,
        decided_by: str,
        reason: Optional[str] = None,
        edited_body: Optional[dict[str, Any]] = None
    ) -> Optional[ApprovalItem]:
        """Record a decision only if the item is still pending (flush only).

        A single conditional UPDATE, so two reviewers cannot both decide the
        same item. Returns None when the item is missing or already decided;
        the service turns that into 404 / 409.
        """
        result = await self.session.execute(
            update(ApprovalItem)
            .where(ApprovalItem.id == item_id, ApprovalItem.decision == ApprovalDecision.PENDING)
            .values(
                decision=decision,
                decided_by=decided_by,
                decision_reason=reason,
                edited_body=edited_body,
                decided_at=utcnow(),
            )
            .returning(ApprovalItem)
            .execution_options(synchronize_session="fetch")
        )
        return result.scalar_one_or_none()
