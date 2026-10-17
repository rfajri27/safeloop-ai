"""In-process response cache that stays exact under live data ingestion.

A cached response remembers which tables it read (captured from the SQL it ran)
and each table's version when it started computing. Every committed INSERT,
UPDATE or DELETE bumps the version of the table it wrote, so the next request
for an affected response recomputes. A replay tick writes sensor_readings and
health_assessments, which invalidates the overview and asset views but leaves
the HAZOP register, matrix and audit log cached until a band change.

Versions are bumped after the commit returns, so a response computed before
the bump is dropped and one computed after it sees the committed data.

State that lives only in memory (the replay clock in replay_manager) is a
pseudo-table: readers call depends_on(REPLAY_STATE), writers call bump().

One Uvicorn worker is assumed (spec Section 12). Writes from other processes
(seed scripts, psql) are not seen; MAX_AGE_SECONDS bounds how long they hide.

Usage:
    @live_cached
    async def get_overview(self, unit_code: str) -> JSONResponse: ...
"""
import re
import time
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Optional
from fastapi.responses import JSONResponse, Response
from sqlalchemy import event
from sqlalchemy.orm import Session
from config.databases.postgresql import engine

MAX_ENTRIES = 256
MAX_AGE_SECONDS = 60
REPLAY_STATE = "replay_state"

_WRITE_SQL = re.compile(r'^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?(\w+)', re.IGNORECASE)
_READ_SQL = re.compile(r'\b(?:FROM|JOIN)\s+"?(\w+)', re.IGNORECASE)
_DIRTY = "live_cache.dirty_tables"
_TXN_INFOS = "live_cache.txn_infos"

_versions: dict[str, int] = {}
_reads: ContextVar[Optional[set[str]]] = ContextVar("live_cache_reads", default=None)


@dataclass
class _Entry:
    at: float
    deps: dict[str, int]
    body: bytes


_entries: "OrderedDict[str, _Entry]" = OrderedDict()


def bump(*sources: str) -> None:
    """Mark tables (or pseudo-tables) changed; responses that read them recompute."""
    for source in sources:
        _versions[source] = _versions.get(source, 0) + 1


def depends_on(*sources: str) -> None:
    """Record a non-SQL dependency of the response being computed (no-op outside one)."""
    reads = _reads.get()
    if reads is not None:
        reads.update(sources)


def clear() -> None:
    _entries.clear()


# ---------------------------------------------------------------- write/read capture

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _capture(conn, cursor, statement, parameters, context, executemany):
    write = _WRITE_SQL.match(statement)
    if write:
        conn.info.setdefault(_DIRTY, set()).add(write.group(1).lower())
    else:
        depends_on(*(table.lower() for table in _READ_SQL.findall(statement)))


@event.listens_for(engine.sync_engine, "rollback")
def _discard(conn):
    conn.info.pop(_DIRTY, None)


@event.listens_for(Session, "after_begin")
def _remember_connection(session, transaction, connection):
    session.info.setdefault(_TXN_INFOS, []).append(connection.info)


@event.listens_for(Session, "after_commit")
def _publish_writes(session):
    for info in session.info.pop(_TXN_INFOS, ()):
        bump(*info.pop(_DIRTY, ()))


@event.listens_for(Session, "after_rollback")
def _forget_connections(session):
    session.info.pop(_TXN_INFOS, None)


# ------------------------------------------------------------------------- caching

def _fresh(entry: _Entry) -> bool:
    if time.monotonic() - entry.at > MAX_AGE_SECONDS:
        return False
    return all(_versions.get(source, 0) == version for source, version in entry.deps.items())


def live_cached(fn):
    """Cache a service method's 200 JSON response, keyed by its arguments.

    Only for responses that are the same for every user and depend on nothing
    but the database and declared depends_on() sources (no wall clock).
    """
    @wraps(fn)
    async def wrapper(self, *args, **kwargs):
        key = f"{fn.__qualname__}:{args!r}:{sorted(kwargs.items())!r}"
        entry = _entries.get(key)
        if entry and _fresh(entry):
            _entries.move_to_end(key)
            return Response(entry.body, media_type="application/json")

        snapshot = dict(_versions)
        reads: set[str] = set()
        token = _reads.set(reads)
        try:
            response = await fn(self, *args, **kwargs)
        finally:
            _reads.reset(token)

        # No captured reads means capture did not work for this path: never cache blind.
        if type(response) is JSONResponse and response.status_code == 200 and reads:
            _entries[key] = _Entry(time.monotonic(), {t: snapshot.get(t, 0) for t in reads}, response.body)
            _entries.move_to_end(key)
            while len(_entries) > MAX_ENTRIES:
                _entries.popitem(last=False)
        return response
    return wrapper
