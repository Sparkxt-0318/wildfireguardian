"""Export a backward field as ``wfg.f31.field/1`` (shared format proposed to F-3.2): sorted closed integer intervals,
only non-empty entries. Certificate semantics: for every edge state s and second t not in R[s], every allowed
successor edge j has t in B[j] or t + D[j] not in G[j] = R[j] u A[j], and a wait (waitable head) has t in W[head] or
t + 1 not in R[s]; ``core.check_fixed_point`` verifies exactly this (and the converse) in one linear pass."""
from __future__ import annotations


def export_field(pm, fld, variant: str, destination: dict, origins=(), hashes=None) -> dict:
    from .core import issue_core
    from . import intervals as iv
    inst = fld.inst
    eid, nid = pm.g.edge_ids, pm.node_ids
    nz = lambda L: {k: [list(p) for p in v] for k, v in L if v}
    out = {
        "schema": "wfg.f31.field/1", "variant": variant, "H": inst.H, "destination": destination,
        "hashes": hashes or {},
        "R": nz((eid[j], fld.R[j]) for j in range(len(eid))),
        "A": nz((eid[j], inst.A[j]) for j in range(len(eid))),
        "B": nz((eid[j], inst.B[j]) for j in range(len(eid))),
        "W": nz((nid[v], inst.W[v]) for v in range(len(nid))),
        "issue": {},
    }
    for o in origins:
        oi = pm.nidx[o]
        core = issue_core(fld, oi)
        blocked = inst.IB.get(oi, [])
        out["issue"][o] = {"core": [list(p) for p in core], "blocked": [list(p) for p in blocked],
                           "feasible": [list(p) for p in iv.subtract_all(core, iv.normalize(blocked))]}
    return out
