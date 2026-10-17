"""Site SQLAlchemy model (plant model group)."""
from sqlalchemy import Column, String
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_pk
from app.models.enums import DataOrigin, data_origin_enum


class Site(Base):
    """A plant site, e.g. DEMO-SITE."""
    __tablename__ = "sites"

    id = uuid_pk()
    code = Column(String(32), nullable=False, unique=True, comment="e.g. DEMO-SITE")
    name = Column(String(200), nullable=False)
    origin = Column(
        data_origin_enum,
        nullable=False,
        default=DataOrigin.SYNTHETIC,
        server_default=DataOrigin.SYNTHETIC.value
    )
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<Site(code={self.code})>"
