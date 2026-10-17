"""Live plant state shared by the asset, HAZOP and unit screens.

"Live" means the active replay run. With no active run (none started yet, or
the last one was reset) assets have no health yet and every HAZOP row sits at
its design-basis likelihood.

Reads: replay_runs, assets, process_nodes, sensor_tags, health_assessments,
       hazop_rows, hazop_row_safeguards, safeguards, risk_rescores, approval_items
"""
import json
from dataclasses import dataclass
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import DataOrigin, RecordStatus
from app.models.hazop_row_model import HazopRow
from app.models.process_node_model import ProcessNode
from app.models.replay_run_model import ReplayRun
from app.models.risk_rescore_model import RiskRescore
from app.models.sensor_tag_model import SensorTag
from app.repositories.approval_item_repository import ApprovalItemRepository
from app.repositories.asset_repository import AssetRepository
from app.repositories.hazop_row_repository import HazopRowRepository
from app.repositories.hazop_row_safeguard_repository import HazopRowSafeguardRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.process_node_repository import ProcessNodeRepository
from app.repositories.replay_run_repository import ReplayRunRepository
from app.repositories.risk_rescore_repository import RiskRescoreRepository
from app.repositories.sensor_tag_repository import SensorTagRepository

# Risk matrix bands (spec 6.2): Low 1-4, Medium 5-9, High 10-14, Extreme 15-25.
RISK_BANDS = ((15, "extreme"), (10, "high"), (5, "medium"), (1, "low"))


def risk_band(score: int) -> str:
    """Band name for a likelihood x severity score."""
    return next(name for floor, name in RISK_BANDS if score >= floor)


async def get_live_run(db: AsyncSession) -> Optional[ReplayRun]:
    """The active replay run, or None."""
    return await ReplayRunRepository(db).get_active()


def _driver_tags(sensor_tags: Sequence[SensorTag]) -> dict[str, SensorTag]:
    """Asset tag -> the sensor tag that drives its health model (hi.v1).

    The seed stores each model in its driver tag's `transform` JSON, which is how
    V-201 and FV-201 get their provenance from transmitter tags (LT-201, FT-201).
    """
    drivers = {}
    for sensor_tag in sensor_tags:
        try:
            models = json.loads(sensor_tag.transform or "{}").get("health_models", [])
        except (ValueError, AttributeError):
            continue
        for model in models:
            drivers[model["asset"]] = sensor_tag
    return drivers


async def list_asset_health(
    db: AsyncSession,
    run: Optional[ReplayRun],
    unit_id: Optional[str] = None,
    node_code: Optional[str] = None
) -> list[dict]:
    """Monitored assets with their latest health in the run, by node then tag (asset list, health tiles)."""
    assets = await AssetRepository(db).list_by_unit(unit_id, node_code, monitored_only=True)
    if not assets:
        return []

    nodes = await ProcessNodeRepository(db).list_by_ids([a.node_id for a in assets if a.node_id])
    node_codes = {n.id: n.code for n in nodes}
    sensor_tags = await SensorTagRepository(db).get_all(limit=1000)
    drivers = _driver_tags(sensor_tags)
    own_tags = {}
    for sensor_tag in sensor_tags:
        own_tags.setdefault(sensor_tag.asset_id, sensor_tag)

    latest = {}
    if run:
        assessments = await HealthAssessmentRepository(db).get_latest_per_asset(run.id, [a.id for a in assets])
        latest = {h.asset_id: h for h in assessments}

    items = []
    for asset in assets:
        source = drivers.get(asset.tag) or own_tags.get(asset.id)
        health = latest.get(asset.id)
        items.append({
            "tag": asset.tag,
            "name": asset.name,
            "node": node_codes.get(asset.node_id),
            "health_index": health.health_index if health else None,
            "band": health.band.value if health else None,
            "origin": (source.origin if source else asset.origin).value,
            "source_dataset": source.source_dataset if source else None,
        })
    return sorted(items, key=lambda item: (item["node"] or "", item["tag"]))


@dataclass
class LiveHazopRow:
    """A current HAZOP row with its live risk (register, matrix, overview)."""
    row: HazopRow
    node: ProcessNode
    rescore: Optional[RiskRescore]
    summary: dict


async def list_hazop_rows(
    db: AsyncSession,
    run: Optional[ReplayRun],
    unit_id: Optional[str] = None,
    node_code: Optional[str] = None
) -> list[LiveHazopRow]:
    """Current HAZOP rows with live likelihood, score and band, sorted by row code."""
    pairs = await HazopRowRepository(db).list_current(node_code, unit_id)
    if not pairs:
        return []

    rescores = {}
    if run:
        rescores = {r.hazop_row_id: r for r in await RiskRescoreRepository(db).get_latest_per_row(run.id)}
    pending = set(await ApprovalItemRepository(db).list_pending_row_ids())
    links = await HazopRowSafeguardRepository(db).list_for_rows([row.id for row, _ in pairs])
    safeguards_by_row: dict[str, list] = {}
    for link, safeguard in links:
        safeguards_by_row.setdefault(link.hazop_row_id, []).append((link, safeguard))

    result = []
    for row, node in pairs:
        rescore = rescores.get(row.id)
        lost = set(rescore.safeguards_lost or []) if rescore else set()
        likelihood = rescore.likelihood_new if rescore else row.likelihood_base
        score = likelihood * row.severity
        status = RecordStatus.UNDER_REVIEW if row.id in pending else row.status
        result.append(LiveHazopRow(row=row, node=node, rescore=rescore, summary={
            "row_code": row.row_code,
            "version": row.version,
            "status": status.value,
            "guide_word": row.guide_word.value,
            "parameter": row.parameter.value,
            "deviation": row.deviation,
            "cause": row.cause,
            "consequence": row.consequence,
            "severity": row.severity,
            "likelihood_base": row.likelihood_base,
            "likelihood_live": likelihood,
            "score_live": score,
            "band_live": risk_band(score),
            "safeguards": [
                {
                    "ref_code": safeguard.ref_code,
                    "type": safeguard.type.value,
                    "credited": link.credited and safeguard.id not in lost,
                }
                for link, safeguard in safeguards_by_row.get(row.id, [])
            ],
            "rescored_this_run": rescore is not None,
            # The MVP register is the synthetic Unit 100 study.
            "origin": DataOrigin.SYNTHETIC.value,
        }))
    return sorted(result, key=lambda live: live.row.row_code)
