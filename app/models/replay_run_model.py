"""ReplayRun SQLAlchemy model (telemetry & health group)."""
from sqlalchemy import CheckConstraint, Column, DateTime, Index, SmallInteger, String
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class ReplayRun(Base):
    """One scenario replay (S1 or S2). Active while ended_at IS NULL."""
    __tablename__ = "replay_runs"
    __table_args__ = (
        CheckConstraint("speed IN (1, 3, 8)", name="ck_replay_runs_speed"),
        # Only one active run at a time (the MVP has a single unit).
        Index(
            "uq_replay_runs_one_active",
            sa_text("(ended_at IS NULL)"),
            unique=True,
            postgresql_where=sa_text("ended_at IS NULL")
        ),
    )

    id = uuid_pk()
    scenario_code = Column(String(8), nullable=False, comment="S1, S2")
    speed = Column(SmallInteger, nullable=False, default=3, server_default="3", comment="1x, 3x, 8x")
    started_by = uuid_fk("users.id")
    started_at = timestamp_now()
    ended_at = Column(DateTime(timezone=True))
    final_hour = Column(SmallInteger)

    def __repr__(self) -> str:
        return f"<ReplayRun(id={self.id}, scenario={self.scenario_code})>"
