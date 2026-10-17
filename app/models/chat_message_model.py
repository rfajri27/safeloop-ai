"""ChatMessage SQLAlchemy model (AI & governance group)."""
from sqlalchemy import CheckConstraint, Column, Index, String, Text
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class ChatMessage(Base):
    """A user question or an assistant answer in a chat session."""
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
    )

    id = uuid_pk()
    session_id = uuid_fk("chat_sessions.id", nullable=False)
    role = Column(String(10), nullable=False, comment="user / assistant")
    content = Column(Text, nullable=False)
    kind = Column(String(16), comment="answer / insufficient / refused / cancelled")
    confidence = Column(String(8))
    guardrail_reason = Column(String(64), comment="Set when refused before any model call")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role}, kind={self.kind})>"
