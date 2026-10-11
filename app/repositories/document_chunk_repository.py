"""Repository for DocumentChunk entity."""
from typing import Optional, Sequence
from sqlalchemy import delete, func, select
from app.repositories.base import BaseRepository
from app.models.document_chunk_model import DocumentChunk
from app.models.document_model import Document


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Repository for DocumentChunk queries."""
    model_class = DocumentChunk

    async def get_with_document(self, chunk_id: str) -> Optional[tuple[DocumentChunk, Document]]:
        """(chunk, document) for the source panel."""
        result = await self.session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id == chunk_id)
        )
        return result.tuples().one_or_none()

    async def list_with_documents(self, chunk_ids: Sequence[str]) -> Sequence[tuple[DocumentChunk, Document]]:
        """(chunk, document) for retrieved or cited chunks."""
        if not chunk_ids:
            return []
        result = await self.session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(chunk_ids))
        )
        return result.tuples().all()

    async def list_by_document(self, document_id: str) -> Sequence[DocumentChunk]:
        """Chunks of a document in order."""
        result = await self.session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return result.scalars().all()

    async def count_by_document(self, document_id: str) -> int:
        """Number of chunks in a document."""
        result = await self.session.execute(
            select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        return result.scalar() or 0

    async def find_current_by_section(self, doc_code: str, section: Optional[str] = None) -> Sequence[DocumentChunk]:
        """Chunks of a current document, optionally matching a section (Judge `doc:CODE#section`)."""
        query = (
            select(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.doc_code == doc_code, Document.is_current.is_(True))
        )
        if section:
            query = query.where(DocumentChunk.section.ilike(f"%{section}%"))
        result = await self.session.execute(query.order_by(DocumentChunk.chunk_index))
        return result.scalars().all()

    async def delete_by_document(self, document_id: str) -> None:
        """Remove a document's chunks before re-ingesting it (flush only)."""
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await self.session.flush()
