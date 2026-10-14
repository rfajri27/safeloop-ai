"""Red Team service for running the Red Team agent and Judge on a HAZOP row.

Endpoints served:
    POST /hazop-rows/{row_code}/red-team        - Run Red Team + Judge, return the result
    POST /hazop-rows/{row_code}/red-team/stream - Same, streamed (SSE)
    GET  /red-team-runs/{run_id}                - A finished run with proposals and verdicts

Writes (one transaction): agent_runs, hazop_proposals, judge_verdicts, citations,
                          approval_items (pass only), audit_log
"""
import logging
from typing import Any, AsyncIterator, Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from config.databases.postgresql import AsyncSessionLocal
from config.settings import env
from app.agents.base import AgentEvent
from app.agents.red_team.agent import RedTeamAgent
from app.agents.red_team.prompts import REDTEAM_PROMPT_VERSION
from app.agents.red_team.schemas import RedTeamInput
from app.engines.corpus import headings_in, section_id, section_ids_in
from app.engines.judge import JudgeContext
from app.models.agent_run_model import AgentRun
from app.models.approval_item_model import ApprovalItem
from app.models.citation_model import Citation
from app.models.enums import (
    AgentName, ApprovalDecision, ArtifactType, CitationTarget, GuideWord, HazopParam, Verdict,
)
from app.models.hazop_proposal_model import HazopProposal
from app.models.judge_verdict_model import JudgeVerdict
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.asset_link_repository import AssetLinkRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.hazop_row_repository import HazopRowRepository
from app.repositories.prompt_template_repository import PromptTemplateRepository
from app.repositories.safeguard_dependency_repository import SafeguardDependencyRepository
from app.repositories.safeguard_repository import SafeguardRepository
from app.schemas.auth_schema import CurrentUser
from app.services import unit_events
from app.services.audit_records import audit_entry, audit_id
from app.services.chat_service import guardrail
from app.services.live_state import get_live_run, list_asset_health, list_hazop_rows
from app.services.plant_model import DEFAULT_UNIT, load_plant_model
from app.services.retrieval_index import retrieval_index
from app.utils import idempotency
from app.utils.ids import is_uuid, new_id
from app.utils.response import response_error, response_success
from app.utils.sse import SSE_HEADERS, FrameCounter

logger = logging.getLogger(__name__)
CONTEXT_CHUNKS = 6
SOURCE_CHARS = 1200

# Rows with a Red Team run in progress in this process (409 on a second run).
_running_rows: set[str] = set()


async def load_context(row_code: str, focus: str) -> tuple[dict[str, Any], JudgeContext, set[str]]:
    """Everything the Red Team sees, plus what the Judge resolves against (own session)."""
    async with AsyncSessionLocal() as db:
        plant = await load_plant_model(db)
        run = await get_live_run(db)
        live = next(r for r in await list_hazop_rows(db, run) if r.row.row_code == row_code)
        health = {t["tag"]: {"health_index": t["health_index"], "band": t["band"] or "healthy (no live replay)"}
                  for t in await list_asset_health(db, run)}
        assets = await AssetRepository(db).list_by_unit(plant.unit_id, limit=1000)
        tags = {a.id: a.tag for a in assets}
        links = await AssetLinkRepository(db).list_all()
        safeguards = await SafeguardRepository(db).list_by_unit(plant.unit_id)
        deps = await SafeguardDependencyRepository(db).list_for_safeguards([s.id for s in safeguards])
        chunk_rows = await DocumentChunkRepository(db).list_current_with_documents()
        pending = await ApprovalItemRepository(db).list_filtered(ApprovalDecision.PENDING, ArtifactType.HAZOP_CHANGE, limit=200)
        current_codes = [row.row_code for row, _ in await HazopRowRepository(db).list_current()]

    depends_on: dict[str, list[str]] = {}
    for dep, asset in deps:
        depends_on.setdefault(dep.safeguard_id, []).append(asset.tag)
    row_input = next(r for r in plant.rows if r.row_code == row_code)
    touched = {row_input.cause_asset} | {t for sg in row_input.safeguards for t in sg.depends_on}
    touched |= {tag for tag in tags.values() if tag in f"{live.row.cause} {live.row.consequence} {live.row.deviation}"}
    touched.discard(None)

    link_view = [{"code": l.code, "from": tags.get(l.from_asset_id), "relation": l.relation, "to": tags.get(l.to_asset_id)} for l in links]
    sources = [
        {"id": f"asset_model:{l['code']}", "text": f"{l['from']} {l['relation']} {l['to']}"}
        for l in link_view if l["from"] in touched or l["to"] in touched
    ]
    query = f"{live.row.deviation}. Cause: {live.row.cause}. Consequence: {live.row.consequence}. " \
            f"Safeguards: {', '.join(sg.ref_code for sg in row_input.safeguards)}"
    await retrieval_index.ensure_loaded()
    for hit in await retrieval_index.search(query, k=CONTEXT_CHUNKS):
        for heading, text in _subsections(hit.text):
            sources.append({"id": f"doc:{hit.doc_code}#{section_id(heading)}", "text": text[:SOURCE_CHARS]})

    doc_sections: dict[str, set[str]] = {}
    for chunk, doc in chunk_rows:
        doc_sections.setdefault(doc.doc_code, set()).update(section_ids_in(chunk.text))
    judge_context = JudgeContext(
        asset_tags=frozenset(tags.values()),
        safeguard_refs=frozenset(s.ref_code for s in safeguards),
        link_codes=frozenset(l.code for l in links if l.code),
        doc_sections={code: frozenset(s) for code, s in doc_sections.items()},
        actuation=guardrail().actuation_wording,
    )
    context = {
        "row": {**{k: live.summary[k] for k in (
            "row_code", "guide_word", "parameter", "deviation", "cause", "consequence",
            "severity", "likelihood_base", "likelihood_live", "band_live",
        )}, "node": plant.row_nodes.get(row_code), "cause_asset": row_input.cause_asset,
            "safeguards": [{"ref_code": sg.ref_code, "type": sg.type, "credited": sg.credited, "depends_on": list(sg.depends_on)}
                           for sg in row_input.safeguards]},
        "health": health,
        "asset_model": {"assets": [{"tag": a.tag, "name": a.name, "class": a.asset_class} for a in assets], "links": link_view},
        "safeguards": [{"ref_code": s.ref_code, "type": s.type.value, "description": s.description,
                        "depends_on": depends_on.get(s.id, [])} for s in safeguards],
        "sources": sources,
    }
    taken = set(current_codes) | {(i.body or {}).get("proposed_row_code") for i in pending} - {None}
    return context, judge_context, taken


def _subsections(text: str) -> list[tuple[str, str]]:
    """Split a chunk into (heading, text) per heading so each citable section is its own source."""
    headings = headings_in(text)
    if len(headings) <= 1:
        return [(headings[0] if headings else "", text)]
    parts, lines, current = [], [], None
    for line in text.splitlines():
        stripped = line.lstrip("#").strip()
        if line.startswith("#") and stripped in headings:
            if current is not None:
                parts.append((current, "\n".join(lines).strip()))
            current, lines = stripped, [line]
        else:
            lines.append(line)
    if current is not None:
        parts.append((current, "\n".join(lines).strip()))
    return parts


async def run_red_team(payload: RedTeamInput, run_id: str, user_id: Optional[str], persist: bool = True) -> AsyncIterator[AgentEvent]:
    """Run the Red Team with this process's dependencies (endpoints and evaluation)."""
    deps = {"load_context": load_context, "persist": None}
    if persist:
        async def persist_fn(state: dict, result: dict) -> dict:
            return await _save_run(state, result, user_id)
        deps["persist"] = persist_fn
    async for event in RedTeamAgent().stream(payload, run_id, deps):
        yield event


async def _resolve_citation(db, ref: str, proposal_id: str) -> Citation:
    """A proposal citation row; unresolved references are kept with resolved = false."""
    if ref.startswith("asset_model:"):
        link = await AssetLinkRepository(db).get_by_code(ref.split(":", 1)[1].strip())
        return Citation(target_type=CitationTarget.ASSET, asset_id=link.from_asset_id if link else None,
                        resolved=link is not None, raw_ref=ref[:128], proposal_id=proposal_id)
    if ref.startswith("doc:"):
        doc_code, _, section = ref[4:].partition("#")
        chunks = await DocumentChunkRepository(db).find_current_by_section(doc_code.strip())
        match = next((c for c in chunks if not section or section.strip().lower() in section_ids_in(c.text)), None)
        return Citation(target_type=CitationTarget.CHUNK, chunk_id=match.id if match else None,
                        resolved=match is not None, raw_ref=ref[:128], proposal_id=proposal_id)
    return Citation(target_type=CitationTarget.CHUNK, resolved=False, raw_ref=ref[:128], proposal_id=proposal_id)


async def _save_run(state: dict, result: dict, user_id: Optional[str]) -> dict:
    """agent_runs + hazop_proposals + judge_verdicts + citations + approval_items + audit_log (operation 2)."""
    usage = state.get("usage") or {}
    row_code = state["row_code"]
    queued: list[str] = []
    async with AsyncSessionLocal() as db:
        target = await HazopRowRepository(db).get_current_by_code(row_code)
        template = await PromptTemplateRepository(db).get_by_version(AgentName.RED_TEAM, REDTEAM_PROMPT_VERSION)
        run = AgentRun(
            id=state["run_id"], agent=AgentName.RED_TEAM, prompt_template_id=template.id if template else None,
            model_id=usage.get("model_id"), model_endpoint="cloud_api",
            input={"row_code": row_code, "max_proposals": state.get("max_proposals"), "focus": state.get("focus"),
                   "requested_by": user_id, "sources": len(state.get("context", {}).get("sources", []))},
            output=None, schema_valid=state.get("schema_valid", False),
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
            latency_ms=usage.get("latency_ms"), hazop_row_id=target.id if target else None,
        )
        db.add(run)
        await db.flush()

        if not state.get("schema_valid"):
            db.add(audit_entry(
                "schema_invalid", "agent_runs", run.id,
                text=f"Red Team output for {row_code} failed the schema twice; no proposals queued",
                outcome="not_queued", actor_agent=AgentName.RED_TEAM, model_id=run.model_id,
                prompt_version=REDTEAM_PROMPT_VERSION, row_code=row_code,
            ))

        node = state.get("context", {}).get("row", {}).get("node")
        for proposal in result["proposals"]:
            verdict = proposal["verdict"]
            passed = verdict["verdict"] == "pass"
            hazop_proposal = HazopProposal(
                id=new_id(), agent_run_id=run.id, target_row_id=target.id,
                guide_word=GuideWord(proposal["guide_word"]), parameter=HazopParam(proposal["parameter"]),
                deviation=proposal["deviation"], cause=proposal["cause"], consequence=proposal["consequence"],
                proposed_safeguards=list(proposal.get("safeguards", [])), recommendation=proposal.get("recommendation"),
            )
            db.add(hazop_proposal)
            await db.flush()
            judge_verdict = JudgeVerdict(
                id=new_id(), proposal_id=hazop_proposal.id, verdict=Verdict(verdict["verdict"]),
                unknown_entities=proposal["judge"]["unknown_entities"],
                unresolved_citations=proposal["judge"]["unresolved_citations"],
                actuation_wording=proposal["judge"]["actuation_wording"], reason=verdict.get("reason"),
            )
            db.add(judge_verdict)
            await db.flush()
            citations = [await _resolve_citation(db, c["ref"], hazop_proposal.id) for c in proposal["citations"]]
            db.add_all(citations)

            item = None
            if passed:
                resolved = sum(c.resolved for c in citations)
                item = ApprovalItem(
                    id=new_id(), artifact_type=ArtifactType.HAZOP_CHANGE,
                    title=f"{proposal['proposed_row_code']} · {proposal['title']}"[:300],
                    asset_id=target.cause_asset_id, proposal_id=hazop_proposal.id,
                    confidence="high" if resolved >= 2 and resolved == len(citations) else "medium",
                    judge_verdict_id=judge_verdict.id, decision=ApprovalDecision.PENDING,
                    body={k: v for k, v in proposal.items() if k not in ("judge", "approval_item_id", "audit_id")}
                    | {"node": node, "run_id": run.id},
                )
                db.add(item)
                await db.flush()
                queued.append(item.id)
            short = proposal["title"] if len(proposal["title"]) <= 90 else proposal["title"][:87] + "…"
            audit = audit_entry(
                "draft_created" if passed else "judge_block", "hazop_proposals", hazop_proposal.id,
                text=f"Red Team proposal {proposal['index']} for {row_code}: {short}" if passed
                else f"Judge blocked Red Team proposal {proposal['index']} for {row_code}: {verdict.get('reason')}",
                outcome="queued" if passed else "not_queued", sources=len(citations),
                actor_agent=AgentName.RED_TEAM if passed else AgentName.JUDGE,
                model_id=run.model_id, prompt_version=REDTEAM_PROMPT_VERSION,
                row_code=row_code, proposal_index=proposal["index"], verdict=verdict["verdict"],
                judge=verdict.get("reason"), approval_item_id=item.id if item else None, run_id=run.id,
            )
            db.add(audit)
            await db.flush()
            proposal.update({
                "proposal_id": hazop_proposal.id,
                "approval_item_id": item.id if item else None,
                "audit_id": audit_id(audit.id),
            })
        run.output = result
        await db.commit()
        pending = await ApprovalItemRepository(db).count_pending()
    await unit_events.publish(DEFAULT_UNIT, [
        ("approval_changed", {"approval_item_id": item_id, "decision": "pending", "pending_count": pending})
        for item_id in queued
    ])
    return result


class RedTeamService:
    """
    Service for Red Team runs.

    REQUEST-SCOPED: Created per request with injected session.
    Pre-stream checks: row exists (404), no run in progress on the row (409),
    LLM enabled (503 "AI service disabled").
    """

    def __init__(self, db: AsyncSession):
        """Initialize RedTeamService with a DB session."""
        self.db = db

    async def _check(self, row_code: str) -> RedTeamInput:
        if not await HazopRowRepository(self.db).get_current_by_code(row_code):
            response_error(f"HAZOP row {row_code} not found", code=404)
        if row_code in _running_rows:
            response_error(f"A Red Team run on {row_code} is already in progress", code=409)
        if not env.llm_enabled:
            response_error("AI service disabled", code=503)

    async def run(
        self,
        row_code: str,
        max_proposals: int,
        focus: str,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> JSONResponse:
        """Run the Red Team graph to completion and return the RUN_FINISHED result."""
        replayed = await idempotency.get_replayed(f"red-team:{row_code}", user.id, idempotency_key)
        if replayed:
            return replayed
        await self._check(row_code)
        payload = RedTeamInput(row_code=row_code, max_proposals=max_proposals, focus=focus)
        result, error = None, None
        _running_rows.add(row_code)
        try:
            async for event in run_red_team(payload, new_id(), user.id):
                if event.type == "RUN_FINISHED":
                    result = event.data["result"]
                elif event.type == "RUN_ERROR":
                    error = event.data
        finally:
            _running_rows.discard(row_code)
        if error:
            if error.get("code") == "LLM_RATE_LIMITED":
                return response_error(error["message"], code=429)
            return response_error("AI service unavailable, please retry", code=500)
        response = response_success(result)
        return await idempotency.remember(f"red-team:{row_code}", user.id, idempotency_key, response)

    async def run_stream(
        self,
        row_code: str,
        max_proposals: int,
        focus: str,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> StreamingResponse:
        """Stream the Red Team graph as AG-UI events (proposal, judge_verdict, approval_queued)."""
        await self._check(row_code)
        payload = RedTeamInput(row_code=row_code, max_proposals=max_proposals, focus=focus)

        async def frames() -> AsyncIterator[str]:
            counter = FrameCounter()
            _running_rows.add(row_code)
            try:
                async for event in run_red_team(payload, new_id(), user.id):
                    yield counter.frame(event.type, **event.data)
            finally:
                _running_rows.discard(row_code)

        return StreamingResponse(frames(), media_type="text/event-stream", headers=SSE_HEADERS)

    async def get_run(self, run_id: str) -> JSONResponse:
        """Return a finished run in the same shape as RUN_FINISHED.result."""
        run = await AgentRunRepository(self.db).get_by_id(run_id) if is_uuid(run_id) else None
        if not run or run.agent != AgentName.RED_TEAM or not isinstance(run.output, dict):
            return response_error(f"Red Team run {run_id} not found", code=404)
        result = dict(run.output)
        approvals = ApprovalItemRepository(self.db)
        proposals = []
        for proposal in result.get("proposals", []):
            proposal = dict(proposal)
            proposal.pop("judge", None)
            if proposal.get("approval_item_id"):
                item = await approvals.get_by_id(proposal["approval_item_id"])
                proposal["decision"] = item.decision.value if item else None
            proposals.append(proposal)
        result["proposals"] = proposals
        result["started_at"] = run.started_at
        result["latency_ms"] = run.latency_ms
        return response_success(result)
