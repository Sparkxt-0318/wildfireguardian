"""Rate-assumed tier sensitivity at 1 h (rule: RATE_ASSUMED_RULE.md section 1, committed first).

Per cache and variant (A, rate-assumed R at 1.5 / 8.2 / 16.4 km/h, and B16.4 where present), per origin vs the
optimistic (frozen packet) field: removed (optimistic has a deadline, the variant none), moved (both, differ; median and
max of optimistic - variant, s), unchanged; plus job label counts. CERT contact field (pessimistic 'checked' is
contact-only).
    python3 -m deadline_field.rate_sensitivity --base DIR_WITH_A_R1.5_R8.2 --extra DIR_R16.4 [DIR_B16.4] --out OUT
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def per_variant(od_base, od_var, name):
    rem = mov = unch = 0
    shifts = []
    for o, x in od_base.items():
        opt = x["optimistic"]
        v = od_var[o][name]
        if opt is None:
            continue
        if v is None:
            rem += 1
        elif v != opt:
            mov += 1
            shifts.append(opt - v)
        else:
            unch += 1
    shifts.sort()
    return {"origins_with_optimistic_deadline": sum(1 for x in od_base.values() if x["optimistic"] is not None),
            "removed": rem, "moved": mov, "unchanged": unch,
            "moved_shift_s": {"median": shifts[len(shifts) // 2] if shifts else None, "max": shifts[-1] if shifts else None}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--extra", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = []
    for f in sorted(a.base.glob("*.json")):
        b = json.loads(f.read_text())
        od = b["origin_deadlines"]
        row = {"cache_file": b["cache_file"], "variants": {}}
        for name in ("A", "R1.5", "R8.2"):
            row["variants"][name] = per_variant(od, od, name)
            row["variants"][name]["job_labels"] = dict(Counter(j[name] for j in b["jobs"]))
        for d in a.extra:
            g = d / f.name
            if not g.exists():
                continue
            e = json.loads(g.read_text())
            names = [k for k in next(iter(e["origin_deadlines"].values())) if k != "optimistic"]
            # the extra run recomputed the optimistic field: it must equal the base one
            assert all(e["origin_deadlines"][o]["optimistic"] == od[o]["optimistic"] for o in od), "optimistic mismatch"
            for name in names:
                row["variants"][name] = per_variant(od, e["origin_deadlines"], name)
                row["variants"][name]["job_labels"] = dict(Counter(j[name] for j in e["jobs"]))
        out.append(row)
    a.out.write_text(json.dumps({"what": "rate-assumed tier sensitivity at 1 h (RATE_ASSUMED_RULE.md); per origin vs "
                                         "optimistic; CERT contact field, pessimistic 'checked' is contact-only; tier "
                                         "label 'rate-assumed, v km/h'; Tier A = all unknown blocked from 0",
                                 "caches": out}, indent=1))
    for r in out:
        print(r["cache_file"].split("/")[-2][:2], r["cache_file"][-21:-5],
              " | ".join("%s rem %d mov %d (med %s, max %s)" % (k, v["removed"], v["moved"], v["moved_shift_s"]["median"],
                                                               v["moved_shift_s"]["max"]) for k, v in r["variants"].items()))


if __name__ == "__main__":
    main()
