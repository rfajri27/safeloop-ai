"""Replay service for starting and controlling scenario replays.

Endpoints served:
    POST /replay-runs                  - Start S1 or S2 at 1x, 3x or 8x (202)
    GET  /replay-runs/current          - Current run, state, hour, speed
    POST /replay-runs/{run_id}/actions - Pause, resume, change speed, reset

Writes: replay_runs, sensor_readings, health_assessments, risk_rescores, approval_items, audit_log
(the per-hour writes happen in app/services/replay_runtime.py)
"""
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import AgentName
from app.models.replay_run_model import ReplayRun
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.replay_run_repository import ReplayRunRepository
from app.schemas.auth_schema import CurrentUser
from app.services import unit_events
from app.services.audit_records import audit_entry
from app.services.plant_model import DEFAULT_UNIT, load_plant_model
from app.services.replay_runtime import FINISHED, PAUSED, RUNNING, replay_manager
from app.utils import idempotency
from app.utils.ids import is_uuid
from app.utils.live_cache import live_cached
from app.utils.response import response_error, response_success

WITHDRAW_REASON = "Replay run reset; the re-score is no longer live."


class ReplayService:
    """
    Service for replay runs.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ReplayService with a DB session."""
        self.db = db
        self.runs = ReplayRunRepository(db)
        self.audit = AuditLogRepository(db)

    async def start_run(
        self,
        scenario: str,
        speed: int,
        from_reset: bool,
        user: CurrentUser,
        idempotency_key: Optional[str] = None
    ) -> JSONResponse:
        """Start a replay run; 409 if one is already active for the unit.

        A finished run (all 240 hours played, not yet reset) is closed first
        when `from_reset` is true, so S2 can follow S1 without a manual reset.
        """
        replayed = await idempotency.get_replayed("replay-runs", user.id, idempotency_key)
        if replayed:
            return replayed

        active = await self.runs.get_active()
        if active:
            state = replay_manager.state_of(active)
            if state == FINISHED and from_reset:
                await self._close(active, user, state)
            else:
                return response_error(f"Replay {active.scenario_code} is already {state}; reset it first", code=409)

        plant = await load_plant_model(self.db, DEFAULT_UNIT)
        if not plant or not plant.health_models or not plant.rule_set:
            return response_error("Demo data is not seeded; run POST /admin/seed first", code=409)

        run = ReplayRun(scenario_code=scenario, speed=speed, started_by=user.id)
        try:
            await self.runs.add(run)
            await self.audit.add(audit_entry(
                "replay_started", "replay_runs", run.id,
                text=f"Scenario {scenario} started{' from reset' if from_reset else ''} at {speed}x",
                outcome="logged", actor_user=user.id, replay_run_id=run.id, replay_hour=0,
                scenario=scenario, speed=speed, from_reset=from_reset,
            ))
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            return response_error("A replay run is already active", code=409)

        await replay_manager.launch(run, plant)
        await unit_events.publish(plant.unit_code, [
            ("replay_state", {"run_id": run.id, "state": RUNNING, "speed": speed, "scenario": scenario}),
        ])
        response = response_success(self._view(run, RUNNING, 0), msg="Accepted", code=202)
        return await idempotency.remember("replay-runs", user.id, idempotency_key, response)

    @live_cached
    async def get_current_run(self) -> JSONResponse:
        """Return the active run with state, replay_hour and speed (data is null when none)."""
        run = await self.runs.get_active()
        if not run:
            return response_success(None, msg="No active replay run")
        return response_success(self._view(run, replay_manager.state_of(run), await self._hour(run)))

    async def apply_action(
        self,
        run_id: str,
        action: str,
        speed: Optional[int],
        user: CurrentUser
    ) -> JSONResponse:
        """Pause, resume, set_speed or reset; writes an audit event and a `replay_state` SSE event."""
        run = await self.runs.get_by_id(run_id) if is_uuid(run_id) else None
        if not run:
            return response_error(f"Replay run {run_id} not found", code=404)
        state = replay_manager.state_of(run)
        if state == "reset":
            return response_error("Replay run was already reset", code=409)

        if action == "reset":
            await self._close(run, user, state)
            return response_success(self._view(run, "reset", run.final_hour))

        if state == FINISHED:
            return response_error("Replay already finished; reset it or start a new run", code=409)
        hour = await self._hour(run)

        if action == "pause":
            if state != RUNNING:
                return response_error("Replay is not running", code=409)
            replay_manager.pause(run.id)
            new_state, text = PAUSED, f"Scenario {run.scenario_code} paused at replay hour {hour}"
        elif action == "resume":
            if state != PAUSED:
                return response_error("Replay is not paused", code=409)
            if replay_manager.get(run.id):
                replay_manager.resume(run.id)
            else:
                await replay_manager.attach(run)
            new_state, text = RUNNING, f"Scenario {run.scenario_code} resumed at replay hour {hour}"
        else:  # set_speed
            if speed == run.speed:
                return response_success(self._view(run, state, hour), msg="Speed unchanged")
            previous = run.speed
            run.speed = speed
            replay_manager.set_speed(run.id, speed)
            new_state, text = state, f"Replay speed changed from {previous}x to {speed}x"

        await self.audit.add(audit_entry(
            {"pause": "replay_paused", "resume": "replay_resumed", "set_speed": "replay_speed_changed"}[action],
            "replay_runs", run.id, text=text, outcome="logged", actor_user=user.id,
            replay_run_id=run.id, replay_hour=hour, speed=run.speed,
        ))
        await self.db.commit()
        await unit_events.publish(DEFAULT_UNIT, [
            ("replay_state", {"run_id": run.id, "state": new_state, "speed": run.speed, "replay_hour": hour}),
        ])
        return response_success(self._view(run, new_state, hour))

    async def _close(self, run: ReplayRun, user: CurrentUser, state: str) -> None:
        """Reset: stop the task, close the run, withdraw its pending re-scores; history stays."""
        last = await replay_manager.stop(run.id)
        if last is None:
            last = run.final_hour if run.final_hour is not None else await self._hour(run)
        await self.runs.end_run(run, last)
        withdrawn = await ApprovalItemRepository(self.db).withdraw_pending_rescores(run.id, WITHDRAW_REASON)
        await self.audit.add(audit_entry(
            "replay_reset", "replay_runs", run.id,
            text=f"Scenario {run.scenario_code} reset at replay hour {last}; HAZOP rows back to design basis",
            outcome="logged", actor_user=user.id, replay_run_id=run.id, replay_hour=last,
            previous_state=state,
        ))
        if withdrawn:
            await self.audit.add(audit_entry(
                "rescore_withdrawn", "replay_runs", run.id,
                text=f"{len(withdrawn)} pending re-score item{'s' if len(withdrawn) != 1 else ''} withdrawn: replay reset",
                outcome="logged", actor_agent=AgentName.RISK_ENGINE, replay_run_id=run.id, replay_hour=last,
                approval_item_ids=list(withdrawn),
            ))
        await self.db.commit()
        events = [("replay_state", {"run_id": run.id, "state": "reset", "speed": run.speed, "replay_hour": last})]
        pending = await ApprovalItemRepository(self.db).count_pending()
        events += [
            ("approval_changed", {"approval_item_id": item_id, "decision": "rejected", "pending_count": pending})
            for item_id in withdrawn
        ]
        await unit_events.publish(DEFAULT_UNIT, events)

    async def _hour(self, run: ReplayRun) -> int:
        hour = replay_manager.hour_of(run)
        if hour is None:
            hour = await HealthAssessmentRepository(self.db).get_latest_hour(run.id)
        return hour or 0

    @staticmethod
    def _view(run: ReplayRun, state: str, hour: Optional[int]) -> dict:
        return {
            "run_id": run.id,
            "scenario": run.scenario_code,
            "state": state,
            "speed": run.speed,
            "replay_hour": hour or 0,
            "started_at": run.started_at,
            "started_by": run.started_by,
            "ended_at": run.ended_at,
        }
