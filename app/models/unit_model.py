"""Unit SQLAlchemy model (plant model group)."""
from sqlalchemy import Column, String, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class Unit(Base):
    """A process unit within a site, e.g. U100."""
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("site_id", "code", name="uq_units_site_code"),
    )

    id = uuid_pk()
    site_id = uuid_fk("sites.id", nullable=False)
    code = Column(String(32), nullable=False, comment="e.g. U100")
    name = Column(String(200), nullable=False)
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<Unit(code={self.code})>"
