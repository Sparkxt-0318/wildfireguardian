"""G6a sample selection (PLAN G6; G6_RULE.md), deterministic from a fixed seed, written before any G6 run.
Strata from the planner caches (planner/cache/INDEX.json, 6 files, 9,722 route-check jobs):
  TIMEOUT  all jobs with raw_status UNRESOLVED (291 originals + 6 rechecks = 297)
  AT_ISSUE all jobs with raw_status AT_ISSUE_FAILURE (186)
  ROUTE    seeded draw of N_ROUTE_PER_CACHE checked_route jobs per cache
  NOROUTE  seeded draw of N_NOROUTE_PER_CACHE model_no_route jobs per cache
  python g6_select.py --seed 20261112 --routes-per-cache 25 --noroutes-per-cache 12 --out G6A_SAMPLE.json
"""
import argparse, hashlib, json, random
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True); ap.add_argument('--routes-per-cache', type=int, required=True)
    ap.add_argument('--noroutes-per-cache', type=int, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    idx = json.loads((REPO / 'planner/cache/INDEX.json').read_text())
    rng = random.Random(a.seed); out = {'seed': a.seed, 'routes_per_cache': a.routes_per_cache,
                                        'noroutes_per_cache': a.noroutes_per_cache, 'caches': {}, 'jobs': []}
    for e in sorted(idx, key=lambda e: e['path']):
        p = REPO / 'planner/cache' / e['path']; c = json.loads(p.read_text())
        out['caches'][e['path']] = hashlib.sha256(p.read_bytes()).hexdigest()
        rc = c['route_checks']; ids = sorted(rc)
        st = lambda j: (rc[j].get('result') or {})
        tim = [j for j in ids if st(j).get('raw_status') == 'UNRESOLVED']
        ati = [j for j in ids if st(j).get('raw_status') == 'AT_ISSUE_FAILURE']
        rou = [j for j in ids if st(j).get('verdict') == 'checked_route']
        nor = [j for j in ids if st(j).get('verdict') == 'model_no_route']
        pick = lambda xs, n: sorted(rng.sample(xs, min(n, len(xs))))
        for stratum, js in (('TIMEOUT', tim), ('AT_ISSUE', ati), ('ROUTE', pick(rou, a.routes_per_cache)), ('NOROUTE', pick(nor, a.noroutes_per_cache))):
            out['jobs'] += [{'cache': e['path'], 'job_id': j, 'stratum': stratum} for j in js]
    a.out.write_text(json.dumps(out, indent=1) + '\n')
    from collections import Counter
    print(Counter(j['stratum'] for j in out['jobs']), len(out['jobs']))


if __name__ == '__main__':
    main()
