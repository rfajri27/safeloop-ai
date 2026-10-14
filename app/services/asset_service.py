"""Asset service for the Asset health screen.

Endpoints served:
    GET /assets                     - Asset list with health index and band
    GET /assets/{tag}               - Asset detail, standby, last band change, linked rows
    GET /assets/{tag}/trend         - Sensor series for one tag and the alert line
    GET /assets/{tag}/health-history - Health index per replay hour

Reads: assets, asset_links, sensor_tags, sensor_readings, health_assessments
"""
import math
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.risk_engine import tightened_alert_assets
from app.models.asset_model import Asset
from app.models.sensor_tag_model import SensorTag
from app.repositories.asset_repository import AssetRepository
from app.repositories.health_assessment_repository import HealthAssessmentRepository
from app.repositories.process_node_repository import ProcessNodeRepository
from app.repositories.sensor_reading_repository import SensorReadingRepository
from app.repositories.sensor_tag_repository import SensorTagRepository
from app.services.live_state import get_live_run, list_asset_health, list_hazop_rows
from app.services.plant_model import PlantModel, load_plant_model
from app.utils.response import response_error, response_success

MAX_TREND_POINTS = 500
SUMMARY_WINDOW_HOURS = 6


def _num(value) -> Optional[float]:
    return float(value) if value is not None else None


def _trend_summary(sensor_tag: SensorTag, points: list[dict]) -> str:
    """Chart text alternative from a code template (never the LLM)."""
    label = sensor_tag.description or sensor_tag.tag
    unit = sensor_tag.eng_unit if sensor_tag.eng_unit not in ("-", "") else ""
    if not points:
        return f"No readings for {label} in the current run yet."
    window = [p for p in points if p["replay_hour"] >= points[-1]["replay_hour"] - SUMMARY_WINDOW_HOURS]
    first, last = window[0]["value"], window[-1]["value"]
    hours = window[-1]["replay_hour"] - window[0]["replay_hour"]
    threshold = max(abs(first) * 0.02, 0.05)
    span = f"over the last {hours} replay hour{'s' if hours != 1 else ''}"
    if last - first > threshold:
        text = f"{label} rose from {first:.1f} to {last:.1f} {unit} {span}."
    elif first - last > threshold:
        text = f"{label} fell from {first:.1f} to {last:.1f} {unit} {span}."
    else:
        text = f"{label} held steady near {last:.1f} {unit} {span}."
    alert = _num(sensor_tag.alert_high)
    if alert is not None and last >= alert:
        text += f" It is above the {alert:g} {unit} alert line."
    return " ".join(text.split()).replace(" .", ".")


class AssetService:
    """
    Service for assets and their health.

    REQUEST-SCOPED: Created per request with injected session.
    """

    def __init__(self, db: AsyncSession):
        """Initialize AssetService with a DB session."""
        self.db = db

    async def get_assets(
        self,
        node: Optional[str] = None,
        band: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> JSONResponse:
        """List monitored assets with their latest health index and band (null before a run)."""
        run = await get_live_run(self.db)
        items = await list_asset_health(self.db, run, node_code=node)
        if band:
            items = [item for item in items if item["band"] == band.value]

        return response_success(
            items[skip:skip + limit],
            metadata={"total": len(items), "skip": skip, "limit": limit}
        )

    async def get_asset(self, tag: str) -> JSONResponse:
        """Return asset detail; 404 for an unknown tag."""
        assets = AssetRepository(self.db)
        asset = await assets.get_by_tag(tag)
        if not asset:
            return response_error(f"Asset {tag} not found", code=404)

        plant = await load_plant_model(self.db)
        run = await get_live_run(self.db)
        health_repo = HealthAssessmentRepository(self.db)
        node = await ProcessNodeRepository(self.db).get_by_id(asset.node_id) if asset.node_id else None

        async def health_of(target: Asset) -> tuple[Optional[int], Optional[str]]:
            if not run:
                return None, None
            latest = await health_repo.get_latest_for_asset(run.id, target.id)
            return (latest.health_index, latest.band.value) if latest else (None, None)

        health_index, band = await health_of(asset)
        standby = await assets.get_standby_for(asset.id)
        standby_view = None
        if standby:
            standby_hi, standby_band = await health_of(standby)
            standby_view = {"tag": standby.tag, "health_index": standby_hi, "band": standby_band}

        last_change = await health_repo.get_last_band_change(run.id, asset.id) if run else None
        tightened = tightened_alert_assets(plant.rows, plant.rule_set) if plant and plant.rule_set else set()

        return response_success({
            "tag": asset.tag,
            "name": asset.name,
            "asset_class": asset.asset_class,
            "criticality": asset.criticality,
            "is_monitored": asset.is_monitored,
            "origin": asset.origin.value,
            "node": {"code": node.code, "name": node.name} if node else None,
            "health_index": health_index,
            "band": band,
            "standby": standby_view,
            "last_band_change": {
                "at": last_change.created_at,
                "replay_hour": last_change.replay_hour,
                "from": last_change.previous_band.value,
                "to": last_change.band.value,
                "health_index": last_change.health_index,
            } if last_change else None,
            "alert_tightened": asset.tag in tightened,
            "sensor_tags": [
                {
                    "tag": t.tag,
                    "description": t.description,
                    "eng_unit": t.eng_unit,
                    "alert_high": _num(t.alert_high),
                    "alert_high_tightened": _num(t.alert_high_tightened),
                    "origin": t.origin.value,
                    "source_dataset": t.source_dataset,
                    "drives_health": plant is not None and plant.driver_tags.get(asset.tag) == t.tag,
                }
                for t in await self._sensor_tags(asset, plant)
            ],
            "feeds_rows": await self._feeds_rows(asset, plant, run),
        })

    async def get_trend(
        self,
        tag: str,
        sensor_tag: Optional[str],
        from_hour: int,
        to_hour: Optional[int]
    ) -> JSONResponse:
        """Return at most 500 points (downsampled) plus a code-template summary."""
        asset = await AssetRepository(self.db).get_by_tag(tag)
        if not asset:
            return response_error(f"Asset {tag} not found", code=404)
        plant = await load_plant_model(self.db)
        tags = await self._sensor_tags(asset, plant)
        if not tags:
            return response_error(f"Asset {tag} has no sensor tags", code=404)

        if sensor_tag:
            selected = next((t for t in tags if t.tag == sensor_tag), None)
            if not selected:
                return response_error(f"Sensor tag {sensor_tag} not found on {tag}", code=404)
        else:
            driver = plant.driver_tags.get(asset.tag) if plant else None
            selected = next((t for t in tags if t.tag == driver), tags[0])

        run = await get_live_run(self.db)
        readings = await SensorReadingRepository(self.db).get_series(run.id, selected.id, from_hour, to_hour) if run else []
        points = [{"replay_hour": r.replay_hour, "value": round(float(r.value), 3)} for r in readings]
        stride = math.ceil(len(points) / MAX_TREND_POINTS) if len(points) > MAX_TREND_POINTS else 1
        sampled = points[::stride]
        if points and sampled[-1] is not points[-1]:
            sampled.append(points[-1])

        tightened = tightened_alert_assets(plant.rows, plant.rule_set) if plant and plant.rule_set else set()
        alert_high = _num(selected.alert_high)
        alert_tight = _num(selected.alert_high_tightened)
        return response_success({
            "sensor_tag": selected.tag,
            "description": selected.description,
            "eng_unit": selected.eng_unit,
            "alert_high": alert_high,
            "alert_high_tightened": alert_tight,
            "alert_line": alert_tight if asset.tag in tightened and alert_tight is not None else alert_high,
            "origin": selected.origin.value,
            "source_dataset": selected.source_dataset,
            "run_id": run.id if run else None,
            "downsampled": stride > 1,
            "points": sampled,
            "summary": _trend_summary(selected, points),
        })

    async def get_health_history(self, tag: str) -> JSONResponse:
        """Return [{replay_hour, health_index, band}] for the current run."""
        asset = await AssetRepository(self.db).get_by_tag(tag)
        if not asset:
            return response_error(f"Asset {tag} not found", code=404)
        run = await get_live_run(self.db)
        history = await HealthAssessmentRepository(self.db).get_history(run.id, asset.id) if run else []
        return response_success(
            [{"replay_hour": h.replay_hour, "health_index": h.health_index, "band": h.band.value} for h in history],
            metadata={"run_id": run.id if run else None, "total": len(history)},
        )

    async def _sensor_tags(self, asset: Asset, plant: Optional[PlantModel]) -> list[SensorTag]:
        """The asset's own tags plus the tag that drives its health model (V-201 is driven by LT-201's level)."""
        tags = list(await SensorTagRepository(self.db).list_by_asset(asset.id))
        driver = plant.sensor_tags.get(plant.driver_tags.get(asset.tag, "")) if plant else None
        if driver and all(t.id != driver.id for t in tags):
            tags.insert(0, driver)
        return tags

    async def _feeds_rows(self, asset: Asset, plant: Optional[PlantModel], run) -> list[dict]:
        """Current rows the asset causes, or protects through a safeguard dependency, with live risk."""
        if not plant:
            return []
        relation = {}
        for row in plant.rows:
            if row.cause_asset == asset.tag:
                relation[row.row_code] = "cause"
            elif any(asset.tag in sg.depends_on for sg in row.safeguards):
                relation[row.row_code] = "safeguard_dependency"
        out = []
        for live in await list_hazop_rows(self.db, run):
            if live.row.row_code not in relation:
                continue
            summary = live.summary
            out.append({
                "row_code": summary["row_code"],
                "deviation": summary["deviation"],
                "severity": summary["severity"],
                "likelihood_base": summary["likelihood_base"],
                "likelihood_live": summary["likelihood_live"],
                "score": summary["score_live"],
                "band": summary["band_live"],
                "rule": ", ".join(live.rescore.rules_applied) if live.rescore else None,
                "safeguards": [sg["ref_code"] for sg in summary["safeguards"]],
                "relation": relation[live.row.row_code],
            })
        return out
