"""Deterministic engine tests (spec Section 11): no database, no model calls.

The oracle is the demo data package: data/replay/scenarios.json lists the band
changes and re-scores the reference engine produces for S1 and S2, and the
guardrail golden set lists the prompts that must be refused or allowed.
"""
import ast
import json
from pathlib import Path
import pytest
from app.engines.corpus import load_corpus, section_ids_in
from app.engines.guardrail import load_guardrail
from app.engines.health_engine import BandPolicy, HealthModel, HealthTracker
from app.engines.judge import JudgeContext, check
from app.engines.replay_engine import load_scenario
from app.engines.risk_engine import RowInput, RuleSet, SafeguardInput, rescore, score_rows

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "safeloop-demo-data" / "data"
ENGINES = ROOT / "app" / "engines"
FORBIDDEN = ("langchain", "langgraph", "google", "openai", "httpx", "requests", "aiohttp", "urllib", "socket")


def _json(path: str) -> dict:
    return json.loads((DATA / path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plant():
    asset_model = _json("seed/asset_model_unit100.json")
    hazop = _json("seed/hazop_unit100.json")
    health = _json("seed/health_models.json")
    safeguards = {s["ref_code"]: s for s in asset_model["safeguards"]}
    rows = [
        RowInput(r["row_code"], r["row_code"], r["severity"], r["likelihood_base"], r["cause_asset"], tuple(
            SafeguardInput(ref, ref, safeguards[ref]["type"], True, tuple(safeguards[ref]["depends_on"]))
            for ref in r["safeguards"]
        ))
        for r in hazop["rows"]
    ]
    return {
        "rows": rows,
        "rule_set": RuleSet.from_rules("v1", _json("seed/risk_rule_set_v1.json")),
        "models": [HealthModel.from_dict(m) for m in health["models"]],
        "policy": BandPolicy.from_meta(health["_meta"]),
        "asset_model": asset_model,
    }


def test_engines_import_no_ai_or_network_package():
    """NFR-01: nothing under app/engines/ may import an AI library or a network client."""
    for path in ENGINES.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.split(".")[0] in FORBIDDEN, f"{path.name} imports {name}"


@pytest.mark.parametrize("scenario", ["S1", "S2"])
def test_engines_reproduce_scenario_oracle(plant, scenario):
    """Health + risk engines give exactly the scenarios.json timeline, three times over (NFR-05)."""
    expected = [
        e for e in _json("replay/scenarios.json")["scenarios"][scenario]["expected_events"]
        if e["type"] != "trip"
    ]
    runs = []
    for _ in range(3):
        trackers = [HealthTracker(m, plant["policy"]) for m in plant["models"]]
        bands = {t.model.asset: "healthy" for t in trackers}
        scores = score_rows(plant["rows"], bands, plant["rule_set"])
        events = []
        for hour, values in enumerate(load_scenario(DATA, scenario).hours):
            for tracker in trackers:
                step = tracker.step(hour, values[tracker.model.driver_tag])
                if not step.band_changed:
                    continue
                events.append({
                    "replay_hour": hour, "type": "health_band_changed", "asset_tag": step.asset,
                    "previous_band": step.previous_band, "band": step.band, "health_index": step.health_index,
                    "trigger_tag": step.driver_tag, "trigger_value": round(step.driver_value, 3),
                })
                bands[step.asset] = step.band
                changes, scores = rescore(plant["rows"], bands, scores, plant["rule_set"])
                events.extend({
                    "replay_hour": hour, "type": "risk_rescored", "row_code": c.row_code,
                    "score_old": c.score_old, "score_new": c.score_new, "likelihood_new": c.likelihood_new,
                    "band_new": c.band_new, "rules_applied": list(c.rules_applied),
                    "safeguards_lost": list(c.safeguards_lost), "trigger_asset": step.asset, "rule_set_version": "v1",
                } for c in changes)
        runs.append(events)
    assert runs[0] == expected
    assert runs[0] == runs[1] == runs[2]


def test_trip_hour_s1():
    assert load_scenario(DATA, "S1").trip_hour() == 236
    assert load_scenario(DATA, "S2").trip_hour() is None


def test_likelihood_is_capped(plant):
    row = RowInput("r", "R", 5, 4, "P-101", (SafeguardInput("s", "S", "bpcs", True, ("P-101",)),))
    score = score_rows([row], {"P-101": "critical"}, plant["rule_set"])["R"]
    assert score.likelihood == 5 and score.score == 25 and score.band == "extreme"
    assert score.rules_applied == ("R-L-02", "R-S-01")


def test_guardrail_golden_set():
    guard = load_guardrail(DATA / "seed" / "guardrail_rules.yaml")
    for line in (DATA / "golden" / "guardrail.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        result = guard.check(item["prompt"])
        assert result.blocked == (item["expected"] == "refuse"), item["prompt"]
        if result.blocked:
            assert result.rule_id == item["expected_rule"], item["prompt"]


def test_actuation_wording_only_flags_instructions():
    guard = load_guardrail(DATA / "seed" / "guardrail_rules.yaml")
    assert guard.actuation_wording("Open TV-301 to 100%")
    assert guard.actuation_wording("Then close FV-201 slowly.")
    assert guard.actuation_wording("Disable the PAH-201 alarm during the test")
    assert not guard.actuation_wording("Keep the monthly P-101B auto-start test, including a check that FT-201 is reading live.")
    assert not guard.actuation_wording("Review the S-101 ΔP alarm setpoint and add a strainer check to the P-101B auto-start test.")


@pytest.fixture(scope="module")
def judge_context(plant):
    am = plant["asset_model"]
    sections: dict[str, set[str]] = {}
    for doc in load_corpus(DATA / "corpus"):
        if doc.is_current:
            for chunk in doc.chunks:
                sections.setdefault(doc.doc_code, set()).update(section_ids_in(chunk.text))
    guard = load_guardrail(DATA / "seed" / "guardrail_rules.yaml")
    return JudgeContext(
        asset_tags=frozenset(a["tag"] for a in am["assets"]),
        safeguard_refs=frozenset(s["ref_code"] for s in am["safeguards"]),
        link_codes=frozenset(link["code"] for link in am["asset_links"]),
        doc_sections={k: frozenset(v) for k, v in sections.items()},
        actuation=guard.actuation_wording,
    )


GOOD = {
    "title": "Strainer S-101 blocked starves P-101 and P-101B",
    "entities": ["S-101", "P101B", "p-101"],
    "safeguards": ["PSV-201", "PAH-201"],
    "recommendation": "Review the S-101 ΔP alarm setpoint and add a strainer check to the P-101B auto-start test.",
    "citations": ["asset_model:L-104", "doc:SOP-P101-02#step-3", "doc:MAN-P101#5", "doc:INC-2023-009"],
}


def test_judge_passes_grounded_proposal(judge_context):
    result = check(GOOD, judge_context)
    assert result.verdict == "pass"
    assert [c.passed for c in result.checks] == [True, True, True]


@pytest.mark.parametrize("change, reason", [
    ({"entities": ["FSL-201", "P-101B"]}, "FSL-201 not found in asset model"),
    ({"citations": ["doc:MAN-K401#2"]}, "doc:MAN-K401#2 not found"),
    ({"citations": ["doc:SOP-P101-02#step-12"]}, "doc:SOP-P101-02#step-12 not found"),
    ({"citations": []}, "no citations"),
    ({"recommendation": "Open TV-301 to 100%."}, '"Open TV-301" reads as a control action'),
])
def test_judge_blocks(judge_context, change, reason):
    result = check({**GOOD, **change}, judge_context)
    assert result.verdict == "block"
    assert result.reason == reason


def test_superseded_revision_not_citable(judge_context):
    """SOP-P101-02 rev B is superseded; only rev C sections resolve (rev C has 9 steps, rev B 4)."""
    assert judge_context.resolve_citation("doc:SOP-P101-02#step-9")
    corpus = {(d.doc_code, d.revision): d for d in load_corpus(DATA / "corpus")}
    assert not corpus[("SOP-P101-02", "B")].is_current
