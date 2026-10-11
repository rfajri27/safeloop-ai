"""Document SQLAlchemy model (knowledge base group)."""
from sqlalchemy import Boolean, Column, Date, String, Text, UniqueConstraint
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk
from app.models.enums import DataOrigin, data_origin_enum, doc_type_enum


class Document(Base):
    """Source document metadata; vectors live in Qdrant."""
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("doc_code", "revision", name="uq_documents_doc_code_revision"),
    )

    id = uuid_pk()
    doc_code = Column(
        String(32),
        nullable=False,
        comment="MAN-P101, SOP-P101-02, INC-2024-017"
    )
    title = Column(String(300), nullable=False)
    type = Column(doc_type_enum, nullable=False)
    revision = Column(String(16), nullable=False, default="A", server_default="A")
    effective_date = Column(Date)
    is_current = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sa_text("true"),
        comment="Superseded revisions excluded from retrieval"
    )
    origin = Column(
        data_origin_enum,
        nullable=False,
        default=DataOrigin.SYNTHETIC,
        server_default=DataOrigin.SYNTHETIC.value
    )
    generator_model = Column(String(64), comment="Set for LLM-generated synthetic documents")
    reviewed_by = uuid_fk("users.id")
    storage_uri = Column(Text, comment="Object-store path of the source file")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<Document(doc_code={self.doc_code}, revision={self.revision})>"
