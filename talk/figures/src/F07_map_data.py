"""Inputs of the real-map F07 and F08: Uiseong-Andong, 25 March 2025, 18:00 KST, computed with research/kcf-replay's own
code (the same setup as F04_routing.py) and written to build/F07_map.json (committed). F07_map.py and F08_map.py only
read that file.

1. Known fire area and road-cell blocking seconds at 18:00 KST, MEASURED arm, 8 h (replay.Region, measured_arms).
2. Backward: one pass of deadline_field.core.backward with every shelter used by any village of the region accepting at
   once (the shelters of replay.run_one). Every road node gets its latest safe departure. The two villages outside the
   known fire area must get the same latest departure as the stored replay (scene.js hourly lsd); checked.
3. Forward: one time-dependent search from Wondang-ri, leaving at 18:00:00, edge by edge in order of arrival time
   (turn restrictions and blocked edge starts as in the instance; no waiting), until the first accepted arrival at a
   shelter. It records every road edge the search looked at. This is the repository's illustration of "one search
   per village and per departure time"; it is not the earlier method's code (an external kit, research/kcf-bench).
4. One backward step on one real road of Wondang-ri's route: the route edge whose fire blocking sets the village's
   leave-by time. Its latest safe arrival at the far end, drive time, the second the fire blocks the road, and the
   resulting latest departure min(arrival - drive, block start - 1) are recorded and checked against the field.
"""
import hashlib
import heapq
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIG = HERE.parent
REGION = "uiseong_andong_2025"
PLACE = "osm:node/415160430"          # Wondang-ri
T_ISO = "2025-03-25T09:00:00+00:00"   # 18:00 KST
K = 6
H = 8 * 3600
ROUTING = Path(os.environ.get("WFG_ROUTING", "/Users/jp/wildfireguardian-forecast/data/routing"))


def load_scene():
    s = (REPO / "planner/public/kcf-scene/data/scene.js").read_text()
    i = s.index("=", s.index("KCF") + 20)
    return json.loads(s[i + 1:].strip().rstrip(";"))


def hms_to_s(txt):
    """'03-25 18:15' -> seconds after 18:00 (minute resolution)."""
    hh, mm = map(int, txt.split()[1].split(":"))
    return (hh - 18) * 3600 + mm * 60


def main():
    sc = load_scene()
    assert sc["issue_utc"][K] == "2025-03-25T09:00:00Z"
    gpath = ROUTING / f"graphs/{REGION}/graph.json"
    want = [x for x in sc["built"]["inputs"] if x["path"] == f"data/routing/graphs/{REGION}/graph.json"][0]["sha256"]
    got = hashlib.sha256(gpath.read_bytes()).hexdigest()
    assert got == want, ("graph SHA-256 differs from scene.js built.inputs", got, want)
    tmp = Path(tempfile.mkdtemp())
    (tmp / "data").mkdir()
    (tmp / "data/routing").symlink_to(ROUTING)
    (tmp / "planner").symlink_to(REPO / "planner")
    sys.path.insert(0, str(REPO / "research/kcf-replay"))
    import replay
    import measured_arms as MA
    from deadline_field import core
    replay.ROOT = tmp
    replay.init([REGION], str(REPO / "research/kcf-replay/fire_discs.json"))
    R = replay.REG[REGION]
    T = datetime.fromisoformat(T_ISO)
    dist = R.cell_distance(replay.DISCS, T)
    r5, r8, cls_, info = MA.curve("MEASURED", replay.DISCS, T, H // 3600)
    close_s = {}
    for c in range(len(dist)):
        if np.isfinite(dist[c]):
            s = MA.closure_s(r5, r8, float(dist[c]))
            if s <= H:
                close_s[c] = int(math.ceil(s))
    cells = sc["roadCells"][REGION]["cells"]
    stored = sc["close"]["MEASURED"][REGION][K]
    for c, v in zip(cells, stored):
        assert close_s.get(c, -1) == v, (c, close_s.get(c), v)
    inst = R.instance(close_s, H)
    E = len(inst.tail)
    N = len(R.node_ids)

    # ------------------------------------------------------------------ backward: one pass from every shelter
    shelters = {}
    for oid, (o, near) in R.cands.items():
        for s in near:
            shelters.setdefault(s["properties"]["entry"]["node"], s)
    inst.A = [[] for _ in range(E)]
    for snode in shelters:
        sn = R.nidx[snode]
        acc = R.accept(close_s, sn, H)
        for j in R.inc_by_node.get(sn, []):
            inst.A[j] = sorted(set(map(tuple, inst.A[j])) | set(map(tuple, acc)))
    inst.AN = {}
    fld = core.backward(inst)
    node_ld = np.full(N, -1, dtype=np.int64)
    for n in range(N):
        b = close_s.get(R.node_cell[n])
        inst.IB = {n: [(b, H)] if b is not None else []}
        S = core.issue_set(fld, n)
        if S:
            node_ld[n] = S[-1][1]
    states = core.check_fixed_point(fld)
    inst.IB = {}
    # villages: latest departure from this one pass against the stored replay (3 nearest shelters per village)
    villages = []
    for oid, (o, near) in R.cands.items():
        on = R.nidx[o["properties"]["entry"]["node"]]
        h = sc["hourly"]["MEASURED"][oid][K]
        ld = int(node_ld[on])
        if h["state"] == "LATEST_SAFE_DEPARTURE":
            assert ld >= 0 and ld // 60 * 60 == hms_to_s(h["lsd"]), (oid, ld, h["lsd"])
        villages.append({"id": oid, "name": o["properties"].get("name"), "name_en": o["properties"].get("name_en"),
                         "lonlat": o["geometry"]["coordinates"], "entry_node": o["properties"]["entry"]["node"],
                         "state": h["state"], "ld_one_pass_s": ld, "lsd_stored": h.get("lsd") or None})

    # ------------------------------------------------------------------ forward from Wondang-ri at 18:00:00
    o, near = R.cands[PLACE]
    on = R.nidx[o["properties"]["entry"]["node"]]
    t0 = 0
    b0 = close_s.get(R.node_cell[on])
    assert b0 is None or b0 > t0
    acc_edge = [bool(a) for a in inst.A]

    def blocked(j, t):
        return any(lo <= t <= hi for lo, hi in inst.B[j])

    def accepted(j, t):
        return any(lo <= t <= hi for lo, hi in inst.A[j])

    best = {}
    heap = []
    looked = set()
    for j in inst.out[on]:
        looked.add(j)
        if not blocked(j, t0) and t0 + inst.D[j] <= H:
            heapq.heappush(heap, (t0 + inst.D[j], j))
    found = None
    pops = 0
    while heap:
        t, j = heapq.heappop(heap)
        if j in best:
            continue
        best[j] = t
        pops += 1
        if acc_edge[j] and accepted(j, t):
            found = (j, t)
            break
        for k in inst.out[inst.head[j]]:
            if (j, k) in inst.forbidden:
                continue
            looked.add(k)
            if k in best or blocked(k, t) or t + inst.D[k] > H:
                continue
            heapq.heappush(heap, (t + inst.D[k], k))
    assert found is not None
    # the field agrees: leaving at 18:00:00 is inside Wondang-ri's departure set
    inst.IB = {on: [(b0, H)] if b0 is not None else []}
    S_on = core.issue_set(fld, on)
    inst.IB = {}
    assert any(lo <= t0 <= hi for lo, hi in S_on), S_on

    # ------------------------------------------------------------------ one backward step on a route road (F08)
    raw = json.loads(gpath.read_text())
    eid = {e["id"]: e for e in raw["edges"]}
    jid = {e: j for j, e in enumerate(R.g.edge_ids)}
    route = sc["routes"]["MEASURED"][PLACE][K]
    redges = sc["routeEdges"][REGION]
    t = route["ld"]
    steps = []
    for i in route["e"]:
        e = eid[redges[i]["id"]]
        j = jid[e["id"]]
        lo = inst.B[j][0][0] if inst.B[j] else None
        g_hi = max(hi for _, hi in fld.G[j]) if fld.G[j] else None
        cand = min(g_hi - inst.D[j], (lo - 1) if lo is not None else H)
        # the second the fire blocks the road cell that sets lo, and where along the edge that cell ends
        seg = None
        for s in e["segments"]:
            b = close_s.get(int(s["cell"]))
            if b is None:
                continue
            start = max(math.ceil(b - inst.D[j] * float(s["end"])), 0)
            if lo is not None and start == lo:
                seg = {"cell": int(s["cell"]), "block_s": b, "end_fraction": float(s["end"])}
                break
        steps.append({"edge": e["id"], "j": j, "way": e["source_way"], "depart_s": t, "drive_s": inst.D[j],
                      "latest_arrival_far_end_s": g_hi, "block_start_s": lo, "fire_cell": seg,
                      "latest_departure_via_edge_s": cand, "tail_node_ld_s": int(node_ld[inst.tail[j]]),
                      "binding": "fire" if lo is not None and lo - 1 < g_hi - inst.D[j] else "arrival",
                      "lonlat": []})
        t += inst.D[j]
    from pyproj import Transformer
    tr = Transformer.from_crs(5179, 4326, always_xy=True)
    for st in steps:
        e = eid[st["edge"]]
        xy = np.array([R.g.xy(e["u"]), R.g.xy(e["v"])], dtype=float)
        lo_, la_ = tr.transform(xy[:, 0], xy[:, 1])
        st["lonlat"] = np.round(np.column_stack([lo_, la_]), 6).tolist()
        st["length_m"] = round(float(np.hypot(*(xy[1] - xy[0]))), 1)
    # the F08 road: the first route edge where the fire, not the arrival, sets the time, and which equals the
    # village's leave-by time when driven from the latest departure
    pick = next(s for s in steps if s["binding"] == "fire" and s["latest_departure_via_edge_s"] == s["depart_s"])

    # ------------------------------------------------------------------ geometry for drawing
    xy = np.array([R.g.xy(n) for n in R.node_ids], dtype=float)
    lon, lat = tr.transform(xy[:, 0], xy[:, 1])
    seen, pairs, blocked0, fwd = set(), [], [], []
    for j in range(E):
        u, v = inst.tail[j], inst.head[j]
        key = (min(u, v), max(u, v))
        if key not in seen:
            seen.add(key)
            pairs.append(key)
    blocked_pairs = sorted({(min(inst.tail[j], inst.head[j]), max(inst.tail[j], inst.head[j]))
                            for j in range(E) if inst.B[j] and inst.B[j][0][0] == 0})
    fwd_pairs = sorted({(min(inst.tail[j], inst.head[j]), max(inst.tail[j], inst.head[j])) for j in best})
    looked_pairs = sorted({(min(inst.tail[j], inst.head[j]), max(inst.tail[j], inst.head[j])) for j in looked})
    # forward route (predecessor chain is not kept: rebuild by walking back over best arrival times)
    fj, ft = found
    chain = [fj]
    while inst.tail[chain[-1]] != on:
        j = chain[-1]
        prev = [i for i in inst.inc[inst.tail[j]] if i in best and best[i] + inst.D[j] == best[j]
                and (i, j) not in inst.forbidden]
        assert prev, j
        chain.append(prev[0])
    chain.reverse()
    out = {
        "region": REGION, "issue_utc": T_ISO, "standin": "MEASURED", "horizon_s": H, "graph_sha256": got,
        "measured_class": cls_, "R8_m": r8, "blocked_cells": len(close_s),
        "backward": {"shelter_nodes": len(shelters), "passes": 1, "fixed_point": "PASS", "states_checked": states,
                     "nodes": N, "nodes_with_departure": int((node_ld >= 0).sum()), "edges": E},
        "forward": {"origin": PLACE, "depart_s": t0, "edges_settled": len(best), "edges_looked_at": len(looked),
                    "arrival_s": ft, "shelter_node": R.node_ids[inst.head[fj]], "route_edges": len(chain),
                    "route_lonlat": [[float(lon[inst.tail[chain[0]]]), float(lat[inst.tail[chain[0]]])]] +
                                    [[float(lon[inst.head[j]]), float(lat[inst.head[j]])] for j in chain],
                    "field_departure_set_contains_depart": True},
        "villages": villages,
        "shelters_lonlat": [list(s["geometry"]["coordinates"]) for s in shelters.values()],
        "route_lonlat": None, "route_ld_s": route["ld"], "route_arr_s": route["arr"],
        "f08_step": pick, "route_steps": steps,
        "node_lonlat": np.round(np.column_stack([lon, lat]), 6).tolist(),
        "node_ld_s": node_ld.tolist(),
        "edge_pairs": pairs, "blocked_at_issue_pairs": blocked_pairs, "forward_settled_pairs": fwd_pairs,
        "forward_looked_pairs": looked_pairs,
        "made_by": "talk/figures/src/F07_map_data.py",
        "made_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # router cells with a blocking second, inside the drawn area: corners in lon/lat (EPSG:5179 square of 375 m)
    cells_out = []
    for c, b in sorted(close_s.items()):
        x0, x1, y0, y1 = (float(v) for v in R.grid.rect(c))
        lo_, la_ = tr.transform([x0, x1, x1, x0], [y0, y0, y1, y1])
        if 128.60 <= min(lo_) and max(lo_) <= 128.76 and 36.30 <= min(la_) and max(la_) <= 36.40:
            cells_out.append({"cell": c, "block_s": b, "lonlat": np.round(np.column_stack([lo_, la_]), 6).tolist()})
    out["cells"] = cells_out
    out["cell_size_m"] = float(R.grid.res)
    rl = []
    for i in route["e"]:
        a, b = redges[i]["c"]
        if not rl or rl[-1] != a:
            rl.append(a)
        rl.append(b)
    out["route_lonlat"] = rl
    (FIG / "build/F07_map.json").write_text(json.dumps(out, separators=(",", ":")))
    print(json.dumps({k: {q: w for q, w in out[k].items() if q != "route_lonlat"} for k in ("backward", "forward")}))
    print("f08", {k: v for k, v in pick.items() if k != "lonlat"})
    print("villages with departure", [(v["name"], v["ld_one_pass_s"], v["lsd_stored"]) for v in villages
                                      if v["ld_one_pass_s"] >= 0])


if __name__ == "__main__":
    main()
