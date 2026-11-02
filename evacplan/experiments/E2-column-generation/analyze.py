"""E2 results over the committed rows: per-seed table against B2 in the same interleaved holds, bounds, the validity
check of every E2 bound, and the pre-registered decision. Reads rows only (it computes no bound, declares no state).

    .venv/bin/python evacplan/experiments/E2-column-generation/analyze.py [--results-dir DIR] [--no-write]

Writes ``results.csv`` (one line per instance and seed: E2 and its B2 partner of the same pair) next to this file and
prints the README tables (SYNTHETIC). Exit status 1 if any E2 bound is below a delivered value of any row (a bug).
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from evacplan.harness import RESULTS_DIR, all_facility_rows, all_rows, is_bound_only, row_config
from evacplan.instances import SPLIT_PATH, load_split

HERE = Path(__file__).resolve().parent
E2, B2 = "e2_colgen", "b2_vrptw"
TIGHT_M = ("SYNTHETIC-M-grid-t75-s107", "SYNTHETIC-M-geo-t75-s108")
BAR = 1751


def _f(x) -> float | None:
    return None if x in (None, "") else float(x)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    split = load_split(SPLIT_PATH)
    dev = [e.id for e in split.entries("dev")]
    size = {e.id: e.config["size"] for e in split.entries("dev")}
    residents = {e.id: e.stats.get("residents") for e in split.entries("dev")}
    rows = [r for r in all_rows(args.results_dir) if row_config(r)["set"] == "dev" and r["instance"] in dev]
    e2 = [r for r in rows if r["method"] == E2]
    if not e2:
        print("no e2_colgen rows on dev")
        return 1
    host = e2[0]["host"]
    e2 = [r for r in e2 if r["host"] == host and float(row_config(r)["budget_s"]) == 60.0]
    holds = sorted({row_config(r).get("hold") for r in e2 if row_config(r).get("hold")})
    pair_b2 = {(row_config(r).get("hold"), row_config(r).get("pair")): r for r in rows
               if r["method"] == B2 and r["host"] == host and row_config(r).get("hold") in holds}
    unserv: dict[str, float] = defaultdict(float)
    seen = set()
    for f in all_facility_rows(args.results_dir):
        key = (f["instance"], f["facility"], f.get("mobility_class"))
        if f["instance"] in dev and key not in seen and f.get("unservable") not in (None, ""):
            seen.add(key)
            unserv[f["instance"]] += float(f["unservable"])
    # ---- per instance and seed
    table = []
    for r in sorted(e2, key=lambda r: (dev.index(r["instance"]), int(r["seed"]))):
        cfg = row_config(r)
        d = cfg.get("diagnostics", {})
        b = pair_b2.get((cfg.get("hold"), cfg.get("pair")))
        table.append({
            "instance": r["instance"], "size": size[r["instance"]], "seed": int(r["seed"]),
            "residents": residents[r["instance"]], "e2_delivered": int(r["delivered_checked"]),
            "e2_unresolved": int(r["unresolved"]), "e2_bound": _f(r["best_bound"]),
            "e2_lagrangian": d.get("lagrangian_bound"), "e2_converged": d.get("converged"), "e2_stop": d.get("stop"),
            "e2_rounds": d.get("rounds"), "e2_runtime_s": _f(r["runtime_s"]), "e2_certify_s": cfg.get("certify_s"),
            "e2_time_to_certified_s": None if cfg.get("certify_s") is None else round(
                float(r["runtime_s"]) + float(cfg["certify_s"]), 2),
            "b2_seed": None if b is None else int(b["seed"]), "b2_delivered": None if b is None else int(b["delivered_checked"]),
            "b2_unresolved": None if b is None else int(b["unresolved"]),
            "b2_time_to_certified_s": None if b is None or row_config(b).get("certify_s") is None else round(
                float(b["runtime_s"]) + float(row_config(b)["certify_s"]), 2),
            "speed_probe_s": cfg.get("speed_probe_s"), "hold": cfg.get("hold"),
        })
    # ---- validity: every E2 bound >= every delivered value of every row on that instance (any method, seed, host)
    best_any: dict[str, int] = defaultdict(int)
    for r in rows:
        if not is_bound_only(r):
            best_any[r["instance"]] = max(best_any[r["instance"]], int(r["delivered_checked"]))
    violations = [(t["instance"], t["seed"], t["e2_bound"], best_any[t["instance"]]) for t in table
                  if t["e2_bound"] is not None and t["e2_bound"] < best_any[t["instance"]]]
    n_rows_checked = sum(1 for r in rows if not is_bound_only(r))
    # ---- totals
    def totals(method_rows: dict[int, dict[str, int]], insts) -> dict[int, int]:
        return {s: sum(v[i] for i in insts) for s, v in method_rows.items() if all(i in v for i in insts)}
    e2_by, b2_by = defaultdict(dict), defaultdict(dict)
    for t in table:
        e2_by[t["seed"]][t["instance"]] = t["e2_delivered"]
        if t["b2_delivered"] is not None:
            b2_by[t["seed"]][t["instance"]] = t["b2_delivered"]          # B2's partner of E2's seed
    m_insts = [i for i in dev if size[i] == "M"]
    tot_all_e2, tot_all_b2 = totals(e2_by, dev), totals(b2_by, dev)
    tot_m_e2, tot_m_b2 = totals(e2_by, m_insts), totals(b2_by, m_insts)
    bound_min: dict[str, float] = {}
    for t in table:
        if t["e2_bound"] is not None:
            bound_min[t["instance"]] = min(bound_min.get(t["instance"], math.inf), t["e2_bound"])
    trivial = {i: min(residents[i] - unserv.get(i, 0.0),
                      min((row_config(r).get("diagnostics", {}).get("resource_bound") or math.inf)
                          for r in e2 if r["instance"] == i)) for i in dev}
    every_m_row_bound = all(t["e2_bound"] is not None for t in table if t["size"] == "M")
    below = {i: (i in bound_min and bound_min[i] < trivial[i]) for i in TIGHT_M}
    worst_all = min(tot_all_e2.values()) if len(tot_all_e2) >= 5 else None
    keep = worst_all is not None and worst_all > BAR and all(t["e2_runtime_s"] <= 60.0 for t in table)
    cond_a = bool(tot_m_e2) and bool(tot_m_b2) and min(tot_m_e2.values()) >= min(tot_m_b2.values())
    cond_b = every_m_row_bound and any(below.values())
    decision = "KEEP" if keep else ("ITERATE" if (cond_a or cond_b) else "KILL")
    # ---- output
    print(f"host: {host}\nholds: {holds}")
    print(f"validity: {len(violations)} violations over {len(table)} E2 rows against {n_rows_checked} plan rows of "
          f"{len({r['method'] for r in rows if not is_bound_only(r)})} methods on dev (any seed, budget, host)")
    for v in violations:
        print("  VIOLATION", v)
    print("\n| instance (SYNTHETIC) | residents | trivial | E2 bound (min) | E2 delivered [seeds 0-4] | B2 delivered "
          "(partner seeds) | E2 time to certified (s) |")
    print("|---|---|---|---|---|---|---|")
    for i in dev:
        ts = [t for t in table if t["instance"] == i]
        if not ts:
            continue
        print(f"| {i.replace('SYNTHETIC-', '')} | {residents[i]} | {trivial[i]:g} | "
              f"{bound_min.get(i, float('nan')):g} | {', '.join(str(t['e2_delivered']) for t in ts)} | "
              f"{', '.join(str(t['b2_delivered']) for t in ts)} | "
              f"{statistics.median([t['e2_time_to_certified_s'] for t in ts if t['e2_time_to_certified_s'] is not None] or [float('nan')]):.1f} |")
    print(f"\nper-seed totals, all 10: E2 {dict(tot_all_e2)}  B2 partners {dict(tot_all_b2)}")
    print(f"per-seed totals, M (4): E2 {dict(tot_m_e2)}  B2 partners {dict(tot_m_b2)}")
    print(f"worst of 5, all: E2 {worst_all}; bar {BAR}")
    print(f"(a) E2 worst M {min(tot_m_e2.values()) if tot_m_e2 else None} >= B2 worst M "
          f"{min(tot_m_b2.values()) if tot_m_b2 else None}: {cond_a}")
    print(f"(b) bound in every M row: {every_m_row_bound}; below trivial on tight M: {below}: {cond_b}")
    print(f"decision: {decision}")
    if not args.no_write:
        with (HERE / "results.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(table[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(table)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
