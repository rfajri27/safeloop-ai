"""Document API routes for the knowledge corpus.

Endpoints:
    GET /documents                  - Indexed documents and metadata
    GET /documents/{doc_code}       - One document with its chunks
    GET /document-chunks/{chunk_id} - One cited passage for the source panel
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import get_db
from app.middleware.auth_middleware import get_current_user
from app.services.document_service import DocumentService
from app.schemas.common_schema import DEFAULT_LIMIT, MAX_LIMIT, DocType

router = APIRouter(tags=["Knowledge"], dependencies=[Depends(get_current_user)])


def get_document_service(db: AsyncSession = Depends(get_db)) -> DocumentService:
    """Dependency: Create DocumentService."""
    return DocumentService(db)


@router.get("/documents", summary="List indexed documents")
async def get_documents(
    type: Optional[DocType] = Query(None, description="Document type filter"),
    asset_tag: Optional[str] = Query(None, description="Only documents linked to this asset"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description="Maximum records to return"),
    service: DocumentService = Depends(get_document_service)
):
    """Indexed documents and metadata."""
    return await service.get_documents(type, asset_tag, skip, limit)


@router.get("/documents/{doc_code}", summary="Get a document by code")
async def get_document(
    doc_code: str,
    service: DocumentService = Depends(get_document_service)
):
    """One document with its metadata and chunk count."""
    return await service.get_document(doc_code)


@router.get("/document-chunks/{chunk_id}", summary="Get a document chunk")
async def get_chunk(
    chunk_id: str,
    service: DocumentService = Depends(get_document_service)
):
    """One cited passage for the source panel."""
    return await service.get_chunk(chunk_id)
