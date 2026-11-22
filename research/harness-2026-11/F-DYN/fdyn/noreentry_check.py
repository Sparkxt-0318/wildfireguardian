"""NOREENTRY_RULE.md acceptance 1-6 on chosen MANIFEST_v3_6 (region, start, H, variant) samples.

Per sample: build (if absent) the reopening (v3.5-path) and the no_reentry packet from their manifest commands, then
  1  the reopening HAZARD sha256 (no transform) is reported against the per-numpy v3.5 table where one is recorded
  2  builder self-check of the no_reentry packet (BUILD_SUMMARY fdyn.packet_self_check) and its transform identity
  3  own derivation: for every member and HAZARD bin [l, r) of the no_reentry packet, flame == {cells whose reopening
     phase birth b <= l} (births from the reopening packet's flame bins: first flame bin start per member and cell)
  4  flux: max and total (sum over bins x duration) per member, no_reentry vs reopening (reported, not asserted)
  5  array path: no_reentry packets (envelope included) are scalar-law consistent (fdyn/consistency.py)
  6  Richard's reader: deadline_field.real.load_packet on both packets; per member, same cells, same births, and the
     no_reentry phase ends at or beyond H ("never" arm = reopening phases with end -> infinity)

    python3 research/harness-2026-11/F-DYN/fdyn/noreentry_check.py --richard-dir DIR_CONTAINING_deadline_field \
        --only REGION:START:H:VARIANT [...] --out NOREENTRY_CHECK.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MAN = REPO / 'research/harness-2026-11/F-DYN/MANIFEST_v3_6.json'
V35_KRIGED_YD25T11_H5 = {'2.5': '6940f2939318126437b6109853033ab0b1534dd288f3775c6c0352ed44646f2f',
                         '1.26': '5716c09e70b285ce10db54bc87ec37c89987d124ae7010438a02870dfe5d4326'}
sys.path.insert(0, str(HERE.parent))
from fdyn import consistency  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build(e):
    out = REPO / e['out']
    if (out / 'BUILD_SUMMARY.json').exists():
        return 0, 'present'
    cmd = list(e['cmd'])
    if cmd[0] == 'python3':
        cmd[0] = sys.executable
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def births_from_bins(hz):
    """per member: {cell: birth} from the first flame bin (HAZARD flat layout)."""
    out = []
    for m in hz['members']:
        bp = m['breakpoints']
        b = {}
        for k, row in enumerate(m['flame']):
            for c in np.flatnonzero(np.asarray(row, bool)):
                b.setdefault(int(c), bp[k])
        out.append(b)
    return out


def own_derivation(hz_re, hz_nr, H):
    births = births_from_bins(hz_re)
    bad = 0
    for s, m in enumerate(hz_nr['members']):
        bp = m['breakpoints']
        if bp[-1] != H:
            bad += 1
        for k, row in enumerate(m['flame']):
            l = bp[k]
            want = np.zeros(len(row), bool)
            idx = [c for c, b in births[s].items() if b <= l]
            want[idx] = True
            bad += int((np.asarray(row, bool) != want).sum())
    return bad


def flux_stats(hz):
    rows = []
    for m in hz['members']:
        bp = np.asarray(m['breakpoints'], float)
        f = np.asarray(m['flux'], float)
        rows.append({'max_kW_m2': float(f.max()), 'integral_kJ_m2_cells': float((f * np.diff(bp)[:, None]).sum())})
    return rows


def richard(richard_dir, re_dir, nr_dir, hz):
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(richard_dir))
    from deadline_field.real import load_packet
    from tools.explain_deadlines.geometry import Grid
    g = hz['grid']
    grid = Grid(g['x0'], g['y0'], g['resolution'], g['width'], g['height'])
    pre, _ = load_packet(re_dir, grid)
    pnr, _ = load_packet(nr_dir, grid)
    H = pre.horizon
    res = {'members': pre.S, 'cell_set_diff': 0, 'birth_diff': 0, 'nr_end_before_H': 0}
    for s in range(pre.S):
        a, b = pre.phases[s], pnr.phases[s]
        res['cell_set_diff'] += len(set(a) ^ set(b))
        for c in set(a) & set(b):
            res['birth_diff'] += int(a[c][0] != b[c][0])
            res['nr_end_before_H'] += int(b[c][1] < H)
    res['ok'] = res['cell_set_diff'] == 0 and res['birth_diff'] == 0 and res['nr_end_before_H'] == 0
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--richard-dir', type=Path, default=None)
    ap.add_argument('--only', nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    man = json.loads(MAN.read_text())
    want = {tuple(s.split(':')) for s in a.only}
    rows = []
    for key in sorted(want):
        pick = [e for e in man['entries'] if (e['region'], e['start'], str(e['horizon_h']), e['variant']) == key]
        re_e = next(e for e in pick if e['transform'] == 'reopening')
        nr_e = next(e for e in pick if e['transform'] == 'no_reentry/1')
        row = {'entry': ':'.join(key)}
        for tag, e in (('reopening', re_e), ('no_reentry', nr_e)):
            rc, log = build(e)
            row[f'{tag}_build_rc'] = rc
            if rc:
                row[f'{tag}_log'] = log
        if row['reopening_build_rc'] or row['no_reentry_build_rc']:
            row['ok'] = False
            rows.append(row); print(json.dumps(row)[:800]); continue
        dre, dnr = REPO / re_e['out'], REPO / nr_e['out']
        hz_re = json.loads((dre / 'HAZARD.json').read_text()); hz_nr = json.loads((dnr / 'HAZARD.json').read_text())
        H = float(hz_nr['valid_until'])
        if key == ('yeongdeok_2025', '20250325T110000Z', '5', 'kriged_mean'):
            exp = V35_KRIGED_YD25T11_H5.get('.'.join(np.__version__.split('.')[:2]))
            row['1_reopening_hazard_sha256'] = sha(dre / 'HAZARD.json')
            row['1_equals_v35'] = None if exp is None else row['1_reopening_hazard_sha256'] == exp
        summ = json.loads((dnr / 'BUILD_SUMMARY.json').read_text())
        st = json.loads((dnr / 'NATIVE_METADATA.json').read_text())['settings']
        row['2_self_check_consistent'] = summ['fdyn']['packet_self_check']['consistent']
        row['2_identity'] = {'source_law_version': st.get('source_law_version'),
                             'transform': st['fdyn'].get('transform'), 'no_reentry_flux': st['fdyn'].get('no_reentry_flux'),
                             'packet_writer_sha256': hz_nr['provenance']['identity']['packet_writer_sha256'],
                             'scenario_ids_differ_from_reopening': [m['id'] for m in hz_nr['members']] != [m['id'] for m in hz_re['members']]}
        row['3_own_derivation_mismatches'] = own_derivation(hz_re, hz_nr, H)
        row['4_flux'] = {'reopening': flux_stats(hz_re), 'no_reentry': flux_stats(hz_nr)}
        chk = consistency.check(dnr)
        row['5_array_path_consistent'] = chk['consistent']
        if a.richard_dir:
            row['6_richard_never'] = richard(a.richard_dir, dre, dnr, hz_re)
        row['ok'] = (row['2_self_check_consistent'] and row['3_own_derivation_mismatches'] == 0 and
                     row['5_array_path_consistent'] and row['2_identity']['transform'] == 'no_reentry/1' and
                     row['2_identity']['scenario_ids_differ_from_reopening'] and
                     row.get('1_equals_v35', True) in (True, None) and
                     (not a.richard_dir or row['6_richard_never']['ok']))
        rows.append(row)
        print(json.dumps({k: row[k] for k in ('entry', 'ok', '3_own_derivation_mismatches', '5_array_path_consistent')}
                         | {'richard': row.get('6_richard_never')}))
    a.out.write_text(json.dumps({'rule': 'NOREENTRY_RULE.md', 'manifest_sha256': sha(MAN), 'numpy': np.__version__,
                                 'rows': rows, 'all_ok': bool(rows) and all(r['ok'] for r in rows)}, indent=1))
    print('all_ok', bool(rows) and all(r['ok'] for r in rows))


if __name__ == '__main__':
    main()
