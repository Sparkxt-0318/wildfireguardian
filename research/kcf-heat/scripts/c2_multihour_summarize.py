"""Summarize the 48 multi-hour runs (c2_multihour_batch.py output) into one compact JSON.

    python scripts/c2_multihour_summarize.py RUN_DIR OUT.json

Per packet: reproduction of F-3.1's recorded CERT leave-by, and leave-by changes cert -> cert_heat -> tdu<B>.
Per (region, start, horizon) and place: the range across the named timing variants (kriged_mean, firms_early,
envelope), as MULTIHOUR_HEADLINE_RULE.md (2), for cert, cert_heat and each budget; envelope_burnset is the separate
static final-footprint row.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TIMING = ("kriged_mean", "firms_early", "envelope")


def main(run_dir, out):
    runs = [json.loads(p.read_text()) for p in sorted(Path(run_dir).glob("*.json"))]
    budgets = runs[0]["budgets_tdu"]
    vars_ = ["cert", "cert_heat"] + ["tdu%g" % b for b in budgets]
    packets, tot = [], Counter()
    places = defaultdict(dict)
    for d in runs:
        key = (d["region"], d["start"], d["H"] // 3600)
        row = {"region": d["region"], "start": d["start"], "horizon_h": d["H"] // 3600, "variant": d["variant"],
               "hazard_sha256": d.get("hazard_sha256"), "burning_cells": d["dose_model"]["burning_cells"],
               "origins": d["origins"], "reference_cert_reproduction": d["reference_cert_reproduction"],
               "witness_checks": d["witness_checks"], "nonprefix_feasible_unions": d["nonprefix_feasible_unions"],
               "timing_s": {k: round(v, 1) for k, v in d["timing_s"].items()},
               "tdu_field_stats": d["tdu_field_stats"],
               "compare": {k: {kk: vv for kk, vv in v.items() if kk != "shift_s"} | {"shift_s_median": (
                   statistics.median(v["shift_s"]) if v["shift_s"] else None), "shift_s_max": max(v["shift_s"], default=None)}
                   for k, v in d["compare"].items()}}
        packets.append(row)
        for k, v in d["reference_cert_reproduction"].items():
            tot["reproduction:" + k] += v
        for k, v in d["witness_checks"].items():
            tot["witness:" + k] += v
        for oid, r in d["origins_detail"].items():
            places[key + (oid,)][d["variant"]] = {v: r["leave_by_" + v] for v in vars_}
    # ranges across timing variants per place, and the static row
    rng = Counter()
    place_rows = []
    for (region, start, h, oid), per in sorted(places.items()):
        pr = {"region": region, "start": start, "horizon_h": h, "origin": oid}
        for v in vars_:
            vals = {var: per[var][v] for var in TIMING if var in per}
            got = [x for x in vals.values() if x is not None]
            pr[v] = {"min_s": min(got) if got else None, "max_s": max(got) if got else None,
                     "variants_without_route": sorted(k for k, x in vals.items() if x is None)}
            if "envelope_burnset" in per:
                pr[v]["static_final_footprint"] = per["envelope_burnset"][v]
        for v in vars_[1:]:
            a, b = pr["cert"], pr[v]
            if a["min_s"] != b["min_s"] or a["variants_without_route"] != b["variants_without_route"]:
                rng["range_earliest_edge_changed:" + v] += 1
        place_rows.append(pr)
    agg = defaultdict(Counter)
    for p in packets:
        grp = "static_final_footprint" if p["variant"] == "envelope_burnset" else "timing_variants"
        for k, v in p["compare"].items():
            for kk in ("moved_earlier", "lost_route", "MOVED_LATER", "GAINED_route", "unchanged", "both_none"):
                agg[grp + ":" + k][kk] += v.get(kk, 0)
    shifts = defaultdict(list)
    for d in runs:
        grp = "static_final_footprint" if d["variant"] == "envelope_burnset" else "timing_variants"
        for k, v in d["compare"].items():
            shifts[grp + ":" + k] += v["shift_s"]
    for k, s in shifts.items():
        s.sort()
        agg[k]["shift_s_median"] = statistics.median(s) if s else None
        agg[k]["shift_s_max"] = max(s) if s else None
        agg[k]["shift_s_min"] = min(s) if s else None
    out_doc = {"schema": "kcf-heat.multihour-summary/1", "packets_run": len(runs), "budgets_tdu": budgets,
               "label": "SCENARIO (F-DYN), not what happened; roads limited to the recorded windows",
               "totals": dict(tot), "by_group": {k: dict(v) for k, v in sorted(agg.items())},
               "place_ranges_changed": dict(rng), "packets": packets, "places": place_rows}
    Path(out).write_text(json.dumps(out_doc, indent=1))
    print(json.dumps({"packets_run": len(runs), "totals": dict(tot), "place_ranges_changed": dict(rng),
                      "by_group": {k: dict(v) for k, v in sorted(agg.items()) if k.startswith("timing")}}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
