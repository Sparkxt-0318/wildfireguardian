"""Solver side: build the contact-relaxation instance, solve it with SIPP, and emit a .wfgc certificate bundle.

The certificate is the exact forward-reachable lattice set truncated below the threshold T (T = SIPP arrival for a
route, H + 1 for a no-route claim). See CERTIFICATE_SPEC.md and FORMAT.md.
"""
from __future__ import annotations

import hashlib
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for _n in ("sipp-routing", "scenario-members", "synthetic-truth"):
    _p = str(ROOT / "experimental" / _n / "src")
    if _p not in sys.path:
        sys.path.insert(0, _p)

from wfg_sipp import sipp as S  # noqa: E402
from wfg_sipp.intervals import complement, normalise, next_member, clip  # noqa: E402


# ---------------------------------------------------------------- interval-set helpers (sets as normalised lists)
def union(a, b):
    return normalise(list(a) + list(b))


def minus(a, b):
    out = []
    for lo, hi in a:
        out.extend(complement(b, lo, hi))
    return out


# ---------------------------------------------------------------- reachability
def reachable(inst, T):
    """Exact reachable sets R[s] (all) and A[s] (admitted) restricted to times <= min(H, T-1)."""
    H, dep, E = inst.horizon, inst.departure, inst.E
    lim = min(H, T - 1)
    succ = inst.successors()
    R, A = {}, {}
    queue, queued = deque(), set()
    pending = {}

    def add(s, ivs, admitted):
        ivs = clip(normalise(ivs), dep, lim)
        if not ivs:
            return
        if admitted:
            A[s] = union(A.get(s, []), ivs)
        new = minus(ivs, R.get(s, []))
        if not new:
            return
        node = inst.state_head(s)
        if inst.waitable[node]:
            wb = inst.wait_block.get(node, [])
            ext = []
            for lo, hi in new:
                x = next_member(wb, hi)
                end = lim if x is None else min(x, lim)
                ext.append((lo, max(hi, end)))
            new = minus(normalise(ext), R.get(s, []))
        R[s] = union(R.get(s, []), new)
        pending[s] = union(pending.get(s, []), new)
        if s not in queued:
            queued.add(s)
            queue.append(s)

    if dep <= lim:
        add(inst.start_state, [(dep, dep)], True)
    while queue:
        s = queue.popleft()
        queued.discard(s)
        delta = pending.pop(s)
        for j in succ[s]:
            Dj = inst.D[j]
            eb = inst.edge_block.get(j, [])
            arr = []
            for lo, hi in delta:
                top = min(hi, lim - Dj)
                if top >= lo:
                    arr.extend((x + Dj, y + Dj) for x, y in complement(eb, lo, top))
            if arr:
                add(j, arr, True)
    return R, A


# ---------------------------------------------------------------- serialisation
def _ivl(ivs):
    return " ".join([str(len(ivs))] + ["%d %d" % (a, b) for a, b in ivs])


def instance_text(inst):
    lines = ["INSTANCE", "V %d E %d" % (inst.n_nodes, inst.E),
             "DEP %d HOR %d ORIGIN %d START %d" % (inst.departure, inst.horizon, inst.origin, inst.start_state), "EDGES"]
    lines += ["%d %d %d" % (inst.tail[j], inst.head[j], inst.D[j]) for j in range(inst.E)]
    w = [n for n in range(inst.n_nodes) if inst.waitable[n]]
    lines.append("WAITABLE %d" % len(w))
    lines += [" ".join(map(str, w[i:i + 20])) for i in range(0, len(w), 20)]
    fb = sorted(inst.forbidden)
    lines.append("FORBID %d" % len(fb))
    lines += ["%d %d" % p for p in fb]
    for key, table in (("EB", inst.edge_block), ("WB", inst.wait_block), ("AC", inst.accept)):
        rows = [(k, normalise(v)) for k, v in sorted(table.items()) if v]
        lines.append("%s %d" % (key, len(rows)))
        lines += ["%d %s" % (k, _ivl(v)) for k, v in rows]
    lines.append("END_INSTANCE")
    return "\n".join(lines) + "\n"


def certificate_bundle(inst, *, claim, T, legs, R, A):
    inst_txt = instance_text(inst)
    out = ["WFGC 1", inst_txt.rstrip("\n")]
    out.append("CLAIM ROUTE %d" % T if claim == "ROUTE" else "CLAIM NO_ROUTE")
    out.append("WITNESS %d" % len(legs))
    for kind, ident, a, b in legs:
        out.append("%s %d %d %d" % ("E" if kind == "EDGE" else "W", ident, a, b))
    states = sorted(set(R) | set(A))
    out.append("CERT %d %d" % (T, len(states)))
    for s in states:
        out.append("%d %s %s" % (s, _ivl(R.get(s, [])), _ivl(A.get(s, []))))
    out.append("END")
    text = "\n".join(out) + "\n"
    return text, hashlib.sha256(inst_txt.encode()).hexdigest()


def certify(inst, *, deadline=None):
    """Solve with SIPP and emit (claim, T, bundle_text, instance_sha256, stats). Raises on unresolved search."""
    res = S.solve(inst, deadline=deadline)
    if res["status"] == "FOUND":
        claim, T, legs = "ROUTE", res["arrival"], res["legs"]
    elif res["status"] == "EXHAUSTED":
        claim, T, legs = "NO_ROUTE", inst.horizon + 1, []
    else:
        raise RuntimeError("UNRESOLVED:" + res["status"])
    R, A = reachable(inst, T)
    text, ih = certificate_bundle(inst, claim=claim, T=T, legs=legs, R=R, A=A)
    stats = dict(states=len(R), r_intervals=sum(len(v) for v in R.values()),
                 a_intervals=sum(len(v) for v in A.values()), sipp_metrics=res["metrics"])
    return claim, T, text, ih, stats


# ---------------------------------------------------------------- backward (co-reachable) certificate, COCERT form
def prev_member(ivs, t):
    """Largest x <= t in the normalised set, or None."""
    best = None
    for a, b in ivs:
        if a > t:
            break
        best = min(b, t)
    return best


def coreachable(inst, T):
    """Gr[s]: seconds t <= lim at which a NON-admitted point (s,t,0) can still reach a goal with arrival < T.
    Ga[s] = Gr[s] ∪ (AC_hd(s) ∩ [dep, lim]) for admitted points. Exact least fixed point, computed backward."""
    H, dep, E = inst.horizon, inst.departure, inst.E
    lim = min(H, T - 1)
    succ = inst.successors()
    preds = [[] for _ in range(E + 1)]
    for s in range(E + 1):
        for j in succ[s]:
            preds[j].append(s)
    Gr, Ga = {}, {}
    queue, pending = deque(), {}

    def grow_ga(s, ivs):
        new = minus(clip(normalise(ivs), dep, lim), Ga.get(s, []))
        if new:
            Ga[s] = union(Ga.get(s, []), new)
            if s not in pending:
                queue.append(s)
            pending[s] = union(pending.get(s, []), new)

    def grow_gr(s, ivs):
        ivs = clip(normalise(ivs), dep, lim)
        new = minus(ivs, Gr.get(s, []))
        if not new:
            return
        node = inst.state_head(s)
        if inst.waitable[node]:
            wb = inst.wait_block.get(node, [])
            ext = []
            for lo, hi in new:      # t reaches t+1 by waiting iff t not in WB: extend each run downward
                x = prev_member(wb, lo - 1)
                ext.append((dep if x is None else max(dep, x + 1), hi))
            new = minus(normalise(ext), Gr.get(s, []))
        Gr[s] = union(Gr.get(s, []), new)
        grow_ga(s, new)

    for n, ac in inst.accept.items():
        for s in range(E + 1):
            if inst.state_head(s) == n:
                grow_ga(s, ac)
    while queue:
        j = queue.popleft()
        delta = pending.pop(j)
        Dj = inst.D[j]
        eb = inst.edge_block.get(j, [])
        dep_times = []
        for lo, hi in delta:
            a, b = max(dep, lo - Dj), hi - Dj
            if a <= b:
                dep_times.extend(complement(eb, a, b))
        if dep_times:
            for s in preds[j]:
                grow_gr(s, dep_times)
    return Gr, Ga


def cocert_bundle(inst, *, claim, T, legs):
    """Bundle whose certificate lists, per state, the complements NR_s = Gr_s and NA_s = Ga_s (FORMAT.md, COCERT)."""
    Gr, Ga = coreachable(inst, T)
    text, ih = certificate_bundle(inst, claim=claim, T=T, legs=legs, R={}, A={})
    head = text[:text.index("CERT ")]
    states = sorted(set(Gr) | set(Ga))
    out = [head.rstrip("\n"), "COCERT %d %d" % (T, len(states))]
    out += ["%d %s %s" % (s, _ivl(Gr.get(s, [])), _ivl(Ga.get(s, []))) for s in states]
    out.append("END")
    return "\n".join(out) + "\n", ih, dict(co_states=len(states), co_intervals=sum(len(v) for v in Ga.values()))
