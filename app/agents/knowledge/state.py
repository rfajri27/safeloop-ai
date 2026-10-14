"""Knowledge graph state (spec Section 7.1)."""
from typing import Any, Optional, TypedDict


class KnowledgeState(TypedDict, total=False):
    run_id: str
    message_id: str
    question: str
    asset_tag: Optional[str]
    user_id: str
    history: list[tuple[str, str]]       # last 6 turns, oldest first
    guard: Optional[dict[str, Any]]      # {blocked, rule_id, reason, refusal}
    hits: list[dict[str, Any]]           # chunk_id, doc_code, section, text, score
    evidence_ok: bool
    draft: str                           # streamed text
    usage: dict[str, Any]                # model_id, input_tokens, output_tokens, latency_ms
    answer: Optional[dict[str, Any]]     # CitedAnswer, final and verified
