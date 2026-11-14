"""WIDENED_GRAPH_RULE.md: run fdyn/widened_run.py over the built packet pairs, one process per run, N at a time.

Places per (region, start, horizon): the candidate places of NR2_ROAD_LIMITED_CANDIDATES.json (union over variants, §4)
minus places not located on the 2025-01-01 graph (§7; WIDENED_INPUTS.json); the control set (§8(iii)3) uses every
located INSTANCE place and runs only waiting arm (a) (arms g1, g1p, a_closed, a_open).
A run whose output exists is skipped. Pairs that failed P2 or P3 are not run (the rule stops there).

    python3 fdyn/widened_runs.py --pairs PAIRS.json --candidates CAND.json --inputs results/WIDENED_INPUTS.json \
        --graphs GDIR --widened KFS.json --f31 F31 --work DIR --jobs 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTROL = {('uiseong_andong_2025', '20250325T170000Z', 5, 'kriged_mean'), ('yeongdeok_2025', '20250325T190000Z', 5, 'kriged_mean')}


def main():
    ap = argparse.ArgumentParser()
    for k in ('--pairs', '--candidates', '--inputs', '--graphs', '--widened', '--f31', '--work'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    pairs = json.loads(a.pairs.read_text())['rows']
    cand = json.loads(a.candidates.read_text())['rows']
    inputs = json.loads(a.inputs.read_text())['windows']
    unlocated = {p for w in inputs.values() for p in w['membership']['places_not_located']}
    places = {}
    for r in cand:
        places.setdefault((r['region'], r['start'], int(r['horizon_h'])), set()).add(r['origin'])
    jobs = []
    for p in pairs:
        c = tuple(p['combo'])
        if not (p.get('P2') and p.get('P3')):
            print('SKIP (P2/P3 not passed)', c, flush=True)
            continue
        key = c[:3]
        if key in places:
            pl = sorted(places[key] - unlocated)
            jobs.append((c, 'candidates', ','.join(pl), 'g1,g1p,a_closed,a_open,b_closed,b_open', p))
        if c in CONTROL:
            jobs.append((c, 'control', 'ALL', 'g1,g1p,a_closed,a_open', p))

    def run(j):
        c, kind, pl, arms, p = j
        out = a.work / kind / f'{c[0]}/{c[1]}_h{c[2]}_{c[3]}.json'
        if out.exists():
            return {'combo': list(c), 'kind': kind, 'skipped': 'exists'}
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(HERE / 'widened_run.py'), '--f31', str(a.f31), '--region', c[0], '--start', c[1],
               '--horizon-h', str(c[2]), '--old-packet', p['old'], '--new-packet', p['new'],
               '--g1', str(a.graphs / c[0] / 'G1.json'), '--g1p', str(a.graphs / c[0] / 'G1p.json'),
               '--widened', str(a.widened), '--arm-a', str(HERE.parent / 'results' / 'WIDENED_ARM_A_WAITABLE.json'),
               '--instance', str(HERE.parent / '_data' / 'INSTANCE.json'), '--places', pl, '--arms', arms, '--out', str(out)]
        r = subprocess.run(['/usr/bin/time', '-f', 'maxrss_kb %M wall %e'] + cmd, capture_output=True, text=True)
        out.with_suffix('.log').write_text((r.stdout + r.stderr)[-8000:])
        row = {'combo': list(c), 'kind': kind, 'rc': r.returncode, 'tail': r.stderr.strip().splitlines()[-1:] }
        print(json.dumps(row), flush=True)
        return row

    with ThreadPoolExecutor(a.jobs) as ex:
        rows = list(ex.map(run, jobs))
    print('done', len(rows), 'failed', sum(1 for r in rows if r.get('rc')))


if __name__ == '__main__':
    main()
