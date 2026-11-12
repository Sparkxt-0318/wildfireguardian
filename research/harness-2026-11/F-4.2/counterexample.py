"""Reproduce the non-monotonicity counterexample of MONOTONICITY.md (exact rational arithmetic, stdlib only).

Source law of the frozen bridge: a source with drawn ignition b emits on [b, b+T) with T > H. A fixed route dwells at
one point on [3480, 3600] (H = 3600). Two sources each give flux k at that point (k = 1, so the budget is 200 dose units).
Under the uniform advance A_delta (b -> b - delta), dwell dose = sum over sources of |[3480, 3600] ∩ [b-delta, b-delta+T)|.
Admissible iff dose <= budget. Also prints the shipped scale: on the frozen panel the largest route dose is 0.33 of
its budget and the largest peak 0.0005 of its budget (RESULTS.md), so this mechanism cannot flip a verdict there.

  python3 counterexample.py
"""
from fractions import Fraction as F

T = F(3970464281524927, 10 ** 12)    # ≈ 3970.464 s: cell_duration_s of the frozen exports (rounded rational)
H = F(3600)
DWELL = (F(3480), F(3600))
SOURCES = [F(10), F(3590)]
K = F(1)
BUDGET = 200 * K


def overlap(a, b, c, d):
    return max(F(0), min(b, d) - max(a, c))


def dose(delta):
    return sum(K * overlap(DWELL[0], DWELL[1], b - delta, b - delta + T) for b in SOURCES)


def main():
    assert T > H
    print('T = %.3f s, H = %s s, dwell = [%s, %s], sources b = %s, budget = %s' % (float(T), H, *DWELL, [int(b) for b in SOURCES], BUDGET))
    rows = []
    for delta in [F(0), F(50), F(100), F(300), F(370), F(380), F(450), F(500), F(1000)]:
        d = dose(delta); ok = d <= BUDGET
        rows.append((delta, d, ok))
        print('delta=%5s  dose=%8.3f  admissible=%s' % (delta, float(d), ok))
    flips = sum(1 for (_, _, a), (_, _, b) in zip(rows, rows[1:]) if a != b)
    assert rows[0][2] and not rows[2][2] and rows[7][2], 'expected admissible / inadmissible / admissible'
    print('verdict changes along the grid: %d (a monotone property would change at most once)' % flips)
    # Claim 1 boundary: monotone for delta < T - t_end + b_min = T - 3600 + 10
    # S1 overlaps the dwell for (b1 + T - delta) - 3480 seconds once it burns out inside the dwell; S2 gives 120.
    readmit = SOURCES[0] + T - DWELL[0] - (BUDGET - 120 * K) / K
    print('Claim 1 monotone range here: delta < %.3f s; inadmissible from delta = 70; re-admitted from delta >= %.3f s '
          '(S1 overlap <= 80 s); S1 fully burned out before the dwell from delta >= %.3f s'
          % (float(T - DWELL[1] + min(SOURCES)), float(readmit), float(SOURCES[0] + T - DWELL[0])))
    assert dose(readmit) == BUDGET and dose(readmit - F(1, 1000)) > BUDGET and dose(F(70)) == BUDGET and dose(F(71)) > BUDGET


if __name__ == '__main__':
    main()
