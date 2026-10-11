"""JudgeVerdict SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Boolean, CheckConstraint, Column, Text
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import ARRAY
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import verdict_enum


class JudgeVerdict(Base):
    """Rule-based Judge result. Exactly one of proposal_id / chat_message_id is set."""
    __tablename__ = "judge_verdicts"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(proposal_id, chat_message_id) = 1",
            name="ck_judge_verdicts_one_owner"
        ),
    )

    id = uuid_pk()
    proposal_id = uuid_fk("hazop_proposals.id", index=True)
    chat_message_id = uuid_fk("chat_messages.id", index=True)
    verdict = Column(verdict_enum, nullable=False)
    unknown_entities = Column(ARRAY(Text))
    unresolved_citations = Column(ARRAY(Text))
    actuation_wording = Column(Boolean, nullable=False, default=False, server_default=sa_text("false"))
    reason = Column(Text)
    checked_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<JudgeVerdict(id={self.id}, verdict={self.verdict})>"
