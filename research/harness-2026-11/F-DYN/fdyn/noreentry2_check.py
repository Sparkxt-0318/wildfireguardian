"""NOREENTRY2_RULE.md acceptance 1-5 (and the B0 counts) on chosen MANIFEST_v3_7 (region, start, H, variant) samples.

Per sample: build (if absent) the reopening, no_reentry/1 and no_reentry/2 packets from their manifest commands, then
  1  reopening kriged_mean HAZARD sha256 vs the per-numpy v3.5 table; where a stored v3.6 no_reentry/1 packet exists,
     a fresh /1 rebuild (current code) is byte-identical to it (HAZARD, REPORT, NATIVE_METADATA; npz array for array)
  2  builder self-check of /2, transform identity, F1 label, scenario ids differ from /1 and reopening
  3  own derivation: B0 recomputed here from the export npz and the variant raster (NOT from the plan meta):
       C0 = export known-burned | arrival (envelope: lo) <= start (integer ms since t0, inclusive)
       B0 = C0 minus the cells active in the /1 packet's first bin
     then for every member and HAZARD bin: /2 flame == /1 flame | B0; the B0 count == plan meta b0_total;
     reported: |C0 minus (burn set | present fire)| and whether the /2 burnset content equals /1
  4  flux, reported: max and integral per member, /2 vs /1 vs reopening
  5  array path: /2 packets are scalar-law consistent (fdyn/consistency.py)

    python3 research/harness-2026-11/F-DYN/fdyn/noreentry2_check.py --manifest MANIFEST_v3_7.json \
        --only REGION:START:H:VARIANT [...] --work DIR --out NOREENTRY2_CHECK.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
T0 = dt.datetime(2025, 3, 22, 2, 24, tzinfo=dt.timezone.utc)
V35_KRIGED_YD25T11_H5 = {'2.5': '6940f2939318126437b6109853033ab0b1534dd288f3775c6c0352ed44646f2f',
                         '1.26': '5716c09e70b285ce10db54bc87ec37c89987d124ae7010438a02870dfe5d4326'}
FILES = ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json')
sys.path.insert(0, str(HERE.parent))
from fdyn import consistency  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, out=None):
    cmd = list(cmd)
    if cmd[0] == 'python3':
        cmd[0] = sys.executable
    if out is not None:
        cmd[cmd.index('--out') + 1] = str(out)
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def build(e):
    if (REPO / e['out'] / 'BUILD_SUMMARY.json').exists():
        return 0, 'present'
    return run(e['cmd'])


def arg(cmd, k):
    return cmd[cmd.index(k) + 1] if k in cmd else None


def raster_h(path):
    p = REPO / path
    if p.suffix == '.npz':
        with np.load(p, allow_pickle=False) as z:
            assert dt.datetime.fromisoformat(str(z['t0_utc'])) == T0
            return z['arrival_h'].astype(float)
    import rasterio
    with rasterio.open(p) as s:
        return s.read(1).astype(float)


def independent_c0(e):
    """C0 on the north-up export grid, from the files named in the entry's cmd (NOREENTRY2_RULE.md 6.1)."""
    cmd = e['cmd']
    start = dt.datetime.strptime(e['start'], '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    syn = arg(cmd, '--synthetic-export-dir')
    exp = (REPO / syn) if syn else REPO / 'data/routing/latest_inputs_try02/exports/KFS_01'
    with np.load(exp / f'FORECAST_{e["start"]}.npz') as z:
        burned = z['source_burned_area_valid'].astype(bool) & (z['source_burned_area'] == 1)
        iv = z['heat__initial_burning_valid'].astype(bool)
        present = (iv & (z['heat__initial_active_burning_probability'] == 1) & burned) | (burned & ~iv)
    a = raster_h(arg(cmd, '--arrival'))                     # envelope: --arrival is lo
    h_ms = int((start - T0).total_seconds()) * 1000
    fin = np.isfinite(a)
    a_ms = np.zeros(a.shape, np.int64)
    a_ms[fin] = np.rint(a[fin] * 3_600_000).astype(np.int64)
    c0 = burned | (fin & (a_ms <= h_ms))
    return c0, burned, present, exp


def flat(grid):
    return np.flipud(np.asarray(grid, bool)).ravel()          # HAZARD layout: south-up row-major


def flux_stats(hz):
    rows = []
    for m in hz['members']:
        bp = np.asarray(m['breakpoints'], float)
        f = np.asarray(m['flux'], float)
        rows.append({'max_kW_m2': float(f.max()), 'integral_kJ_m2_cells': float((f * np.diff(bp)[:, None]).sum())})
    return rows


def npz_equal(a, b):
    with np.load(a) as x, np.load(b) as y:
        return sorted(x.files) == sorted(y.files) and all(np.array_equal(x[k], y[k]) for k in x.files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--only', nargs='+', required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    man = json.loads(a.manifest.read_text())
    rows = []
    for key in [tuple(s.split(':')) for s in a.only]:
        pick = {e['transform']: e for e in man['entries']
                if (e['region'], e['start'], str(e['horizon_h']), e['variant']) == key}
        row = {'entry': ':'.join(key)}
        for t in ('reopening', 'no_reentry/1', 'no_reentry/2'):
            rc, log = build(pick[t])
            row[f'build_rc[{t}]'] = rc
            if rc:
                row[f'log[{t}]'] = log
        if any(row[f'build_rc[{t}]'] for t in pick):
            row['ok'] = False
            rows.append(row); print(json.dumps(row)[:1200]); continue
        d = {t: REPO / pick[t]['out'] for t in pick}
        hz = {t: json.loads((d[t] / 'HAZARD.json').read_text()) for t in pick}
        # 1
        if key == ('yeongdeok_2025', '20250325T110000Z', '5', 'kriged_mean'):
            exp = V35_KRIGED_YD25T11_H5.get('.'.join(np.__version__.split('.')[:2]))
            row['1_reopening_equals_v35'] = None if exp is None else sha(d['reopening'] / 'HAZARD.json') == exp
        fresh = a.work / ('nr1_' + '_'.join(key))
        if not fresh.exists():
            rc, log = run(pick['no_reentry/1']['cmd'], fresh)
            row['1_nr1_rebuild_rc'] = rc
        row['1_nr1_rebuild_byte_identical'] = (all(sha(fresh / f) == sha(d['no_reentry/1'] / f) for f in FILES) and
                                               npz_equal(fresh / 'constructed_arrays.npz',
                                                         d['no_reentry/1'] / 'constructed_arrays.npz'))
        # 2
        summ = json.loads((d['no_reentry/2'] / 'BUILD_SUMMARY.json').read_text())
        st = json.loads((d['no_reentry/2'] / 'NATIVE_METADATA.json').read_text())['settings']
        ids = {t: [m['id'] for m in hz[t]['members']] for t in hz}
        row['2_self_check_consistent'] = summ['fdyn']['packet_self_check']['consistent']
        row['2_identity'] = {'transform': st['fdyn'].get('transform'), 'source_law_version': st.get('source_law_version'),
                             'no_reentry_flux': st['fdyn'].get('no_reentry_flux'),
                             'writer_identity_transform': summ['writer_identity']['transform'],
                             'ids_differ': ids['no_reentry/2'] != ids['no_reentry/1'] and ids['no_reentry/2'] != ids['reopening']}
        # 3
        c0, burned, present, exp = independent_c0(pick['no_reentry/2'])
        c0f = flat(c0)
        bad, b0_counts = 0, []
        for m1, m2 in zip(hz['no_reentry/1']['members'], hz['no_reentry/2']['members']):
            if m1['breakpoints'] != m2['breakpoints']:
                bad += 1
                continue
            f1 = np.asarray(m1['flame'], bool)
            f2 = np.asarray(m2['flame'], bool)
            b0 = c0f & ~f1[0]
            b0_counts.append(int(b0.sum()))
            bad += int((f2 != (f1 | b0[None])).sum())
        meta_counts = [x['b0_total'] for x in st['fdyn']['no_reentry2']['added_at_0']]
        row['3_own_derivation_mismatches'] = bad
        row['3_b0_independent'] = b0_counts
        row['3_b0_plan_meta'] = meta_counts
        row['3_b0_counts_equal'] = b0_counts == meta_counts
        row['3_export'] = str(exp.relative_to(REPO))
        row['3_c0_cells'] = int(c0.sum())
        with np.load(REPO / 'research/harness-2026-11/F-DYN/_data/variants/envelope_burnset_lo.npz') as z:
            burnset = np.isfinite(z['arrival_h'])
        row['3_c0_outside_burnset_or_present'] = int((c0 & ~(burnset | present)).sum())
        if key[3] == 'envelope_burnset':
            row['3_burnset_nr2_flame_equals_nr1'] = all(
                np.array_equal(np.asarray(x['flame'], bool), np.asarray(y['flame'], bool))
                for x, y in zip(hz['no_reentry/1']['members'], hz['no_reentry/2']['members']))
        # 4
        row['4_flux'] = {t: flux_stats(hz[t]) for t in hz}
        # 5
        row['5_array_path_consistent'] = consistency.check(d['no_reentry/2'])['consistent']
        row['ok'] = (row.get('1_reopening_equals_v35', True) in (True, None) and row['1_nr1_rebuild_byte_identical'] and
                     row['2_self_check_consistent'] and row['2_identity']['transform'] == 'no_reentry/2' and
                     row['2_identity']['writer_identity_transform'] == 'no_reentry/2' and row['2_identity']['ids_differ'] and
                     bad == 0 and row['3_b0_counts_equal'] and row['5_array_path_consistent'])
        rows.append(row)
        print(json.dumps({k: row[k] for k in row if not k.startswith('4_')})[:1500])
    a.out.write_text(json.dumps({'rule': 'NOREENTRY2_RULE.md', 'manifest_sha256': sha(a.manifest), 'numpy': np.__version__,
                                 'rows': rows, 'all_ok': bool(rows) and all(r['ok'] for r in rows)}, indent=1))
    print('all_ok', bool(rows) and all(r['ok'] for r in rows))


if __name__ == '__main__':
    main()
