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
