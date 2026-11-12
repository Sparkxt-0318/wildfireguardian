"""Verify margin witnesses written by clearance_panel.py (and the published routes) two independent ways:

1. the kit's unchanged whole-road checker on the ORIGINAL frozen packet (fixed_route_check.py, own interpreter):
   status must be CERTIFIED_ADMISSIBLE (contact, radiation dose/peak, grammar, opening, dwell, horizon);
2. exact rational clearance: for every route segment (EDGE, WAIT, DWELL; positions linear in time) and every source
   whose activity overlaps it, the squared distance from the moving point (restricted to the overlap) to the closed
   source rectangle is minimised exactly (piecewise quadratic in the line parameter; minimum at a piece boundary or a
   vertex, all rational). The route's exact clearance must exceed the claimed r_lo.
Binary64 is used only to skip pairs farther than r_lo + 50 m.

  python verify_witnesses.py --kit KIT --margins OUT/margin_routes --out VERIFY.jsonl [--published]
"""
import argparse, json, math, subprocess, sys
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import clearance as C  # noqa: E402


def exact_min_d2(p0, p1, rect):
    """min over u in [0,1] of squared distance from p0 + u (p1 - p0) to the closed rectangle (exact Fractions)."""
    x0, x1, y0, y1 = rect
    ax, ay = p0; bx, by = p1; dx, dy = bx - ax, by - ay
    cuts = {F(0), F(1)}
    for c, a, d in ((x0, ax, dx), (x1, ax, dx), (y0, ay, dy), (y1, ay, dy)):
        if d != 0:
            u = (c - a) / d
            if 0 < u < 1:
                cuts.add(u)
    cuts = sorted(cuts)
    def d2(u):
        px, py = ax + dx * u, ay + dy * u
        ex = max(x0 - px, F(0), px - x1); ey = max(y0 - py, F(0), py - y1)
        return ex * ex + ey * ey
    best = min(d2(u) for u in cuts)
    for lo, hi in zip(cuts, cuts[1:]):
        mid = (lo + hi) / 2
        px, py = ax + dx * mid, ay + dy * mid
        # on this piece each axis term is 0 or linear; the quadratic's vertex in (lo, hi) is a candidate
        cx = (x0 - ax) if px < x0 else (x1 - ax) if px > x1 else None
        cy = (y0 - ay) if py < y0 else (y1 - ay) if py > y1 else None
        num = (dx * cx if cx is not None else 0) + (dy * cy if cy is not None else 0)
        den = (dx * dx if cx is not None else 0) + (dy * dy if cy is not None else 0)
        if den:
            u = F(num) / den
            if lo < u < hi:
                best = min(best, d2(u))
    return best


def exact_clearance_exceeds(I, route, r):
    """True iff every time-overlapping (segment, source) pair is at exact distance > r. Also returns the exact min d."""
    req = I.req; segs = []
    for L in route['legs']:
        if L['kind'] == 'EDGE':
            e = I.edges[I.eidx[L['edge']]]
            segs.append(((F(I.nodes[e['u']]['x']), F(I.nodes[e['u']]['y'])), (F(I.nodes[e['v']]['x']), F(I.nodes[e['v']]['y'])), F(L['start']), F(L['end'])))
        else:
            n = I.nodes[L['node']]; p = (F(n['x']), F(n['y'])); segs.append((p, p, F(L['start']), F(L['end'])))
    dw = [d['dwell'] for d in req['destinations'] if d['node'] == route['destination']][0]
    n = I.nodes[route['destination']]; p = (F(n['x']), F(n['y']))
    segs.append((p, p, F(route['arrival']), F(route['arrival'] + dw)))
    rr = F(r) * F(r); best = None; pairs = 0
    import numpy as np
    for p0, p1, t0, t1 in segs:
        k = np.flatnonzero((I.SB <= float(t1)) & (I.SE > float(t0)))
        if not k.size:
            continue
        P0 = np.array([[float(p0[0]), float(p0[1])]] * k.size); P1 = np.array([[float(p1[0]), float(p1[1])]] * k.size)
        _, dm = C.seg_rect(P0, P1, I.SR[k])
        for j in k[dm <= r + 50.0]:
            s = I.src[j]
            b, e = F(s['birth']), F(s['expiry'])
            ta, tb = max(t0, b), min(t1, e)           # closed occupancy meets half-open activity
            if ta > tb or (ta == tb and tb == e):
                continue
            span = t1 - t0
            ua = (ta - t0) / span if span else F(0); ub = (tb - t0) / span if span else F(0)
            q0 = (p0[0] + (p1[0] - p0[0]) * ua, p0[1] + (p1[1] - p0[1]) * ua)
            q1 = (p0[0] + (p1[0] - p0[0]) * ub, p0[1] + (p1[1] - p0[1]) * ub)
            d2 = exact_min_d2(q0, q1, tuple(F(v) for v in s['rect'])); pairs += 1
            best = d2 if best is None else min(best, d2)
    ok = best is None or best > rr
    return ok, (None if best is None else math.sqrt(float(best))), pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--margins', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--published', action='store_true', help='also verify routes/*.json at r = their own clearance - 1e-6')
    a = ap.parse_args()
    files = sorted(a.margins.glob('*.json'))
    if a.published:
        files += sorted((HERE / 'routes').glob('*.json'))
    cache = {}; done = {}
    for f in files:
        w = json.loads(f.read_text()); m = w['mission']; region, case = m.split('__')
        key = (m, json.dumps(w['legs'], sort_keys=True), w['arrival'])
        if m not in cache:
            cache[m] = C.Instance(*C.load(region, case))
        I = cache[m]
        r = w.get('r_lo_m')
        if r is None:
            r = I.route_clearance(w)[0] - 1e-6
        ok, dmin, pairs = exact_clearance_exceeds(I, w, r)
        cutoff = case.split('_')[0]
        if key in done:                      # identical route already checked by the full checker
            c = done[key]
        else:
          chk = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'fixed_route_check.py'), '--kit', str(a.kit),
                              '--packet', str(REPO / 'data/routing/latest_inputs_try02/packets' / region / cutoff),
                              '--graph', str(REPO / 'data/routing/graphs' / region / 'graph.json'),
                              '--request', str(REPO / 'data/routing/latest_inputs_try02/requests' / region / (case + '.json')),
                              '--route', str(f), '--wall', '900'], capture_output=True, text=True)
          try:
            c = json.loads(chk.stdout.strip().splitlines()[-1])
          except Exception:
            c = {'status': 'CHECK_FAILED', 'tail': (chk.stdout + chk.stderr)[-500:]}
          done[key] = c
        row = {'file': f.name, 'mission': m, 'deadline': w.get('deadline', 'published'), 'arrival': w['arrival'], 'claimed_r_m': r,
               'exact_clearance_exceeds_claim': ok, 'exact_min_distance_m': dmin, 'exact_pairs': pairs,
               'full_checker_status': c.get('status'), 'full_checker_reason': c.get('reason'), 'full_checker_s': c.get('elapsed_s')}
        with a.out.open('a') as fh:
            fh.write(json.dumps(row) + '\n')
        print('%-60s r=%8.2f exact_ok=%s dmin=%s checker=%s %s' % (f.name, r, ok, None if dmin is None else round(dmin, 3),
                                                                   c.get('status'), c.get('reason')), flush=True)


if __name__ == '__main__':
    main()
