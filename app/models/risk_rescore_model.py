"""RiskRescore SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import CheckConstraint, Column, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class RiskRescore(Base):
    """Deterministic output of the Risk Engine. No LLM involved. Append-only."""
    __tablename__ = "risk_rescores"
    __table_args__ = (
        Index("ix_risk_rescores_row_computed", "hazop_row_id", "computed_at"),
        CheckConstraint("likelihood_old BETWEEN 1 AND 5", name="ck_risk_rescores_likelihood_old"),
        CheckConstraint("likelihood_new BETWEEN 1 AND 5", name="ck_risk_rescores_likelihood_new"),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_risk_rescores_severity"),
    )

    id = uuid_pk()
    hazop_row_id = uuid_fk("hazop_rows.id", nullable=False)
    rule_set_id = uuid_fk("risk_rule_sets.id", nullable=False)
    replay_run_id = uuid_fk("replay_runs.id", index=True)
    trigger_health_id = uuid_fk(
        "health_assessments.id",
        comment="Band change that caused this re-score"
    )
    likelihood_old = Column(SmallInteger, nullable=False)
    likelihood_new = Column(SmallInteger, nullable=False)
    severity = Column(SmallInteger, nullable=False)
    score_old = Column(SmallInteger, nullable=False)
    score_new = Column(SmallInteger, nullable=False)
    rules_applied = Column(ARRAY(Text), nullable=False, comment="{'R-L-01','R-S-01'}")
    safeguards_lost = Column(
        ARRAY(UUID(as_uuid=False)),
        comment="Safeguard ids whose credit was removed"
    )
    computed_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<RiskRescore(row={self.hazop_row_id}, {self.score_old}->{self.score_new})>"
