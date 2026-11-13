"""Acceptance 8, spotting-dilation half (SPOTTING_NR2_ACCEPT8_RULE.md): d = 0 control vs the committed HEADLINE /2
kriged_mean h5 rows, and monotonicity of CERT / ROUTER leave-by over d = 0 <= 500 <= 1000 <= 2000 (and 0 -> 2000).
    python3 -m deadline_field.spot_nr2_compare --dir OUT --headline results/HEADLINE_NR2_summary.json --out X.json"""
import argparse, json, glob, os
from collections import Counter

D = (0, 500, 1000, 2000)
PAIRS = [(0, 500), (500, 1000), (1000, 2000), (0, 2000)]
LABELS = ["SCENARIO, not what happened; graphs are road-limited", "isotropic dilation, no wind field; nothing is claimed "
          "about actual spotting distances in 2025", "research check of monotonicity, not a spotting result",
          "CERT = router OR closed footprint; ROUTER = router rule only",
          "Assumes no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour."]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True); ap.add_argument("--headline", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hd = json.load(open(a.headline))
    H = {(p["region"], p["start"], p["origin"]): p for p in hd["places"] if p["horizon_h"] == 5}
    runs, meta = {}, json.load(open(os.path.join(a.dir, "rasters_meta.json")))
    for f in glob.glob(os.path.join(a.dir, "*_h5_d*.json")):
        x = json.load(open(f)); n = os.path.basename(f)[:-5]; reg, rest = n.split("__"); st = rest[:16]
        runs[(reg, st, x["spot"]["d_m"])] = x
    out = {"what": "acceptance 8, spotting-dilation half, no_reentry/2", "labels": LABELS, "starts": {}}
    tot = Counter()
    for (reg, st) in sorted({(r, s) for r, s, _ in runs}):
        have = [d for d in D if (reg, st, d) in runs]
        row = {"d_run": have, "nesting": meta.get("%s|%s|nesting" % (reg, st)),
               "clamped_cells": {d: meta["%s|%s|%d" % (reg, st, d)]["clamped_cells"] for d in D},
               "witness_checks": {d: runs[(reg, st, d)]["witness_checks"] for d in have},
               "no_route_split": {d: runs[(reg, st, d)]["no_route_split"] for d in have},
               "transform": {d: (runs[(reg, st, d)]["build_summaries"]["nr"] or {}).get("writer_identity", {}).get("transform") for d in have}}
        lb = {}
        bad_w = set()
        for d in have:
            x = runs[(reg, st, d)]
            for o, v in x["origins_detail"].items():
                lb[(d, o)] = {"nr_cert": v["leave_by_nr_cert"], "nr_router": v["leave_by_nr_router"],
                              "no_route": (v.get("no_route") or {}).get("split")}
            for w in x.get("witnesses", []):
                if not (w["nr"]["full_policy_ok"] and w["nr"]["closed_and_router_replay_clear"]):
                    bad_w.add(w["origin"])
        origins = sorted({o for (_, o) in lb})
        # control
        ctrl = []
        if 0 in have:
            for o in origins:
                hp = H.get((reg, st, o))
                if hp is None:
                    ctrl.append({"origin": o, "issue": "not in headline"}); continue
                for f in ("nr_cert", "nr_router"):
                    hv = hp[f]["per_variant"]["kriged_mean"]
                    want = hv.get("leave_by_s")
                    if want != lb[(0, o)][f]:
                        ctrl.append({"origin": o, "field": f, "headline": want, "d0": lb[(0, o)][f]})
        row["control_d0_mismatches"] = ctrl
        row["control_pass"] = (0 in have) and not ctrl
        mono, viol = {}, []
        for d1, d2 in PAIRS:
            if d1 not in have or d2 not in have:
                continue
            for f in ("nr_cert", "nr_router"):
                c = Counter()
                for o in origins:
                    if o in bad_w:
                        c["excluded_failing_witness"] += 1; continue
                    x1, x2 = lb[(d1, o)][f], lb[(d2, o)][f]
                    if x1 is None and x2 is None: s = "none_on_both"
                    elif x2 is None: s = "lost"
                    elif x1 is None: s = "VIOLATION"
                    elif x2 == x1: s = "equal"
                    elif x2 < x1: s = "earlier"
                    else: s = "VIOLATION"
                    c[s] += 1
                    if s == "VIOLATION":
                        viol.append({"origin": o, "field": f, "d": d1, "d_prime": d2, "leave_by_d": x1, "leave_by_d_prime": x2,
                                     "no_route_d": lb[(d1, o)]["no_route"]})
                mono["%d->%d:%s" % (d1, d2, f)] = dict(c)
                for k, v in c.items(): tot["%s:%s" % (f, k)] += v
        row["monotonicity"] = mono; row["violations"] = viol; row["failing_witness_origins"] = sorted(bad_w)
        if not row["control_pass"]:
            row["monotonicity_status"] = "not interpretable (d = 0 control failed or missing)"
        out["starts"]["%s|%s" % (reg, st)] = row
    out["totals"] = dict(tot)
    out["violations_total"] = sum(len(r["violations"]) for r in out["starts"].values())
    out["controls_pass"] = {k: r["control_pass"] for k, r in out["starts"].items()}
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    print(json.dumps({"controls_pass": out["controls_pass"], "violations_total": out["violations_total"], "totals": out["totals"]}, indent=1))

if __name__ == "__main__":
    main()
