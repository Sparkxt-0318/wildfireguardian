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
    causes: dict[str, int] = defaultdict(int)
    for a, c in enumerate(cs):
        r = recs[c]
        if len(r["states"]) != len(trips):
            raise AssertionError(f"{plan['instance']}/{plan['plan']}: trip count differs in member {c}")
        for i in deliv:
            if r["states"][i] != "0":
                fail[a, i] = True
                causes[r["causes"].get(str(i)) or "?"] += trips[i]["n"]
    n = np.array([t["n"] for t in trips], dtype=float)
    slack = np.array([t["slack_s"] if t["slack_s"] is not None else np.nan for t in trips], dtype=float)
    return {"cs": cs, "fail": fail, "deliv": deliv, "n": n, "slack": slack, "causes": dict(causes)}


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
        N = len(o["cs"])
        d = o["deliv"]
        nres = float(o["n"][d].sum())
        any_fail = o["fail"][:, d].any(axis=1) if d else np.zeros(N, dtype=bool)
        x_plan = int(any_fail.sum())
        x_res = float((o["fail"][:, d] * o["n"][d][None, :]).sum()) if d else 0.0
        pl_lo, pl_hi = st.clopper_pearson(x_plan, N, conf)
        per_member = (o["fail"][:, d] * o["n"][d][None, :]).sum(axis=1) if d else np.zeros(N)
        rc = st.cluster_ci(per_member, np.full(N, nres), conf)
        sp = support.get((iid, pid))
        K = int(pl["K"])
        row = {"instance": iid, "size": size_of(iid), "label": LABEL, "plan": pid, "arm": pl["arm"], "K": K,
               "method": pl["method"], "planning_members": " ".join(map(str, pl["members"])),
               "delivered_in_sample": pl["delivered"], "unresolved_in_sample": pl["unresolved"],
               "min_slack_s": pl["min_slack_s"], "n_fresh": N,
               "plan_violations": x_plan, "plan_rate": x_plan / N if N else math.nan, "plan_lo": pl_lo, "plan_hi": pl_hi,
               "resident_member_pairs": nres * N, "resident_violations": x_res, "resident_rate": rc["rate"],
               "resident_lo": rc["kish_lo"], "resident_hi": rc["kish_hi"],
               "causes": json.dumps(o["causes"], sort_keys=True),
               "support_size": sp["s"] if sp else "", "eps_nonconvex": st.eps_nonconvex(sp["s"], K, beta) if sp else "",
               "eps_wait_and_judge": st.eps_wait_and_judge(sp["s"], K, beta) if sp else "",
               "s_over_K1": sp["s"] / (K + 1) if sp else "", "runtime_s": pl["runtime_s"], **common}
        rows.append(row)
    _write_csv(out_dir / "results.csv", rows)

    # ---- pooled by arm and K
    by_k = []
    for (arm, K) in sorted({(r["arm"], r["K"]) for r in rows}, key=lambda t: (t[0], t[1])):
        for size in ("all", "S", "M", "L"):
            sel = [(k, o) for k, o in outs.items() if plans[k]["arm"] == arm and int(plans[k]["K"]) == K
                   and (size == "all" or size_of(k[0]) == size)]
            if not sel:
                continue
            by_k.append({"arm": arm, "K": K, "size": size, "label": LABEL, **_pooled(sel, conf), **common})
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
            res = _margin_stats(sel, 60.0 * m, conf)
            res.update(set=name, margin_min=m, delivered_fraction=res["residents"] / total if total else math.nan)
            curve.append(res)
            if m in MARGINS_MIN or m in (90, 120):
                by_margin.append({"set": name, "label": LABEL, "margin_min": m, **{k: v for k, v in res.items()
                                                                                  if k not in ("set", "margin_min")},
                                  **common})
        curves[name] = curve
        for lo, hi in zip(edges_min[:-1], edges_min[1:]):
            res = _margin_stats(sel, 60.0 * lo, conf, hi_s=60.0 * hi)
            bins_rows.append({"set": name, "label": LABEL, "slack_from_min": lo, "slack_to_min": hi, **res, **common})
    _write_csv(out_dir / "by_margin.csv", by_margin)
    _write_csv(out_dir / "by_slack_bin.csv", bins_rows)

    # ---- recommendation (pre-registered rule: primary set, U = max(Korn-Graubard, Kish) upper bound)
    rec_rows = []
    prim = "B1 A8 (instance members, K=8)"
    for name in curves:
        for alpha in cfg["statistics"]["alphas"]:
            pick = None
            for r in by_margin:
                if r["set"] != name or r["margin_min"] not in MARGINS_MIN:
                    continue
                if r["residents"] > 0 and max(r["kg_hi"], r["kish_hi"]) <= alpha:
                    pick = r
                    break
            rec_rows.append({"set": name, "primary": name == prim, "alpha": alpha, "label": LABEL,
                             "margin_min": pick["margin_min"] if pick else "none <= 60",
                             "rate": pick["rate"] if pick else "", "upper": max(pick["kg_hi"], pick["kish_hi"]) if pick else "",
                             "residents_kept": pick["residents"] if pick else "",
                             "delivered_fraction": pick["delivered_fraction"] if pick else "", **common})
    _write_csv(out_dir / "recommendation.csv", rec_rows)

    _figures(rows, by_k, curves, bins_rows, outs, plans, support, cfg, beta)
    _print_tables(rows, by_k, by_margin, bins_rows, rec_rows, support, plans, outs, beta)
    return 0


def _pooled(sel, conf: float) -> dict:
    """Pool plans: per-resident rate with clusters (instance, fresh member) and the plan-level rate."""
    xs: dict[tuple, float] = defaultdict(float)
    ns: dict[tuple, float] = defaultdict(float)
    xp, np_ = 0, 0
    plans_n = 0
    causes: dict[str, float] = defaultdict(float)
    claimed = 0.0
    for (iid, pid), o in sel:
        d = o["deliv"]
        plans_n += 1
        claimed += float(o["n"][d].sum())
        for a, c in enumerate(o["cs"]):
            xs[(iid, c)] += float((o["fail"][a, d] * o["n"][d]).sum()) if d else 0.0
            ns[(iid, c)] += float(o["n"][d].sum())
            xp += int(o["fail"][a, d].any()) if d else 0
            np_ += 1
        for k, v in o["causes"].items():
            causes[k] += v
    keys = sorted(xs)
    rc = st.cluster_ci([xs[k] for k in keys], [ns[k] for k in keys], conf)
    lo, hi = st.clopper_pearson(xp, np_, conf)
    tot = sum(causes.values())
    return {"plans": plans_n, "claimed_residents": claimed, "resident_member_pairs": rc["n"],
            "resident_violations": rc["x"], "resident_rate": rc["rate"], "resident_naive_lo": rc["naive_lo"],
            "resident_naive_hi": rc["naive_hi"], "resident_kg_hi": rc["kg_hi"], "resident_kish_lo": rc["kish_lo"],
            "resident_kish_hi": rc["kish_hi"], "plan_member_pairs": np_, "plan_violations": xp,
            "plan_rate": xp / np_ if np_ else math.nan, "plan_lo": lo, "plan_hi": hi,
            "share_contact": causes.get("FLAME_CONTACT", 0.0) / tot if tot else math.nan,
            "causes": json.dumps({k: round(v) for k, v in sorted(causes.items())})}


def _margin_stats(sel, lo_s: float, conf: float, hi_s: float = math.inf) -> dict:
    """Residents with in-sample slack in [lo_s, hi_s) (1 us tolerance below, as the harness) and their
    out-of-sample violation, clusters = (instance, fresh member)."""
    xs: dict[tuple, float] = defaultdict(float)
    ns: dict[tuple, float] = defaultdict(float)
    residents = 0.0
    for (iid, pid), o in sel:
        d = [i for i in o["deliv"] if o["slack"][i] >= lo_s - 1e-6 and o["slack"][i] < hi_s - 1e-6]
        if not d:
            continue
        residents += float(o["n"][d].sum())
        for a, c in enumerate(o["cs"]):
            xs[(iid, c)] += float((o["fail"][a, d] * o["n"][d]).sum())
            ns[(iid, c)] += float(o["n"][d].sum())
    keys = sorted(xs)
    rc = st.cluster_ci([xs[k] for k in keys], [ns[k] for k in keys], conf)
    return {"residents": residents, "pairs": rc["n"], "violations": rc["x"], "rate": rc["rate"],
            "naive_lo": rc["naive_lo"], "naive_hi": rc["naive_hi"], "kg_lo": rc["kg_lo"], "kg_hi": rc["kg_hi"],
            "kish_lo": rc["kish_lo"], "kish_hi": rc["kish_hi"], "n_eff_kish": rc["n_eff_kish"],
            "n_eff_kg": rc["n_eff_kg"], "deff": rc["deff"]}


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

    host_note = "dev set, B1/B2 plans, fresh members of each instance's own hazard model"
    # 1. violation vs K
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=110)
    for arm, color, lab in (("A", "tab:blue", "planning members = instance members"),
                            ("B", "tab:orange", "planning members = fresh draws")):
        pts = sorted((r["K"], r) for r in by_k if r["arm"] == arm and r["size"] == "all")
        if not pts:
            continue
        ks = [k for k, _ in pts]
        for ax, key, lo, hi in ((axes[0], "resident_rate", "resident_kish_lo", "resident_kish_hi"),
                                (axes[1], "plan_rate", "plan_lo", "plan_hi")):
            y = np.array([r[key] for _, r in pts])
            yl = np.array([r[lo] for _, r in pts])
            yh = np.array([r[hi] for _, r in pts])
            ax.errorbar(ks, y, yerr=[y - yl, yh - y], marker="o", color=color, capsize=3, label=lab)
    sup_pts = defaultdict(list)
    for (iid, pid), s in support.items():
        sup_pts[int(s["K"])].append(s["s"])
    if sup_pts:
        ks = sorted(sup_pts)
        axes[1].plot(ks, [np.mean(sup_pts[k]) / (k + 1) for k in ks], "k--", lw=1, label="mean s*/(K+1)")
        axes[1].plot(ks, [np.median([st.eps_nonconvex(s, k, beta) for s in sup_pts[k]]) for k in ks], "k:", lw=1,
                     label=f"median scenario bound eps(s*), beta={beta:g}")
    for ax, t in ((axes[0], "per delivered resident"), (axes[1], "per plan (any delivered resident fails)")):
        ax.set_xscale("log", base=2)
        ax.set_xlabel("K (planning members)")
        ax.set_ylabel("out-of-sample violation rate")
        ax.set_title(t, fontsize=10)
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.3)
    axes[1].legend(fontsize=7)
    axes[0].legend(fontsize=7)
    fig.suptitle(f"SYNTHETIC: out-of-sample violation vs K (B1; 95% CP; {host_note})", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "violation_vs_K.png")
    plt.close(fig)

    # 2. violation vs required margin (cumulative), with delivered fraction
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=110)
    colors = ["tab:blue", "tab:green", "tab:orange", "tab:gray"]
    for (name, curve), color in zip(curves.items(), colors):
        m = np.array([c["margin_min"] for c in curve], dtype=float)
        y = np.array([c["rate"] for c in curve], dtype=float)
        u = np.array([max(c["kg_hi"], c["kish_hi"]) for c in curve], dtype=float)
        f = np.array([c["delivered_fraction"] for c in curve], dtype=float)
        axes[0].plot(m, y, color=color, label=name)
        axes[0].plot(m, u, color=color, ls="--", lw=0.8)
        axes[1].plot(m, f, color=color, label=name)
    for a in (0.05, 0.01):
        axes[0].axhline(a, color="red", lw=0.6, ls=":")
    axes[0].set_ylabel("out-of-sample violation of residents with slack >= m\n(solid: rate, dashed: 95% upper bound)")
    axes[1].set_ylabel("share of delivered residents with slack >= m")
    for ax in axes:
        ax.set_xlabel("required margin m (min of in-sample safety slack, ASSUMPTIONS #91)")
        ax.grid(alpha=0.3)
        ax.set_xlim(0, 120)
        ax.set_ylim(bottom=0)
    axes[0].legend(fontsize=7)
    fig.suptitle("SYNTHETIC: violation and delivered cost vs required margin (dev set; fresh members)", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "violation_vs_margin.png")
    plt.close(fig)

    # 3. per slack bin
    fig, ax = plt.subplots(figsize=(8, 4), dpi=110)
    names = [n for n in curves]
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
    ax.set_title("SYNTHETIC: violation by in-sample slack bin (dev set)", fontsize=9)
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
                        yerr=[[r["plan_rate"] - r["plan_lo"] for r in q], [r["plan_hi"] - r["plan_rate"] for r in q]],
                        fmt=mk, ms=4, capsize=2, alpha=0.8, label=f"arm {arm} (K = {sorted({r['K'] for r in q})})")
        ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="measured = bound")
        ax.set_xlabel(f"scenario bound eps(s*) (Campi, Garatti & Ramponi 2018), beta = {beta:g}")
        ax.set_ylabel("measured plan-level violation rate (95% CP)")
        ax.set_xlim(0, 1.02)
        ax.set_ylim(0, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
        ax.set_title("SYNTHETIC: measured violation vs a-posteriori scenario bound (B1)", fontsize=9)
        fig.tight_layout()
        fig.savefig(FIG_DIR / "scenario_bound.png")
        plt.close(fig)


def _print_tables(rows, by_k, by_margin, bins_rows, rec_rows, support, plans, outs, beta) -> None:
    def pct(x):
        return "–" if x == "" or x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.2f} %"

    print("\n### Per instance, B1 with the instance's 8 members (A8-g0) and B2\n")
    print("| instance | plan | delivered (in-sample) | min slack (s) | fresh members | plan-level violation [95% CP] | per-resident violation [95% CP] | support s* | eps(s*) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["plan"] in ("A8-g0", "B2-A8"):
            print(f"| {r['instance']} | {r['plan']} | {r['delivered_in_sample']} | {r['min_slack_s']} | {r['n_fresh']} | "
                  f"{pct(r['plan_rate'])} [{pct(r['plan_lo'])}, {pct(r['plan_hi'])}] | {pct(r['resident_rate'])} "
                  f"[{pct(r['resident_lo'])}, {pct(r['resident_hi'])}] | {r['support_size']} | "
                  f"{pct(r['eps_nonconvex']) if r['eps_nonconvex'] != '' else '–'} |")
    print("\n### Pooled by arm and K\n")
    print("| arm | K | size | plans | claimed residents | per-resident violation [Kish 95% CP] | plan-level [95% CP] | contact share |")
    print("|---|---|---|---|---|---|---|---|")
    for r in by_k:
        print(f"| {r['arm']} | {r['K']} | {r['size']} | {r['plans']} | {r['claimed_residents']:.0f} | {pct(r['resident_rate'])} "
              f"[{pct(r['resident_kish_lo'])}, {pct(r['resident_kish_hi'])}] | {pct(r['plan_rate'])} "
              f"[{pct(r['plan_lo'])}, {pct(r['plan_hi'])}] | {pct(r['share_contact'])} |")
    print("\n### By required margin (cumulative: residents with in-sample slack >= m)\n")
    print("| set | m (min) | residents kept | share of delivered | violation | naive CP hi | KG hi | Kish hi |")
    print("|---|---|---|---|---|---|---|---|")
    for r in by_margin:
        print(f"| {r['set']} | {r['margin_min']} | {r['residents']:.0f} | {pct(r['delivered_fraction'])} | {pct(r['rate'])} | "
              f"{pct(r['naive_hi'])} | {pct(r['kg_hi'])} | {pct(r['kish_hi'])} |")
    print("\n### Recommendation rule\n")
    for r in rec_rows:
        print(f"- {r['set']} (primary: {r['primary']}), alpha {r['alpha']}: margin {r['margin_min']} "
              f"(rate {pct(r['rate'])}, upper {pct(r['upper'])}, kept {r['residents_kept']}, share {pct(r['delivered_fraction'])})")
    print("\n### Support sets\n")
    for (iid, pid), s in sorted(support.items()):
        o = outs.get((iid, pid))
        print(f"- {iid} {pid}: s* = {s['s']} of K = {s['K']} ({s['support']}); eps_nonconvex = "
              f"{st.eps_nonconvex(s['s'], s['K'], beta):.3f}, wait-and-judge = {st.eps_wait_and_judge(s['s'], s['K'], beta):.3f}, "
              f"s*/(K+1) = {s['s'] / (s['K'] + 1):.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=None)
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--out-dir", default=None, help="where the CSVs and figures/ go (default: this folder)")
    return cmd_analyze(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
