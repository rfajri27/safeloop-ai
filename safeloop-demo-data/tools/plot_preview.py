"""Draw docs/replay_preview.png: the driving signal of each scenario with its health bands.

Usage:
    python plot_preview.py DATA_DIR OUT_PNG
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE, INK, INK2, GRID, SERIES = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"


def hi_to_x(hi: float, model: dict) -> float:
    return model["x_healthy"] + (100 - hi) / 100 * (model["x_fail"] - model["x_healthy"])


def panel(ax, df, tag, unit, model, events, title, ylim):
    ax.set_facecolor(SURFACE)
    x80, x50 = hi_to_x(80, model), hi_to_x(50, model)
    for y, label in ((x80, "HI 80 · Degraded below"), (x50, "HI 50 · Critical below")):
        ax.axhline(y, color=INK2, lw=1, ls=(0, (4, 3)), zorder=1)
        ax.text(2, y, label, ha="left", va="bottom", fontsize=8.5, color=INK2)
    ax.plot(df.replay_hour, df[tag], color=SERIES, lw=2, zorder=3)
    for e in events:
        y = float(df[tag][e["replay_hour"]])
        ax.plot([e["replay_hour"]], [y], "o", ms=7, color=SERIES, mec=SURFACE, mew=2, zorder=4)
        if not e["label"]:
            continue
        ax.annotate(e["label"], (e["replay_hour"], y), xytext=e.get("offset", (-8, 10)), textcoords="offset points",
                    ha=e.get("ha", "right"), fontsize=8.5, color=INK, arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.8},
                    bbox={"boxstyle": "round,pad=0.2", "fc": SURFACE, "ec": "none"})
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold", pad=8)
    ax.set_ylabel(unit, color=INK2, fontsize=9)
    ax.set_xlim(0, 240)
    ax.set_ylim(*ylim)
    ax.set_xticks(range(0, 241, 40))
    ax.grid(axis="y", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5, length=0)


def main(data_dir: str, out_png: str) -> None:
    root = Path(data_dir)
    models = {m["asset"]: m for m in json.loads((root / "seed/health_models.json").read_text())["models"]}
    man = json.loads((root / "replay/scenarios.json").read_text())["scenarios"]
    s1, s2 = pd.read_csv(root / "replay/S1.csv"), pd.read_csv(root / "replay/S2.csv")
    trip = man["S1"]["trip_hour"]
    ev1 = []
    for e in man["S1"]["expected_events"]:
        if e["type"] != "health_band_changed":
            continue
        if e["band"] == "critical":
            ev1.append({"replay_hour": e["replay_hour"], "label": f'P-101 critical h{e["replay_hour"]}, trips h{trip}', "offset": (-24, 40)})
        else:
            ev1.append({"replay_hour": e["replay_hour"], "label": f'P-101 degraded, h{e["replay_hour"]}', "offset": (-10, 12)})
    ev1.append({"replay_hour": trip, "label": None})
    ev2 = [{"replay_hour": e["replay_hour"], "label": f'E-301 {e["band"]}, h{e["replay_hour"]}', "offset": (14, 56), "ha": "left"}
           for e in man["S2"]["expected_events"] if e["type"] == "health_band_changed"]
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.6), facecolor=SURFACE)
    panel(axes[0], s1, "P101_DE_VIB_RMS", "mm/s RMS", models["P-101"], ev1,
          "S1 · P-101 drive-end vibration (NASA IMS test 2, bearing 1)", (0, 20))
    panel(axes[1], s2, "TV301_POS", "% open", models["E-301"], ev2,
          "S2 · TV-301 position, E-301 cooling margin (TEP IDV 5, fault at hour 40)", (45, 85))
    axes[1].set_xlabel("Replay hour", color=INK2, fontsize=9)
    fig.text(0.01, 0.005, "Raw hourly values. Bands are judged on a 6-hour rolling median with a 24-hour recovery hold (hi.v1).",
             fontsize=8, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=160, facecolor=SURFACE)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
