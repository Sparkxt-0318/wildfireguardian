"""Village cards: exits, dangerous road, forest share, clearance time, trigger line, departure order, pickup list.

No new science. Everything here is arithmetic or standard graph search on what the tool already computes:

* exits and the dangerous road: ``exits.py`` (edge-disjoint routes to any shelter, fire-independent);
* forest share: ``data/edges/<region>_forest.csv.gz`` (OSM wood/forest within 50 m of the road, from the planner
  basemap; the repository has no conifer map, so the conifer share is reported as not available);
* clearance time = vehicles / capacity of the narrowest road on the route (road class from the basemap, capacities
  from settings with their sources in data/traffic_sources.json);
* trigger line: the deadline field run a second time with every closure moved ``margin_min`` earlier gives the latest
  departure that keeps that margin on the whole route and at the shelter; minus the clearance time this is the
  trigger time; the trigger line is the fire input's own arrival isochrone at the trigger time;
* departure order: villages whose routes share a road leave one after another (latest-start scheduling, latest
  deadline last); pickup: van routes visiting places with residents assumed to have no car, most urgent first.
"""
from __future__ import annotations

import csv
import gzip
import math
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

from . import exits as ex
from . import fireinput, fmt
from .errors import Refusal, reason
from .regiondata import PRODUCT

DEFAULT = Path(__file__).with_name("cards.toml")
_SCHEMA = {
    "trigger": {"margin_min": (int, float)},
    "exits": {"max_exits": (int,)},
    "traffic": {"vehicles_per_household": (int, float), "no_car_share": (int, float), "cap_motorway": (int, float),
                "cap_trunk": (int, float), "cap_primary": (int, float), "cap_secondary": (int, float),
                "cap_tertiary": (int, float), "cap_other": (int, float)},
    "pickup": {"van_seats": (int,), "vans": (int,), "board_s_per_person": (int, float), "unload_s": (int, float)},
}
CLASS_CAP = {"motorway": "cap_motorway", "motorway_link": "cap_motorway", "trunk": "cap_trunk", "trunk_link": "cap_trunk",
             "primary": "cap_primary", "primary_link": "cap_primary", "secondary": "cap_secondary",
             "secondary_link": "cap_secondary", "tertiary": "cap_tertiary", "tertiary_link": "cap_tertiary"}
CLASS_KO = {"motorway": "고속도로", "trunk": "자동차전용·간선", "primary": "국도급", "secondary": "지방도급", "tertiary": "군도급",
            "unclassified": "마을길", "residential": "마을길", "service": "진입로", "track": "농로·임도", "living_street": "생활도로",
            "unmatched": "미확인", "path": "소로"}


def load_settings(path=None) -> dict:
    with open(DEFAULT, "rb") as f:
        s = tomllib.load(f)
    src = [DEFAULT.name]
    if path is not None:
        p = Path(path)
        if not p.is_file():
            raise Refusal(reason("SETTINGS_MISSING", "카드 설정 파일이 없습니다: %s" % p, "card settings file not found: %s" % p))
        with open(p, "rb") as f:
            user = tomllib.load(f)
        for sec, vals in user.items():
            for k, v in vals.items():
                if sec not in _SCHEMA or k not in _SCHEMA[sec]:
                    raise Refusal(reason("SETTINGS_INVALID", "알 수 없는 카드 설정 %s.%s" % (sec, k), "unknown card setting %s.%s" % (sec, k)))
                s[sec][k] = v
        src.append(str(p))
    for sec, keys in _SCHEMA.items():
        for k, typ in keys.items():
            v = s[sec][k]
            if isinstance(v, bool) or not isinstance(v, typ) or v < 0:
                raise Refusal(reason("SETTINGS_INVALID", "카드 설정 %s.%s 값이 잘못됨: %r" % (sec, k, v),
                                     "card setting %s.%s has an invalid value: %r" % (sec, k, v)))
    if not 0 <= s["traffic"]["no_car_share"] <= 1 or s["pickup"]["van_seats"] < 1 or s["pickup"]["vans"] < 1 \
            or s["exits"]["max_exits"] < 1 or any(s["traffic"][k] <= 0 for k in s["traffic"] if k.startswith("cap_")):
        raise Refusal(reason("SETTINGS_INVALID", "카드 설정 범위 오류", "card settings out of range"))
    s["_sources"] = src
    return s


# ------------------------------------------------------------------------------------------------ bundled data
def load_edge_data(rid: str):
    forest = {}
    with gzip.open(PRODUCT / "data/edges" / ("%s_forest.csv.gz" % rid), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            forest[r["edge_id"]] = int(r["forest_share_permille"]) / 1000
    ways = {}
    with gzip.open(PRODUCT / "data/edges" / ("%s_ways.csv.gz" % rid), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ways[int(r["source_way"])] = {"class": r["kind_detail"] or r["kind"], "name": r["name"], "ref": r["ref"]}
    return forest, ways


def load_households(rid: str):
    return {r["place_id"]: r for r in csv.DictReader(open(PRODUCT / "data/households" / ("%s.csv" % rid), encoding="utf-8"))}


def way_label(ways, w, lang="ko"):
    """Road name for a card: route number and name from the basemap when OSM has them, the class, and the OSM way id."""
    m = ways.get(w) or {}
    cls = m.get("class") or "unmatched"
    parts = []
    if lang == "ko":
        if m.get("ref"):
            parts.append("%s번" % m["ref"])
        if m.get("name"):
            parts.append(m["name"])
        parts.append("(%s, OSM way %s)" % (CLASS_KO.get(cls.replace("_link", ""), cls), w))
    else:
        if m.get("ref"):
            parts.append("route %s" % m["ref"])
        if m.get("name"):
            parts.append("%s (%s)" % (fmt.romanize(m["name"]), m["name"]))
        parts.append("(%s, OSM way %s)" % (cls, w))
    return " ".join(parts)


def edge_cap(road, ways, tcfg, j):
    cls = (ways.get(road.source_way[j]) or {}).get("class") or "unmatched"
    return tcfg[CLASS_CAP.get(cls, "cap_other")], cls


class _AllCells:
    """Shim so that fireinput.load_geotiff resamples every cell of the routing lattice (for the trigger line), with the
    same earliest-pixel rule as for road cells."""

    def __init__(self, road):
        self.road_cells = range(road.W * road.H)
        self.cell_rect = road.cell_rect


def full_grid_arrival(c) -> dict:
    fire = c["fire"]
    if fire.kind != "geotiff":
        return dict(fire.arrival_s)  # packets: road cells only
    f2 = fireinput.load_geotiff(fire.path, _AllCells(c["region"].road), issue_utc=fire.issue_utc, horizon_min=fire.horizon_s / 60,
                                not_reached_value=fire.info.get("not_reached_value"))
    return f2.arrival_s


def edge_len_m(road, j):
    (x0, y0), (x1, y1) = road.node_xy[road.tail[j]], road.node_xy[road.head[j]]
    return math.hypot(x1 - x0, y1 - y0)


# ------------------------------------------------------------------------------------------------ per place
def route_edges(row):
    if row.get("last") is not None and row["last"]["w_last"] is not None:
        return [l[1] for l in row["last"]["w_last"]["legs"] if l[0] == "EDGE"], "last"
    return None, None


def compute(c, cm, ccfg) -> list:
    """c: pipeline.compute() at the issue time; cm: the same with closures moved margin earlier. One record per
    origin, refused ones included (with the refusal)."""
    region, road = c["region"], c["region"].road
    H = c["H"]
    tcfg = ccfg["traffic"]
    forest, ways = load_edge_data(region.id)
    hh = load_households(region.id)
    shelter_nodes = {s["node"] for s in region.shelters if s["node"] is not None}
    sh_by_node = defaultdict(list)
    for s in region.shelters:
        if s["node"] is not None:
            sh_by_node[s["node"]].append(s)
    fg = ex.FlowGraph(road, shelter_nodes)
    by_m = {r["origin"]["id"]: r for r in cm["rows"]}
    out = []
    for row in c["rows"]:
        o = row["origin"]
        rec = {"origin": o, "row": row, "refusal": row["refusal"]}
        out.append(rec)
        if row["refusal"]:
            continue
        s = o["node"]
        a = ex.analyse(fg, s, ccfg["exits"]["max_exits"], excluded_sinks=[s] if s in shelter_nodes else [])
        paths = []
        for p in a["paths"]:
            L = sum(edge_len_m(road, j) for j in p)
            fo = sum(edge_len_m(road, j) * forest.get(road.edge_ids[j], 0.0) for j in p)
            end = road.head[p[-1]] if p else s
            sh = sorted(sh_by_node.get(end, []), key=lambda x: x["id"])
            caps = [edge_cap(road, ways, tcfg, j) for j in p]
            paths.append({"edges": p, "length_m": L, "travel_s": sum(road.D[j] for j in p), "forest_share": (fo / L) if L else 0.0,
                          "shelter": sh[0] if sh else None, "min_cap": min(caps)[0] if caps else None})
        rec["exits"] = a["exits"]
        rec["paths"] = paths
        d = a["danger"]
        rec["danger"] = d
        rec["single_exit"] = a["exits"] == 1
        rec["danger_all"] = bool(d and a["exits"] >= 2 and d["cut"] == a["exits"])
        # traffic
        h = hh.get(o["id"])
        if h is None:
            raise Refusal(reason("HOUSEHOLDS_MISSING", "세대 자료 없음: %s" % o["id"], "no household row for %s" % o["id"]))
        rec["hh"] = h
        if h["kind"] == "care_facility":
            households, vehicles = 0.0, 0
            no_car_persons = int(h["facility_residents"])
        else:
            households = float(h["households"])
            vehicles = int(math.ceil(households * tcfg["vehicles_per_household"]))
            no_car_persons = int(round(households * tcfg["no_car_share"] * float(h["persons_per_household"])))
        rec.update(households=households, vehicles=vehicles, no_car_persons=no_car_persons)
        edges, kind = route_edges(row)
        if edges is None and paths:
            edges, kind = paths[0]["edges"], "exit1"
        rec["route_kind"] = kind
        rec["route_edges"] = edges or []
        if edges:
            capj = sorted(((edge_cap(road, ways, tcfg, j), j) for j in edges), key=lambda x: (x[0][0], x[1]))[0]
            rec["narrow_cap"], rec["narrow_class"], rec["narrow_way"] = capj[0][0], capj[0][1], road.source_way[capj[1]]
            rec["clearance_s"] = int(math.ceil(vehicles / rec["narrow_cap"] * 3600))
        else:
            rec["narrow_cap"] = rec["narrow_class"] = rec["narrow_way"] = None
            rec["clearance_s"] = None
        # leave-by with and without clearance; with margin; trigger
        cl = rec["clearance_s"] or 0
        rec["leave_by"] = row["leave_by"] if row["cut"] is not None else None
        rec["no_deadline"] = row["cut"] is None
        rec["leave_by_clear"] = (row["leave_by"] - cl) if rec["leave_by"] is not None else None
        rm = by_m[o["id"]]
        rec["m_refusal"] = rm["refusal"]
        if rm["refusal"] or rm["cut"] is None:
            rec["leave_by_m"] = None
            rec["m_no_deadline"] = not rm["refusal"]
        else:
            rec["leave_by_m"] = rm["leave_by"]
            rec["m_no_deadline"] = False
        if rec["m_no_deadline"]:
            rec["trigger_s"] = None
            rec["trigger_state"] = "beyond_horizon"
        elif rec["leave_by_m"] is None:
            rec["trigger_s"] = None
            rec["trigger_state"] = "passed"
        else:
            t = rec["leave_by_m"] - cl
            rec["trigger_s"] = t
            rec["trigger_state"] = "passed" if t <= 0 else "line"
        rec["horizon"] = H
    return out


# ------------------------------------------------------------------------------------------------ departure order
def departure_order(recs, road, ways, tcfg):
    """Villages whose routes (at the latest departure) share a road in the same direction leave one after another.
    Latest-start scheduling, latest deadline last: start_i = min(deadline_i - clearance_i, min over shared roads of
    (start of the village scheduled after it on that road - its vehicles / that road's capacity)). Travel time between
    the village and the shared road is ignored (stated). Villages without a deadline in the horizon use the horizon's
    last departure and come last."""
    use = defaultdict(set)
    for i, r in enumerate(recs):
        if r["refusal"] or r["row"]["leave_by"] is None or r["route_kind"] != "last":
            continue
        for j in r["route_edges"]:
            use[(road.source_way[j], road.edge_ids[j].rsplit(":", 1)[-1])].add(i)
    shared = {k: v for k, v in use.items() if len(v) >= 2}
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    res_of = defaultdict(set)
    for k, v in shared.items():
        v = sorted(v)
        for i in v:
            res_of[i].add(k)
            parent[find(i)] = find(v[0])
    groups = defaultdict(list)
    for i in res_of:
        groups[find(i)].append(i)
    gid = 0
    for root, members in sorted(groups.items(), key=lambda kv: min(recs[i]["row"]["leave_by"] for i in kv[1])):
        gid += 1
        free = {}
        order = sorted(members, key=lambda i: (-recs[i]["row"]["leave_by"], recs[i]["origin"]["id"]))
        for i in order:
            r = recs[i]
            dl = r["row"]["leave_by"]
            start = dl - (r["clearance_s"] or 0)
            for k in res_of[i]:
                if k in free:
                    cap = tcfg[CLASS_CAP.get((ways.get(k[0]) or {}).get("class") or "unmatched", "cap_other")]
                    start = min(start, free[k] - int(math.ceil(r["vehicles"] / cap * 3600)))
            for k in res_of[i]:
                free[k] = start
            r["dep_start"] = start
        seq = sorted(members, key=lambda i: (recs[i]["dep_start"], recs[i]["origin"]["id"]))
        cnt = Counter(k[0] for i in members for k in res_of[i])
        top = [w for w, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
        for n, i in enumerate(seq, 1):
            recs[i].update(dep_group="G%d" % gid, dep_pos=n, dep_size=len(seq), dep_roads=top,
                           dep_late=max(0, -recs[i]["dep_start"]),
                           dep_before=recs[seq[n - 2]]["origin"] if n > 1 else None)
    for r in recs:
        r.setdefault("dep_group", None)
    return len(groups)


# ------------------------------------------------------------------------------------------------ pickup
def pickup(recs, region, horizon_s, pcfg, log=lambda *_: None):
    """Van routes over the places with residents assumed to have no car. Vans start at the depot (the shelter most
    often used as the last road out) at the issue time; the next stop is always the unserved place with the earliest
    leave-by (no deadline in the horizon: last), served by the van that can be there first; a full van drives to the
    nearest candidate shelter of the place it is at and unloads. Fire-free fastest roads (turn restrictions kept);
    the van is not routed around fire: a stop reached after the place's leave-by is marked late. Planning stops when no
    van can reach the next stop inside the forecast horizon; residents not picked up by then are reported unserved."""
    road = region.road
    stops = [r for r in recs if not r["refusal"] and r["no_car_persons"] > 0]
    reach = [r for r in stops if r["row"]["leave_by"] is not None]
    unreach = [r for r in stops if r["row"]["leave_by"] is None]
    use = Counter(r["row"]["last"]["shelter"]["node"] for r in recs if not r["refusal"] and r["row"].get("last"))
    depot_node = sorted(use.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if use else region.shelters[0]["node"]
    depot = next(s for s in region.shelters if s["node"] == depot_node)
    targets = {r["origin"]["node"] for r in stops} | {s["node"] for r in stops for s in r["row"]["candidates"]} | {depot_node}
    cache = {}

    def tt(a, b):
        if a == b:
            return 0
        if a not in cache:
            cache[a] = road.fastest_ticks(a, targets)
        v = cache[a].get(b)
        return v if v is not None else None

    seats = pcfg["van_seats"]
    vans = [{"van": k + 1, "node": depot_node, "t": 0, "load": 0, "where": depot["name"]} for k in range(pcfg["vans"])]
    pending = sorted(reach, key=lambda r: (r["leave_by"] if r["leave_by"] is not None else 1 << 40, r["origin"]["id"]))
    left = {id(r): r["no_car_persons"] for r in pending}
    log_rows = []

    def unload(v, near_rec):
        best = None
        for s in near_rec["row"]["candidates"]:
            d = tt(v["node"], s["node"])
            if d is not None and (best is None or d < best[0]):
                best = (d, s)
        if best is None:
            return False
        v["t"] += best[0]
        log_rows.append({"van": v["van"], "kind": "unload", "where": best[1], "arrive": v["t"], "persons": v["load"], "rec": near_rec})
        v["t"] += pcfg["unload_s"]
        v["node"], v["load"] = best[1]["node"], 0
        v["last_rec"] = None
        return True

    guard = 0
    while pending:
        guard += 1
        if guard > 100000:
            break
        r = pending[0]
        node = r["origin"]["node"]
        best = None
        for v in vans:
            if v["load"] >= seats:
                continue
            d = tt(v["node"], node)
            if d is not None and (best is None or (v["t"] + d, v["van"]) < best[0]):
                best = ((v["t"] + d, v["van"]), v, d)
        if best is None:
            full = [v for v in vans if v["load"] >= seats]
            if full and all(not unload(v, v.get("last_rec") or r) for v in full):
                pending.pop(0)
            elif not full:
                pending.pop(0)  # unreachable by road from every van
            continue
        _, v, d = best
        if v["t"] + d > horizon_s:  # no van can be there inside the horizon: stop planning
            break
        v["t"] += d
        v["node"] = node
        board = min(left[id(r)], seats - v["load"])
        arrive = v["t"]
        v["t"] += int(board * pcfg["board_s_per_person"])
        v["load"] += board
        left[id(r)] -= board
        v["last_rec"] = r
        late = r["leave_by"] is not None and arrive > r["leave_by"]
        log_rows.append({"van": v["van"], "kind": "pickup", "rec": r, "arrive": arrive, "persons": board, "load": v["load"],
                         "late": late, "remaining": left[id(r)]})
        if left[id(r)] == 0:
            pending.pop(0)
        if v["load"] >= seats:
            unload(v, r)
    for v in vans:
        if v["load"] > 0 and v.get("last_rec") is not None:
            unload(v, v["last_rec"])
    # per place summary
    first = {}
    done_t = {}
    late_any = defaultdict(bool)
    for e in log_rows:
        if e["kind"] != "pickup":
            continue
        k = e["rec"]["origin"]["id"]
        first.setdefault(k, e)
        done_t[k] = e["arrive"]
        late_any[k] |= e["late"]
    for r in stops:
        k = r["origin"]["id"]
        r["pickup_first"] = first.get(k)
        r["pickup_last_s"] = done_t.get(k)
        r["pickup_late"] = late_any.get(k, False)
        r["pickup_unreachable"] = any(r is u for u in unreach)
        r["pickup_unserved"] = left.get(id(r), r["no_car_persons"]) if not r["pickup_unreachable"] else 0
    unserved = [r for r in reach if left[id(r)] > 0]
    return {"depot": depot, "log": log_rows, "unreachable": unreach, "stops": stops, "unserved": unserved, "left": left}
