"""PromptTemplate SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Column, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_pk
from app.models.enums import agent_name_enum


class PromptTemplate(Base):
    """Versioned prompt for an agent, e.g. redteam.v1."""
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("agent", "version", name="uq_prompt_templates_agent_version"),
    )

    id = uuid_pk()
    agent = Column(agent_name_enum, nullable=False)
    version = Column(String(16), nullable=False, comment="redteam.v1")
    template = Column(Text, nullable=False)
    output_schema = Column(JSONB, comment="JSON schema the output must validate against")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<PromptTemplate(agent={self.agent}, version={self.version})>"
