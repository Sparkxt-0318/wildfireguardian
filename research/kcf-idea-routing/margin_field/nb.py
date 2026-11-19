"""Compiled (numba) form of the margin pass of ``field.py`` (METHOD.md section 4.7).

The same algorithm on fixed-size integer arrays: a function is rows ``[lo, hi, v, s]`` of an int64 array. Every routine
below is a line-by-line port of the routine of the same name in ``pl.py`` / ``field.py`` (general path, no fast path).
If a state needs more than ``cap`` pieces, a scratch buffer fills up, or the heap fills up, the compiled pass gives up
and ``margin_field_nb`` falls back to the pure-Python pass (``stats["fallback"]`` says so).

With M = 0 on a widened instance the same kernel is a compiled level-by-level pass; that is the compiled baseline
used in BENCH.md section 2 (there is no compiled form of the existing ``core.backward``).

Without numba installed the module still imports and runs (slowly) as plain Python, which is how the port is tested
where numba is missing.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:                                          # pragma: no cover
    HAVE_NUMBA = False

    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

from . import pl
from .field import MarginField, _Lazy, _accept_level, margin_field as _py_margin_field

BIG = 1 << 60
TMP = 1024


@njit(cache=True)
def _emit(out, n, lo, hi, v, s):
    if lo > hi:
        return n
    if n >= out.shape[0] - 1:                              # scratch full: caller sees n >= TMP - 2 and gives up
        return n
    if lo == hi:
        s = 0
    if n > 0:
        plo = out[n - 1, 0]
        phi = out[n - 1, 1]
        pv = out[n - 1, 2]
        ps = out[n - 1, 3]
        if phi + 1 == lo:
            d = v - (pv + ps * (phi - plo))
            if plo == phi:
                if -1 <= d <= 1:
                    if lo == hi or s == d:
                        out[n - 1, 1] = hi
                        out[n - 1, 3] = d
                        return n
                    out[n - 1, 1] = lo
                    out[n - 1, 3] = d
                    lo += 1
                    v += s
                    if lo == hi:
                        s = 0
            elif d == ps:
                if lo == hi or s == ps:
                    out[n - 1, 1] = hi
                    return n
                out[n - 1, 1] = lo
                lo += 1
                v += s
                if lo == hi:
                    s = 0
    out[n, 0] = lo
    out[n, 1] = hi
    out[n, 2] = v
    out[n, 3] = s
    return n + 1


@njit(cache=True)
def _copy(src, n, dst):
    for i in range(n):
        dst[i, 0] = src[i, 0]
        dst[i, 1] = src[i, 1]
        dst[i, 2] = src[i, 2]
        dst[i, 3] = src[i, 3]
    return n


@njit(cache=True)
def _value(f, nf, t):
    for i in range(nf):
        if f[i, 0] <= t <= f[i, 1]:
            return f[i, 2] + f[i, 3] * (t - f[i, 0])
        if f[i, 0] > t:
            break
    return -1


@njit(cache=True)
def _restrict(f, nf, a, b, out):
    n = 0
    for i in range(nf):
        lo = f[i, 0]
        hi = f[i, 1]
        v = f[i, 2]
        s = f[i, 3]
        if hi < a:
            continue
        if lo > b:
            break
        if lo < a:
            v += s * (a - lo)
            lo = a
        if hi > b:
            hi = b
        if n >= out.shape[0] - 1:
            return n
        out[n, 0] = lo
        out[n, 1] = hi
        out[n, 2] = v
        out[n, 3] = s if lo < hi else 0
        n += 1
    return n


@njit(cache=True)
def _pmin(f, nf, g, ng, out):
    n = 0
    i = 0
    j = 0
    while i < nf and j < ng:
        alo = f[i, 0]
        ahi = f[i, 1]
        av = f[i, 2]
        asl = f[i, 3]
        blo = g[j, 0]
        bhi = g[j, 1]
        bv = g[j, 2]
        bsl = g[j, 3]
        lo = alo if alo > blo else blo
        hi = ahi if ahi < bhi else bhi
        if lo <= hi:
            fa = av + asl * (lo - alo)
            ga = bv + bsl * (lo - blo)
            d0 = fa - ga
            d1 = d0 + (asl - bsl) * (hi - lo)
            if d0 <= 0 and d1 <= 0:
                n = _emit(out, n, lo, hi, fa, asl)
            elif d0 >= 0 and d1 >= 0:
                n = _emit(out, n, lo, hi, ga, bsl)
            elif d0 < 0:
                k = (-d0) // (asl - bsl)
                n = _emit(out, n, lo, lo + k, fa, asl)
                n = _emit(out, n, lo + k + 1, hi, ga + bsl * (k + 1), bsl)
            else:
                k = d0 // (bsl - asl)
                n = _emit(out, n, lo, lo + k, ga, bsl)
                n = _emit(out, n, lo + k + 1, hi, fa + asl * (k + 1), asl)
        if ahi < bhi:
            i += 1
        elif bhi < ahi:
            j += 1
        else:
            i += 1
            j += 1
    return n


@njit(cache=True)
def _raise(f, nf, g, ng, out):
    """max(f, g) into out; returns (n, clo, chi) with clo = BIG when g is nowhere above f."""
    n = 0
    clo = BIG
    chi = -BIG
    i = 0
    j = 0
    ha = nf > 0
    hb = ng > 0
    alo = ahi = av = asl = 0
    blo = bhi = bv = bsl = 0
    if ha:
        alo = f[0, 0]
        ahi = f[0, 1]
        av = f[0, 2]
        asl = f[0, 3]
    if hb:
        blo = g[0, 0]
        bhi = g[0, 1]
        bv = g[0, 2]
        bsl = g[0, 3]
    while ha or hb:
        if (not hb) or (ha and ahi < blo):
            n = _emit(out, n, alo, ahi, av, asl)
            i += 1
            ha = i < nf
            if ha:
                alo = f[i, 0]
                ahi = f[i, 1]
                av = f[i, 2]
                asl = f[i, 3]
            continue
        if (not ha) or bhi < alo:
            n = _emit(out, n, blo, bhi, bv, bsl)
            if clo == BIG:
                clo = blo
            chi = bhi
            j += 1
            hb = j < ng
            if hb:
                blo = g[j, 0]
                bhi = g[j, 1]
                bv = g[j, 2]
                bsl = g[j, 3]
            continue
        if alo < blo:
            n = _emit(out, n, alo, blo - 1, av, asl)
            av += asl * (blo - alo)
            alo = blo
            continue
        if blo < alo:
            n = _emit(out, n, blo, alo - 1, bv, bsl)
            if clo == BIG:
                clo = blo
            chi = alo - 1
            bv += bsl * (alo - blo)
            blo = alo
            continue
        lo = alo
        hi = ahi if ahi < bhi else bhi
        d0 = av - bv
        d1 = d0 + (asl - bsl) * (hi - lo)
        if d0 >= 0 and d1 >= 0:
            n = _emit(out, n, lo, hi, av, asl)
        elif d0 <= 0 and d1 <= 0:
            n = _emit(out, n, lo, hi, bv, bsl)
            x = lo + 1 if d0 == 0 else lo
            y = hi - 1 if d1 == 0 else hi
            if clo == BIG:
                clo = x
            chi = y
        elif d0 < 0:
            k = (-d0 - 1) // (asl - bsl)
            n = _emit(out, n, lo, lo + k, bv, bsl)
            n = _emit(out, n, lo + k + 1, hi, av + asl * (k + 1), asl)
            if clo == BIG:
                clo = lo
            chi = lo + k
        else:
            k = d0 // (bsl - asl) + 1
            n = _emit(out, n, lo, lo + k - 1, av, asl)
            n = _emit(out, n, lo + k, hi, bv + bsl * k, bsl)
            if clo == BIG:
                clo = lo + k
            chi = hi
        if ahi == hi:
            i += 1
            ha = i < nf
            if ha:
                alo = f[i, 0]
                ahi = f[i, 1]
                av = f[i, 2]
                asl = f[i, 3]
        else:
            av += asl * (hi + 1 - alo)
            alo = hi + 1
        if bhi == hi:
            j += 1
            hb = j < ng
            if hb:
                blo = g[j, 0]
                bhi = g[j, 1]
                bv = g[j, 2]
                bsl = g[j, 3]
        else:
            bv += bsl * (hi + 1 - blo)
            blo = hi + 1
    return n, clo, chi


@njit(cache=True)
def _suffix_max(q, nq, left, rev, out, out2):
    r = 0
    m = -1
    nxt = BIG
    cap = rev.shape[0] - 3
    for idx in range(nq - 1, -1, -1):
        if r >= cap:
            return out2.shape[0]                           # signals overflow to the caller
        lo = q[idx, 0]
        hi = q[idx, 1]
        v = q[idx, 2]
        s = q[idx, 3]
        if nxt != BIG and hi + 1 < nxt and m >= 0:
            rev[r, 0] = hi + 1
            rev[r, 1] = nxt - 1
            rev[r, 2] = m
            rev[r, 3] = 0
            r += 1
        e = v + s * (hi - lo)
        if s >= 0:
            top = e if e > m else m
            rev[r, 0] = lo
            rev[r, 1] = hi
            rev[r, 2] = top
            rev[r, 3] = 0
            r += 1
            m = top
        elif m <= e:
            rev[r, 0] = lo
            rev[r, 1] = hi
            rev[r, 2] = v
            rev[r, 3] = s
            r += 1
            m = v
        elif m >= v:
            rev[r, 0] = lo
            rev[r, 1] = hi
            rev[r, 2] = m
            rev[r, 3] = 0
            r += 1
        else:
            c = lo + v - m
            rev[r, 0] = c + 1
            rev[r, 1] = hi
            rev[r, 2] = m
            rev[r, 3] = 0
            r += 1
            rev[r, 0] = lo
            rev[r, 1] = c
            rev[r, 2] = v
            rev[r, 3] = s
            r += 1
            m = v
        nxt = lo
    if nxt != BIG and left < nxt and m >= 0:
        rev[r, 0] = left
        rev[r, 1] = nxt - 1
        rev[r, 2] = m
        rev[r, 3] = 0
        r += 1
    n = 0
    for k in range(r - 1, -1, -1):
        n = _emit(out, n, rev[k, 0], rev[k, 1], rev[k, 2], rev[k, 3])
    return _restrict(out, n, left, BIG, out2)


@njit(cache=True)
def _wait_close(mu, nmu, om, nom, c, c2, t1, t2, t3, t4):
    """cl_omega(mu) into c; returns its piece count (>= c.shape[0] - 2 on overflow)."""
    lim = c.shape[0] - 2
    nc = _copy(mu, nmu, c)
    if nmu == 0 or nom == 0:
        return nc
    carry = -1
    nxt_lo = BIG
    for idx in range(nom - 1, -1, -1):
        x = om[idx, 0]
        y = om[idx, 1]
        v = om[idx, 2]
        s = om[idx, 3]
        if nxt_lo == BIG or y + 1 != nxt_lo:
            carry = _value(c, nc, y + 1)
        wy = v + s * (y - x)
        k = carry if carry < wy else wy
        nb = 0                                             # base lives in t3
        if y > x:
            n1 = _restrict(mu, nmu, x + 1, y, t1)
            t2[0, 0] = x + 1
            t2[0, 1] = y
            t2[0, 2] = v
            t2[0, 3] = s
            nq = _pmin(t1, n1, t2, 1, t4)
            if nq > 0:
                nb = _suffix_max(t4, nq, x + 1, t1, t2, t3)
                if nb >= lim:
                    return lim
                for i in range(nb):
                    t3[i, 0] -= 1
                    t3[i, 1] -= 1
        if k >= 0:
            t1[0, 0] = x
            t1[0, 1] = y
            t1[0, 2] = k
            t1[0, 3] = 0
            nb2, _a, _b = _raise(t3, nb, t1, 1, t4)
            nb = _copy(t4, nb2, t3)
        if nb > 0:
            t1[0, 0] = x
            t1[0, 1] = y
            t1[0, 2] = v
            t1[0, 3] = s if y > x else 0
            na = _pmin(t1, 1, t3, nb, t2)
            if na > 0:
                nc2, _a, _b = _raise(c, nc, t2, na, c2)
                nc = _copy(c2, nc2, c)
                if nc >= lim:
                    return lim
        carry = _value(c, nc, x)
        nxt_lo = x
    return nc


@njit(cache=True)
def _hpush(hk, hv, n, k, v):
    i = n
    hk[i] = k
    hv[i] = v
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] >= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hv[p], hv[i] = hv[i], hv[p]
        i = p
    return n + 1


@njit(cache=True)
def _hpop(hk, hv, n):
    v = hv[0]
    n -= 1
    hk[0] = hk[n]
    hv[0] = hv[n]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= n:
            break
        r = l + 1
        c = l
        if r < n and hk[r] > hk[l]:
            c = r
        if hk[i] >= hk[c]:
            break
        hk[i], hk[c] = hk[c], hk[i]
        hv[i], hv[c] = hv[c], hv[i]
        i = c
    return v, n


@njit(cache=True)
def _pass(E, H, M, D, head, waitable, pptr, pidx, bptr, bdat, aptr, adat, optr, odat, mu, cnt):
    """Returns (status, pushes, pops, relaxations). status 0 = done, 1 = a function outgrew its buffer,
    2 = heap full."""
    CAP = mu.shape[1]
    g = np.zeros((TMP, 4), np.int64)
    cand = np.zeros((TMP, 4), np.int64)
    new = np.zeros((TMP, 4), np.int64)
    c = np.zeros((TMP, 4), np.int64)
    c2 = np.zeros((TMP, 4), np.int64)
    t1 = np.zeros((TMP, 4), np.int64)
    t2 = np.zeros((TMP, 4), np.int64)
    t3 = np.zeros((TMP, 4), np.int64)
    t4 = np.zeros((TMP, 4), np.int64)
    one = np.zeros((2, 4), np.int64)
    lim = TMP - 2
    dlo = np.zeros(E, np.int64)
    dhi = np.zeros(E, np.int64)
    dirty = np.zeros(E, np.uint8)
    hcap = 8 * E + 1024
    hk = np.zeros(hcap, np.int64)
    hv = np.zeros(hcap, np.int64)
    hn = 0
    pushes = 0
    pops = 0
    relax = 0
    for j in range(E):
        if aptr[j + 1] > aptr[j]:
            dlo[j] = adat[aptr[j], 0]
            dhi[j] = adat[aptr[j + 1] - 1, 1]
            dirty[j] = 1
            hn = _hpush(hk, hv, hn, dhi[j], j)
            pushes += 1
    while hn > 0:
        j, hn = _hpop(hk, hv, hn)
        if dirty[j] == 0:
            continue
        dirty[j] = 0
        pops += 1
        a = dlo[j]
        b = dhi[j]
        ng = _restrict(mu[j], cnt[j], a, b, g)
        na = aptr[j + 1] - aptr[j]
        if na > 0:
            n1 = _restrict(adat[aptr[j]:aptr[j + 1]], na, a, b, t1)
            n2, _x, _y = _raise(t1, n1, g, ng, t2)
            ng = _copy(t2, n2, g)
        dj = D[j]
        for i in range(ng):
            g[i, 0] -= dj
            g[i, 1] -= dj
        nb = bptr[j + 1] - bptr[j]
        if nb > 0:
            ncand = _pmin(bdat[bptr[j]:bptr[j + 1]], nb, g, ng, cand)
        elif nb == 0 and H - dj >= 0:
            one[0, 0] = 0
            one[0, 1] = H - dj
            one[0, 2] = M
            one[0, 3] = 0
            ncand = _pmin(one, 1, g, ng, cand)
        else:
            ncand = 0
        if ncand == 0:
            continue
        if ncand >= lim:
            return 1, pushes, pops, relax
        for q in range(pptr[j], pptr[j + 1]):
            s = pidx[q]
            relax += 1
            nn, clo, chi = _raise(mu[s], cnt[s], cand, ncand, new)
            if clo == BIG:
                continue
            if nn >= lim:
                return 1, pushes, pops, relax
            hd = head[s]
            if waitable[hd]:
                nom = optr[hd + 1] - optr[hd]
                if nom > 0:
                    nc = _wait_close(new, nn, odat[optr[hd]:optr[hd + 1]], nom, c, c2, t1, t2, t3, t4)
                    if nc >= lim:
                        return 1, pushes, pops, relax
                    n3, clo2, _y = _raise(new, nn, c, nc, t1)
                    if clo2 < clo:
                        clo = clo2
                    nn = _copy(c, nc, new)
            if nn > CAP:
                return 1, pushes, pops, relax
            row = mu[s]
            for i in range(nn):
                row[i, 0] = new[i, 0]
                row[i, 1] = new[i, 1]
                row[i, 2] = new[i, 2]
                row[i, 3] = new[i, 3]
            cnt[s] = nn
            if dirty[s]:
                if clo < dlo[s]:
                    dlo[s] = clo
                if chi > dhi[s]:
                    dhi[s] = chi
            else:
                dirty[s] = 1
                dlo[s] = clo
                dhi[s] = chi
            if hn >= hcap:
                return 2, pushes, pops, relax
            hn = _hpush(hk, hv, hn, dhi[s], s)
            pushes += 1
    return 0, pushes, pops, relax


# ----------------------------------------------------------------------------------------------------- Python wrapper
def graph_arrays(inst):
    """The part of the packing that depends only on the graph (shared by every widening of an instance)."""
    E = len(inst.tail)
    inc, tail, forb = inst.inc, inst.tail, inst.forbidden
    if forb:
        pred = [[i for i in inc[tail[j]] if (i, j) not in forb] for j in range(E)]
    else:
        pred = [inc[tail[j]] for j in range(E)]
    pptr = np.zeros(E + 1, np.int64)
    pptr[1:] = np.cumsum(np.fromiter((len(p) for p in pred), np.int64, E))
    pidx = np.fromiter((i for p in pred for i in p), np.int64, int(pptr[-1]))
    return {"D": np.asarray(inst.D, np.int64), "head": np.asarray(inst.head, np.int64),
            "waitable": np.asarray(inst.waitable, np.uint8), "pptr": pptr, "pidx": pidx}


def _pack(n, items):
    """items: {index: piece list} -> (ptr[n + 1], data[k, 4]). An index mapped to [] gets the marker ptr step 0."""
    ptr = np.zeros(n + 1, np.int64)
    rows = []
    for i in sorted(items):
        ptr[i + 1] = len(items[i])
        rows.extend(items[i])
    np.cumsum(ptr, out=ptr)
    dat = np.asarray(rows, np.int64).reshape(-1, 4) if rows else np.zeros((1, 4), np.int64)
    return ptr, dat


def margin_field_nb(inst, M, *, erode_accept=False, graph=None, cap=16) -> MarginField:
    """Same result as ``field.margin_field``. ``graph`` = ``graph_arrays(inst)`` may be passed to share it."""
    E, H, D = len(inst.tail), inst.H, inst.D
    gr = graph or graph_arrays(inst)
    B, W, waitable = inst.B, inst.W, inst.waitable
    # edges with a closure get their tent; an edge closed at every start second gets a one-row sentinel that is BOTTOM
    bt = {}
    for j in range(E):
        if B[j]:
            t = pl.tent(B[j], 0, H - D[j], M)
            bt[j] = t if t else [(-(1 << 40), -(1 << 40), 0, 0)]   # far below every shifted function
    bptr, bdat = _pack(E, bt)
    alpha_l = {j: _accept_level(a, M, erode_accept) for j, a in enumerate(inst.A) if a}
    aptr, adat = _pack(E, {j: f for j, f in alpha_l.items() if f})
    om = {}
    for v in range(inst.n_nodes):
        if waitable[v]:
            om[v] = pl.tent(W[v], 0, H - 1, M)
    optr, odat = _pack(inst.n_nodes, {v: f for v, f in om.items() if f})
    while True:
        mu = np.zeros((E, cap, 4), np.int64)
        cnt = np.zeros(E, np.int64)
        status, pushes, pops, relax = _pass(E, H, M, gr["D"], gr["head"], gr["waitable"], gr["pptr"], gr["pidx"],
                                            bptr, bdat, aptr, adat, optr, odat, mu, cnt)
        if status == 1 and cap < 256:
            cap *= 4
            continue
        break
    if status != 0:
        fld = _py_margin_field(inst, M, erode_accept=erode_accept)
        fld.stats["fallback"] = int(status)
        return fld
    alpha = [alpha_l.get(j, []) for j in range(E)] if E <= 4096 else _Lazy(lambda j: alpha_l.get(j, []), E)
    mu_l = _Lazy(lambda s: [tuple(r) for r in mu[s, :cnt[s]].tolist()], E)
    gamma = _Lazy(lambda j: pl.pmax(alpha_l[j], mu_l[j]) if alpha_l.get(j) else mu_l[j], E)
    beta = _Lazy(lambda j: pl.tent(B[j], 0, H - D[j], M), E)
    omega = _Lazy(lambda v: pl.tent(W[v], 0, H - 1, M) if waitable[v] else [], inst.n_nodes)
    fld = MarginField(inst, M, erode_accept, mu_l, gamma, beta, alpha, omega,
                      {"pushes": int(pushes), "pops": int(pops), "relaxations": int(relax), "pieces": int(cnt.sum()),
                       "max_pieces": int(cnt.max()) if E else 0, "compiled": HAVE_NUMBA, "cap": cap})
    fld.arrays = (mu, cnt)
    return fld


@njit(cache=True)
def _levels(mu, cnt, m, out, ocnt):
    """{t : mu_s(t) >= m} for every state, as rows [lo, hi] (the compiled form of ``pl.level_set``)."""
    for s in range(mu.shape[0]):
        n = 0
        for i in range(cnt[s]):
            lo = mu[s, i, 0]
            hi = mu[s, i, 1]
            v = mu[s, i, 2]
            sl = mu[s, i, 3]
            if sl == 0:
                if v < m:
                    continue
                a = lo
                b = hi
            elif sl > 0:
                a = lo + m - v if lo + m - v > lo else lo
                b = hi
            else:
                a = lo
                b = lo + v - m if lo + v - m < hi else hi
            if a > b:
                continue
            if n > 0 and out[s, n - 1, 1] + 1 >= a:
                out[s, n - 1, 1] = b
            else:
                out[s, n, 0] = a
                out[s, n, 1] = b
                n += 1
        ocnt[s] = n


def level_arrays(fld, m):
    """R of every edge state at margin m from a compiled field: (intervals[E, cap, 2], count[E])."""
    mu, cnt = fld.arrays
    out = np.zeros((mu.shape[0], mu.shape[1], 2), np.int64)
    ocnt = np.zeros(mu.shape[0], np.int64)
    _levels(mu, cnt, m, out, ocnt)
    return out, ocnt
