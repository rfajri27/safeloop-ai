"""GoldenItem SQLAlchemy model (evaluation group)."""
from sqlalchemy import CheckConstraint, Column, String
from sqlalchemy.dialects.postgresql import JSONB
from config.databases.postgresql import Base
from app.models.columns import timestamp_now, uuid_fk, uuid_pk


class GoldenItem(Base):
    """A labelled evaluation item. Test split items are never used in prompts."""
    __tablename__ = "golden_items"
    __table_args__ = (
        CheckConstraint("split IN ('train', 'test')", name="ck_golden_items_split"),
    )

    id = uuid_pk()
    set_name = Column(
        String(32),
        nullable=False,
        index=True,
        comment="hazop_rows, qa, out_of_corpus, guardrail, rca"
    )
    split = Column(String(8), nullable=False, default="test", server_default="test", comment="train / test")
    input = Column(JSONB, nullable=False)
    expected = Column(JSONB, nullable=False)
    authored_by = uuid_fk("users.id")
    reviewed_by = uuid_fk("users.id")
    created_at = timestamp_now()

    def __repr__(self) -> str:
        return f"<GoldenItem(id={self.id}, set={self.set_name})>"
