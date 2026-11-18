"""Twin summary exactly as PROTOCOL.md section 3 defines it. Usage: python3 summarize_twin.py OUT_DIR   (reads twin_cells.csv, twin_places.csv)"""
import csv, json, sys
from pathlib import Path
import numpy as np

out = Path(sys.argv[1])
cells = list(csv.DictReader(open(out / "twin_cells.csv")))
places = list(csv.DictReader(open(out / "twin_places.csv")))
f = lambda v: float(v) if v not in ("", "None", None) else None
rng = np.random.default_rng(20261118)
SEEDS = sorted({int(r["seed"]) for r in cells})


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else None


def place_metrics(rows):
    ok = [r for r in rows if r["true_state"] != "REFUSED"]
    tc = [r for r in ok if r["true_state"] == "CUT"]
    m = {"places_pairs": len(ok), "refused_pairs": len(rows) - len(ok), "true_CUT": len(tc), "true_NOT_CUT": len(ok) - len(tc),
         "system_CUT": sum(r["system_state"] == "CUT" for r in ok)}
    both = [r for r in tc if r["system_state"] == "CUT"]
    missed_absent = [r for r in tc if r["system_state"] == "NOT_CUT"]
    late_s = [f(r["system_cut_s"]) - f(r["truth_cut_s"]) for r in both]
    m["both_CUT"] = len(both); m["true_CUT_system_NOT_CUT"] = len(missed_absent)
    for name, thr in (("gt0", 0.0), ("ge15min", 900.0), ("ge60min", 3600.0)):
        m["missed_cutoff_" + name] = len(missed_absent) + sum((x > 0 if thr == 0 else x >= thr) for x in late_s)
    m["false_cutoff_system_CUT_truth_NOT_CUT"] = sum(r["system_state"] == "CUT" and r["true_state"] == "NOT_CUT" for r in ok)
    e = np.array(late_s) / 60.0
    m["cutoff_err_min_system_minus_true"] = {"n": int(e.size), "p10": pct(e, 10), "median": pct(e, 50), "p90": pct(e, 90),
                                             "min": float(e.min()) if e.size else None, "max": float(e.max()) if e.size else None}
    arr = [(f(r["system_arrival_s"]) - f(r["truth_arrival_s"])) / 60.0 for r in ok if f(r["system_arrival_s"]) is not None and f(r["truth_arrival_s"]) is not None]
    m["village_arrival_err_min_system_minus_true"] = {"n": len(arr), "p10": pct(arr, 10), "median": pct(arr, 50), "p90": pct(arr, 90)}
    m["village_arrival_true_in_horizon"] = sum(f(r["truth_arrival_s"]) is not None for r in ok)
    m["village_arrival_system_absent_while_true_in_horizon"] = sum(f(r["truth_arrival_s"]) is not None and f(r["system_arrival_s"]) is None for r in ok)
    return m


def cell_metrics(rows):
    s = lambda k: sum(int(r[k]) for r in rows)
    reach = s("true_reach_cells")
    m = {"pairs": len(rows), "true_reach_cells": reach, "late": s("late"), "late_ge15": s("late_ge15"), "late_ge60": s("late_ge60"),
         "system_absent": s("system_absent"), "finite_both": s("finite_both"), "false_reach_cells": s("false_reach_cells"),
         "system_known_but_truth_not_burning": s("system_known_but_truth_not_burning")}
    for k in ("late", "late_ge15", "late_ge60", "system_absent"):
        m[k + "_rate"] = m[k] / reach if reach else None
    return m


res = {"label": "Twin experiment: a simulator is the truth. Model output on synthetic inputs. Not what happened to people.",
       "protocol": "research/kcf-validate/PROTOCOL.md §3", "seeds": SEEDS, "arms": {}}
for arm in ("system", "control"):
    pr = [r for r in places if r["arm"] == arm]; cr = [r for r in cells if r["arm"] == arm]
    A = {"cells_pooled": cell_metrics(cr), "places_pooled": place_metrics(pr), "per_seed": {}, "by_issue": {}}
    A["places_split"] = {
        "truth_cut_inside_horizon": place_metrics([r for r in pr if r["true_state"] == "NOT_CUT" or r["truth_status"] == "cut"]),
        "truth_already_cut_at_issue": place_metrics([r for r in pr if r["true_state"] == "NOT_CUT" or r["truth_status"].startswith("already cut")])}
    for h in sorted({int(r["issue_offset_h"]) for r in cr}):
        A["by_issue"][str(h)] = {"cells": cell_metrics([r for r in cr if int(r["issue_offset_h"]) == h]),
                                 "places": place_metrics([r for r in pr if int(r["issue_offset_h"]) == h])}
    for sd in SEEDS:
        A["per_seed"][str(sd)] = {"cells": cell_metrics([r for r in cr if int(r["seed"]) == sd]),
                                  "places": place_metrics([r for r in pr if int(r["seed"]) == sd])}
    # seed-level bootstrap (descriptive): pooled missed-cutoff rate (>0) = missed / true_CUT, and late-cell rate
    def rate(sel, kind):
        if kind == "place":
            m = place_metrics([r for r in pr if int(r["seed"]) in sel])
            return m["missed_cutoff_gt0"] / m["true_CUT"] if m["true_CUT"] else None
        m = cell_metrics([r for r in cr if int(r["seed"]) in sel])
        return m["late_rate"]
    boots = {"place": [], "cell": []}
    byseed_p = {sd: [r for r in pr if int(r["seed"]) == sd] for sd in SEEDS}; byseed_c = {sd: [r for r in cr if int(r["seed"]) == sd] for sd in SEEDS}
    for _ in range(2000):
        draw = rng.choice(SEEDS, len(SEEDS), replace=True)
        P = [r for sd in draw for r in byseed_p[int(sd)]]; C = [r for sd in draw for r in byseed_c[int(sd)]]
        mp = place_metrics(P); mc = cell_metrics(C)
        if mp["true_CUT"]:
            boots["place"].append(mp["missed_cutoff_gt0"] / mp["true_CUT"])
        if mc["true_reach_cells"]:
            boots["cell"].append(mc["late_rate"])
    A["bootstrap_over_seeds_95"] = {k: ([pct(v, 2.5), pct(v, 97.5)] if v else None) for k, v in boots.items()}
    A["bootstrap_n_valid"] = {k: len(v) for k, v in boots.items()}
    res["arms"][arm] = A
(out / "twin_summary.json").write_text(json.dumps(res, indent=1))
for arm, A in res["arms"].items():
    p = A["places_pooled"]; c = A["cells_pooled"]
    print(arm, "cells:", {k: c[k] for k in ("true_reach_cells", "late", "late_rate", "late_ge60", "false_reach_cells")})
    print(arm, "places:", {k: p[k] for k in ("places_pairs", "true_CUT", "system_CUT", "both_CUT", "true_CUT_system_NOT_CUT", "missed_cutoff_gt0", "missed_cutoff_ge15min", "missed_cutoff_ge60min", "false_cutoff_system_CUT_truth_NOT_CUT")})
    print("   boot", A["bootstrap_over_seeds_95"], A["bootstrap_n_valid"])
    for k, v in A["places_split"].items():
        print("   ", k, {x: v[x] for x in ("true_CUT", "both_CUT", "true_CUT_system_NOT_CUT", "missed_cutoff_gt0", "missed_cutoff_ge15min", "missed_cutoff_ge60min", "false_cutoff_system_CUT_truth_NOT_CUT")})
