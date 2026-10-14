"""Replay engine data side (spec Section 9.1): the scenario files and clock maths.

Each scenario file has one row per replay hour (240 hours) and one column per
sensor tag. The CSV twin of each parquet file is read, so no parquet reader is
needed. The asyncio task that drives the clock lives in
app/services/replay_runtime.py.
"""
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

SCENARIOS = ("S1", "S2")
REPLAY_HOURS = 240

# S1 ends with a vibration trip of P-101; P-101B takes over reflux duty.
TRIP_TAG = "P101_DE_VIB_RMS"
TRIP_LIMIT = 11.2
TRIP_ASSET = "P-101"
TRIP_STANDBY = "P-101B"


@dataclass(frozen=True)
class Scenario:
    code: str
    tags: tuple[str, ...]
    hours: tuple[dict[str, float], ...]

    @property
    def length(self) -> int:
        return len(self.hours)

    def trip_hour(self) -> Optional[int]:
        """First hour P-101 vibration reaches the trip limit, if it does."""
        for hour, values in enumerate(self.hours):
            if values.get(TRIP_TAG, 0.0) >= TRIP_LIMIT:
                return hour
        return None


def load_scenario(data_dir: Path, code: str) -> Scenario:
    """Read data/replay/<code>.csv: replay_hour plus one numeric column per tag."""
    path = data_dir / "replay" / f"{code}.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        tags = tuple(name for name in reader.fieldnames or [] if name != "replay_hour" and name.isupper())
        rows = sorted(reader, key=lambda row: int(row["replay_hour"]))
    hours = tuple({tag: float(row[tag]) for tag in tags} for row in rows)
    return Scenario(code=code, tags=tags, hours=hours)


@lru_cache(maxsize=4)
def get_scenario(data_dir: str, code: str) -> Scenario:
    """Cached scenario (the files never change while the app runs)."""
    return load_scenario(Path(data_dir), code)


def tick_seconds(speed: int, seconds_per_hour: float) -> float:
    """Wall-clock seconds per replay hour at a speed (2.0 s at 1x)."""
    return seconds_per_hour / speed
