"""Descriptive extras for RESULTS.md (counting only; PROTOCOL 6): cut-limited villages, binding roads with names, overlap diagnostic,
villages with no free-flow window, and paired LOW/MID/HIGH changes."""
import csv, glob, gzip, json, statistics as st, collections
from pathlib import Path
from kq import real

HERE = Path(__file__).resolve().parent
rows = []
for fn in sorted(glob.glob(str(HERE / "results/work/*.json.gz"))):
    if "oat" in fn: continue
    rows += json.load(gzip.open(fn, "rt"))["rows"]
pp = {}
cat = {}
for r in csv.DictReader(open(real.ROOT / "research/kcf-replay/per_place.csv")):
    if r["standin"] == "MEASURED" and r["horizon"] == "8h":
        h = (int(r["issue_kst"][6:8]) - 9) % 24
        pp[(r["region"], r["place_id"], h)] = r["departure_state"]; cat[r["place_id"]] = r["category"]
for r in rows: r["ff"] = pp[(r["region"], r["place_id"], r["issue_utc"])]
ways = {rid: real.cards.load_edge_data(rid)[1] for rid in real.REGIONS}
def mins(x): return round(x / 60, 2)
out = {}
# villages without any free-flow window / already inside
nv = collections.Counter()
for (rid, pid, h), s in pp.items():
    if cat[pid] in ("village", "hamlet"): nv[s] += 1
out["village_place_hours_by_free_flow_state"] = dict(nv)
for pn in ("LOW", "MID", "HIGH"):
    rs = [r for r in rows if r["param"] == pn and r["ff"] == "LATEST_SAFE_DEPARTURE"]
    ok = [r for r in rs if r["contested_s"] is not None]
    d = {"cut_limited_place_hours": len(rs), "clear": len(ok), "cannot_clear": len(rs) - len(ok)}
    sh = [r["L0"] - r["contested_s"] for r in ok]
    sf = [r["S_free"] - r["contested_s"] for r in ok]
    d["shift_vs_L0_min"] = {"median": mins(st.median(sh)), "max": mins(max(sh)), "n": len(sh)}
    d["shift_vs_S_free_min"] = {"median": mins(st.median(sf)), "max": mins(max(sf)), "n": len(sf),
                               "ge1": sum(x >= 60 for x in sf), "ge5": sum(x >= 300 for x in sf), "ge15": sum(x >= 900 for x in sf)}
    # overlap diagnostic: could neighbours' release window (0..W) overlap v's own (s..s+W)?
    ov = [r for r in ok if r["contested_s"] < r["W"] and r["neighbours"] > 0]
    d["clear_with_start_inside_neighbours_release_window"] = len(ov)
    bind = collections.Counter(); pl = collections.defaultdict(set)
    kinds = collections.Counter()
    for r in ok:
        b = r.get("contested_bind") or {}
        kinds[b.get("kind")] += 1
        if b.get("kind") == "edge":
            bind[(r["region"], b["way"])] += 1; pl[(r["region"], b["way"])].add(r["place_id"])
    d["binding_kind"] = dict(kinds)
    top = sorted(((len(v), bind[k], k) for k, v in pl.items()), reverse=True)[:10]
    d["top_binding_roads"] = [{"region": k[0], "osm_way": k[1], "places": n, "place_hours": c,
                              "class": (ways[k[0]].get(k[1]) or {}).get("class"), "name": (ways[k[0]].get(k[1]) or {}).get("name")} for n, c, k in top]
    d["roads_binding_for_ge2_places"] = sum(1 for v in pl.values() if len(v) >= 2)
    out[pn] = d
# paired changes for cut-limited rows present in all three params
key = lambda r: (r["region"], r["issue_utc"], r["place_id"])
by = {pn: {key(r): r for r in rows if r["param"] == pn and r["ff"] == "LATEST_SAFE_DEPARTURE"} for pn in ("LOW", "MID", "HIGH")}
both = [k for k in by["MID"] if k in by["LOW"] and k in by["HIGH"] and all(by[p][k]["contested_s"] is not None for p in by)]
d = {"n_clear_in_all_three": len(both)}
for a, b in (("LOW", "MID"), ("MID", "HIGH"), ("LOW", "HIGH")):
    x = [by[a][k]["contested_s"] - by[b][k]["contested_s"] for k in both]
    d["%s_minus_%s_start_min" % (a, b)] = {"median": mins(st.median(x)), "max": mins(max(x))}
out["paired_cut_limited"] = d
json.dump(out, open(HERE / "results/extra.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:5000])
