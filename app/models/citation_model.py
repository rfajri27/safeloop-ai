"""Citation SQLAlchemy model (AI & governance group)."""
from sqlalchemy import Boolean, CheckConstraint, Column, SmallInteger, String
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import citation_target_enum


class Citation(Base):
    """
    Polymorphic evidence link.

    One owner (chat message / proposal / approval item / re-score) and one
    target (chunk / asset / tag window / HAZOP row) per row.
    """
    __tablename__ = "citations"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(chat_message_id, proposal_id, approval_item_id, rescore_id) = 1",
            name="ck_citations_one_owner"
        ),
    )

    id = uuid_pk()
    target_type = Column(citation_target_enum, nullable=False)
    chunk_id = uuid_fk("document_chunks.id")
    asset_id = uuid_fk("assets.id")
    tag_id = uuid_fk("sensor_tags.id")
    hour_from = Column(SmallInteger)
    hour_to = Column(SmallInteger)
    hazop_row_id = uuid_fk("hazop_rows.id")
    resolved = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa_text("true"),
        comment="False = cited id did not resolve"
    )
    raw_ref = Column(String(128), comment="Reference exactly as returned by the model")
    chat_message_id = uuid_fk("chat_messages.id", index=True)
    proposal_id = uuid_fk("hazop_proposals.id", index=True)
    approval_item_id = uuid_fk("approval_items.id", index=True)
    rescore_id = uuid_fk("risk_rescores.id", index=True)

    def __repr__(self) -> str:
        return f"<Citation(id={self.id}, target_type={self.target_type})>"
