"""AuditLog SQLAlchemy model (AI & governance group)."""
from sqlalchemy import BigInteger, Column, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk
from app.models.enums import agent_name_enum


class AuditLog(Base):
    """
    Append-only audit record.

    UPDATE/DELETE are revoked from the app role; insert via service only.
    The display id is `AUD-` + zero-padded id.
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_table", "entity_id"),
        Index("ix_audit_log_occurred_at", "occurred_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at = timestamp_now()
    action = Column(
        String(48),
        nullable=False,
        comment="health_band_changed, risk_rescore, draft_created, judge_block, approved, rejected, guardrail_refusal"
    )
    actor_agent = Column(agent_name_enum)
    actor_user = uuid_fk("users.id")
    entity_table = Column(String(48), nullable=False)
    entity_id = Column(UUID(as_uuid=False), nullable=False)
    model_id = Column(String(64))
    prompt_version = Column(String(16))
    rule_set_version = Column(String(16))
    replay_run_id = uuid_fk("replay_runs.id", index=True)
    replay_hour = Column(SmallInteger)
    detail = Column(JSONB)

    @property
    def audit_id(self) -> str:
        """Display id, e.g. AUD-0148."""
        return f"AUD-{self.id:04d}" if self.id is not None else None

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action})>"
