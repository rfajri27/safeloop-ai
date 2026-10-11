"""ChatSession SQLAlchemy model (AI & governance group)."""
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class ChatSession(Base):
    """A knowledge assistant session; its id is also the LangGraph thread_id."""
    __tablename__ = "chat_sessions"

    id = uuid_pk()
    user_id = uuid_fk("users.id", nullable=False, index=True)
    started_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id})>"
