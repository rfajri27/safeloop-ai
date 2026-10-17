#!/usr/bin/env bash
# Download the two open datasets used to build the replay files, into SRC_DIR (default ./sources).
# Raw source data is not shipped in this package; run this, then tools/build_all.sh, to rebuild from scratch.
set -euo pipefail
SRC_DIR="${1:-sources}"
mkdir -p "$SRC_DIR"

# Tennessee Eastman Process test runs (Braatz lab, University of Illinois licence; see LICENSES/).
# Pinned to the commit used to build this package.
if [ ! -d "$SRC_DIR/tep" ]; then
  git clone https://github.com/camaramm/tennessee-eastman-profBraatz.git "$SRC_DIR/tep"
  git -C "$SRC_DIR/tep" checkout 0643318858ce7c87292bd59820b459e12a13d009
fi

# NASA IMS bearing test 2 raw snapshots (U.S. Government work, via data.gov).
# Original: https://catalog.data.gov/dataset/ims-bearings (NASA Prognostics Data Repository).
# GitHub mirror of the 2nd_test snapshots used here, pinned to the commit used to build this package:
if [ ! -d "$SRC_DIR/ims" ]; then
  git clone https://github.com/BLarzalere/LSTM-Autoencoder-for-Anomaly-Detection.git "$SRC_DIR/ims"
  git -C "$SRC_DIR/ims" checkout db20db37d9d533bb91a3b2549d896047e03a3f3c
fi
echo "Sources ready in $SRC_DIR"
