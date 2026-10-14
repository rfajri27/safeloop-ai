"""Qdrant collection for chunk vectors, over its REST API (spec Section 10).

Used only when QDRANT_URL is set. Collection `unit100_chunks`: named dense
vector `dense` (768, cosine); point id = document_chunks.qdrant_point_id;
payload chunk_id, doc_code, doc_type, asset_tags, revision, is_current,
is_synthetic, section. Sparse BM25 is computed in-process by the retrieval index.
"""
from typing import Any, Sequence
import httpx
from config.settings import env

TIMEOUT_SECONDS = 10.0


def enabled() -> bool:
    return bool(env.qdrant_url)


def _url(path: str) -> str:
    return f"{env.qdrant_url.rstrip('/')}/collections/{env.qdrant_collection}{path}"


async def ensure_collection() -> None:
    """Create the collection if it does not exist."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(_url(""))
        if response.status_code == 200:
            return
        response = await client.put(_url(""), json={
            "vectors": {"dense": {"size": env.embedding_dim, "distance": "Cosine"}},
        })
        response.raise_for_status()


async def upsert(points: Sequence[dict[str, Any]]) -> None:
    """points: [{id, vector, payload}]."""
    if not points:
        return
    await ensure_collection()
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.put(_url("/points?wait=true"), json={
            "points": [{"id": p["id"], "vector": {"dense": p["vector"]}, "payload": p["payload"]} for p in points],
        })
        response.raise_for_status()


async def delete(point_ids: Sequence[str]) -> None:
    if not point_ids:
        return
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(_url("/points/delete?wait=true"), json={"points": list(point_ids)})
        if response.status_code != 404:
            response.raise_for_status()


async def search(vector: Sequence[float], point_ids: Sequence[str], limit: int) -> list[tuple[str, float]]:
    """Cosine search restricted to the given (current, filtered) points: [(point id, score)]."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(_url("/points/query"), json={
            "query": list(vector),
            "using": "dense",
            "filter": {"must": [{"has_id": list(point_ids)}, {"key": "is_current", "match": {"value": True}}]},
            "limit": limit,
        })
        response.raise_for_status()
        points = response.json().get("result", {}).get("points", [])
    return [(str(p["id"]), float(p["score"])) for p in points]
