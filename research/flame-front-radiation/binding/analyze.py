"""Aggregate the replay and the five-policy study into RESULTS.json and figures fig02 to fig04.

Reads binding/REPLAY.json and binding/POLICY_STUDY.json (written by run_replay.py and run_policy_study.py); writes
../RESULTS.json, binding/MISSIONS.csv, binding/THRESHOLDS.csv and the figures in ../figures/. Deterministic.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(RES))
sys.path.insert(0, str(REPO / "experimental/flame-front-radiation/adapters"))
FIG = RES / "figures"


def mission_outcome(rows):
    """Mission-level outcome from the executions of one (mission, policy, setting): requires agreement across reps."""
    keys = set()
    for r in rows:
        if r["planner_status"] == "ROUTE":
            own_fail = r.get("exact_own_fail")
            keys.add(("ROUTE_FAILS_EXACT_CHECK" if own_fail else "CHECKED_ROUTE", r["arrival"]))
        elif r["planner_status"] in ("EXHAUSTED", "AT_ISSUE_FAILURE"):
            keys.add(("NO_ROUTE", None))
        else:
            keys.add((r["planner_status"], None))
    if len(keys) != 1:
        return ("INCONSISTENT_REPS", None)
    return keys.pop()


def classify(study):
    rows = study["rows"]
    by = defaultdict(list)
    for r in rows:
        by[(r["case_id"], r["policy"], r["setting"])].append(r)
    missions = sorted({(r["cohort"], r["case_id"]) for r in rows})
    out = {}
    for cohort, cid in missions:
        rec = {"cohort": cohort}
        for setting in ("v1", "E100", "E23"):
            for pol in ("A0", "A1", "A2", "A3", "A4"):
                rr = by.get((cid, pol, setting))
                if not rr:
                    continue
                status, arr = mission_outcome(rr)
                # model-scoped no-route needs the exact contact sweep: any policy with contact exhausted under A1
                if status in ("NO_ROUTE", "NO_ROUTE_PLANNING") and pol != "A0":
                    a1 = mission_outcome(by[(cid, "A1", setting if setting != "v1" else "v1")])
                    if a1[0] == "NO_ROUTE":
                        status = "NO_ROUTE_MODEL_SCOPED"
                    elif status == "NO_ROUTE" and pol == "A2":
                        status = "NO_ROUTE_PLANNING"
                r0 = rr[0]
                rec["%s_%s" % (setting, pol)] = {
                    "status": status, "arrival": arr, "lb_arrival": r0.get("lb_arrival"),
                    "optimal_planning_model": r0.get("optimal_planning_model"), "theta": r0.get("theta"),
                    "v2_full_pass": r0.get("v2_full_pass"), "v2_peak_ok": r0.get("v2_peak_ok"),
                    "v2_dose_ok": r0.get("v2_dose_ok"), "v2_contact_ok": r0.get("v2_contact_ok"),
                    "max_peak_kw_m2": r0.get("max_peak_kw_m2"), "max_dose_added_kj_m2": r0.get("max_dose_added_kj_m2"),
                    "max_dose_tdu": r0.get("max_dose_tdu"), "min_dose_margin_kj_m2": r0.get("min_dose_margin_kj_m2"),
                    "exact_own_certified": r0.get("exact_own_certified"), "engulfed_samples": r0.get("engulfed_samples"),
                    "matches_frozen": r0.get("matches_frozen"), "planner_wall_s_median":
                        float(np.median([x["planner_wall_s"] for x in rr]))}
        out[cid] = rec
    return out


def binds(m, setting, pol):
    a, b = m.get("%s_A1" % setting), m.get("%s_%s" % (setting, pol))
    if a is None or b is None:
        return None
    return (a["status"], a["arrival"]) != (b["status"], b["arrival"])


def summarize(missions):
    s = {}
    for setting in ("E100", "E23"):
        d = {}
        for pol in ("A0", "A1", "A2", "A3", "A4"):
            c = Counter(m["%s_%s" % (setting, pol)]["status"] for m in missions.values() if "%s_%s" % (setting, pol) in m)
            d[pol] = dict(c)
        d["peak_binds_missions"] = sum(bool(binds(m, setting, "A2")) for m in missions.values())
        d["dose_binds_missions"] = sum(bool(binds(m, setting, "A3")) for m in missions.values())
        d["full_differs_from_contact_missions"] = sum(bool(binds(m, setting, "A4")) for m in missions.values())
        deltas = []
        for cid, m in missions.items():
            a1, a4 = m.get("%s_A1" % setting), m.get("%s_A4" % setting)
            if a1 and a4 and a1["status"] == "CHECKED_ROUTE" and a4["status"] == "CHECKED_ROUTE" and a4["arrival"] != a1["arrival"]:
                deltas.append({"case_id": cid, "contact_arrival": a1["arrival"], "full_arrival": a4["arrival"],
                               "delta_s": a4["arrival"] - a1["arrival"]})
        d["full_policy_detours"] = deltas
        trav = [m["%s_A0" % setting] for m in missions.values()]
        d["travel_only_routes_failing_v2_full_policy"] = sum(1 for t in trav if t["v2_full_pass"] is False)
        d["travel_only_failing_by_component"] = {
            "contact": sum(1 for t in trav if t["v2_contact_ok"] is False),
            "peak": sum(1 for t in trav if t["v2_peak_ok"] is False),
            "dose": sum(1 for t in trav if t["v2_dose_ok"] is False)}
        d["contact_routes_failing_v2_thermal"] = sum(1 for m in missions.values()
                                                     if m["%s_A1" % setting]["status"] == "CHECKED_ROUTE"
                                                     and not (m["%s_A1" % setting]["v2_peak_ok"] and m["%s_A1" % setting]["v2_dose_ok"]))
        s[setting] = d
    s["v1_regression"] = {"A0_A1_executions_matching_frozen_ablation": None}
    return s


def thresholds_table(replay, study_rows):
    """Fail counts for the same routes at current and proposed thresholds (no re-planning)."""
    out = []
    for setting in ("E100", "E23"):
        recs = []
        for j in replay["journeys"]:
            for mid, r in j["v2_" + setting]["per_member"].items():
                recs.append((j["case_id"], j["legs_sha256"], r))
        journeys = defaultdict(set)
        for cid, lh, r in recs:
            key = (cid, lh)
            if r["peak_kw_m2"] > 10.0:
                journeys["peak>10"].add(key)
            if r["peak_kw_m2"] > 12.5:
                journeys["peak>12.5"].add(key)
            if r["dose_kj_m2"] > r["dose_budget_kj_m2"]:
                journeys["dose>budget"].add(key)
            if r["dose_tdu"] > 92.0:
                journeys["TDU>92"].add(key)
            if r["dose_tdu"] > 290.0:
                journeys["TDU>290"].add(key)
        out.append({"setting": setting, "routes": "18 returned journeys (15 missions)",
                    **{k: len(journeys[k]) for k in ("peak>10", "peak>12.5", "dose>budget", "TDU>92", "TDU>290")}})
        # travel-only routes of the policy study (no re-planning): same counts
        tr = [r for r in study_rows if r["setting"] == setting and r["policy"] == "A0" and r["rep"] == 1
              and r.get("max_peak_kw_m2") is not None]
        out.append({"setting": setting, "routes": "%d travel-only routes (20 missions)" % len(tr),
                    "peak>10": sum(r["max_peak_kw_m2"] > 10.0 for r in tr),
                    "peak>12.5": sum(r["max_peak_kw_m2"] > 12.5 for r in tr),
                    "dose>budget": sum(r["min_dose_margin_kj_m2"] < 0 for r in tr),
                    "TDU>92": sum(r["max_dose_tdu"] > 92.0 for r in tr),
                    "TDU>290": sum(r["max_dose_tdu"] > 290.0 for r in tr)})
    return out


def main():
    replay = json.loads((HERE / "REPLAY.json").read_text())
    study = json.loads((HERE / "POLICY_STUDY.json").read_text())
    missions = classify(study)
    summ = summarize(missions)
    v1_rows = [r for r in study["rows"] if r["setting"] == "v1"]
    summ["v1_regression"] = {"executions": len(v1_rows),
                             "matching_frozen_ablation": sum(1 for r in v1_rows if r.get("matches_frozen")),
                             "note": "own sweep, A0 and A1, both repetitions, against research/routing/final-input-ablation ROWS.csv"}
    thr = thresholds_table(replay, study["rows"])
    with open(HERE / "THRESHOLDS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(thr[0])); w.writeheader(); w.writerows(thr)
    flat = []
    for cid, m in missions.items():
        for k, v in m.items():
            if isinstance(v, dict):
                flat.append({"case_id": cid, "cohort": m["cohort"], "setting_policy": k, **v})
    with open(HERE / "MISSIONS.csv", "w", newline="") as f:
        keys = list(flat[0]); w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(flat)
    rs = replay["summary"]
    depth = None
    if (HERE / "DEPTH_COLUMN.json").exists():
        dc = json.loads((HERE / "DEPTH_COLUMN.json").read_text())
        a0 = [r for r in dc["routes"] if r["policy"] == "A0" and r["status"] == "ROUTE"]
        a1 = [r for r in dc["routes"] if r["policy"] == "A1" and r["status"] == "ROUTE"]
        depth = {"label": dc["law"],
                 "returned_journeys": dict(Counter(j["journey_status"] for j in dc["journeys"])),
                 "returned_journeys_max_peak_kw_m2": max(m["peak_kw_m2"] for j in dc["journeys"] for m in j["per_member"].values()),
                 "returned_journeys_max_added_dose_kj_m2": max(m["dose_added_kj_m2"] for j in dc["journeys"] for m in j["per_member"].values()),
                 "travel_only_routes": len(a0),
                 "travel_only_failing_full_policy": sum(1 for r in a0 if not (r["contact_ok"] and r["peak_ok"] and r["dose_ok"])),
                 "travel_only_failing_by_component": {"contact": sum(not r["contact_ok"] for r in a0),
                                                      "peak": sum(not r["peak_ok"] for r in a0),
                                                      "dose": sum(not r["dose_ok"] for r in a0)},
                 "contact_routes": len(a1),
                 "contact_routes_failing_thermal": sum(1 for r in a1 if not (r["peak_ok"] and r["dose_ok"])),
                 "scope": "fixed routes only; thermal policies A2 to A4 not re-planned under this law"}
    results = {
        "schema": "wfg.flamefront.results/1",
        "law_version": "wfg.radiation.law/2-flamefront",
        "scope": "Korean 20-mission panel only (Caldor/Rim packets not available in this container); model-relative; no field validation",
        "replay_18_journeys": rs,
        "policy_study": summ,
        "thresholds_side_by_side": thr,
        "flame_depth_column": depth,
        "physics_decision": json.loads((RES / "physics_validation/VALIDATION.json").read_text())["depth_law_decision"],
        "table_costs": study["table_costs"],
        "hosts": {"replay": replay["host"], "policy_study": study["host"]},
        "missions": missions,
    }
    (RES / "RESULTS.json").write_text(json.dumps(results, indent=1, default=str))
    figures(replay, study, missions, summ)
    print(json.dumps({"replay": rs, "study": {k: v for k, v in summ.items()}}, indent=1, default=str))


def figures(replay, study, missions, summ):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from figstyle import OKABE, apply_style, save
    apply_style(plt)
    FIG.mkdir(exist_ok=True)
    # fig02: mission outcomes per policy and law
    cats = [("CHECKED_ROUTE", "checked route", OKABE[2]), ("NO_ROUTE_MODEL_SCOPED", "model-scoped no route", OKABE[0]),
            ("NO_ROUTE_PLANNING", "no route under planning tables", OKABE[6]),
            ("ROUTE_FAILS_EXACT_CHECK", "route fails exact check", OKABE[1]),
            ("UNRESOLVED_NO_FEASIBLE_LADDER_ROUTE", "unresolved", OKABE[7]), ("INCONSISTENT_REPS", "inconsistent", OKABE[4])]
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.8), sharey=True)
    frozen = {"A0": (20, 0), "A1": (15, 5), "A2": (15, 5), "A3": (15, 5), "A4": (15, 5)}
    labels = ["travel\nonly", "contact", "contact\n+ peak", "contact\n+ dose", "full"]
    for ax, setting, title in zip(axes, ("v1", "E100", "E23"), ("law v1 (frozen ablation)", "law v2, E = 100", "law v2, E = 22.6")):
        x = np.arange(5)
        bottom = np.zeros(5)
        for key, lab, col in cats:
            vals = []
            for pol in ("A0", "A1", "A2", "A3", "A4"):
                if setting == "v1":
                    vals.append(frozen[pol][0] if key == "CHECKED_ROUTE" else (frozen[pol][1] if key == "NO_ROUTE_MODEL_SCOPED" else 0))
                else:
                    vals.append(sum(1 for m in missions.values() if m.get("%s_%s" % (setting, pol), {}).get("status") == key))
            vals = np.array(vals)
            ax.bar(x, vals, bottom=bottom, color=col, width=0.7, label=lab if setting == "E100" else None)
            bottom += vals
        if setting != "v1":
            for i, pol in enumerate(("A0", "A1", "A2", "A3", "A4")):
                if pol == "A0":
                    n = summ[setting]["travel_only_routes_failing_v2_full_policy"]
                    ax.text(i, 20.4, "%d fail\nfull v2" % n, ha="center", fontsize=6)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=6.5)
        ax.set_title(title, fontsize=8, loc="left")
        ax.set_ylim(0, 23)
    axes[0].set_ylabel("missions (of 20)")
    fig.legend(loc="lower center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    save(fig, FIG / "fig02_binding_counts")
    plt.close(fig)
    # fig04: cost of the journey check
    t = replay["timings"]
    js = sorted({x["journey"] for x in t})
    v1 = [np.median([x["wall_s"] for x in t if x["journey"] == j and x["law"] == "v1"]) for j in js]
    v2 = [np.median([x["wall_s"] for x in t if x["journey"] == j and x["law"] == "v2"]) for j in js]
    m1 = [np.max([x["tracemalloc_peak_bytes"] for x in t if x["journey"] == j and x["law"] == "v1"]) / 2**20 for j in js]
    m2 = [np.max([x["tracemalloc_peak_bytes"] for x in t if x["journey"] == j and x["law"] == "v2"]) / 2**20 for j in js]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    x = np.arange(len(js))
    axes[0].bar(x - 0.2, v1, 0.4, color=OKABE[5], label="v1 centre check (frozen copy)")
    axes[0].bar(x + 0.2, v2, 0.4, color=OKABE[1], label="v2 check, 4 members, certified")
    axes[0].axhline(30, color="0.3", ls=":", lw=0.8); axes[0].text(0, 31, "30 s request allowance", fontsize=6.5)
    axes[0].set_xlabel("returned journey (index)"); axes[0].set_ylabel("wall time, median of 2 (s)")
    axes[0].legend(fontsize=6.5, frameon=False, loc="upper left", bbox_to_anchor=(0, 0.92))
    axes[1].bar(x - 0.2, m1, 0.4, color=OKABE[5]); axes[1].bar(x + 0.2, m2, 0.4, color=OKABE[1])
    axes[1].set_xlabel("returned journey (index)"); axes[1].set_ylabel("tracemalloc peak (MiB)")
    for ax in axes:
        ax.set_xticks(x); ax.set_xticklabels([str(j) for j in js], fontsize=6)
    fig.tight_layout()
    save(fig, FIG / "fig04_cost")
    plt.close(fig)
    peak_map(plt, OKABE, save, study, missions)


def peak_map(plt, OKABE, save, study, missions):
    """fig03: road trajectory with sampled v2 flux, flame pieces at the peak time and the peak position."""
    import journey_check as JC
    import wfg_flamefront as W
    inputs = os.environ.get("WFG_ROUTING_INPUTS", "/home/user/wfg-shared/routing-inputs")
    # choose the travel-only (A0) route with the largest sampled E100 peak that is not engulfed (radiation only)
    cand = [r for r in study["rows"] if r["setting"] == "E100" and r["policy"] in ("A0", "A1") and r["rep"] == 1
            and r.get("max_peak_kw_m2") is not None]
    if not cand:
        return
    best = max(cand, key=lambda r: (r["engulfed_samples"] == 0, r["max_peak_kw_m2"]))
    case = JC.Case(inputs, best["cohort"], best["case_id"])
    import policy_sweep as PS
    P = PS.Problem(case)
    contact = PS.POLICIES[best["policy"]][0]
    r = PS.reach_sweep(P, contact=contact)
    chk = JC.check_v2(case, r["legs"], r["destination"], fuel={}, certify=False)
    k = int(np.argmax([m["peak_kw_m2"] for m in chk["per_member"].values()]))
    mid = case.member_ids[k]; rec = chk["per_member"][mid]
    pieces, arrival = JC.trajectory_pieces(case, r["legs"], r["destination"])
    T, X, Y, kinds, boxes, intervals = JC.sample_track(pieces, 0.5, 5.0)
    q, eng = W.flux_at_events(np.column_stack([X, Y]), T, case.fields[k], case.grid, None)
    tp = rec["peak_time_s"]
    fp = W.front_pieces(case.fields[k], tp)
    px, py = rec["peak_x"], rec["peak_y"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), gridspec_kw={"width_ratios": [1.15, 1]})
    for ax, half in zip(axes, (2500.0, 300.0)):
        sel = (np.abs(X - px) < half * 1.2) & (np.abs(Y - py) < half * 1.2)
        g = case.grid
        H, Wd = g.height, g.width
        x0 = g.transform[2]; y0 = g.transform[5]
        for c in range(Wd + 1):
            xx = x0 + c * g.a
            if abs(xx - px) < half:
                ax.axvline(xx - px, color="0.88", lw=0.5, zorder=0)
        for rr in range(H + 1):
            yy = y0 + rr * g.e
            if abs(yy - py) < half:
                ax.axhline(yy - py, color="0.88", lw=0.5, zorder=0)
        act = case.fields[k].active_at(tp)
        for rr, cc in zip(*np.nonzero(act)):
            cx, cy = g.centre_x(cc) - px, g.centre_y(rr) - py
            if abs(cx) < half + 200 and abs(cy) < half + 200:
                ax.add_patch(plt.Rectangle((cx - g.dx / 2, cy - g.dy / 2), g.dx, g.dy, color=OKABE[1], alpha=0.12, lw=0))
        for i in range(fp["x0"].size):
            ax.plot([fp["x0"][i] - px, fp["x1"][i] - px], [fp["y0"][i] - py, fp["y1"][i] - py], color=OKABE[6], lw=1.6)
        sc = ax.scatter(X[sel] - px, Y[sel] - py, c=np.maximum(q[sel], 1e-3), s=3, cmap="viridis",
                        norm=matplotlib_lognorm(1e-2, max(q.max(), 1.0)), zorder=3)
        ax.plot(0, 0, marker="*", color="k", ms=9, zorder=4)
        ax.set_xlim(-half, half); ax.set_ylim(-half, half); ax.set_aspect("equal")
        ax.set_xlabel("easting relative to the peak (m)")
    axes[0].set_ylabel("northing relative to the peak (m)")
    cb = fig.colorbar(sc, ax=axes, shrink=0.85, pad=0.02)
    cb.set_label("sampled incident flux, E = 100 (kW/m$^2$)")
    pol_name = {"A0": "travel-only", "A1": "contact-avoiding"}[best["policy"]]
    axes[0].set_title("%s %s route, member %d" % (best["case_id"], pol_name, k), fontsize=7.5, loc="left")
    axes[1].set_title("peak %.1f kW/m$^2$ at t = %.0f s (%s)" % (rec["peak_kw_m2"], tp, rec["peak_band"]), fontsize=7.5, loc="left")
    save(fig, FIG / "fig03_peak_positions_map")
    plt.close(fig)
    (FIG / "fig03_source.json").write_text(json.dumps({"case_id": best["case_id"], "cohort": best["cohort"],
                                                        "policy": best["policy"], "member": mid, "peak": rec,
                                                        "route_arrival": r["arrival"]}, indent=1, default=str))


def matplotlib_lognorm(lo, hi):
    from matplotlib.colors import LogNorm
    return LogNorm(vmin=lo, vmax=hi)


if __name__ == "__main__":
    main()
