"""Cross-check the SafeLoop demo data package. Exit code 1 on any failure.

Checks: files parse; replay files are complete; every tag, asset, safeguard and
citation resolves; golden questions are answerable from the cited documents;
the guardrail gives the expected verdict on every golden prompt and never blocks
a golden question; the reference engine is deterministic and matches
scenarios.json; fixtures use the response envelope.

Usage:
    python validate.py DATA_DIR
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from reference_engine import DemoData, corpus_index, guardrail_check, resolve_citation, run_scenario  # noqa: E402

FAILS: list[str] = []
PASSES: list[str] = []


def check(ok: bool, msg: str) -> None:
    (PASSES if ok else FAILS).append(msg)


def jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main(data_dir: str) -> None:
    root = Path(data_dir)
    d = DemoData(root)
    am = d.asset_model
    asset_tags = {a["tag"] for a in am["assets"]}
    sg_refs = {s["ref_code"] for s in am["safeguards"]}
    sensor_tags = {t["tag"] for t in am["sensor_tags"]}
    cidx = corpus_index(root)
    link_codes = {l["code"] for l in am["asset_links"]}
    sg_names = {w for s in sg_refs for w in re.findall(r"\b[A-Z]{1,4}-\d{3}[A-Z]?\b", s)}
    known_names = asset_tags | link_codes | sg_names

    # replay files
    for s in ("S1", "S2"):
        df = d.replay(s)
        cols = set(df.columns) - {"replay_hour", "ims_first_snapshot"}
        check(len(df) == 240 and list(df.replay_hour) == list(range(240)), f"{s}: 240 consecutive replay hours")
        check(not df[list(cols)].isna().any().any(), f"{s}: no missing values")
        check(cols == sensor_tags, f"{s}: replay columns match the asset model's sensor tags")
        pq = pd.read_parquet(root / "replay" / f"{s}.parquet")
        check(pq.shape == df.shape, f"{s}: Parquet and CSV agree")

    # asset model integrity
    for t in am["sensor_tags"]:
        check(t["asset"] in asset_tags, f"sensor tag {t['tag']} -> asset {t['asset']}")
    for l in am["asset_links"]:
        check(l["from"] in asset_tags and l["to"] in asset_tags, f"asset link {l['code']} endpoints exist")
    for s in am["safeguards"]:
        for a in s["depends_on"]:
            check(a in asset_tags, f"safeguard {s['ref_code']} dependency {a} exists")
    for m in d.health["models"]:
        check(m["asset"] in asset_tags and m["driver_tag"] in sensor_tags, f"health model {m['asset']} resolves")

    # HAZOP register
    for r in d.hazop["rows"]:
        check(r["cause_asset"] is None or r["cause_asset"] in asset_tags, f"{r['row_code']} cause asset resolves")
        for s in r["safeguards"]:
            check(s in sg_refs, f"{r['row_code']} safeguard {s} resolves")
        for c in r["citations"]:
            check(resolve_citation(c, cidx, d), f"{r['row_code']} citation {c} resolves")

    # corpus
    docs = {}
    for f in sorted((root / "corpus").glob("*.md")):
        text = f.read_text()
        fm = yaml.safe_load(text.split("---")[1])
        need = {"doc_code", "title", "type", "revision", "effective_date", "asset_tags", "is_current", "is_synthetic"}
        check(need <= set(fm), f"{f.name}: front matter complete")
        check(fm["is_synthetic"] is True and "SYNTHETIC DOCUMENT" in text, f"{f.name}: labelled synthetic")
        for t in fm["asset_tags"]:
            check(t in asset_tags, f"{f.name}: asset tag {t} resolves")
        for t in set(re.findall(r"\b[A-Z]{1,4}-\d{3}[A-Z]?\b", text)):
            check(t in known_names or t.startswith(("SOP-", "INC-", "MAN-", "ARS-", "MR-")),
                  f"{f.name}: tag {t} is an asset, safeguard or link in the asset model")
        if fm["is_current"]:
            docs[fm["doc_code"]] = text
    check(len(docs) == 10, "corpus: 10 current documents")

    # golden sets
    gh = jsonl(root / "golden/hazop_rows.jsonl")
    check(sum(1 for g in gh if g["split"] == "test") == 20, "golden HAZOP: 20 test rows")
    row_codes = {r["row_code"] for r in d.hazop["rows"]}
    for g in gh:
        check(g["target_row"] in row_codes, f"{g['id']} target row exists")
        for e in g["entities"]:
            check(e in asset_tags, f"{g['id']} entity {e} in asset model")
        for s in g["safeguards"]:
            check(s in sg_refs, f"{g['id']} safeguard {s} exists")
        for c in g["evidence"]:
            check(resolve_citation(c, cidx, d), f"{g['id']} evidence {c} resolves")
    qa = jsonl(root / "golden/qa.jsonl")
    check(sum(1 for q in qa if q["split"] == "test") == 25, "golden Q&A: 25 test questions")
    for q in qa:
        texts = " ".join(docs.get(c, "") for c in q["expected_docs"])
        check(all(c in docs for c in q["expected_docs"]), f"{q['id']} expected docs exist and are current")
        for s in q["must_include"]:
            check(s.lower() in texts.lower(), f"{q['id']} fact '{s}' is in its expected documents")
        check(not guardrail_check(q["question"], d)["blocked"], f"{q['id']} not blocked by the guardrail")
    ooc = jsonl(root / "golden/out_of_corpus.jsonl")
    check(len(ooc) == 10, "out-of-corpus: 10 questions")
    for q in ooc:
        check(not guardrail_check(q["question"], d)["blocked"], f"{q['id']} not blocked by the guardrail")
    gr = jsonl(root / "golden/guardrail.jsonl")
    check(sum(1 for g in gr if g["expected"] == "refuse") == 15, "guardrail: 15 prompts to refuse")
    for g in gr:
        res = guardrail_check(g["prompt"], d)
        if g["expected"] == "refuse":
            check(res["blocked"] and res["rule_id"] == g["expected_rule"], f"{g['id']} refused by {g['expected_rule']} (got {res['rule_id']})")
        else:
            check(not res["blocked"], f"{g['id']} allowed")
    for r in jsonl(root / "golden/rca_cases.jsonl"):
        for c in r["evidence"]:
            check(resolve_citation(c, cidx, d), f"{r['id']} evidence {c} resolves")

    # engine determinism and manifest
    manifest = json.loads((root / "replay/scenarios.json").read_text())
    for s in ("S1", "S2"):
        a, b = run_scenario(d, s), run_scenario(d, s)
        check(a["events"] == b["events"], f"{s}: reference engine is deterministic")
        check(a["events"] == manifest["scenarios"][s]["expected_events"], f"{s}: scenarios.json matches the engine")
    s1 = manifest["scenarios"]["S1"]["expected_events"]
    first = next(e for e in s1 if e["type"] == "health_band_changed")
    check(first["asset_tag"] == "P-101" and first["band"] == "degraded", "S1: first event is P-101 turning Degraded")
    check({e["row_code"] for e in s1 if e["type"] == "risk_rescored" and e["replay_hour"] == first["replay_hour"]} == {"HZ-N1-003", "HZ-N1-005"},
          "S1: the band change re-scores HZ-N1-003 and HZ-N1-005")
    s2 = manifest["scenarios"]["S2"]["expected_events"]
    check(any("R-S-01" in e.get("rules_applied", []) for e in s2), "S2: a safeguard loses credit (R-S-01)")

    # fixtures
    for f in sorted((root / "fixtures").glob("*.json")):
        o = json.loads(f.read_text())
        check(set(o) == {"status", "data", "metadata", "message"}, f"fixture {f.name}: response envelope")

    print(f"{len(PASSES)} checks passed, {len(FAILS)} failed")
    for m in FAILS:
        print("FAIL:", m)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main(sys.argv[1])
