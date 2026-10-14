"""Live unit events on a Redis stream (spec Section 5).

Producers (replay task, approval decisions) XADD to `unit:{code}:events`, keeping
the last 1,000 entries. GET /units/{code}/events/stream reads it with XREAD; the
Redis entry id is the SSE `id`, so a client reconnecting with Last-Event-ID gets
every entry after it.
"""
import json
import logging
from typing import Any, AsyncIterator, Optional
from config.databases.redis import redis_client

STREAM_MAXLEN = 1000
READ_BLOCK_MS = 3000   # under the client's 5 s socket timeout
logger = logging.getLogger(__name__)


def stream_key(unit_code: str) -> str:
    return f"unit:{unit_code}:events"


async def publish(unit_code: str, events: list[tuple[str, dict[str, Any]]]) -> None:
    """Append CUSTOM events (name, value) in order. Failures are logged, never raised:
    the database already holds the record, and the UI also polls."""
    if not events:
        return
    try:
        pipe = redis_client.pipeline(transaction=False)
        for name, value in events:
            pipe.xadd(
                stream_key(unit_code),
                {"name": name, "value": json.dumps(value, default=str)},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        await pipe.execute()
    except Exception:
        logger.exception("Could not publish %d unit events", len(events))


async def latest_id(unit_code: str) -> str:
    """Id of the newest entry, or 0-0 for an empty stream."""
    entries = await redis_client.xrevrange(stream_key(unit_code), count=1)
    return entries[0][0] if entries else "0-0"


async def read(unit_code: str, after_id: str) -> list[tuple[str, str, Any]]:
    """Entries after `after_id`, waiting up to READ_BLOCK_MS: [(id, name, value)]."""
    result = await redis_client.xread({stream_key(unit_code): after_id}, count=100, block=READ_BLOCK_MS)
    entries = []
    for _key, items in result or []:
        for entry_id, fields in items:
            try:
                value = json.loads(fields.get("value", "null"))
            except ValueError:
                value = None
            entries.append((entry_id, fields.get("name", "unknown"), value))
    return entries


async def follow(unit_code: str, last_event_id: Optional[str]) -> AsyncIterator[list[tuple[str, str, Any]]]:
    """Yield batches of new entries forever (an empty batch on each idle wait)."""
    cursor = last_event_id or await latest_id(unit_code)
    while True:
        batch = await read(unit_code, cursor)
        if batch:
            cursor = batch[-1][0]
        yield batch
