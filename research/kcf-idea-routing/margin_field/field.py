"""One-pass margin field (METHOD.md).

For an F-3.1 ``Instance`` and a largest margin M, ``margin_field`` returns for every edge state s the function

    mu_s(t) = max{ m in 0..M : t in R_s of the instance whose closures are widened by m seconds on both sides }

(BOTTOM = -1 where t is not in R_s at margin 0). ``{t : mu_s(t) >= m}`` is exactly the F-3.1 field of the m-widened
instance, for every m in 0..M at once (Theorem 1 of METHOD.md). The existing code in
``research/harness-2026-11/F-3.1/deadline_field`` is imported read-only (``Instance`` and ``intervals``) and is not
changed.
"""
from __future__ import annotations

import heapq
import sys
from dataclasses import dataclass
from pathlib import Path

from . import pl

_F31 = Path(__file__).resolve().parents[2] / "harness-2026-11" / "F-3.1"
if str(_F31) not in sys.path:
    sys.path.insert(0, str(_F31))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import Field, Instance  # noqa: E402


# --------------------------------------------------------------------------------------------------- the margin family
def widen(inst: Instance, m: int, *, erode_accept: bool = False) -> Instance:
    """The m-widened instance I(m): every closure set B_j, W_v, IB_o becomes {t : dist(t, set) <= m}. With
    ``erode_accept`` every acceptance set A_j, AN_o loses the m seconds next to each of its ends. I(0) = inst."""
    def dil(ivs):
        return iv.normalize([(lo - m, hi + m) for lo, hi in ivs])

    def ero(ivs):
        return [(lo + m, hi - m) for lo, hi in ivs if lo + m <= hi - m] if erode_accept else list(ivs)

    return Instance(H=inst.H, n_nodes=inst.n_nodes, tail=list(inst.tail), head=list(inst.head), D=list(inst.D),
                    waitable=list(inst.waitable), forbidden=set(inst.forbidden),
                    B=[dil(b) for b in inst.B], W=[dil(w) for w in inst.W], A=[ero(a) for a in inst.A],
                    IB={o: dil(iv.normalize(x)) for o, x in inst.IB.items()},
                    AN={o: ero(x) for o, x in inst.AN.items()})


def _accept_level(ivs, M, erode_accept):
    """Largest margin at which an acceptance set still holds t: M on the set, or its eroded tent."""
    if not erode_accept:
        return [(lo, hi, M, 0) for lo, hi in ivs]
    out = []
    for lo, hi in ivs:                                     # complement is closed on both sides of each interval
        f = pl.pmin(pl.pmin(pl.const(lo, hi, M), [(lo, hi, 0, 1)]), [(lo, hi, hi - lo, -1)])
        out.extend(f)
    return out


# ------------------------------------------------------------------------------------------------------ waiting closure
def wait_close(mu, omega):
    """Least c >= mu with c(t) >= min(omega(t), c(t + 1)): the (max, min) closure under waiting.
    c(t) = max over u >= t of min(mu(u), min of omega over [t, u - 1]). Exact, piece by piece of omega, from the
    right (METHOD.md Lemma 3.3)."""
    if not mu or not omega:
        return mu
    c = mu
    carry = pl.BOTTOM                                      # c(y + 1) when the next omega piece to the right is adjacent
    nxt_lo = None
    for x, y, v, s in reversed(omega):
        if nxt_lo is None or y + 1 != nxt_lo:
            carry = pl.value(c, y + 1)                     # wait at y leads to y + 1, where c = mu so far
        wy = v + s * (y - x)
        k = carry if carry < wy else wy
        seg_w = [(x, y, v, s)]
        base = []
        if y > x:
            q = pl.pmin(pl.restrict(mu, x + 1, y), [(x + 1, y, v, s)])       # min(mu(u), omega(u - 1))
            if q:
                base = pl.shift(pl.suffix_max(q, x + 1), -1)                   # Q(t + 1) for t in [x, y - 1]
        if k >= 0:
            base = pl.pmax(base, pl.const(x, y, k))
        if base:
            add = pl.pmin(seg_w, base)
            if add:
                c = pl.pmax(c, add)
        carry = pl.value(c, x)
        nxt_lo = x
    return c


# ------------------------------------------------------------------------------------------------------------ the pass
@dataclass
class MarginField:
    inst: Instance
    M: int
    erode_accept: bool
    mu: list          # per edge state: margin function of R
    gamma: list       # per edge state: max(alpha, mu), margin function of G
    beta: list        # per edge: margin at which the edge is open at start second t, t in [0, H - D]
    alpha: list       # per edge: margin at which arrival over the edge is accepted
    omega: list       # per node: margin at which a 1-second wait is open (waitable nodes only)
    stats: dict


def margin_field(inst: Instance, M: int, *, erode_accept: bool = False) -> MarginField:
    E, H = len(inst.tail), inst.H
    D = inst.D
    beta = [pl.tent(inst.B[j], 0, H - D[j], M) for j in range(E)]
    alpha = [_accept_level(inst.A[j], M, erode_accept) for j in range(E)]
    omega = [pl.tent(inst.W[v], 0, H - 1, M) if inst.waitable[v] else [] for v in range(inst.n_nodes)]
    pred = [[i for i in inst.inc[inst.tail[j]] if (i, j) not in inst.forbidden] for j in range(E)]
    mu = [[] for _ in range(E)]
    dirty = {}
    heap = []
    pushes = pops = relax = 0
    for j in range(E):
        if alpha[j]:
            dirty[j] = (alpha[j][0][0], alpha[j][-1][1])
            heap.append((-alpha[j][-1][1], j))
            pushes += 1
    heapq.heapify(heap)
    head, waitable = inst.head, inst.waitable
    while heap:
        _, j = heapq.heappop(heap)
        d = dirty.pop(j, None)
        if d is None:
            continue
        pops += 1
        a, b = d
        g = pl.restrict(mu[j], a, b)
        if alpha[j]:
            g = pl.pmax(pl.restrict(alpha[j], a, b), g)
        dj = D[j]
        cand = pl.pmin(beta[j], pl.shift(g, -dj))
        if not cand:
            continue
        for s in pred[j]:
            relax += 1
            new, clo, chi = pl.raise_to(mu[s], cand)
            if clo is None:
                continue
            hv = head[s]
            if waitable[hv] and omega[hv]:
                closed = wait_close(new, omega[hv])
                if closed is not new:
                    _, c2, _ = pl.raise_to(new, closed)
                    if c2 is not None and c2 < clo:
                        clo = c2
                    new = closed
            mu[s] = new
            old = dirty.get(s)
            if old is not None:
                clo = min(clo, old[0])
                chi = max(chi, old[1])
            dirty[s] = (clo, chi)
            heapq.heappush(heap, (-chi, s))
            pushes += 1
    gamma = [pl.pmax(alpha[j], mu[j]) if alpha[j] else mu[j] for j in range(E)]
    return MarginField(inst, M, erode_accept, mu, gamma, beta, alpha, omega,
                       {"pushes": pushes, "pops": pops, "relaxations": relax,
                        "pieces": sum(len(f) for f in mu), "max_pieces": max((len(f) for f in mu), default=0)})


# ------------------------------------------------------------------------------------------------------------- read-off
def issue_margin(fld: MarginField, o: int):
    """Margin function of origin o: issue_margin(t) >= m  iff  t is a feasible departure of o in I(m)."""
    inst, M = fld.inst, fld.M
    X = []
    for j in inst.out[o]:
        X = pl.pmax(X, pl.pmin(fld.beta[j], pl.shift(fld.gamma[j], -inst.D[j])))
    if inst.waitable[o]:
        X = wait_close(X, fld.omega[o])
    an = inst.AN.get(o)
    if an:
        X = pl.pmax(X, _accept_level(an, M, fld.erode_accept))
    ib = iv.normalize(inst.IB.get(o, []))
    return pl.pmin(X, pl.tent(ib, 0, inst.H, M)) if ib else X


def issue_set_at(fld: MarginField, o: int, m: int):
    """Feasible departure seconds of origin o at margin m (interval list, as ``core.issue_set`` on I(m))."""
    return pl.level_set(issue_margin(fld, o), m)


def leave_by(fld: MarginField, o: int):
    """[(m, end of the first window if it starts at 0 else None)] for every m at which the answer changes."""
    f = issue_margin(fld, o)
    out, last = [], object()
    for m in range(fld.M + 1):
        s = pl.level_set(f, m)
        x = s[0][1] if s and s[0][0] == 0 else None
        if x != last:
            out.append((m, x))
            last = x
    return out


def field_at(fld: MarginField, m: int) -> Field:
    """The ordinary F-3.1 ``Field`` of the m-widened instance, read off the margin field (no new pass). The unchanged
    ``core.issue_set`` / ``core.witness`` then work on it."""
    R = [pl.level_set(f, m) for f in fld.mu]
    G = [pl.level_set(f, m) for f in fld.gamma]
    return Field(widen(fld.inst, m, erode_accept=fld.erode_accept), R, G, {"from_margin_field": m})


def check_fixed_point(fld: MarginField):
    """Certificate independent of the solving order: for every edge state, mu_s must EQUAL the right-hand side of
    equation (E_mu) evaluated on the stored functions. By METHOD.md Lemma 2.2 the equation has one solution, so
    equality proves the stored field is the margin field of the instance. Returns the number of states checked."""
    inst = fld.inst
    for s in range(len(inst.tail)):
        hv = inst.head[s]
        rhs = []
        for j in inst.out[hv]:
            if (s, j) in inst.forbidden:
                continue
            rhs = pl.pmax(rhs, pl.pmin(fld.beta[j], pl.shift(fld.gamma[j], -inst.D[j])))
        if inst.waitable[hv]:
            rhs = pl.pmax(rhs, pl.pmin(fld.omega[hv], pl.shift(fld.mu[s], -1)))
        if pl.canon(rhs) != pl.canon(fld.mu[s]):
            raise AssertionError("margin fixed point violated at state %d" % s)
        want = pl.pmax(fld.alpha[s], fld.mu[s]) if fld.alpha[s] else fld.mu[s]
        if pl.canon(want) != pl.canon(fld.gamma[s]):
            raise AssertionError("gamma != max(alpha, mu) at state %d" % s)
    return len(inst.tail)
