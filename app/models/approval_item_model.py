"""ApprovalItem SQLAlchemy model (AI & governance group)."""
from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import (
    ApprovalDecision,
    approval_decision_enum,
    artifact_type_enum,
)


class ApprovalItem(Base):
    """A draft waiting for a human decision (HAZOP change, re-score, ...)."""
    __tablename__ = "approval_items"
    __table_args__ = (
        Index("ix_approval_items_decision", "decision"),
        Index("ix_approval_items_type_created", "artifact_type", "created_at"),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_approval_items_confidence"
        ),
        CheckConstraint(
            "decision <> 'rejected' OR decision_reason IS NOT NULL",
            name="ck_approval_items_reject_reason"
        ),
    )

    id = uuid_pk()
    artifact_type = Column(artifact_type_enum, nullable=False)
    title = Column(String(300), nullable=False)
    asset_id = uuid_fk("assets.id")
    proposal_id = uuid_fk("hazop_proposals.id", index=True)
    rescore_id = uuid_fk("risk_rescores.id", index=True)
    body = Column(JSONB, comment="Draft content for reports and recommendations")
    confidence = Column(String(8), nullable=False, comment="high / medium / low")
    judge_verdict_id = uuid_fk("judge_verdicts.id")
    decision = Column(
        approval_decision_enum,
        nullable=False,
        default=ApprovalDecision.PENDING,
        server_default=ApprovalDecision.PENDING.value
    )
    decided_by = uuid_fk("users.id")
    decision_reason = Column(Text, comment="Required when decision = rejected (CHECK)")
    edited_body = Column(JSONB, comment="Reviewer edits, kept as a diff source")
    created_at = timestamp_now()
    decided_at = Column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<ApprovalItem(id={self.id}, type={self.artifact_type}, decision={self.decision})>"
