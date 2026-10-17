"""Chroma collection for chunk vectors: the dense half of hybrid retrieval (spec Section 10).

Embedded (persistent, under CHROMA_PERSIST_DIR) unless CHROMA_HOST is set,
then a Chroma server over HTTP. Collection `unit100_chunks`: cosine HNSW over
`gemini-embedding-001` vectors (768 dimensions); record id =
document_chunks.vector_id; metadata chunk_id, doc_code, doc_type, asset_tags,
revision, is_current, is_synthetic, section. The collection remembers its
embedding model and dimension and is recreated when either changes.

Chroma's own sparse (BM25) index is Chroma Cloud only, so BM25 is computed
in-process by the retrieval index and fused with these results there.
The client is synchronous; every call runs in a worker thread.
"""
import asyncio
import threading
from typing import Any, Callable, Optional, Sequence, TypeVar
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import env

T = TypeVar("T")

_client: Optional[chromadb.ClientAPI] = None
_collection: Optional[chromadb.Collection] = None
_lock = threading.Lock()


def describe() -> str:
    """Where the vectors live, for ingest responses."""
    where = f"{env.chroma_host}:{env.chroma_port}" if env.chroma_host else str(env.chroma_persist_path)
    return f"chroma:{env.chroma_collection}@{where}"


def _make_client() -> chromadb.ClientAPI:
    settings = ChromaSettings(anonymized_telemetry=False)
    if env.chroma_host:
        return chromadb.HttpClient(host=env.chroma_host, port=env.chroma_port, ssl=env.chroma_ssl, settings=settings)
    return chromadb.PersistentClient(path=str(env.chroma_persist_path), settings=settings)


def _get_collection() -> chromadb.Collection:
    """The chunk collection, created on first use; recreated if the embedding model or dimension changed."""
    global _client, _collection
    with _lock:
        if _collection is not None:
            return _collection
        _client = _client or _make_client()
        wanted = {"embedding_model": env.gemini_embedding_model, "embedding_dim": env.embedding_dim}
        options = {"configuration": {"hnsw": {"space": "cosine"}}, "metadata": wanted, "embedding_function": None}
        collection = _client.get_or_create_collection(env.chroma_collection, **options)
        stored = collection.metadata or {}
        if any(stored.get(key) != value for key, value in wanted.items()):
            _client.delete_collection(env.chroma_collection)
            collection = _client.create_collection(env.chroma_collection, **options)
        _collection = collection
        return collection


async def _run(fn: Callable[[chromadb.Collection], T]) -> T:
    """Run fn(collection) in a thread; drop the cached handle on failure so the next call reconnects."""
    global _collection

    def call() -> T:
        return fn(_get_collection())

    try:
        return await asyncio.to_thread(call)
    except Exception:
        _collection = None
        raise


async def list_ids() -> set[str]:
    """Every record id in the collection."""
    return set(await _run(lambda c: c.get(include=[])["ids"]))


async def upsert(records: Sequence[dict[str, Any]]) -> None:
    """records: [{id, vector, document, metadata}]; empty-list metadata values are dropped (Chroma rejects them)."""
    if not records:
        return

    def write(collection: chromadb.Collection) -> None:
        batch_size = _client.get_max_batch_size()
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]
            collection.upsert(
                ids=[r["id"] for r in batch],
                embeddings=[r["vector"] for r in batch],
                documents=[r["document"] for r in batch],
                metadatas=[{k: v for k, v in r["metadata"].items() if v != []} for r in batch],
            )

    await _run(write)


async def delete(ids: Sequence[str]) -> None:
    if ids:
        await _run(lambda c: c.delete(ids=list(ids)))


async def query(
    vector: Sequence[float],
    ids: Sequence[str],
    where: Optional[dict[str, Any]],
    limit: int,
) -> list[tuple[str, float]]:
    """Cosine search over the given records, narrowed by a metadata filter: [(record id, similarity)], best first."""
    if not ids:
        return []
    result = await _run(lambda c: c.query(
        query_embeddings=[list(vector)], ids=list(ids), where=where,
        n_results=min(limit, len(ids)), include=["distances"],
    ))
    return [(rid, 1.0 - distance) for rid, distance in zip(result["ids"][0], result["distances"][0])]


async def heartbeat() -> bool:
    """True when the client answers (server mode) or the local store opens (embedded mode)."""
    try:
        await _run(lambda _: _client.heartbeat())
        return True
    except Exception:
        return False
