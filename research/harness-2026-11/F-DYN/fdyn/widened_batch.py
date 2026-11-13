"""WIDENED_GRAPH_RULE.md: build the packet pairs (v3.7 `/2` twin + padded widened packet) and run P2/P3 on each.

Combos: every (region, start, horizon, variant) of the candidate list (NR2_ROAD_LIMITED_CANDIDATES.json @ 50535521)
x the four timing variants (§4), plus the control set (§8(iii)3: UA 25T17Z and YD 25T19Z, h5, kriged_mean).
The v3.7 twin is rebuilt from its MANIFEST_v3_7 command with only --out changed; the padded packet is the same command
with --graph (widened), --pad-cells 14, --padded-export-dir and the padding support mask (supplied/1).
Each build is its own process (row 79 note 1). Skips a pair whose BUILD_SUMMARY.json exists.

    python3 fdyn/widened_batch.py --manifest MANIFEST_v3_7.json --candidates CAND.json --widened KFS.json \
        --work DIR --jobs 3 --out PAIRS.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VARIANTS = ('kriged_mean', 'firms_early', 'envelope', 'envelope_burnset')
CONTROL = (('uiseong_andong_2025', '20250325T170000Z', 5, 'kriged_mean'), ('yeongdeok_2025', '20250325T190000Z', 5, 'kriged_mean'))
PROV = {'rule': 'WIDENED_GRAPH_RULE.md §2', 'reason': 'export-grid padding, no fire data', 'padding_cells': 9632}


def arg_set(cmd, k, v):
    cmd = list(cmd)
    if k in cmd:
        cmd[cmd.index(k) + 1] = v
    else:
        cmd += [k, v]
    return cmd


def run(cmd, log):
    if cmd[0] == 'python3':
        cmd = [sys.executable] + cmd[1:]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    log.write_text((r.stdout + r.stderr)[-6000:])
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    for k in ('--manifest', '--candidates', '--widened', '--work', '--out'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--only-region', default=None)
    a = ap.parse_args()
    man = json.loads(a.manifest.read_text())
    cand = json.loads(a.candidates.read_text())['rows']
    combos = sorted({(r['region'], r['start'], int(r['horizon_h']), v) for r in cand for v in VARIANTS} | set(CONTROL))
    if a.only_region:
        combos = [c for c in combos if c[0] == a.only_region]
    a.work.mkdir(parents=True, exist_ok=True)
    mask = a.work / 'padding_support.npz'
    if not mask.exists():
        m = np.ones((107, 265), bool)
        m[:14, :] = m[-14:, :] = False
        m[:, :14] = m[:, -14:] = False
        np.savez(mask, support=m)
    entries = {(e['region'], e['start'], int(e['horizon_h']), e['variant']): e for e in man['entries']
               if e['transform'] == 'no_reentry/2'}

    def job(c):
        e = entries[c]
        tag = f'{c[0]}/{c[1]}_h{c[2]}_{c[3]}'
        old, new = a.work / 'v37' / tag, a.work / 'padded' / tag
        row = {'combo': list(c), 'v37_cmd_out': e['out'], 'old': str(old), 'new': str(new)}
        old.parent.mkdir(parents=True, exist_ok=True)
        new.parent.mkdir(parents=True, exist_ok=True)
        if not (old / 'BUILD_SUMMARY.json').exists():
            row['old_rc'] = run(arg_set(e['cmd'], '--out', str(old)), old.with_name(old.name + '.log'))
        cmd = arg_set(e['cmd'], '--out', str(new))
        cmd = arg_set(cmd, '--graph', str(a.widened))
        cmd += ['--pad-cells', '14', '--padded-export-dir', str(new.with_name(new.name + '.export')),
                '--support-mask', str(mask), '--support-rule', 'supplied/1', '--support-provenance', json.dumps(PROV)]
        if not (new / 'BUILD_SUMMARY.json').exists():
            row['new_rc'] = run(cmd, new.with_name(new.name + '.log'))
        if (old / 'BUILD_SUMMARY.json').exists() and (new / 'BUILD_SUMMARY.json').exists():
            r = subprocess.run([sys.executable, str(HERE / 'widened_packet_check.py'), '--old', str(old), '--new', str(new)],
                               capture_output=True, text=True)
            chk = json.loads(r.stdout) if r.returncode == 0 else {'error': r.stderr[-2000:]}
            row.update({k: chk.get(k) for k in ('P2', 'P3', 'flux_max_abs_diff', 'flux_max_rel_diff', 'error')})
        print(json.dumps(row), flush=True)
        return row

    with ThreadPoolExecutor(a.jobs) as ex:          # threads only dispatch subprocesses
        rows = list(ex.map(job, combos))
    a.out.write_text(json.dumps({'rule': 'WIDENED_GRAPH_RULE.md', 'combos': len(combos), 'rows': rows,
                                 'all_P2': all(r.get('P2') for r in rows), 'all_P3': all(r.get('P3') for r in rows)}, indent=1))
    print('all_P2', all(r.get('P2') for r in rows), 'all_P3', all(r.get('P3') for r in rows))


if __name__ == '__main__':
    main()
