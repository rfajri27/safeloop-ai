#!/usr/bin/env bash
# Rebuild every generated file in the package from the open sources and the hand-written seed files.
#   tools/fetch_sources.sh sources
#   tools/build_all.sh sources
# Requires Python 3.11+ with numpy, pandas, scipy, pyarrow, pyyaml, matplotlib.
set -euo pipefail
SRC_DIR="${1:-sources}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
DATA="$ROOT/data"

python3 "$HERE/extract_ims.py" "$DATA/replay/source_features/ims_test2_features.csv" \
  "$SRC_DIR/ims/Sensor Data/Bearing_Sensor_Data_pt1.zip" "$SRC_DIR/ims/Sensor Data/Bearing_Sensor_Data_pt2.zip"
python3 "$HERE/build_replay.py" "$DATA/replay/source_features/ims_test2_features.csv" "$SRC_DIR/tep" "$DATA/replay"
python3 "$HERE/build_fixtures.py" "$DATA"           # also writes replay/scenarios.json
python3 "$HERE/build_seed_sql.py" "$DATA" "$DATA/sql/seed.sql"
python3 "$HERE/plot_preview.py" "$DATA" "$ROOT/docs/replay_preview.png"
python3 "$HERE/validate.py" "$DATA"
