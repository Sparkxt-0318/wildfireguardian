"""Summaries, RESULTS.json, CSV tables and figures for track 1C-1 from data/decisions*.jsonl and data/reduction_costs*.jsonl.

  python research/scenario-members/analyze.py [--exports /path/exports_v3]
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members"))
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import figures as FG  # noqa: E402
from wfg_members import kit  # noqa: E402

C = FG.OKABE_ITO
ORDER = ["v1", "v2_first4_uniform", "v2_first4_ordered"] + ["v2_%s_K%d" % (m, k) for k in (8, 16, 32)
                                                            for m in ("first_k", "forward_selection", "k_medoids")]


def load(pattern):
    rows = []
    for p in sorted(glob.glob(str(HERE / "data" / pattern))):
        with open(p) as f:
            rows += [json.loads(l) for l in f]
    return rows


def outcome_table(rows):
    out = []
    for ms in ORDER:
        for rule in ("all", "k_of_m"):
            rs = [r for r in rows if r["member_set"] == ms and r["rule"] == rule]
            if not rs:
                continue
            v = collections.Counter(r["verdict"] for r in rs)
            arr = [r["arrival_s"] for r in rs if r["arrival_s"] is not None]
            cov = [r["coverage_all_N"] for r in rs if r["coverage_all_N"] is not None]
            bind_contact = sum(1 for r in rs if (r["binding"] or {}).get("contact"))
            bind_window = sum(1 for r in rs if (r["binding"] or {}).get("destination_window"))
            bind_dose = sum(1 for r in rs if (r["binding"] or {}).get("dose"))
            out.append({"member_set": ms, "rule": rule, "missions": len(rs), "K_members_median": statistics.median(r["K_members"] for r in rs),
                        "checked_route": v.get("checked_route", 0), "model_no_route": v.get("model_no_route", 0),
                        "unresolved": v.get("unresolved", 0), "arrival_s_median": statistics.median(arr) if arr else None,
                        "arrival_s_sum": sum(arr) if arr else None,
                        "decision_wall_s_median": statistics.median(r["decision_wall_s"] for r in rs),
                        "decision_wall_s_max": max(r["decision_wall_s"] for r in rs),
                        "coverage_mean": statistics.fmean(cov) if cov else None, "coverage_min": min(cov) if cov else None,
                        "binding_contact": bind_contact, "binding_destination_window": bind_window, "binding_dose": bind_dose,
                        "k_of_m_identical_to_all": sum(1 for r in rs if "K_OF_M_EQUALS_ALL" in str(r["reason"]))})
    return out


def per_mission(rows):
    out = collections.defaultdict(dict)
    for r in rows:
        out["%s %s %s" % (r["region"], r["cutoff"], r["mission"])]["%s/%s" % (r["member_set"], r["rule"])] = (
            r["verdict"], r["arrival_s"], None if r["coverage_all_N"] is None else round(r["coverage_all_N"], 4))
    return out


def cost_table(costs):
    out = []
    for d in ("edge_arrival", "first_burn_l1", "road_symdiff"):
        for m in ("first_k", "forward_selection", "k_medoids"):
            for K in (4, 8, 16, 32):
                rs = [r for r in costs if r["distance"] == d and r["method"] == m and r["K"] == K and r["max_distance"] > 0]
                if not rs:
                    continue
                out.append({"distance": d, "method": m, "K": K, "windows_with_variation": len(rs),
                            "cost_mean": statistics.fmean(r["cost"] for r in rs),
                            "cost_with_extremes_mean": statistics.fmean(r["cost_with_extremes"] for r in rs),
                            "relative_to_first_k_K4": None, "extremes_appended_mean": statistics.fmean(r["extremes"] for r in rs),
                            "distinct_trajectories_mean": statistics.fmean(r["distinct_trajectories"] for r in rs)})
    base = {(r["distance"]): r["cost_mean"] for r in out if r["method"] == "first_k" and r["K"] == 4}
    for r in out:
        if base.get(r["distance"]):
            r["relative_to_first_k_K4"] = r["cost_mean"] / base[r["distance"]]
    return out


def smallest_k(rows):
    """Per method: smallest K whose mean coverage of checked routes is within 1 and 2 percentage points of K = 32."""
    out = {}
    for m in ("first_k", "forward_selection", "k_medoids"):
        cov = {}
        for K in (8, 16, 32):
            rs = [r["coverage_all_N"] for r in rows if r["member_set"] == "v2_%s_K%d" % (m, K) and r["rule"] == "all"
                  and r["coverage_all_N"] is not None]
            cov[K] = statistics.fmean(rs) if rs else None
        if cov.get(32) is None:
            continue
        out[m] = {"coverage_mean": cov,
                  "within_1pp": next((K for K in (8, 16, 32) if cov[K] is not None and cov[32] - cov[K] <= 0.01), None),
                  "within_2pp": next((K for K in (8, 16, 32) if cov[K] is not None and cov[32] - cov[K] <= 0.02), None)}
    return out


def fig_members(exports, out):
    import bridge_v2 as B2
    region, tag, event = "uiseong_andong_2025", "20250325T170000Z", "KFS_01"
    p = kit.paths(region, tag, event)
    with np.load(p["packet"] / "constructed_arrays.npz") as a:
        v1 = a["ignition_time_s"][0].copy()
        cur = a["current_active"].copy()
    win = B2.frozen_window(p["packet"])
    with np.load(Path(exports) / event / ("FORECAST_%s.npz" % tag)) as z:
        fbh = z["trajectory_first_burn_hour"]
    v2u = B2.ignition_seconds(fbh, [0], timing="uniform")[0]
    v2o = B2.ignition_seconds(fbh, [0], timing="ordered")[0]
    v2u = v2u[win["r0"]:win["r1"] + 1, win["c0"]:win["c1"] + 1]
    v2o = v2o[win["r0"]:win["r1"] + 1, win["c0"]:win["c1"] + 1]
    FG.setup()
    fig, axes = FG.plt.subplots(1, 3, figsize=(FG.DOUBLE, 2.7), sharey=True)
    cmap = FG.plt.get_cmap("cividis").copy()
    for ax, arr, title in zip(axes, (v1, v2u, v2o), ("v1 member 0, independent", "v2 trajectory 0, uniform",
                                                      "v2 trajectory 0, ordered")):
        bg = np.where(cur, 1.0, np.nan)
        ax.imshow(bg, cmap="Greys", vmin=0, vmax=2, interpolation="nearest")
        im = ax.imshow(np.where(np.isfinite(arr), arr, np.nan), cmap=cmap, vmin=0, vmax=3600, interpolation="nearest")
        ys, xs = np.nonzero(np.isfinite(arr))
        ax.scatter(xs, ys, s=14, facecolors="none", edgecolors=C["vermillion"], linewidths=0.6)
        ax.set_title(title)
        ax.set_xlabel("window column (375 m cells)")
    axes[0].set_ylabel("window row (375 m cells, north up)")
    cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.01)
    cb.set_label("first-new ignition second after the cutoff (s)")
    return FG.save(fig, out, "fig01_member_examples")


def fig_costs(ct, out):
    FG.setup()
    fig, axes = FG.plt.subplots(1, 3, figsize=(FG.DOUBLE, 2.4))
    names = {"edge_arrival": "edge-arrival distance (m s)", "first_burn_l1": "first-burn-hour L1 (cells)",
             "road_symdiff": "road-weighted symmetric difference"}
    cols = {"first_k": C["grey"], "forward_selection": C["blue"], "k_medoids": C["orange"]}
    for ax, d in zip(axes, names):
        for m, col in cols.items():
            rs = sorted([r for r in ct if r["distance"] == d and r["method"] == m], key=lambda r: r["K"])
            if rs:
                ax.plot([r["K"] for r in rs], [r["cost_mean"] for r in rs], marker="o", ms=3, color=col, label=m.replace("_", " "))
        ax.set_xscale("log", base=2)
        ax.set_xticks([4, 8, 16, 32])
        ax.set_xticklabels(["4", "8", "16", "32"])
        ax.set_xlabel("retained members K")
        ax.set_title(names[d])
    axes[0].set_ylabel("reduction cost D_J (mean over windows)")
    axes[-1].legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    fig.tight_layout()
    return FG.save(fig, out, "fig02_reduction_cost_vs_k")


def fig_outcomes(tab, out):
    FG.setup()
    fig, ax = FG.plt.subplots(figsize=(FG.DOUBLE, 3.0))
    labels = ["%s\n%s" % (r["member_set"].replace("v2_", "").replace("forward_selection", "fs").replace("k_medoids", "kmed")
                         .replace("first_k", "first").replace("first4_", "K4 "), r["rule"]) for r in tab]
    x = np.arange(len(tab))
    a = np.array([r["checked_route"] for r in tab])
    b = np.array([r["model_no_route"] for r in tab])
    c = np.array([r["unresolved"] for r in tab])
    ax.bar(x, a, color=C["green"], label="checked route")
    ax.bar(x, b, bottom=a, color=C["blue"], label="model-scoped no-route")
    ax.bar(x, c, bottom=a + b, color=C["vermillion"], label="unresolved")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=5, rotation=90)
    ax.set_ylabel("missions (of 20)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    return FG.save(fig, out, "fig03_outcomes_vs_k_and_rule")


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", default="/home/user/wfg-artifacts-1c/exports_v3")
    a = ap.parse_args()
    rows = load("decisions*.jsonl")
    costs = load("reduction_costs*.jsonl")
    tab = outcome_table(rows)
    ct = cost_table(costs)
    res = {"outcomes": tab, "reduction_costs": ct, "smallest_k": smallest_k(rows), "per_mission": per_mission(rows),
           "rows": len(rows), "cost_rows": len(costs)}
    (HERE / "RESULTS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    write_csv(HERE / "OUTCOMES.csv", tab)
    write_csv(HERE / "REDUCTION_COSTS.csv", ct)
    flat = [{k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items() if k != "per_member"} for r in rows]
    write_csv(HERE / "DECISIONS.csv", flat)
    fig_members(a.exports, HERE / "figures")
    if ct:
        fig_costs(ct, HERE / "figures")
    if tab:
        fig_outcomes(tab, HERE / "figures")
    print(json.dumps(tab, indent=0, default=str)[:3000])


if __name__ == "__main__":
    main()
