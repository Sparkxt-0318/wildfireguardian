"""Memoization headroom of the exact-rational radiation kernel (F-3.4 option "memoize first").

Runs the kit's unchanged whole-road checker (adaptive_checker.HybridChecker) on fixed published routes and counts
RationalKernel.corner calls, actual evaluations (the kernel already memoizes on the exact (x, y) key within one
checker object) and distinct keys, per route and pooled across routes that share a packet (what a persistent
per-forecast corner cache could reuse). Optionally snaps receiver boxes outward to a dyadic grid of 2**-k metres
(--snap-bits k) to measure how many more keys would repeat; snapping widens the enclosure and is NOT the frozen
behaviour - verdicts are reported so any change is visible.

  python corner_stats.py --kit KIT --routes routes/a.json routes/b.json [--snap-bits 6]
"""
import argparse, json, sys, time
from fractions import Fraction as F
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--routes', type=Path, nargs='+', required=True)
    ap.add_argument('--snap-bits', type=int, default=None)
    a = ap.parse_args()
    kit = a.kit.resolve()
    q = json.loads((kit / 'queues/LATEST_PREFLIGHT_REAL.json').read_text())['jobs'][0]
    src = Path(q['source_root']); src = src if src.is_absolute() else kit / src
    sys.path[:0] = [str(src / 'baseline/routing-package'), str(src / 'baseline'), str(src / 'search'), str(kit / 'phaseB')]
    import importlib, math
    HC = importlib.import_module(q['checker_module']).HybridChecker
    import road_exposure as RE
    import hybrid_radiation as HR
    from mission_contract import graph_digest
    keys_all = {}; calls = {'n': 0}
    orig_corner = RE.RationalKernel.corner

    def corner(self, x, y):
        calls['n'] += 1
        k = (RE.rational(x), RE.rational(y)); keys_all[k] = keys_all.get(k, 0) + 1
        return orig_corner(self, x, y)
    RE.RationalKernel.corner = corner
    if a.snap_bits is not None:
        orig_srb = RE.RationalKernel.source_receiver_box
        s = 2 ** a.snap_bits

        def snapped(self, source, receiver):
            rx0, rx1, ry0, ry1 = receiver   # outward: lower ends down, upper ends up, on the 2**-k grid
            box = (F(math.floor(F(rx0) * s), s), F(math.ceil(F(rx1) * s), s), F(math.floor(F(ry0) * s), s), F(math.ceil(F(ry1) * s), s))
            return orig_srb(self, source, box)
        RE.RationalKernel.source_receiver_box = snapped
    rows = []
    for rp in a.routes:
        r = json.loads(rp.read_text()); region, case = r['mission'].split('__'); cutoff = case.split('_')[0]
        graph = json.loads((REPO / 'data/routing/graphs' / region / 'graph.json').read_text())
        req = json.loads((REPO / 'data/routing/latest_inputs_try02/requests' / region / (case + '.json')).read_text())
        n0 = calls['n']; k0 = len(keys_all); t0 = time.perf_counter()
        chk = HC(REPO / 'data/routing/latest_inputs_try02/packets' / region / cutoff)
        rec = chk.check(graph, req, r['legs'], r['destination'], wall_s=900, deadline=time.perf_counter() + 900,
                        expected_graph_revision=graph['revision'], expected_graph_sha256=graph_digest(graph))
        rad = rec.get('radiation') or {}
        rows.append({'mission': r['mission'], 'status': rec.get('status'), 'reason': rec.get('reason'),
                     'corner_calls': calls['n'] - n0, 'corner_evaluations_in_checker': rad.get('analytic_corner_evaluations'),
                     'new_distinct_keys_vs_previous_routes': len(keys_all) - k0, 'radiation_s': (rec.get('timing_s') or {}).get('radiation_check'),
                     'check_s': time.perf_counter() - t0, 'snap_bits': a.snap_bits})
        print(json.dumps(rows[-1]), flush=True)
    print(json.dumps({'total_calls': calls['n'], 'distinct_keys_pooled': len(keys_all),
                      'pooled_hit_rate_upper_bound': 1 - len(keys_all) / max(1, calls['n'])}))


if __name__ == '__main__':
    main()
