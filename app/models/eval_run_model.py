"""EvalRun SQLAlchemy model (evaluation group)."""
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class EvalRun(Base):
    """One evaluation run over the golden sets. Running while finished_at IS NULL."""
    __tablename__ = "eval_runs"

    id = uuid_pk()
    started_at = timestamp_now()
    finished_at = Column(DateTime(timezone=True))
    git_sha = Column(String(40))
    model_id = Column(String(64))
    rule_set_id = uuid_fk("risk_rule_sets.id")
    dataset_hash = Column(String(64))
    is_frozen = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa_text("false"),
        comment="True for the demo-day run"
    )

    def __repr__(self) -> str:
        return f"<EvalRun(id={self.id}, frozen={self.is_frozen})>"
