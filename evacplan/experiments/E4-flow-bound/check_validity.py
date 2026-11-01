"""E4 validity checks over the committed result rows, plus the experiment's results table and figure.

    .venv/bin/python evacplan/experiments/E4-flow-bound/check_validity.py [--results-dir DIR] [--no-write]

Reads every row of ``evacplan/results/*.csv`` (dev only; no test instance is read or run). For each dev instance
with an ``e4_flow_bound`` row:

* check 1 (Siyeong): every B3 row on an S instance delivers at most the E4 bound;
* check 2: every checked plan of every method (any seed, budget or host) delivers at most the E4 bound;
* the gap = (bound - best delivered by any method on the E4 row's host) / bound, next to the trivial bound
  (residents of servable classes: min(resource bound, residents - unservable)).

Writes ``results.csv`` and ``figures/bounds_vs_best_dev.png`` next to this file (SYNTHETIC), prints a summary
and exits with status 1 if any check fails. Reads rows only: it computes no bound and declares no state.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from evacplan.harness import RESULTS_DIR, all_facility_rows, all_rows, is_bound_only, row_config
from evacplan.instances import SPLIT_PATH, load_split

HERE = Path(__file__).resolve().parent
E4 = "e4_flow_bound"
COLUMNS = ("instance", "size", "residents", "unservable", "trivial_bound", "e4_bound", "best_delivered_host",
           "best_method_host", "gap", "trivial_gap", "trivial_gap_closed", "best_delivered_any_host", "rows_checked",
           "violations", "runtime_s", "delta_s", "grouping", "lp_rows", "lp_cols", "lp_status", "lp_objective",
           "dual_bound", "resource_bound", "host", "commit")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--no-write", action="store_true", help="print only; do not write results.csv or the figure")
    args = ap.parse_args(argv)
    split = load_split(SPLIT_PATH)
    dev = {e.id: e for e in split.entries("dev")}
    rows = [r for r in all_rows(args.results_dir) if row_config(r)["set"] == "dev" and r["instance"] in dev]
    e4 = [r for r in rows if r["method"] == E4]
    if not e4:
        print("no e4_flow_bound rows on dev")
        return 1
    assert all(is_bound_only(r) for r in e4), "e4_flow_bound rows must say bound_only"
    bound = {}
    for r in e4:
        b = float(r["best_bound"])
        if r["instance"] in bound and bound[r["instance"]][0] != b:
            print(f"note: {r['instance']}: e4 bounds differ between rows ({bound[r['instance']][0]} vs {b})")
        if r["instance"] not in bound or b < bound[r["instance"]][0]:
            bound[r["instance"]] = (b, r)
    plans = [r for r in rows if not is_bound_only(r)]
    unserv: dict[str, float] = {}                 # residents the oracle declares unservable (per instance)
    per: dict[tuple[str, str, int, str], float] = defaultdict(float)
    for f in all_facility_rows(args.results_dir):
        if row_config(f)["set"] == "dev" and f["instance"] in dev:
            per[(f["instance"], f["method"], int(f["seed"]), f["host"])] += float(f["unservable"])
    for (inst, *_), u in per.items():
        unserv[inst] = max(unserv.get(inst, 0.0), u)

    violations, b3_checked, out = [], 0, []
    for inst in dev:
        if inst not in bound:
            continue
        b, er = bound[inst]
        host = er["host"]
        mine = [r for r in plans if r["instance"] == inst]
        bad = [r for r in mine if float(r["delivered_checked"]) > b]
        violations += [f"{inst}: {r['method']} seed {r['seed']} delivered {r['delivered_checked']} > bound {b:g} "
                       f"(host {r['host']})" for r in bad]
        b3_checked += sum(1 for r in mine if r["method"] == "b3_mip")
        same = [r for r in mine if r["host"] == host]
        best = max(same, key=lambda r: float(r["delivered_checked"]), default=None)
        best_any = max((float(r["delivered_checked"]) for r in mine), default=None)
        e = dev[inst]
        n = int(e.stats["residents"])
        cfg = row_config(er)
        diag = cfg.get("diagnostics", {})
        rb = diag.get("resource_bound")
        trivial = min(n - unserv.get(inst, 0.0), rb if rb is not None else n)
        bd = None if best is None else float(best["delivered_checked"])
        gap = None if bd is None else (b - bd) / b if b > 0 else 0.0
        tgap = None if bd is None else (trivial - bd) / trivial if trivial > 0 else 0.0
        closed = None if (bd is None or trivial <= bd) else (trivial - b) / (trivial - bd)
        out.append({
            "instance": inst, "size": e.config.get("size"), "residents": n, "unservable": f"{unserv.get(inst, 0.0):g}",
            "trivial_bound": f"{trivial:g}", "e4_bound": f"{b:g}", "best_delivered_host": "" if bd is None else f"{bd:g}",
            "best_method_host": "" if best is None else best["method"], "gap": "" if gap is None else f"{gap:.4f}",
            "trivial_gap": "" if tgap is None else f"{tgap:.4f}",
            "trivial_gap_closed": "" if closed is None else f"{closed:.4f}",
            "best_delivered_any_host": "" if best_any is None else f"{best_any:g}", "rows_checked": len(mine),
            "violations": len(bad), "runtime_s": er["runtime_s"], "delta_s": diag.get("delta_eff_s"),
            "grouping": diag.get("grouping"), "lp_rows": diag.get("rows"), "lp_cols": diag.get("cols"),
            "lp_status": diag.get("lp_status"), "lp_objective": diag.get("lp_objective"),
            "dual_bound": diag.get("dual_bound"), "resource_bound": rb, "host": host, "commit": er["commit"][:12]})
    # ---- report
    print(f"{'instance':28s} {'res':>4s} {'triv':>5s} {'E4':>5s} {'best':>5s} {'gap':>7s} {'trivgap':>7s} {'closed':>7s} "
          f"{'rows':>4s} {'viol':>4s} {'run s':>7s}")
    for o in out:
        print(f"{o['instance']:28s} {o['residents']:4d} {o['trivial_bound']:>5s} {o['e4_bound']:>5s} "
              f"{o['best_delivered_host']:>5s} {o['gap']:>7s} {o['trivial_gap']:>7s} {o['trivial_gap_closed']:>7s} "
              f"{o['rows_checked']:4d} {o['violations']:4d} {float(o['runtime_s']):7.1f}")
    for size in ("S", "M", "L", None):
        sel = [o for o in out if (size is None or o["size"] == size) and o["gap"]]
        if sel:
            g = statistics.mean(float(o["gap"]) for o in sel)
            t = statistics.mean(float(o["trivial_gap"]) for o in sel)
            print(f"mean gap {size or 'all'}: E4 {100 * g:.1f}%  trivial {100 * t:.1f}%  ({len(sel)} instances)")
    print(f"check 1 (S, B3 rows): {b3_checked} B3 rows checked; check 2: {sum(o['rows_checked'] for o in out)} rows "
          f"of {len({r['method'] for r in plans})} methods checked; violations: {len(violations)}")
    for v in violations:
        print("VIOLATION", v)
    if not args.no_write:
        with (HERE / "results.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
            w.writeheader()
            for o in out:
                w.writerow({k: ("" if o.get(k) is None else o[k]) for k in COLUMNS})
        _figure(out, HERE / "figures" / "bounds_vs_best_dev.png")
    return 1 if violations else 0


def _figure(out: list[dict], path: Path) -> None:
    import matplotlib.style
    from matplotlib import rc_context
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    sel = [o for o in out if o["best_delivered_host"]]
    labels = [o["instance"].replace("SYNTHETIC-", "") for o in sel]
    x = list(range(len(sel)))
    with matplotlib.style.context("default"), rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        fig = Figure(figsize=(9.0, 4.2), dpi=100, facecolor="#fcfcfb")
        FigureCanvasAgg(fig)
        ax = fig.add_subplot()
        ax.set_facecolor("#fcfcfb")
        w = 0.27
        series = (("trivial bound (servable residents)", "trivial_bound", "#c3c2b7"),
                  ("E4 flow bound", "e4_bound", "#2a78d6"),
                  ("best delivered, any method (this host)", "best_delivered_host", "#eb6834"))
        for n, (name, key, colour) in enumerate(series):
            ax.bar([v + (n - 1) * w for v in x], [float(o[key]) / o["residents"] * 100 for o in sel], w,
                   label=name, color=colour)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel("% of the instance's residents")
        ax.set_ylim(0, 105)
        ax.grid(True, axis="y", color="#e1e0d9", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.set_title("SYNTHETIC dev instances - E4 upper bound vs trivial bound vs best plan", loc="left", fontsize=10)
        ax.legend(loc="lower left", frameon=False, fontsize=8)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=100, facecolor="#fcfcfb", bbox_inches="tight",
                    metadata={"Software": None, "Title": "SYNTHETIC - E4 bound vs best plan (dev)"})


if __name__ == "__main__":
    sys.exit(main())
