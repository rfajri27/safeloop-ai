"""Reference implementation of the SafeLoop deterministic engines, for test oracles.

Implements, over the prepared replay files:
  - health engine (hi.v1): smoothing, HI formula, bands with hysteresis and a recovery hold
  - risk engine (rules v1): R-L-01, R-L-02, R-S-01, R-P-01
  - guardrail (gr.v1) from guardrail_rules.yaml
  - citation resolution used by the Judge

The production code lives in app/engines/ and must give the same results on the
same inputs. Run `python reference_engine.py DATA_DIR S1` to print the event
timeline of a scenario.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

BANDS = ("healthy", "degraded", "critical")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@dataclass
class DemoData:
    root: Path
    asset_model: dict = field(init=False)
    hazop: dict = field(init=False)
    rules: dict = field(init=False)
    health: dict = field(init=False)
    guardrail: dict = field(init=False)

    def __post_init__(self) -> None:
        seed = self.root / "seed"
        self.asset_model = load_json(seed / "asset_model_unit100.json")
        self.hazop = load_json(seed / "hazop_unit100.json")
        self.rules = load_json(seed / "risk_rule_set_v1.json")
        self.health = load_json(seed / "health_models.json")
        self.guardrail = yaml.safe_load((seed / "guardrail_rules.yaml").read_text())

    def replay(self, scenario: str) -> pd.DataFrame:
        return pd.read_csv(self.root / "replay" / f"{scenario}.csv")


# ---------------------------------------------------------------- health engine
def raw_band(hi: float, cfg: dict) -> str:
    if hi >= cfg["bands"]["healthy_min"]:
        return "healthy"
    if hi >= cfg["bands"]["degraded_min"]:
        return "degraded"
    return "critical"


def health_index(x: float, model: dict) -> float:
    if model["mode"] == "abs_deviation":
        x = abs(x - model["centre"])
    hi = 100 - 100 * (x - model["x_healthy"]) / (model["x_fail"] - model["x_healthy"])
    return float(min(100.0, max(0.0, hi)))


def run_health(df: pd.DataFrame, data: DemoData) -> tuple[pd.DataFrame, list[dict]]:
    """Return per-hour HI and band per asset, and the band-change events."""
    meta = data.health["_meta"]
    half = meta["hysteresis_points"] / 2
    hold = meta["recovery_hold_hours"]
    out = {"replay_hour": df.replay_hour}
    events: list[dict] = []
    for m in data.health["models"]:
        w = m["smoothing"]["window_hours"]
        smooth = df[m["driver_tag"]].rolling(w, min_periods=1).median()
        his, bands = [], []
        band, better_count = "healthy", 0
        for h, x in enumerate(smooth):
            hi = health_index(float(x), m)
            # Worse: move at once, past a hysteresis margin. Better: only after `hold` hours.
            worse = raw_band(hi + half, meta)
            better = raw_band(hi - half, meta)
            new = band
            if BANDS.index(worse) > BANDS.index(band):
                new, better_count = worse, 0
            elif BANDS.index(better) < BANDS.index(band):
                better_count += 1
                if better_count >= hold:
                    new, better_count = better, 0
            else:
                better_count = 0
            if new != band:
                events.append({"replay_hour": h, "type": "health_band_changed", "asset_tag": m["asset"],
                               "previous_band": band, "band": new, "health_index": round(hi),
                               "trigger_tag": m["driver_tag"], "trigger_value": round(float(df[m["driver_tag"]][h]), 3)})
                band = new
            his.append(round(hi, 1))
            bands.append(band)
        out[f"{m['asset']}__hi"] = his
        out[f"{m['asset']}__band"] = bands
    return pd.DataFrame(out), events


# ------------------------------------------------------------------ risk engine
def score_band(score: int, rules: dict) -> str:
    for b in rules["bands"]:
        if b["min"] <= score <= b["max"]:
            return b["name"]
    raise ValueError(score)


def rescore_rows(bands: dict[str, str], data: DemoData) -> dict[str, dict]:
    """Live likelihood and score for every HAZOP row given current asset bands."""
    sg_by_ref = {s["ref_code"]: s for s in data.asset_model["safeguards"]}
    cap = data.rules["likelihood_cap"]
    result = {}
    for row in data.hazop["rows"]:
        applied, lost = [], []
        delta = 0
        cb = bands.get(row["cause_asset"] or "", "healthy")
        if cb == "critical":
            delta += 2
            applied.append("R-L-02")
        elif cb == "degraded":
            delta += 1
            applied.append("R-L-01")
        for ref in row["safeguards"]:
            sg = sg_by_ref[ref]
            if sg["type"] == "bpcs" and any(bands.get(a, "healthy") != "healthy" for a in sg["depends_on"]):
                lost.append(ref)
        if lost:
            delta += 1
            applied.append("R-S-01")
        lik = min(cap, row["likelihood_base"] + delta)
        score = lik * row["severity"]
        result[row["row_code"]] = {"likelihood": lik, "severity": row["severity"], "score": score,
                                   "band": score_band(score, data.rules), "rules_applied": applied,
                                   "safeguards_lost": lost}
    return result


def run_scenario(data: DemoData, scenario: str) -> dict:
    df = data.replay(scenario)
    health_df, band_events = run_health(df, data)
    assets = [m["asset"] for m in data.health["models"]]
    bands = {a: "healthy" for a in assets}
    base = rescore_rows(bands, data)
    current = {k: v["score"] for k, v in base.items()}
    events: list[dict] = []
    by_hour: dict[int, list[dict]] = {}
    for e in band_events:
        by_hour.setdefault(e["replay_hour"], []).append(e)
    trip_hour = None
    if scenario == "S1":
        hits = df.index[df["P101_DE_VIB_RMS"] >= 11.2]
        trip_hour = int(hits[0]) if len(hits) else None
    for h in range(len(df)):
        for e in by_hour.get(h, []):
            events.append(e)
            bands[e["asset_tag"]] = e["band"]
            live = rescore_rows(bands, data)
            for code, r in live.items():
                if r["score"] != current[code]:
                    old = current[code]
                    events.append({"replay_hour": h, "type": "risk_rescored", "row_code": code,
                                   "score_old": old, "score_new": r["score"],
                                   "likelihood_new": r["likelihood"], "band_new": r["band"],
                                   "rules_applied": r["rules_applied"], "safeguards_lost": r["safeguards_lost"],
                                   "trigger_asset": e["asset_tag"], "rule_set_version": data.rules["version"]})
                    current[code] = r["score"]
        if trip_hour is not None and h == trip_hour:
            events.append({"replay_hour": h, "type": "trip", "asset_tag": "P-101",
                           "detail": "P-101 vibration reached 11.2 mm/s; P-101B takes over reflux duty"})
    return {"scenario": scenario, "health": health_df, "events": events, "trip_hour": trip_hour,
            "final_bands": bands, "base_rows": base, "final_rows": rescore_rows(bands, data)}


# -------------------------------------------------------------------- guardrail
def guardrail_check(text: str, data: DemoData) -> dict:
    for rule in data.guardrail["rules"]:
        if re.search(rule["pattern"], text, flags=re.IGNORECASE):
            allow = rule.get("allow_if")
            if allow and re.search(allow, text, flags=re.IGNORECASE):
                continue
            return {"blocked": True, "rule_id": rule["id"], "refusal": rule["refusal"]}
    return {"blocked": False, "rule_id": None}


# ------------------------------------------------------------ citation resolver
def section_id(heading: str) -> str:
    """Section id used in citations: '6.3 Bearing...' -> '6.3', 'Step 7' -> 'step-7', 'Node 1: ...' -> 'node-1'."""
    h = heading.strip()
    m = re.match(r"^(\d+(?:\.\d+)*)\b", h)
    if m:
        return m.group(1)
    m = re.match(r"^(step|node)\s+(\d+)", h, flags=re.IGNORECASE)
    if m:
        return f"{m.group(1).lower()}-{m.group(2)}"
    return re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")


def corpus_index(root: Path) -> dict[str, set[str]]:
    """Map current doc_code -> set of section ids found in its headings."""
    index: dict[str, set[str]] = {}
    for f in sorted((root / "corpus").glob("*.md")):
        text = f.read_text()
        fm = yaml.safe_load(text.split("---")[1])
        if not fm["is_current"]:
            continue
        index[fm["doc_code"]] = {section_id(m) for m in re.findall(r"^#{2,4}\s+(.+)$", text, flags=re.M)}
    return index


def resolve_citation(ref: str, cindex: dict[str, set[str]], data: DemoData) -> bool:
    if ref.startswith("asset_model:"):
        code = ref.split(":", 1)[1]
        return any(link["code"] == code for link in data.asset_model["asset_links"])
    if ref.startswith("doc:"):
        body = ref[4:]
        doc, _, sec = body.partition("#")
        if doc not in cindex:
            return False
        return not sec or sec in cindex[doc]
    return False


if __name__ == "__main__":
    d = DemoData(Path(sys.argv[1]))
    res = run_scenario(d, sys.argv[2])
    for ev in res["events"]:
        print(json.dumps(ev))
    print("trip_hour", res["trip_hour"])
