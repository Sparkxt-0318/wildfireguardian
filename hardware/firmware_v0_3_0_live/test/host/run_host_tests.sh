#!/usr/bin/env bash
# Builds and runs the HOST/SIMULATED tests (no ESP32 hardware involved).
# Usage: firmware_v0_3_0_live/test/host/run_host_tests.sh            (from anywhere)
#   WFG_BUILD_DIR    build directory (default ${TMPDIR:-/tmp}/wfg_host_build)
#   WFG_SAMPLES_DIR  where test_core writes the sample sessions and reads format_v1/ (default ../phone_export/samples,
#                    as in 0.2.0; point it at a copy to leave that folder untouched)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FW="$(cd "$HERE/../.." && pwd)"
SAMPLES="${WFG_SAMPLES_DIR:-$(cd "$FW/.." && pwd)/phone_export/samples}"
# Build outside the source tree (some mounts are noexec). Override with WFG_BUILD_DIR.
BUILD="${WFG_BUILD_DIR:-${TMPDIR:-/tmp}/wfg_host_build}"
mkdir -p "$BUILD" "$SAMPLES"
CXX="${CXX:-g++}"
"$CXX" -std=c++17 -O1 -g -Wall -Wextra -Wno-format-truncation -fsanitize=address,undefined \
  -I"$FW/lib/wfg_core/src" "$HERE/test_core.cpp" "$FW"/lib/wfg_core/src/*.cpp -o "$BUILD/test_core"
"$BUILD/test_core" "$BUILD/tmp" "$SAMPLES"
# USB protocol fake device + Python exporter tests (pyserial required); -B: no __pycache__ in the source folders
"$CXX" -std=c++17 -O1 -Wall -Wextra -Wno-format-truncation -I"$FW/lib/wfg_core/src" \
  "$HERE/fake_device.cpp" "$FW"/lib/wfg_core/src/*.cpp -o "$BUILD/fake_device"
python3 -B "$FW/../phone_export/tests/test_usb_export.py" "$BUILD/fake_device"
# LIVE lines through the fake device (Python standard library only)
python3 -B "$HERE/test_fake_device_live.py" "$BUILD/fake_device"
