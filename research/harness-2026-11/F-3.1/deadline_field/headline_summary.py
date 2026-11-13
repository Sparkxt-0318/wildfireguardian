"""Summary of headline-runner outputs (MULTIHOUR_HEADLINE_RULE.md, amendments up to 19:15 UTC).

Per region, start, horizon and origin:
  * leave-by per timing variant (kriged_mean, firms_early, envelope), CERT and ROUTER, and the range across them
    ("range across named timing variants; none is a bound; no time-dependent pessimistic variant exists at
    multi-hour"); a variant with no route is named in the range, never dropped;
  * the static final-footprint row (envelope_burnset), its own row;
  * no-route rows carry the ROAD-LIMITED label and the split.
Per packet: acceptance 7, verdict differences no re-entry vs clearing, witness checks, non-prefix sets.
Per region/start/horizon: places where an earlier-arrival variant (firms_early, envelope) gives a LATER leave-by than
kriged_mean (amendment 19:15 UTC), listed, CERT and ROUTER.
    python3 -m deadline_field.headline_summary --dir DIR --out OUT
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

TIMING = ("kriged_mean", "firms_early", "envelope")
RANGE_LABEL = ("range across named timing variants; none is a bound; no time-dependent pessimistic variant exists at "
               "multi-hour")
STATIC_LABEL = ("static final-footprint bound (no timing; identical across starts; single implementation); burn set = "
                "kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 "
                "FIRMS-only)")
VARIANT_LABEL = {"kriged_mean": "central scenario", "firms_early": "bracket-start, not a lower bound",
                 "envelope": "bracket-start, not a lower bound"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    runs = {}
    for f in sorted(a.dir.glob("*.json")):
        d = json.loads(f.read_text())
        region, rest = f.stem.split("__")
        start, h, var = rest.split("_", 2)
        runs[(region, start, int(h[1:]), var)] = d
    transforms = Counter(d.get("transform") for d in runs.values())
    labels = sorted({d["label"] for d in runs.values()})
    packets = []
    for (region, start, h, var), d in sorted(runs.items()):
        packets.append({"region": region, "start": start, "horizon_h": h, "variant": var, "transform": d.get("transform"),
                        "hazard_sha256": {k: v["HAZARD_sha256"] for k, v in d["packets"].items()},
                        "writer_identity": {k: (v or {}).get("writer_identity") for k, v in d.get("build_summaries", {}).items()},
                        "witness_checks": d["witness_checks"], "acceptance7": d["acceptance7"],
                        "verdict_diff_noreentry_vs_clearing": d["verdict_diff_noreentry_vs_clearing"],
                        "no_route_split": d["no_route_split"], "nonprefix_feasible_sets": d["nonprefix_feasible_sets"],
                        "precondition_noreentry_ok": d["precondition_noreentry_ok"]})
    groups = defaultdict(dict)
    for (region, start, h, var), d in runs.items():
        groups[(region, start, h)][var] = d
    places, later = [], []
    for (region, start, h), vs in sorted(groups.items()):
        origins = sorted(next(iter(vs.values()))["origins_detail"])
        for o in origins:
            row = {"region": region, "start": start, "horizon_h": h, "origin": o}
            for fld in ("nr_cert", "nr_router"):
                per = {}
                for v in TIMING:
                    if v not in vs:
                        per[v] = "NOT_RUN"
                        continue
                    r = vs[v]["origins_detail"][o]
                    lb = r["leave_by_" + fld]
                    if lb is None:
                        nr = r.get("no_route", {})
                        per[v] = {"no_route": nr.get("split", "no route"),
                                  "label": "ROAD-LIMITED" if nr.get("split") != "origin_point_in_flame_at_departure" else None}
                    else:
                        per[v] = {"leave_by_s": lb, "horizon_censored": r.get("censored_at_horizon"),
                                  "variant_label": VARIANT_LABEL[v]}
                vals = [x["leave_by_s"] for x in per.values() if isinstance(x, dict) and "leave_by_s" in x]
                row[fld] = {"per_variant": per, "range": {"min_s": min(vals) if vals else None,
                                                          "max_s": max(vals) if vals else None,
                                                          "variants_without_route": [v for v, x in per.items()
                                                                                     if isinstance(x, dict) and "no_route" in x],
                                                          "label": RANGE_LABEL}}
                km = per.get("kriged_mean")
                for v in ("firms_early", "envelope"):
                    x = per.get(v)
                    if not (isinstance(km, dict) and isinstance(x, dict)):
                        continue
                    a_ = km.get("leave_by_s")
                    b_ = x.get("leave_by_s")
                    if (b_ is not None and (a_ is None or b_ > a_)):
                        later.append({"region": region, "start": start, "horizon_h": h, "origin": o, "field": fld,
                                      "variant": v, "kriged_mean_leave_by_s": a_, "variant_leave_by_s": b_})
            if "envelope_burnset" in vs:
                r = vs["envelope_burnset"]["origins_detail"][o]
                row["static_final_footprint_row"] = {"label": STATIC_LABEL,
                                                     "nr_cert": r["leave_by_nr_cert"], "nr_router": r["leave_by_nr_router"],
                                                     "no_route": r.get("no_route", {}).get("split")}
            places.append(row)
    tot = Counter()
    for p in packets:
        for k, v in p["acceptance7"].items():
            tot["acceptance7:" + k] += v
        for k, v in p["verdict_diff_noreentry_vs_clearing"].items():
            tot["verdict_diff:" + k] += v
        for k, v in p["witness_checks"].items():
            tot["witness:" + k] += v
        for k, v in p["no_route_split"].items():
            tot["no_route:" + k] += v
        for k, v in p["nonprefix_feasible_sets"].items():
            tot["nonprefix:" + k] += v
    lc = Counter((x["field"], x["variant"], x["region"], x["horizon_h"]) for x in later)
    out = {"what": "headline-runner summary; SCENARIO, not what happened; roads limited to the recorded windows",
           "transforms": dict(transforms), "labels": labels,
           "assumption": ("Assumes no fire outside mapped or forecast cells; no conservative unknown-support tier "
                          "exists at multi-hour. The static final-footprint row shows whether the road crosses the "
                          "eventual burn area, not when it was safe to leave."),
           "fields": "CERT = router OR closed footprint; ROUTER = router rule only; refusal-grade statements only from ROUTER",
           "packets_run": len(packets), "totals": dict(tot),
           "earlier_variant_later_than_kriged_mean": {"count_by_field_variant_region_horizon":
                                                       {"|".join(map(str, k)): v for k, v in sorted(lc.items())},
                                                       "places": later},
           "packets": packets, "places": places}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({"packets_run": len(packets), "transforms": dict(transforms), "totals": dict(tot),
                      "later": {"|".join(map(str, k)): v for k, v in sorted(lc.items())}}, indent=1))


if __name__ == "__main__":
    main()
