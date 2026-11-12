"""Export a backward field as Thomas's ``wfg.cert/1`` (direction "backward") plus the canonical integer instance.

Semantics (exact, not a superset): for edge state s, ``R`` = seconds from which an accepted completion exists while
standing at head(s) with admission false; ``A`` = accepted admitted-arrival seconds over s. ``issue:<node>`` holds the
origin's completion seconds (``R``, before the issue-point check) and the issue-point blocked seconds (``blocked``).
Closure check (both directions; ``core.check_fixed_point``): for every s,
R_s = U_{allowed j} {t : t not in B_j, t + D_j in R_j u A_j}  u  {t : head waitable, t not in W_head, t + 1 in R_s}.
Departure t from origin o is infeasible iff t in blocked(o) or t not in R_issue(o).
Canonical hash: sha256 of json.dumps(instance, sort_keys=True, separators=(",", ":")).
"""
from __future__ import annotations

import hashlib
import json

from . import intervals as iv
from .core import issue_core


def canonical_instance(inst) -> dict:
    E = len(inst.tail)
    return {"format": "wfg.f31.instance/1", "H": inst.H, "n_nodes": inst.n_nodes,
            "tail": list(inst.tail), "head": list(inst.head), "D": list(inst.D),
            "waitable": [bool(w) for w in inst.waitable],
            "forbidden": sorted([int(a), int(b)] for a, b in inst.forbidden),
            "B": {str(j): [list(p) for p in inst.B[j]] for j in range(E) if inst.B[j]},
            "W": {str(v): [list(p) for p in inst.W[v]] for v in range(inst.n_nodes) if inst.W[v]},
            "A": {str(j): [list(p) for p in inst.A[j]] for j in range(E) if inst.A[j]},
            "IB": {str(o): [list(p) for p in iv.normalize(x)] for o, x in sorted(inst.IB.items())}}


def instance_sha256(ci: dict) -> str:
    return hashlib.sha256(json.dumps(ci, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def export_cert(fld, origins=(), *, threshold=None, labels=None) -> tuple:
    """Returns (certificate, canonical_instance). ``origins`` are node indices; ``labels`` optional id maps
    {"edges": [...], "nodes": [...]} recorded alongside (indices remain the keys)."""
    inst = fld.inst
    ci = canonical_instance(inst)
    states = {}
    for s in range(len(inst.tail)):
        if fld.R[s] or inst.A[s]:
            states[str(s)] = {"R": [list(p) for p in fld.R[s]], "A": [list(p) for p in inst.A[s]]}
    for o in origins:
        states["issue:%d" % o] = {"R": [list(p) for p in issue_core(fld, o)],
                                  "blocked": [list(p) for p in iv.normalize(inst.IB.get(o, []))]}
    cert = {"format": "wfg.cert/1", "direction": "backward", "instance_sha256": instance_sha256(ci),
            "threshold": threshold, "exact": True, "states": states}
    if labels:
        cert["labels"] = labels
    return cert, ci
