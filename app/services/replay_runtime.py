"""In-process replay task: replay clock -> health engine -> risk engine -> one transaction -> Redis.

One asyncio task per active run (spec Section 9.1). Each tick (2.0 s / speed)
it reads the next replay hour of the scenario file and, in one transaction,
writes the sensor readings and every monitored asset's health assessment. A
band change adds, in the same transaction, the risk re-scores, a re-score
approval item per re-scored row, their citations and audit records
(single-transaction operation 1). After commit the tick's events go to the
Redis stream `unit:{code}:events`.

The database is the source of truth for a run: a run whose task is gone (the
process restarted) shows as paused, and resuming rebuilds the engine state by
replaying the scenario file up to the last hour written. The engines are
deterministic, so the rebuilt state is identical.

One Uvicorn worker is assumed (spec Section 12): the task lives in-process.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from sqlalchemy import update
from config.databases.postgresql import AsyncSessionLocal
from config.settings import env
from app.engines.health_engine import HealthTracker
from app.engines.replay_engine import (
    TRIP_ASSET, TRIP_LIMIT, TRIP_STANDBY, TRIP_TAG, Scenario, get_scenario, tick_seconds,
)
from app.engines.risk_engine import RowScore, rescore, score_row, score_rows
from app.models.approval_item_model import ApprovalItem
from app.models.citation_model import Citation
from app.models.columns import utcnow
from app.models.enums import (
    AgentName, ApprovalDecision, ArtifactType, CitationTarget, DocType, HealthBand,
)
from app.models.health_assessment_model import HealthAssessment
from app.models.replay_run_model import ReplayRun
from app.models.risk_rescore_model import RiskRescore
from app.models.sensor_reading_model import SensorReading
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.services import unit_events
from app.services.audit_records import audit_entry
from app.services.plant_model import PlantModel, load_plant_model, load_row_inputs
from app.utils.ids import new_id

logger = logging.getLogger(__name__)

RUNNING, PAUSED, FINISHED = "running", "paused", "finished"
TAG_WINDOW_HOURS = 6


@dataclass
class RunControl:
    """Live state of one replay run."""
    run_id: str
    scenario: Scenario
    plant: PlantModel
    speed: int
    started_by: Optional[str]
    state: str = PAUSED
    next_hour: int = 0
    trackers: list[HealthTracker] = field(default_factory=list)
    bands: dict[str, str] = field(default_factory=dict)
    last_hi: dict[str, int] = field(default_factory=dict)
    scores: dict[str, RowScore] = field(default_factory=dict)
    trip_hour: Optional[int] = None
    rows_stale: bool = False
    task: Optional[asyncio.Task] = None
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def last_hour(self) -> Optional[int]:
        return self.next_hour - 1 if self.next_hour > 0 else None


def _build_state(ctl: RunControl, upto_hour: Optional[int]) -> None:
    """(Re)build tracker, band and score state by replaying hours 0..upto_hour (no writes)."""
    ctl.trackers = [HealthTracker(model, ctl.plant.policy) for model in ctl.plant.health_models]
    ctl.bands = {t.model.asset: "healthy" for t in ctl.trackers}
    ctl.last_hi = {}
    for hour in range(0, (upto_hour if upto_hour is not None else -1) + 1):
        values = ctl.scenario.hours[hour]
        for tracker in ctl.trackers:
            step = tracker.step(hour, values[tracker.model.driver_tag])
            ctl.bands[step.asset] = step.band
            ctl.last_hi[step.asset] = step.health_index
    rule_set = ctl.plant.rule_set
    ctl.scores = score_rows(ctl.plant.rows, ctl.bands, rule_set) if rule_set else {}
    ctl.next_hour = (upto_hour + 1) if upto_hour is not None else 0
    ctl.trip_hour = ctl.scenario.trip_hour()


class ReplayManager:
    """Owns the replay tasks of this process."""

    def __init__(self):
        self._runs: dict[str, RunControl] = {}

    # ------------------------------------------------------------------ queries
    def get(self, run_id: str) -> Optional[RunControl]:
        return self._runs.get(run_id)

    def state_of(self, run: ReplayRun) -> str:
        """running / paused / finished. A run with no task in this process is paused."""
        if run.ended_at is not None:
            return "reset"
        if run.final_hour is not None:
            return FINISHED
        ctl = self._runs.get(run.id)
        return ctl.state if ctl else PAUSED

    def hour_of(self, run: ReplayRun) -> Optional[int]:
        """Last replay hour written, if this process knows it."""
        ctl = self._runs.get(run.id)
        return ctl.last_hour if ctl else None

    # ----------------------------------------------------------------- controls
    async def launch(self, run: ReplayRun, plant: PlantModel, resume_from: Optional[int] = None) -> RunControl:
        """Create the run's control state and start its task (from hour 0, or after resume_from)."""
        scenario = get_scenario(str(env.demo_data_path), run.scenario_code)
        ctl = RunControl(run_id=run.id, scenario=scenario, plant=plant, speed=run.speed, started_by=run.started_by)
        _build_state(ctl, resume_from)
        ctl.state = RUNNING
        ctl.resume_event.set()
        self._runs[run.id] = ctl
        ctl.task = asyncio.create_task(self._loop(ctl), name=f"replay-{run.id}")
        return ctl

    async def attach(self, run: ReplayRun) -> RunControl:
        """Resume a run whose task is gone, continuing after the last hour in the database."""
        async with AsyncSessionLocal() as db:
            plant = await load_plant_model(db)
            last_hour = await HealthAssessmentRepository(db).get_latest_hour(run.id)
        return await self.launch(run, plant, resume_from=last_hour)

    def pause(self, run_id: str) -> None:
        ctl = self._runs[run_id]
        ctl.state = PAUSED
        ctl.resume_event.clear()

    def resume(self, run_id: str) -> None:
        ctl = self._runs[run_id]
        ctl.state = RUNNING
        ctl.resume_event.set()

    def mark_rows_changed(self) -> None:
        """An approval changed the register; the next band change reloads the rows."""
        for ctl in self._runs.values():
            ctl.rows_stale = True

    def set_speed(self, run_id: str, speed: int) -> None:
        ctl = self._runs.get(run_id)
        if ctl:
            ctl.speed = speed

    async def stop(self, run_id: str) -> Optional[int]:
        """Cancel a run's task (reset). Returns the last hour written."""
        ctl = self._runs.pop(run_id, None)
        if not ctl:
            return None
        await self._cancel(ctl)
        return ctl.last_hour

    async def shutdown(self) -> None:
        for ctl in list(self._runs.values()):
            await self._cancel(ctl)
        self._runs.clear()

    @staticmethod
    async def _cancel(ctl: RunControl) -> None:
        if ctl.task and not ctl.task.done():
            ctl.task.cancel()
            try:
                await ctl.task
            except (asyncio.CancelledError, Exception):
                pass

    # --------------------------------------------------------------------- loop
    async def _loop(self, ctl: RunControl) -> None:
        loop = asyncio.get_running_loop()
        try:
            while ctl.next_hour < ctl.scenario.length:
                await ctl.resume_event.wait()
                started = loop.time()
                hour = ctl.next_hour
                try:
                    await self._tick(ctl, hour)
                except Exception:
                    # Roll the in-memory state back to the last committed hour and pause.
                    logger.exception("Replay %s failed at hour %s; pausing", ctl.run_id, hour)
                    _build_state(ctl, hour - 1 if hour > 0 else None)
                    ctl.state = PAUSED
                    ctl.resume_event.clear()
                    await unit_events.publish(ctl.plant.unit_code, [
                        ("replay_state", {"run_id": ctl.run_id, "state": PAUSED, "speed": ctl.speed, "reason": "tick_failed"}),
                    ])
                    continue
                ctl.next_hour = hour + 1
                delay = tick_seconds(ctl.speed, env.replay_seconds_per_hour) - (loop.time() - started)
                if delay > 0:
                    await asyncio.sleep(delay)
            await self._finish(ctl)
        except asyncio.CancelledError:
            raise

    async def _tick(self, ctl: RunControl, hour: int) -> None:
        plant = ctl.plant
        values = ctl.scenario.hours[hour]
        previous_hi = dict(ctl.last_hi)
        steps = [t.step(hour, values[t.model.driver_tag]) for t in ctl.trackers]
        events: list[tuple[str, dict[str, Any]]] = [("replay_tick", {
            "run_id": ctl.run_id,
            "replay_hour": hour,
            "readings": {tag: round(value, 4) for tag, value in values.items()},
            "health": {s.asset: {"health_index": s.health_index, "band": s.band} for s in steps},
        })]

        async with AsyncSessionLocal() as db:
            now = utcnow()
            db.add_all(
                SensorReading(
                    replay_run_id=ctl.run_id,
                    tag_id=plant.sensor_tags[tag].id,
                    replay_hour=hour,
                    ts=now,
                    value=value,
                )
                for tag, value in values.items() if tag in plant.sensor_tags
            )
            assessments: dict[str, HealthAssessment] = {}
            for step in steps:
                asset_id = plant.asset_ids.get(step.asset)
                if not asset_id:
                    continue
                assessments[step.asset] = HealthAssessment(
                    id=new_id(),
                    replay_run_id=ctl.run_id,
                    asset_id=asset_id,
                    replay_hour=hour,
                    health_index=step.health_index,
                    band=HealthBand(step.band),
                    previous_band=HealthBand(step.previous_band) if step.previous_band else None,
                    model_version=plant.policy.version,
                    created_at=now,
                )
            db.add_all(assessments.values())
            await db.flush()

            for step in steps:
                ctl.last_hi[step.asset] = step.health_index
                if step.band_changed and step.asset in assessments:
                    events.extend(await self._band_change(
                        db, ctl, hour, step, assessments[step.asset], previous_hi.get(step.asset),
                    ))

            if ctl.trip_hour == hour:
                trip = audit_entry(
                    "asset_trip", "assets", plant.asset_ids.get(TRIP_ASSET, ctl.run_id),
                    text=f"{TRIP_ASSET} tripped on high vibration ({TRIP_TAG} ≥ {TRIP_LIMIT} mm/s); "
                         f"{TRIP_STANDBY} takes over reflux duty",
                    outcome="logged", sources=1, actor_agent=AgentName.HEALTH_AGENT,
                    model_id=plant.policy.version, replay_run_id=ctl.run_id, replay_hour=hour,
                    asset_tag=TRIP_ASSET, standby=TRIP_STANDBY, value=round(values[TRIP_TAG], 3),
                )
                db.add(trip)
                await db.flush()
                events.append(("trip", {
                    "asset_tag": TRIP_ASSET, "standby": TRIP_STANDBY, "replay_hour": hour,
                    "value": round(values[TRIP_TAG], 3), "audit_id": f"AUD-{trip.id:04d}",
                }))
            await db.commit()

        await unit_events.publish(plant.unit_code, events)

    async def _band_change(
        self,
        db,
        ctl: RunControl,
        hour: int,
        step,
        assessment: HealthAssessment,
        hi_before: Optional[int],
    ) -> list[tuple[str, dict[str, Any]]]:
        """Re-score linked rows and queue approvals; everything flushes in the tick's transaction.

        The engine runs before any further database work, so `computed_at` minus
        the assessment time is the in-process band-change-to-re-score latency.
        """
        plant = ctl.plant
        rule_set = plant.rule_set
        previous_bands = dict(ctl.bands)
        ctl.bands[step.asset] = step.band

        changes = []
        if rule_set:
            if ctl.rows_stale:
                # Rows approved during the run join the engine with their score before this change.
                plant.rows = await load_row_inputs(db, plant.unit_id)
                ctl.rows_stale = False
                for row in plant.rows:
                    if row.row_code not in ctl.scores:
                        ctl.scores[row.row_code] = score_row(row, previous_bands, rule_set)
            changes, ctl.scores = rescore(plant.rows, ctl.bands, ctl.scores, rule_set)
        rescores = [
            RiskRescore(
                id=new_id(),
                hazop_row_id=c.row_id,
                rule_set_id=plant.rule_set_row.id,
                replay_run_id=ctl.run_id,
                trigger_health_id=assessment.id,
                likelihood_old=c.likelihood_old,
                likelihood_new=c.likelihood_new,
                severity=c.severity,
                score_old=c.score_old,
                score_new=c.score_new,
                rules_applied=list(c.rules_applied),
                safeguards_lost=list(c.safeguard_ids_lost),
                computed_at=utcnow(),
            )
            for c in changes
        ]

        health_audit = audit_entry(
            "health_band_changed", "health_assessments", assessment.id,
            text=f"{step.asset} HealthBandChanged: {step.previous_band.title()} → {step.band.title()}, "
                 f"HI {step.health_index}",
            outcome="logged", sources=1, actor_agent=AgentName.HEALTH_AGENT,
            model_id=plant.policy.version, replay_run_id=ctl.run_id, replay_hour=hour,
            asset_tag=step.asset, previous_band=step.previous_band, band=step.band,
            health_index=step.health_index, health_index_old=hi_before,
            trigger_tag=step.driver_tag, trigger_value=round(step.driver_value, 3),
            rows_rescored=[c.row_code for c in changes],
        )
        db.add(health_audit)
        db.add_all(rescores)
        await db.flush()
        events: list[tuple[str, dict[str, Any]]] = [("health_band_changed", {
            "asset_tag": step.asset,
            "health_index": step.health_index,
            "previous_band": step.previous_band,
            "band": step.band,
            "replay_hour": hour,
            "audit_id": f"AUD-{health_audit.id:04d}",
        })]
        if not changes:
            return events

        items = [
            ApprovalItem(
                id=new_id(),
                artifact_type=ArtifactType.RISK_RESCORE,
                title=(
                    f"{c.row_code} · {c.band_old.title()} → {c.band_new.title()}" if c.band_old != c.band_new
                    else f"{c.row_code} · {c.band_new.title()} {c.score_old} → {c.score_new}"
                ),
                asset_id=plant.asset_ids.get(step.asset),
                rescore_id=r.id,
                confidence="high",
                decision=ApprovalDecision.PENDING,
                body={
                    "row_code": c.row_code,
                    "rules_applied": list(c.rules_applied),
                    "rule_set_version": rule_set.version,
                    "safeguards_lost": list(c.safeguards_lost),
                    "replay_run_id": ctl.run_id,
                    "replay_hour": hour,
                },
            )
            for c, r in zip(changes, rescores)
        ]
        db.add_all(items)
        await db.flush()

        citations_by_rescore = await self._rescore_citations(db, ctl, hour, step, changes, rescores)
        db.add_all(c for cites in citations_by_rescore.values() for c in cites)

        audits = [
            audit_entry(
                "risk_rescore", "risk_rescores", r.id,
                text=f"{c.row_code} L{c.likelihood_old} → L{c.likelihood_new} "
                     f"({c.band_old.title()} → {c.band_new.title()})",
                outcome="queued", sources=len(citations_by_rescore.get(r.id, [])),
                actor_agent=AgentName.RISK_ENGINE, rule_set_version=rule_set.version,
                replay_run_id=ctl.run_id, replay_hour=hour,
                row_code=c.row_code, rules_applied=list(c.rules_applied),
                safeguards_lost=list(c.safeguards_lost), score_old=c.score_old, score_new=c.score_new,
                trigger_asset=step.asset, approval_item_id=item.id,
            )
            for c, r, item in zip(changes, rescores, items)
        ]
        db.add_all(audits)
        await db.flush()

        pending = await ApprovalItemRepository(db).count_pending()
        for c, r, item, audit in zip(changes, rescores, items, audits):
            latency_ms = int((r.computed_at - assessment.created_at).total_seconds() * 1000)
            events.append(("risk_rescored", {
                "row_code": c.row_code,
                "score_old": c.score_old,
                "score_new": c.score_new,
                "likelihood_old": c.likelihood_old,
                "likelihood_new": c.likelihood_new,
                "band_new": c.band_new,
                "rules_applied": list(c.rules_applied),
                "safeguards_lost": list(c.safeguards_lost),
                "rule_set_version": rule_set.version,
                "latency_ms": latency_ms,
                "audit_id": f"AUD-{audit.id:04d}",
            }))
            events.append(("approval_changed", {
                "approval_item_id": item.id, "decision": "pending", "pending_count": pending,
            }))
        return events

    async def _rescore_citations(self, db, ctl, hour, step, changes, rescores) -> dict[str, list[Citation]]:
        """Evidence for each re-score: the driver tag's manual section, the HAZOP node, the tag window, the cause asset."""
        plant = ctl.plant
        chunks = DocumentChunkRepository(db)
        driver = await chunks.find_current(text_contains=step.driver_tag)
        sensor_tag = plant.sensor_tags.get(step.driver_tag)
        out: dict[str, list[Citation]] = {}
        for change, rescore_row in zip(changes, rescores):
            cites = []
            if driver:
                cites.append(Citation(target_type=CitationTarget.CHUNK, chunk_id=driver[0][0].id, rescore_id=rescore_row.id,
                                      raw_ref=f"doc:{driver[0][1].doc_code}#{driver[0][0].section}"))
            node = plant.row_nodes.get(change.row_code, "")
            node_section = f"node-{node.lstrip('N')}" if node else None
            hazop = await chunks.find_current(doc_type=DocType.HAZOP, section=node_section) if node_section else []
            if hazop:
                cites.append(Citation(target_type=CitationTarget.CHUNK, chunk_id=hazop[0][0].id, rescore_id=rescore_row.id,
                                      raw_ref=f"doc:{hazop[0][1].doc_code}#{hazop[0][0].section}"))
            if sensor_tag:
                cites.append(Citation(target_type=CitationTarget.TAG_WINDOW, tag_id=sensor_tag.id, rescore_id=rescore_row.id,
                                      hour_from=max(0, hour - TAG_WINDOW_HOURS), hour_to=hour,
                                      raw_ref=f"tag:{step.driver_tag}@{max(0, hour - TAG_WINDOW_HOURS)}-{hour}"))
            asset_id = plant.asset_ids.get(step.asset)
            if asset_id:
                cites.append(Citation(target_type=CitationTarget.ASSET, asset_id=asset_id, hazop_row_id=change.row_id,
                                      rescore_id=rescore_row.id, raw_ref=f"asset:{step.asset}->{change.row_code}"))
            out[rescore_row.id] = cites
        return out

    async def _finish(self, ctl: RunControl) -> None:
        """Mark the run finished (it stays live until reset) and tell the stream."""
        last = ctl.scenario.length - 1
        async with AsyncSessionLocal() as db:
            await db.execute(update(ReplayRun).where(ReplayRun.id == ctl.run_id).values(final_hour=last))
            db.add(audit_entry(
                "replay_finished", "replay_runs", ctl.run_id,
                text=f"Scenario {ctl.scenario.code} finished at replay hour {last}",
                outcome="logged", actor_user=ctl.started_by, replay_run_id=ctl.run_id, replay_hour=last,
            ))
            await db.commit()
        ctl.state = FINISHED
        await unit_events.publish(ctl.plant.unit_code, [
            ("replay_state", {"run_id": ctl.run_id, "state": FINISHED, "speed": ctl.speed, "replay_hour": last}),
        ])


# SINGLETON: replay tasks of this process
replay_manager = ReplayManager()
