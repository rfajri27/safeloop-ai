"""Red Team agent graph (spec Section 7.2): HAZOP proposals checked by the Judge.

    START -> build_context -> propose -> judge -> persist -> END

Only `propose` calls Gemini (structured output, RedTeamOutput schema, two
attempts). The Judge is code. Dependencies arrive through config["configurable"]:
load_context (async, row_code -> (context, judge_context, taken_codes)) and
persist (async callback, may be None for evaluation runs).
"""
import string
import time
from functools import lru_cache
from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from config.ai_services.llm_client import llm_client
from config.settings import env
from app.agents.base import classify_llm_error, configurable, emit, step
from app.agents.red_team.prompts import REDTEAM_PROMPT_VERSION, REDTEAM_SYSTEM_PROMPT, user_turn
from app.agents.red_team.schemas import RedTeamOutput
from app.agents.red_team.state import RedTeamState
from app.engines import judge as judge_engine

MAX_ATTEMPTS = 2
MAX_OUTPUT_TOKENS = 8192   # medium thinking counts against the limit


@step("build_context")
async def build_context(state: RedTeamState, config: RunnableConfig) -> dict:
    """Row, assets it touches with current health, safeguards with dependencies, best chunks."""
    load = configurable(config, "load_context")
    context, judge_context, taken = await load(state["row_code"], state.get("focus", "any"))
    return {"context": {**context, "taken_codes": sorted(taken)}, "judge_context": judge_context}


@step("propose")
async def propose(state: RedTeamState, config: RunnableConfig) -> dict:
    """Gemini with redteam.v1 and the RedTeamOutput schema; fails closed after two invalid outputs."""
    llm = llm_client.gemini(thinking_level="medium", max_tokens=MAX_OUTPUT_TOKENS, timeout=env.llm_timeout_seconds)
    structured = llm.with_structured_output(RedTeamOutput, method="json_schema", include_raw=True)
    system = REDTEAM_SYSTEM_PROMPT.replace("{max_proposals}", str(state.get("max_proposals", 2)))
    messages = [("system", system), ("human", user_turn(state["context"], state.get("focus", "any")))]
    usage: dict[str, Any] = {"model_id": env.gemini_model, "input_tokens": 0, "output_tokens": 0, "attempts": 0}
    started = time.perf_counter()
    parsed = None
    for _ in range(MAX_ATTEMPTS):
        usage["attempts"] += 1
        try:
            result = await structured.ainvoke(messages)
        except Exception as exc:
            raise classify_llm_error(exc) from exc
        raw = result.get("raw")
        if raw is not None:
            meta = getattr(raw, "usage_metadata", None) or {}
            usage["input_tokens"] += meta.get("input_tokens") or 0
            usage["output_tokens"] += meta.get("output_tokens") or 0
            usage["model_id"] = (getattr(raw, "response_metadata", None) or {}).get("model_name") or usage["model_id"]
        if result.get("parsed") is not None:
            parsed = result["parsed"]
            break
    usage["latency_ms"] = int((time.perf_counter() - started) * 1000)
    if parsed is None:
        return {"raw": None, "schema_valid": False, "usage": usage}
    drafts = [p.model_dump(mode="json") for p in parsed.proposals[: state.get("max_proposals", 2)]]
    return {"raw": drafts, "schema_valid": True, "usage": usage}


def _proposed_code(row_code: str, kind: str, taken: set[str]) -> str:
    """New scenarios get the next free letter suffix (HZ-N1-003a); worsened rows keep the code."""
    if kind != "new_scenario":
        return row_code
    for letter in string.ascii_lowercase:
        code = f"{row_code}{letter}"
        if code not in taken:
            taken.add(code)
            return code
    return f"{row_code}z"


@step("judge")
async def judge(state: RedTeamState, config: RunnableConfig) -> dict:
    """judge.check() per proposal (code, not the model)."""
    taken = set(state["context"].get("taken_codes", []))
    proposals = []
    for index, draft in enumerate(state.get("raw") or [], start=1):
        result = judge_engine.check(draft, state["judge_context"])
        proposal = {
            "index": index,
            **draft,
            "proposed_row_code": _proposed_code(state["row_code"], draft["kind"], taken),
            "parent_row_code": state["row_code"],
            "citations": [{"ref": ref} for ref in draft.get("citations", [])],
            "verdict": result.as_dict(),
            "judge": {
                "unknown_entities": list(result.unknown_entities),
                "unresolved_citations": list(result.unresolved_citations),
                "actuation_wording": result.actuation_wording,
            },
            "approval_item_id": None,
            "audit_id": None,
        }
        proposals.append(proposal)
        emit("CUSTOM", name="proposal", value={k: v for k, v in proposal.items() if k not in ("verdict", "judge")})
        emit("CUSTOM", name="judge_verdict", value={
            "proposal_index": index, "verdict": result.verdict, "checks": [c.as_dict() for c in result.checks],
            "reason": result.reason, "audit_id": None,
        })
    return {"proposals": proposals}


@step("persist")
async def persist(state: RedTeamState, config: RunnableConfig) -> dict:
    """Hand the run to the service's persist callback (one transaction, spec Section 10)."""
    usage = state.get("usage") or {}
    result = {
        "run_id": state["run_id"],
        "row_code": state["row_code"],
        "prompt_version": REDTEAM_PROMPT_VERSION,
        "model_id": usage.get("model_id"),
        "schema_valid": state.get("schema_valid", False),
        "proposals": state.get("proposals", []),
    }
    callback = configurable(config, "persist")
    if callback:
        result = await callback(state, result)
        for proposal in result["proposals"]:
            if proposal.get("approval_item_id"):
                emit("CUSTOM", name="approval_queued", value={
                    "approval_item_id": proposal["approval_item_id"],
                    "title": f"{proposal['proposed_row_code']} · {proposal['title']}",
                })
    return {"result": result}


@lru_cache(maxsize=1)
def build_red_team_graph():
    """Compile the graph once (no checkpointer: each run is self-contained)."""
    graph = StateGraph(RedTeamState)
    graph.add_node("build_context", build_context)
    graph.add_node("propose", propose)
    graph.add_node("judge", judge)
    graph.add_node("persist", persist)
    graph.add_edge(START, "build_context")
    graph.add_edge("build_context", "propose")
    graph.add_edge("propose", "judge")
    graph.add_edge("judge", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
