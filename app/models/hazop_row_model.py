"""HazopRow SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import CheckConstraint, Column, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import (
    RecordStatus,
    agent_name_enum,
    guide_word_enum,
    hazop_param_enum,
    record_status_enum,
)


class HazopRow(Base):
    """
    One version of a HAZOP worksheet row, e.g. HZ-N1-003 v1.

    Approved rows are immutable; a change creates a new version that
    supersedes the old one.
    """
    __tablename__ = "hazop_rows"
    __table_args__ = (
        UniqueConstraint("node_id", "row_code", "version", name="uq_hazop_rows_node_code_version"),
        Index("ix_hazop_rows_status", "status"),
        Index("ix_hazop_rows_row_code", "row_code"),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_hazop_rows_severity"),
        CheckConstraint("likelihood_base BETWEEN 1 AND 5", name="ck_hazop_rows_likelihood_base"),
    )

    id = uuid_pk()
    node_id = uuid_fk("process_nodes.id", nullable=False)
    row_code = Column(String(24), nullable=False, comment="HZ-N1-003")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    guide_word = Column(guide_word_enum, nullable=False)
    parameter = Column(hazop_param_enum, nullable=False)
    deviation = Column(Text, nullable=False)
    cause = Column(Text, nullable=False)
    cause_asset_id = uuid_fk(
        "assets.id",
        index=True,
        comment="Asset whose health drives likelihood"
    )
    consequence = Column(Text, nullable=False)
    severity = Column(SmallInteger, nullable=False, comment="1-5")
    likelihood_base = Column(SmallInteger, nullable=False, comment="1-5, design basis")
    status = Column(
        record_status_enum,
        nullable=False,
        default=RecordStatus.APPROVED,
        server_default=RecordStatus.APPROVED.value
    )
    supersedes_id = uuid_fk("hazop_rows.id")
    created_by_agent = Column(agent_name_enum, comment="Null when written by a person")
    created_by_user = uuid_fk("users.id")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<HazopRow(row_code={self.row_code}, version={self.version})>"
