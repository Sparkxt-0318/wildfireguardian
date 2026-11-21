"""Post hoc (labelled in RESULTS): cells on the fire-free fastest route of each movement, closed at the issue time
under M0/MR with tau 240, with their reopening times; the time the whole documented route is open again."""
import sys, json, math, os
__file__ = os.path.abspath("camp_tests.py")
sys.argv = ["camp_tests.py", "_work/graph.json", "out/_scratch"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camp_tests.py")).read().split("# ------------------------------------------------------------------ Test 4.2 and 4.3")[0]
exec(src)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "camp_tests.py")).read().split("# ------------------------------------------------------------------ Test 4.1: the two movements")[1].split("mv = {m")[0])
import heapq
def fastest(o, d):
    dist, heap, prev = {o: 0}, [(0, o)], {}
    while heap:
        t, v = heapq.heappop(heap)
        if v == d: break
        if t != dist[v]: continue
        for j in rd.out_by_node.get(v, []):
            w, nt = rd.head[j], t + rd.D[j]
            if nt < dist.get(w, 1 << 60): dist[w] = nt; prev[w] = j; heapq.heappush(heap, (nt, w))
    path, v = [], d
    while v != o:
        j = prev[v]; path.append(j); v = rd.tail[j]
    return path[::-1]
mv = {m["movement"]: m for m in read_csv(CAMP / "data/movements_tn2252.csv")}
out = {}
for m, t in (("a", "12:00"), ("b", "13:58")):
    M = mv[m]; o, _ = nearest_node(float(M["origin_lat"]), float(M["origin_lon"])); dn, _ = nearest_node(float(M["dest_lat"]), float(M["dest_lon"]))
    T = minutes("11-08", t)
    path = fastest(o, dn)
    cells = []
    for j in path:
        for c, _ in rd.seg[j]:
            if c not in cells: cells.append(c)
    cells = [rd.node_cell[o]] + [c for c in cells if c != rd.node_cell[o]]
    for v in ("M0", "MR"):
        CL, OP = windows_at(T, v, "w240")
        rows = []
        for c in cells:
            if c in CL and CL[c] == 0 and OP.get(c, 10**9) > 0:
                r = OP.get(c)
                rows.append({"cell": c, "road": next((name[j] for j in path if any(cc == c for cc, _ in rd.seg[j])), ""), "reopens": hhmm(T + r / 60) if r is not None else "never (no arrival in cell)"})
        fin = [T + OP[c] / 60 for c in cells if c in CL and CL[c] == 0 and c in OP and OP[c] > 0]
        never = sum(1 for x in rows if x["reopens"].startswith("never"))
        out["%s_%s_%s" % (m, t, v)] = {"route_cells": len(cells), "closed_at_issue": rows, "route_open_again": "never" if never else (hhmm(max(fin)) if fin else "open")}
        print(m, t, v, len(cells), "closed at issue:", [(x["road"], x["reopens"]) for x in rows], "-> open again", out["%s_%s_%s" % (m, t, v)]["route_open_again"])
json.dump(out, open("out/camp_test41_route_cells_posthoc.json", "w"), indent=1)
