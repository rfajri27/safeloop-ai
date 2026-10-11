"""SensorReading SQLAlchemy model (telemetry & health group)."""
from sqlalchemy import Column, Numeric, SmallInteger, String
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk


class SensorReading(Base):
    """One value per (run, tag, replay hour). Append-only."""
    __tablename__ = "sensor_readings"

    replay_run_id = uuid_fk("replay_runs.id", nullable=False, primary_key=True)
    tag_id = uuid_fk("sensor_tags.id", nullable=False, primary_key=True)
    replay_hour = Column(SmallInteger, primary_key=True)
    ts = timestamp_now()
    value = Column(Numeric, nullable=False)
    quality = Column(
        String(12),
        nullable=False,
        default="good",
        server_default="good",
        comment="good / bad / uncertain"
    )

    def __repr__(self) -> str:
        return f"<SensorReading(tag_id={self.tag_id}, hour={self.replay_hour}, value={self.value})>"
