#!/usr/bin/env python3
"""E3 scenario robustness, analysis step: per-plan and pooled out-of-sample violation, violation vs K and vs
in-sample safety slack, the scenario-approach bounds, the margin recommendation, CSVs and figures.

Reads the raw records of ``e3_compute.py`` (``evacplan/runs/E3-scenario-robustness/``) and writes
``results.csv``, ``by_K.csv``, ``by_margin.csv``, ``by_slack_bin.csv``, ``recommendation.csv`` and ``figures/``
next to this file; prints the README tables. Run from the worktree root inside the bench lock (rule 6):

    .venv/bin/python program/benchlock.py --label E3-analyze -- \\
        .venv/bin/python evacplan/experiments/E3-scenario-robustness/e3_analyze.py

Only reads oracle outputs recorded by the compute step (rule 3). SYNTHETIC everywhere (rule 7).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

EXP_DIR = Path(__file__).resolve().parent
EVACPLAN_DIR = EXP_DIR.parents[1]
REPO_DIR = EVACPLAN_DIR.parent
CONFIG_PATH = EXP_DIR / "config.yaml"
RUNS_DIR = EVACPLAN_DIR / "runs" / "E3-scenario-robustness"
sys.path.insert(0, str(EXP_DIR))
import e3_stats as st  # noqa: E402

LABEL = "SYNTHETIC"
MARGINS_MIN = (0, 1, 2, 5, 10, 15, 20, 30, 45, 60)      # evacplan.harness.MARGINS_MIN
FIG_DIR = EXP_DIR / "figures"
GENERATED = ("results.csv", "by_K.csv", "by_margin.csv", "by_slack_bin.csv", "recommendation.csv", "figures")


def size_of(iid: str) -> str:
    return iid.split("-")[1]


def git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_DIR, capture_output=True, text=True, check=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "evacplan", "hazard_contract", "program"],
                           cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout
    dirty = [ln for ln in dirty.splitlines() if "evacplan/runs/" not in ln and not any(
        ("E3-scenario-robustness/" + g) in ln for g in GENERATED)]
    return out.stdout.strip() + ("+dirty" if dirty else "")


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _load_all(runs_dir: Path):
    plans = {(r["instance"], r["plan"]): r for r in _jsonl(runs_dir / "plans.jsonl")}
    support = {(r["instance"], r["plan"]): r for r in _jsonl(runs_dir / "support.jsonl")}
    checks: dict[tuple, dict[int, dict]] = defaultdict(dict)
    for r in _jsonl(runs_dir / "checks.jsonl"):
        checks[(r["instance"], r["plan"])][r["c"]] = r
    return plans, support, checks


def plan_outcomes(plan: dict, recs: dict[int, dict]) -> dict:
    """Per plan: the in-sample delivered trips and, per fresh member, which of them are not checked there."""
    trips = plan["trips"]
    deliv = [i for i, t in enumerate(trips) if t["slack_s"] is not None]
    cs = sorted(recs)
    fail = np.zeros((len(cs), len(trips)), dtype=bool)
    cause_of: dict[tuple[int, int], str] = {}
    for a, c in enumerate(cs):
        r = recs[c]
        if len(r["states"]) != len(trips):
            raise AssertionError(f"{plan['instance']}/{plan['plan']}: trip count differs in member {c}")
        for i in deliv:
            if r["states"][i] != "0":
                fail[a, i] = True
                cause_of[(c, i)] = r["causes"].get(str(i)) or "?"
    n = np.array([t["n"] for t in trips], dtype=float)
    slack = np.array([t["slack_s"] if t["slack_s"] is not None else np.nan for t in trips], dtype=float)
    return {"cs": cs, "fail": fail, "deliv": deliv, "n": n, "slack": slack, "cause_of": cause_of}


def cmd_analyze(args) -> int:
    global FIG_DIR
    if os.environ.get("EVACPLAN_MILESTONE"):
        raise SystemExit("refused: EVACPLAN_MILESTONE is set; E3 uses the dev set only (program rule 5)")
    cfg = yaml.safe_load(Path(args.config or CONFIG_PATH).read_text())
    runs_dir = Path(args.runs_dir) if args.runs_dir else RUNS_DIR
    out_dir = Path(args.out_dir) if args.out_dir else EXP_DIR
    FIG_DIR = out_dir / "figures"
    plans, support, checks = _load_all(runs_dir)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    commit = git_head()
    runs = _jsonl(runs_dir / "runs.jsonl")
    hosts = sorted({r["host"] for r in plans.values()} | {r["host"] for r in runs})
    compute_commits = sorted({r["commit"] for r in plans.values()})
    beta = float(cfg["statistics"]["beta"])
    conf = float(cfg["statistics"]["confidence"])
    cfg_json = json.dumps({"members": cfg["members"], "planner": cfg["planner"], "beta": beta, "confidence": conf,
                           "clusters": "instance x fresh member"}, sort_keys=True, separators=(",", ":"))
    host = hosts[0] if len(hosts) == 1 else " | ".join(hosts)
    common = {"compute_commit": " ".join(compute_commits), "analysis_commit": commit, "seed": "none",
              "config": cfg_json, "host": host}
    outs = {key: plan_outcomes(plans[key], recs) for key, recs in checks.items() if key in plans}

    # ---- per plan
    rows = []
    for (iid, pid), o in sorted(outs.items(), key=lambda kv: (["S", "M", "L"].index(size_of(kv[0][0])), kv[0])):
        pl = plans[(iid, pid)]
        r = _rate([((iid, pid), o)], conf)
        sp = support.get((iid, pid))
        K = int(pl["K"])
        rows.append({
            "instance": iid, "size": size_of(iid), "label": LABEL, "plan": pid, "arm": pl["arm"], "K": K,
            "method": pl["method"], "planning_members": " ".join(map(str, pl["members"])),
            "delivered_in_sample": pl["delivered"], "unresolved_in_sample": pl["unresolved"],
            "min_slack_s": pl["min_slack_s"], "n_fresh": len(o["cs"]),
            "plan_violations": r["plan_violations"], "plan_rate": r["plan_rate"], "plan_lo": r["plan_lo"],
            "plan_hi": r["plan_hi"], "resident_member_pairs": r["pairs"], "resident_violations": r["violations"],
            "resident_rate": r["rate"], "resident_kg_lo": r["kg_lo"], "resident_kg_hi": r["kg_hi"],
            "resident_kish_lo": r["kish_lo"], "resident_kish_hi": r["kish_hi"], "causes": r["causes"],
            "support_size": sp["s"] if sp else "", "support_members": " ".join(map(str, sp["support"])) if sp else "",
            "eps_nonconvex": st.eps_nonconvex(sp["s"], K, beta) if sp else "",
            "eps_wait_and_judge": st.eps_wait_and_judge(sp["s"], K, beta) if sp else "",
            "s_over_K1": sp["s"] / (K + 1) if sp else "", "runtime_s": pl["runtime_s"],
            "b2_diagnostics": json.dumps(pl.get("diagnostics") or {}, sort_keys=True) if pl["method"] == "b2_vrptw" else "",
            **common})
    _write_csv(out_dir / "results.csv", rows)

    # ---- pooled by arm and K. Primary: the core plans on check members 0-31 of the instances where every core
    # plan was checked on all of them; secondary: every plan and member available.
    core = ("A1-g0", "A2-g0", "A4-g0", "A8-g0", "B8-g0", "B16-g0", "B32-g0")
    cmax = 32
    complete = sorted({iid for (iid, _) in outs
                       if all((iid, pid) in outs and set(range(cmax)) <= set(outs[(iid, pid)]["cs"]) for pid in core)})
    by_k = []
    for scope in ("primary", "all"):
        for (arm, K) in sorted({(r["arm"], r["K"]) for r in rows if r["arm"] in ("A", "B")}, key=lambda t: (t[0], t[1])):
            for size in ("all", "S", "M", "L"):
                sel = [(k, o) for k, o in outs.items() if plans[k]["arm"] == arm and int(plans[k]["K"]) == K
                       and (size == "all" or size_of(k[0]) == size)
                       and (scope == "all" or (k[1] in core and k[0] in complete))]
                if not sel:
                    continue
                r = _rate(sel, conf, cmax=cmax if scope == "primary" else None)
                by_k.append({"scope": scope, "arm": arm, "K": K, "size": size, "label": LABEL,
                             "instances": len({k[0] for k, _ in sel}), **r, **common})
    _write_csv(out_dir / "by_K.csv", by_k)

    # ---- margins (cumulative slack >= m) and slack bins
    sets = {"B1 A8 (instance members, K=8)": lambda k: k[1] == "A8-g0",
            "B2 (instance members, K=8)": lambda k: k[1] == "B2-A8",
            "B1 B8 (fresh planning members, K=8)": lambda k: k[1].startswith("B8-"),
            "all K=8 plans": lambda k: int(plans[k]["K"]) == 8}
    fine = list(range(0, 121))
    by_margin, bins_rows, curves = [], [], {}
    edges_min = [0, 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120, math.inf]
    for name, pick in sets.items():
        sel = [(k, o) for k, o in outs.items() if pick(k)]
        if not sel:
            continue
        total = sum(float(o["n"][o["deliv"]].sum()) for _, o in sel)
        curve = []
        for m in fine:
            r = _rate(sel, conf, lo_s=60.0 * m)
            r.update(set=name, margin_min=m, delivered_fraction=r["residents"] / total if total else math.nan,
                     upper=max(r["kg_hi"], r["kish_hi"]) if r["residents"] else math.nan)
            curve.append(r)
            if m in MARGINS_MIN or m in (90, 120):
                by_margin.append({"set": name, "label": LABEL, "margin_min": m, "instances": len({k[0] for k, _ in sel}),
                                  **{k: v for k, v in r.items() if k not in ("set", "margin_min")}, **common})
        curves[name] = curve
        for lo, hi in zip(edges_min[:-1], edges_min[1:]):
            r = _rate(sel, conf, lo_s=60.0 * lo, hi_s=60.0 * hi)
            bins_rows.append({"set": name, "label": LABEL, "slack_from_min": lo, "slack_to_min": hi, **r, **common})
    _write_csv(out_dir / "by_margin.csv", by_margin)
    _write_csv(out_dir / "by_slack_bin.csv", bins_rows)

    # ---- recommendation. Pre-registered rule: primary set, U = max(Korn-Graubard, Kish) upper end of the
    # two-sided 95 % CP interval <= alpha, smallest m of the harness grid. Sensitivity (not the rule):
    # Korn-Graubard alone.
    rec_rows = []
    prim = "B1 A8 (instance members, K=8)"
    for name in curves:
        for alpha in cfg["statistics"]["alphas"]:
            for bound in ("max(KG, Kish) [pre-registered]", "KG only [sensitivity]"):
                pick = None
                for r in by_margin:
                    if r["set"] != name or r["margin_min"] not in MARGINS_MIN or not r["residents"]:
                        continue
                    u = max(r["kg_hi"], r["kish_hi"]) if bound.startswith("max") else r["kg_hi"]
                    if u <= alpha:
                        pick = (r, u)
                        break
                rec_rows.append({"set": name, "primary": name == prim, "alpha": alpha, "bound": bound, "label": LABEL,
                                 "margin_min": pick[0]["margin_min"] if pick else "none <= 60",
                                 "rate": pick[0]["rate"] if pick else "", "upper": pick[1] if pick else "",
                                 "residents_kept": pick[0]["residents"] if pick else "",
                                 "delivered_fraction": pick[0]["delivered_fraction"] if pick else "",
                                 "contact_share": pick[0]["share_contact"] if pick else "", **common})
    _write_csv(out_dir / "recommendation.csv", rec_rows)

    _figures(rows, by_k, curves, bins_rows, outs, plans, support, cfg, beta)
    _print_tables(rows, by_k, by_margin, bins_rows, rec_rows, support, plans, outs, beta, complete)
    return 0


def _rate(sel, conf: float, lo_s: float = -math.inf, hi_s: float = math.inf, cmax: int | None = None) -> dict:
    """Out-of-sample violation of the in-sample delivered residents of the selected plans whose slack is in
    [lo_s, hi_s) (1 us tolerance, as the harness), over the plans' checked fresh members (only c < cmax if given).

    Per-resident rate: each plan weighs its residents equally whatever the number of members it was checked
    against (a (plan, member) pair counts 1/N_plan), clusters = (instance, fresh member) for the intervals.
    Plan-level rate: (plan, member) pairs in which at least one counted resident fails; exact CP over the pairs
    (i.i.d. members within a plan; plans of one instance share members, so pooled plan-level intervals are
    descriptive)."""
    xs: dict[tuple, float] = defaultdict(float)
    ns: dict[tuple, float] = defaultdict(float)
    residents, pairs, xp, npairs, plans_n = 0.0, 0.0, 0, 0, 0
    causes: dict[str, float] = defaultdict(float)
    for (iid, pid), o in sel:
        idx = [a for a, c in enumerate(o["cs"]) if cmax is None or c < cmax]
        d = [i for i in o["deliv"] if lo_s - 1e-6 <= o["slack"][i] < hi_s - 1e-6]
        if not idx:
            continue
        plans_n += 1
        if not d:
            continue
        w = o["n"][d]
        N = len(idx)
        residents += float(w.sum())
        pairs += float(w.sum()) * N
        for a in idx:
            c = o["cs"][a]
            f = o["fail"][a, d]
            xs[(iid, c)] += float((f * w).sum()) / N
            ns[(iid, c)] += float(w.sum()) / N
            xp += int(f.any())
            npairs += 1
            for i in np.flatnonzero(f):
                causes[o["cause_of"].get((c, d[i]), "?")] += float(w[i]) / N
    keys = sorted(xs)
    rc = st.cluster_ci([xs[k] for k in keys], [ns[k] for k in keys], pairs=pairs, conf=conf)
    lo, hi = st.clopper_pearson(xp, npairs, conf) if npairs else (math.nan, math.nan)
    tot = sum(causes.values())
    return {"plans": plans_n, "residents": residents, "pairs": pairs, "violations": rc.get("violations", 0.0),
            "rate": rc["rate"], "naive_lo": rc["naive_lo"], "naive_hi": rc["naive_hi"], "kg_lo": rc["kg_lo"],
            "kg_hi": rc["kg_hi"], "kish_lo": rc["kish_lo"], "kish_hi": rc["kish_hi"], "n_eff_kg": rc["n_eff_kg"],
            "n_eff_kish": rc["n_eff_kish"], "deff": rc["deff"], "clusters": rc["clusters"],
            "plan_member_pairs": npairs, "plan_violations": xp, "plan_rate": xp / npairs if npairs else math.nan,
            "plan_lo": lo, "plan_hi": hi,
            "share_contact": causes.get("FLAME_CONTACT", 0.0) / tot if tot else math.nan,
            "causes": json.dumps({k: round(v, 2) for k, v in sorted(causes.items())})}


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    cols = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in cols:
                cols.append(k)

    def fmt(v):
        if isinstance(v, float):
            return "" if not math.isfinite(v) else f"{v:.6g}"
        return v

    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(r.get(k, "")) for k in cols})


# ---------------------------------------------------------------------------------- figures
def _figures(rows, by_k, curves, bins_rows, outs, plans, support, cfg, beta) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["tab:blue", "tab:green", "tab:orange", "tab:gray"]
    # 1. violation vs K (primary scope: core plans, check members 0-31, instances with every core plan)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=110)
    for arm, color, lab in (("A", "tab:blue", "arm A: planning members = the instance's members"),
                            ("B", "tab:orange", "arm B: planning members = fresh draws")):
        pts = sorted((r["K"], r) for r in by_k if r["scope"] == "primary" and r["arm"] == arm and r["size"] == "all")
        if not pts:
            continue
        ks = [k for k, _ in pts]
        for ax, key, lo, hi in ((axes[0], "rate", "kg_lo", "kg_hi"), (axes[1], "plan_rate", "plan_lo", "plan_hi")):
            y = np.array([r[key] for _, r in pts], dtype=float)
            yl = np.array([r[lo] for _, r in pts], dtype=float)
            yh = np.array([r[hi] for _, r in pts], dtype=float)
            ax.errorbar(ks, y, yerr=[np.maximum(y - yl, 0), np.maximum(yh - y, 0)], marker="o", color=color,
                        capsize=3, label=lab)
    sup_pts = defaultdict(list)
    for (iid, pid), sp in support.items():
        if (iid, pid) in outs:
            sup_pts[int(sp["K"])].append(sp["s"])
    if sup_pts:
        ks = sorted(sup_pts)
        axes[1].plot(ks, [np.mean(sup_pts[k]) / (k + 1) for k in ks], "k--", lw=1, label="mean s*/(K+1)")
        axes[1].plot(ks, [np.median([st.eps_nonconvex(x, k, beta) for x in sup_pts[k]]) for k in ks], "k:", lw=1,
                     label=f"median scenario bound eps(s*), beta = {beta:g}")
    for ax, t in ((axes[0], "per delivered resident (95% Korn-Graubard CP)"),
                  (axes[1], "per plan: any delivered resident fails (95% CP)")):
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 2, 4, 8, 16, 32])
        ax.set_xticklabels(["1", "2", "4", "8", "16", "32"])
        ax.set_xlabel("K (planning members)")
        ax.set_ylabel("out-of-sample violation rate")
        ax.set_title(t, fontsize=9)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.suptitle("SYNTHETIC dev instances: out-of-sample violation vs K (B1; fresh members of each instance's "
                 "own hazard model)", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "violation_vs_K.png")
    plt.close(fig)

    # 2. violation vs required margin (cumulative), with the share of delivered residents kept
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=110)
    for (name, curve), color in zip(curves.items(), colors):
        m = np.array([c["margin_min"] for c in curve], dtype=float)
        y = np.array([c["rate"] for c in curve], dtype=float)
        u = np.array([c["upper"] for c in curve], dtype=float)
        f = np.array([c["delivered_fraction"] for c in curve], dtype=float)
        axes[0].plot(m, y, color=color, label=name)
        axes[0].plot(m, u, color=color, ls="--", lw=0.8)
        axes[1].plot(m, f, color=color, label=name)
    for a_ in (0.05, 0.01):
        axes[0].axhline(a_, color="red", lw=0.6, ls=":")
    axes[0].set_ylabel("violation of residents with slack >= m\n(solid: rate; dashed: 95% upper bound max(KG, Kish))")
    axes[1].set_ylabel("share of delivered residents with slack >= m")
    for ax in axes:
        ax.set_xlabel("required margin m (min of in-sample safety slack, ASSUMPTIONS #91)")
        ax.grid(alpha=0.3)
        ax.set_xlim(0, 120)
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=7)
    fig.suptitle("SYNTHETIC dev instances: out-of-sample violation and delivered share vs required margin", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "violation_vs_margin.png")
    plt.close(fig)

    # 3. per slack bin
    fig, ax = plt.subplots(figsize=(8, 4), dpi=110)
    names = list(curves)
    width = 0.8 / max(1, len(names))
    labels = None
    for i, name in enumerate(names):
        rr = [r for r in bins_rows if r["set"] == name]
        labels = [f"{r['slack_from_min']}-{r['slack_to_min']}" if math.isfinite(r["slack_to_min"])
                  else f">={r['slack_from_min']}" for r in rr]
        y = np.array([r["rate"] if r["residents"] else np.nan for r in rr], dtype=float)
        ax.bar(np.arange(len(rr)) + i * width, y, width, color=colors[i % len(colors)], label=name)
    if labels:
        ax.set_xticks(np.arange(len(labels)) + 0.4 - width / 2)
        ax.set_xticklabels(labels, rotation=45, fontsize=7)
    ax.set_xlabel("in-sample safety slack bin (min)")
    ax.set_ylabel("out-of-sample violation rate")
    ax.set_title("SYNTHETIC dev instances: violation by in-sample slack bin", fontsize=9)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "violation_by_slack_bin.png")
    plt.close(fig)

    # 4. scenario bound vs measured, per plan with a support set
    pts = [r for r in rows if r["support_size"] != ""]
    if pts:
        fig, ax = plt.subplots(figsize=(6, 5), dpi=110)
        for arm, mk in (("A", "o"), ("B", "s")):
            q = [r for r in pts if r["arm"] == arm]
            if not q:
                continue
            ax.errorbar([r["eps_nonconvex"] for r in q], [r["plan_rate"] for r in q],
                        yerr=[[max(r["plan_rate"] - r["plan_lo"], 0) for r in q],
                              [max(r["plan_hi"] - r["plan_rate"], 0) for r in q]],
                        fmt=mk, ms=4, capsize=2, alpha=0.8, label=f"arm {arm} (K = {sorted({r['K'] for r in q})})")
        ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="measured = bound")
        ax.set_xlabel(f"scenario bound eps(s*) (Campi, Garatti & Ramponi 2018), beta = {beta:g}")
        ax.set_ylabel("measured plan-level violation rate (95% CP)")
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        ax.set_title("SYNTHETIC dev instances: measured violation vs a-posteriori scenario bound (B1)", fontsize=9)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "scenario_bound.png")
        plt.close(fig)


def _pct(x) -> str:
    if x == "" or x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "–"
    return f"{100 * x:.2f} %"


def _print_tables(rows, by_k, by_margin, bins_rows, rec_rows, support, plans, outs, beta, complete) -> None:
    pct = _pct
    print("\n### Per plan: B1 with the instance's 8 members (A8-g0) and B2\n")
    print("| instance | plan | delivered (in-sample) | min slack (s) | fresh members | plan-level violation [95% CP] | "
          "per-resident violation [KG 95% CP] | Kish upper | causes (residents x members / N) | support s* | eps(s*) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["plan"] in ("A8-g0", "B2-A8"):
            ms = f"{r['min_slack_s']:.1f}" if isinstance(r["min_slack_s"], (int, float)) else "–"
            print(f"| {r['instance']} | {r['plan']} | {r['delivered_in_sample']} | {ms} | {r['n_fresh']} | "
                  f"{pct(r['plan_rate'])} [{pct(r['plan_lo'])}, {pct(r['plan_hi'])}] | {pct(r['resident_rate'])} "
                  f"[{pct(r['resident_kg_lo'])}, {pct(r['resident_kg_hi'])}] | {pct(r['resident_kish_hi'])} | "
                  f"{r['causes']} | {r['support_size'] if r['support_size'] != '' else '–'} | "
                  f"{pct(r['eps_nonconvex']) if r['eps_nonconvex'] != '' else '–'} |")
    print(f"\n### Pooled by arm and K (primary scope: core plans, check members 0-31, instances {complete})\n")
    print("| scope | arm | K | size | instances | plans | residents | per-resident violation [KG 95% CP] | Kish upper | "
          "plan-level [95% CP] | contact share |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in by_k:
        print(f"| {r['scope']} | {r['arm']} | {r['K']} | {r['size']} | {r['instances']} | {r['plans']} | {r['residents']:.0f} | "
              f"{pct(r['rate'])} [{pct(r['kg_lo'])}, {pct(r['kg_hi'])}] | {pct(r['kish_hi'])} | {pct(r['plan_rate'])} "
              f"[{pct(r['plan_lo'])}, {pct(r['plan_hi'])}] | {pct(r['share_contact'])} |")
    print("\n### By required margin (cumulative: residents with in-sample slack >= m)\n")
    print("| set | m (min) | residents kept | share of delivered | violation | naive CP hi | KG hi | Kish hi | "
          "U = max(KG, Kish) | contact share |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in by_margin:
        print(f"| {r['set']} | {r['margin_min']} | {r['residents']:.0f} | {pct(r['delivered_fraction'])} | {pct(r['rate'])} | "
              f"{pct(r['naive_hi'])} | {pct(r['kg_hi'])} | {pct(r['kish_hi'])} | {pct(r['upper'])} | "
              f"{pct(r['share_contact'])} |")
    print("\n### By slack bin\n")
    print("| set | slack bin (min) | residents | violation | KG hi |")
    print("|---|---|---|---|---|")
    for r in bins_rows:
        print(f"| {r['set']} | {r['slack_from_min']}-{r['slack_to_min']} | {r['residents']:.0f} | {pct(r['rate'])} | "
              f"{pct(r['kg_hi'])} |")
    print("\n### Recommendation rule\n")
    for r in rec_rows:
        print(f"- {r['set']} (primary: {r['primary']}), alpha {r['alpha']}, {r['bound']}: margin {r['margin_min']} "
              f"(rate {pct(r['rate'])}, upper {pct(r['upper'])}, kept {r['residents_kept']}, "
              f"share {pct(r['delivered_fraction'])}, contact share {pct(r['contact_share'])})")
    print("\n### Support sets\n")
    for (iid, pid), sp in sorted(support.items()):
        print(f"- {iid} {pid}: s* = {sp['s']} of K = {sp['K']} ({sp['support']}); eps_nonconvex = "
              f"{st.eps_nonconvex(sp['s'], sp['K'], beta):.3f}, wait-and-judge = "
              f"{st.eps_wait_and_judge(sp['s'], sp['K'], beta):.3f}, s*/(K+1) = {sp['s'] / (sp['K'] + 1):.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--out-dir", default=None, help="where the CSVs and figures/ go (default: this folder)")
    return cmd_analyze(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
