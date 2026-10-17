"""Engine inputs loaded from the database (the seeded source of truth).

The replay task, the evaluation runner and the HAZOP/asset views all build the
health and risk engine inputs here, so they never disagree:

- health models (hi.v1) from each driver sensor tag's `transform` JSON, with the
  band policy from data/seed/health_models.json `_meta`
- current HAZOP rows with their credited safeguards and safeguard dependencies
- the active risk rule set
"""
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from config.settings import env
from app.engines.health_engine import BandPolicy, HealthModel
from app.engines.risk_engine import RowInput, RuleSet, SafeguardInput
from app.models.risk_rule_set_model import RiskRuleSet
from app.models.sensor_tag_model import SensorTag
from app.repositories.asset_repository import AssetRepository
from app.repositories.hazop_row_repository import HazopRowRepository
from app.repositories.hazop_row_safeguard_repository import HazopRowSafeguardRepository
from app.repositories.risk_rule_set_repository import RiskRuleSetRepository
from app.repositories.safeguard_dependency_repository import SafeguardDependencyRepository
from app.repositories.sensor_tag_repository import SensorTagRepository
from app.repositories.unit_repository import UnitRepository

DEFAULT_UNIT = "U100"
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def band_policy() -> BandPolicy:
    """hi.v1 band policy from health_models.json, or the built-in hi.v1 defaults."""
    path = env.demo_data_path / "seed" / "health_models.json"
    try:
        return BandPolicy.from_meta(json.loads(path.read_text(encoding="utf-8")).get("_meta"))
    except (OSError, ValueError):
        logger.warning("health_models.json not readable at %s; using hi.v1 defaults", path)
        return BandPolicy()


def health_models_from_tags(sensor_tags: list[SensorTag]) -> list[HealthModel]:
    """Health models stored in the driver tags' transform JSON, in asset order."""
    models = []
    for sensor_tag in sensor_tags:
        try:
            entries = json.loads(sensor_tag.transform or "{}").get("health_models", [])
        except (ValueError, AttributeError):
            continue
        models.extend(HealthModel.from_dict(entry) for entry in entries)
    return sorted(models, key=lambda m: m.asset)


@dataclass
class PlantModel:
    unit_id: str
    unit_code: str
    health_models: list[HealthModel]
    policy: BandPolicy
    rows: list[RowInput]
    rule_set: Optional[RuleSet]
    rule_set_row: Optional[RiskRuleSet]
    asset_ids: dict[str, str] = field(default_factory=dict)
    asset_tags: dict[str, str] = field(default_factory=dict)
    sensor_tags: dict[str, SensorTag] = field(default_factory=dict)
    row_nodes: dict[str, str] = field(default_factory=dict)

    @property
    def driver_tags(self) -> dict[str, str]:
        """Asset tag -> driver sensor tag."""
        return {m.asset: m.driver_tag for m in self.health_models}


async def load_rule_set(db: AsyncSession) -> tuple[Optional[RiskRuleSet], Optional[RuleSet]]:
    """The active rule set row and its engine form."""
    row = await RiskRuleSetRepository(db).get_active()
    return row, (RuleSet.from_rules(row.version, row.rules) if row else None)


async def load_row_inputs(db: AsyncSession, unit_id: Optional[str] = None) -> list[RowInput]:
    """Current HAZOP rows as risk engine inputs."""
    pairs = await HazopRowRepository(db).list_current(unit_id=unit_id)
    rows = [row for row, _ in pairs]
    links = await HazopRowSafeguardRepository(db).list_for_rows([r.id for r in rows])
    deps = await SafeguardDependencyRepository(db).list_for_safeguards(list({sg.id for _, sg in links}))
    depends_on: dict[str, list[str]] = {}
    for dep, asset in deps:
        depends_on.setdefault(dep.safeguard_id, []).append(asset.tag)
    cause_ids = [r.cause_asset_id for r in rows if r.cause_asset_id]
    cause_tags = {a.id: a.tag for a in await AssetRepository(db).list_by_ids(cause_ids)}

    by_row: dict[str, list[SafeguardInput]] = {}
    for link, sg in links:
        by_row.setdefault(link.hazop_row_id, []).append(SafeguardInput(
            safeguard_id=sg.id,
            ref_code=sg.ref_code,
            type=sg.type.value,
            credited=link.credited,
            depends_on=tuple(depends_on.get(sg.id, [])),
        ))
    return [
        RowInput(
            row_id=r.id,
            row_code=r.row_code,
            severity=r.severity,
            likelihood_base=r.likelihood_base,
            cause_asset=cause_tags.get(r.cause_asset_id),
            safeguards=tuple(by_row.get(r.id, [])),
        )
        for r in sorted(rows, key=lambda r: r.row_code)
    ]


async def load_plant_model(db: AsyncSession, unit_code: str = DEFAULT_UNIT) -> Optional[PlantModel]:
    """Everything the health and risk engines need for one unit; None if the unit is unknown."""
    unit = await UnitRepository(db).get_by_code(unit_code)
    if not unit:
        return None
    sensor_tags = list(await SensorTagRepository(db).get_all(limit=1000))
    assets = await AssetRepository(db).list_by_unit(unit.id, limit=1000)
    rule_set_row, rule_set = await load_rule_set(db)
    pairs = await HazopRowRepository(db).list_current(unit_id=unit.id)
    return PlantModel(
        unit_id=unit.id,
        unit_code=unit.code,
        health_models=health_models_from_tags(sensor_tags),
        policy=band_policy(),
        rows=await load_row_inputs(db, unit.id),
        rule_set=rule_set,
        rule_set_row=rule_set_row,
        asset_ids={a.tag: a.id for a in assets},
        asset_tags={a.id: a.tag for a in assets},
        sensor_tags={t.tag: t for t in sensor_tags},
        row_nodes={row.row_code: node.code for row, node in pairs},
    )
