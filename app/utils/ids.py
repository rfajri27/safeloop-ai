"""Identifier helpers."""
import uuid
from typing import Any


def is_uuid(value: Any) -> bool:
    """True for a UUID string. Path ids are checked first so a malformed id is a 404, not a DB error."""
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def new_id() -> str:
    """A new UUID string (rows whose id is needed before flush)."""
    return str(uuid.uuid4())
