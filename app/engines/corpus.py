"""Corpus parsing and chunking for ingestion and citation resolution (spec Section 10).

Documents are Markdown with YAML front matter (doc_code, title, type, revision,
effective_date, asset_tags, is_current). A chunk is one `##` section together
with its `###` sub-sections (SOP steps stay together; tables stay whole). Each
chunk keeps its headings, so a citation such as `doc:SOP-P101-02#step-3`
resolves to the chunk whose headings include `Step 3`.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional
import yaml

HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)


def section_id(heading: str) -> str:
    """'6.3 Bearing...' -> '6.3', 'Step 7' -> 'step-7', 'Node 1: ...' -> 'node-1', else a slug."""
    text = heading.strip()
    match = re.match(r"^(\d+(?:\.\d+)*)\b", text)
    if match:
        return match.group(1)
    match = re.match(r"^(step|node)\s+(\d+)", text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1).lower()}-{match.group(2)}"
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def section_title(heading: str) -> str:
    """Heading without its numeric id: '6.3 Bearing lubrication' -> 'Bearing lubrication'."""
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", heading.strip())


def headings_in(text: str) -> list[str]:
    """Every ##/###/#### heading in a chunk, in order."""
    return [m.group(2) for m in HEADING.finditer(text)]


def section_ids_in(text: str) -> set[str]:
    """Section ids a chunk can be cited by."""
    return {section_id(h) for h in headings_in(text)}


def approx_tokens(text: str) -> int:
    """Rough token count (words x 1.3) for chunk metadata."""
    return int(len(text.split()) * 1.3) + 1


@dataclass(frozen=True)
class CorpusChunk:
    chunk_index: int
    section: str
    title: str
    text: str
    content_hash: str
    token_count: int


@dataclass(frozen=True)
class CorpusDocument:
    path: Path
    doc_code: str
    title: str
    type: str
    revision: str
    effective_date: Optional[date]
    asset_tags: tuple[str, ...]
    is_current: bool
    origin: str
    meta: dict[str, Any] = field(default_factory=dict)
    chunks: tuple[CorpusChunk, ...] = ()


def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    _, front, body = raw.split("---", 2)
    return yaml.safe_load(front) or {}, body


def chunk_body(body: str) -> list[CorpusChunk]:
    """One chunk per `##` section (with its sub-sections); text before the first one is skipped."""
    starts = [m for m in re.finditer(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE)]
    chunks = []
    for i, match in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        text = body[match.start():end].strip()
        heading = match.group(1)
        chunks.append(CorpusChunk(
            chunk_index=i,
            section=section_id(heading),
            title=section_title(heading),
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            token_count=approx_tokens(text),
        ))
    return chunks


def parse_document(path: Path) -> CorpusDocument:
    """Front matter + chunks of one corpus file."""
    meta, body = _split_front_matter(path.read_text(encoding="utf-8"))
    effective = meta.get("effective_date")
    if isinstance(effective, str):
        effective = date.fromisoformat(effective)
    return CorpusDocument(
        path=path,
        doc_code=str(meta["doc_code"]),
        title=str(meta["title"]),
        type=str(meta["type"]),
        revision=str(meta.get("revision", "A")),
        effective_date=effective,
        asset_tags=tuple(meta.get("asset_tags") or ()),
        is_current=bool(meta.get("is_current", True)),
        origin=str(meta.get("origin", "synthetic")),
        meta=meta,
        chunks=tuple(chunk_body(body)),
    )


def load_corpus(corpus_dir: Path) -> list[CorpusDocument]:
    """Every *.md document in the corpus directory, ordered by file name."""
    return [parse_document(path) for path in sorted(corpus_dir.glob("*.md"))]
