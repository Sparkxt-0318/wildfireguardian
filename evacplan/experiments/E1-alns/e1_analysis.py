"""E1 analysis: ``results.csv`` and ``figures/`` from the harness's result rows (``evacplan/results/*.csv``) and the
oracle results it saved (``evacplan/results/runs/e1_alns/dev-b60/*.result.json``, git-ignored). Dev rows of one host
only (default: this machine's host string). Everything here is SYNTHETIC.

    .venv/bin/python program/benchlock.py --label E1-analysis -- \
        .venv/bin/python evacplan/experiments/E1-alns/e1_analysis.py
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from evacplan import harness
from evacplan.instances import load_split

HERE = Path(__file__).resolve().parent
SET, BUDGET, METHOD = "dev", 60.0, "e1_alns"
COMPARE = ("b1_greedy", "b2_vrptw", METHOD)
LABELS = {"b1_greedy": "B1 greedy (warm start)", "b2_vrptw": "B2 OR-Tools VRPTW", METHOD: "E1 ALNS"}
COLORS = dict(zip(COMPARE, harness.SERIES_COLORS[:3]))      # the validated reference palette, slots 1-3
MARKERS = dict(zip(COMPARE, ("o", "s", "D")))
INK, INK_2, MUTED, GRID, SURFACE = harness._INK, harness._INK_2, harness._MUTED, harness._GRID, harness._SURFACE
DOSE = ("DOSE_ABOVE_BUDGET", "DOSE_UNRESOLVED")


def med(xs):
    return statistics.median(xs) if xs else None


def stat(xs) -> str:
    if not xs:
        return "–"
    m = med(xs)
    fm = f"{m:g}"
    return fm if min(xs) == max(xs) else f"{fm} [{min(xs):g}–{max(xs):g}]"


def main(host: str | None = None) -> int:
    host = host or harness.host_string()
    ids = [e.id for e in load_split().entries(SET)]
    rows = [r for r in harness.all_rows() if harness.table_key(r) == (SET, BUDGET, host) and r["instance"] in ids]
    frows = [r for r in harness.all_facility_rows() if harness.table_key(r) == (SET, BUDGET, host)]
    by = defaultdict(list)
    for r in rows:
        by[(r["method"], r["instance"])].append(r)
    e1 = sorted((r for r in rows if r["method"] == METHOD), key=lambda r: (ids.index(r["instance"]), int(r["seed"])))
    if not e1:
        print(f"no {METHOD} rows for {SET} at {BUDGET:g} s on host {host}")
        return 1
    residents, not_planned = defaultdict(int), defaultdict(int)
    for r in frows:
        if r["method"] == METHOD:
            if r["seed"] == e1[0]["seed"]:
                residents[r["instance"]] += int(r["residents"])
            not_planned[(r["instance"], int(r["seed"]))] += int(r["not_planned"])
    runs = harness.RESULTS_DIR / "runs" / METHOD / f"{SET}-b{BUDGET:g}"
    out = []
    for r in e1:
        cfg = harness.row_config(r)
        dg = cfg.get("diagnostics", {})
        seed = int(r["seed"])
        res = runs / f"{r['instance']}-s{seed}.result.json"
        dose_mnr = dose_unr = None
        if res.exists():
            pr = json.loads(res.read_text())
            dose_mnr = int(pr["model_no_route_by_reason"].get("DOSE_ABOVE_BUDGET", 0))
            dose_unr = int(pr["unresolved_by_reason"].get("DOSE_UNRESOLVED", 0))
        cut = dg.get("oracle_cut_by_cause", {})
        b1 = [float(x["delivered_checked"]) for x in by[("b1_greedy", r["instance"])]]
        b2 = [float(x["delivered_checked"]) for x in by[("b2_vrptw", r["instance"])]]
        out.append({
            "instance": r["instance"], "seed": seed, "label": "SYNTHETIC", "residents": residents[r["instance"]],
            "delivered_checked": int(r["delivered_checked"]), "unresolved": int(r["unresolved"]),
            "model_no_route": int(r["model_no_route"]), "not_planned": not_planned[(r["instance"], seed)],
            "delivered_slack_ge_5m": int(r["delivered_slack_ge_5m"]),
            "delivered_slack_ge_15m": int(r["delivered_slack_ge_15m"]),
            "delivered_slack_ge_30m": int(r["delivered_slack_ge_30m"]), "min_slack_s": r["min_slack_s"],
            "runtime_s": r["runtime_s"], "over_budget": int(float(r["runtime_s"]) > BUDGET),
            "dose_above_budget_model_no_route": dose_mnr, "dose_unresolved": dose_unr,
            "search_cut_dose": sum(v for k, v in cut.items() if k in DOSE),
            "search_cut_other": sum(v for k, v in cut.items() if k not in DOSE),
            "certified": dg.get("certified"), "warm_planned": dg.get("warm_planned"),
            "relaxed_best": dg.get("relaxed_best"), "iterations": dg.get("iterations"),
            "oracle_calls": dg.get("oracle_calls"), "certifications": dg.get("certifications"),
            "time_warm_s": dg.get("time_s", {}).get("warm_start"), "time_search_s": dg.get("time_s", {}).get("search"),
            "time_oracle_s": dg.get("time_s", {}).get("oracle"),
            "b1_median": med(b1), "b2_median": med(b2), "b2_range": f"{min(b2):g}-{max(b2):g}" if b2 else "",
            "commit": r["commit"], "host": host,
            "config": json.dumps(cfg["method"], sort_keys=True, separators=(",", ":")),
        })
    with open(HERE / "results.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    # ---------------------------------------------------------------- summary (markdown, printed)
    cmp = harness.compare_to_b2(rows, ids, set_name=SET, budget=BUDGET, host=host,
                                observations=harness.load_recorded_observations())
    totals = {m: harness.seed_totals([r for r in rows if r["method"] == m], "delivered_checked", ids) for m in COMPARE}
    print(f"host: {host}")
    print(cmp.bar_line())
    print(f"verdict e1_alns: {cmp.verdicts.get(METHOD)}")
    for m in COMPARE:
        t = list(totals[m].values())
        print(f"{m}: per-seed totals {totals[m]}; median {stat(t)}; worst {min(t) if t else '–'}")
    cols = ("delivered_checked", "unresolved", "model_no_route", "not_planned", "delivered_slack_ge_5m",
            "delivered_slack_ge_15m", "delivered_slack_ge_30m", "over_budget", "search_cut_dose",
            "dose_above_budget_model_no_route", "dose_unresolved")
    seeds = sorted({o["seed"] for o in out})
    print("\n| quantity (sum over the 10 dev instances, per seed) | median [min–max] |\n|---|---|")
    for c in cols:
        per = [sum((o[c] or 0) for o in out if o["seed"] == s) for s in seeds]
        print(f"| {c} | {stat(per)} |")
    ms = [float(o["min_slack_s"]) for o in out if o["min_slack_s"] not in ("", None)]
    print(f"| min slack over all rows (s) | {min(ms) if ms else '–'} |")
    print("\n| instance | residents | B1 median | B2 median [min–max] | E1 median [min–max] | E1 − B2 (medians) | "
          "E1 iterations median | E1 oracle calls median |\n|---|---|---|---|---|---|---|---|")
    for i in ids:
        oi = [o for o in out if o["instance"] == i]
        b2 = [float(x["delivered_checked"]) for x in by[("b2_vrptw", i)]]
        b1 = [float(x["delivered_checked"]) for x in by[("b1_greedy", i)]]
        e = [o["delivered_checked"] for o in oi]
        diff = (med(e) - med(b2)) if (e and b2) else None
        print(f"| {i} | {residents[i]} | {stat(b1)} | {stat(b2)} | {stat(e)} | "
              f"{'–' if diff is None else f'{diff:+g}'} | {med([o['iterations'] for o in oi])} | "
              f"{med([o['oracle_calls'] for o in oi])} |")
    figures(out, by, ids, residents, totals, cmp, host)
    return 0


def figures(out, by, ids, residents, totals, cmp, host) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    def style(ax):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(harness._AXIS)
        ax.tick_params(colors=MUTED, labelcolor=INK_2)
        ax.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)

    # 1) share of residents delivered per instance: medians with the min-max over seeds
    fig = Figure(figsize=(8.6, 5.2), dpi=100, facecolor=SURFACE)
    ax = fig.add_subplot(1, 1, 1)
    style(ax)
    ys = list(range(len(ids)))[::-1]
    off = {"b1_greedy": 0.22, "b2_vrptw": 0.0, METHOD: -0.22}
    for m in COMPARE:
        for y, i in zip(ys, ids):
            vals = [float(x["delivered_checked"]) for x in by[(m, i)]]
            if not vals or not residents[i]:
                continue
            lo, mi, hi = (100 * v / residents[i] for v in (min(vals), med(vals), max(vals)))
            if hi > lo:
                ax.plot([lo, hi], [y + off[m]] * 2, color=COLORS[m], linewidth=2, solid_capstyle="round", zorder=2)
            ax.plot([mi], [y + off[m]], marker=MARKERS[m], markersize=8, color=COLORS[m], markeredgecolor=SURFACE,
                    markeredgewidth=1.2, linestyle="none", zorder=3, label=LABELS[m] if y == ys[0] else None)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{i.replace('SYNTHETIC-', '')} ({residents[i]})" for i in ids], color=INK_2)
    ax.set_xlabel("residents delivered, % of the instance's residents (median over seeds; line = min–max)",
                  color=INK_2)
    ax.set_xlim(0, 102)
    ax.legend(loc="lower left", frameon=False, labelcolor=INK_2)
    ax.set_title(f"SYNTHETIC dev instances, 60 s, 5 seeds: E1 vs B1 and B2 (host {host_tag(host)})",
                 color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    FigureCanvasAgg(fig).print_png(str(HERE / "figures" / "e1_by_instance.png"))

    # 2) per-seed totals against the bar for beating B2
    fig = Figure(figsize=(7.2, 4.4), dpi=100, facecolor=SURFACE)
    ax = fig.add_subplot(1, 1, 1)
    style(ax)
    for x, m in enumerate(COMPARE):
        t = sorted(totals[m].values())
        if t:
            ax.plot([x] * len(t), t, marker=MARKERS[m], markersize=8, color=COLORS[m], markeredgecolor=SURFACE,
                    markeredgewidth=1.2, linestyle="none", zorder=3)
            ax.annotate(f"worst {min(t):g}", (x, min(t)), xytext=(10, -4), textcoords="offset points",
                        color=INK_2, fontsize=9)
    if cmp.bar is not None:
        ax.axhline(cmp.bar, color=INK_2, linewidth=1.2, linestyle="--", zorder=2)
        ax.annotate(f"bar for beating B2: {cmp.bar:g}", (len(COMPARE) - 0.5, cmp.bar), xytext=(0, 4),
                    textcoords="offset points", ha="right", color=INK_2, fontsize=9)
    ax.set_xticks(range(len(COMPARE)))
    ax.set_xticklabels([LABELS[m] for m in COMPARE], color=INK_2)
    ax.set_xlim(-0.5, len(COMPARE) - 0.5)
    ax.set_ylabel("residents delivered, sum over the 10 dev instances", color=INK_2)
    ax.set_title(f"SYNTHETIC dev set, 60 s: per-seed totals (seeds 0-4), host {host_tag(host)}", color=INK,
                 fontsize=11, loc="left")
    fig.tight_layout()
    FigureCanvasAgg(fig).print_png(str(HERE / "figures" / "e1_seed_totals.png"))


def host_tag(host: str) -> str:
    return host.split(", ")[-1].rstrip(")") if "vm boot" in host else host.split(" (")[0]


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
