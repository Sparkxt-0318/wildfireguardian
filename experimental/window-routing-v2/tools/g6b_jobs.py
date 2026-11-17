"""G6b job list (G6B_RUN.md "Jobs"): all route-check jobs of the six planner caches, deterministic.
  python -B g6b_jobs.py OUT.json
Strata as in g6_select.py: TIMEOUT = raw_status UNRESOLVED; AT_ISSUE = raw_status AT_ISSUE_FAILURE; ROUTE = checked_route;
NOROUTE = model_no_route. Caches in G6B_RUN.md's order, jobs sorted by job_id.
"""
import hashlib, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ORDER = ['uiseong_andong_2025/20250323T010000Z.json', 'uiseong_andong_2025/20250324T090000Z.json',
         'uiseong_andong_2025/20250325T170000Z.json', 'yeongdeok_2025/20250325T190000Z.json',
         'yeongdeok_2025/20250325T230000Z.json', 'yeongdeok_2025/20250326T080000Z.json']


def stratum(res):
    if res.get('raw_status') == 'UNRESOLVED':
        return 'TIMEOUT'
    if res.get('raw_status') == 'AT_ISSUE_FAILURE':
        return 'AT_ISSUE'
    return {'checked_route': 'ROUTE', 'model_no_route': 'NOROUTE'}.get(res.get('verdict'), 'OTHER')


def main():
    out = {'caches': ORDER, 'cache_sha256': {}, 'jobs': []}
    idx = {e['path'] for e in json.loads((REPO / 'planner/cache/INDEX.json').read_text())}
    assert set(ORDER) == idx, (set(ORDER) ^ idx)
    for c in ORDER:
        p = REPO / 'planner/cache' / c
        out['cache_sha256'][c] = hashlib.sha256(p.read_bytes()).hexdigest()
        rc = json.loads(p.read_text())['route_checks']
        out['jobs'] += [{'cache': c, 'job_id': j, 'stratum': stratum(rc[j].get('result') or {})} for j in sorted(rc)]
    assert len(out['jobs']) == 9722, len(out['jobs'])
    assert not [j for j in out['jobs'] if j['stratum'] == 'OTHER']
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1) + '\n')
    from collections import Counter
    print(len(out['jobs']), Counter(j['stratum'] for j in out['jobs']))


if __name__ == '__main__':
    main()
