"""Static-snapshot baselines S1/S2 and the no-re-entry hazard reading, on the O2 integer instance (F-BASE).

S1 "block only what is burning at departure": edge j fully blocked iff dep in EB_j, else never blocked; waiting at
node n forbidden iff dep in WB_n, else always allowed.
S2 "block everything that burns at any time in the horizon": edge j fully blocked iff EB_j meets [dep, H]; waiting at
n forbidden iff WB_n meets [dep, H].
Both are solved EXACTLY on the static instance (same states, forbidden turns, durations, waitable set and acceptance
windows; only EB/WB replaced) by fbase.solve_exact, so the only thing changed is the hazard reading. An S1 route is
then replayed on the TRUE instance with fbase.replay.

no_reentry(inst): every edge block and wait block is closed to the horizon: EB_j := [min EB_j, H] (if any),
WB_n := [min WB_n, H] (if any). The O2 blocks as built (ContactModel flame intervals) are the reopening reading.
"""
from __future__ import annotations

import copy

from fbase import Instance, solve_exact


def _meets(ivs, lo, hi):
    return any(a <= hi and b >= lo for a, b in ivs)


def _contains(ivs, t):
    return any(a <= t <= b for a, b in ivs)


def no_reentry(inst: Instance) -> Instance:
    i = copy.deepcopy(inst)
    i.EB = {j: [(min(a for a, _ in v), i.H)] for j, v in i.EB.items() if v}
    i.WB = {n: [(min(a for a, _ in v), i.H)] for n, v in i.WB.items() if v}
    return i


def static_instance(inst: Instance, mode: str) -> Instance:
    if mode not in ("S1", "S2"):
        raise ValueError(mode)
    i = copy.deepcopy(inst)
    full = [(0, i.H)]
    if mode == "S1":
        hit_e = lambda v: _contains(v, inst.dep)  # noqa: E731
    else:
        hit_e = lambda v: _meets(v, inst.dep, inst.H)  # noqa: E731
    i.EB = {j: full for j, v in inst.EB.items() if v and hit_e(v)}
    i.WB = {n: full for n, v in inst.WB.items() if v and hit_e(v)}
    return i


def solve_static(inst: Instance, mode: str):
    """(claim, T, witness) on the static instance."""
    return solve_exact(static_instance(inst, mode))


def snapshot(inst: Instance, s: int, t: int) -> Instance:
    """S1 snapshot taken at second t, planning from state s at time t (rule (e) step 1)."""
    i = copy.deepcopy(inst)
    i.s0, i.dep = s, t
    full = [(0, i.H)]
    i.EB = {j: full for j, v in inst.EB.items() if v and _contains(v, t)}
    i.WB = {n: full for n, v in inst.WB.items() if v and _contains(v, t)}
    return i


def solve_s3(inst: Instance, delta: int, max_replans: int = 10000):
    """S3(delta) per DESIGN.md (e). Returns (outcome, T, executed_legs, n_plans); outcome in
    ROUTE / VIOLATION / REFUSED / UNRESOLVED. Legality is checked against `inst` (the time-dependent model)."""
    s, t = inst.s0, inst.dep
    if inst.hd(s) in inst.AC and _contains(inst.AC[inst.hd(s)], t):
        return "ROUTE", t, [], 0
    executed, plans = [], 0
    next_replan = t
    while plans < max_replans:
        claim, _, legs = solve_exact(snapshot(inst, s, t))
        plans += 1
        if claim != "ROUTE":
            return "REFUSED", None, executed, plans
        next_replan = t + delta
        replanned = False
        for kind, x, a, b in legs:
            if a != t:
                return "UNRESOLVED", None, executed, plans  # plan not contiguous with the vehicle (should not happen)
            if kind == "E":
                if inst.tail[x] != inst.hd(s) or (s, x) in inst.forbid or b != a + inst.D[x] or b > inst.H:
                    return "UNRESOLVED", None, executed, plans
                if _contains(inst.EB.get(x, []), a):
                    executed.append((kind, x, a, b))
                    return "VIOLATION", None, executed, plans
                executed.append((kind, x, a, b))
                s, t = x, b
                if inst.head[x] in inst.AC and _contains(inst.AC[inst.head[x]], t):
                    return "ROUTE", t, executed, plans
                if t >= next_replan:
                    replanned = True
                    break
            else:
                n = x
                if n != inst.hd(s) or n not in inst.waitable or b != a + 1 or b > inst.H:
                    return "UNRESOLVED", None, executed, plans
                if _contains(inst.WB.get(n, []), a):
                    executed.append((kind, x, a, b))
                    return "VIOLATION", None, executed, plans
                executed.append((kind, x, a, b))
                t = b
        if not replanned:
            return "UNRESOLVED", None, executed, plans  # plan ended without reaching an admitted goal
    return "UNRESOLVED", None, executed, plans
