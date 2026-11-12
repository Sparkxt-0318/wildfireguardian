"""Run the kit's mandatory whole-road checker on ONE fixed route against ONE (possibly perturbed) hazard packet.

The checker is the kit's own `adaptive_checker.HybridChecker` (the RDA_CAND whole-road checker: exact closed-footprint
flame contact + request-window radiation dose/peak enclosure, adaptive fallback), imported from the kit with the same
sys.path the worker uses. Nothing is re-implemented. Prints one JSON line.

  python -I -B fixed_route_check.py --kit KIT --packet DIR --graph G.json --request R.json --route RESULT.json [--wall 600]
`--route` is a worker RESULT.json (its published result's legs/destination are used) or a JSON with legs/destination.
"""
import argparse, json, sys, time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    for k in ('--kit', '--packet', '--graph', '--request', '--route'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--wall', type=float, default=600.0)
    a = ap.parse_args()
    kit = a.kit.resolve()
    q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
    src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
    sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
    import importlib
    HC = importlib.import_module(q['checker_module']).HybridChecker
    from mission_contract import graph_digest
    graph = json.loads(a.graph.read_text()); request = json.loads(a.request.read_text())
    r = json.loads(a.route.read_text())
    route = r.get('result', r) if 'legs' not in r else r
    legs, dest = route['legs'], route['destination']
    t0 = time.perf_counter()
    checker = HC(a.packet.resolve())
    rec = checker.check(graph, request, legs, dest, wall_s=a.wall, deadline=time.perf_counter() + a.wall,
                        expected_graph_revision=graph['revision'], expected_graph_sha256=graph_digest(graph))
    out = {'status': rec.get('status'), 'reason': rec.get('reason'), 'contact': (rec.get('contact') or {}).get('status'),
           'radiation': (rec.get('radiation') or {}).get('status'),
           'adaptive': (rec.get('adaptive_fallback') or {}).get('status') if rec.get('adaptive_fallback') else None,
           'per_member': (rec.get('adaptive_fallback') or {}).get('per_member') or (rec.get('radiation') or {}).get('per_member'),
           'arrival': route.get('arrival'), 'n_legs': len(legs), 'elapsed_s': time.perf_counter() - t0,
           'process_lifetime_rss_mb': rec.get('process_lifetime_rss_mb'), 'rss_gate_mb': rec.get('rss_gate_mb'),
           'checked_result_is_secondary': rec.get('checked_result_is_secondary'),
           'secondary_status': (rec.get('checked_result') or {}).get('status')}
    print(json.dumps(out, default=str))


if __name__ == '__main__':
    main()
