"""Packet self-check: do the routing arrays and HAZARD.json express the same hazard law?

Array readers (experimental/scenario-members contact.py ContactModel.from_packet, frontend.build_instance, certificates)
see ONLY constructed_arrays.npz ignition_time_s [S,H,W] + current_active [H,W] and REPORT construction assumptions
burning_duration_s (T) and initial_remaining_s (R): member s cell c is active on [birth, birth + T), present fire on
[0, R). HAZARD.json members carry breakpoints and per-bin flame masks (flat, row 0 = south).

For every member: on every HAZARD bin [l, r) the array-law active set must be constant (no array knot strictly inside)
and equal to the HAZARD flame mask. Any difference is reported cell by cell; `consistent` is True only with none.

    python3 research/harness-2026-11/F-DYN/fdyn/consistency.py PACKET_DIR [PACKET_DIR ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

TOL = 1e-6   # s: exact b + T vs the writer's rounded-up float end (sub-microsecond, reported by Thomas)


def check(packet_dir) -> dict:
    d = Path(packet_dir)
    rep = json.loads((d / 'REPORT.json').read_text())
    asm = rep['native_metadata']['construction']['assumptions']
    T, R = float(asm['burning_duration_s']), float(asm['initial_remaining_s'])
    hz = json.loads((d / 'HAZARD.json').read_text())
    with np.load(d / 'constructed_arrays.npz', allow_pickle=False) as a:
        ign = np.asarray(a['ignition_time_s'], float)
        cur = np.asarray(a['current_active'], bool)
    S, H, W = ign.shape
    out = {'packet': str(d), 'T': T, 'R': R, 'members': S, 'member_rows': []}
    if np.isnan(ign).any():
        out.update(consistent=False, array_path='REFUSED (NaN ignition: ContactModel.from_arrays rejects)')
        return out
    ok = True
    for s in range(S):
        b = np.flipud(ign[s]).ravel()                      # to HAZARD layout: flat, row 0 = south
        c = np.flipud(cur).ravel() if R > 0 else np.zeros(H * W, bool)
        fin = np.isfinite(b)
        knots = set(b[fin].tolist()) | set((b[fin] + T).tolist()) | ({R} if c.any() else set())
        m = hz['members'][s]
        bp = [float(x) for x in m['breakpoints']]
        mis_cells, misaligned, hz_ever, arr_ever = 0, 0, np.zeros(H * W, bool), np.zeros(H * W, bool)
        for k in range(len(bp) - 1):
            l, r = bp[k], bp[k + 1]
            misaligned += sum(1 for t in knots if l + TOL < t < r - TOL)   # writer ends use round_up_sum (>= exact)
            arr = (fin & (b <= l) & (l < b + T)) | (c & (l < R))
            fl = np.asarray(m['flame'][k], bool)
            mis_cells += int((arr != fl).sum())
            hz_ever |= fl
            arr_ever |= arr
        row = {'member': s, 'bins': len(bp) - 1, 'cell_bin_mismatches': mis_cells, 'array_knots_inside_bins': misaligned,
               'hazard_cells_ever': int(hz_ever.sum()), 'array_cells_ever': int(arr_ever.sum()),
               'hazard_only_cells': int((hz_ever & ~arr_ever).sum()), 'array_only_cells': int((arr_ever & ~hz_ever).sum())}
        ok &= mis_cells == 0 and misaligned == 0
        out['member_rows'].append(row)
    out['consistent'] = bool(ok)
    return out


if __name__ == '__main__':
    bad = 0
    for p in sys.argv[1:]:
        r = check(p)
        bad += not r['consistent']
        print(json.dumps({k: r[k] for k in ('packet', 'consistent', 'T', 'R')} | {'rows': r.get('member_rows'),
                                                                            'array_path': r.get('array_path')}))
    sys.exit(1 if bad else 0)
