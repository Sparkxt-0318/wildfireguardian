#!/usr/bin/env bash
# Builds and runs the HOST/SIMULATED tests (no ESP32 hardware involved).
# Usage: firmware/test/host/run_host_tests.sh            (from anywhere)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FW="$(cd "$HERE/../.." && pwd)"
SAMPLES="$(cd "$FW/.." && pwd)/phone_export/samples"
# Build outside the source tree (some mounts are noexec). Override with WFG_BUILD_DIR.
BUILD="${WFG_BUILD_DIR:-${TMPDIR:-/tmp}/wfg_host_build}"
mkdir -p "$BUILD" "$SAMPLES"
CXX="${CXX:-g++}"
"$CXX" -std=c++17 -O1 -g -Wall -Wextra -Wno-format-truncation -fsanitize=address,undefined \
  -I"$FW/lib/wfg_core/src" "$HERE/test_core.cpp" "$FW"/lib/wfg_core/src/*.cpp -o "$BUILD/test_core"
"$BUILD/test_core" "$BUILD/tmp" "$SAMPLES"
# USB protocol fake device + Python exporter tests (pyserial required)
"$CXX" -std=c++17 -O1 -Wall -Wextra -Wno-format-truncation -I"$FW/lib/wfg_core/src" \
  "$HERE/fake_device.cpp" "$FW"/lib/wfg_core/src/*.cpp -o "$BUILD/fake_device"
python3 "$FW/../phone_export/tests/test_usb_export.py" "$BUILD/fake_device"
