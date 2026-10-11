"""AssetLink SQLAlchemy model (plant model group)."""
from sqlalchemy import Column, String
from config.databases.postgresql import Base
from app.models.columns import uuid_fk


class AssetLink(Base):
    """Edge of the asset graph, e.g. P-101 suction_from S-101; PSV-201 protects V-201."""
    __tablename__ = "asset_links"

    from_asset_id = uuid_fk("assets.id", nullable=False, primary_key=True)
    to_asset_id = uuid_fk("assets.id", nullable=False, primary_key=True, index=True)
    relation = Column(
        String(32),
        primary_key=True,
        comment="suction_from, protects, controls, feeds"
    )

    def __repr__(self) -> str:
        return f"<AssetLink({self.from_asset_id} {self.relation} {self.to_asset_id})>"
