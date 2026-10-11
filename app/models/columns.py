"""Column helpers shared by SafeLoop models.

DBML conventions: UUID primary keys (gen_random_uuid()), timestamptz in UTC.
UUIDs are handled as strings (as_uuid=False), matching the rest of the app.
Python-side defaults are set too, so ids and timestamps are known right after
`session.add()` without a refresh.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID


def utcnow() -> datetime:
    """Current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def uuid_pk() -> Column:
    """UUID primary key with DB and Python defaults."""
    return Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID primary key"
    )


def uuid_fk(
    target: str,
    nullable: bool = True,
    primary_key: bool = False,
    index: bool = False,
    comment: str = None
) -> Column:
    """UUID foreign key column, e.g. uuid_fk("assets.id", nullable=False)."""
    return Column(
        UUID(as_uuid=False),
        ForeignKey(target),
        nullable=nullable,
        primary_key=primary_key,
        index=index,
        comment=comment
    )


def timestamp_now(comment: str = None) -> Column:
    """NOT NULL timestamptz defaulting to now()."""
    return Column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        comment=comment
    )
