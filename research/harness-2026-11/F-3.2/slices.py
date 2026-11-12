"""Proof-carrying route: bytes of the smallest instance slice a verifier needs, per mission.

  A  legality only: the witness corridor (edges used with D and EB, turn pairs, WB of wait nodes, AC of the end node).
  B  optimality, forward CERT: for every node n = hd(s), s in R: ALL out-edges (tail, head, D, EB), the forbidden pairs
     (s, j) for s in R, WB_n, AC_n; plus the certificate records.
  C  optimality, COCERT: unlisted states default to the full window, so C2/C3 need data only around listed states:
     for every node m = tail[j], j listed, and every destination node: ALL in-edges (their head record), plus EB_j, D_j
     for listed j and the forbidden pairs into listed j; WB at heads of listed states; AC; plus the certificate records.

Sizes are bytes in the .wfgc record syntax (one integer record per line). A slice is only sound if the verifier can
confirm adjacency lists are COMPLETE; that needs an authenticated per-node commitment (e.g. a Merkle tree over node
adjacency blocks under the instance hash). `merkle_upper` is an ESTIMATE: 32 bytes x ceil(log2 nV) per authenticated
node block, not shared between blocks (real multi-proofs are smaller). Not implemented or verified.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(HERE))
import cases  # noqa: E402
import generate as G  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance  # noqa: E402


def ivl(ivs):
    return G._ivl(ivs)


def edge_rec(inst, j, eb=True):
    s = "%d %d %d %d" % (j, inst.tail[j], inst.head[j], inst.D[j])
    if eb:
        s += " " + ivl(inst.edge_block.get(j, []))
    return s + "\n"


def main():
    rows = []
    for c in cases.korean_cases():
        g = json.loads(Path(c["graph"]).read_text()); r = json.loads(Path(c["request"]).read_text())
        inst, _ = build_instance(g, r, ContactModel.from_packet(c["packet"]))
        res = G.S.solve(inst)
        claim, T, legs = ("ROUTE", res["arrival"], res["legs"]) if res["status"] == "FOUND" else ("NO_ROUTE", inst.horizon + 1, [])
        E, nV = inst.E, inst.n_nodes
        hd = lambda s: inst.state_head(s)
        out_by, in_by = [[] for _ in range(nV)], [[] for _ in range(nV)]
        for j in range(E):
            out_by[inst.tail[j]].append(j); in_by[inst.head[j]].append(j)
        hdr = "DEP %d HOR %d ORIGIN %d START %d\n" % (inst.departure, inst.horizon, inst.origin, inst.start_state)
        acc = "".join("%d %s\n" % (n, ivl(v)) for n, v in sorted(inst.accept.items()))
        wb = lambda n: ("%d %s\n" % (n, ivl(inst.wait_block[n]))) if n in inst.wait_block else ""
        # A: witness corridor
        a_txt, s = hdr + acc, inst.start_state
        for kind, x, t0, t1 in legs:
            if kind == "EDGE":
                a_txt += edge_rec(inst, x) + ("%d %d\n" % (s, x)); s = x
            else:
                a_txt += wb(x)
        a_txt += "".join("%s %d %d %d\n" % ("E" if k == "EDGE" else "W", x, t0, t1) for k, x, t0, t1 in legs)
        # B: forward certificate support
        R, A = G.reachable(inst, T)
        nodes_b = {hd(s) for s in R}
        b_inst = hdr + acc + "".join(edge_rec(inst, j) for n in sorted(nodes_b) for j in out_by[n])
        b_inst += "".join(edge_rec(inst, s, eb=False) for s in sorted(R) if s < E and inst.tail[s] not in nodes_b)
        b_inst += "".join("%d %d\n" % p for p in sorted(inst.forbidden) if p[0] in R)
        b_inst += "".join(wb(n) for n in sorted(nodes_b) if inst.waitable[n])
        b_cert = "".join("%d %s %s\n" % (s, ivl(R[s]), ivl(A.get(s, []))) for s in sorted(R))
        # C: complement certificate support
        Gr, Ga = G.coreachable(inst, T)
        listed = set(Gr) | set(Ga)
        nodes_c = {inst.tail[j] for j in listed if j < E} | set(inst.accept)
        c_inst = hdr + acc + "".join(edge_rec(inst, j, eb=(j in listed)) for m in sorted(nodes_c) for j in in_by[m])
        c_inst += "".join(edge_rec(inst, j) for j in sorted(listed) if j < E)
        c_inst += "".join("%d %d\n" % p for p in sorted(inst.forbidden) if p[1] in listed)
        c_inst += "".join(wb(hd(s)) for s in sorted(listed) if inst.waitable[hd(s)])
        c_cert = "".join("%d %s %s\n" % (s, ivl(Gr.get(s, [])), ivl(Ga.get(s, []))) for s in sorted(listed))
        lg = math.ceil(math.log2(max(nV, 2)))
        full = len(G.instance_text(inst))
        row = dict(mission=c["mission"], claim=claim, T=T, full_instance_bytes=full, legs=len(legs),
                   A_witness_slice=len(a_txt),
                   B_fwd_slice_instance=len(b_inst), B_fwd_cert=len(b_cert), B_nodes=len(nodes_b),
                   B_merkle_upper=len(nodes_b) * 32 * lg,
                   C_co_slice_instance=len(c_inst), C_co_cert=len(c_cert), C_nodes=len(nodes_c),
                   C_merkle_upper=len(nodes_c) * 32 * lg)
        row["best_optimality_total"] = min(row["B_fwd_slice_instance"] + row["B_fwd_cert"] + row["B_merkle_upper"],
                                           row["C_co_slice_instance"] + row["C_co_cert"] + row["C_merkle_upper"])
        rows.append(row); print(json.dumps(row), flush=True)
    (HERE / "results" / "slices.json").write_text(json.dumps(rows, indent=1) + "\n")


if __name__ == "__main__":
    main()
