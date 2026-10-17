"""DocumentChunk SQLAlchemy model (knowledge base group)."""
from sqlalchemy import Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk


class DocumentChunk(Base):
    """A retrievable passage of a document, keyed in the vector store (Chroma) by vector_id."""
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
    )

    id = uuid_pk()
    document_id = uuid_fk("documents.id", nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    page = Column(Integer)
    section = Column(String(200))
    token_count = Column(Integer)
    # Column keeps its original name; it is the Chroma record id
    vector_id = Column("qdrant_point_id", UUID(as_uuid=False), nullable=False, unique=True)
    embedding_model = Column(String(64), nullable=False)

    def __repr__(self) -> str:
        return f"<DocumentChunk(document={self.document_id}, index={self.chunk_index})>"
