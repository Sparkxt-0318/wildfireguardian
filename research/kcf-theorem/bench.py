"""Running-time comparison (THEOREM.md section 5): one backward pass for all origins and all departure seconds,
versus checking departures one at a time with the checker's exhaustive search (checker.find_route), on k x k
bidirectional grids with random permanent closures (hypotheses M1-M4) and one shelter in a corner.

    python3 research/kcf-theorem/bench.py            # writes results/bench.json
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checker  # noqa: E402
import randgraphs  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402


def grid(k, H, rng):
    nid = lambda r, c: r * k + c  # noqa: E731
    edges = []
    for r in range(k):
        for c in range(k):
            for dr, dc in ((0, 1), (1, 0)):
                if r + dr < k and c + dc < k:
                    D = rng.randint(1, 4)
                    edges += [[nid(r, c), nid(r + dr, c + dc), D], [nid(r + dr, c + dc), nid(r, c), D]]
    B = {j: [[rng.randint(0, H), H]] for j in range(len(edges)) if rng.random() < 0.3}
    A = {j: [[0, H - 2]] for j, e in enumerate(edges) if e[1] == k * k - 1}
    return {"H": H, "n_nodes": k * k, "edges": edges, "waitable": [], "forbidden": [], "B": B, "W": {}, "A": A,
            "IB": {}, "AN": {}}


def main():
    rows = []
    for k, H in ((3, 30), (3, 60), (3, 120), (4, 60), (4, 120), (4, 240), (5, 120), (5, 240), (6, 240)):
        chk = grid(k, H, random.Random(f"{k}-{H}"))
        inst = randgraphs.to_instance(chk)
        t0 = time.perf_counter()
        fld = backward(inst)
        sets = [issue_set(fld, o) for o in range(k * k)]
        t_field = time.perf_counter() - t0
        m = checker.Model(chk)
        o = 0
        t0 = time.perf_counter()
        bf = checker.feasible_set(m, o)
        t_one = time.perf_counter() - t0
        assert set(bf) == {t for lo, hi in sets[o] for t in range(lo, hi + 1)}
        rows.append({"grid": f"{k}x{k}", "edges": len(chk["edges"]), "H": H, "pushes": fld.stats["pushes"],
                     "pushes_per_edge": round(fld.stats["pushes"] / len(chk["edges"]), 2),
                     "max_pieces_per_state": max(len(r) for r in fld.R),
                     "field_all_origins_s": round(t_field, 4),
                     "one_at_a_time_ONE_origin_s": round(t_one, 4),
                     "one_at_a_time_all_origins_est_s": round(t_one * k * k, 2)})
        print(rows[-1], flush=True)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "bench.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
