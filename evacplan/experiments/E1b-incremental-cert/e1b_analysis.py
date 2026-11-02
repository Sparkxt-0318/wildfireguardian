"""E1b analysis: ``results.csv`` and the README's tables from the harness's result rows (``evacplan/results/*.csv``,
``evacplan/results/speed/speed_check.csv``): E1b against B2 in the same interleaved holds, per seed and per instance,
with time to certified plan (runtime + ``certify_s``). Dev rows of one host only (default: this machine's host
string). Reads rows only; runs nothing. Everything here is SYNTHETIC (``results.csv`` says so in its ``label`` column).

    .venv/bin/python evacplan/experiments/E1b-incremental-cert/e1b_analysis.py [--host HOST] [--results-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from evacplan import harness
from evacplan.instances import load_split

HERE = Path(__file__).resolve().parent
SET, BUDGET, METHOD, B2 = "dev", 60.0, "e1b_alns", "b2_vrptw"


def med(xs):
    return statistics.median(xs) if xs else None


def stat(xs, nd: int = 0) -> str:
    xs = [x for x in xs if x is not None]
    if not xs:
        return "–"
    f = (lambda x: f"{x:.{nd}f}") if nd else (lambda x: f"{x:g}")
    m = med(xs)
    return f(m) if min(xs) == max(xs) else f"{f(m)} [{f(min(xs))}–{f(max(xs))}]"


def ttc(r) -> float | None:
    c = harness.row_config(r).get("certify_s")
    return None if c is None else float(r["runtime_s"]) + float(c)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default=None)
    ap.add_argument("--results-dir", type=Path, default=harness.RESULTS_DIR)
    ap.add_argument("--out", type=Path, default=HERE / "results.csv")
    args = ap.parse_args()
    host = args.host or harness.host_string()
    ids = [e.id for e in load_split().entries(SET)]
    rows = [r for r in harness.all_rows(args.results_dir)
            if harness.table_key(r) == (SET, BUDGET, host) and r["instance"] in ids and r["method"] in (METHOD, B2)]
    held = [r for r in rows if harness.row_config(r).get("hold")]
    e1b = [r for r in held if r["method"] == METHOD]
    if not e1b:
        print(f"no interleaved {METHOD} rows for {SET} at {BUDGET:g} s on host {host}")
        return 1
    pair = {(harness.row_config(r)["hold"], harness.row_config(r)["pair"], r["method"]): r for r in held}
    out, per_seed = [], defaultdict(lambda: defaultdict(dict))
    for r in sorted(e1b, key=lambda r: (ids.index(r["instance"]), int(r["seed"]))):
        c = harness.row_config(r)
        b = pair.get((c["hold"], c["pair"], B2))
        d = c.get("diagnostics", {})
        inc = d.get("incremental", {})
        ts = d.get("time_s", {})
        rec = {
            "instance": r["instance"], "seed": int(r["seed"]), "label": "SYNTHETIC", "hold": c["hold"],
            "speed_probe_s": c.get("speed_probe_s"),
            "e1b_delivered": int(r["delivered_checked"]), "e1b_unresolved": int(r["unresolved"]),
            "e1b_model_no_route": int(r["model_no_route"]), "e1b_runtime_s": float(r["runtime_s"]),
            "e1b_certify_s": c.get("certify_s"), "e1b_time_to_certified_s": ttc(r),
            "e1b_slack_ge_30m": int(r["delivered_slack_ge_30m"]),
            "b2_seed": int(b["seed"]) if b else None, "b2_delivered": int(b["delivered_checked"]) if b else None,
            "b2_unresolved": int(b["unresolved"]) if b else None, "b2_runtime_s": float(b["runtime_s"]) if b else None,
            "b2_certify_s": harness.row_config(b).get("certify_s") if b else None,
            "b2_time_to_certified_s": ttc(b) if b else None,
            "b2_slack_ge_30m": int(b["delivered_slack_ge_30m"]) if b else None,
            "iterations": d.get("iterations"), "stop": d.get("stop"), "warm_planned": d.get("warm_planned"),
            "relaxed_best": d.get("relaxed_best"), "certifications": d.get("certifications"),
            "certifications_skipped": d.get("certifications_skipped"), "oracle_calls": d.get("oracle_calls"),
            "oracle_legs": d.get("oracle_legs"), "oracle_s_per_leg": d.get("oracle_s_per_leg"),
            "oracle_cut_residents": d.get("oracle_cut_residents"),
            "changed_vehicles": inc.get("changed_vehicles"), "unchanged_warm_vehicles": inc.get("unchanged_warm_vehicles"),
            "delivered_checked_in_loop": inc.get("delivered_checked_in_loop"),
            "planned_unchecked_warm": inc.get("planned_unchecked_warm"),
            "t_warm_start": ts.get("warm_start"), "t_search": ts.get("search"), "t_oracle": ts.get("oracle"),
            "t_final_certification": ts.get("final_certification"), "t_total": ts.get("total"),
            "incumbents": json.dumps(d.get("incumbents")),
        }
        out.append(rec)
        per_seed["e1b"][rec["seed"]][r["instance"]] = rec["e1b_delivered"]
        if b:
            per_seed["b2"][rec["seed"]][r["instance"]] = rec["b2_delivered"]
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print(f"-> {args.out} ({len(out)} E1b rows, SYNTHETIC)\n")

    # per-seed totals over the instances each method covers in every seed
    insts = [i for i in ids if any(o["instance"] == i for o in out)]
    print("| SYNTHETIC dev, 60 s, " + host.split(", vm boot ")[-1] + " | " + " | ".join(f"seed {s}" for s in range(5))
          + " | median [min–max] | worst |")
    print("|---|" + "---|" * 7)
    for key, name in (("e1b", "E1b"), ("b2", "B2 (same holds, seed s)")):
        tots = {s: sum(v[i] for i in insts) for s, v in sorted(per_seed[key].items()) if set(insts) <= set(v)}
        if tots:
            print(f"| {name} | " + " | ".join(str(tots.get(s, "–")) for s in range(5))
                  + f" | {stat(list(tots.values()))} | {min(tots.values())} |")
    for size in ("S", "M", "L"):
        si = [i for i in insts if f"-{size}-" in i]
        cells = []
        for key in ("e1b", "b2"):
            tots = [sum(v[i] for i in si) for s, v in sorted(per_seed[key].items()) if set(si) <= set(v)]
            cells.append(stat(tots))
        print(f"| {size} ({len(si)} instances): E1b / B2 | {cells[0]} / {cells[1]} |")
    print()

    print("| instance | residents | B2 median [min–max] | E1b median [min–max] | E1b − B2 (median) | time to certified "
          "plan, B2 / E1b (s, median) | E1b certify_s | E1b iterations | E1b oracle calls | E1b changed / unchanged "
          "vehicles | E1b in-loop oracle s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    res = {e.id: e.stats.get("residents") for e in load_split().entries(SET)}
    for i in insts:
        rs = [o for o in out if o["instance"] == i]
        e, b = [o["e1b_delivered"] for o in rs], [o["b2_delivered"] for o in rs if o["b2_delivered"] is not None]
        print(f"| {i} | {res.get(i)} | {stat(b)} | {stat(e)} | {(med(e) - med(b)) if b else '–':+g} | "
              f"{stat([o['b2_time_to_certified_s'] for o in rs], 1)} / {stat([o['e1b_time_to_certified_s'] for o in rs], 1)} | "
              f"{stat([o['e1b_certify_s'] for o in rs], 1)} | {stat([o['iterations'] for o in rs])} | "
              f"{stat([o['oracle_calls'] for o in rs])} | {stat([o['changed_vehicles'] for o in rs])} / "
              f"{stat([o['unchanged_warm_vehicles'] for o in rs])} | {stat([o['t_oracle'] for o in rs], 1)} |")
    print()
    print("Per seed, per instance (E1b / B2 delivered; E1b changed/unchanged vehicles; stop):")
    for o in out:
        print(f"  {o['instance']} s{o['seed']}: E1b {o['e1b_delivered']} (unres {o['e1b_unresolved']}, mnr "
              f"{o['e1b_model_no_route']}, ttc {o['e1b_time_to_certified_s']:.1f} s) / B2 {o['b2_delivered']} (ttc "
              f"{(o['b2_time_to_certified_s'] or 0):.1f} s); it {o['iterations']} stop {o['stop']} relaxed_best "
              f"{o['relaxed_best']} warm {o['warm_planned']} changed/unchanged {o['changed_vehicles']}/"
              f"{o['unchanged_warm_vehicles']} oracle {o['oracle_calls']} calls {o['t_oracle']} s cuts "
              f"{o['oracle_cut_residents']} certs {o['certifications']} skipped {o['certifications_skipped']} "
              f"incumbents {o['incumbents']}")
    speed = [r for r in harness.speed_rows(args.results_dir) if r["host"] == host and r["method"] == METHOD]
    by_hold = defaultdict(list)
    for r in speed:
        by_hold[r["hold"]].append(float(r["probe_s"]))
    print()
    for h, ps in sorted(by_hold.items()):
        print(f"speed check {h}: {len(ps)} probes, median {med(ps):.3f} s [{min(ps):.3f}–{max(ps):.3f}], spread "
              f"{100 * (max(ps) - min(ps)) / med(ps):.0f} %")
    stops = Counter(o["stop"] for o in out)
    print(f"stops: {dict(stops)}; over budget: {sum(o['e1b_runtime_s'] > BUDGET for o in out)} E1b, "
          f"{sum((o['b2_runtime_s'] or 0) > BUDGET for o in out)} B2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
