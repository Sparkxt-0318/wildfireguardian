"""Cell-by-cell and edge-by-edge check of Leo's no-re-entry packets (MANIFEST_v3_6 transform no_reentry/1) against
this field's never-clears arm on the matching reopening packet: PacketModel(reopen, duration_factor="never") vs
PacketModel(noreentry).  Compares per member and cell the birth and whether the phase reaches past H, and per edge
the blocked start sets under the router and closed rules (the field's actual inputs).
    python3 -m deadline_field.noreentry_check --graph G --reopen P1 --noreentry P2 --out OUT.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field.real import PacketModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--reopen", type=Path, required=True)
    ap.add_argument("--noreentry", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    A = PacketModel(a.graph, a.reopen, duration_factor="never")
    B = PacketModel(a.graph, a.noreentry)
    H = A.H
    cell_diff, birth_diff, end_short = [], [], []
    for rule, pa, pb in (("router", A.router_ph, B.router_ph), ("closed", A.closed_ph, B.closed_ph)):
        cells = set(pa) | set(pb)
        for c in cells:
            xa = sorted((b, s) for b, _x, s in pa.get(c, ()))
            xb = sorted((b, s) for b, _x, s in pb.get(c, ()))
            if [s for _, s in xa] != [s for _, s in xb]:
                cell_diff.append((rule, c))
            elif xa != xb:
                birth_diff.append((rule, c))
            for b, x, s in pb.get(c, ()):
                if x is not None and x < H:
                    end_short.append((rule, c, s))
    edge_diff = {r: sum(1 for j in range(len(A.B[r])) if A.B[r][j] != B.B[r][j]) for r in ("router", "closed")}
    out = {"reopen": str(a.reopen), "noreentry": str(a.noreentry), "H": H,
           "noreentry_reader": B.pk.consistency, "cells_with_member_set_difference": len(cell_diff),
           "cells_with_birth_difference": len(birth_diff), "noreentry_phases_ending_before_H": len(end_short),
           "edges_with_blocked_set_difference": edge_diff, "edges": len(A.B["router"]),
           "examples": {"cell_diff": cell_diff[:5], "birth_diff": birth_diff[:5], "end_short": end_short[:5]}}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in out if k != "examples"}, default=str))


if __name__ == "__main__":
    main()
