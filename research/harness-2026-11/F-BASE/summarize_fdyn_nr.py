"""Summarise the (f) no-re-entry re-run (fdyn_f_nr1/*.jsonl): rule (d) S1/S2 columns and rule (e) S3 columns for the
labelled reading, plus acceptance (3): per departure, the NR verdicts next to reopening (from fdyn_d), reported only.

    python summarize_fdyn_nr.py --dir fdyn_f_nr1 --reopening fdyn_d --out RESULTS_fdyn_nr1.json
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

WAITABLE = ("NO_ROUTE / REFUSED counts depend on the as-built waitable rule: the graph.json 'waitable' flag, "
            "undocumented, empirically = graph dead end (RESULTS.md 'Where the waitable rule comes from').")
DELTAS = (600, 1800, 3600)


def med(x):
    return dict(n=len(x), median=float(np.median(x)) if x else None, max=int(max(x)) if x else None,
                positive=int(sum(v > 0 for v in x)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--reopening", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    groups, problems, headers = defaultdict(list), [], []
    reo = {}
    for f in sorted(a.reopening.glob("*.jsonl")):
        ls = [json.loads(l) for l in f.read_text().splitlines()]
        for r in ls[1:]:
            reo[(ls[0]["packet"], r["origin"], r["departure"])] = r["reopening"]["exact"][0]
    sig = Counter()
    labels = set()
    for f in sorted(list(a.dir.glob("*.jsonl")) + list(a.dir.glob("*.jsonl.gz"))):
        txt = gzip.decompress(f.read_bytes()).decode() if f.suffix == ".gz" else f.read_text()
        ls = [json.loads(l) for l in txt.splitlines()]
        h0 = ls[0]
        labels.add(h0["label"])
        headers.append({k: h0.get(k) for k in ("packet", "started_utc", "script_sha256", "nr_hazard_sha256")})
        region, _, h, variant = h0["packet"].split(":")
        for r in ls[1:]:
            if "status" in r:
                problems.append(dict(packet=h0["packet"], origin=r["origin"], departure=r["departure"], status=r["status"]))
                continue
            x = r["no_reentry"]
            groups[(region, h, variant)].append((r["departure"], x))
            sig[(r["departure"], x["exact"][0], reo.get((h0["packet"], r["origin"], r["departure"])))] += 1
    rows = []
    for (region, h, variant), js in sorted(groups.items()):
        n = len(js)
        xs = [x for _, x in js]
        er = sum(x["exact"][0] == "ROUTE" for x in xs)
        v = lambda k: {c: sum(x[k][0] == c for x in xs) for c in ("ROUTE", "NO_ROUTE")}  # noqa: E731
        row = dict(region=region, horizon_h=int(h), variant=variant, requests=n,
                   exact=v("exact"), s1=v("s1"), s2=v("s2"),
                   by_departure={str(d): dict(n=sum(dd == d for dd, _ in js),
                                              exact_no_route=sum(dd == d and x["exact"][0] == "NO_ROUTE" for dd, x in js))
                                 for d in sorted({dd for dd, _ in js})},
                   d_i_s1_route_rejected=dict(count=sum(x["i_s1_route_rejected"] for x in xs), denominator=n),
                   d_ii_s2_refuses_resolvable=dict(count=sum(x["ii_s2_refuses_resolvable"] for x in xs), denominator=er),
                   s2_delay_s=med([x["s2"][1] - x["exact"][1] for x in xs if x["exact"][0] == x["s2"][0] == "ROUTE"]),
                   s1_replays_different_T=sum(1 for x in xs if x["s1"][0] == "ROUTE" and x["s1_replays_true"]
                                              and x["exact"][0] == "ROUTE" and x["s1"][1] != x["exact"][1]),
                   s3={})
        for d in DELTAS:
            s = [x[f"s3_{d}"] for x in xs]
            oc = {o: sum(y["outcome"] == o for y in s) for o in ("ROUTE", "VIOLATION", "REFUSED", "UNRESOLVED")}
            row["s3"][str(d)] = dict(
                outcomes=oc, e_i_violation=dict(count=oc["VIOLATION"], denominator=n),
                e_ii_refuses_resolvable=dict(count=sum(y["ii_refuses_resolvable"] for y in s), denominator=n),
                route_replays_all=all(y["replays"] for y in s if y["outcome"] == "ROUTE"),
                T_minus_exact_s=med([y["T"] - x["exact"][1] for x, y in zip(xs, s)
                                     if y["outcome"] == "ROUTE" and x["exact"][0] == "ROUTE"]),
                max_plans=max(y["plans"] for y in s))
        rows.append(row)
    tot = dict(requests=sum(r["requests"] for r in rows), exact_route=sum(r["exact"]["ROUTE"] for r in rows),
               exact_no_route=sum(r["exact"]["NO_ROUTE"] for r in rows),
               d_i=sum(r["d_i_s1_route_rejected"]["count"] for r in rows),
               d_ii=sum(r["d_ii_s2_refuses_resolvable"]["count"] for r in rows),
               s3={str(d): {k: sum(r["s3"][str(d)]["outcomes"][k] for r in rows)
                            for k in ("ROUTE", "VIOLATION", "REFUSED", "UNRESOLVED")}
                   | dict(e_ii=sum(r["s3"][str(d)]["e_ii_refuses_resolvable"]["count"] for r in rows),
                          replays_all=all(r["s3"][str(d)]["route_replays_all"] for r in rows)) for d in DELTAS})
    out = dict(rule="DESIGN.md (f) (columns of (d) and (e))", labels=sorted(labels),
               wording="violations are relative to the time-dependent model", waitable_note=WAITABLE,
               headers=headers, problems=problems, totals=tot,
               acceptance3_signature=[dict(departure=k[0], nr_exact=k[1], reopening_exact=k[2], count=v)
                                      for k, v in sorted(sig.items(), key=str)], rows=rows)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(labels=sorted(labels), problems=len(problems),
                          scripts=sorted({h["script_sha256"] for h in headers}), totals=tot,
                          signature=out["acceptance3_signature"]), indent=1))
    for r in rows:
        s = r["s3"]
        print(f"{r['region']} h{r['horizon_h']} {r['variant']}: n={r['requests']} exact {r['exact']['ROUTE']}/{r['exact']['NO_ROUTE']} "
              f"S1 {r['s1']['ROUTE']}/{r['s1']['NO_ROUTE']} S2 {r['s2']['ROUTE']}/{r['s2']['NO_ROUTE']} "
              f"(i) {r['d_i_s1_route_rejected']['count']} (ii) {r['d_ii_s2_refuses_resolvable']['count']}/{r['d_ii_s2_refuses_resolvable']['denominator']} "
              f"S2dly {r['s2_delay_s']['median']}/{r['s2_delay_s']['max']} | S3 " +
              " ".join(f"{d}:{s[str(d)]['outcomes']['ROUTE']}/{s[str(d)]['outcomes']['VIOLATION']}/{s[str(d)]['outcomes']['REFUSED']}/{s[str(d)]['outcomes']['UNRESOLVED']} ii={s[str(d)]['e_ii_refuses_resolvable']['count']}" for d in DELTAS))


if __name__ == "__main__":
    main()
