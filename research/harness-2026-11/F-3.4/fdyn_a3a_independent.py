"""FDYN_PLAN A3(a), second checker (Iris condition 4): run the routing package's INDEPENDENT checker
(routing.independent.check_route via routing.core.check_route, after validate_graph/validate_hazard/validate_request)
on the same Yeongdeok witness routes, one fresh interpreter per route, and record hashes of the checker code and inputs.
Labelled: re-checked offline outside the kit; not published by the kit.
  python -I fdyn_a3a_independent.py KIT RUN_DIR ROUTE_JSON GRAPH PACKET_DIR
"""
import hashlib, json, sys, time
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    kit, run, route_p, graph_p, packet = map(Path, sys.argv[1:6])
    pkg = kit / 'routing_candidate/baseline/routing-package'
    sys.path.insert(0, str(pkg))
    from routing import validation as V, core
    graph = json.loads(graph_p.read_text()); hazard = json.loads((packet / 'HAZARD.json').read_text())
    req = json.loads((run / 'ORIGINAL_REQUEST.json').read_text()); route = json.loads(route_p.read_text())
    t0 = time.perf_counter()
    g = V.validate_graph(graph) or graph
    h = V.validate_hazard(g, hazard, req.get('as_of')) or hazard
    r = V.validate_request(g, h, req) or req
    res = core.check_route(g, h, r, route['legs'], route['destination'])
    pm = res.get('per_member') or {}
    out = {'ok': res.get('ok'), 'codes': res.get('codes'), 'elapsed_s': time.perf_counter() - t0,
           'max_dose_share': max((float(v['dose']) / req['budgets']['dose'][k] for k, v in pm.items() if v.get('dose') is not None), default=None),
           'max_peak_share': max((v['peak'] / req['budgets']['peak'] for k, v in pm.items()), default=None),
           'hashes': {'independent.py': sha(pkg / 'routing/independent.py'), 'core.py': sha(pkg / 'routing/core.py'),
                      'validation.py': sha(pkg / 'routing/validation.py'), 'route': sha(route_p), 'graph': sha(graph_p),
                      'hazard': sha(packet / 'HAZARD.json'), 'request': sha(run / 'ORIGINAL_REQUEST.json')},
           'label': 're-checked offline outside the kit; not published by the kit'}
    print(json.dumps(out, default=str))


if __name__ == '__main__':
    main()
