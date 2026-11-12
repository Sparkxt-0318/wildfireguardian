"""Unknown-support instances (Iris's definition, adopted by the orchestrator for all routing streams).

From the packet's own native masks (constructed_arrays.npz, identical for all members):
  U_state = mask__unknown_cumulative_state
  U_q     = mask__policy_assigned_zero AND NOT mask__known_burned AND NOT U_state
  UNKNOWN = U_state OR U_q
Optimistic instance = the frozen packet exactly. Pessimistic instances add a pseudo-phase [start, beyond H) on the
unknown cells under both contact rules:
  tier A       : every UNKNOWN cell from 0;
  tier B (v)   : U_state from 0; a U_q cell at centre distance d from S0 = present fire OR U_state OR positive native
                 probability, from ceil(d / v); not blocked when d / v > H. Conditional on the speed v.
  tier R (v)   : reconstruction-consistent (Iris, update): U_state is not present fire; U_state and U_q cells at
                 centre distance d from S0R = present fire OR positive native probability are blocked from ceil(d / v).
                 Premise: the arrival reconstruction's no-data cells did not burn (to be supported by the share outside
                 the final footprint and FIRMS/AHI detections; detected cells are NOT yet blocked from 0 here).
Three-way label per request: checked = feasible in the pessimistic instance; no-route = infeasible in the optimistic
instance; otherwise unresolved.
"""
from __future__ import annotations

import math

import numpy as np


def masks(packet):
    """Router-cell index sets from the npz (north-up native rows mapped as the packet reader does)."""
    with np.load(packet.dir / "constructed_arrays.npz", allow_pickle=False) as z:
        us = np.array(z["mask__unknown_cumulative_state"], bool)
        pz = np.array(z["mask__policy_assigned_zero"], bool)
        kb = np.array(z["mask__known_burned"], bool)
        pos = np.array(z["mask__positive_native_probability"], bool)
        cur = np.array(z["current_active"], bool)
    uq = pz & ~kb & ~us
    to_r = lambda m: {packet.native_to_router(int(i)) for i in np.flatnonzero(m.ravel())}
    return {"U_state": to_r(us), "U_q": to_r(uq), "S0": to_r(cur | us | pos), "S0R": to_r(cur | pos)}


def extra_blocks(packet, grid, H: int, tier: str, v_kmh: float | None = None) -> dict:
    m = masks(packet)
    if tier == "A":
        return {c: 0 for c in m["U_state"] | m["U_q"]}
    if tier not in ("B", "R") or not v_kmh:
        raise ValueError("tier A, or tier B/R with a speed")
    v = v_kmh * 1000.0 / 3600.0                     # m/s
    if tier == "B":
        S0, out, targets = sorted(m["S0"]), {c: 0 for c in m["U_state"]}, m["U_q"]
    else:  # R: reconstruction-consistent; U_state is not present fire, both unknown kinds are speed-bounded from S0R
        S0, out, targets = sorted(m["S0R"]), {}, m["U_q"] | m["U_state"]
    if not S0:
        return out
    cs = np.array([[float(x) for x in grid.centre(c)] for c in S0])
    for c in targets:
        x, y = (float(t) for t in grid.centre(c))
        d = float(np.sqrt(((cs - (x, y)) ** 2).sum(1)).min())
        st = math.ceil(d / v)
        if st <= H:
            out[c] = min(out.get(c, st), st)
    return out


def summary(packet) -> dict:
    m = masks(packet)
    return {k: len(v) for k, v in m.items()}
