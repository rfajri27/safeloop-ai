"""Risk engine, rule set v1 (spec Section 9.1).

| Rule   | Condition                                              | Effect                         |
| R-L-01 | The row's cause asset is Degraded                      | Likelihood +1                  |
| R-L-02 | The row's cause asset is Critical                      | Likelihood +2 (replaces R-L-01) |
| R-S-01 | A credited BPCS safeguard depends on a non-healthy asset | Credit removed; likelihood +1  |
| R-P-01 | An asset causes a row with severity >= 4               | Alert line tightens            |

Likelihood is capped (5); score = likelihood x severity. The same inputs always
give the same output.
"""
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional

DEFAULT_BANDS = (("low", 1, 4), ("medium", 5, 9), ("high", 10, 14), ("extreme", 15, 25))


@dataclass(frozen=True)
class RuleSet:
    """The parts of a `risk_rule_sets.rules` document the engine needs."""
    version: str
    likelihood_cap: int = 5
    bands: tuple[tuple[str, int, int], ...] = DEFAULT_BANDS
    degraded_delta: int = 1
    critical_delta: int = 2
    safeguard_delta: int = 1
    tighten_severity: int = 4
    texts: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_rules(cls, version: str, rules: Mapping[str, Any]) -> "RuleSet":
        by_id = {r["id"]: r for r in rules.get("rules", [])}

        def delta(rule_id: str, default: int) -> int:
            return int(by_id.get(rule_id, {}).get("effect", {}).get("likelihood_delta", default))

        bands = tuple((b["name"], int(b["min"]), int(b["max"])) for b in rules.get("bands", [])) or DEFAULT_BANDS
        tighten = by_id.get("R-P-01", {}).get("when", {}).get("cause_of_row_with_severity_gte", 4)
        return cls(
            version=version,
            likelihood_cap=int(rules.get("likelihood_cap", 5)),
            bands=bands,
            degraded_delta=delta("R-L-01", 1),
            critical_delta=delta("R-L-02", 2),
            safeguard_delta=delta("R-S-01", 1),
            tighten_severity=int(tighten),
            texts=tuple((r["id"], r.get("text", "")) for r in rules.get("rules", [])),
        )

    def text(self, rule_id: str) -> str:
        return dict(self.texts).get(rule_id, rule_id)


@dataclass(frozen=True)
class SafeguardInput:
    """A safeguard as credited against one row."""
    safeguard_id: str
    ref_code: str
    type: str
    credited: bool
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class RowInput:
    """A current HAZOP row version."""
    row_id: str
    row_code: str
    severity: int
    likelihood_base: int
    cause_asset: Optional[str]
    safeguards: tuple[SafeguardInput, ...] = ()


@dataclass(frozen=True)
class RowScore:
    """Live risk of one row."""
    row_id: str
    row_code: str
    severity: int
    likelihood: int
    score: int
    band: str
    rules_applied: tuple[str, ...] = ()
    safeguards_lost: tuple[str, ...] = ()
    safeguard_ids_lost: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rescore:
    """A row whose score changed after a band change."""
    row_id: str
    row_code: str
    severity: int
    likelihood_old: int
    likelihood_new: int
    score_old: int
    score_new: int
    band_old: str
    band_new: str
    rules_applied: tuple[str, ...] = field(default_factory=tuple)
    safeguards_lost: tuple[str, ...] = field(default_factory=tuple)
    safeguard_ids_lost: tuple[str, ...] = field(default_factory=tuple)


def score_band(score: int, rule_set: RuleSet) -> str:
    """Band name for a likelihood x severity score."""
    for name, low, high in rule_set.bands:
        if low <= score <= high:
            return name
    raise ValueError(f"Score {score} is outside every band")


def score_row(row: RowInput, bands: Mapping[str, str], rule_set: RuleSet) -> RowScore:
    """Live likelihood, score and band of one row given current asset bands."""
    applied: list[str] = []
    delta = 0
    cause_band = bands.get(row.cause_asset or "", "healthy")
    if cause_band == "critical":
        delta += rule_set.critical_delta
        applied.append("R-L-02")
    elif cause_band == "degraded":
        delta += rule_set.degraded_delta
        applied.append("R-L-01")

    lost = [
        sg for sg in row.safeguards
        if sg.credited and sg.type == "bpcs"
        and any(bands.get(asset, "healthy") != "healthy" for asset in sg.depends_on)
    ]
    if lost:
        delta += rule_set.safeguard_delta
        applied.append("R-S-01")

    likelihood = min(rule_set.likelihood_cap, row.likelihood_base + delta)
    score = likelihood * row.severity
    return RowScore(
        row_id=row.row_id,
        row_code=row.row_code,
        severity=row.severity,
        likelihood=likelihood,
        score=score,
        band=score_band(score, rule_set),
        rules_applied=tuple(applied),
        safeguards_lost=tuple(sg.ref_code for sg in lost),
        safeguard_ids_lost=tuple(sg.safeguard_id for sg in lost),
    )


def score_rows(rows: Iterable[RowInput], bands: Mapping[str, str], rule_set: RuleSet) -> dict[str, RowScore]:
    """Live risk for every row, keyed by row code."""
    return {row.row_code: score_row(row, bands, rule_set) for row in rows}


def rescore(
    rows: Iterable[RowInput],
    bands: Mapping[str, str],
    current: Mapping[str, RowScore],
    rule_set: RuleSet,
) -> tuple[list[Rescore], dict[str, RowScore]]:
    """Rows whose score changed against `current`, and the new live scores."""
    live = score_rows(rows, bands, rule_set)
    changes = []
    for code, new in sorted(live.items()):
        old = current[code]
        if new.score != old.score:
            changes.append(Rescore(
                row_id=new.row_id,
                row_code=code,
                severity=new.severity,
                likelihood_old=old.likelihood,
                likelihood_new=new.likelihood,
                score_old=old.score,
                score_new=new.score,
                band_old=old.band,
                band_new=new.band,
                rules_applied=new.rules_applied,
                safeguards_lost=new.safeguards_lost,
                safeguard_ids_lost=new.safeguard_ids_lost,
            ))
    return changes, live


def tightened_alert_assets(rows: Iterable[RowInput], rule_set: RuleSet) -> set[str]:
    """R-P-01: assets that cause a row with severity >= threshold get the tightened alert line."""
    return {row.cause_asset for row in rows if row.cause_asset and row.severity >= rule_set.tighten_severity}
