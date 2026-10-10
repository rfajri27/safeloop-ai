"""Example User SQLAlchemy model.

This module defines the ExampleUser database model for tutorial purposes.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from config.databases.postgresql import Base


class ExampleUser(Base):
    """
    Example User model for authentication and user management.

    Attributes:
        id: UUID primary key
        name: User's display name
        email: Unique email address
        role: User role (user, admin, superadmin)
        status: Account status (1=active, 0=inactive/deleted)
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "example_users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key"
    )
    name = Column(
        String(100),
        nullable=False,
        comment="User display name"
    )
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique email address"
    )
    role = Column(
        String(20),
        nullable=False,
        default="user",
        comment="User role: user, admin, superadmin"
    )
    status = Column(
        Integer,
        nullable=False,
        default=1,
        comment="1=active, 0=inactive/deleted"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Account creation timestamp"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Last update timestamp"
    )

    def __repr__(self) -> str:
        return f"<ExampleUser(id={self.id}, email={self.email}, role={self.role})>"
