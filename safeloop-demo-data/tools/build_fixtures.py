"""Build data/replay/scenarios.json and the fixtures-mode API responses.

All numbers in the fixtures come from running the reference engine over the
replay files. The only hand-written parts are marked "_fixture_note": an example
Red Team proposal and an example chat stream, which stand in for model output.

Usage:
    python build_fixtures.py DATA_DIR
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from reference_engine import DemoData, rescore_rows, run_scenario, score_band  # noqa: E402

START = datetime(2026, 10, 18, 7, 20, 0, tzinfo=timezone.utc)  # 14:20 WIB
SPEED = 8
SECONDS_PER_HOUR = 2.0
SNAPSHOT_HOUR = 176  # S1, two replay hours after P-101 turns Degraded


def at(h: float) -> str:
    return (START + timedelta(seconds=h * SECONDS_PER_HOUR / SPEED)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def env(data, metadata=None, message="Success") -> dict:
    return {"status": 1, "data": data, "metadata": metadata, "message": message}


def write(out: Path, name: str, obj) -> None:
    (out / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def main(data_dir: str) -> None:
    root = Path(data_dir)
    d = DemoData(root)
    out = root / "fixtures"
    out.mkdir(parents=True, exist_ok=True)
    mapping = json.loads((root / "replay/tag_mapping.json").read_text())["tags"]
    am = d.asset_model
    tags_by_asset: dict[str, list[dict]] = {}
    for t in am["sensor_tags"]:
        tags_by_asset.setdefault(t["asset"], []).append(t)
    assets = {a["tag"]: a for a in am["assets"]}
    nodes = {n["code"]: n for n in am["nodes"]}
    hmodels = {m["asset"]: m for m in d.health["models"]}

    # ------------------------------------------------------------ scenario manifest
    results = {s: run_scenario(d, s) for s in ("S1", "S2")}
    manifest = {
        "replay_hours": 240, "seconds_per_replay_hour_at_1x": SECONDS_PER_HOUR, "speeds": [1, 3, 8],
        "health_model_version": d.health["_meta"]["version"], "rule_set_version": d.rules["version"],
        "scenarios": {
            "S1": {"name": "P-101 bearing degradation", "label": "S1 · P-101 bearing",
                   "source": "NASA IMS bearing test 2 (bearing 1, outer-race failure), 980 snapshots from 12 to 19 Feb 2004, "
                             "about 4.1 snapshots (41 min) per replay hour; process tags from the TEP normal run d00_te.dat",
                   "files": ["S1.csv", "S1.parquet"], "trip_hour": results["S1"]["trip_hour"],
                   "expected_events": [e for e in results["S1"]["events"]]},
            "S2": {"name": "E-301 cooling loss", "label": "S2 · E-301 cooling",
                   "source": "Tennessee Eastman Process test run d05_te.dat, IDV(5) condenser cooling-water inlet temperature step "
                             "introduced at sample 160 (replay hour 40); 4 samples (12 min) per replay hour",
                   "files": ["S2.csv", "S2.parquet"], "fault_onset_hour": 40,
                   "expected_events": [e for e in results["S2"]["events"]]},
        },
    }
    write(root / "replay", "scenarios.json", manifest)

    # ------------------------------------------------------------- S1 snapshot state
    s1 = results["S1"]
    df = d.replay("S1")
    hdf = s1["health"]
    h = SNAPSHOT_HOUR
    events = [e for e in s1["events"] if e["replay_hour"] <= h]
    bands_now = {a: hdf[f"{a}__band"][h] for a in hmodels}
    live = rescore_rows(bands_now, d)
    base = s1["base_rows"]
    band_change = next(e for e in events if e["type"] == "health_band_changed")
    rescores = [e for e in events if e["type"] == "risk_rescored"]

    def hi(a: str) -> int:
        return int(round(hdf[f"{a}__hi"][h]))

    # audit events, newest first
    audit = [{"audit_id": "AUD-0001", "at": at(0), "replay_hour": 0, "type": "replay", "event": "Scenario S1 started from reset at 8x",
              "actor": "Dimas", "model": None, "prompt_version": None, "rule_set_version": None, "sources": 0, "outcome": "logged"}]
    n = 2
    for e in events:
        if e["type"] == "health_band_changed":
            audit.append({"audit_id": f"AUD-{n:04d}", "at": at(e["replay_hour"]), "replay_hour": e["replay_hour"], "type": "health",
                          "event": f'{e["asset_tag"]} HealthBandChanged: {e["previous_band"].title()} → {e["band"].title()}, HI {e["health_index"]}',
                          "actor": "Health Agent", "model": d.health["_meta"]["version"], "prompt_version": None, "rule_set_version": None,
                          "sources": 1, "outcome": "logged"})
        elif e["type"] == "risk_rescored":
            row = next(r for r in d.hazop["rows"] if r["row_code"] == e["row_code"])
            lo = base[e["row_code"]]["likelihood"]
            audit.append({"audit_id": f"AUD-{n:04d}", "at": at(e["replay_hour"] + 0.2), "replay_hour": e["replay_hour"], "type": "re_score",
                          "event": f'{e["row_code"]} L{lo} → L{e["likelihood_new"]} ({score_band(e["score_old"], d.rules).title()} → {e["band_new"].title()})',
                          "actor": "Risk Engine", "model": None, "prompt_version": None,
                          "rule_set_version": f'rules {d.rules["version"]} · {", ".join(e["rules_applied"])}',
                          "sources": 1, "outcome": "queued"})
            e["audit_id"] = f"AUD-{n:04d}"
            e["severity"] = row["severity"]
        n += 1
    audit.reverse()
    write(out, "audit-events.json", env(audit, {"total": len(audit), "skip": 0, "limit": 50}))
    write(out, "audit-events_summary.json", env({"complete_records_pct": 100, "events": len(audit), "blocked_by_judge": 0, "refused": 0}))

    # health tiles and assets
    tiles = []
    for a in ("P-101", "P-101B", "V-201", "FV-201", "E-301", "TV-301"):
        m = hmodels[a]
        t = next(x for x in am["sensor_tags"] if x["tag"] == m["driver_tag"])
        tiles.append({"tag": a, "name": assets[a]["name"], "node": assets[a]["node"], "health_index": hi(a), "band": bands_now[a],
                      "origin": t["origin"], "source_dataset": t["source_dataset"]})
    write(out, "assets.json", env(tiles, {"total": len(tiles), "skip": 0, "limit": 50}))

    def feeds(asset: str) -> list[dict]:
        out_rows = []
        for r in d.hazop["rows"]:
            sgs = [s for s in am["safeguards"] if s["ref_code"] in r["safeguards"]]
            if r["cause_asset"] == asset or any(asset in s["depends_on"] for s in sgs):
                lv = live[r["row_code"]]
                out_rows.append({"row_code": r["row_code"], "deviation": r["deviation"], "severity": r["severity"],
                                 "likelihood_base": r["likelihood_base"], "likelihood_live": lv["likelihood"], "score": lv["score"],
                                 "band": lv["band"], "rule": ", ".join(lv["rules_applied"]) or None, "safeguards": r["safeguards"],
                                 "relation": "cause" if r["cause_asset"] == asset else "safeguard_dependency"})
        return out_rows

    p101 = {
        "tag": "P-101", "name": assets["P-101"]["name"], "asset_class": assets["P-101"]["asset_class"],
        "node": {"code": "N1", "name": nodes["N1"]["name"]}, "health_index": hi("P-101"), "band": bands_now["P-101"],
        "standby": {"tag": "P-101B", "health_index": hi("P-101B"), "band": bands_now["P-101B"]},
        "last_band_change": {"at": at(band_change["replay_hour"]), "replay_hour": band_change["replay_hour"],
                             "from": band_change["previous_band"], "to": band_change["band"]},
        "sensor_tags": [{"tag": t["tag"], "eng_unit": t["eng_unit"], "alert_high": t.get("alert_high"),
                         "alert_high_tightened": t.get("alert_high_tightened"), "origin": t["origin"],
                         "source_dataset": t["source_dataset"]} for t in tags_by_asset["P-101"]],
        "feeds_rows": feeds("P-101"),
    }
    write(out, "assets_P-101.json", env(p101))
    v0, v1 = float(df["P101_DE_VIB_RMS"][h - 6]), float(df["P101_DE_VIB_RMS"][h])
    write(out, "assets_P-101_trend.json", env({
        "sensor_tag": "P101_DE_VIB_RMS", "eng_unit": "mm/s", "alert_high": 4.5, "alert_high_tightened": 3.5,
        "origin": "public_proxy", "source_dataset": "NASA IMS bearing test 2",
        "points": [{"replay_hour": i, "value": round(float(df["P101_DE_VIB_RMS"][i]), 3)} for i in range(h + 1)],
        "summary": f"Vibration rose from {v0:.1f} to {v1:.1f} mm/s over the last 6 replay hours."}))
    write(out, "assets_P-101_health-history.json", env([{"replay_hour": i, "health_index": hdf["P-101__hi"][i],
                                                          "band": hdf["P-101__band"][i]} for i in range(h + 1)]))

    # HAZOP register and matrix
    nodes_out = []
    moved = {e["row_code"] for e in rescores}
    for code in ("N1", "N2"):
        rows = []
        for r in d.hazop["rows"]:
            if r["node"] != code:
                continue
            lv = live[r["row_code"]]
            sg_types = {s["ref_code"]: s["type"] for s in am["safeguards"]}
            rows.append({"row_code": r["row_code"], "version": 1, "status": "under_review" if r["row_code"] in moved else "approved",
                         "guide_word": r["guide_word"], "parameter": r["parameter"], "deviation": r["deviation"], "cause": r["cause"],
                         "consequence": r["consequence"], "severity": r["severity"], "likelihood_base": r["likelihood_base"],
                         "likelihood_live": lv["likelihood"], "score_live": lv["score"], "band_live": lv["band"],
                         "safeguards": [{"ref_code": s, "type": sg_types[s], "credited": s not in lv["safeguards_lost"]} for s in r["safeguards"]],
                         "rescored_this_run": r["row_code"] in moved, "origin": "synthetic"})
        nodes_out.append({"code": code, "name": nodes[code]["name"], "rows": rows})
    write(out, "hazop-rows.json", env({"nodes": nodes_out}))
    cells = []
    for lik in range(5, 0, -1):
        for sev in range(1, 6):
            cells.append({"likelihood": lik, "severity": sev, "score": lik * sev, "band": score_band(lik * sev, d.rules),
                          "live": [c for c, v in live.items() if v["likelihood"] == lik and v["severity"] == sev],
                          "design_basis": [c for c, v in base.items() if v["likelihood"] == lik and v["severity"] == sev and c in moved]})
    write(out, "hazop-rows_matrix.json", env({
        "cells": cells, "rule_set_version": d.rules["version"],
        "moved": [{"row_code": c, "from": {"likelihood": base[c]["likelihood"], "severity": base[c]["severity"]},
                   "to": {"likelihood": live[c]["likelihood"], "severity": live[c]["severity"]}} for c in sorted(moved)]}))

    row3 = next(r for r in d.hazop["rows"] if r["row_code"] == "HZ-N1-003")
    rule_text = {r["id"]: r["text"] for r in d.rules["rules"]}
    applied = live["HZ-N1-003"]["rules_applied"]
    hi_before = int(round(hdf["P-101__hi"][band_change["replay_hour"] - 1]))
    write(out, "hazop-rows_HZ-N1-003_why.json", env({
        "row_code": "HZ-N1-003", "deviation": row3["deviation"], "cause": row3["cause"],
        "design_basis": {"likelihood": base["HZ-N1-003"]["likelihood"], "severity": 4, "score": base["HZ-N1-003"]["score"], "band": base["HZ-N1-003"]["band"]},
        "live": {k: live["HZ-N1-003"][k] for k in ("likelihood", "severity", "score", "band")},
        "trigger": {"sensor_tag": band_change["trigger_tag"], "value": band_change["trigger_value"], "eng_unit": "mm/s",
                    "at": at(band_change["replay_hour"]), "replay_hour": band_change["replay_hour"], "asset_tag": "P-101",
                    "health_index_old": hi_before, "health_index_new": band_change["health_index"], "band": band_change["band"]},
        "rules": [{"rule_id": rid, "text": rule_text[rid], "applied": rid in applied} for rid in ("R-L-01", "R-L-02", "R-S-01")],
        "rule_set_version": d.rules["version"],
        "safeguards": [{"ref_code": s["ref_code"], "credited": s["ref_code"] not in live["HZ-N1-003"]["safeguards_lost"],
                        "depends_on": [{"tag": a, "band": bands_now.get(a, "not_monitored"),
                                        "health_index": hi(a) if a in hmodels else None} for a in s["depends_on"]]}
                       for s in am["safeguards"] if s["ref_code"] in row3["safeguards"]],
        "citations": [{"index": 1, "target_type": "chunk", "doc_code": "MAN-P101", "section": "6.3",
                       "title": "Bearing lubrication and vibration limits", "is_synthetic": True},
                      {"index": 2, "target_type": "chunk", "doc_code": "HAZOP-U100", "section": "node-1",
                       "title": "Unit 100 HAZOP worksheet, Node 1", "is_synthetic": True},
                      {"index": 3, "target_type": "tag_window", "sensor_tag": "P101_DE_VIB_RMS",
                       "hour_from": band_change["replay_hour"] - 6, "hour_to": band_change["replay_hour"]}],
        "latency_s": 0.2 * SECONDS_PER_HOUR / SPEED, "audit_id": next(e["audit_id"] for e in rescores if e["row_code"] == "HZ-N1-003")}))
    write(out, "risk-rule-sets_active.json", env(d.rules))

    # approvals: re-score items from the engine + one illustrative Red Team proposal
    items = []
    for i, e in enumerate(rescores):
        items.append({"id": f"fixture-rescore-{i + 1}", "artifact_type": "risk_rescore",
                      "title": f'{e["row_code"]} · {score_band(e["score_old"], d.rules).title()} → {e["band_new"].title()}',
                      "source": f'Risk Engine · {", ".join(e["rules_applied"])} {d.rules["version"]}', "judge": None,
                      "confidence": "high", "decision": "pending", "age_s": round((h - e["replay_hour"]) * SECONDS_PER_HOUR / SPEED, 1)})
    items.insert(0, {"id": "fixture-proposal-1", "artifact_type": "hazop_change", "title": "HZ-N1-003a · strainer common cause",
                     "source": "Red Team · redteam.v1 · Node 1", "judge": "pass", "confidence": "medium", "decision": "pending", "age_s": 0.3,
                     "_fixture_note": "Illustrative example of a Red Team proposal, written by hand from golden item GH-01. Not model output."})
    write(out, "approval-items.json", env(items, {"total": len(items), "skip": 0, "limit": 50}))

    # overview
    r3, r5 = live["HZ-N1-003"], live["HZ-N1-005"]
    counts = {b: sum(1 for v in live.values() if v["band"] == b) for b in ("low", "medium", "high", "extreme")}
    write(out, "units_U100_overview.json", env({
        "unit": {"code": "U100", "name": am["unit"]["name"], "nodes": 2, "assets": 6, "hazop_rows": len(d.hazop["rows"])},
        "replay": {"run_id": "fixture-run-s1", "scenario": "S1", "state": "running", "speed": SPEED, "replay_hour": h},
        "headline": {"tone": "warning",
                     "title": f"P-101 moved from Healthy to Degraded. {len(rescores)} linked HAZOP rows were re-scored.",
                     "detail": f"Health index {hi_before} → {band_change['health_index']}. "
                               f"HZ-N1-003 {base['HZ-N1-003']['band'].title()} → {r3['band'].title()}, "
                               f"HZ-N1-005 {base['HZ-N1-005']['band'].title()} → {r5['band'].title()}. Rule R-L-01 v1.",
                     "latency_s": 0.05, "link": {"screen": "matrix", "row_code": "HZ-N1-003"}},
        "health_tiles": tiles,
        "matrix_summary": {**counts, "moved": len(moved)},
        "rescored_rows": [{"row_code": e["row_code"], "deviation": next(r["deviation"] for r in d.hazop["rows"] if r["row_code"] == e["row_code"]),
                           "likelihood_old": base[e["row_code"]]["likelihood"], "likelihood_new": e["likelihood_new"], "severity": e["severity"],
                           "score_old": e["score_old"], "score_new": e["score_new"]} for e in rescores],
        "red_team_summary": None,
        "loop": [{"stage": "sense", "done": True, "at": at(band_change["replay_hour"])},
                 {"stage": "rescore", "done": True, "offset_s": 0.05},
                 {"stage": "red_team", "done": False}, {"stage": "approve", "done": False, "pending": len(items)}],
        "activity": [{"audit_id": a["audit_id"], "at": a["at"], "text": a["event"], "actor": a["actor"]} for a in audit[:6]]}))

    # documents
    docs = []
    for f in sorted((root / "corpus").glob("*.md")):
        fm = yaml.safe_load(f.read_text().split("---")[1])
        docs.append({"doc_code": fm["doc_code"], "title": fm["title"], "type": fm["type"], "revision": str(fm["revision"]),
                     "effective_date": str(fm["effective_date"]), "asset_tags": fm["asset_tags"], "is_current": fm["is_current"],
                     "is_synthetic": True})
    write(out, "documents.json", env([x for x in docs if x["is_current"]], {"total": sum(x["is_current"] for x in docs), "skip": 0, "limit": 50}))

    # evaluation: no fabricated results
    write(out, "eval-runs_latest.json", env({
        "run_id": None, "frozen": False, "finished_at": None, "gate": {"name": "G1", "passed": None, "total": 5},
        "objectives": [{"code": c, "passed": None, "value": None} for c in ("PO-1", "PO-2", "PO-3", "PO-4", "PO-5")],
        "_fixture_note": "No evaluation has been run. Values stay null until `make eval` writes a real run."}, message="No run yet"))
    write(out, "auth_demo-login_rina.json", env({"access_token": "fixture-token", "token_type": "bearer", "expires_in": 28800,
                                                 "user": {"id": "fixture-user-rina", "display_name": "Rina", "role": "process_safety_engineer"}}))

    # SSE samples
    sse = []
    seq = 0
    for e in s1["events"]:
        seq += 1
        name = e["type"] if e["type"] != "trip" else "trip"
        sse.append(f'id: {seq}\nevent: CUSTOM\ndata: {json.dumps({"type": "CUSTOM", "name": name, "value": e}, ensure_ascii=False)}\n')
    (out / "sse_unit-events_S1.txt").write_text("\n".join(sse) + "\n")
    chat = [
        ('RUN_STARTED', {"runId": "run_fx1", "threadId": "fixture-session", "input": {"content": "What is the procedure to switch P-101 to the standby pump?"}}),
        ('STEP_STARTED', {"stepName": "guard_input", "runId": "run_fx1"}), ('STEP_FINISHED', {"stepName": "guard_input", "runId": "run_fx1"}),
        ('STEP_STARTED', {"stepName": "retrieve", "runId": "run_fx1"}),
        ('TOOL_CALL_START', {"toolCallId": "tc1", "toolCallName": "hybrid_search"}),
        ('TOOL_CALL_ARGS', {"toolCallId": "tc1", "delta": json.dumps({"query": "switch P-101 to standby pump", "asset_tag": "P-101", "k": 8})}),
        ('TOOL_CALL_END', {"toolCallId": "tc1"}),
        ('TOOL_CALL_RESULT', {"toolCallId": "tc1", "content": "5 chunks: SOP-P101-02 (steps 3-7), MAN-P101 (5, 4.1), SHIFT-LOG-06"}),
        ('STEP_FINISHED', {"stepName": "retrieve", "runId": "run_fx1"}),
        ('STEP_STARTED', {"stepName": "draft_answer", "runId": "run_fx1"}),
        ('TEXT_MESSAGE_START', {"messageId": "msg_fx1", "role": "assistant"}),
        ('TEXT_MESSAGE_CONTENT', {"messageId": "msg_fx1", "delta": "Follow SOP-P101-02, steps 3 to 7. [1] "}),
        ('TEXT_MESSAGE_CONTENT', {"messageId": "msg_fx1", "delta": "First check the S-101 strainer differential pressure is below 0.5 bar, because a blocked strainer starves both pumps. [1][2] "}),
        ('TEXT_MESSAGE_CONTENT', {"messageId": "msg_fx1", "delta": "Then start P-101B, open its discharge slowly, stop P-101 and close its discharge valve. [1]"}),
        ('TEXT_MESSAGE_END', {"messageId": "msg_fx1"}),
        ('STEP_FINISHED', {"stepName": "draft_answer", "runId": "run_fx1"}),
        ('STEP_STARTED', {"stepName": "verify_citations", "runId": "run_fx1"}),
        ('CUSTOM', {"name": "citations", "value": [{"index": 1, "doc_code": "SOP-P101-02", "title": "Switchover to standby reflux pump", "section": "step-3", "revision": "C", "is_synthetic": True, "resolved": True},
                                                    {"index": 2, "doc_code": "MAN-P101", "title": "P-101 / P-101B reflux pump operating and maintenance manual", "section": "5", "revision": "3", "is_synthetic": True, "resolved": True}]}),
        ('CUSTOM', {"name": "answer_kind", "value": {"kind": "answer", "confidence": "high"}}),
        ('STEP_FINISHED', {"stepName": "verify_citations", "runId": "run_fx1"}),
        ('RUN_FINISHED', {"runId": "run_fx1", "result": {"kind": "answer", "confidence": "high", "prompt_version": "kb.v1"}}),
    ]
    lines = ["# Illustrative AG-UI chat stream for fixtures mode. The answer text is hand-written, not model output.\n"]
    for i, (typ, payload) in enumerate(chat, 1):
        lines.append(f"id: {i}\nevent: {typ}\ndata: {json.dumps({'type': typ, **payload}, ensure_ascii=False)}\n")
    (out / "sse_chat_example.txt").write_text("\n".join(lines) + "\n")
    print(f"fixtures written to {out}; snapshot S1 hour {h}; S1 events {len(s1['events'])}, S2 events {len(results['S2']['events'])}")


if __name__ == "__main__":
    main(sys.argv[1])
