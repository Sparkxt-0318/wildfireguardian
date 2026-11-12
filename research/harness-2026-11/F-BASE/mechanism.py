"""Which rule each naive-baseline failure trips (Iris). Ablations on the instance, comparing the naive solver with the
exact solver ON THE SAME ablated instance:
  no_WB      : all blocked wait-start seconds removed (waitable set unchanged)
  all_wait   : every node waitable (WB unchanged)
  no_AC      : acceptance windows replaced by [dep, H] at the same destinations
A failure that disappears under an ablation is attributed to the removed rule.

    python mechanism.py --bundles DIR [--out RESULTS_mechanism.json]
"""
import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fbase  # noqa: E402

FAIL = {"n2": ["20230402T140000Z_FW2", "20220601T020000Z_FW1", "20250325T170000Z_FW1", "20220304T120000Z_FW2",
               "20250326T080000Z_FW1"],
        "n3": ["20230402T140000Z_FW2", "20220601T020000Z_FW1", "20250325T170000Z_FW1", "20220304T120000Z_FW2",
               "20250326T080000Z_FW1", "20250325T190000Z_FD1"]}


def ablate(inst, kind):
    i = copy.deepcopy(inst)
    if kind == "no_WB":
        i.WB = {}
    elif kind == "all_wait":
        i.waitable = set(range(i.nV))
    elif kind == "no_AC":
        i.AC = {n: [(i.dep, i.H)] for n in i.AC}
    return i


ap = argparse.ArgumentParser()
ap.add_argument("--bundles", type=Path, required=True)
ap.add_argument("--out", type=Path, default=HERE / "RESULTS_mechanism.json")
a = ap.parse_args()
rows = []
for solver, missions in FAIL.items():
    for m in missions:
        path = next(p for p in a.bundles.glob(f"*__{m}.wfgc"))
        inst = fbase.parse_instance(path.read_text())
        naive = getattr(fbase, f"solve_{solver}")
        row = dict(solver=solver, mission=m, base=dict(exact=fbase.solve_exact(inst)[:2], naive=naive(inst)),
                   n_WB_nodes=len(inst.WB), n_waitable=len(inst.waitable), nV=inst.nV,
                   AC={str(k): v for k, v in inst.AC.items()})
        for kind in ("no_WB", "all_wait", "no_AC"):
            i = ablate(inst, kind)
            e, n = fbase.solve_exact(i)[:2], naive(i)
            row[kind] = dict(exact=e, naive=n, naive_correct=(e == n))
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("solver", "mission", "base", "n_WB_nodes", "n_waitable", "nV", "AC")}),
              {k: row[k]["naive_correct"] for k in ("no_WB", "all_wait", "no_AC")}, flush=True)
a.out.write_text(json.dumps(rows, indent=1))
