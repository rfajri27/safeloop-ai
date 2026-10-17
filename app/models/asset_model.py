"""Asset SQLAlchemy model (plant model group)."""
from sqlalchemy import Boolean, CheckConstraint, CHAR, Column, String, UniqueConstraint
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import DataOrigin, data_origin_enum


class Asset(Base):
    """Equipment or instrument, e.g. P-101, TV-301, PSV-201."""
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("unit_id", "tag", name="uq_assets_unit_tag"),
        CheckConstraint("criticality IN ('A', 'B', 'C')", name="ck_assets_criticality"),
    )

    id = uuid_pk()
    unit_id = uuid_fk("units.id", nullable=False)
    node_id = uuid_fk("process_nodes.id")
    tag = Column(String(32), nullable=False, comment="P-101, TV-301, PSV-201")
    name = Column(String(200), nullable=False)
    asset_class = Column(
        String(64),
        nullable=False,
        comment="centrifugal_pump, control_valve, psv, heat_exchanger"
    )
    criticality = Column(CHAR(1), comment="A / B / C")
    standby_of_id = uuid_fk("assets.id", comment="P-101B is standby of P-101")
    is_monitored = Column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    origin = Column(
        data_origin_enum,
        nullable=False,
        default=DataOrigin.SYNTHETIC,
        server_default=DataOrigin.SYNTHETIC.value
    )

    def __repr__(self) -> str:
        return f"<Asset(tag={self.tag})>"
