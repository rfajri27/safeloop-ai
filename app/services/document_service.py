"""Document service for the indexed knowledge corpus.

Endpoints served:
    GET /documents                 - Indexed documents and metadata
    GET /documents/{doc_code}      - One document with its chunks
    GET /document-chunks/{chunk_id} - One cited passage for the source panel

Reads: documents, document_assets, document_chunks
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.corpus import headings_in, section_title
from app.models.document_model import Document
from app.models.enums import DataOrigin
from app.repositories.document_asset_repository import DocumentAssetRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.utils.ids import is_uuid
from app.utils.response import response_error, response_success


class DocumentService:
    """
    Service for documents and chunks.

    REQUEST-SCOPED: Created per request with injected session.
    Chunk text is returned as plain strings; the UI renders it as text, never HTML.
    """

    def __init__(self, db: AsyncSession):
        """Initialize DocumentService with a DB session."""
        self.db = db
        self.docs = DocumentRepository(db)
        self.chunks = DocumentChunkRepository(db)
        self.links = DocumentAssetRepository(db)

    async def _summary(self, doc: Document) -> dict:
        return {
            "doc_code": doc.doc_code,
            "title": doc.title,
            "type": doc.type.value,
            "revision": doc.revision,
            "effective_date": doc.effective_date,
            "asset_tags": list(await self.links.list_asset_tags(doc.id)),
            "is_current": doc.is_current,
            "is_synthetic": doc.origin == DataOrigin.SYNTHETIC,
            "chunk_count": await self.chunks.count_by_document(doc.id),
        }

    async def get_documents(
        self,
        doc_type: Optional[str] = None,
        asset_tag: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List indexed documents with metadata."""
        docs = await self.docs.list_filtered(doc_type, asset_tag, current_only=True, skip=skip, limit=limit)
        total = await self.docs.count_filtered(doc_type, asset_tag, current_only=True)
        return response_success(
            [await self._summary(doc) for doc in docs],
            metadata={"total": total, "skip": skip, "limit": limit},
        )

    async def get_document(self, doc_code: str) -> JSONResponse:
        """Return {doc_code, title, type, revision, effective_date, asset_tags, is_synthetic, chunk_count}."""
        doc = await self.docs.get_by_code(doc_code)
        if not doc:
            return response_error(f"Document {doc_code} not found", code=404)
        chunks = await self.chunks.list_by_document(doc.id)
        revisions = await self.docs.list_revisions(doc_code)
        return response_success({
            **await self._summary(doc),
            "storage_uri": doc.storage_uri,
            "revisions": [
                {"revision": r.revision, "is_current": r.is_current, "effective_date": r.effective_date}
                for r in revisions
            ],
            "chunks": [
                {
                    "chunk_id": c.id,
                    "chunk_index": c.chunk_index,
                    "section": c.section,
                    "title": _title(c.text),
                    "page": c.page,
                    "token_count": c.token_count,
                    "text": c.text,
                }
                for c in chunks
            ],
        })

    async def get_chunk(self, chunk_id: str) -> JSONResponse:
        """Return {chunk_id, doc_code, title, section, page, text}; text is data, never HTML."""
        found = await self.chunks.get_with_document(chunk_id) if is_uuid(chunk_id) else None
        if not found:
            return response_error(f"Document chunk {chunk_id} not found", code=404)
        chunk, doc = found
        return response_success({
            "chunk_id": chunk.id,
            "doc_code": doc.doc_code,
            "title": doc.title,
            "section": chunk.section,
            "section_title": _title(chunk.text),
            "page": chunk.page,
            "text": chunk.text,
            "revision": doc.revision,
            "is_current": doc.is_current,
            "is_synthetic": doc.origin == DataOrigin.SYNTHETIC,
        })


def _title(text: str) -> Optional[str]:
    headings = headings_in(text)
    return section_title(headings[0]) if headings else None
