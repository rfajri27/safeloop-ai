"""Repository for DocumentAsset entity (document <-> asset)."""
from typing import Sequence
from sqlalchemy import delete, select
from app.repositories.base import BaseRepository
from app.models.asset_model import Asset
from app.models.document_asset_model import DocumentAsset


class DocumentAssetRepository(BaseRepository[DocumentAsset]):
    """Repository for DocumentAsset queries. Composite key: no get_by_id."""
    model_class = DocumentAsset

    async def list_asset_tags(self, document_id: str) -> Sequence[str]:
        """Asset tags a document covers, ordered by tag."""
        result = await self.session.execute(
            select(Asset.tag)
            .join(DocumentAsset, DocumentAsset.asset_id == Asset.id)
            .where(DocumentAsset.document_id == document_id)
            .order_by(Asset.tag)
        )
        return result.scalars().all()

    async def list_document_ids(self, asset_id: str) -> Sequence[str]:
        """Documents linked to an asset."""
        result = await self.session.execute(
            select(DocumentAsset.document_id).where(DocumentAsset.asset_id == asset_id)
        )
        return result.scalars().all()

    async def replace_for_document(self, document_id: str, asset_ids: Sequence[str]) -> None:
        """Replace a document's asset links (flush only; part of ingestion)."""
        await self.session.execute(delete(DocumentAsset).where(DocumentAsset.document_id == document_id))
        self.session.add_all(DocumentAsset(document_id=document_id, asset_id=a) for a in asset_ids)
        await self.session.flush()
