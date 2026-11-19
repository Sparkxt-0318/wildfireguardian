"""Integer piecewise-linear "tent" functions (METHOD.md section 3).

A function f : Z -> {-1} ∪ {0, 1, 2, ...} is stored as a sorted list of pieces ``(lo, hi, v, s)``: on the integer
interval [lo, hi] the value is ``v + s * (t - lo)`` with slope ``s`` in {-1, 0, +1} and every value >= 0. Outside the
pieces the value is BOTTOM = -1 ("not feasible at any margin"). Pieces are disjoint and sorted; ``canon`` gives the
unique greedy-maximal form used for equality.

Standard library only; imports nothing from the repository.
"""
from __future__ import annotations

BOTTOM = -1


def _emit(out, lo, hi, v, s):
    """Append a piece, merging with the previous one when it continues it exactly (greedy-maximal, see canon)."""
    if lo > hi:
        return
    if lo == hi:
        s = 0
    if out:
        plo, phi, pv, ps = out[-1]
        if phi + 1 == lo:
            d = v - (pv + ps * (phi - plo))
            if plo == phi:                               # previous piece is a single point: its slope is free
                if -1 <= d <= 1:
                    if lo == hi or s == d:
                        out[-1] = (plo, hi, pv, d)
                        return
                    out[-1] = (plo, lo, pv, d)           # take the first point of the new piece
                    lo, v = lo + 1, v + s
                    if lo == hi:
                        s = 0
            elif d == ps:
                if lo == hi or s == ps:
                    out[-1] = (plo, hi, pv, ps)
                    return
                out[-1] = (plo, lo, pv, ps)
                lo, v = lo + 1, v + s
                if lo == hi:
                    s = 0
    out.append((lo, hi, v, s))


def canon(f):
    """Canonical form: every piece is the longest linear run starting at its first point."""
    out = []
    for lo, hi, v, s in f:
        _emit(out, lo, hi, v, s)
    return out


def const(lo, hi, c):
    return [(lo, hi, c, 0)] if lo <= hi and c >= 0 else []


def value(f, t):
    for lo, hi, v, s in f:
        if lo <= t <= hi:
            return v + s * (t - lo)
        if lo > t:
            break
    return BOTTOM


def restrict(f, a, b):
    out = []
    for lo, hi, v, s in f:
        if hi < a:
            continue
        if lo > b:
            break
        if lo < a:
            v += s * (a - lo)
            lo = a
        if hi > b:
            hi = b
        out.append((lo, hi, v, s if lo < hi else 0))
    return out


def shift(f, d):
    return [(lo + d, hi + d, v, s) for lo, hi, v, s in f]


def pmin(f, g):
    """Pointwise minimum; BOTTOM where either is BOTTOM."""
    out = []
    i = j = 0
    nf, ng = len(f), len(g)
    while i < nf and j < ng:
        alo, ahi, av, asl = f[i]
        blo, bhi, bv, bsl = g[j]
        lo = alo if alo > blo else blo
        hi = ahi if ahi < bhi else bhi
        if lo <= hi:
            fa = av + asl * (lo - alo)
            ga = bv + bsl * (lo - blo)
            d0 = fa - ga
            d1 = d0 + (asl - bsl) * (hi - lo)
            if d0 <= 0 and d1 <= 0:
                _emit(out, lo, hi, fa, asl)
            elif d0 >= 0 and d1 >= 0:
                _emit(out, lo, hi, ga, bsl)
            elif d0 < 0:                                   # f below, then g below
                k = (-d0) // (asl - bsl)
                _emit(out, lo, lo + k, fa, asl)
                _emit(out, lo + k + 1, hi, ga + bsl * (k + 1), bsl)
            else:                                          # g below, then f below
                k = d0 // (bsl - asl)
                _emit(out, lo, lo + k, ga, bsl)
                _emit(out, lo + k + 1, hi, fa + asl * (k + 1), asl)
        if ahi < bhi:
            i += 1
        elif bhi < ahi:
            j += 1
        else:
            i += 1
            j += 1
    return out


def raise_to(f, g):
    """Pointwise maximum h = max(f, g), plus the hull [clo, chi] of {t : g(t) > f(t)} (None, None if empty).
    Where f = g the piece of f is kept."""
    out = []
    clo = chi = None
    i = j = 0
    nf, ng = len(f), len(g)
    a = f[0] if nf else None
    b = g[0] if ng else None
    while a is not None or b is not None:
        if b is None or (a is not None and a[1] < b[0]):
            _emit(out, *a)
            i += 1
            a = f[i] if i < nf else None
            continue
        if a is None or b[1] < a[0]:
            _emit(out, *b)
            if clo is None:
                clo = b[0]
            chi = b[1]
            j += 1
            b = g[j] if j < ng else None
            continue
        alo, ahi, av, asl = a
        blo, bhi, bv, bsl = b
        if alo < blo:
            _emit(out, alo, blo - 1, av, asl)
            a = (blo, ahi, av + asl * (blo - alo), asl)
            continue
        if blo < alo:
            _emit(out, blo, alo - 1, bv, bsl)
            if clo is None:
                clo = blo
            chi = alo - 1
            b = (alo, bhi, bv + bsl * (alo - blo), bsl)
            continue
        lo = alo
        hi = ahi if ahi < bhi else bhi
        d0 = av - bv                                       # f - g at lo
        d1 = d0 + (asl - bsl) * (hi - lo)
        if d0 >= 0 and d1 >= 0:
            _emit(out, lo, hi, av, asl)
        elif d0 <= 0 and d1 <= 0:                          # g >= f, strictly somewhere
            _emit(out, lo, hi, bv, bsl)
            x = lo + 1 if d0 == 0 else lo
            y = hi - 1 if d1 == 0 else hi
            if clo is None:
                clo = x
            chi = y
        elif d0 < 0:                                       # g above first, f from the crossing on
            k = (-d0 - 1) // (asl - bsl)
            _emit(out, lo, lo + k, bv, bsl)
            _emit(out, lo + k + 1, hi, av + asl * (k + 1), asl)
            if clo is None:
                clo = lo
            chi = lo + k
        else:                                              # f above first, g strictly above after the crossing
            k = d0 // (bsl - asl) + 1
            _emit(out, lo, lo + k - 1, av, asl)
            _emit(out, lo + k, hi, bv + bsl * k, bsl)
            if clo is None:
                clo = lo + k
            chi = hi
        if ahi == hi:
            i += 1
            a = f[i] if i < nf else None
        else:
            a = (hi + 1, ahi, av + asl * (hi + 1 - alo), asl)
        if bhi == hi:
            j += 1
            b = g[j] if j < ng else None
        else:
            b = (hi + 1, bhi, bv + bsl * (hi + 1 - blo), bsl)
    return out, clo, chi


def pmax(f, g):
    return raise_to(f, g)[0]


def suffix_max(q, left):
    """Q(t) = max over u >= t of q(u), for t in [left, last point of q]; BOTTOM where that maximum is BOTTOM."""
    rev = []
    m = BOTTOM
    nxt = None                                             # lo of the piece processed just before (to the right)
    for lo, hi, v, s in reversed(q):
        if nxt is not None and hi + 1 < nxt and m >= 0:
            rev.append((hi + 1, nxt - 1, m, 0))
        e = v + s * (hi - lo)
        if s >= 0:
            top = e if e > m else m
            rev.append((lo, hi, top, 0))
            m = top
        elif m <= e:
            rev.append((lo, hi, v, s))
            m = v
        elif m >= v:
            rev.append((lo, hi, m, 0))
        else:                                              # follows q on [lo, lo + v - m], constant m after
            c = lo + v - m
            rev.append((c + 1, hi, m, 0))
            rev.append((lo, c, v, s))
            m = v
        nxt = lo
    if nxt is not None and left < nxt and m >= 0:
        rev.append((left, nxt - 1, m, 0))
    out = []
    for p in reversed(rev):
        _emit(out, *p)
    return restrict(out, left, 1 << 62)


def level_set(f, m):
    """{t : f(t) >= m} as a normalized list of closed integer intervals (m >= 0)."""
    out = []
    for lo, hi, v, s in f:
        if s == 0:
            if v < m:
                continue
            a, b = lo, hi
        elif s > 0:
            a, b = max(lo, lo + m - v), hi
        else:
            a, b = lo, min(hi, lo + v - m)
        if a > b:
            continue
        if out and out[-1][1] + 1 >= a:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def tent(closed, lo_dom, hi_dom, M):
    """min(M, dist(t, closed) - 1) for t in [lo_dom, hi_dom] outside ``closed`` (a normalized interval list);
    BOTTOM inside it. With no closure the function is the constant M."""
    if lo_dom > hi_dom:
        return []
    out = []
    prev_end = None                                        # last closed second to the left of the current gap
    edges = [(lo, hi) for lo, hi in closed] + [None]
    for c in edges:
        g_lo = lo_dom if prev_end is None else prev_end + 1
        g_hi = hi_dom if c is None else c[0] - 1
        a, b = max(g_lo, lo_dom), min(g_hi, hi_dom)
        if a <= b:
            f = const(a, b, M)
            if prev_end is not None:                       # rising from 0 at prev_end + 1
                f = pmin(f, [(a, b, a - prev_end - 1, 1)])
            if c is not None:                              # falling to 0 at c.lo - 1
                f = pmin(f, [(a, b, c[0] - 1 - a, -1)])
            for p in f:
                _emit(out, *p)
        if c is not None:
            prev_end = c[1] if prev_end is None else max(prev_end, c[1])
    return out


def to_dense(f, lo, hi):
    out = [BOTTOM] * (hi - lo + 1)
    for a, b, v, s in f:
        for t in range(max(a, lo), min(b, hi) + 1):
            out[t - lo] = v + s * (t - a)
    return out


def n_pieces(f):
    return len(f)
