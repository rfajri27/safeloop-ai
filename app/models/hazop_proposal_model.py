"""HazopProposal SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import ARRAY
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import guide_word_enum, hazop_param_enum


class HazopProposal(Base):
    """A Red Team proposal for a HAZOP row, before Judge and human approval."""
    __tablename__ = "hazop_proposals"

    id = uuid_pk()
    agent_run_id = uuid_fk("agent_runs.id", nullable=False, index=True)
    target_row_id = uuid_fk("hazop_rows.id", nullable=False, index=True)
    guide_word = Column(guide_word_enum, nullable=False)
    parameter = Column(hazop_param_enum, nullable=False)
    deviation = Column(Text, nullable=False)
    cause = Column(Text, nullable=False)
    consequence = Column(Text)
    proposed_safeguards = Column(ARRAY(Text), comment="As returned by the model, before grounding")
    recommendation = Column(Text)
    resulting_row_id = uuid_fk("hazop_rows.id", comment="New row version created on approval")

    def __repr__(self) -> str:
        return f"<HazopProposal(id={self.id}, target_row={self.target_row_id})>"
