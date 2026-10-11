"""DocumentAsset SQLAlchemy model (knowledge base group)."""
from config.databases.postgresql import Base
from app.models.columns import uuid_fk


class DocumentAsset(Base):
    """Link between a document and an asset it covers."""
    __tablename__ = "document_assets"

    document_id = uuid_fk("documents.id", nullable=False, primary_key=True)
    asset_id = uuid_fk("assets.id", nullable=False, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<DocumentAsset(document={self.document_id}, asset={self.asset_id})>"
