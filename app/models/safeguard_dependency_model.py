"""SafeguardDependency SQLAlchemy model (HAZOP & risk group)."""
from config.databases.postgresql import Base
from app.models.columns import uuid_fk


class SafeguardDependency(Base):
    """
    Asset a safeguard depends on, e.g. P-101B auto-start depends on P-101B and FT-201.

    Drives rule R-S-01: a credited safeguard loses credit when an asset it
    depends on is Degraded or Critical.
    """
    __tablename__ = "safeguard_dependencies"

    safeguard_id = uuid_fk("safeguards.id", nullable=False, primary_key=True)
    asset_id = uuid_fk("assets.id", nullable=False, primary_key=True, index=True)

    def __repr__(self) -> str:
        return f"<SafeguardDependency(safeguard={self.safeguard_id}, asset={self.asset_id})>"
