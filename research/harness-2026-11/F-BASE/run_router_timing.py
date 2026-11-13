"""Router (SIPP) search-only timing on the 20 frozen panel missions, like for like with F-BASE (DESIGN.md rule 4 and the
dated 2026-11-12 section): each mission in a fresh process, median of 3; instance construction (packet load +
frontend.build_instance) timed separately from search (wfg_sipp.sipp.solve). The router's verdict and arrival second
are checked against F-3.2's recorded panel summary, so a timing row is only reported for an agreeing run.

Uses Thomas's F-3.2 code at its frozen commit, unchanged: cases.korean_cases(), ContactModel.from_packet,
frontend.build_instance, sipp.solve. Run from that worktree's root with its PYTHONPATH:

    PYTHONPATH=experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src \
      python <repo>/research/harness-2026-11/F-BASE/run_router_timing.py --f32 research/harness-2026-11/F-3.2 \
      --summary research/harness-2026-11/F-3.2/results/panel_summary_py312.json --out RESULTS_router_timing.json
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


def child(f32, mission):
    sys.path.insert(0, str(Path(f32).resolve()))
    import cases
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.frontend import build_instance
    from wfg_sipp import sipp as S
    c = next(c for c in cases.korean_cases() if c["mission"] == mission)
    t0 = time.perf_counter()
    graph = json.loads(Path(c["graph"]).read_text())
    request = json.loads(Path(c["request"]).read_text())
    model = ContactModel.from_packet(c["packet"])
    inst, _ = build_instance(graph, request, model)
    t1 = time.perf_counter()
    res = S.solve(inst)
    t2 = time.perf_counter()
    # Same mapping as F-3.2 generate.certify: FOUND -> ROUTE at res["arrival"]; EXHAUSTED -> NO_ROUTE; else unresolved.
    claim = {"FOUND": "ROUTE", "EXHAUSTED": "NO_ROUTE"}.get(res["status"], "UNRESOLVED:" + res["status"])
    T = res["arrival"] if res["status"] == "FOUND" else None
    print(json.dumps(dict(raw_keys=sorted(res.keys()), status=res.get("status"), claim=claim, T=T,
                          build_s=t1 - t0, search_s=t2 - t1,
                          peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f32", type=Path, required=True)
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--child", default=None)
    a = ap.parse_args()
    if a.child:
        child(a.f32, a.child)
        return
    summary = json.loads(a.summary.read_text())
    rows = []
    for ref in summary:
        m = ref["mission"]
        rec = [ref["recorded_sipp"][0][0], ref["recorded_sipp"][0][1]]
        runs = []
        for _ in range(a.repeats):
            r = subprocess.run([sys.executable, __file__, "--f32", str(a.f32), "--summary", str(a.summary),
                                "--out", "-", "--child", m], capture_output=True, text=True)
            if r.returncode:
                runs = None
                rows.append(dict(mission=m, recorded=rec, status="FAILED", err=r.stderr.strip()[-400:]))
                break
            runs.append(json.loads(r.stdout.strip().splitlines()[-1]))
        if not runs:
            print(json.dumps(rows[-1])[:300], flush=True)
            continue
        f = runs[0]
        row = dict(mission=m, recorded=rec, claim=f["claim"], T=f["T"], status=f["status"], raw_keys=f["raw_keys"],
                   agrees=(f["claim"] == rec[0] and (f["T"] == rec[1] or rec[0] == "NO_ROUTE")),
                   consistent_across_repeats=all((x["claim"], x["T"]) == (f["claim"], f["T"]) for x in runs),
                   build_s_median=statistics.median(x["build_s"] for x in runs),
                   search_s_median=statistics.median(x["search_s"] for x in runs),
                   peak_rss_mib_max=max(x["peak_rss_mib"] for x in runs))
        rows.append(row)
        print(json.dumps({k: row[k] for k in ("mission", "recorded", "claim", "T", "agrees", "build_s_median",
                                              "search_s_median", "peak_rss_mib_max")}), flush=True)
    a.out.write_text(json.dumps(dict(rule="DESIGN.md rule 4 + dated 2026-11-12 (search only; build separate)",
                                     rows=rows), indent=1))


if __name__ == "__main__":
    main()
