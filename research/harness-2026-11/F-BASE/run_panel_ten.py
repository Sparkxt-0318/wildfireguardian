"""Run F-BASE-TEN (third-party BFS on the explicit time-expanded network) on the frozen panel missions.

Dated addition to DESIGN.md (2026-11-12, Iris's critique). A mission runs only if its arc count is <= --max-arcs;
missions above the budget are listed with their size, not run. Each run is a fresh process: build time (graph
construction) and search time (BFS + goal scan + witness) reported separately; peak RSS. Exact witnesses are
spliced into the bundle and checked by F-3.2's check_py.py.

    python run_panel_ten.py --bundles DIR --f32 <F-3.2 dir at a03f218> --summary <panel_summary_py312.json>
"""
from __future__ import annotations

import argparse
import json
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def child(path):
    import fbase_ten as X
    t0 = time.perf_counter()
    I = X.parse(Path(path).read_text())
    t1 = time.perf_counter()
    claim, T, legs, stats = X.solve_ten(I)
    t2 = time.perf_counter()
    print(json.dumps(dict(claim=claim, T=T, legs=legs, stats=stats, parse_s=t1 - t0, build_and_search_s=t2 - t1,
                          build_s=stats.get("build_s"), peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                          scipy=X.SCIPY_VERSION)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundles", type=Path)
    ap.add_argument("--f32", type=Path)
    ap.add_argument("--summary", type=Path)
    ap.add_argument("--max-arcs", type=float, default=3.5e8)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, default=HERE / "RESULTS_panel_ten.json")
    ap.add_argument("--child", default=None)
    args = ap.parse_args()
    if args.child:
        child(args.child)
        return
    import fbase_ten as X
    from run_panel_fbase import splice_witness
    summary = {r["mission"]: r for r in json.loads(args.summary.read_text())}
    rows = []
    for path in sorted(p for p in args.bundles.glob("*.wfgc") if "fbase_witness" not in p.name and "ten_witness" not in p.name):
        mission = path.stem.split("__", 1)[1]
        ref = summary[mission]
        rec = [ref["recorded_sipp"][0][0], ref["recorded_sipp"][0][1]]
        I = X.parse(path.read_text())
        _, arcs_ub, nodes = X.count_arcs(I)
        row = dict(mission=mission, recorded=rec, nodes=nodes, arcs_upper_bound=arcs_ub)
        if arcs_ub > args.max_arcs:
            row["status"] = f"NOT RUN: arc upper bound {arcs_ub:.3g} > budget {args.max_arcs:.3g}"
        else:
            runs = []
            for _ in range(args.repeats):
                r = subprocess.run([sys.executable, __file__, "--child", str(path)], capture_output=True, text=True)
                if r.returncode != 0:
                    runs = None
                    row["status"] = "FAILED: " + r.stderr.strip()[-300:]
                    break
                runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
            if runs:
                f = runs[0]
                row.update(status="RUN", claim=f["claim"], T=f["T"], stats=f["stats"],
                           agrees=(f["claim"] == rec[0] and (f["T"] == rec[1] or rec[0] == "NO_ROUTE")),
                           consistent_across_repeats=all((x["claim"], x["T"]) == (f["claim"], f["T"]) for x in runs),
                           parse_s_median=statistics.median(x["parse_s"] for x in runs),
                           build_and_search_s_median=statistics.median(x["build_and_search_s"] for x in runs),
                           peak_rss_mib_max=max(x["peak_rss_mib"] for x in runs), scipy=f["scipy"])
                if f["claim"] == "ROUTE":
                    sp = path.with_suffix(".ten_witness.wfgc")
                    sp.write_text(splice_witness(path.read_text(), [tuple(l) for l in f["legs"]]))
                    c = subprocess.run([sys.executable, str(args.f32 / "check_py.py"), str(sp)], capture_output=True, text=True)
                    row["f32_check_py_on_ten_witness"] = c.stdout.strip() or c.stderr.strip()[-200:]
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("mission", "recorded", "status", "claim", "T", "agrees",
                                                   "build_and_search_s_median", "peak_rss_mib_max",
                                                   "f32_check_py_on_ten_witness")}), flush=True)
    ran = [r for r in rows if r["status"] == "RUN"]
    tally = dict(run=len(ran), agree=sum(r["agrees"] for r in ran), not_run=[r["mission"] for r in rows if r["status"] != "RUN"])
    args.out.write_text(json.dumps(dict(rule="DESIGN.md dated section 2026-11-12 (F-BASE-TEN)", tally=tally, rows=rows), indent=1))
    print(json.dumps(tally))


if __name__ == "__main__":
    main()
