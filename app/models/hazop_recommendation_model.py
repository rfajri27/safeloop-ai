"""HazopRecommendation SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import Column, Text
from config.databases.postgresql import Base
from app.models.columns import uuid_fk, uuid_pk
from app.models.enums import user_role_enum


class HazopRecommendation(Base):
    """A recommendation attached to a HAZOP row version."""
    __tablename__ = "hazop_recommendations"

    id = uuid_pk()
    hazop_row_id = uuid_fk("hazop_rows.id", nullable=False, index=True)
    text = Column(Text, nullable=False)
    owner_role = Column(user_role_enum)

    def __repr__(self) -> str:
        return f"<HazopRecommendation(hazop_row_id={self.hazop_row_id})>"
