"""Safeguard SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import Column, Date, String, Text, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import safeguard_type_enum


class Safeguard(Base):
    """A safeguard, e.g. PSV-201, FAL-201, P-101B auto-start."""
    __tablename__ = "safeguards"
    __table_args__ = (
        UniqueConstraint("unit_id", "ref_code", name="uq_safeguards_unit_ref_code"),
    )

    id = uuid_pk()
    unit_id = uuid_fk("units.id", nullable=False)
    ref_code = Column(String(64), nullable=False, comment="PSV-201, FAL-201, P-101B auto-start")
    type = Column(safeguard_type_enum, nullable=False)
    description = Column(Text)
    last_test_date = Column(Date)

    def __repr__(self) -> str:
        return f"<Safeguard(ref_code={self.ref_code}, type={self.type})>"
