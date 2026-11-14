"""Packet-by-packet diff, v3 directory against v3.1 directory (QUANT_v3_1_RULE.md acceptance).

For every packet directory present in both: constructed_arrays.npz (every array, exact equality) and HAZARD.json
(every top-level key; for `provenance` and `members`, which keys differ). Data channels must be identical where the
schedule diff (DIFF_v3_v31.json) reports no change; identity digests change because the settings now carry the
quantization version.

    python3 research/harness-2026-11/F-DYN/fdyn/diff_packets.py --v3 _data/packets_v3 --v31 _data/packets_v31 --out PACKET_DIFF_v3_v31.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def diff_obj(a, b, path='', out=None, depth=0):
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict) and depth < 4:
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f'{path}/{k} (only in {"v31" if k not in a else "v3"})')
            else:
                diff_obj(a[k], b[k], f'{path}/{k}', out, depth + 1)
    elif isinstance(a, list) and isinstance(b, list) and depth < 4 and len(a) == len(b) and len(a) < 50:
        for i, (x, y) in enumerate(zip(a, b)):
            diff_obj(x, y, f'{path}[{i}]', out, depth + 1)
    elif a != b:
        out.append(path)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v3', type=Path, required=True)
    ap.add_argument('--v31', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    rows = []
    for d31 in sorted(p for p in a.v31.glob('*/*') if p.is_dir()):
        d3 = a.v3 / d31.parent.name / d31.name
        row = {'packet': f'{d31.parent.name}/{d31.name}', 'v3_present': d3.is_dir()}
        if d3.is_dir():
            z3, z31 = np.load(d3 / 'constructed_arrays.npz'), np.load(d31 / 'constructed_arrays.npz')
            row['arrays_differing'] = [k for k in sorted(set(z3.files) | set(z31.files))
                                       if k not in z3.files or k not in z31.files
                                       or not np.array_equal(z3[k], z31[k], equal_nan=True)]
            h3, h31 = json.loads((d3 / 'HAZARD.json').read_text()), json.loads((d31 / 'HAZARD.json').read_text())
            row['hazard_channels_identical'] = h3.get('channels') == h31.get('channels')
            row['hazard_members_identical'] = h3.get('members') == h31.get('members')
            row['hazard_paths_differing'] = diff_obj(h3, h31)
        else:
            row['note'] = 'no v3 packet on disk (boundary-cell sample for the acceptance test)'
        b = json.loads((d31 / 'BUILD_SUMMARY.json').read_text())
        row['v31_status'] = b.get('status')
        row['v31_quantization'] = (b.get('fdyn') or {}).get('quantization')
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ('packet', 'arrays_differing', 'hazard_channels_identical',
                                                    'hazard_members_identical')}))
    a.out.write_text(json.dumps({'rule': 'QUANT_v3_1_RULE.md', 'packets': rows}, indent=1))


if __name__ == '__main__':
    main()
