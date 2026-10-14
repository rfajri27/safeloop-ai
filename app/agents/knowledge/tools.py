"""Knowledge agent tools (spec Section 7.4).

Tools are called by nodes, not chosen by the model, so every run is bounded and
every retrieval is auditable. The index comes from the run config, never from
model arguments.
"""
import json
from typing import Any, Optional, Sequence
from langchain_core.runnables import RunnableConfig
from app.agents.base import configurable, emit
from app.utils.sse import generate_tool_call_id


async def hybrid_search(
    query: str,
    asset_tag: Optional[str],
    doc_types: Optional[Sequence[str]],
    k: int,
    config: RunnableConfig,
) -> list[dict[str, Any]]:
    """Up to k chunks (chunk_id, doc_code, section, text <= 1,200 chars, score), with TOOL_CALL events."""
    index = configurable(config, "index")
    call_id = generate_tool_call_id()
    emit("TOOL_CALL_START", toolCallId=call_id, toolCallName="hybrid_search")
    emit("TOOL_CALL_ARGS", toolCallId=call_id, delta=json.dumps(
        {"query": query, "asset_tag": asset_tag, "doc_types": list(doc_types) if doc_types else None, "k": k}
    ))
    emit("TOOL_CALL_END", toolCallId=call_id)
    hits = [hit.as_dict() for hit in await index.search(query, asset_tag=asset_tag, doc_types=doc_types, k=k)] if index else []
    summary = ", ".join(f"{h['doc_code']} ({h['section']})" for h in hits[:5])
    emit("TOOL_CALL_RESULT", toolCallId=call_id, content=f"{len(hits)} chunks: {summary}" if hits else "0 chunks")
    return hits
