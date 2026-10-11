"""HealthAssessment SQLAlchemy model (telemetry & health group)."""
from sqlalchemy import CheckConstraint, Column, Index, SmallInteger, String, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import health_band_enum


class HealthAssessment(Base):
    """Health index of an asset at a replay hour; previous_band is set on a band change."""
    __tablename__ = "health_assessments"
    __table_args__ = (
        UniqueConstraint(
            "replay_run_id", "asset_id", "replay_hour",
            name="uq_health_assessments_run_asset_hour"
        ),
        Index("ix_health_assessments_asset_created", "asset_id", "created_at"),
        CheckConstraint("health_index BETWEEN 0 AND 100", name="ck_health_assessments_index"),
    )

    id = uuid_pk()
    replay_run_id = uuid_fk("replay_runs.id", nullable=False)
    asset_id = uuid_fk("assets.id", nullable=False)
    replay_hour = Column(SmallInteger, nullable=False)
    health_index = Column(SmallInteger, nullable=False, comment="0-100, rounded")
    band = Column(health_band_enum, nullable=False)
    previous_band = Column(health_band_enum, comment="Set when this row is a band change")
    model_version = Column(String(32), nullable=False, comment="e.g. pca-hi-v1")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<HealthAssessment(asset_id={self.asset_id}, hour={self.replay_hour}, hi={self.health_index})>"
