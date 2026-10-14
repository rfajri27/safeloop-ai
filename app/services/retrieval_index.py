"""Hybrid retrieval over the current document chunks (spec Section 10).

Sparse: BM25 over chunk text, computed in-process (tag-aware tokens, so
`P-101` and `P-101B` stay distinct). Dense: `gemini-embedding-001` vectors
(768 dimensions, cosine), from Qdrant when QDRANT_URL is set, else held in
memory and embedded once per process. The two rankings are fused with
reciprocal rank fusion (k = 8); the fused score is normalised to 0..1 so it can
be compared with KB_MIN_SCORE. Superseded revisions are never indexed.

Filters: `is_current` always; the document's asset tags when `asset_tag` is
given; document types when `doc_types` is given.
"""
import asyncio
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Sequence
from config.ai_services.genai_client import genai_client
from config.databases.postgresql import AsyncSessionLocal
from config.settings import env
from app.engines.corpus import headings_in, section_title
from app.repositories.document_asset_repository import DocumentAssetRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.services import qdrant_store

logger = logging.getLogger(__name__)

RRF_K = 8
BM25_K1, BM25_B = 1.2, 0.75
MAX_HIT_CHARS = 1200
TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by do does for from how i in is it its me my of on or our the this to "
    "was what when where which who why will with you your can should there".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-case tokens; compound tags also yield their parts (p101_de_vib_rms -> p101, de, vib, rms)."""
    tokens = []
    for token in TOKEN.findall(text.lower()):
        if token in STOPWORDS:
            continue
        tokens.append(token)
        parts = re.split(r"[-_.]", token)
        if len(parts) > 1:
            tokens.extend(p for p in parts if p and p not in STOPWORDS)
    return tokens


@dataclass
class IndexedChunk:
    chunk_id: str
    doc_code: str
    doc_title: str
    doc_type: str
    revision: str
    is_synthetic: bool
    section: Optional[str]
    title: Optional[str]
    text: str
    asset_tags: tuple[str, ...]
    point_id: str
    tokens: Counter = field(default_factory=Counter)
    length: int = 0


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    doc_code: str
    doc_title: str
    doc_type: str
    revision: str
    is_synthetic: bool
    section: Optional[str]
    title: Optional[str]
    text: str
    score: float

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id, "doc_code": self.doc_code, "doc_title": self.doc_title,
            "doc_type": self.doc_type, "revision": self.revision, "is_synthetic": self.is_synthetic,
            "section": self.section, "title": self.title, "text": self.text, "score": round(self.score, 3),
        }


class RetrievalIndex:
    """Process-wide index; rebuilt lazily after ingestion invalidates it."""

    def __init__(self):
        self.chunks: list[IndexedChunk] = []
        self.vectors: dict[str, list[float]] = {}
        self.doc_freq: Counter = Counter()
        self.avg_length = 0.0
        self.loaded = False
        self._lock = asyncio.Lock()

    @property
    def document_count(self) -> int:
        return len({c.doc_code for c in self.chunks})

    def invalidate(self) -> None:
        self.loaded = False
        self.chunks = []
        self.vectors = {}

    async def ensure_loaded(self) -> None:
        if self.loaded:
            return
        async with self._lock:
            if self.loaded:
                return
            async with AsyncSessionLocal() as db:
                rows = await DocumentChunkRepository(db).list_current_with_documents()
                tags_repo = DocumentAssetRepository(db)
                doc_tags: dict[str, tuple[str, ...]] = {}
                for _, doc in rows:
                    if doc.id not in doc_tags:
                        doc_tags[doc.id] = tuple(await tags_repo.list_asset_tags(doc.id))
            chunks = []
            for chunk, doc in rows:
                headings = headings_in(chunk.text)
                tokens = Counter(tokenize(f"{doc.title} {chunk.text}"))
                chunks.append(IndexedChunk(
                    chunk_id=chunk.id, doc_code=doc.doc_code, doc_title=doc.title, doc_type=doc.type.value,
                    revision=doc.revision, is_synthetic=doc.origin.value == "synthetic", section=chunk.section,
                    title=section_title(headings[0]) if headings else None, text=chunk.text,
                    asset_tags=doc_tags.get(doc.id, ()), point_id=chunk.qdrant_point_id,
                    tokens=tokens, length=sum(tokens.values()),
                ))
            self.chunks = chunks
            self.doc_freq = Counter(term for c in chunks for term in c.tokens)
            self.avg_length = (sum(c.length for c in chunks) / len(chunks)) if chunks else 0.0
            self.loaded = True

    async def ensure_vectors(self) -> bool:
        """Embed every chunk once (in-memory dense backend). False if embeddings are unavailable."""
        if not env.llm_enabled or not self.chunks:
            return False
        missing = [c for c in self.chunks if c.chunk_id not in self.vectors]
        if not missing:
            return True
        try:
            vectors = await genai_client.embed_documents([f"{c.doc_title}\n{c.text}" for c in missing])
        except Exception:
            logger.exception("Embedding chunks failed; retrieval falls back to BM25 only")
            return False
        for chunk, vector in zip(missing, vectors):
            self.vectors[chunk.chunk_id] = vector
        return True

    def _bm25(self, query_tokens: list[str], candidates: Sequence[IndexedChunk]) -> list[tuple[IndexedChunk, float]]:
        n = len(self.chunks)
        scored = []
        for chunk in candidates:
            score = 0.0
            for term in set(query_tokens):
                tf = chunk.tokens.get(term, 0)
                if not tf:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                norm = tf + BM25_K1 * (1 - BM25_B + BM25_B * chunk.length / (self.avg_length or 1))
                score += idf * tf * (BM25_K1 + 1) / norm
            if score > 0:
                scored.append((chunk, score))
        return sorted(scored, key=lambda pair: -pair[1])

    async def _dense(self, query: str, candidates: Sequence[IndexedChunk], k: int) -> list[tuple[IndexedChunk, float]]:
        if not env.llm_enabled:
            return []
        try:
            query_vector = await genai_client.embed_query(query)
        except Exception:
            logger.exception("Query embedding failed; BM25 only")
            return []
        allowed = {c.point_id: c for c in candidates}
        if qdrant_store.enabled():
            try:
                hits = await qdrant_store.search(query_vector, list(allowed), limit=k)
                return [(allowed[pid], score) for pid, score in hits if pid in allowed]
            except Exception:
                logger.exception("Qdrant search failed; using in-memory vectors")
        if not await self.ensure_vectors():
            return []
        scored = []
        for chunk in candidates:
            vector = self.vectors.get(chunk.chunk_id)
            if vector:
                scored.append((chunk, _cosine(query_vector, vector)))
        return sorted(scored, key=lambda pair: -pair[1])[:k]

    async def search(
        self,
        query: str,
        asset_tag: Optional[str] = None,
        doc_types: Optional[Sequence[str]] = None,
        k: int = 8,
    ) -> list[Hit]:
        """Up to k chunks, best first, each with a fused score in 0..1."""
        await self.ensure_loaded()
        candidates = [
            c for c in self.chunks
            if (not asset_tag or asset_tag in c.asset_tags) and (not doc_types or c.doc_type in doc_types)
        ]
        if asset_tag and not candidates:   # unknown tag: do not filter everything away
            candidates = [c for c in self.chunks if not doc_types or c.doc_type in doc_types]
        if not candidates:
            return []

        sparse = self._bm25(tokenize(query), candidates)[:k * 2]
        dense = await self._dense(query, candidates, k * 2)
        lists = [ranked for ranked in (sparse, dense) if ranked]
        if not lists:
            return []
        fused: dict[str, float] = {}
        by_id = {c.chunk_id: c for c in candidates}
        for ranked in lists:
            for rank, (chunk, _score) in enumerate(ranked, start=1):
                fused[chunk.chunk_id] = fused.get(chunk.chunk_id, 0.0) + 1 / (RRF_K + rank)
        best_possible = 2 / (RRF_K + 1)   # first in both rankings
        top = sorted(fused.items(), key=lambda pair: -pair[1])[:k]
        return [
            Hit(
                chunk_id=cid, doc_code=by_id[cid].doc_code, doc_title=by_id[cid].doc_title,
                doc_type=by_id[cid].doc_type, revision=by_id[cid].revision, is_synthetic=by_id[cid].is_synthetic,
                section=by_id[cid].section, title=by_id[cid].title, text=by_id[cid].text[:MAX_HIT_CHARS],
                score=min(1.0, score / best_possible),
            )
            for cid, score in top
        ]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


# SINGLETON: shared by the knowledge agent, the Red Team context and the evaluation
retrieval_index = RetrievalIndex()
