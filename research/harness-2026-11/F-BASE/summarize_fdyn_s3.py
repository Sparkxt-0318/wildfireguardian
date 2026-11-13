"""Summarise the S3 run (DESIGN.md (e)) from fdyn_e/*.jsonl. Columns exactly as (e) fixes them; no pass/fail.
Rates are over ALL jobs; UNRESOLVED jobs are counted separately. Violations are relative to the time-dependent model.

    python summarize_fdyn_s3.py --dir fdyn_e --out RESULTS_fdyn_s3.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

WAITABLE = ("NO_ROUTE / REFUSED verdicts depend on the as-built waitable rule (which nodes the router lets a vehicle "
            "wait at); see RESULTS.md 'Where the waitable rule comes from'.")
DELTAS = ("600", "1800", "3600")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    groups = defaultdict(list)
    problems, headers = [], []
    for f in sorted(a.dir.glob("*.jsonl")):
        lines = [json.loads(l) for l in f.read_text().splitlines()]
        headers.append({k: lines[0].get(k) for k in ("packet", "started_utc", "script_sha256")})
        region, _, h, variant = lines[0]["packet"].split(":")
        for r in lines[1:]:
            if "status" in r or not r.get("instance_sha_matches_c"):
                problems.append(dict(packet=lines[0]["packet"], origin=r["origin"], departure=r["departure"],
                                     status=r.get("status")))
                continue
            for reading in ("no_reentry", "reopening"):
                for d in DELTAS:
                    groups[(region, h, variant, reading, d)].append((r[reading]["exact"], r[reading][f"s3_{d}"]))
    rows = []
    for (region, h, variant, reading, d), js in sorted(groups.items(), key=lambda kv: (kv[0][:4], int(kv[0][4]))):
        n = len(js)
        oc = {o: sum(1 for _, s in js if s["outcome"] == o) for o in ("ROUTE", "VIOLATION", "REFUSED", "UNRESOLVED")}
        ii = sum(1 for e, s in js if s["outcome"] == "REFUSED" and e[0] == "ROUTE")
        dT = [s["T"] - e[1] for e, s in js if s["outcome"] == "ROUTE" and e[0] == "ROUTE"]
        rows.append(dict(region=region, horizon_h=int(h), variant=variant, reading=reading, delta_s=int(d), jobs=n,
                         exact_route=sum(1 for e, _ in js if e[0] == "ROUTE"), outcomes=oc,
                         i_violation=dict(count=oc["VIOLATION"], denominator=n, rate=oc["VIOLATION"] / n),
                         ii_refuses_resolvable=dict(count=ii, denominator=n, rate=ii / n),
                         legal_route=dict(count=oc["ROUTE"], denominator=n, rate=oc["ROUTE"] / n),
                         route_replays_all=all(s.get("replays") for _, s in js if s["outcome"] == "ROUTE"),
                         route_but_exact_no_route=sum(1 for e, s in js if s["outcome"] == "ROUTE" and e[0] != "ROUTE"),
                         T_minus_exact_s=dict(n=len(dT), median=float(np.median(dT)) if dT else None,
                                              max=int(max(dT)) if dT else None, min=int(min(dT)) if dT else None,
                                              positive=int(sum(x > 0 for x in dT))),
                         max_plans=max(s["plans"] for _, s in js)))
    tot = {}
    for reading in ("no_reentry", "reopening"):
        for d in DELTAS:
            rr = [r for r in rows if r["reading"] == reading and r["delta_s"] == int(d)]
            tot[f"{reading}_d{d}"] = dict(jobs=sum(r["jobs"] for r in rr),
                                          exact_route=sum(r["exact_route"] for r in rr),
                                          **{o: sum(r["outcomes"][o] for r in rr) for o in rows[0]["outcomes"]},
                                          ii=sum(r["ii_refuses_resolvable"]["count"] for r in rr),
                                          route_replays_all=all(r["route_replays_all"] for r in rr),
                                          route_but_exact_no_route=sum(r["route_but_exact_no_route"] for r in rr))
    out = dict(rule="DESIGN.md (e)", wording="violations are relative to the time-dependent model",
               waitable_note=WAITABLE, headers=headers, problems=problems, totals=tot, rows=rows)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(problems=len(problems), scripts=sorted({h["script_sha256"] for h in headers}), totals=tot),
                     indent=1))
    print("region | h | variant | reading | Δ | jobs | ROUTE/VIOL/REF/UNRES | (i) | (ii) | T−exact med/max (n>0)")
    for r in rows:
        o, t = r["outcomes"], r["T_minus_exact_s"]
        print(f"{r['region']} | {r['horizon_h']} | {r['variant']} | {r['reading']} | {r['delta_s']} | {r['jobs']} | "
              f"{o['ROUTE']}/{o['VIOLATION']}/{o['REFUSED']}/{o['UNRESOLVED']} | {r['i_violation']['count']} | "
              f"{r['ii_refuses_resolvable']['count']} | {t['median']}/{t['max']} ({t['positive']})")


if __name__ == "__main__":
    main()
