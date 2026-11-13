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


# ------------------------------------------------------------------------------------- Thomas's .wfgc (F-3.2 FORMAT.md)
def _ivl(ivs):
    return "%d %s" % (len(ivs), " ".join("%d %d" % p for p in ivs)) if ivs else "0"


def _clip(ivs, lo, hi):
    return [(max(a, lo), min(b, hi)) for a, b in ivs if b >= lo and a <= hi]


def wfgc_instance_text(inst, origin: int, dep: int) -> str:
    """INSTANCE ... END_INSTANCE block (FORMAT.md v1). Sentinel state nE = issue state at ``origin``; turn rules
    are not applied at issue. EB/WB clipped to [dep, H]; AC per destination node (opening, horizon, dwell-clear),
    the per-node acceptance ``inst.AN``."""
    E, H = len(inst.tail), inst.H
    lines = ["INSTANCE", "V %d E %d" % (inst.n_nodes, E), "DEP %d HOR %d ORIGIN %d START %d" % (dep, H, origin, E), "EDGES"]
    lines += ["%d %d %d" % (inst.tail[j], inst.head[j], inst.D[j]) for j in range(E)]
    wt = [v for v in range(inst.n_nodes) if inst.waitable[v]]
    lines.append("WAITABLE %d%s" % (len(wt), "".join(" %d" % v for v in wt)))
    fb = sorted(inst.forbidden)
    lines.append("FORBID %d%s" % (len(fb), "".join(" %d %d" % p for p in fb)))
    eb = [(j, _clip(inst.B[j], dep, H)) for j in range(E)]
    eb = [(j, x) for j, x in eb if x]
    lines.append("EB %d" % len(eb)); lines += ["%d %s" % (j, _ivl(x)) for j, x in eb]
    wb = [(v, _clip(inst.W[v], dep, H)) for v in range(inst.n_nodes) if inst.waitable[v]]
    wb = [(v, x) for v, x in wb if x]
    lines.append("WB %d" % len(wb)); lines += ["%d %s" % (v, _ivl(x)) for v, x in wb]
    ac = {n: a for n, a in inst.AN.items() if a}
    acl = [(n, _clip(ac[n], dep, H)) for n in sorted(ac)]
    lines.append("AC %d" % len(acl)); lines += ["%d %s" % (n, _ivl(x)) for n, x in acl]
    lines.append("END_INSTANCE")
    return "\n".join(lines) + "\n"


def wfgc_no_route(fld, origin: int, dep: int) -> tuple:
    """NO_ROUTE bundle from the exact backward field (complement = forward invariant, T = H + 1).
    Valid iff dep is not a feasible departure; issue-point refusal is outside the instance (frontend)."""
    inst = fld.inst
    E, H = len(inst.tail), inst.H
    core = issue_core(fld, origin)
    if iv.contains(core, dep):
        raise ValueError("departure is feasible in the field; no NO_ROUTE certificate")
    full = [(dep, H)]
    recs = []
    for s in range(E):
        Rp = iv.subtract((dep, H), fld.R[s])
        Ap = iv.subtract((dep, H), fld.G[s])
        if Rp:
            recs.append("%d %s %s" % (s, _ivl(Rp), _ivl(Ap)))
    # sentinel: not-admitted completion set (waits never re-admit) vs the admitted initial label at dep
    Rp = iv.subtract((dep, H), issue_core(fld, origin, initial_admission=False))
    Ap = [(dep, dep)]
    recs.append("%d %s %s" % (E, _ivl(Rp), _ivl(Ap)))
    inst_text = wfgc_instance_text(inst, origin, dep)
    text = "WFGC 1\n" + inst_text + "CLAIM NO_ROUTE\nWITNESS 0\nCERT %d %d\n" % (H + 1, len(recs)) + "\n".join(recs) + "\nEND\n"
    return text, hashlib.sha256(inst_text.encode()).hexdigest()


def wfgc_index_map(graph_path) -> dict:
    """Map from .wfgc indices to graph ids for every certificate built on this graph (Thomas): edge index j ->
    graph edge id (edge order of graph.json), node index v -> node id (node order of graph.json). The sentinel
    state E is the issue state at the certificate's ORIGIN and has no edge id."""
    import json as _j
    from pathlib import Path as _P
    from tools.explain_deadlines.roads import RoadGraph
    raw = _j.loads(_P(graph_path).read_text())
    g = RoadGraph(raw)
    return {"graph": str(graph_path), "graph_sha256": hashlib.sha256(_P(graph_path).read_bytes()).hexdigest(),
            "revision": raw.get("revision"), "edges": list(g.edge_ids), "nodes": list(g.node_xy),
            "note": "edge index j = position in 'edges'; node index v = position in 'nodes'; sentinel state E = issue state"}
