"""Unit service for the Unit 100 overview screen and live events.

Endpoints served:
    GET /units/{unit_code}/overview      - Headline, health tiles, matrix summary, loop stages, activity
    GET /units/{unit_code}/events/stream - Live replay, health, risk and approval events (SSE)

Reads: units, assets, health_assessments, hazop_rows, risk_rescores, approval_items, audit_log
"""
import time
from typing import AsyncIterator, Optional
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import AgentName
from app.models.replay_run_model import ReplayRun
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.process_node_repository import ProcessNodeRepository
from app.repositories.risk_rescore_repository import RiskRescoreRepository
from app.repositories.risk_rule_set_repository import RiskRuleSetRepository
from app.repositories.unit_repository import UnitRepository
from app.repositories.user_repository import UserRepository
from app.services import unit_events
from app.services.audit_records import actor_label, audit_id
from app.services.replay_runtime import replay_manager
from app.services.live_state import (
    RISK_BANDS,
    LiveHazopRow,
    get_live_run,
    list_asset_health,
    list_hazop_rows,
    risk_band,
)
from app.utils.response import response_error, response_success
from app.utils.sse import SSE_HEADERS, sse_frame, sse_ping

HEADLINE_TONES = {"critical": "critical", "degraded": "warning", "healthy": "success"}
ACTIVITY_LIMIT = 10
PING_SECONDS = 15


class UnitService:
    """
    Service for unit-level views.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize UnitService with a DB session."""
        self.db = db

    async def get_overview(self, unit_code: str) -> JSONResponse:
        """Build the one-call Overview payload. Headline text comes from code templates, never the LLM."""
        unit = await UnitRepository(self.db).get_by_code(unit_code)
        if not unit:
            return response_error(f"Unit {unit_code} not found", code=404)

        run = await get_live_run(self.db)
        tiles = await list_asset_health(self.db, run, unit_id=unit.id)
        rows = await list_hazop_rows(self.db, run, unit_id=unit.id)
        nodes = await ProcessNodeRepository(self.db).list_by_unit(unit.id)
        moved = [live for live in rows if live.summary["likelihood_live"] != live.row.likelihood_base]

        matrix_summary = {name: 0 for _, name in reversed(RISK_BANDS)}
        for live in rows:
            matrix_summary[live.summary["band_live"]] += 1
        matrix_summary["moved"] = len(moved)

        headline, loop_times = await self._headline(run, rows)
        pending = await ApprovalItemRepository(self.db).count_pending()
        red_team = await self._red_team_summary(run, loop_times)

        return response_success({
            "unit": {
                "code": unit.code,
                "name": unit.name,
                "nodes": len(nodes),
                "assets": len(tiles),
                "hazop_rows": len(rows),
            },
            "replay": await self._replay(run),
            "headline": headline,
            "health_tiles": tiles,
            "matrix_summary": matrix_summary,
            "rescored_rows": [
                {
                    "row_code": live.row.row_code,
                    "deviation": live.row.deviation,
                    "likelihood_old": live.row.likelihood_base,
                    "likelihood_new": live.summary["likelihood_live"],
                    "severity": live.row.severity,
                    "score_old": live.row.likelihood_base * live.row.severity,
                    "score_new": live.summary["score_live"],
                }
                for live in moved
            ],
            "red_team_summary": red_team,
            "loop": [
                {"stage": "sense", "done": loop_times["sense_at"] is not None, "at": loop_times["sense_at"]},
                {"stage": "rescore", "done": loop_times["rescore_s"] is not None, "offset_s": loop_times["rescore_s"]},
                {"stage": "red_team", "done": red_team is not None, "offset_s": loop_times["red_team_s"]},
                {"stage": "approve", "done": red_team is not None and pending == 0, "pending": pending},
            ],
            "activity": await self._activity(run),
        })

    async def _replay(self, run: Optional[ReplayRun]) -> Optional[dict]:
        """Replay strip; the hour is the last one the Health Agent assessed."""
        if not run:
            return None
        hour = replay_manager.hour_of(run)
        if hour is None:
            hour = await HealthAssessmentRepository(self.db).get_latest_hour(run.id)
        return {
            "run_id": run.id,
            "scenario": run.scenario_code,
            "state": replay_manager.state_of(run),
            "speed": run.speed,
            "replay_hour": hour or 0,
        }

    async def _red_team_summary(self, run: Optional[ReplayRun], loop_times: dict) -> Optional[dict]:
        """Latest Red Team run (since the replay started, when one is live)."""
        latest = await AgentRunRepository(self.db).get_latest(AgentName.RED_TEAM, since=run.started_at if run else None)
        loop_times["red_team_s"] = None
        if not latest or not isinstance(latest.output, dict):
            return None
        proposals = latest.output.get("proposals", [])
        passed = sum(1 for p in proposals if (p.get("verdict") or {}).get("verdict") == "pass")
        if loop_times.get("sense_dt"):
            loop_times["red_team_s"] = round((latest.started_at - loop_times["sense_dt"]).total_seconds(), 1)
        return {
            "run_id": latest.id,
            "row_code": latest.output.get("row_code"),
            "proposals": len(proposals),
            "passed": passed,
            "blocked": len(proposals) - passed,
        }

    async def _headline(self, run: Optional[ReplayRun], rows: list[LiveHazopRow]) -> tuple[dict, dict]:
        """Headline for the latest band change, plus the sense/rescore times for the loop strip."""
        loop_times = {"sense_at": None, "sense_dt": None, "rescore_s": None}
        if not run:
            return {
                "tone": "neutral",
                "title": "No replay running. HAZOP rows show design-basis risk.",
                "detail": "Start scenario S1 or S2 to stream sensor data.",
                "latency_s": None,
                "link": None,
            }, loop_times

        health_repo = HealthAssessmentRepository(self.db)
        changes = await health_repo.list_band_changes(run.id)
        if not changes:
            return {
                "tone": "info",
                "title": f"Scenario {run.scenario_code} running. No health band changes yet.",
                "detail": f"Replaying at {run.speed}x. All HAZOP rows are at design-basis risk.",
                "latency_s": None,
                "link": None,
            }, loop_times

        change = changes[-1]
        asset = await AssetRepository(self.db).get_by_id(change.asset_id)
        history = await health_repo.get_history(run.id, change.asset_id)
        before = [h for h in history if h.replay_hour < change.replay_hour]
        previous_hi = before[-1].health_index if before else None
        loop_times["sense_at"] = change.created_at.isoformat()
        loop_times["sense_dt"] = change.created_at

        rescores = await RiskRescoreRepository(self.db).list_by_trigger(change.id)
        codes = {live.row.id: live.row.row_code for live in rows}
        title = (
            f"{asset.tag} moved from {change.previous_band.value.title()} to {change.band.value.title()}. "
            f"{len(rescores)} linked HAZOP row{'' if len(rescores) == 1 else 's'} "
            f"{'was' if len(rescores) == 1 else 'were'} re-scored."
        )
        detail = f"Health index {previous_hi} → {change.health_index}." if previous_hi is not None \
            else f"Health index {change.health_index}."
        latency_s, link = None, None
        if rescores:
            rescores = sorted(rescores, key=lambda r: -r.score_new)
            moves = ", ".join(
                f"{codes.get(r.hazop_row_id, '?')} {risk_band(r.score_old).title()} → {risk_band(r.score_new).title()}"
                for r in rescores
            )
            rules = sorted({rule for r in rescores for rule in r.rules_applied})
            rule_set = await RiskRuleSetRepository(self.db).get_by_id(rescores[0].rule_set_id)
            version = f" {rule_set.version}" if rule_set else ""
            detail += f" {moves}. Rule {', '.join(rules)}{version}."
            latency_s = round((min(r.computed_at for r in rescores) - change.created_at).total_seconds(), 2)
            loop_times["rescore_s"] = latency_s
            link = {"screen": "matrix", "row_code": codes.get(rescores[0].hazop_row_id)}

        return {
            "tone": HEADLINE_TONES[change.band.value],
            "title": title,
            "detail": detail,
            "latency_s": latency_s,
            "link": link,
        }, loop_times

    async def _activity(self, run: Optional[ReplayRun]) -> list[dict]:
        """Latest audit events for the run (all events when no run is active), newest first."""
        events = await AuditLogRepository(self.db).list_filtered(
            replay_run_id=run.id if run else None, limit=ACTIVITY_LIMIT
        )
        users = UserRepository(self.db)
        names: dict[str, str] = {}
        for user_id in {e.actor_user for e in events if e.actor_user}:
            user = await users.get_by_id(user_id)
            names[user_id] = user.display_name if user else "Unknown user"
        return [
            {
                "audit_id": audit_id(event.id),
                "at": event.occurred_at.isoformat(),
                "text": (event.detail or {}).get("text") or event.action.replace("_", " ").capitalize(),
                "actor": actor_label(event, names),
            }
            for event in events
        ]

    async def stream_events(
        self,
        unit_code: str,
        last_event_id: Optional[str] = None
    ) -> StreamingResponse:
        """Stream the Redis stream `unit:{code}:events`, replaying entries after Last-Event-ID.

        Each entry is one AG-UI CUSTOM frame whose `id` is the Redis entry id. A
        `: ping` comment goes out after 15 s without a frame.
        """
        unit = await UnitRepository(self.db).get_by_code(unit_code)
        if not unit:
            return response_error(f"Unit {unit_code} not found", code=404)
        return StreamingResponse(
            self._event_frames(unit.code, last_event_id),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    @staticmethod
    async def _event_frames(unit_code: str, last_event_id: Optional[str]) -> AsyncIterator[str]:
        last_sent = time.monotonic()
        yield sse_ping()
        async for batch in unit_events.follow(unit_code, last_event_id):
            for entry_id, name, value in batch:
                yield sse_frame(entry_id, {"type": "CUSTOM", "name": name, "value": value})
                last_sent = time.monotonic()
            if not batch and time.monotonic() - last_sent >= PING_SECONDS:
                yield sse_ping()
                last_sent = time.monotonic()
