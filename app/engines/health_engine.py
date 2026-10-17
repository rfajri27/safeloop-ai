"""Health engine, model version hi.v1 (spec Section 9.1).

For each monitored asset:

    HI = clip(100 - 100 * (x - x_healthy) / (x_fail - x_healthy), 0, 100)

where x is the rolling median (6 replay hours) of the asset's driving feature;
for `abs_deviation` models x is first taken as |x - centre|. Bands: Healthy
>= 80, Degraded 50-79, Critical < 50, with a 2-point hysteresis. A band gets
worse at once; it improves only after 24 consecutive hours in the better band.

HealthTracker processes one replay hour at a time, so the replay task and the
evaluation runner share the exact same state machine.
"""
from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Optional

BANDS = ("healthy", "degraded", "critical")
MODEL_VERSION = "hi.v1"


@dataclass(frozen=True)
class BandPolicy:
    """Band thresholds shared by every hi.v1 model (health_models.json `_meta`)."""
    healthy_min: float = 80
    degraded_min: float = 50
    hysteresis_points: float = 2
    recovery_hold_hours: int = 24
    version: str = MODEL_VERSION

    @classmethod
    def from_meta(cls, meta: Optional[dict[str, Any]]) -> "BandPolicy":
        if not meta:
            return cls()
        bands = meta.get("bands", {})
        return cls(
            healthy_min=bands.get("healthy_min", cls.healthy_min),
            degraded_min=bands.get("degraded_min", cls.degraded_min),
            hysteresis_points=meta.get("hysteresis_points", cls.hysteresis_points),
            recovery_hold_hours=meta.get("recovery_hold_hours", cls.recovery_hold_hours),
            version=meta.get("version", cls.version),
        )


@dataclass(frozen=True)
class HealthModel:
    """One asset's health model: driver tag and anchors."""
    asset: str
    driver_tag: str
    mode: str
    x_healthy: float
    x_fail: float
    centre: float = 0.0
    window_hours: int = 6

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HealthModel":
        return cls(
            asset=data["asset"],
            driver_tag=data["driver_tag"],
            mode=data.get("mode", "rising"),
            x_healthy=float(data["x_healthy"]),
            x_fail=float(data["x_fail"]),
            centre=float(data.get("centre", 0.0)),
            window_hours=int(data.get("smoothing", {}).get("window_hours", 6)),
        )


def health_index(x: float, model: HealthModel) -> float:
    """Unrounded health index for a smoothed driver value."""
    if model.mode == "abs_deviation":
        x = abs(x - model.centre)
    hi = 100 - 100 * (x - model.x_healthy) / (model.x_fail - model.x_healthy)
    return float(min(100.0, max(0.0, hi)))


def raw_band(hi: float, policy: BandPolicy) -> str:
    """Band without hysteresis."""
    if hi >= policy.healthy_min:
        return "healthy"
    if hi >= policy.degraded_min:
        return "degraded"
    return "critical"


@dataclass(frozen=True)
class HealthStep:
    """Result of one replay hour for one asset."""
    asset: str
    replay_hour: int
    health_index: int
    health_index_exact: float
    band: str
    previous_band: Optional[str]
    driver_tag: str
    driver_value: float

    @property
    def band_changed(self) -> bool:
        return self.previous_band is not None


@dataclass
class HealthTracker:
    """Per-asset hi.v1 state machine; feed it one raw driver value per replay hour."""
    model: HealthModel
    policy: BandPolicy = field(default_factory=BandPolicy)
    band: str = "healthy"
    better_count: int = 0
    window: deque = field(init=False)

    def __post_init__(self) -> None:
        self.window = deque(maxlen=self.model.window_hours)

    def step(self, replay_hour: int, raw_value: float) -> HealthStep:
        """Advance one hour. A band change sets previous_band on the returned step."""
        self.window.append(float(raw_value))
        hi = health_index(median(self.window), self.model)
        half = self.policy.hysteresis_points / 2
        worse = raw_band(hi + half, self.policy)
        better = raw_band(hi - half, self.policy)

        new = self.band
        if BANDS.index(worse) > BANDS.index(self.band):
            new, self.better_count = worse, 0
        elif BANDS.index(better) < BANDS.index(self.band):
            self.better_count += 1
            if self.better_count >= self.policy.recovery_hold_hours:
                new, self.better_count = better, 0
        else:
            self.better_count = 0

        previous = self.band if new != self.band else None
        self.band = new
        return HealthStep(
            asset=self.model.asset,
            replay_hour=replay_hour,
            health_index=round(hi),
            health_index_exact=hi,
            band=new,
            previous_band=previous,
            driver_tag=self.model.driver_tag,
            driver_value=float(raw_value),
        )
