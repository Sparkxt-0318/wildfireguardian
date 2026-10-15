"""Outward-rounded binary64 interval enclosure of the declared rectangle
solid-angle kernel  I(R) = density * Omega(R)/(4 pi),
Omega([x0,x1]x[y0,y1]) = V(x1,y1)-V(x0,y1)-V(x1,y0)+V(x0,y0),
V(x,y) = sign(xy) * atan(|xy| / (h sqrt(x^2+y^2+h^2))).
This is the same closed form used by road_exposure.RationalKernel.rectangle
(baseline lines 134-164), evaluated in vectorized IEEE-754 binary64 with every
operation rounded outward by one ulp (np.nextafter), sqrt brackets verified by
interval squaring (baseline radiation_bounds.sqrt_bracket), and atan enclosed
by two half-angle reductions plus an alternating Taylor series with an explicit
remainder term. Only correctly rounded IEEE +,-,*,/,sqrt are relied on (the
same assumption as the baseline 'elementary_binary64_outward' proof flag); no
libm transcendental result is trusted."""
import numpy as np
from radiation_bounds import sqrt_bracket

NEG = -np.inf; POS = np.inf
def dn(x): return np.nextafter(x, NEG)
def up(x): return np.nextafter(x, POS)

N_TERMS = 24  # after two reductions t <= tan(pi/16) < 0.2; remainder < 0.2**49/49 ~ 1e-36

def _series(tl, th):
    """Lower bound of atan(tl), upper bound of atan(th), for 0 <= tl <= th < 0.21."""
    t2l = dn(tl * tl); t2h = up(th * th)
    pl = tl.copy(); ph = th.copy()
    lo = np.zeros_like(tl); hi = np.zeros_like(th)
    for k in range(N_TERMS):
        d = 2 * k + 1
        tlo = dn(pl / d); thi = up(ph / d)
        if k % 2 == 0:
            lo = dn(lo + tlo); hi = up(hi + thi)
        else:
            lo = dn(lo - thi); hi = up(hi - tlo)
        pl = dn(pl * t2l); ph = up(ph * t2h)
    # |remainder| <= t^(2N+1)/(2N+1); pl/ph now hold t^(2N+1) bounds
    rem = up(ph / (2 * N_TERMS + 1))
    return np.maximum(0, dn(lo - rem)), up(hi + rem)

def _reduce(zl, zh):
    """t = z/(1+sqrt(1+z^2)) is increasing in z; atan z = 2 atan t."""
    sl = sqrt_bracket(dn(1 + dn(zl * zl)))[0]  # lower sqrt of a lower radicand
    sh = sqrt_bracket(up(1 + up(zh * zh)))[1]
    tl = np.maximum(0, dn(zl / up(1 + sh)))
    th = up(zh / dn(1 + sl))
    return tl, th

def atan_bounds(zl, zh, pi_lo, pi_hi):
    """Al <= atan(zl), Ah >= atan(zh), for 0 <= zl <= zh (arrays)."""
    zl = np.asarray(zl, float); zh = np.asarray(zh, float)
    if not (np.all(zl >= 0) and np.all(zh >= zl) and np.all(np.isfinite(zh))): raise ArithmeticError('atan_bounds precondition')
    # small branch (argument <= 1)
    def small(a, b):
        a1, b1 = _reduce(a, b); a2, b2 = _reduce(a1, b1)
        if not np.all(b2 < 0.21): raise ArithmeticError('series range precondition')
        l, h = _series(a2, b2)
        return 4 * l, 4 * h  # exact power-of-two scaling
    big_l = zl > 1; big_h = zh > 1
    # lower bound
    al_arg = np.where(big_l, 0.0, zl)
    Al_small, _ = small(al_arg, al_arg)
    inv_up = np.where(big_l, up(1 / np.where(big_l, zl, 1.0)), 0.0)  # >= 1/zl
    _, B_up = small(inv_up, inv_up)
    Al = np.where(big_l, dn(pi_lo / 2 - B_up), Al_small)
    # upper bound
    ah_arg = np.where(big_h, 0.0, zh)
    _, Ah_small = small(ah_arg, ah_arg)
    inv_dn = np.where(big_h, dn(1 / np.where(big_h, zh, 1.0)), 0.0)  # <= 1/zh
    B_dn, _ = small(inv_dn, inv_dn)
    Ah = np.where(big_h, up(pi_hi / 2 - B_dn), Ah_small)
    return np.maximum(0, Al), np.minimum(up(pi_hi / 2), Ah)

def corner_bounds(x, y, h, pi_lo, pi_hi):
    """Bounds of V(x,y) for exactly represented float arrays x,y and exact h."""
    ax = np.abs(x); ay = np.abs(y)
    pl = dn(ax * ay); ph = up(ax * ay)
    rl = dn(dn(dn(ax * ax) + dn(ay * ay)) + dn(h * h)); rh = up(up(up(ax * ax) + up(ay * ay)) + up(h * h))
    sl = sqrt_bracket(rl)[0]; sh = sqrt_bracket(rh)[1]
    dl = dn(h * sl); dh = up(h * sh)
    zl = np.maximum(0, dn(pl / dh)); zh = up(ph / dl)
    Al, Ah = atan_bounds(zl, zh, pi_lo, pi_hi)
    s = np.sign(x) * np.sign(y)
    lo = np.where(s > 0, Al, np.where(s < 0, -Ah, 0.0))
    hi = np.where(s > 0, Ah, np.where(s < 0, -Al, 0.0))
    return lo, hi

def rectangle_bounds(x0, x1, y0, y1, h, pi_lo, pi_hi):
    """Bounds of Omega/(4 pi) for rectangles relative to the receiver."""
    a = corner_bounds(x1, y1, h, pi_lo, pi_hi); b = corner_bounds(x0, y1, h, pi_lo, pi_hi)
    c = corner_bounds(x1, y0, h, pi_lo, pi_hi); d = corner_bounds(x0, y0, h, pi_lo, pi_hi)
    ol = dn(dn(dn(a[0] - b[1]) - c[1]) + d[0]); oh = up(up(up(a[1] - b[0]) - c[0]) + d[1])
    lo = np.maximum(0, dn(ol / (4 * pi_hi))); hi = np.minimum(0.5, np.maximum(0, up(oh / (4 * pi_lo))))
    empty = (x0 >= x1) | (y0 >= y1)
    lo = np.where(empty, 0.0, lo); hi = np.where(empty, 0.0, hi)
    return lo, hi

def exact_diff(a, b):
    """a-b for positive floats within a factor two (Sterbenz lemma: exact)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    if not (np.all(a > 0) and np.all(b > 0) and np.all(a <= 2 * b) and np.all(b <= 2 * a)): raise ArithmeticError('Sterbenz precondition')
    return a - b
