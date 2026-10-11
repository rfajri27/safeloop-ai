"""ProcessNode SQLAlchemy model (plant model group)."""
from sqlalchemy import Column, String, Text, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk


class ProcessNode(Base):
    """A HAZOP node within a unit, e.g. N1 Reflux circuit."""
    __tablename__ = "process_nodes"
    __table_args__ = (
        UniqueConstraint("unit_id", "code", name="uq_process_nodes_unit_code"),
    )

    id = uuid_pk()
    unit_id = uuid_fk("units.id", nullable=False)
    code = Column(String(16), nullable=False, comment="N1, N2, N3")
    name = Column(String(200), nullable=False)
    design_intent = Column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<ProcessNode(code={self.code})>"
