"""User SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Boolean, Column, String
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_pk
from app.models.enums import user_role_enum


class User(Base):
    """A SafeLoop user. MVP users are seeded demo users (no password store)."""
    __tablename__ = "users"

    id = uuid_pk()
    handle = Column(
        String(32),
        nullable=False,
        unique=True,
        comment="Demo login handle: rina, dimas, agus, auditor, admin"
    )
    display_name = Column(String(120), nullable=False)
    email = Column(String(200), unique=True)
    role = Column(user_role_enum, nullable=False)
    is_demo = Column(Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<User(handle={self.handle}, role={self.role})>"
