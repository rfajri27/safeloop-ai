"""Approval service for the human-in-the-loop approval queue.

Endpoints served:
    GET  /approval-items                    - Queue, filter by decision and type
    GET  /approval-items/{item_id}          - Item with draft, Judge checks and audit record
    POST /approval-items/{item_id}/decision - Approve, or reject with a reason

Writes (one transaction): approval_items, hazop_rows, hazop_recommendations, audit_log
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.judge import normalize_tag
from app.models.approval_item_model import ApprovalItem
from app.models.columns import utcnow
from app.models.enums import (
    AgentName, ApprovalDecision, ArtifactType, GuideWord, HazopParam, RecordStatus, UserRole,
)
from app.models.hazop_recommendation_model import HazopRecommendation
from app.models.hazop_row_model import HazopRow
from app.models.hazop_row_safeguard_model import HazopRowSafeguard
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.citation_repository import CitationRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.hazop_proposal_repository import HazopProposalRepository
from app.repositories.hazop_row_repository import HazopRowRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.judge_verdict_repository import JudgeVerdictRepository
from app.repositories.risk_rescore_repository import RiskRescoreRepository
from app.repositories.risk_rule_set_repository import RiskRuleSetRepository
from app.repositories.safeguard_repository import SafeguardRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import CurrentUser
from app.services import unit_events
from app.services.audit_records import audit_entry, audit_id
from app.services.live_state import risk_band
from app.services.plant_model import DEFAULT_UNIT
from app.services.replay_runtime import replay_manager
from app.utils.ids import is_uuid
from app.utils.response import response_error, response_success

EDITABLE_FIELDS = (
    "title", "guide_word", "parameter", "deviation", "cause", "consequence",
    "severity", "likelihood", "safeguards", "recommendation",
)


class ApprovalService:
    """
    Service for approval items.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ApprovalService with a DB session."""
        self.db = db
        self.items = ApprovalItemRepository(db)

    async def get_items(
        self,
        decision: Optional[str] = None,
        artifact_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List approval items newest first."""
        items = await self.items.list_filtered(decision, artifact_type, skip, limit)
        total = await self.items.count_filtered(decision, artifact_type)
        return response_success(
            [await self._summary(item) for item in items],
            metadata={"total": total, "skip": skip, "limit": limit,
                      "pending": await self.items.count_pending()},
        )

    async def get_item(self, item_id: str) -> JSONResponse:
        """Return the item with full draft, Judge checks, citations and audit block."""
        item = await self.items.get_by_id(item_id) if is_uuid(item_id) else None
        if not item:
            return response_error(f"Approval item {item_id} not found", code=404)
        return response_success(await self._detail(item))

    async def decide(
        self,
        item_id: str,
        decision: str,
        reason: Optional[str],
        edited_body: Optional[dict[str, Any]],
        user: CurrentUser
    ) -> JSONResponse:
        """Decide once (409 if not pending); approving a proposal creates a new hazop_rows version."""
        if user.role != UserRole.PROCESS_SAFETY_ENGINEER:
            return response_error(f"Role {user.role.value} cannot decide approvals", code=403)
        existing = await self.items.get_by_id(item_id) if is_uuid(item_id) else None
        if not existing:
            return response_error(f"Approval item {item_id} not found", code=404)

        reason = (reason or "").strip() or None
        item = await self.items.decide(item_id, ApprovalDecision(decision), user.id, reason, edited_body)
        if not item:
            await self.db.rollback()
            return response_error("Approval item already decided", code=409)

        effect = None
        if decision == "approved":
            if item.artifact_type == ArtifactType.HAZOP_CHANGE:
                effect = await self._apply_proposal(item, user)
            elif item.artifact_type == ArtifactType.RISK_RESCORE:
                effect = await self._accept_rescore(item)

        title = item.title
        logged_effect = {k: v for k, v in (effect or {}).items() if k != "created_row"} or None
        audit = audit_entry(
            decision, "approval_items", item.id,
            text=f"{user.name} {decision} {title}" + (f": {reason}" if reason else ""),
            outcome=decision, sources=0, actor_user=user.id,
            artifact_type=item.artifact_type.value, reason=reason, effect=logged_effect,
            edited=edited_body is not None,
        )
        await AuditLogRepository(self.db).add(audit)
        await self.db.commit()

        if effect and effect.pop("created_row", False):
            replay_manager.mark_rows_changed()
        pending = await self.items.count_pending()
        await unit_events.publish(DEFAULT_UNIT, [
            ("approval_changed", {"approval_item_id": item.id, "decision": decision, "pending_count": pending}),
        ])
        return response_success({
            "id": item.id,
            "decision": decision,
            "decided_by": user.name,
            "decided_at": item.decided_at,
            "reason": reason,
            "effect": effect,
            "audit_id": audit_id(audit.id),
        })

    # ------------------------------------------------------------------ effects
    async def _apply_proposal(self, item: ApprovalItem, user: CurrentUser) -> dict:
        """New HAZOP row (new scenario) or new version of the row (worsened), same transaction."""
        proposal = await HazopProposalRepository(self.db).get_by_id(item.proposal_id)
        rows = HazopRowRepository(self.db)
        target = await rows.get_by_id(proposal.target_row_id)
        draft = {**(item.body or {}), **{k: v for k, v in (item.edited_body or {}).items() if k in EDITABLE_FIELDS}}
        kind = draft.get("kind", "new_scenario")

        if kind == "worsened":
            current = await rows.get_current_by_code(target.row_code) or target
            row_code, version, supersedes = current.row_code, current.version + 1, current
        else:
            row_code = draft.get("proposed_row_code") or f"{target.row_code}a"
            version, supersedes = await rows.get_next_version(row_code), None

        cause_asset_id = await self._cause_asset(draft, target)
        new_row = HazopRow(
            node_id=target.node_id, row_code=row_code, version=version,
            guide_word=GuideWord(draft.get("guide_word", target.guide_word.value)),
            parameter=HazopParam(draft.get("parameter", target.parameter.value)),
            deviation=draft.get("deviation") or target.deviation,
            cause=draft.get("cause") or target.cause,
            cause_asset_id=cause_asset_id,
            consequence=draft.get("consequence") or target.consequence,
            severity=int(draft.get("severity") or target.severity),
            likelihood_base=int(draft.get("likelihood") or target.likelihood_base),
            status=RecordStatus.APPROVED,
            supersedes_id=supersedes.id if supersedes else None,
            created_by_agent=AgentName.RED_TEAM,
            created_by_user=user.id,
        )
        if supersedes:
            await rows.supersede(supersedes)
        await rows.add(new_row)

        safeguards = await SafeguardRepository(self.db).list_by_ref_codes(draft.get("safeguards") or [])
        self.db.add_all(HazopRowSafeguard(hazop_row_id=new_row.id, safeguard_id=sg.id, credited=True) for sg in safeguards)
        if draft.get("recommendation"):
            self.db.add(HazopRecommendation(
                hazop_row_id=new_row.id, text=draft["recommendation"], owner_role=UserRole.PROCESS_SAFETY_ENGINEER,
            ))
        proposal.resulting_row_id = new_row.id
        await self.db.flush()
        return {
            "hazop_row_code": new_row.row_code, "version": new_row.version, "status": new_row.status.value,
            "hazop_row_id": new_row.id, "supersedes_version": supersedes.version if supersedes else None,
            "created_row": True,
        }

    async def _cause_asset(self, draft: dict, target: HazopRow) -> Optional[str]:
        """The first named entity that appears in the cause text, else the target row's cause asset."""
        entities = draft.get("entities") or []
        cause = normalize_tag(draft.get("cause") or "")
        named = [e for e in entities if normalize_tag(e) in cause]
        assets = await AssetRepository(self.db).list_by_tags(named) if named else []
        by_key = {normalize_tag(a.tag): a.id for a in assets}
        for entity in named:
            if normalize_tag(entity) in by_key:
                return by_key[normalize_tag(entity)]
        return target.cause_asset_id

    async def _accept_rescore(self, item: ApprovalItem) -> dict:
        """The live likelihood is accepted as the row's current assessment; the row itself is unchanged."""
        rescore = await RiskRescoreRepository(self.db).get_by_id(item.rescore_id)
        row = await HazopRowRepository(self.db).get_by_id(rescore.hazop_row_id)
        return {
            "hazop_row_code": row.row_code, "version": row.version, "status": RecordStatus.APPROVED.value,
            "likelihood_accepted": rescore.likelihood_new, "score_accepted": rescore.score_new,
        }

    # ------------------------------------------------------------------- views
    async def _source(self, item: ApprovalItem) -> tuple[str, Optional[str]]:
        """('Risk Engine · R-L-01 v1', None) or ('Red Team · redteam.v1 · Node 1', 'pass')."""
        if item.artifact_type == ArtifactType.RISK_RESCORE:
            body = item.body or {}
            rules = ", ".join(body.get("rules_applied") or [])
            return f"Risk Engine · {rules} {body.get('rule_set_version', '')}".strip(), None
        verdict = await JudgeVerdictRepository(self.db).get_by_id(item.judge_verdict_id) if item.judge_verdict_id else None
        node = (item.body or {}).get("node")
        node_label = f" · Node {node.lstrip('N')}" if node else ""
        return f"Red Team · {(item.body or {}).get('prompt_version', 'redteam.v1')}{node_label}", verdict.verdict.value if verdict else None

    async def _summary(self, item: ApprovalItem) -> dict:
        source, judge = await self._source(item)
        reference = item.decided_at if item.decision != ApprovalDecision.PENDING and item.decided_at else utcnow()
        return {
            "id": item.id,
            "artifact_type": item.artifact_type.value,
            "title": item.title,
            "source": source,
            "judge": judge,
            "confidence": item.confidence,
            "decision": item.decision.value,
            "age_s": round((utcnow() - item.created_at).total_seconds(), 1),
            "created_at": item.created_at,
            "decided_at": item.decided_at,
            "open_for_s": round((reference - item.created_at).total_seconds(), 1),
        }

    async def _detail(self, item: ApprovalItem) -> dict:
        data = await self._summary(item)
        decided_by = await UserRepository(self.db).get_by_id(item.decided_by) if item.decided_by else None
        decision_audit = None
        if item.decision != ApprovalDecision.PENDING:
            decision_audit = await AuditLogRepository(self.db).get_latest_for_entity("approval_items", item.id)
        data.update({
            "decided_by": decided_by.display_name if decided_by else (None if item.decision == ApprovalDecision.PENDING else "System"),
            "decision_reason": item.decision_reason,
            "edited_body": item.edited_body,
            "audit_id": audit_id(decision_audit.id) if decision_audit else None,
        })
        if item.artifact_type == ArtifactType.RISK_RESCORE:
            data.update(await self._rescore_detail(item))
        else:
            data.update(await self._proposal_detail(item))
        return data

    async def _rescore_detail(self, item: ApprovalItem) -> dict:
        rescore = await RiskRescoreRepository(self.db).get_by_id(item.rescore_id)
        row = await HazopRowRepository(self.db).get_by_id(rescore.hazop_row_id)
        rule_set = await RiskRuleSetRepository(self.db).get_by_id(rescore.rule_set_id)
        health = await HealthAssessmentRepository(self.db).get_by_id(rescore.trigger_health_id) if rescore.trigger_health_id else None
        asset = await AssetRepository(self.db).get_by_id(health.asset_id) if health else None
        drafted = await AuditLogRepository(self.db).get_latest_for_entity("risk_rescores", rescore.id)
        citations = await CitationRepository(self.db).list_by_owner(rescore_id=rescore.id)
        return {
            "draft": {
                "row_code": row.row_code,
                "deviation": row.deviation,
                "likelihood_old": rescore.likelihood_old,
                "likelihood_new": rescore.likelihood_new,
                "severity": rescore.severity,
                "score_old": rescore.score_old,
                "score_new": rescore.score_new,
                "band_old": risk_band(rescore.score_old),
                "band_new": risk_band(rescore.score_new),
                "rules_applied": list(rescore.rules_applied),
                "rule_set_version": rule_set.version if rule_set else None,
                "safeguards_lost": (item.body or {}).get("safeguards_lost", []),
                "replay_run_id": rescore.replay_run_id,
                "trigger": {
                    "asset_tag": asset.tag if asset else None,
                    "band": health.band.value,
                    "previous_band": health.previous_band.value if health.previous_band else None,
                    "health_index": health.health_index,
                    "replay_hour": health.replay_hour,
                } if health else None,
            },
            "checks": [],
            "citations": [{"index": i, "target_type": c.target_type.value, "label": c.raw_ref, "resolved": c.resolved}
                          for i, c in enumerate(citations, start=1)],
            "audit": {
                "agent": "Risk Engine",
                "model_id": None,
                "prompt_version": None,
                "rule_set_version": rule_set.version if rule_set else None,
                "sources": len(citations),
                "judge": None,
                "drafted_at": rescore.computed_at,
                "audit_id": audit_id(drafted.id) if drafted else None,
            },
        }

    async def _proposal_detail(self, item: ApprovalItem) -> dict:
        body = dict(item.body or {})
        verdict = await JudgeVerdictRepository(self.db).get_by_id(item.judge_verdict_id) if item.judge_verdict_id else None
        citations = await CitationRepository(self.db).list_by_owner(proposal_id=item.proposal_id) if item.proposal_id else []
        chunks = {c.id: (c, d) for c, d in await DocumentChunkRepository(self.db).list_with_documents(
            [c.chunk_id for c in citations if c.chunk_id])}
        proposal = await HazopProposalRepository(self.db).get_by_id(item.proposal_id) if item.proposal_id else None
        run = await AgentRunRepository(self.db).get_by_id(proposal.agent_run_id) if proposal else None
        drafted = await AuditLogRepository(self.db).get_latest_for_entity("hazop_proposals", proposal.id) if proposal else None
        cite_view = []
        for index, citation in enumerate(citations, start=1):
            entry = {"index": index, "ref": citation.raw_ref, "target_type": citation.target_type.value,
                     "resolved": citation.resolved, "label": citation.raw_ref}
            if citation.chunk_id in chunks:
                chunk, doc = chunks[citation.chunk_id]
                entry.update({"doc_code": doc.doc_code, "chunk_id": chunk.id, "section": chunk.section, "label": None})
            cite_view.append(entry)
        return {
            "draft": {k: v for k, v in body.items() if k not in ("verdict", "citations")},
            "checks": (body.get("verdict") or {}).get("checks", []),
            "judge_reason": verdict.reason if verdict else None,
            "citations": cite_view,
            "audit": {
                "agent": "Red Team",
                "model_id": run.model_id if run else None,
                "prompt_version": body.get("prompt_version", "redteam.v1"),
                "sources": len(citations),
                "judge": verdict.verdict.value if verdict else None,
                "drafted_at": run.started_at if run else item.created_at,
                "run_id": run.id if run else None,
                "audit_id": audit_id(drafted.id) if drafted else None,
            },
        }
