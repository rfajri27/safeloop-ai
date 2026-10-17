"""Repository for DocumentChunk entity."""
from typing import Optional, Sequence
from sqlalchemy import case, delete, func, select
from app.repositories.base import BaseRepository
from app.models.document_chunk_model import DocumentChunk
from app.models.document_model import Document
from app.models.enums import DocType


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

    async def find_current(
        self,
        doc_type: Optional[DocType] = None,
        section: Optional[str] = None,
        text_contains: Optional[str] = None,
        limit: int = 1
    ) -> Sequence[tuple[DocumentChunk, Document]]:
        """(chunk, document) of current documents by exact section id and/or text, manuals first."""
        query = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_current.is_(True))
        )
        if doc_type:
            query = query.where(Document.type == doc_type)
        if section:
            query = query.where(DocumentChunk.section == section)
        if text_contains:
            query = query.where(DocumentChunk.text.contains(text_contains))
        manuals_first = case((Document.type == DocType.MANUAL, 0), else_=1)
        result = await self.session.execute(
            query.order_by(manuals_first, Document.doc_code, DocumentChunk.chunk_index).limit(limit)
        )
        return result.tuples().all()

    async def list_current_with_documents(self) -> Sequence[tuple[DocumentChunk, Document]]:
        """(chunk, document) for every chunk of a current document (retrieval index, Judge)."""
        result = await self.session.execute(
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.is_current.is_(True))
            .order_by(Document.doc_code, DocumentChunk.chunk_index)
        )
        return result.tuples().all()

    async def get_by_document_index(self, document_id: str, chunk_index: int) -> Optional[DocumentChunk]:
        """One chunk by position (ingestion upsert)."""
        result = await self.session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id, DocumentChunk.chunk_index == chunk_index
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_document(self, document_id: str) -> None:
        """Remove a document's chunks before re-ingesting it (flush only)."""
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await self.session.flush()
