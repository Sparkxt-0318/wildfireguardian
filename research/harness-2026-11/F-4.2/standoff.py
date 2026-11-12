"""Standoff distances for radiant-heat thresholds, compared with the route clearances of the 1-hour panel (F-4.2 / FIRE 6.2).

Model (explicit assumptions, not a fire model): a vertical planar flame face of height H and width W radiates with
emissive power E to a vertical target element facing it, centred on the face, at horizontal distance d, with
transmissivity 1. Incident flux q = E * F(d), where F is the configuration factor of a rectangle to a parallel
differential element on its normal through a corner, summed over the 4 sub-rectangles (Howell catalogue C-11):

    F_corner(a, b, d) = 1/(2 pi) [ X/sqrt(1+X^2) atan(Y/sqrt(1+X^2)) + Y/sqrt(1+Y^2) atan(X/sqrt(1+Y^2)) ]

with X = a/d and Y = b/d. The target is at the flame base height (ground level, receiver height 0): the face spans
heights [0, H], i.e. two corner rectangles of height H and half-width W/2. F is decreasing in d, so the standoff
d*(q0) solving E F(d) = q0 is found by bisection. Limits use 1.0 and 2.5 kW/m^2 (Iris's proposed ceilings).

Ranges, all assumed: H 5-20 m, E 50-100 kW/m^2 (typical solid-flame emissive powers for vegetation fires), and
W 375 m (one burning cell) or 3,750 m (a long front).
The clearances are the published-route clearances (F-4.2/results/CLEARANCE.jsonl), measured from the closed flaming
cell rectangle, so they are directly comparable with a standoff from the flame face.

  python3 standoff.py [--clearance results/CLEARANCE.jsonl]
"""
import argparse, json, math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def f_corner(a, b, d):
    X, Y = a / d, b / d
    return (X / math.sqrt(1 + X * X) * math.atan(Y / math.sqrt(1 + X * X))
            + Y / math.sqrt(1 + Y * Y) * math.atan(X / math.sqrt(1 + Y * Y))) / (2 * math.pi)


def flux(E, H, W, d):
    return E * 2 * f_corner(H, W / 2, d)          # two corner rectangles (heights 0..H, each half-width W/2)


def standoff(E, H, W, q0, window=1.0):
    E = E * window                                    # window factor multiplies the received flux
    if flux(E, H, W, 1e-6) < q0:
        return 0.0
    lo, hi = 1e-6, 1e6
    for _ in range(200):
        m = math.sqrt(lo * hi)
        lo, hi = (m, hi) if flux(E, H, W, m) > q0 else (lo, m)
    return hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clearance', type=Path, default=HERE / 'results/CLEARANCE.jsonl')
    a = ap.parse_args()
    # sanity: at the face the flux is E/2 for an infinite face (half-space view), and E F -> 0 far away
    assert abs(flux(100, 1e6, 1e6, 1e-3) - 50) < 0.1
    clear = [(json.loads(l)['mission'], json.loads(l)['published_clearance_m'], json.loads(l)['published_limit_label'])
             for l in a.clearance.read_text().splitlines() if l.strip()]
    rows = []
    print('%6s %6s %7s %6s | %10s %10s' % ('E', 'H', 'W', 'window', 'd(1.0)', 'd(2.5)'))
    for window in (1.0, 0.5):
        for W in (375.0, 3750.0):
            for H in (5.0, 10.0, 20.0):
                for E in (50.0, 100.0):
                    d1, d25 = standoff(E, H, W, 1.0, window), standoff(E, H, W, 2.5, window)
                    n1 = sum(c < d1 for _, c, _ in clear); n25 = sum(c < d25 for _, c, _ in clear)
                    c1 = sum(c < d1 and lab == 'CROP' for _, c, lab in clear); c25 = sum(c < d25 and lab == 'CROP' for _, c, lab in clear)
                    rows.append({'E_kW_m2': E, 'H_m': H, 'W_m': W, 'window': window, 'standoff_1p0_m': d1, 'standoff_2p5_m': d25,
                                 'routes_below_1p0': n1, 'routes_below_2p5': n25, 'crop_limited_below_1p0': c1, 'crop_limited_below_2p5': c25})
                    print('%6.0f %6.0f %7.0f %6.1f | %8.1f m %8.1f m   below: %d (1.0) %d (2.5) of %d; crop-limited among them %d / %d'
                          % (E, H, W, window, d1, d25, n1, n25, len(clear), c1, c25))
    for window in (1.0, 0.5):
        rr = [r for r in rows if r['window'] == window]
        print('window %.1f: routes below 1.0-standoff range %d-%d; below 2.5-standoff range %d-%d (of %d)'
              % (window, min(r['routes_below_1p0'] for r in rr), max(r['routes_below_1p0'] for r in rr),
                 min(r['routes_below_2p5'] for r in rr), max(r['routes_below_2p5'] for r in rr), len(clear)))
    (HERE / 'results/STANDOFF.json').write_text(json.dumps({'plan': 'RADIANT_PLAN.md', 'rows': rows,
        'clearances_m': {m: c for m, c, _ in clear}}, indent=1) + '\n')
    worst = max(rows, key=lambda r: r['standoff_1p0_m'])
    print('\nlargest standoff in the range: %.0f m (E=%g, H=%g, W=%g)' % (worst['standoff_1p0_m'], worst['E_kW_m2'], worst['H_m'], worst['W_m']))
    print('published clearances (m):', ', '.join('%.0f' % c for _, c, _ in sorted(clear, key=lambda x: x[1])))


if __name__ == '__main__':
    main()
