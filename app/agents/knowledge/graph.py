"""Knowledge agent graph (spec Section 7.1): cited Q&A over the synthetic corpus.

    START -> guard_input -> refuse ------------------------------------> persist -> END
                         -> retrieve -> grade_evidence -> insufficient --> persist
                                                       -> draft_answer -> verify_citations -> persist

Only draft_answer calls Gemini. A refused or weak-evidence question skips the
model entirely (PO-3, PO-4). Dependencies arrive through config["configurable"]:
index, guardrail, persist (async callback), llm_enabled, started (perf counter).
"""
import re
import time
from functools import lru_cache
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from config.ai_services.llm_client import llm_client
from config.settings import env
from app.agents.base import classify_llm_error, configurable, emit, step
from app.agents.knowledge.prompts import (
    ADVISORY_NOTE, INSUFFICIENT_MARKER, KB_PROMPT_VERSION, KB_SYSTEM_PROMPT,
    LLM_DISABLED_NOTE, insufficient_text, user_turn,
)
from app.agents.knowledge.state import KnowledgeState
from app.agents.knowledge.tools import hybrid_search

MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
STEP_LINE = re.compile(r"^\s*(\d+)[.)]\s+(.*\S)\s*$")
HISTORY_TURNS = 6
MAX_ANSWER_TOKENS = 2048   # thinking tokens count against the limit


def _answer(state: KnowledgeState, kind: str, content: str, **extra: Any) -> dict[str, Any]:
    return {
        "message_id": state["message_id"],
        "kind": kind,
        "confidence": None,
        "content": content,
        "steps": [],
        "citations": [],
        "advisory_note": None,
        "guardrail": None,
        "latency_ms": None,
        "model_id": None,
        "prompt_version": KB_PROMPT_VERSION,
        "audit_id": None,
        **extra,
    }


def _document_count(config: RunnableConfig) -> int:
    index = configurable(config, "index")
    return index.document_count if index else 0


@step("guard_input")
async def guard_input(state: KnowledgeState, config: RunnableConfig) -> dict:
    guardrail = configurable(config, "guardrail")
    result = guardrail.check(state["question"])
    return {"guard": {
        "blocked": result.blocked, "rule_id": result.rule_id,
        "reason": result.reason, "refusal": result.refusal,
    }}


async def refuse(state: KnowledgeState, config: RunnableConfig) -> dict:
    """Fixed refusal template for the rule; no model call."""
    guard = state["guard"]
    return {"answer": _answer(
        state, "refused", guard["refusal"],
        guardrail={"rule_id": guard["rule_id"], "reason": guard["reason"], "model_calls": 0},
    )}


@step("retrieve")
async def retrieve(state: KnowledgeState, config: RunnableConfig) -> dict:
    hits = await hybrid_search(state["question"], state.get("asset_tag"), None, env.kb_top_k, config)
    return {"hits": hits[:env.kb_context_chunks]}


async def grade_evidence(state: KnowledgeState, config: RunnableConfig) -> dict:
    hits = state.get("hits") or []
    return {"evidence_ok": bool(hits) and hits[0]["score"] >= env.kb_min_score}


async def insufficient(state: KnowledgeState, config: RunnableConfig) -> dict:
    """Fixed 'insufficient evidence' template naming the topic; no model call."""
    content = insufficient_text(_document_count(config), f'"{state["question"]}"')
    if not configurable(config, "llm_enabled", True) and state.get("evidence_ok"):
        content = f"{LLM_DISABLED_NOTE} {content}"
    emit("CUSTOM", name="citations", value=[])
    emit("CUSTOM", name="answer_kind", value={"kind": "insufficient", "confidence": None})
    return {"answer": _answer(state, "insufficient", content)}


def _sources_block(hits: list[dict]) -> str:
    return "\n\n".join(
        f"[{i}] {h['doc_code']} rev {h['revision']}, section {h['section']} ({h['doc_title']})\n{h['text']}"
        for i, h in enumerate(hits, start=1)
    )


def _history_block(history: list[tuple[str, str]]) -> str:
    turns = history[-HISTORY_TURNS * 2:]
    return "\n".join(f"{role}: {content[:600]}" for role, content in turns)


@step("draft_answer")
async def draft_answer(state: KnowledgeState, config: RunnableConfig) -> dict:
    """Gemini with kb.v1; streams text deltas. The only node that calls the model."""
    llm = llm_client.gemini(thinking_level="low", max_tokens=MAX_ANSWER_TOKENS, timeout=30)
    messages = [
        ("system", KB_SYSTEM_PROMPT),
        ("human", user_turn(state["question"], _sources_block(state["hits"]), _history_block(state.get("history") or []))),
    ]
    message_id = state["message_id"]
    started = time.perf_counter()
    parts: list[str] = []
    usage = {"input_tokens": None, "output_tokens": None, "model_id": env.gemini_model}
    emit("TEXT_MESSAGE_START", messageId=message_id, role="assistant")
    try:
        async for chunk in llm.astream(messages):
            delta = chunk.text
            if delta:
                parts.append(delta)
                emit("TEXT_MESSAGE_CONTENT", messageId=message_id, delta=delta)
            if chunk.usage_metadata:
                usage["input_tokens"] = chunk.usage_metadata.get("input_tokens")
                usage["output_tokens"] = chunk.usage_metadata.get("output_tokens")
            model_name = (chunk.response_metadata or {}).get("model_name")
            if model_name:
                usage["model_id"] = model_name
    except Exception as exc:
        raise classify_llm_error(exc) from exc
    finally:
        emit("TEXT_MESSAGE_END", messageId=message_id)
    usage["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return {"draft": "".join(parts), "usage": usage}


def _citation(index: int, hit: dict) -> dict:
    return {
        "index": index, "doc_code": hit["doc_code"], "title": hit["doc_title"], "chunk_id": hit["chunk_id"],
        "section": hit["section"], "revision": hit["revision"], "is_synthetic": hit["is_synthetic"], "resolved": True,
    }


@step("verify_citations")
async def verify_citations(state: KnowledgeState, config: RunnableConfig) -> dict:
    """Map [n] markers to retrieved chunks, drop unresolved ones, renumber, set confidence."""
    draft = (state.get("draft") or "").strip()
    hits = state.get("hits") or []
    usage = state.get("usage") or {}
    model_fields = {"model_id": usage.get("model_id")}

    if not draft or draft.startswith(INSUFFICIENT_MARKER):
        missing = draft.split(":", 1)[1].strip() if ":" in draft else ""
        content = insufficient_text(_document_count(config), f'"{state["question"]}"')
        if missing:
            content = f"{missing.rstrip('.')}. {content}"
        emit("CUSTOM", name="citations", value=[])
        emit("CUSTOM", name="answer_kind", value={"kind": "insufficient", "confidence": None})
        return {"answer": _answer(state, "insufficient", content, **model_fields)}

    renumber: dict[int, int] = {}

    def rewrite(match: re.Match) -> str:
        kept = []
        for raw in match.group(1).split(","):
            n = int(raw.strip())
            if 1 <= n <= len(hits):
                renumber.setdefault(n, len(renumber) + 1)
                kept.append(f"[{renumber[n]}]")
        return "".join(kept)

    content = MARKER.sub(rewrite, draft)
    content = re.sub(r"[ \t]+([.,;:])", r"\1", content).strip()
    if not renumber:
        content = insufficient_text(_document_count(config), f'"{state["question"]}"')
        emit("CUSTOM", name="citations", value=[])
        emit("CUSTOM", name="answer_kind", value={"kind": "insufficient", "confidence": None})
        return {"answer": _answer(state, "insufficient", content, **model_fields)}

    citations = [_citation(new, hits[old - 1]) for old, new in sorted(renumber.items(), key=lambda p: p[1])]
    top_score = max(hits[old - 1]["score"] for old in renumber)
    if len(citations) >= 2 and top_score >= 0.6:
        confidence = "high"
    elif len(citations) == 1:
        confidence = "medium"
    else:
        confidence = "low"

    steps = []
    for line in content.splitlines():
        match = STEP_LINE.match(line)
        if match:
            text = match.group(2)
            steps.append({
                "text": MARKER.sub("", text).strip(),
                "citations": [int(n) for group in MARKER.findall(text) for n in group.split(",")],
            })

    emit("CUSTOM", name="citations", value=citations)
    emit("CUSTOM", name="answer_kind", value={"kind": "answer", "confidence": confidence})
    return {"answer": _answer(
        state, "answer", content, confidence=confidence, steps=steps,
        citations=citations, advisory_note=ADVISORY_NOTE, **model_fields,
    )}


@step("persist")
async def persist(state: KnowledgeState, config: RunnableConfig) -> dict:
    """Hand the answer to the service's persist callback (one transaction, spec Section 10)."""
    answer = dict(state["answer"])
    started = configurable(config, "started")
    if started is not None:
        answer["latency_ms"] = int((time.perf_counter() - started) * 1000)
    callback = configurable(config, "persist")
    if callback:
        saved = await callback(state, answer)
        answer.update(saved or {})
    if answer["kind"] == "refused":
        emit("CUSTOM", name="guardrail_refusal", value={
            "rule_id": answer["guardrail"]["rule_id"],
            "reason": answer["guardrail"]["reason"],
            "audit_id": answer.get("audit_id"),
        })
        emit("CUSTOM", name="answer_kind", value={"kind": "refused", "confidence": None})
    return {"answer": answer}


def _after_guard(state: KnowledgeState) -> str:
    return "refuse" if state["guard"]["blocked"] else "retrieve"


def _after_grade(state: KnowledgeState, config: RunnableConfig) -> str:
    if state.get("evidence_ok") and configurable(config, "llm_enabled", True):
        return "draft_answer"
    return "insufficient"


@lru_cache(maxsize=1)
def build_knowledge_graph():
    """Compile the graph once; it holds no per-request state."""
    graph = StateGraph(KnowledgeState)
    graph.add_node("guard_input", guard_input)
    graph.add_node("refuse", refuse)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_evidence", grade_evidence)
    graph.add_node("insufficient", insufficient)
    graph.add_node("draft_answer", draft_answer)
    graph.add_node("verify_citations", verify_citations)
    graph.add_node("persist", persist)
    graph.add_edge(START, "guard_input")
    graph.add_conditional_edges("guard_input", _after_guard, ["refuse", "retrieve"])
    graph.add_edge("retrieve", "grade_evidence")
    graph.add_conditional_edges("grade_evidence", _after_grade, ["insufficient", "draft_answer"])
    graph.add_edge("draft_answer", "verify_citations")
    graph.add_edge("refuse", "persist")
    graph.add_edge("insufficient", "persist")
    graph.add_edge("verify_citations", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
