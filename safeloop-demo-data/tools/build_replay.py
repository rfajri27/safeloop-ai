"""Build the S1 and S2 replay files for SafeLoop Unit 100 from open datasets.

Every tag is mapped from a real public signal except P101_BRG_TEMP, which the
IMS data does not contain; it is derived from the real vibration with a
documented first-order model and labelled synthetic.

Usage:
    python build_replay.py IMS_FEATURES_CSV TEP_DIR OUT_DIR

Outputs in OUT_DIR:
    S1.csv / S1.parquet   240 replay hours, P-101 bearing degradation (NASA IMS test 2)
    S2.csv / S2.parquet   240 replay hours, E-301 cooling loss (TEP IDV(5))
    tag_mapping.json      source signal, transform and label for every tag
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HOURS = 240
TEP_SAMPLES_PER_HOUR = 4  # TEP test runs: 960 samples every 3 min = 48 h; 4 samples = 12 min per replay hour

# TEP column numbers (1-based) in the Braatz files: XMEAS(1..41) then XMV(1..11)
TEP = {"XMEAS11": 11, "XMEAS12": 12, "XMEAS13": 13, "XMEAS14": 14, "XMEAS22": 22, "XMV11": 52}

# Linear rescales from source units to Unit 100 engineering ranges (shape preserved).
# Baselines are the means of the TEP normal-operation test run (d00_te.dat).
TEP_MAP = {
    "FI201_REFLUX_FLOW": ("XMEAS14", 20.0, 0.8, "m3/h", "Separator underflow, rescaled to reflux flow"),
    "LI201_V201_LEVEL": ("XMEAS12", 50.0, 1.0, "%", "Separator level, kept in %"),
    "PI201_V201_PRESS": ("XMEAS13", 1.80, 0.01, "barg", "Separator pressure kPa, rescaled to barg"),
    "TI301_CW_OUT": ("XMEAS22", 35.0, 2.0, "degC", "Separator cooling-water outlet temperature, rescaled"),
    "TV301_POS": ("XMV11", 55.0, 4.0, "%", "Condenser cooling-water flow valve, rescaled to position %"),
}


def ims_hourly(features_csv: str) -> pd.DataFrame:
    """Average the IMS snapshots into 240 replay hours (about 4.1 snapshots, 41 min each)."""
    d = pd.read_csv(features_csv)
    d = d[d.b1_rms_g > 0.01].reset_index(drop=True)  # drop the 2 snapshots taken after the rig stopped
    n = len(d)
    rows = []
    for h in range(HOURS):
        a, b = int(np.floor(h * n / HOURS)), int(np.floor((h + 1) * n / HOURS))
        seg = d.iloc[a:b]
        rows.append({
            "replay_hour": h,
            "ims_first_snapshot": seg.snapshot.iloc[0],
            "b1_rms_g": seg.b1_rms_g.mean(),
            "b1_kurtosis": seg.b1_kurtosis.mean(),
            "b4_rms_g": seg.b4_rms_g.mean(),
        })
    return pd.DataFrame(rows)


def tep_hourly(path: Path) -> pd.DataFrame:
    """Average a 960-sample TEP test run into 240 replay hours."""
    x = np.loadtxt(path)
    out = {"replay_hour": np.arange(HOURS)}
    for name, col in TEP.items():
        out[name] = x[:, col - 1].reshape(HOURS, TEP_SAMPLES_PER_HOUR).mean(axis=1)
    return pd.DataFrame(out)


def map_tep(tep: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """Rescale TEP signals onto Unit 100 tags around the normal-run baseline."""
    out = pd.DataFrame({"replay_hour": tep.replay_hour})
    for tag, (src, centre, scale, _unit, _desc) in TEP_MAP.items():
        out[tag] = centre + (tep[src] - base[src].mean()) * scale
    return out


def bearing_temp(vib_mm_s: np.ndarray) -> np.ndarray:
    """Synthetic bearing temperature: first-order lag (tau 3 h) on vibration excess, seeded noise."""
    rng = np.random.default_rng(100)
    target = 58.0 + 2.2 * np.clip(vib_mm_s - 2.8, 0, None)
    temp = np.empty_like(target)
    temp[0] = target[0]
    alpha = 1 - np.exp(-1 / 3.0)
    for i in range(1, len(target)):
        temp[i] = temp[i - 1] + alpha * (target[i] - temp[i - 1])
    return temp + rng.normal(0, 0.3, len(temp))


def build(features_csv: str, tep_dir: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ims = ims_hourly(features_csv)
    k_b1 = 2.8 / ims.b1_rms_g.iloc[:100].median()  # healthy median maps to 2.8 mm/s
    k_b4 = 2.0 / ims.b4_rms_g.iloc[:100].median()  # standby pump baseline 2.0 mm/s
    tep_dir_p = Path(tep_dir)
    base = tep_hourly(tep_dir_p / "d00_te.dat")
    normal = map_tep(base, base)
    idv5 = map_tep(tep_hourly(tep_dir_p / "d05_te.dat"), base)

    # S1: P-101 degrades (IMS test 2, full run); process signals from the TEP normal run.
    s1 = normal.copy()
    s1["P101_DE_VIB_RMS"] = ims.b1_rms_g * k_b1
    s1["P101_DE_VIB_KURT"] = ims.b1_kurtosis
    s1["P101_BRG_TEMP"] = bearing_temp(s1["P101_DE_VIB_RMS"].to_numpy())
    # P-101B is a separate machine. On the IMS rig all four bearings share one shaft, so the
    # failing bearing 1 shakes bearing 4 near the end; a separate pump would not feel that.
    # Use bearing 4 from the healthy first 100 replay hours only, repeated in order.
    healthy_idx = np.arange(HOURS) % 100
    s1["P101B_DE_VIB_RMS"] = ims.b4_rms_g.iloc[healthy_idx].to_numpy() * k_b4
    s1.insert(1, "ims_first_snapshot", ims.ims_first_snapshot)

    # S2: E-301 loses cooling margin (TEP IDV(5), fault at sample 160 = replay hour 40);
    # P-101 runs healthy, using the first 100 hourly IMS values (all healthy), repeated in order.
    s2 = idv5.copy()
    s2["P101_DE_VIB_RMS"] = ims.b1_rms_g.iloc[healthy_idx].to_numpy() * k_b1
    s2["P101_DE_VIB_KURT"] = ims.b1_kurtosis.iloc[healthy_idx].to_numpy()
    s2["P101_BRG_TEMP"] = bearing_temp(s2["P101_DE_VIB_RMS"].to_numpy())
    s2["P101B_DE_VIB_RMS"] = ims.b4_rms_g.iloc[healthy_idx].to_numpy() * k_b4

    cols = ["replay_hour", "P101_DE_VIB_RMS", "P101_DE_VIB_KURT", "P101_BRG_TEMP", "P101B_DE_VIB_RMS",
            "FI201_REFLUX_FLOW", "LI201_V201_LEVEL", "PI201_V201_PRESS", "TI301_CW_OUT", "TV301_POS"]
    for name, df in [("S1", s1), ("S2", s2)]:
        extra = ["ims_first_snapshot"] if name == "S1" else []
        df = df[cols + extra].round(4)
        df.to_csv(out / f"{name}.csv", index=False)
        df.to_parquet(out / f"{name}.parquet", index=False)

    mapping = {
        "replay_hours": HOURS,
        "tags": {
            "P101_DE_VIB_RMS": {"unit": "mm/s", "origin": "public_proxy", "source_dataset": "NASA IMS bearing test 2",
                                "source_signal": "bearing 1 (failed, outer race), channel 1, RMS of each 1 s snapshot",
                                "transform": f"S1: mean of ~4.1 snapshots per replay hour x {k_b1:.2f} (healthy median -> 2.8 mm/s). "
                                             "S2: first 100 healthy hours repeated."},
            "P101_DE_VIB_KURT": {"unit": "-", "origin": "public_proxy", "source_dataset": "NASA IMS bearing test 2",
                                 "source_signal": "bearing 1 kurtosis of each snapshot", "transform": "hourly mean, unscaled"},
            "P101_BRG_TEMP": {"unit": "degC", "origin": "synthetic", "source_dataset": "derived from P101_DE_VIB_RMS",
                              "source_signal": "none: IMS has no temperature channel",
                              "transform": "58 + 2.2 x max(0, vib - 2.8), first-order lag tau 3 h, N(0, 0.3) noise, seed 100"},
            "P101B_DE_VIB_RMS": {"unit": "mm/s", "origin": "public_proxy", "source_dataset": "NASA IMS bearing test 2",
                                 "source_signal": "bearing 4 (did not fail), RMS",
                                 "transform": f"hourly mean x {k_b4:.2f} (healthy median -> 2.0 mm/s); "
                                              "first 100 healthy hours repeated in both scenarios, because the "
                                              "rig's shared shaft couples the failing bearing into bearing 4"},
        },
    }
    for tag, (src, centre, scale, unit, desc) in TEP_MAP.items():
        mapping["tags"][tag] = {
            "unit": unit, "origin": "public_proxy", "source_dataset": "Tennessee Eastman Process (Braatz test runs)",
            "source_signal": f"{src}: {desc}. S1 from d00_te.dat (normal), S2 from d05_te.dat (IDV 5)",
            "transform": f"{centre} + (x - normal mean) x {scale}; 4 samples (12 min) averaged per replay hour",
        }
    (out / "tag_mapping.json").write_text(json.dumps(mapping, indent=2))
    print("S1", s1.shape, "S2", s2.shape, f"k_b1={k_b1:.3f} k_b4={k_b4:.3f}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
