"""Markdown tables for RESULTS.md from out/*.json and data/*.csv (no number typed by hand).
Usage: python3 -I make_tables.py > out/tables.md"""
import json

from model import HERE, VARIANTS, read_csv

T12 = json.load(open(HERE / "out/tests12.json"))
T3 = json.load(open(HERE / "out/test3_movements.json"))
VN = {"M0": "no margin", "M30": "30-min card margin", "MR": "frozen spread margin R(h)", "MR_running": "running-class R(h) (secondary)"}


def ci(c):
    return "%.2f–%.2f" % tuple(c) if c and c[0] is not None else "n/a"


def pct(x):
    return "n/a" if x is None else "%.0f%%" % (100 * x)


def med(m):
    if not m or not m["n"]:
        return "n/a"
    return "%+.0f (95%% CI %+.0f to %+.0f; IQR %+.0f to %+.0f; n = %d)" % (m["median"], m["ci95"][0], m["ci95"][1], m["iqr"][0], m["iqr"][1], m["n"])


print("### Test 1 table (strict hold-out: 500 m and ±60 min)\n")
print("| variant | road-closed rows scored | hits | misses (of which no closure at all) | hit rate (95% CI) | passable rows scored | false closures | false-closure rate (95% CI) | time error C − t, min: median | verdict |")
print("|---|---|---|---|---|---|---|---|---|---|")
for v in VARIANTS:
    s = T12["test1"]["strict"][v]
    print("| %s | %d | %d | %d (%d) | %s (%s) | %d | %d | %s (%s) | %s | **%s** |" % (VN[v], s["closed_scored"], s["hits"], s["misses"], s["misses_no_closure_at_all"],
          pct(s["hit_rate"]), ci(s["hit_ci95"]), s["passable_scored"], s["false_closures"], pct(s["false_closure_rate"]), ci(s["false_closure_ci95"]),
          med(s["time_error_min_closed_rows"]), s["verdict"]))
print("\nLeaky input (only exact duplicates of road-state rows removed), same columns:\n")
print("| variant | hits / scored | hit rate (95% CI) | false closures / passable | rate (95% CI) | time error median | verdict |")
print("|---|---|---|---|---|---|---|")
for v in VARIANTS:
    s = T12["test1"]["leaky"][v]
    print("| %s | %d / %d | %s (%s) | %d / %d | %s (%s) | %s | %s |" % (VN[v], s["hits"], s["closed_scored"], pct(s["hit_rate"]), ci(s["hit_ci95"]), s["false_closures"],
          s["passable_scored"], pct(s["false_closure_rate"]), ci(s["false_closure_ci95"]), med(s["time_error_min_closed_rows"]), s["verdict"]))
print("\nBy day (strict):\n")
print("| variant | 8 Nov hits / scored | 8 Nov false / passable | 9 Nov hits / scored | 9 Nov false / passable |")
print("|---|---|---|---|---|")
for v in VARIANTS:
    a, b = T12["test1"]["strict_11-08"][v], T12["test1"]["strict_11-09"][v]
    print("| %s | %d / %d | %d / %d | %d / %d | %d / %d |" % (VN[v], a["hits"], a["closed_scored"], a["false_closures"], a["passable_scored"], b["hits"], b["closed_scored"], b["false_closures"], b["passable_scored"]))

print("\n### Test 2 table (closed or inside the 30-min margin, of placed burnovers)\n")
print("| variant | at t − 60 | at t − 30 | at t | closed (not just unsafe) at t − 30 | lead of first closure before t, min | verdict |")
print("|---|---|---|---|---|---|---|")
for v in VARIANTS:
    d = T12["test2"]["all"][v]
    f = lambda k: "%d / %d (%s; %s)" % (d[k]["closed_or_unsafe"], d[k]["n"], pct(d[k]["share"]), ci(d[k]["ci95"]))
    print("| %s | %s | %s | %s | %d | %s | **%s** |" % (VN[v], f("t-60"), f("t-30"), f("t"), d["t-30"]["closed"], med(d["lead_min"]), d["verdict"]))
print("\nPer burnover (state at t − 60 / t − 30 / t; C = model closure of the first cell of the burnover stretch):\n")
print("| BO | place | start | " + " | ".join(VN[v] for v in VARIANTS) + " |")
print("|---|---|---|" + "---|" * len(VARIANTS))
for r in read_csv(HERE / "out/test2_burnovers.csv"):
    if r["placed"] != "yes":
        print("| %s | %s | %s %s | not placed: %s |" % (r["bo_id"], r["location"], r["date"][5:], r["initiation"], r["loc_note"]) + " |" * (len(VARIANTS) - 1))
        continue
    cells = []
    for v in VARIANTS:
        ab = {"CLOSED": "C", "UNSAFE": "U", "OPEN": "o"}
        cells.append("%s/%s/%s (C %s)" % (ab[r[v + "_t-60"]], ab[r[v + "_t-30"]], ab[r[v + "_t"]], r["C_" + v] or "never"))
    print("| %s | %s | %s %s%s | %s |" % (r["bo_id"], r["location"], r["date"][5:], r["initiation"], " (e)" if r["first_obs_flag"] == "e" else "", " | ".join(cells)))

print("\n### Test 3 table\n")
print("| movement, issue time | variant | road cells closed (at issue) | feasible at issue? | latest feasible departure | route (roads in order) | share on documented roads | pass |")
print("|---|---|---|---|---|---|---|---|")
for c in T3["cases"]:
    for v in VARIANTS:
        r = c["variants"][v]
        rt = r["route"]
        print("| (%s) %s | %s | %d (%d) | %s | %s | %s | %s | %s |" % (c["movement"], c["issue"], VN[v], r["closed_road_cells"], r["closed_at_issue"],
              "yes" if r["feasible_at_issue"] else "**no**", ("+%d s" % r["latest_departure_s"]) if r["latest_departure_s"] is not None else "none",
              " → ".join(rt["road_sequence"]) if rt else "—", pct(rt["share_on_documented"]) if rt else "—", "PASS" if r["pass"] else "FAIL"))
print("\nFire-free fastest routes (for the road match when the field is infeasible):\n")
for c in T3["cases"]:
    ff = c["fire_free_route"]
    print("* (%s) %s: %d s, %s, %s on documented roads; first closed cell on it: %s" % (c["movement"], c["issue"], c["fire_free_fastest_s"], " → ".join(ff["road_sequence"]),
          pct(ff["share_on_documented"]), "; ".join("%s: %s" % (v, (lambda x: "none" if not x else "%s, closes +%d s, reached +%d s" % (x["edge_name"], x["closure_s"], x["reached_at_s"]))(c["variants"][v]["fire_free_route_first_closed_cell"])) for v in VARIANTS)))
