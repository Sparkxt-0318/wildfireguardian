"""Equivalence counts, cost tables, RESULTS.json and figures for track 1C-2 from data/*.jsonl.

  python research/sipp-routing/analyze.py
"""
import collections
import csv
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
from wfg_members import figures as FG  # noqa: E402

C = FG.OKABE_ITO


def load(name):
    p = HERE / "data" / name
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def main():
    rows = load("cost_executions.jsonl")
    scal = load("members_scaling.jsonl")
    census = json.loads((HERE / "data" / "property_census.json").read_text())
    by = collections.defaultdict(dict)
    for r in rows:
        by[(r["region"], r["cutoff"], r["mission"], r["rep"])][r["planner"]] = r
    pairs = []
    for (region, cutoff, mission, rep), d in sorted(by.items()):
        a, b = d.get("sweep"), d.get("sipp")
        if not a or not b:
            continue
        same = (a.get("raw_status"), a.get("arrival")) == (b.get("raw_status"), b.get("arrival"))
        pairs.append({"region": region, "cutoff": cutoff, "mission": mission, "rep": rep, "sweep_status": a.get("raw_status"),
                      "sipp_status": b.get("raw_status"), "sweep_arrival": a.get("arrival"), "sipp_arrival": b.get("arrival"),
                      "identical": same, "sweep_complete_s": a.get("complete_s"), "sipp_complete_s": b.get("complete_s"),
                      "sweep_planner_s": a.get("planner_s"), "sipp_planner_s": b.get("planner_s"),
                      "sipp_build_s": b.get("build_s"), "sipp_search_s": b.get("search_s"), "sweep_setup_s": a.get("build_s"),
                      "sweep_state_seconds": a.get("states"), "sipp_pieces": b.get("pieces"), "sipp_expansions": b.get("expansions"),
                      "sweep_rss_mib": a.get("peak_rss_mib"), "sipp_rss_mib": b.get("peak_rss_mib"),
                      "ratio_planner": (b["planner_s"] / a["planner_s"]) if a.get("planner_s") and b.get("planner_s") else None,
                      "ratio_complete": (b["complete_s"] / a["complete_s"]) if a.get("complete_s") and b.get("complete_s") else None,
                      "loadavg": b.get("loadavg")})
    missions = {(p["region"], p["cutoff"], p["mission"]) for p in pairs}
    identical_missions = {m for m in missions if all(p["identical"] for p in pairs if (p["region"], p["cutoff"], p["mission"]) == m)}
    unresolved = sum(1 for r in rows if r.get("status") == "UNRESOLVED")
    ratios = [p["ratio_planner"] for p in pairs if p["ratio_planner"]]
    cratios = [p["ratio_complete"] for p in pairs if p["ratio_complete"]]
    per_region = {}
    for region in sorted({p["region"] for p in pairs}):
        ps = [p for p in pairs if p["region"] == region]
        per_region[region] = {"executions_per_solver": len(ps),
                              "sweep_planner_s_median": statistics.median(p["sweep_planner_s"] for p in ps),
                              "sipp_planner_s_median": statistics.median(p["sipp_planner_s"] for p in ps),
                              "sweep_complete_s_median": statistics.median(p["sweep_complete_s"] for p in ps),
                              "sipp_complete_s_median": statistics.median(p["sipp_complete_s"] for p in ps),
                              "sweep_rss_mib_max": max(p["sweep_rss_mib"] for p in ps), "sipp_rss_mib_max": max(p["sipp_rss_mib"] for p in ps),
                              "sipp_faster_in": sum(1 for p in ps if p["sipp_planner_s"] < p["sweep_planner_s"])}
    sc = collections.defaultdict(dict)
    for r in scal:
        sc[(r["region"], r["cutoff"], r["mission"], r["K"])][r["planner"]] = r
    scal_pairs = [(d["sipp"], d["sweep"]) for d in sc.values() if "sipp" in d and "sweep" in d]
    scal_same = sum(1 for a, b in scal_pairs if (a.get("raw_status"), a.get("arrival")) == (b.get("raw_status"), b.get("arrival")))
    res = {"equivalence": {"member_scaling_pairs": len(scal_pairs), "member_scaling_pairs_identical": scal_same,
                           "missions": len(missions), "missions_identical_both_reps": len(identical_missions),
                           "execution_pairs": len(pairs), "pairs_identical": sum(p["identical"] for p in pairs),
                           "unresolved_executions": unresolved, "random_instances": census},
           "cost": {"planner_time_ratio_sipp_over_sweep_median": statistics.median(ratios) if ratios else None,
                    "planner_time_ratio_min": min(ratios) if ratios else None, "planner_time_ratio_max": max(ratios) if ratios else None,
                    "complete_time_ratio_median": statistics.median(cratios) if cratios else None,
                    "sipp_faster_pairs": sum(1 for r in ratios if r < 1), "pairs": len(ratios), "per_region": per_region},
           "members_scaling": scal}
    (HERE / "RESULTS.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    with open(HERE / "PAIRED_EXECUTIONS.csv", "w", newline="") as f:
        if pairs:
            w = csv.DictWriter(f, fieldnames=list(pairs[0]))
            w.writeheader()
            w.writerows(pairs)
    FG.setup()
    # fig01: paired planner time
    fig, ax = FG.plt.subplots(figsize=(FG.SINGLE, 3.0))
    regions = sorted({p["region"] for p in pairs})
    for k, region in enumerate(regions):
        ps = [p for p in pairs if p["region"] == region]
        ax.scatter([p["sweep_planner_s"] for p in ps], [p["sipp_planner_s"] for p in ps], s=12, color=FG.CYCLE[k % len(FG.CYCLE)],
                   label=region.replace("_", " "))
    lim = [0.01, max([p["sweep_planner_s"] for p in pairs] + [1]) * 1.5]
    ax.plot(lim, lim, color=C["grey"], lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("frozen contact sweep (s, this host)")
    ax.set_ylabel("SIPP (s, this host)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
    FG.save(fig, HERE / "figures", "fig01_time_vs_sweep_paired")
    # fig02: pieces versus members
    if scal:
        fig, ax = FG.plt.subplots(figsize=(FG.SINGLE + 1.0, 2.8))
        keys = sorted({(r["region"], r["cutoff"], r["mission"]) for r in scal})
        for k, key in enumerate(keys):
            rs = sorted([r for r in scal if (r["region"], r["cutoff"], r["mission"]) == key and r["planner"] == "sipp" and r.get("pieces")],
                        key=lambda r: r["K"])
            if rs:
                ax.plot([r["K"] for r in rs], [r["pieces"] for r in rs], marker="osd^v"[k % 5], ms=2.5, lw=0.9,
                        ls=("-", "--", ":")[k // len(FG.CYCLE)], color=FG.CYCLE[k % len(FG.CYCLE)],
                        label="%s %s %s" % (key[0].split("_")[0], key[1][4:8], key[2]))
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xlabel("planning members K (first K export v3 trajectories)")
        ax.set_ylabel("SIPP pieces created")
        ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=6)
        FG.save(fig, HERE / "figures", "fig02_states_vs_members")
    # fig03: time breakdown on the largest panel
    ps = [p for p in pairs if p["region"] == "yeongdeok_2025" and p["rep"] == 1]
    if ps:
        fig, ax = FG.plt.subplots(figsize=(FG.SINGLE + 1.0, 2.6))
        x = np.arange(len(ps))
        labels = ["%s %s" % (p["cutoff"][4:11], p["mission"]) for p in ps]
        load_sw = [p["sweep_complete_s"] - p["sweep_planner_s"] for p in ps]
        load_si = [p["sipp_complete_s"] - p["sipp_planner_s"] for p in ps]
        ax.bar(x - 0.2, load_sw, 0.38, color=C["grey"], label="imports and input loading (JSON, packet)")
        ax.bar(x - 0.2, [p["sweep_setup_s"] or 0 for p in ps], 0.38, bottom=load_sw, color=C["sky"], label="setup (sweep static, SIPP instance)")
        ax.bar(x - 0.2, [p["sweep_planner_s"] - (p["sweep_setup_s"] or 0) for p in ps], 0.38,
               bottom=[a + (p["sweep_setup_s"] or 0) for a, p in zip(load_sw, ps)], color=C["blue"], label="search")
        ax.bar(x + 0.2, load_si, 0.38, color=C["grey"])
        ax.bar(x + 0.2, [p["sipp_build_s"] or 0 for p in ps], 0.38, bottom=load_si, color=C["sky"])
        ax.bar(x + 0.2, [(p["sipp_planner_s"] or 0) - (p["sipp_build_s"] or 0) for p in ps], 0.38,
               bottom=[a + (p["sipp_build_s"] or 0) for a, p in zip(load_si, ps)], color=C["blue"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=6)
        ax.set_ylabel("complete execution time (s, this host)")
        ax.set_xlabel("Yeongdeok missions (left bar: frozen sweep; right bar: SIPP)")
        ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False)
        FG.save(fig, HERE / "figures", "fig03_largest_panel_breakdown")
    print(json.dumps({k: res[k] for k in ("equivalence", "cost")}, indent=1, default=str))


if __name__ == "__main__":
    main()
