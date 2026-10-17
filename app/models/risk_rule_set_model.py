"""RiskRuleSet SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import RecordStatus, record_status_enum


class RiskRuleSet(Base):
    """Versioned rules for the deterministic Risk Engine."""
    __tablename__ = "risk_rule_sets"

    id = uuid_pk()
    version = Column(String(16), nullable=False, unique=True, comment="v1.0")
    rules = Column(
        JSONB,
        nullable=False,
        comment='{"R-L-01":{"band":"degraded","dL":1}, "R-S-01":{...}}'
    )
    status = Column(
        record_status_enum,
        nullable=False,
        default=RecordStatus.DRAFT,
        server_default=RecordStatus.DRAFT.value
    )
    approved_by = uuid_fk("users.id", comment="Process safety engineer")
    approved_at = Column(DateTime(timezone=True))
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<RiskRuleSet(version={self.version}, status={self.status})>"
