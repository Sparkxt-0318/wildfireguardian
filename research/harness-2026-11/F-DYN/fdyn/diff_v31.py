"""Schedule-level diff, v3 (binary64 floor) against v3.1 (integer ms; QUANT_v3_1_RULE.md), for every manifest entry.

The v3 module is the ignitions.py of commit 3630b89^ (passed as a file path); v3.1 is the current module. Compared per
entry: ignition times [S,H,W] and, for envelopes, hi_rel. Every differing cell-start is counted with its direction.

    python3 research/harness-2026-11/F-DYN/fdyn/diff_v31.py --v3-module PATH/ignitions_v3.py \
        --manifest research/harness-2026-11/F-DYN/MANIFEST_v3.json --out research/harness-2026-11/F-DYN/DIFF_v3_v31.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn import build, ignitions  # noqa: E402


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v3-module', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    spec = importlib.util.spec_from_file_location('ignitions_v3', a.v3_module)
    v3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v3)
    repo = HERE.parents[3]
    entries = json.loads(a.manifest.read_text())['entries']
    cache, rows = {}, []
    tot = {}
    for e in entries:
        cmd = e['cmd']
        lo = cache.setdefault(arg(cmd, '--arrival'), build.read_raster(repo / arg(cmd, '--arrival')))
        hi_p = arg(cmd, '--arrival-hi')
        hi = cache.setdefault(hi_p, build.read_raster(repo / hi_p)) if hi_p else None
        exp = (repo / arg(cmd, '--synthetic-export-dir')) if '--synthetic-export-dir' in cmd else \
            build.INPUTS / 'exports' / build.EVENT
        if '--synthetic-export-dir' in cmd and not (exp / f"FORECAST_{e['start']}.npz").exists():
            from fdyn import synthetic_export          # written on demand, exactly as build.py does
            synthetic_export.write(repo / arg(cmd, '--kriged-toa'), e['start'], exp)
        with np.load(exp / f"FORECAST_{e['start']}.npz") as z:
            burned = z['source_burned_area_valid'] & (z['source_burned_area'] == 1)
            T = float(z['contract__cell_duration_s'])
        start = build.dt.datetime.strptime(e['start'], '%Y%m%dT%H%M%SZ').replace(tzinfo=build.dt.timezone.utc)
        h = (start - build.T0_UTC).total_seconds() / 3600.0
        H = e['horizon_h'] * 3600.0
        if hi is None:
            old = v3.schedule(lo, h, H, 300.0, ('central',), burned, T)
            new = ignitions.schedule(lo, h, H, 300.0, ('central',), burned, T)
            pairs = [('births', old, new)]
        else:
            ob, oe = v3.envelope_schedule(lo, hi, h, H, 300.0, burned, T)
            nb, ne = ignitions.envelope_schedule(lo, hi, h, H, 300.0, burned, T)
            pairs = [('births', ob, nb), ('hi_rel', oe, ne)]
        row = {'region': e['region'], 'start': e['start'], 'horizon_h': e['horizon_h'], 'variant': e['variant']}
        for name, o, n in pairs:
            same_set = np.array_equal(np.isfinite(o), np.isfinite(n))
            both = np.isfinite(o) & np.isfinite(n)
            d = n[both] - o[both]
            row[name] = {'igniting_v3': int(np.isfinite(o).sum()), 'igniting_v31': int(np.isfinite(n).sum()),
                         'same_igniting_set': bool(same_set),
                         'only_v3': int((np.isfinite(o) & ~np.isfinite(n)).sum()),
                         'only_v31': int((~np.isfinite(o) & np.isfinite(n)).sum()),
                         'later_300': int((d == 300).sum()), 'earlier_300': int((d == -300).sum()),
                         'other_diff': int(((d != 0) & (np.abs(d) != 300)).sum())}
            k = (e['variant'], name)
            t = tot.setdefault(f'{k[0]}:{k[1]}', {'entries': 0, 'entries_differing': 0, 'later_300': 0, 'earlier_300': 0,
                                                  'other_diff': 0, 'only_v3': 0, 'only_v31': 0})
            t['entries'] += 1
            r = row[name]
            changed = r['later_300'] + r['earlier_300'] + r['other_diff'] + r['only_v3'] + r['only_v31']
            t['entries_differing'] += int(changed > 0)
            for f in ('later_300', 'earlier_300', 'other_diff', 'only_v3', 'only_v31'):
                t[f] += r[f]
        rows.append(row)
    a.out.write_text(json.dumps({'rule': 'QUANT_v3_1_RULE.md', 'manifest': str(a.manifest), 'totals': tot,
                                 'entries': rows}, indent=1))
    print(json.dumps(tot, indent=1))


if __name__ == '__main__':
    main()
