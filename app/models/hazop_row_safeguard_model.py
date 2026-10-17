"""HazopRowSafeguard SQLAlchemy model (HAZOP & risk group)."""
from sqlalchemy import Boolean, Column
from sqlalchemy import text as sa_text
from config.databases.postgresql import Base
from app.models.columns import uuid_fk


class HazopRowSafeguard(Base):
    """Safeguard credited (or not) against a HAZOP row version."""
    __tablename__ = "hazop_row_safeguards"

    hazop_row_id = uuid_fk("hazop_rows.id", nullable=False, primary_key=True)
    safeguard_id = uuid_fk("safeguards.id", nullable=False, primary_key=True, index=True)
    credited = Column(Boolean, nullable=False, default=True, server_default=sa_text("true"))

    def __repr__(self) -> str:
        return f"<HazopRowSafeguard(row={self.hazop_row_id}, safeguard={self.safeguard_id})>"
