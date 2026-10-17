"""AgentRun SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import agent_name_enum


class AgentRun(Base):
    """One agent or engine invocation; system of record for model usage."""
    __tablename__ = "agent_runs"

    id = uuid_pk()
    agent = Column(agent_name_enum, nullable=False)
    prompt_template_id = uuid_fk("prompt_templates.id")
    model_id = Column(String(64), comment="Null for rule-based components")
    model_endpoint = Column(String(32), comment="cloud_api / vllm")
    input = Column(JSONB, nullable=False)
    output = Column(JSONB)
    schema_valid = Column(Boolean)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    latency_ms = Column(Integer)
    error = Column(Text)
    hazop_row_id = uuid_fk("hazop_rows.id", index=True, comment="Row the Red Team was run on")
    chat_message_id = uuid_fk("chat_messages.id", index=True)
    started_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<AgentRun(id={self.id}, agent={self.agent})>"
