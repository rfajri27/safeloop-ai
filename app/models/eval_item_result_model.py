"""EvalItemResult SQLAlchemy model (evaluation group)."""
from sqlalchemy import Boolean, Column
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import uuid_fk


class EvalItemResult(Base):
    """Result of one golden item in one eval run."""
    __tablename__ = "eval_item_results"

    eval_run_id = uuid_fk("eval_runs.id", nullable=False, primary_key=True)
    golden_item_id = uuid_fk("golden_items.id", nullable=False, primary_key=True)
    passed = Column(Boolean, nullable=False)
    output = Column(JSONB)
    agent_run_id = uuid_fk("agent_runs.id")

    def __repr__(self) -> str:
        return f"<EvalItemResult(run={self.eval_run_id}, item={self.golden_item_id}, passed={self.passed})>"
