"""HAZOP service for the register, live risk matrix and rule sets.

Endpoints served:
    GET /hazop-rows                - Register grouped by node, live risk
    GET /hazop-rows/matrix         - Design-basis and live cells for every row
    GET /hazop-rows/{row_code}     - One row, versions, safeguards, proposals
    GET /hazop-rows/{row_code}/why - Trigger, rules, safeguards and citations for the last re-score
    GET /risk-rule-sets/active     - Active rule set and version

Reads: hazop_rows, hazop_row_safeguards, safeguards, safeguard_dependencies,
       risk_rescores, risk_rule_sets, citations
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.corpus import section_title, headings_in
from app.models.enums import CitationTarget
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.citation_repository import CitationRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.hazop_proposal_repository import HazopProposalRepository
from app.repositories.hazop_recommendation_repository import HazopRecommendationRepository
from app.repositories.hazop_row_repository import HazopRowRepository
from app.repositories.hazop_row_safeguard_repository import HazopRowSafeguardRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.judge_verdict_repository import JudgeVerdictRepository
from app.repositories.process_node_repository import ProcessNodeRepository
from app.repositories.risk_rule_set_repository import RiskRuleSetRepository
from app.repositories.safeguard_dependency_repository import SafeguardDependencyRepository
from app.repositories.sensor_reading_repository import SensorReadingRepository
from app.repositories.sensor_tag_repository import SensorTagRepository
from app.services.audit_records import audit_id
from app.services.live_state import get_live_run, list_asset_health, list_hazop_rows, risk_band
from app.services.plant_model import load_plant_model
from app.utils.live_cache import live_cached
from app.utils.response import response_error, response_success

WHY_RULES = ("R-L-01", "R-L-02", "R-S-01")


def chunk_heading(text: str) -> Optional[str]:
    """Title of a chunk's first heading, e.g. 'Bearing lubrication and vibration limits'."""
    headings = headings_in(text)
    return section_title(headings[0]) if headings else None


class HazopService:
    """
    Service for HAZOP rows and risk.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize HazopService with a DB session."""
        self.db = db

    @live_cached
    async def get_rows(
        self,
        node: Optional[str] = None,
        band: Optional[str] = None,
        rescored: Optional[bool] = None
    ) -> JSONResponse:
        """Return {nodes: [{code, name, rows: [HazopRowSummary]}]} sorted by row code."""
        run = await get_live_run(self.db)
        nodes: dict[str, dict] = {}
        for live in await list_hazop_rows(self.db, run, node_code=node):
            if band and live.summary["band_live"] != band.value:
                continue
            if rescored is not None and live.summary["rescored_this_run"] != rescored:
                continue
            group = nodes.setdefault(live.node.code, {"code": live.node.code, "name": live.node.name, "rows": []})
            group["rows"].append(live.summary)

        return response_success({"nodes": [nodes[code] for code in sorted(nodes)]})

    @live_cached
    async def get_matrix(self) -> JSONResponse:
        """Return all 25 cells with live and design-basis rows, moved rows and rule set version."""
        run = await get_live_run(self.db)
        rows = await list_hazop_rows(self.db, run)
        moved = [live for live in rows if live.summary["likelihood_live"] != live.row.likelihood_base]
        moved_codes = {live.row.row_code for live in moved}

        cells = []
        for likelihood in range(5, 0, -1):
            for severity in range(1, 6):
                score = likelihood * severity
                cells.append({
                    "likelihood": likelihood,
                    "severity": severity,
                    "score": score,
                    "band": risk_band(score),
                    "live": [
                        live.row.row_code for live in rows
                        if live.summary["likelihood_live"] == likelihood and live.row.severity == severity
                    ],
                    # Design-basis position of rows that moved (where they came from).
                    "design_basis": [
                        live.row.row_code for live in rows
                        if live.row.row_code in moved_codes
                        and live.row.likelihood_base == likelihood and live.row.severity == severity
                    ],
                })

        rule_set = await RiskRuleSetRepository(self.db).get_active()
        return response_success({
            "cells": cells,
            "moved": [
                {
                    "row_code": live.row.row_code,
                    "from": {"likelihood": live.row.likelihood_base, "severity": live.row.severity},
                    "to": {"likelihood": live.summary["likelihood_live"], "severity": live.row.severity},
                }
                for live in moved
            ],
            "rule_set_version": rule_set.version if rule_set else None,
            "run_id": run.id if run else None,
        })

    @live_cached
    async def get_row(self, row_code: str) -> JSONResponse:
        """Return one row with versions, safeguards and proposals; 404 if unknown."""
        rows_repo = HazopRowRepository(self.db)
        row = await rows_repo.get_current_by_code(row_code)
        if not row:
            return response_error(f"HAZOP row {row_code} not found", code=404)

        run = await get_live_run(self.db)
        live = next((r for r in await list_hazop_rows(self.db, run) if r.row.id == row.id), None)
        node = await ProcessNodeRepository(self.db).get_by_id(row.node_id)
        cause = await AssetRepository(self.db).get_by_id(row.cause_asset_id) if row.cause_asset_id else None
        versions = await rows_repo.list_versions(row_code)

        return response_success({
            **(live.summary if live else {}),
            "id": row.id,
            "node": {"code": node.code, "name": node.name} if node else None,
            "cause_asset": cause.tag if cause else None,
            "created_at": row.created_at,
            "created_by_agent": row.created_by_agent.value if row.created_by_agent else None,
            "supersedes_id": row.supersedes_id,
            "versions": [
                {
                    "id": v.id,
                    "version": v.version,
                    "status": v.status.value,
                    "likelihood_base": v.likelihood_base,
                    "severity": v.severity,
                    "created_at": v.created_at,
                    "created_by_agent": v.created_by_agent.value if v.created_by_agent else None,
                }
                for v in versions
            ],
            "safeguards": await self._safeguards(row.id, run, live),
            "recommendations": [
                {"text": r.text, "owner_role": r.owner_role.value if r.owner_role else None}
                for r in await HazopRecommendationRepository(self.db).list_by_row(row.id)
            ],
            "proposals": await self._proposals([v.id for v in versions]),
        })

    @live_cached
    async def get_why(self, row_code: str) -> JSONResponse:
        """Return the "Why it moved" panel; unmoved rows return live = design_basis and trigger = null."""
        row = await HazopRowRepository(self.db).get_current_by_code(row_code)
        if not row:
            return response_error(f"HAZOP row {row_code} not found", code=404)

        run = await get_live_run(self.db)
        live = next((r for r in await list_hazop_rows(self.db, run) if r.row.id == row.id), None)
        rule_set = await RiskRuleSetRepository(self.db).get_active()
        rule_texts = {r["id"]: r.get("text", r["id"]) for r in (rule_set.rules.get("rules", []) if rule_set else [])}
        rescore = live.rescore if live else None
        base_score = row.likelihood_base * row.severity
        design_basis = {
            "likelihood": row.likelihood_base, "severity": row.severity,
            "score": base_score, "band": risk_band(base_score),
        }
        live_view = design_basis
        if rescore:
            live_view = {
                "likelihood": rescore.likelihood_new, "severity": row.severity,
                "score": rescore.score_new, "band": risk_band(rescore.score_new),
            }

        data = {
            "row_code": row.row_code,
            "deviation": row.deviation,
            "cause": row.cause,
            "design_basis": design_basis,
            "live": live_view,
            "trigger": None,
            "rules": [
                {"rule_id": rid, "text": rule_texts.get(rid, rid), "applied": bool(rescore and rid in rescore.rules_applied)}
                for rid in WHY_RULES
            ],
            "rule_set_version": rule_set.version if rule_set else None,
            "safeguards": await self._safeguards(row.id, run, live),
            "citations": [],
            "latency_s": None,
            "audit_id": None,
        }
        if not rescore:
            return response_success(data)

        health = await HealthAssessmentRepository(self.db).get_by_id(rescore.trigger_health_id) if rescore.trigger_health_id else None
        if health:
            data["trigger"] = await self._trigger(health, run)
            data["latency_s"] = round((rescore.computed_at - health.created_at).total_seconds(), 3)
        data["citations"] = await self._rescore_citations(rescore.id)
        audit = await AuditLogRepository(self.db).get_latest_for_entity("risk_rescores", rescore.id)
        data["audit_id"] = audit_id(audit.id) if audit else None
        data["computed_at"] = rescore.computed_at
        return response_success(data)

    @live_cached
    async def get_active_rule_set(self) -> JSONResponse:
        """Return the active risk rule set and its version."""
        rule_set = await RiskRuleSetRepository(self.db).get_active()
        if not rule_set:
            return response_error("No active risk rule set; run POST /admin/seed first", code=404)
        rules = rule_set.rules or {}
        return response_success({
            **rules,
            "id": rule_set.id,
            "version": rule_set.version,
            "status": rule_set.status.value,
            "approved_by": rule_set.approved_by,
            "approved_at": rule_set.approved_at,
            "created_at": rule_set.created_at,
        })

    # ------------------------------------------------------------------ helpers
    async def _health_by_tag(self, run) -> dict[str, dict]:
        return {tile["tag"]: tile for tile in await list_asset_health(self.db, run)}

    async def _safeguards(self, row_id: str, run, live) -> list[dict]:
        """Safeguards credited against a row, with dependencies and their live health."""
        links = await HazopRowSafeguardRepository(self.db).list_for_row(row_id)
        deps = await SafeguardDependencyRepository(self.db).list_for_safeguards([sg.id for _, sg in links])
        depends_on: dict[str, list] = {}
        for dep, asset in deps:
            depends_on.setdefault(dep.safeguard_id, []).append(asset)
        lost = set(live.rescore.safeguards_lost or []) if live and live.rescore else set()
        health = await self._health_by_tag(run)
        out = []
        for link, sg in links:
            out.append({
                "ref_code": sg.ref_code,
                "type": sg.type.value,
                "description": sg.description,
                "credited": link.credited and sg.id not in lost,
                "last_test_date": sg.last_test_date,
                "depends_on": [
                    {
                        "tag": asset.tag,
                        "band": (health.get(asset.tag) or {}).get("band") or ("not_monitored" if not asset.is_monitored else None),
                        "health_index": (health.get(asset.tag) or {}).get("health_index"),
                    }
                    for asset in depends_on.get(sg.id, [])
                ],
            })
        return out

    async def _trigger(self, health, run) -> dict:
        """The band change behind a re-score: sensor value, health before and after."""
        asset = await AssetRepository(self.db).get_by_id(health.asset_id)
        plant = await load_plant_model(self.db)
        driver_tag = plant.driver_tags.get(asset.tag) if plant else None
        sensor_tag = await SensorTagRepository(self.db).get_by_tag(driver_tag) if driver_tag else None
        reading = None
        if sensor_tag:
            reading = await SensorReadingRepository(self.db).get_reading(health.replay_run_id, sensor_tag.id, health.replay_hour)
        history = await HealthAssessmentRepository(self.db).get_history(health.replay_run_id, health.asset_id)
        before = [h for h in history if h.replay_hour < health.replay_hour]
        return {
            "sensor_tag": driver_tag,
            "value": round(float(reading.value), 3) if reading else None,
            "eng_unit": sensor_tag.eng_unit if sensor_tag else None,
            "at": health.created_at,
            "replay_hour": health.replay_hour,
            "asset_tag": asset.tag,
            "health_index_old": before[-1].health_index if before else None,
            "health_index_new": health.health_index,
            "previous_band": health.previous_band.value if health.previous_band else None,
            "band": health.band.value,
        }

    async def _rescore_citations(self, rescore_id: str) -> list[dict]:
        citations = await CitationRepository(self.db).list_by_owner(rescore_id=rescore_id)
        chunk_ids = [c.chunk_id for c in citations if c.chunk_id]
        chunks = {chunk.id: (chunk, doc) for chunk, doc in await DocumentChunkRepository(self.db).list_with_documents(chunk_ids)}
        tags = {t.id: t.tag for t in await SensorTagRepository(self.db).get_all(limit=1000)}
        assets = AssetRepository(self.db)
        rows = HazopRowRepository(self.db)
        out = []
        order = {CitationTarget.CHUNK: 0, CitationTarget.TAG_WINDOW: 1, CitationTarget.ASSET: 2, CitationTarget.HAZOP_ROW: 3}
        for index, citation in enumerate(sorted(citations, key=lambda c: (order[c.target_type], c.raw_ref or "")), start=1):
            item = {"index": index, "target_type": citation.target_type.value, "resolved": citation.resolved, "ref": citation.raw_ref}
            if citation.target_type == CitationTarget.CHUNK and citation.chunk_id in chunks:
                chunk, doc = chunks[citation.chunk_id]
                item.update({
                    "doc_code": doc.doc_code, "chunk_id": chunk.id, "section": chunk.section,
                    "title": chunk_heading(chunk.text) or doc.title, "document_title": doc.title,
                    "revision": doc.revision, "is_synthetic": doc.origin.value == "synthetic",
                })
            elif citation.target_type == CitationTarget.TAG_WINDOW:
                item.update({"sensor_tag": tags.get(citation.tag_id), "hour_from": citation.hour_from, "hour_to": citation.hour_to})
            elif citation.target_type == CitationTarget.ASSET:
                asset = await assets.get_by_id(citation.asset_id) if citation.asset_id else None
                row = await rows.get_by_id(citation.hazop_row_id) if citation.hazop_row_id else None
                item["label"] = (
                    f"Unit 100 asset model: {asset.tag if asset else '?'} → {row.row_code} link" if row
                    else f"Unit 100 asset model: {asset.tag if asset else '?'}"
                )
            out.append(item)
        return out

    async def _proposals(self, row_ids: list[str]) -> list[dict]:
        """Red Team proposals made against any version of the row, newest run first."""
        proposals = await HazopProposalRepository(self.db).list_by_target_rows(row_ids)
        if not proposals:
            return []
        verdicts = {v.proposal_id: v for v in await JudgeVerdictRepository(self.db).list_by_proposals([p.id for p in proposals])}
        approvals = ApprovalItemRepository(self.db)
        runs = AgentRunRepository(self.db)
        out = []
        for proposal in proposals:
            run = await runs.get_by_id(proposal.agent_run_id)
            drafts = (run.output or {}).get("proposals", []) if run else []
            draft = next((d for d in drafts if d.get("proposal_id") == proposal.id), {})
            item = await approvals.get_by_proposal(proposal.id)
            verdict = verdicts.get(proposal.id)
            out.append({
                "proposal_id": proposal.id,
                "run_id": proposal.agent_run_id,
                "started_at": run.started_at if run else None,
                "kind": draft.get("kind"),
                "title": draft.get("title"),
                "proposed_row_code": draft.get("proposed_row_code"),
                "deviation": proposal.deviation,
                "cause": proposal.cause,
                "verdict": verdict.verdict.value if verdict else None,
                "reason": verdict.reason if verdict else None,
                "approval_item_id": item.id if item else None,
                "decision": item.decision.value if item else None,
                "resulting_row_id": proposal.resulting_row_id,
            })
        return sorted(out, key=lambda p: str(p["started_at"] or ""), reverse=True)
