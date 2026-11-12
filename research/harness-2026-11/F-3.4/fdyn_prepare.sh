#!/usr/bin/env bash
# Build the 4 F-DYN v3 packets of FDYN_PLAN.md from Leo's branch (exact MANIFEST_v3 commands), the interim full-grid
# graphs, the FIRMS variants and INSTANCE.json. Usage: fdyn_prepare.sh LEO_WORKTREE PYTHON (python with numpy 1.26.4,
# scipy, rasterio, pandas, pyproj 3.7.0, wfg_latest). The worktree needs data/routing (fetch_routing_inputs or symlink).
set -euo pipefail
W="${1:?leo worktree}"; PY="${2:?python}"
cd "$W"
F=research/harness-2026-11/F-DYN
[ -d data/routing ] || { echo "missing $W/data/routing"; exit 2; }
for r in uiseong_andong_2025 yeongdeok_2025; do
  g=$F/_data/graphs_interim/$r/graph.json
  [ -f "$g" ] || "$PY" $F/fdyn/regrid_graph.py --region $r --out "$g"
done
[ -d $F/_data/variants ] || "$PY" $F/fdyn/variants.py --toa $F/_data/KFS_01_pswt_ok_toa.tif --firms-dir $F/_data/firms --out-dir $F/_data/variants
[ -f $F/_data/INSTANCE.json ] || "$PY" $F/fdyn/instance.py --out $F/_data/INSTANCE.json
"$PY" - "$F" "$PY" <<'EOF'
import json, subprocess, sys
F, PY = sys.argv[1], sys.argv[2]
m = json.load(open(F + '/MANIFEST_v3.json'))
want = {('uiseong_andong_2025', '20250325T170000Z'), ('yeongdeok_2025', '20250325T230000Z')}
for e in m['entries']:
    if (e['region'], e['start']) in want and e['horizon_h'] == 5 and e['variant'] in ('kriged_mean', 'firms_early'):
        import os
        if os.path.exists(e['out'] + '/HAZARD.json'):
            print('exists', e['out']); continue
        cmd = [PY] + e['cmd'][1:]
        print('build', e['out'], flush=True)
        subprocess.run(cmd, check=True)
EOF
sha256sum $F/_data/packets_v3/*/*_h5_*/HAZARD.json $F/_data/packets_v3/*/*_h5_*/constructed_arrays.npz $F/_data/graphs_interim/*/graph.json
