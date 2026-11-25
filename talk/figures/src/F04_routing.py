"""F04 stage (e) inputs: the 18:00 KST deadline field for Wondang-ri, computed with research/kcf-replay's own code.

Runs once and writes build/F04_routing.json (committed); F04_overview.py only reads that file.

What it does, with the replay's functions unchanged (research/kcf-replay/replay.py, measured_arms.py):
  1. known fire area and road-cell closure seconds at T = 2025-03-25 09:00 UTC (18:00 KST), MEASURED arm, 8 h
     (replay.Region.cell_distance, measured_arms.curve, measured_arms.closure_s), checked against the closures
     stored in planner/public/kcf-scene/data/scene.js (close.MEASURED.uiseong_andong_2025[6]);
  2. one backward pass (deadline_field.core.backward) from each of the place's three candidate shelters, exactly as
     replay.run_one sets them up; the latest departure of every road node is the maximum over the three shelters;
  3. checks that the origin's latest departure equals the stored witness route's `ld` (scene.js routes) and the
     per_place.csv row.

The road graph is the frozen routing input (tools/fetch_routing_inputs.py, not committed); its SHA-256 must equal the
one recorded in scene.js built.inputs. Set WFG_ROUTING to the folder holding graphs/ (default: the main checkout's
data/routing).
"""
import hashlib
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
PLACE = "osm:node/415160430"          # 원당리 Wondang-ri
T_ISO = "2025-03-25T09:00:00+00:00"   # 18:00 KST, the F02 issue hour
K = 6                                 # index of 09:00 UTC in the scene's 13 issue hours
H = 8 * 3600
ROUTING = Path(os.environ.get("WFG_ROUTING", "/Users/jp/wildfireguardian-forecast/data/routing"))


def load_scene():
    s = (REPO / "planner/public/kcf-scene/data/scene.js").read_text()
    i = s.index("=", s.index("KCF") + 20)
    return json.loads(s[i + 1:].strip().rstrip(";"))


def main():
    sc = load_scene()
    assert sc["issue_utc"][K] == "2025-03-25T09:00:00Z"
    gpath = ROUTING / f"graphs/{REGION}/graph.json"
    want = [x for x in sc["built"]["inputs"] if x["path"] == f"data/routing/graphs/{REGION}/graph.json"][0]["sha256"]
    got = hashlib.sha256(gpath.read_bytes()).hexdigest()
    assert got == want, ("graph SHA-256 differs from scene.js built.inputs", got, want)
    # replay.py reads ROOT/data/routing and ROOT/planner: point ROOT at a folder with both
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
    # check against the scene's stored closures for its road cells
    cells = sc["roadCells"][REGION]["cells"]
    stored = sc["close"]["MEASURED"][REGION][K]
    for c, v in zip(cells, stored):
        assert close_s.get(c, -1) == v, (c, close_s.get(c), v)
    inst = R.instance(close_s, H)
    o, near = R.cands[PLACE]
    on = R.nidx[o["properties"]["entry"]["node"]]
    E = len(inst.tail)
    node_ld = np.full(len(R.node_ids), -1, dtype=np.int64)
    per_shelter = {}
    for s in near:
        snode = s["properties"]["entry"]["node"]
        sn = R.nidx[snode]
        acc = R.accept(close_s, sn, H)
        inst.A = [[] for _ in range(E)]
        for j in R.inc_by_node.get(sn, []):
            inst.A[j] = list(acc)
        inst.AN = {}
        fld = core.backward(inst)
        ld_s = np.full(len(R.node_ids), -1, dtype=np.int64)
        for n in range(len(R.node_ids)):
            b = close_s.get(R.node_cell[n])
            inst.IB = {n: [(b, H)] if b is not None else []}
            S = core.issue_set(fld, n)
            if S:
                ld_s[n] = S[-1][1]
        node_ld = np.maximum(node_ld, ld_s)
        # certificate check of this field (order-independent fixed-point equation, deadline_field.core)
        states = core.check_fixed_point(fld)
        per_shelter[s["properties"]["id"]] = {"node": snode, "ld_at_origin_s": int(ld_s[on]),
                                              "nodes_with_departure": int((ld_s >= 0).sum()),
                                              "fixed_point": "PASS", "states_checked": states}
    route = sc["routes"]["MEASURED"][PLACE][K]
    assert int(node_ld[on]) == route["ld"], (int(node_ld[on]), route["ld"])
    edges = sc["routeEdges"][REGION]
    route_lonlat = []
    for i in route["e"]:
        a, b = edges[i]["c"]
        if not route_lonlat or route_lonlat[-1] != a:
            route_lonlat.append(a)
        route_lonlat.append(b)
    # nodes in lon/lat
    from pyproj import Transformer
    tr = Transformer.from_crs(5179, 4326, always_xy=True)
    xy = np.array([R.g.xy(n) for n in R.node_ids], dtype=float)
    lon, lat = tr.transform(xy[:, 0], xy[:, 1])
    # graph edges as node-index pairs (one per undirected way segment) for drawing
    seen, pairs, pair_way = set(), [], []
    for j in range(E):
        u, v = inst.tail[j], inst.head[j]
        key = (min(u, v), max(u, v))
        if key not in seen:
            seen.add(key)
            pairs.append(key)
            pair_way.append(R.g.source_way[j])
    # road blocked seconds per OSM way (earliest closed cell of the way, seconds after 18:00 KST)
    raw = json.loads(gpath.read_text())
    way_cells = {}
    for e in raw["edges"]:
        way_cells.setdefault(e["source_way"], set()).update(s["cell"] for s in e["segments"])
    route_ways = []
    eid = {e["id"]: e for e in raw["edges"]}
    for i in route["e"]:
        w = eid[edges[i]["id"]]["source_way"]
        if w not in route_ways:
            route_ways.append(w)
    ways_at_origin = sorted({eid[R.g.edge_ids[j]]["source_way"] for j in range(E)
                             if inst.tail[j] == on or inst.head[j] == on})
    way_block = {str(w): min((close_s[c] for c in cs if c in close_s), default=None) for w, cs in way_cells.items()}
    # the witness route driven from the latest departure: when it leaves each road cell, and when that cell is blocked
    t = route["ld"]
    legs = []
    for i in route["e"]:
        e = eid[edges[i]["id"]]
        for s in e["segments"]:
            legs.append({"way": e["source_way"], "cell": s["cell"], "exit_s": t + e["travel_ticks"] * s["end"],
                         "block_s": close_s.get(s["cell"])})
        t += e["travel_ticks"]
    assert t == route["arr"], (t, route["arr"])
    by_way = {}
    for g in legs:
        if g["block_s"] is None:
            continue
        slack = g["block_s"] - g["exit_s"]
        assert slack >= 0, g
        w = by_way.get(g["way"])
        if w is None or slack < w["slack_s"]:
            by_way[g["way"]] = {"way": g["way"], "block_s": g["block_s"], "exit_s": g["exit_s"], "slack_s": slack,
                                "order": route_ways.index(g["way"])}
    route_way_timing = sorted(by_way.values(), key=lambda w: w["order"])
    # independent replay of the witness route (research/kcf-replay/analyze.py::recheck)
    import analyze
    sh_cell = route["sh_cell"]
    ok, arr = analyze.recheck([edges[i]["id"] for i in route["e"]], eid, {str(k): v for k, v in close_s.items()},
                              route["ld"], route["arr"], sh_cell, H)
    assert ok and arr == route["arr"], (ok, arr)
    # one second later the same check must fail (the route is the latest)
    late_ok, _ = analyze.recheck([edges[i]["id"] for i in route["e"]], eid, {str(k): v for k, v in close_s.items()},
                                 route["ld"] + 1, None, sh_cell, H)
    sh = sc["shelters"][route["sh"]]
    out = {
        "region": REGION, "place_id": PLACE, "issue_utc": T_ISO, "standin": "MEASURED", "horizon_s": H,
        "graph_sha256": got, "graph_revision": raw["revision"],
        "measured_class": cls_, "measured_info": info, "R5_m": r5, "R8_m": r8,
        "closed_cells": len(close_s), "origin_node": R.node_ids[on],
        "origin_lonlat": [float(lon[on]), float(lat[on])],
        "ld_at_origin_s": int(node_ld[on]), "route_ld_s": route["ld"], "route_arr_s": route["arr"],
        "route_shelter": route["sh"], "route_shelter_lonlat": [sh["lon"], sh["lat"]],
        "shelter_category": sh["category"],
        "per_shelter": per_shelter,
        "shelters_lonlat": [[sc["shelters"][s["properties"]["id"]]["lon"], sc["shelters"][s["properties"]["id"]]["lat"]]
                            for s in near],
        "route_lonlat": route_lonlat, "route_ways": route_ways, "ways_at_origin": ways_at_origin,
        "way_block_s": {str(w): way_block[str(w)] for w in set(route_ways) | set(ways_at_origin)},
        "route_way_timing": route_way_timing,
        "witness_recheck": {"depart_s": route["ld"], "accepted": bool(ok), "arrival_s": arr,
                            "depart_one_second_later_accepted": bool(late_ok)},
        "node_lonlat": np.round(np.column_stack([lon, lat]), 6).tolist(),
        "node_ld_s": node_ld.tolist(),
        "edge_pairs": pairs,
        "edge_pair_way": pair_way,
        "checks": {"scene_road_cells_equal": len(cells), "origin_ld_equals_scene_route_ld": True},
        "made_by": "talk/figures/src/F04_routing.py",
        "made_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (FIG / "build/F04_routing.json").write_text(json.dumps(out, separators=(",", ":")))
    print("ld at origin", out["ld_at_origin_s"], "class", cls_, r5, r8, "closed cells", len(close_s),
          "nodes with departure", int((node_ld >= 0).sum()), "of", len(node_ld))
    print("ways at origin", ways_at_origin, "route ways", route_ways[:6], {w: out["way_block_s"][str(w)]
                                                                           for w in out["way_block_s"]})


if __name__ == "__main__":
    main()
