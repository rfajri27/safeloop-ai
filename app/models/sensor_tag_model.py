"""SensorTag SQLAlchemy model (plant model group)."""
from sqlalchemy import Column, Numeric, String, Text
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import DataOrigin, data_origin_enum


class SensorTag(Base):
    """A measured signal on an asset, e.g. P101_DE_VIB_RMS."""
    __tablename__ = "sensor_tags"

    id = uuid_pk()
    asset_id = uuid_fk("assets.id", nullable=False, index=True)
    tag = Column(String(64), nullable=False, unique=True, comment="P101_DE_VIB_RMS")
    description = Column(String(200))
    eng_unit = Column(String(16), nullable=False, comment="mm/s, °C, barg")
    alert_low = Column(Numeric)
    alert_high = Column(Numeric)
    alert_high_tightened = Column(
        Numeric,
        comment="Set by rule R-P-01 for safety-critical assets"
    )
    source_dataset = Column(String(64), comment="NASA IMS, TEP, synthetic")
    source_signal = Column(String(128), comment="Column or channel in the source dataset")
    transform = Column(Text, comment="Feature extraction / rescaling applied")
    origin = Column(
        data_origin_enum,
        nullable=False,
        default=DataOrigin.PUBLIC_PROXY,
        server_default=DataOrigin.PUBLIC_PROXY.value
    )

    def __repr__(self) -> str:
        return f"<SensorTag(tag={self.tag})>"
