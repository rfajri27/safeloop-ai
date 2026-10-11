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
from app.utils.response import response_error


class DocumentService:
    """
    Service for documents and chunks.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize DocumentService with a DB session."""
        self.db = db

    async def get_documents(
        self,
        doc_type: Optional[str] = None,
        asset_tag: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List indexed documents with metadata."""
        return response_error("Not implemented", code=501)

    async def get_document(self, doc_code: str) -> JSONResponse:
        """Return {doc_code, title, type, revision, effective_date, asset_tags, is_synthetic, chunk_count}."""
        return response_error("Not implemented", code=501)

    async def get_chunk(self, chunk_id: str) -> JSONResponse:
        """Return {chunk_id, doc_code, title, section, page, text}; text is data, never HTML."""
        return response_error("Not implemented", code=501)
