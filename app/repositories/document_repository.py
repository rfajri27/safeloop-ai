"""Repository for Document entity."""
from typing import Optional, Sequence
from sqlalchemy import func, select
from app.repositories.base import BaseRepository
from app.models.asset_model import Asset
from app.models.document_asset_model import DocumentAsset
from app.models.document_model import Document
from app.models.enums import DocType


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document queries."""
    model_class = Document

    def _filtered(
        self,
        query,
        doc_type: Optional[DocType],
        asset_tag: Optional[str],
        current_only: bool
    ):
        if doc_type:
            query = query.where(Document.type == doc_type)
        if current_only:
            query = query.where(Document.is_current.is_(True))
        if asset_tag:
            query = query.where(
                Document.id.in_(
                    select(DocumentAsset.document_id)
                    .join(Asset, Asset.id == DocumentAsset.asset_id)
                    .where(Asset.tag == asset_tag)
                )
            )
        return query

    async def get_by_code(self, doc_code: str) -> Optional[Document]:
        """Get a document by code, e.g. SOP-P101-02: the current revision, else the newest."""
        result = await self.session.execute(
            select(Document)
            .where(Document.doc_code == doc_code)
            .order_by(Document.is_current.desc(), Document.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_code_revision(self, doc_code: str, revision: str) -> Optional[Document]:
        """One revision of a document (ingestion upsert key)."""
        result = await self.session.execute(
            select(Document).where(Document.doc_code == doc_code, Document.revision == revision)
        )
        return result.scalar_one_or_none()

    async def list_revisions(self, doc_code: str) -> Sequence[Document]:
        """Every revision of a document, current first."""
        result = await self.session.execute(
            select(Document)
            .where(Document.doc_code == doc_code)
            .order_by(Document.is_current.desc(), Document.revision.desc())
        )
        return result.scalars().all()

    async def list_filtered(
        self,
        doc_type: Optional[DocType] = None,
        asset_tag: Optional[str] = None,
        current_only: bool = True,
        skip: int = 0,
        limit: int = 50
    ) -> Sequence[Document]:
        """List documents ordered by code."""
        query = self._filtered(select(Document), doc_type, asset_tag, current_only)
        result = await self.session.execute(query.order_by(Document.doc_code).offset(skip).limit(limit))
        return result.scalars().all()

    async def count_filtered(
        self,
        doc_type: Optional[DocType] = None,
        asset_tag: Optional[str] = None,
        current_only: bool = True
    ) -> int:
        """Count documents with the same filters as list()."""
        query = self._filtered(select(func.count()).select_from(Document), doc_type, asset_tag, current_only)
        result = await self.session.execute(query)
        return result.scalar() or 0
