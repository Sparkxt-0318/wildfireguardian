"""Summarise the S1/S2 run (DESIGN.md (d)) from fdyn_d/*.jsonl. Columns exactly as (d) fixes them; no pass/fail.

    python summarize_fdyn_static.py --dir fdyn_d --out RESULTS_fdyn_static.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

WAITABLE = ("NO_ROUTE verdicts depend on the as-built waitable rule (which nodes the router lets a vehicle wait at); "
            "see RESULTS.md 'Where the waitable rule comes from'.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    groups = defaultdict(list)
    problems = []
    for f in sorted(a.dir.glob("*.jsonl")):
        lines = [json.loads(l) for l in f.read_text().splitlines()]
        region, _, h, variant = lines[0]["packet"].split(":")
        for r in lines[1:]:
            if "status" in r or not r.get("instance_sha_matches_c"):
                problems.append(dict(packet=lines[0]["packet"], origin=r["origin"], departure=r["departure"],
                                     status=r.get("status")))
                continue
            for reading in ("no_reentry", "reopening"):
                groups[(region, h, variant, reading)].append(r[reading])
    rows = []
    for (region, h, variant, reading), rs in sorted(groups.items()):
        n = len(rs)
        ex_route = [x for x in rs if x["exact"][0] == "ROUTE"]
        i_cnt = sum(x["i_s1_route_rejected"] for x in rs)
        ii_cnt = sum(x["ii_s2_refuses_resolvable"] for x in rs)
        delay = [x["s2"][1] - x["exact"][1] for x in rs if x["exact"][0] == "ROUTE" and x["s2"][0] == "ROUTE"]
        s1_replay = [x for x in rs if x["s1"][0] == "ROUTE" and x["s1_replays_true"]]
        s1_diff_T = sum(1 for x in s1_replay if x["exact"][0] == "ROUTE" and x["s1"][1] != x["exact"][1])
        verdicts = lambda k: {v: sum(1 for x in rs if x[k][0] == v) for v in ("ROUTE", "NO_ROUTE")}  # noqa: E731
        rows.append(dict(
            region=region, horizon_h=int(h), variant=variant, reading=reading, requests=n,
            exact=verdicts("exact"), s1=verdicts("s1"), s2=verdicts("s2"),
            i_s1_route_rejected=dict(count=i_cnt, denominator=n, rate=i_cnt / n if n else None),
            ii_s2_refuses_resolvable=dict(count=ii_cnt, denominator=len(ex_route),
                                          rate=ii_cnt / len(ex_route) if ex_route else None),
            s2_delay_s=dict(n=len(delay), median=float(np.median(delay)) if delay else None,
                            mean=float(np.mean(delay)) if delay else None, max=int(max(delay)) if delay else None,
                            positive=int(sum(d > 0 for d in delay))),
            s1_replays=len(s1_replay), s1_replays_different_T=s1_diff_T))
    tot = {}
    for reading in ("no_reentry", "reopening"):
        rr = [r for r in rows if r["reading"] == reading]
        n = sum(r["requests"] for r in rr)
        er = sum(r["exact"]["ROUTE"] for r in rr)
        tot[reading] = dict(requests=n, exact_route=er, exact_no_route=sum(r["exact"]["NO_ROUTE"] for r in rr),
                            i=sum(r["i_s1_route_rejected"]["count"] for r in rr),
                            ii=sum(r["ii_s2_refuses_resolvable"]["count"] for r in rr),
                            s1_replays_different_T=sum(r["s1_replays_different_T"] for r in rr))
    out = dict(rule="DESIGN.md (d)", waitable_note=WAITABLE, problems=problems, totals=tot, rows=rows)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(problems=len(problems), totals=tot), indent=1))
    hdr = "region | h | variant | reading | n | exact R/NR | S1 R/NR | S2 R/NR | (i) | (ii) | S2 delay med/max (n>0) | S1 replay≠T"
    print(hdr)
    for r in rows:
        d = r["s2_delay_s"]
        print(f"{r['region']} | {r['horizon_h']} | {r['variant']} | {r['reading']} | {r['requests']} | "
              f"{r['exact']['ROUTE']}/{r['exact']['NO_ROUTE']} | {r['s1']['ROUTE']}/{r['s1']['NO_ROUTE']} | "
              f"{r['s2']['ROUTE']}/{r['s2']['NO_ROUTE']} | {r['i_s1_route_rejected']['count']}/{r['requests']} | "
              f"{r['ii_s2_refuses_resolvable']['count']}/{r['ii_s2_refuses_resolvable']['denominator']} | "
              f"{d['median']}/{d['max']} ({d['positive']}) | {r['s1_replays_different_T']}")


if __name__ == "__main__":
    main()
