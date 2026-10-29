"""Brute-force time-expanded reference for an abstract SIPP instance: second-by-second reachability over
(state, second, admission), exactly the lattice of zsweep.contact_sweep, with no intervals and no dominance."""
from __future__ import annotations

from .intervals import contains


def earliest_arrival(inst):
    """Earliest accepted second, or None if no admissible journey exists."""
    E, dep, hor = inst.E, inst.departure, inst.horizon
    succ = inst.successors()
    arrive = {dep: {inst.start_state}}       # admission arrivals by second
    wait = {}                                # wait arrivals by second
    for t in range(dep, hor + 1):
        A = arrive.pop(t, set())
        Wt = wait.pop(t, set())
        for s in sorted(A):
            if contains(inst.accept.get(inst.state_head(s), []), t):
                return t
        for s in A | Wt:
            for j in succ[s]:
                end = t + inst.D[j]
                if end <= hor and not contains(inst.edge_block.get(j, []), t):
                    arrive.setdefault(end, set()).add(j)
            node = inst.state_head(s)
            if inst.waitable[node] and t + 1 <= hor and not contains(inst.wait_block.get(node, []), t):
                wait.setdefault(t + 1, set()).add(s)
        if not arrive and not wait:
            break
    return None


def check_legs(inst, legs, arrival):
    """True iff abstract legs form a legal lattice journey from the issue state ending in acceptance at `arrival`."""
    s, t, admission = inst.start_state, inst.departure, True
    for kind, ident, a, b in legs:
        if a != t:
            return False
        if kind == "WAIT":
            node = inst.state_head(s)
            if ident != node or b != a + 1 or not inst.waitable[node] or contains(inst.wait_block.get(node, []), a) or b > inst.horizon:
                return False
            admission = False
        else:
            j = ident
            if j not in inst.successors()[s] or b != a + inst.D[j] or b > inst.horizon or contains(inst.edge_block.get(j, []), a):
                return False
            s, admission = j, True
        t = b
    return t == arrival and admission and contains(inst.accept.get(inst.state_head(s), []), t)
