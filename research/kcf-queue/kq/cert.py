"""Writes kcf-queue.cert/1 (CERTIFICATE_SPEC.md) from solver output. The checker (../checker.py) shares nothing with this."""
from __future__ import annotations

import hashlib
import json

from .real import DWELL, H
from .solver import BIG


def binding(net, amax_of, subject_paths, releases, subj_id):
    """Binding element of the subject (spec R7): min of (slack, kind order, id, owner, k)."""
    best = None
    order = {"edge": 0, "node": 1, "shelter": 2}
    for k, path in enumerate(subject_paths):
        a = releases[k]
        for i, (e, t) in enumerate(path):
            u = net.tail[e]
            if net.lo[e] < BIG:
                cand = (net.lo[e] - 1 - t, 0, e, subj_id, k, "edge")
                if best is None or cand[:5] < best[:5]:
                    best = cand
            if t > a and net.wcut[u] < BIG:
                cand = (net.wcut[u] - 1 - t, 1, u, subj_id, k, "node")
                if best is None or cand[:5] < best[:5]:
                    best = cand
            a = t + net.D[e]
        sh = net.head[path[-1][0]]
        cand = (amax_of[sh] - a, 2, sh, subj_id, k, "shelter")
        if best is None or cand[:5] < best[:5]:
            best = cand
    s, _, i, _, k, kind = best
    return {"kind": kind, "id": i, "vehicle": [subj_id, k], "slack": s}


def build(R, net, close, cap_vph, rho, owners, subj_id, bind):
    """owners: list of dicts {id, origin, N, start, spread, role, paths, shelters}."""
    rd = R.road
    edges = sorted({e for o in owners for p in o["paths"] for e, _ in p})
    eset = set(edges)
    nodes = {rd.tail[e] for e in edges} | {rd.head[e] for e in edges} | {o["origin"] for o in owners}
    shelters = sorted({s for o in owners for s in o["shelters"]})
    nodes |= set(shelters)
    cells = {rd.node_cell[n] for n in nodes}
    for e in edges:
        cells |= {c for c, _ in rd.seg[e]}
    forb = sorted([i, j] for i in edges for j in net.out[rd.head[i]] if j in eset and (i, j) in net.forbid)
    data = {
        "cell_close": {str(c): close[c] for c in sorted(cells) if c in close},
        "nodes": {str(n): {"cell": rd.node_cell[n]} for n in sorted(nodes)},
        "edges": {str(e): {"tail": rd.tail[e], "head": rd.head[e], "D": rd.D[e], "cap_vph": cap_vph[R.cls[e]],
                           "segs": [[c, "%d/%d" % (z.numerator, z.denominator)] for c, z in rd.seg[e]]} for e in edges},
        "forbidden": forb, "shelters": shelters}
    sha = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    veh = [{"owner": o["id"], "k": k, "path": [[e, t] for e, t in p]} for o in owners for k, p in enumerate(o["paths"])]
    return {"schema": "kcf-queue.cert/1", "H": H, "dwell": DWELL, "bin_s": net.bin_s, "rho": rho, "data": data, "input_sha256": sha,
            "owners": [{k: o[k] for k in ("id", "origin", "N", "start", "spread", "role", "ks") if k in o} for o in owners],
            "vehicles": veh, "claim": {"subject": subj_id, "all_cleared": True, "binding": bind}}
