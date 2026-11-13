"""Summarise the (g) sensitivity run (fdyn_g_allwait/*.jsonl): waiting allowed at every node, for reopening and
no_reentry/1, with (d)/(e) columns and the verdict change vs the documented default (dead-end waiting) rows:
reopening default = fdyn_d (reopening), no_reentry/1 default = fdyn_f_nr1. No pass/fail (DESIGN.md (g)).

    python summarize_fdyn_allwait.py --dir fdyn_g_allwait --d-dir fdyn_d --f-dir fdyn_f_nr1 --out RESULTS_fdyn_allwait.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

LABEL = "SENSITIVITY: waiting allowed at every node (not the documented default; default = graph dead ends only)"


def load(d, key=None):
    out = {}
    for f in sorted(Path(d).glob("*.jsonl")):
        ls = [json.loads(l) for l in f.read_text().splitlines()]
        for r in ls[1:]:
            out[(ls[0]["packet"], r["origin"], r["departure"])] = r if key is None else r[key]
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ("--dir", "--d-dir", "--f-dir", "--out"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    g, dflt_ro, dflt_nr = load(a.dir), load(a.d_dir, "reopening"), load(a.f_dir, "no_reentry")
    rows_per_packet = Counter(k[0] for k in g)
    problems = [dict(key=list(k), reading=rd, status=v[rd].get("status")) for k, v in g.items()
                for rd in ("reopening", "no_reentry/1") if "status" in v[rd] or not v[rd].get("instance_sha_matches_verified")]
    res = {}
    for rd, dflt in (("reopening", dflt_ro), ("no_reentry/1", dflt_nr)):
        xs = {k: v[rd] for k, v in g.items() if "exact" in v[rd]}
        n = len(xs)
        er = sum(x["exact"][0] == "ROUTE" for x in xs.values())
        change = Counter((dflt[k]["exact"][0], x["exact"][0]) for k, x in xs.items())
        dT = [x["exact"][1] - dflt[k]["exact"][1] for k, x in xs.items() if x["exact"][0] == dflt[k]["exact"][0] == "ROUTE"]
        flips = [dict(packet=k[0], origin=k[1], departure=k[2], T_all_wait=x["exact"][1]) for k, x in sorted(xs.items())
                 if dflt[k]["exact"][0] == "NO_ROUTE" and x["exact"][0] == "ROUTE"]
        s3 = {}
        for d in (600, 1800, 3600):
            y = [x[f"s3_{d}"] for x in xs.values()]
            s3[str(d)] = dict(**{o: sum(z["outcome"] == o for z in y) for o in ("ROUTE", "VIOLATION", "REFUSED", "UNRESOLVED")},
                              e_ii=sum(z["ii_refuses_resolvable"] for z in y), replays_all=all(z["replays"] for z in y if z["outcome"] == "ROUTE"))
        res[rd] = dict(label=LABEL, requests=n, exact=dict(ROUTE=er, NO_ROUTE=n - er),
                       s1=dict(ROUTE=sum(x["s1"][0] == "ROUTE" for x in xs.values())),
                       s2=dict(ROUTE=sum(x["s2"][0] == "ROUTE" for x in xs.values())),
                       d_i=sum(x["i_s1_route_rejected"] for x in xs.values()),
                       d_ii=dict(count=sum(x["ii_s2_refuses_resolvable"] for x in xs.values()), denominator=er),
                       s3=s3,
                       change_vs_default_exact={f"{a_}->{b_}": c for (a_, b_), c in sorted(change.items())},
                       route_to_no_route=change[("ROUTE", "NO_ROUTE")],
                       T_change_where_both_route=dict(n=len(dT), earlier=sum(t < 0 for t in dT), same=sum(t == 0 for t in dT),
                                                      later=sum(t > 0 for t in dT), min=min(dT) if dT else None),
                       no_route_to_route=flips)
    out = dict(rule="DESIGN.md (g)", label=LABEL, rows_per_packet=dict(rows_per_packet), problems=problems, readings=res)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(packets=len(rows_per_packet), rows=sorted(set(rows_per_packet.values())), problems=len(problems),
                          **{rd: {k: v for k, v in r.items() if k not in ("no_route_to_route", "label")} for rd, r in res.items()}), indent=1))


if __name__ == "__main__":
    main()
