"""Acceptance run for DESIGN.md §Regression: every recorded c651 packet whose export is present here.

Per packet (all builds in this process's environment, each in its own python -I -B process):
  A  frozen build_packet.py            A2  frozen build_packet.py again (shows the writer's own npz zip-time stamp)
  B  build_packet_f93.py, no mask      C   build_packet_f93.py --support-rule c651_unknown/1
Checks: B == A (HAZARD/REPORT/NATIVE_METADATA bytes; npz array for array; BUILD_SUMMARY except wall time);
A vs the frozen stored packet (ids, breakpoints, flame, support exact; flux relative 1e-9);
C: writer identity differs, support == rule, flame/flux/ids/breakpoints == A, router validator ran inside the build,
array-law check passes.

    python3 research/harness-2026-11/F-9.3/support_mask/regress.py --work DIR --out REGRESSION.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WFG = REPO / 'integration' / 'src' / 'wfg_latest'
INPUTS = REPO / 'data' / 'routing' / 'latest_inputs_try02'
sys.path.insert(0, str(HERE))
import packets_f93 as PF  # noqa: E402  (array_law_check, c651_unknown only; no writer import)

FILES = ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def iso(tag):
    return f'{tag[0:4]}-{tag[4:6]}-{tag[6:8]}T{tag[9:11]}:00:00Z'


def recorded():
    for d in sorted((INPUTS / 'packets').glob('*/*')):
        md = json.loads((d / 'NATIVE_METADATA.json').read_text())
        event = md['construction']['parent_forecast']['event_id']
        tag = d.name
        exp = INPUTS / 'exports' / event
        yield d, d.parent.name, tag, event, exp, md.get('regional', {}).get('window_rows_cols_north_up')


def args_for(region, tag, event, exp, win, out):
    a = ['--graph', str(REPO / 'data' / 'routing' / 'graphs' / region / 'graph.json'), '--export-dir', str(exp),
         '--event', event, '--cutoff', iso(tag), '--region', region, '--out', str(out)]
    return a + (['--window-json', json.dumps(win)] if win is not None else [])


def run(script, argv):
    r = subprocess.run([sys.executable, '-I', '-B', str(script), *argv], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def npz(p):
    with np.load(p, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def npz_equal(a, b):
    A, B = npz(a), npz(b)
    if list(A) != list(B):
        return False, 'names'
    for k in A:
        if A[k].dtype != B[k].dtype or A[k].shape != B[k].shape or A[k].tobytes() != B[k].tobytes():
            return False, k
    return True, None


def summary_equal(a, b):
    A = json.loads(Path(a).read_text()); B = json.loads(Path(b).read_text())
    for d in (A, B):
        d.pop('hazard_construction_wall_s', None)
        d.pop('out_dir', None)
        d['files_sha256'].pop('constructed_arrays.npz', None)   # zip member time stamp, see npz comparison
    return A == B


def vs_frozen(built, frozen):
    h1 = json.loads((built / 'HAZARD.json').read_text()); h0 = json.loads((frozen / 'HAZARD.json').read_text())
    if [m['id'] for m in h1['members']] != [m['id'] for m in h0['members']]:
        return {'ok': False, 'why': 'ids'}
    worst = 0.0
    for m1, m0 in zip(h1['members'], h0['members']):
        for k in ('breakpoints', 'flame', 'support'):
            if m1[k] != m0[k]:
                return {'ok': False, 'why': k}
        f1, f0 = np.asarray(m1['flux']), np.asarray(m0['flux'])
        if f1.shape != f0.shape:
            return {'ok': False, 'why': 'flux shape'}
        rel = np.abs(f1 - f0) / np.maximum(np.abs(f0), 1e-300)
        rel[(f1 == f0)] = 0.0
        worst = max(worst, float(rel.max()) if rel.size else 0.0)
    return {'ok': worst <= 1e-9, 'flux_max_relative_diff': worst, 'hazard_bytes_identical': sha(built / 'HAZARD.json') == sha(frozen / 'HAZARD.json')}


def masked_checks(A, C):
    hA = json.loads((A / 'HAZARD.json').read_text()); hC = json.loads((C / 'HAZARD.json').read_text())
    idA, idC = hA['provenance']['identity'], hC['provenance']['identity']
    arrA = npz(A / 'constructed_arrays.npz'); arrC = npz(C / 'constructed_arrays.npz')
    mask = PF.c651_unknown(arrA)
    flat = np.flipud(mask).ravel()
    same = all(mA[k] == mC[k] for mA, mC in zip(hA['members'], hC['members']) for k in ('id', 'breakpoints', 'flame', 'flux'))
    sup = all((np.asarray(m['support'], bool) == flat).all() for m in hC['members'])
    others = all(arrA[k].tobytes() == arrC[k].tobytes() for k in arrA if k != 'support')
    rep = {f: json.loads((C / f).read_text()) for f in ('REPORT.json', 'NATIVE_METADATA.json')}
    law = PF.array_law_check(C)
    out = {'unsupported_cells': int((~mask).sum()), 'cells': int(mask.size),
           'u_state': int(np.asarray(arrA['mask__unknown_cumulative_state'], bool).sum()),
           'writer_identity_differs': idC['packet_writer_sha256'] != idA['packet_writer_sha256'],
           'base_writer_recorded': idC.get('base_packet_writer_sha256') == idA['packet_writer_sha256'],
           'ids_breakpoints_flame_flux_equal_A': same, 'support_equals_rule': sup, 'npz_support': bool((arrC['support'] == mask[None]).all()),
           'other_arrays_equal_A': others, 'array_law_consistent': law['consistent']}
    out['identity_stamped_in_report_and_metadata'] = (
        rep['REPORT.json']['native_metadata']['identity']['packet_writer_sha256'] == idC['packet_writer_sha256']
        and rep['NATIVE_METADATA.json']['identity']['packet_writer_sha256'] == idC['packet_writer_sha256'])
    out['ok'] = all(v for k, v in out.items() if isinstance(v, bool))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--only', default=None, help='region/tag')
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=False)
    import scipy
    rows, not_rebuilt = [], []
    for d, region, tag, event, exp, win in recorded():
        if a.only and f'{region}/{tag}' != a.only:
            continue
        if not (exp / f'FORECAST_{tag}.npz').exists():
            not_rebuilt.append({'packet': f'{region}/{tag}', 'why': f'export {event}/FORECAST_{tag}.npz not present here'})
            continue
        w = a.work / region / tag
        w.mkdir(parents=True)
        res = {'packet': f'{region}/{tag}'}
        for key, script, extra in (('A', WFG / 'build_packet.py', []), ('A2', WFG / 'build_packet.py', []),
                                   ('B', HERE / 'build_packet_f93.py', []),
                                   ('C', HERE / 'build_packet_f93.py', ['--support-rule', 'c651_unknown/1'])):
            rc, log = run(script, args_for(region, tag, event, exp, win, w / key) + extra)
            res[f'{key}_rc'] = rc
            if rc:
                res[f'{key}_log'] = log
        if any(res[f'{k}_rc'] for k in ('A', 'A2', 'B', 'C')):
            res['ok'] = False
            rows.append(res); print(json.dumps(res)[:400]); continue
        A, A2, B, C = (w / k for k in ('A', 'A2', 'B', 'C'))
        res['B_eq_A_bytes'] = {f: sha(A / f) == sha(B / f) for f in FILES}
        res['B_eq_A_npz_arrays'] = npz_equal(A / 'constructed_arrays.npz', B / 'constructed_arrays.npz')[0]
        res['B_eq_A_npz_bytes'] = sha(A / 'constructed_arrays.npz') == sha(B / 'constructed_arrays.npz')
        res['A2_eq_A_npz_bytes'] = sha(A / 'constructed_arrays.npz') == sha(A2 / 'constructed_arrays.npz')
        res['A2_eq_A_npz_arrays'] = npz_equal(A / 'constructed_arrays.npz', A2 / 'constructed_arrays.npz')[0]
        res['B_eq_A_build_summary_except_wall_out_npz_hash'] = summary_equal(A / 'BUILD_SUMMARY.json', B / 'BUILD_SUMMARY.json')
        res['B_packet_writer_is_frozen'] = (json.loads((B / 'HAZARD.json').read_text())['provenance']['identity']
                                            ['packet_writer_sha256'] == sha(WFG / 'packets.py'))
        res['A_vs_frozen_stored'] = vs_frozen(A, d)
        res['C'] = masked_checks(A, C)
        res['ok'] = (all(res['B_eq_A_bytes'].values()) and res['B_eq_A_npz_arrays'] and res['B_packet_writer_is_frozen']
                     and res['B_eq_A_build_summary_except_wall_out_npz_hash'] and res['A_vs_frozen_stored']['ok'] and res['C']['ok'])
        rows.append(res)
        print(json.dumps({k: res[k] for k in ('packet', 'ok')} | {'unsupported': res['C']['unsupported_cells'],
                                                                   'npz_bytes_A2=A': res['A2_eq_A_npz_bytes']}))
    out = {'schema': 'wfg.f93.support-writer.regression/1', 'design': 'research/harness-2026-11/F-9.3/support_mask/DESIGN.md',
           'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
           'platform': platform.platform(),
           'source_sha256': {'packets.py': sha(WFG / 'packets.py'), 'bridge.py': sha(WFG / 'bridge.py'),
                             'build_packet.py': sha(WFG / 'build_packet.py'), 'packets_f93.py': sha(HERE / 'packets_f93.py'),
                             'build_packet_f93.py': sha(HERE / 'build_packet_f93.py')},
           'recorded_packets': len(rows) + len(not_rebuilt), 'rebuilt': len(rows), 'not_rebuilt': not_rebuilt,
           'all_ok': all(r['ok'] for r in rows), 'rows': rows}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('recorded_packets', 'rebuilt', 'all_ok')} | {'not_rebuilt': len(not_rebuilt)}))


if __name__ == '__main__':
    main()
