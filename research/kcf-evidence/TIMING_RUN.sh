#!/bin/bash
# Clean single-process timing of the F-3.1 deadline field on the six recorded planner caches (item 1).
# Run on the evaluated Mac, from the repository root, on an otherwise idle machine, with Python 3.12 or 3.13 and numpy.
#   bash research/kcf-evidence/TIMING_RUN.sh RUN_DIR
# Then:  python3 research/kcf-evidence/summarize_timing.py RUN_DIR research/kcf-evidence/TIMING_<host>.json
set -euo pipefail
RUN_DIR=${1:?usage: TIMING_RUN.sh RUN_DIR (a new empty directory outside the repository)}
mkdir -p "$RUN_DIR"
[ -d data/routing ] || python3 tools/fetch_routing_inputs.py          # frozen graphs + packets, SHA-256 verified
ROOT=$(pwd)
cd research/harness-2026-11/F-3.1
for f in uiseong_andong_2025/20250323T010000Z uiseong_andong_2025/20250324T090000Z uiseong_andong_2025/20250325T170000Z \
         yeongdeok_2025/20250325T190000Z yeongdeok_2025/20250325T230000Z yeongdeok_2025/20250326T080000Z; do
  n=$(basename "$f")
  s=$(python3 -c 'import time;print(time.time())')
  python3 -m deadline_field.reproduce "$ROOT/planner/cache/$f.json" --timing-only --out "$RUN_DIR/$n.json" > "$RUN_DIR/$n.stdout"
  e=$(python3 -c 'import time;print(time.time())')
  python3 -c "print('$n outer_wall_s=%.3f' % ($e - $s))" >> "$RUN_DIR/WALL.txt"
done
uname -a > "$RUN_DIR/HOST.txt"; python3 -c 'import sys,numpy;print(sys.version, numpy.__version__)' >> "$RUN_DIR/HOST.txt"
