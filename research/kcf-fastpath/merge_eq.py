"""Merge partial eq_real.py outputs (runs over disjoint spec subsets of one cache) into results/eq_<cache>.json.

    python3 merge_eq.py OUT_JSON PART_JSON...
"""
import json
import sys
from collections import Counter

parts = [json.load(open(p)) for p in sys.argv[2:]]
tally, kinds, fails = {}, {}, []
for p in parts:
    for v, t in p["tally"].items():
        tally.setdefault(v, Counter()).update(t)
    for v, k in p["state_kinds_summed_over_specs"].items():
        kinds.setdefault(v, Counter()).update(k)
    fails += p["failure_list"]
share = {v: {kk: vv / k["states"] for kk, vv in k.items() if kk != "states"} for v, k in kinds.items() if k.get("states")}
specs_done = {v: t.get("specs", 0) for v, t in tally.items()}
assert all(n == parts[0]["specs"] for n in specs_done.values()), specs_done
res = {"cache": parts[0]["cache"], "edges": parts[0]["edges"], "specs": parts[0]["specs"], "merged_from_parts": len(parts),
       "tally": {k: dict(v) for k, v in tally.items()}, "state_kinds_summed_over_specs": {k: dict(v) for k, v in kinds.items()},
       "state_kind_shares": share, "failures": sum(p["failures"] for p in parts), "failure_list": fails[:200]}
json.dump(res, open(sys.argv[1], "w"), indent=1)
print(res["cache"], "failures", res["failures"], "specs", specs_done)
