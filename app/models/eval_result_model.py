"""EvalResult SQLAlchemy model (evaluation group)."""
from sqlalchemy import Boolean, Column, Integer, Numeric, String, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk


class EvalResult(Base):
    """One metric for one product objective (PO-1 ... PO-5) in an eval run."""
    __tablename__ = "eval_results"
    __table_args__ = (
        UniqueConstraint(
            "eval_run_id", "objective_code", "metric",
            name="uq_eval_results_run_objective_metric"
        ),
    )

    id = uuid_pk()
    eval_run_id = uuid_fk("eval_runs.id", nullable=False)
    objective_code = Column(String(8), nullable=False, comment="PO-1 ... PO-5")
    metric = Column(String(64), nullable=False)
    value = Column(Numeric)
    target = Column(Numeric)
    passed = Column(Boolean)
    sample_size = Column(Integer)

    def __repr__(self) -> str:
        return f"<EvalResult(objective={self.objective_code}, metric={self.metric})>"
