"""Aggregates results/work/*.json.gz into numbers.json and place_hours.csv (PROTOCOL 6). Pure counting; no tuning."""
import csv, glob, gzip, json, statistics as st, collections, sys
from pathlib import Path
from kq import real

HERE = Path(__file__).resolve().parent
pp = {}
for r in csv.DictReader(open(real.ROOT / "research/kcf-replay/per_place.csv")):
    if r["standin"] == "MEASURED" and r["horizon"] == "8h":
        pp[(r["region"], r["place_id"], r["issue_kst"])] = r["departure_state"]

def kst(hu): return "03-25 %02d:00" % (hu + 9) if hu + 9 < 24 else "03-26 %02d:00" % (hu + 9 - 24)

rows = []
for fn in sorted(glob.glob(str(HERE / "results/work/*.json.gz"))):
    d = json.load(gzip.open(fn, "rt"))
    for r in d["rows"]:
        r["ff_state"] = pp.get((r["region"], r["place_id"], kst(r["issue_utc"])))
        rows.append(r)

def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + .5))] if xs else None

def mins(x): return None if x is None else round(x / 60, 2)

def stats(xs):
    return {"n": len(xs), "median_min": mins(st.median(xs)) if xs else None, "p25_min": mins(q(xs, .25)), "p75_min": mins(q(xs, .75)),
            "p90_min": mins(q(xs, .9)), "max_min": mins(max(xs)) if xs else None}

def block(rs):
    out = {"place_hours": len(rs)}
    cls = collections.Counter()
    for r in rs:
        if r["S_free"] is None: cls["A_spread_alone_exceeds_free_flow_window"] += 1
        elif r["isolated_s"] is None: cls["B_own_queue_prevents_clearing"] += 1
        elif r["contested_s"] is None: cls["C_sharing_with_neighbours_prevents_clearing"] += 1
        else: cls["D_clears"] += 1
    out["classes"] = dict(cls)
    ok = [r for r in rs if r["contested_s"] is not None and r["isolated_s"] is not None]
    out["shift_vs_L0_contested"] = stats([r["L0"] - r["contested_s"] for r in ok])
    out["shift_vs_L0_isolated"] = stats([r["L0"] - r["isolated_s"] for r in ok])
    qe = [r["S_free"] - r["isolated_s"] for r in ok]
    se = [r["isolated_s"] - r["contested_s"] for r in ok]
    out["queue_effect_S_free_minus_isolated"] = stats(qe)
    out["sharing_effect_isolated_minus_contested"] = stats(se)
    for lab, xs in (("queue", qe), ("sharing", se)):
        out[lab + "_effect_counts"] = {">0s": sum(x > 0 for x in xs), ">=60s": sum(x >= 60 for x in xs), ">=300s": sum(x >= 300 for x in xs), ">=900s": sum(x >= 900 for x in xs), "n": len(xs)}
    out["sharing_negative"] = sum(x < 0 for x in se)
    ck = collections.Counter()
    for r in rs:
        for s in ("isolated", "contested"):
            v = r.get(s + "_cert_valid")
            if v is not None: ck[(s, v)] += 1
    out["certificates_checked"] = {"%s_%s" % k: v for k, v in ck.items()}
    bind = collections.Counter(); bplaces = collections.defaultdict(set)
    for r in ok:
        b = r.get("contested_bind")
        if not b: continue
        key = ("way", b["way"]) if b["kind"] == "edge" else (b["kind"], None)
        bind[key] += 1; bplaces[key].add((r["region"], r["place_id"]))
    out["binding_by_kind"] = collections.Counter(r["contested_bind"]["kind"] for r in ok if r.get("contested_bind"))
    out["binding_by_kind"] = dict(out["binding_by_kind"])
    top = sorted(((len(v), bind[k], k) for k, v in bplaces.items() if k[0] == "way"), reverse=True)[:12]
    out["top_binding_ways"] = [{"way": k[1], "places": n, "place_hours": c} for n, c, k in top]
    return out

nums = {"rows": len(rows)}
for pn in sorted({r["param"] for r in rows}):
    rs = [r for r in rows if r["param"] == pn]
    nums[pn] = block(rs)
    nums[pn]["by_free_flow_state"] = {s: block([r for r in rs if r["ff_state"] == s])["classes"] for s in sorted({r["ff_state"] for r in rs if r["ff_state"]})}
json.dump(nums, open(HERE / "results/numbers.json", "w"), indent=1, default=str)
cols = ["region", "issue_utc", "param", "place_id", "name", "sigungu", "eupmyeon", "ff_state", "N", "W", "L0", "S_free", "isolated_s", "contested_s", "neighbours", "contested_nb_unrouted"]
with open(HERE / "results/place_hours.csv.gz", "wt") as _: pass
with gzip.open(HERE / "results/place_hours.csv.gz", "wt", newline="") as f:
    w = csv.writer(f); w.writerow(cols + ["bind_kind", "bind_way", "bind_slack", "iso_cert", "cont_cert"])
    for r in rows:
        b = r.get("contested_bind") or {}
        w.writerow([r.get(c) for c in cols] + [b.get("kind"), b.get("way"), b.get("slack"), r.get("isolated_cert_valid"), r.get("contested_cert_valid")])
print(json.dumps({k: (v if k == "rows" else {kk: v[kk] for kk in ("place_hours", "classes", "shift_vs_L0_contested", "queue_effect_counts", "sharing_effect_counts")}) for k, v in nums.items()}, indent=1, default=str))
