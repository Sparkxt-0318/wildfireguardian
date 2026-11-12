"""PLAN.md G2: every route a v2 run published is re-checked, each in a FRESH interpreter, by
(1) the frozen kit's unchanged whole-road checker (HybridChecker from FROZEN_KIT's queue; status must be CERTIFIED_ADMISSIBLE),
(2) the routing package's independent checker from FROZEN_KIT (validate_graph/hazard/request, then core.check_route; ok and no codes).
Checker code hashes and input hashes are recorded. Run folders are those listed by g1_compare.py (or any v2 run folders).
  python -B g2_recheck.py --frozen FROZEN_KIT --out OUT.jsonl RUN_FOLDER [RUN_FOLDER ...]
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
CHILD = r'''
import json, sys, time
from pathlib import Path
kit, graph_p, packet, req_p, route_p, which = sys.argv[1:7]
kit = Path(kit); q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
graph = json.loads(Path(graph_p).read_text()); req = json.loads(Path(req_p).read_text()); route = json.loads(Path(route_p).read_text())
t0 = time.perf_counter()
if which == 'whole_road':
    sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
    import importlib
    HC = importlib.import_module(q['checker_module']).HybridChecker
    from mission_contract import graph_digest
    rec = HC(Path(packet)).check(graph, req, route['legs'], route['destination'], wall_s=600, deadline=time.perf_counter() + 600,
                                 expected_graph_revision=graph['revision'], expected_graph_sha256=graph_digest(graph))
    out = {'status': rec.get('status'), 'reason': rec.get('reason'), 'lifetime_rss_mb': rec.get('process_lifetime_rss_mb')}
    out['pass'] = out['status'] == 'CERTIFIED_ADMISSIBLE'
else:
    sys.path.insert(0, str(src / 'baseline/routing-package'))
    from routing import validation as V, core
    hazard = json.loads((Path(packet) / 'HAZARD.json').read_text())
    g = V.validate_graph(graph) or graph; h = V.validate_hazard(g, hazard, req.get('as_of')) or hazard; r = V.validate_request(g, h, req) or req
    res = core.check_route(g, h, r, route['legs'], route['destination'])
    out = {'ok': res.get('ok'), 'codes': res.get('codes')}; out['pass'] = bool(res.get('ok')) and not res.get('codes')
out['elapsed_s'] = time.perf_counter() - t0
print(json.dumps(out, default=str))
'''


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--frozen', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('runs', nargs='+', type=Path); a = ap.parse_args()
    kit = a.frozen.resolve(); base = kit / 'routing_candidate/baseline'
    code = {n: sha(base / n) for n in ('adaptive_checker.py', 'hybrid_checker.py', 'hybrid_radiation.py', 'contact_first.py')}
    code['independent.py'] = sha(base / 'routing-package/routing/independent.py'); code['core.py'] = sha(base / 'routing-package/routing/core.py')
    n_pass = n = 0
    for d in a.runs:
        d = d.resolve(); res = json.loads((d / 'RESULT.json').read_text()); job = json.loads((d / 'JOB.json').read_text())
        route = res.get('result') or {}
        if not route.get('legs'):
            route = route.get('checked_incumbent') or {}
        if not route.get('legs'):
            continue
        rp = d / 'G2_ROUTE.json'; rp.write_text(json.dumps({'legs': route['legs'], 'destination': route['destination'], 'arrival': route.get('arrival')}))
        req_p = d / 'ORIGINAL_REQUEST.json'; packet = Path(job['hazard_path']).parent
        row = {'run': str(d), 'arrival': route.get('arrival'), 'decision': (res.get('decision') or {}).get('authoritative_status'),
               'kit_identity': res.get('kit_identity'), 'checker_code_sha256': code,
               'inputs_sha256': {'graph': sha(job['graph_path']), 'hazard': sha(job['hazard_path']), 'request': sha(req_p), 'route': sha(rp)}}
        for which in ('whole_road', 'independent'):
            p = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(kit), job['graph_path'], str(packet), str(req_p), str(rp), which],
                               capture_output=True, text=True)
            row[which] = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {'pass': False, 'error': p.stderr[-1500:]}
        row['pass'] = row['whole_road']['pass'] and row['independent']['pass']
        n += 1; n_pass += row['pass']
        with a.out.open('a') as f:
            f.write(json.dumps(row, default=str) + '\n')
        print('%-90s arr=%s whole_road=%s independent=%s' % (str(d)[-90:], row['arrival'], row['whole_road'].get('status'), row['independent'].get('ok')), flush=True)
    print('G2: %d/%d published routes accepted by both checkers' % (n_pass, n))


if __name__ == '__main__':
    main()
