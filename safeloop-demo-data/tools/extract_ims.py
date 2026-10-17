"""Extract per-snapshot vibration features from the NASA IMS bearing data, test 2.

Input: the raw IMS 2nd_test snapshot files (one file per 10-minute snapshot,
20,480 samples x 4 channels, one channel per bearing), read straight from the
zip archives of a public mirror. Output: one CSV row per snapshot with RMS,
peak, kurtosis and crest factor for each of the four bearings.

Usage:
    python extract_ims.py OUT.csv ZIP [ZIP ...]

Source dataset: J. Lee, H. Qiu, G. Yu, J. Lin and Rexnord Technical Services,
"Bearing Data Set", IMS, University of Cincinnati, NASA Prognostics Data
Repository. In test 2, bearing 1 failed with an outer-race defect.
"""
from __future__ import annotations

import io
import sys
import zipfile
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import kurtosis


def snapshot_features(raw: bytes) -> dict[str, float]:
    """Return RMS, peak, kurtosis and crest factor for each of the 4 channels."""
    data = np.loadtxt(io.BytesIO(raw))
    if data.ndim != 2 or data.shape[1] != 4:
        raise ValueError(f"unexpected snapshot shape {data.shape}")
    out: dict[str, float] = {}
    for ch in range(4):
        x = data[:, ch] - data[:, ch].mean()
        rms = float(np.sqrt(np.mean(x**2)))
        peak = float(np.max(np.abs(x)))
        out[f"b{ch + 1}_rms_g"] = rms
        out[f"b{ch + 1}_peak_g"] = peak
        out[f"b{ch + 1}_kurtosis"] = float(kurtosis(x, fisher=False))
        out[f"b{ch + 1}_crest"] = peak / rms if rms else float("nan")
    return out


def main(out_csv: str, zips: list[str]) -> None:
    rows = []
    for zpath in zips:
        with zipfile.ZipFile(zpath) as z:
            for name in z.namelist():
                base = name.rsplit("/", 1)[-1]
                if name.startswith("__MACOSX") or not base or base.startswith("."):
                    continue
                ts = datetime.strptime(base, "%Y.%m.%d.%H.%M.%S")
                feats = snapshot_features(z.read(name))
                rows.append({"snapshot": base, "timestamp": ts.isoformat(), **feats})
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df.to_csv(out_csv, index=False, float_format="%.6g")
    print(f"{len(df)} snapshots, {df.timestamp.iloc[0]} to {df.timestamp.iloc[-1]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
