"""Validation against records the model never used (PROTOCOL.md §5, amendments 1-2).

Model output on reconstructed inputs. Not what happened to people.

Usage: python3 validation.py RUNS_DIR R_ROWS.json M_ROWS.json BURNED.json OVERTURE_DIR OUT_DIR
"""
from __future__ import annotations

import csv, heapq, json, re, statistics, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import tifffile
from pyproj import Transformer
from shapely import wkb
from shapely.geometry import Point

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/kcf-replay"))
import analyze as AN  # noqa: E402

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
T0_TOA = datetime(2025, 3, 22, 2, 24, tzinfo=UTC)
ISSUES = [datetime(2025, 3, 25, h, tzinfo=UTC) for h in range(3, 16)]
ARMS = ["MEASURED", "RUNNING", "ORDINARY", "WORST", "MEASURED_GUST_KMA", "MEASURED_GUST"]
PRIMARY = "MEASURED"
REGIONS = ("yeongdeok_2025", "uiseong_andong_2025")
LABEL = "Model output on reconstructed inputs. Not what happened to people."
TO_LL = Transformer.from_crs(5179, 4326, always_xy=True)


def kst(s):  # "2025-03-25 15:30" -> aware datetime
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


def fmt(dt):
    return dt.astimezone(KST).strftime("%m-%d %H:%M") if dt else ""


# ---------------------------------------------------------------- records (curated from records_raw/, SOURCES.md)
RAW = HERE / "records_raw"
ROADS = {r["id"]: r for r in json.loads((RAW / "records_roads.json").read_text())["records"]}
EVAC = {r["id"]: r for r in json.loads((RAW / "records_evac.json").read_text())["records"]}
NEWSRO = {"outlet": "뉴스로 (영덕군 조치사항 log, one outlet)", "url": "https://www.newsro.kr/articles/832886",
          "published": "2025-03-29 14:43", "retrieved": "2026-11-16 (page read, HTTP 200; research/kcf-replay/SOURCES.md)",
          "access": "full page"}


def src(raw):
    return {"outlet": raw.get("source_outlet") or raw.get("outlet"), "url": raw.get("url"),
            "published": raw.get("published_kst") or raw.get("published"), "retrieved": raw.get("retrieved_utc"),
            "access": "search snippet only"}


ROAD_RECORDS = [  # id, what, recorded KST, target spec, source
    ("RD1", "서산영덕선 안동JC~청송IC both ways, closure (도로공사)", "2025-03-25 15:30", ("ref", "30", "east_of_andong_jc"), src(ROADS["R1"])),
    ("RD2", "서산영덕선 서의성IC~영덕IC both ways, closure", "2025-03-25 17:00", ("ref", "30", "all"), src(ROADS["R3"])),
    ("RD3", "중앙선 의성IC~서안동IC both ways, closure", "2025-03-25 17:00", ("ref", "55", "all"), src(ROADS["R3"])),
    ("RD4", "중앙선 의성IC~예천IC, closure 'from 18:00' (outlet unidentified)", "2025-03-25 18:00", ("ref", "55", "all"), src(ROADS["R5"])),
    ("RD5", "서산영덕선 동상주IC~영덕IC, closure 'from 18:00' (outlet unidentified)", "2025-03-25 18:00", ("ref", "30", "all"), src(ROADS["R5"])),
    ("RD6", "서산영덕선 동상주IC~영덕IC both ways, closure", "2025-03-25 22:00", ("ref", "30", "all"), src(ROADS["R4"])),
    ("RD7", "중앙선 의성IC~풍기IC both ways, closure", "2025-03-25 22:00", ("ref", "55", "all"), src(ROADS["R4"])),
    ("RD8", "중앙선 의성IC~예천IC both ways, closure 'from 07:55'", "2025-03-26 07:55", ("ref", "55", "all"), src(ROADS["R9"])),
    ("RD9", "지방도 911 지품면 황장리~석보면 화매리, control (time of the county text)", "2025-03-25 19:09", ("path", "황장리", "화매리"), src(ROADS["R7"])),
    ("RD10", "황장재 통행제한 (CBS time)", "2025-03-25 18:25", ("hwangjangjae",), NEWSRO),
    ("RD11", "국도 34 (구미~황장) 교통 통제", "2025-03-25 18:58", ("path", "구미리", "황장리"), NEWSRO),
    ("RD12", "지품면 도계 → 영양 방향 도로통제", "2025-03-25 19:04", ("path", "도계리", "화매리"), NEWSRO),
    ("RD13", "국도 7 송라면 지경삼거리 → 영덕 방향 교통 통제", "2025-03-25 21:58", ("outside",), NEWSRO),
]
ROAD_EXCLUDED = {"R2": "same closure as R1 with a different end (청송JC); reported as a conflict, not a second record",
                 "R6": "no clock time", "R8": "reopening, not a closure", "R10": "status snapshot, not a start time",
                 "R11_context_24Mar": "24 March, before the replay window"}

EVAC_RECORDS = [  # id, county, scope, recorded KST, source
    ("EV1", "안동시", ("villages", ["어담리", "금계리", "인금리"]), "2025-03-25 15:31", src(EVAC["AND-01"])),
    ("EV2", "의성군", ("towns", ["단촌면"]), "2025-03-25 16:14", src(EVAC["US-01"])),
    ("EV3", "영덕군", ("towns", ["지품면"]), "2025-03-25 16:30", src(EVAC["YD-05"]) | {"note": "면장's own order, '4시 반경' (approximate)"}),
    ("EV4", "안동시", ("villages", ["하회리"]), "2025-03-25 16:55", src(EVAC["AND-03"]) | {"note": "'4시 55분쯤' (approximate)"}),
    ("EV5", "안동시", ("county",), "2025-03-25 17:00", src(EVAC["AND-04"]) | {"note": "English edition; called 대피령 by some outlets, 권고 by YTN"}),
    ("EV6", "청송군", ("county",), "2025-03-25 17:44", src(EVAC["CS-01"]) | {"note": "'5시 44분쯤' (approximate); 안전안내문자"}),
    ("EV7", "영덕군", ("towns", ["지품면", "달산면"]), "2025-03-25 18:00", NEWSRO),
    ("EV8", "영양군", ("towns", ["석보면"]), "2025-03-25 18:47", src(EVAC["YY-01"]) | {"note": "'6시 47분쯤' (approximate)"}),
    ("EV9", "영덕군", ("villages", ["옥류리"]), "2025-03-25 18:52", NEWSRO),
    ("EV10", "영덕군", ("villages", ["대리"]), "2025-03-25 19:18", NEWSRO),
    ("EV11", "영덕군", ("county",), "2025-03-25 19:30", NEWSRO),
    ("EV12", "영덕군", ("towns", ["창수면"]), "2025-03-25 19:40", NEWSRO),
    ("EV13", "영덕군", ("county",), "2025-03-25 21:00", NEWSRO),
]
EVAC_EXCLUDED = {"AND-02": "count of texts; same start as AND-01", "AND-05": "no clock time", "AND-06": "university, not a planner place",
                 "AND-07": "no clock time", "AND-08": "24 March", "AND-09": "24 March", "AND-10": "no clock time",
                 "AND-11": "26 March evening, after the replay", "CS-02": "no clock time", "CS-03": "plan, no time",
                 "YY-02": "no clock time", "YD-01": "no explicit time (17:54 + 6 min is arithmetic); the 뉴스로 18:00 row is EV7",
                 "YD-02": "21:00 = EV13 (뉴스로); conflicts with 뉴스로's 18:00 CBS", "YD-03": "19:30 = EV11 (English edition)",
                 "YD-04": "a road-control text (RD9), not an evacuation", "YD-06": "facility notice, English edition only, approximate",
                 "US-02": "24 March", "US-03": "no clock time"}

VILLAGE_ACCOUNTS = [  # research/kcf-replay/SOURCES.md, all single-source, REPORTED
    ("VA1", "매정리", "2025-03-25 20:40", "fire in the village, one resident's account (20:30 + 10 min, derived)", "한국일보 2025-03-27, https://www.hankookilbo.com/news/article/A2025032714350000238"),
    ("VA2", "화매리", "2025-03-25 18:00", "'화염이 마을 가장자리까지' ~18:00", "매일신문 2025-03-26, https://www.imaeil.com/page/view/2025032616432400355"),
    ("VA3", "강구리", "2025-03-26 00:37", "면-level: fire ~30 min after the 00:07 text (derived)", "경향신문 2025-03-26, https://www.khan.co.kr/article/202503261311001"),
]


# ---------------------------------------------------------------- geometry
class Region:
    def __init__(self, region, ways):
        raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
        g = raw["grid"]
        self.name = region
        self.x0, self.y0, self.res, self.W, self.H = g["x0"], g["y0"], g["resolution"], g["width"], g["height"]
        self.xy = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
        self.edges = raw["edges"]
        self.adj = defaultdict(list)
        for e in self.edges:
            self.adj[e["u"]].append((e["v"], e["travel_ticks"], e))
        self.ways = ways
        self.places = {}
        for f in json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]:
            p = f["properties"]
            if p.get("role") == "origin" and p.get("checkable"):
                self.places[p["id"]] = p

    def cell_xy(self, x, y):
        return int((y - self.y0) // self.res) * self.W + int((x - self.x0) // self.res)

    def centre(self, c):
        r, k = divmod(c, self.W)
        return self.x0 + (k + 0.5) * self.res, self.y0 + (r + 0.5) * self.res

    def ref_edges(self, ref):
        return [e for e in self.edges if ref in self.ways.get(e["source_way"], {}).get("refs", ())]

    def edge_cells(self, edges):
        return sorted({int(s["cell"]) for e in edges for s in e["segments"]})

    def place_by_name(self, name):
        return [p for p in self.places.values() if p.get("name") == name]

    def path(self, a, b):
        dist = {a: 0}; prev = {}; h = [(0, a)]
        while h:
            d, u = heapq.heappop(h)
            if u == b:
                break
            if d != dist.get(u):
                continue
            for v, t, e in self.adj[u]:
                if d + t < dist.get(v, 1 << 60):
                    dist[v] = d + t; prev[v] = (u, e); heapq.heappush(h, (d + t, v))
        if b not in dist:
            return None
        out = []; v = b
        while v != a:
            u, e = prev[v]; out.append(e); v = u
        return out[::-1]


def load_ways(odir):
    ways = defaultdict(lambda: {"refs": set(), "names": set()})
    for s in pq.read_table(Path(odir) / "segments.parquet", columns=["names", "routes", "sources"]).to_pylist():
        refs = {str(x.get("ref")) for x in (s["routes"] or []) if x.get("ref")}
        nm = (s["names"] or {}).get("primary")
        for so in s["sources"] or []:
            m = re.match(r"w(\d+)", so.get("record_id") or "")
            if m:
                w = ways[int(m.group(1))]; w["refs"] |= refs
                if nm:
                    w["names"].add(nm)
    return ways


def localities(odir):
    out = []
    for d in pq.read_table(Path(odir) / "divisions.parquet").to_pylist():
        if d["subtype"] == "locality" and d.get("class") == "land":
            out.append(((d["names"] or {}).get("primary"), wkb.loads(d["geometry"])))
    return out


# ---------------------------------------------------------------- road records
def road_cells(regs, spec):
    """-> {region: [cells]}, note"""
    kind = spec[0]
    if kind == "outside":
        return {}, "outside model domain (포항 송라면, south of the 영덕 grid)"
    if kind == "ref":
        _, ref, part = spec
        out = {}
        for R in regs.values():
            es = R.ref_edges(ref)
            if part == "east_of_andong_jc":
                jc = [e for e in R.edges if any("안동JCT" in n for n in R.ways.get(e["source_way"], {}).get("names", ()))]
                if not jc:
                    continue
                xj = np.mean([R.xy[e["u"]][0] for e in jc])
                es = [e for e in es if min(R.xy[e["u"]][0], R.xy[e["v"]][0]) >= xj]
            if es:
                out[R.name] = R.edge_cells(es)
        return out, f"route {ref}: all in-grid cells" + (" east of 안동JC" if part == "east_of_andong_jc" else "")
    R = regs["yeongdeok_2025"]
    if kind == "path":
        a = R.place_by_name(spec[1]); b = R.place_by_name(spec[2])
        if len(a) != 1 or len(b) != 1:
            return {}, f"not located ({spec[1]}: {len(a)}, {spec[2]}: {len(b)} places)"
        es = R.path(a[0]["entry"]["node"], b[0]["entry"]["node"])
        if es is None:
            return {}, "no path"
        share = {}
        for ref in ("34", "911"):
            share[ref] = round(sum(1 for e in es if ref in R.ways.get(e["source_way"], {}).get("refs", ())) / len(es), 2)
        return {R.name: R.edge_cells(es)}, f"shortest path {spec[1]}→{spec[2]}, {len(es)} edges; share on route 34 {share['34']}, 911 {share['911']}"
    if kind == "hwangjangjae":
        loc = dict(LOCS)["지품면"]
        hj = R.place_by_name("황장리")[0]
        xh = R.xy[hj["entry"]["node"]][0]
        es = [e for e in R.ref_edges("34") if R.xy[e["u"]][0] < xh
              and loc.contains(Point(*TO_LL.transform(*R.xy[e["u"]])))]
        return {R.name: R.edge_cells(es)}, f"route-34 cells in 지품면 west of 황장리 ({len(es)} edges)"
    raise ValueError(spec)


def run_file(runs, region, arm, T):
    p = Path(runs) / f"{region}__{arm}__8h__{T.strftime('%H')}.json"
    return json.loads(p.read_text())


def model_closure(runs, cells_by_region, arm, T):
    """earliest closure (datetime) over the cells, 'closed at issue' flag, or None if not closed within 8 h."""
    best = None; at_issue = False
    for region, cells in cells_by_region.items():
        cs = run_file(runs, region, arm, T)["close_s"]
        for c in cells:
            b = cs.get(str(c))
            if b is not None and (best is None or b < best):
                best = b
    if best is None:
        return None, False
    return T + timedelta(seconds=best), best == 0


def issue_for(t, lead_h):
    cands = [T for T in ISSUES if T <= t - timedelta(hours=lead_h)]
    return (cands[-1], True) if cands else (ISSUES[0], False)


# ---------------------------------------------------------------- main
LOCS = []


def main(runs, r_rows, m_rows, burned, odir, outdir):
    global LOCS
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    ways = load_ways(odir)
    LOCS = localities(odir)
    regs = {r: Region(r, ways) for r in REGIONS}
    discs = json.loads((ROOT / "research/kcf-replay/fire_discs.json").read_text())["discs"]
    for d in discs:
        d["ts"] = datetime.fromisoformat(d["t_utc"]).timestamp()
    recon = {}
    for r, R in regs.items():
        cx = np.array([R.centre(c)[0] for c in range(R.W * R.H)]); cy = np.array([R.centre(c)[1] for c in range(R.W * R.H)])
        recon[r] = AN.first_cut_times(discs, cx, cy)
    toa = tifffile.imread(ROOT / "research/harness-2026-11/data-fetch/small/choi2026_kfs01/KFS_01_pswt_ok_toa.tif").astype(float)

    def toa_at(region, c):
        x, y = regs[region].centre(c)
        a = toa[int((1845375 - y) // 375), int((x - 1085250) // 375)]
        return T0_TOA + timedelta(hours=float(a)) if np.isfinite(a) else None

    table = []
    # ---- 5.1 roads
    road_out = []
    for rid, what, t_s, spec, so in ROAD_RECORDS:
        t = kst(t_s)
        cells, note = road_cells(regs, spec)
        row = {"id": rid, "kind": "road closure", "what": what, "recorded_kst": t_s, "flag": "REPORTED",
               "source": so, "location": note, "n_cells": sum(len(v) for v in cells.values())}
        if not cells:
            row["status"] = "NOT COMPARED: " + note
            road_out.append(row); continue
        T, lead_ok = issue_for(t, 1)
        row["issue_kst"] = fmt(T); row["lead_ge_1h"] = lead_ok
        for arm in ARMS:
            mc, at_issue = model_closure(runs, cells, arm, T)
            if mc is None:
                row[arm] = {"model_kst": "", "error_min": None, "status": f"MISS: not closed by {fmt(T + timedelta(hours=8))}"}
            elif at_issue:
                row[arm] = {"model_kst": fmt(mc), "error_min": None, "error_bound_min": round((T - t).total_seconds() / 60),
                            "status": "closed at issue (error <= bound)"}
            else:
                row[arm] = {"model_kst": fmt(mc), "error_min": round((mc - t).total_seconds() / 60), "status": "compared"}
        rc = min((recon[r][c] for r, cs in cells.items() for c in cs), default=np.inf)
        row["reconstruction_kst"] = fmt(datetime.fromtimestamp(rc, UTC)) if np.isfinite(rc) else "not reached by data end"
        row["reconstruction_error_min"] = round((rc - t.timestamp()) / 60) if np.isfinite(rc) else None
        ta = [a for r, cs in cells.items() for c in cs if (a := toa_at(r, c))]
        row["toa_kst"] = fmt(min(ta)) if ta else "outside TOA footprint"
        row["toa_error_min"] = round((min(ta) - t).total_seconds() / 60) if ta else None
        road_out.append(row)

    # ---- 5.2 evacuation orders per town
    R_rows = json.loads(Path(r_rows).read_text())["rows"]
    vt = json.loads((RAW / "village_towns.json").read_text())["towns"]
    place_town = {}
    for r, R in regs.items():
        for pid, p in R.places.items():
            lon, lat = TO_LL.transform(*R.xy[p["entry"]["node"]])
            town = next((n for n, g in LOCS if g.contains(Point(lon, lat))), None)
            sg = (p.get("sigungu") or {}).get("ko", "")
            if town is None and p.get("name"):
                town = next((k.split(" ")[1] for k, v in vt.items() if k.startswith(sg) and p["name"] in v), None)
            place_town[pid] = (sg, town, p.get("name") or "")
    idx = defaultdict(dict)
    for x in R_rows:
        idx[(x["arm"], x["horizon"], x["issue_utc"])][x["place_id"]] = x
    evac_out = []
    for eid, county, scope, t_s, so in EVAC_RECORDS:
        t = kst(t_s)
        if scope[0] == "county":
            pids = [p for p, (sg, tw, nm) in place_town.items() if sg == county]
        elif scope[0] == "towns":
            pids = [p for p, (sg, tw, nm) in place_town.items() if sg == county and tw in scope[1]]
        else:
            pids = [p for p, (sg, tw, nm) in place_town.items() if sg == county and nm in scope[1]]
        T, _ = issue_for(t, 0)
        row = {"id": eid, "kind": "evacuation order", "what": f"{county} {scope[1] if len(scope) > 1 else '(whole county)'}",
               "recorded_kst": t_s, "flag": "REPORTED" if so is not NEWSRO else "REPORTED (county log via one outlet)",
               "source": so, "n_places": len(pids), "issue_kst": fmt(T)}
        for arm in (PRIMARY, "RUNNING"):
            xs = [idx[(arm, "8h", T.isoformat())][p] for p in pids if p in idx[(arm, "8h", T.isoformat())]]
            st = Counter(x["step_from_T_village"] for x in xs)
            sts = Counter(x["state"] for x in xs)
            trs = [T + timedelta(seconds=x["T_road_s"]) for x in xs if x["state"] == "CUT"]
            tvs = [T + timedelta(seconds=x["T_village_s"]) for x in xs if x["state"] != "INSIDE" and x["T_village_s"] is not None]
            med_r = datetime.fromtimestamp(statistics.median([d.timestamp() for d in trs]), UTC) if trs else None
            med_v = datetime.fromtimestamp(statistics.median([d.timestamp() for d in tvs]), UTC) if tvs else None
            row[arm] = {"steps": dict(st), "states": dict(sts), "n_cut": len(trs), "median_T_road_kst": fmt(med_r),
                        "n_T_village_within_H": len(tvs), "median_T_village_kst": fmt(med_v),
                        "order_minus_median_T_road_min": round((t - med_r).total_seconds() / 60) if med_r else None}
        evac_out.append(row)

    # ---- 5.3 burned area
    B = json.loads(Path(burned).read_text())
    M_rows = json.loads(Path(m_rows).read_text())["rows"]
    origin_cell = {x["place_id"]: (x["region"], x["origin_cell"]) for x in R_rows}
    burn_out = {"map": {r: {k: v for k, v in B["regions"][r].items() if k in ("pre", "post", "burned_area_km2", "cells", "valid_pixels", "pixels_in_grid")} for r in REGIONS}}

    def cls_of(region, c, th):
        return B["regions"][region]["cell_class"][th][c]

    def table2(pairs):
        c = Counter()
        for pred, obs in pairs:
            if obs == "N":
                c["not_assessable"] += 1
            else:
                c[{(True, "B"): "hit", (False, "B"): "miss", (True, "U"): "false_alarm", (False, "U"): "correct_negative"}[(pred, obs)]] += 1
        return dict(c)

    places_tab = {}
    for th in ("0.1", "0.27"):
        for arm in ARMS:
            reached = defaultdict(bool)
            for x in R_rows:
                if x["arm"] == arm and x["horizon"] == "8h":
                    reached[x["place_id"]] |= (x["state"] == "INSIDE" or x["T_village_s"] is not None)
            places_tab[f"R/{arm}/8h/dNBR>={th}"] = table2([(reached[p], cls_of(*origin_cell[p], th)) for p in origin_cell])
        for var in ("kriged_mean", "firms_early", "envelope"):
            reached = defaultdict(bool)
            for x in M_rows:
                if x["arm"] == var and x["horizon"] == "8h":
                    reached[x["place_id"]] |= (x["state"] == "INSIDE" or x["T_village_state"] == "within_H")
            places_tab[f"M/{var}/8h/dNBR>={th}"] = table2([(reached[p], cls_of(*origin_cell[p], th)) for p in origin_cell])
    cells_tab = {}
    T_last = ISSUES[-1]
    for th in ("0.1", "0.27"):
        for arm in ARMS:
            pairs = []
            for r in REGIONS:
                cs = run_file(runs, r, arm, T_last)["close_s"]
                n = regs[r].W * regs[r].H
                pairs += [(str(c) in cs, cls_of(r, c, th)) for c in range(n)]
            cells_tab[f"R/{arm}/8h@24:00KST/dNBR>={th}"] = table2(pairs)
        pairs = []
        for r in REGIONS:
            pairs += [(np.isfinite(recon[r][c]), cls_of(r, c, th)) for c in range(regs[r].W * regs[r].H)]
        cells_tab[f"reconstruction (all detections to 26 Mar 02:58 KST)/dNBR>={th}"] = table2(pairs)
    burn_out["places"] = places_tab
    burn_out["cells"] = cells_tab

    # ---- village accounts
    va_out = []
    for vid, name, t_s, what, so in VILLAGE_ACCOUNTS:
        t = kst(t_s)
        T, ok = issue_for(t, 1)
        pid = [p for p in regs["yeongdeok_2025"].places if place_town[p][2] == name]
        row = {"id": vid, "kind": "village fire arrival (account)", "what": f"{name}: {what}", "recorded_kst": t_s,
               "flag": "REPORTED, single source", "source": so, "issue_kst": fmt(T), "n_places": len(pid)}
        for arm in ARMS:
            xs = [idx[(arm, "8h", T.isoformat())].get(p) for p in pid]
            xs = [x for x in xs if x]
            if not xs:
                row[arm] = {"status": "place not found"}; continue
            x = xs[0]
            if x["state"] == "INSIDE":
                row[arm] = {"status": "inside known fire area at issue", "model_kst": f"<= {fmt(T)}"}
            elif x["T_village_s"] is None:
                row[arm] = {"status": f"MISS: not reached by {fmt(T + timedelta(hours=8))}"}
            else:
                tv = T + timedelta(seconds=x["T_village_s"])
                row[arm] = {"model_kst": fmt(tv), "error_min": round((tv - t).total_seconds() / 60), "status": "compared"}
        va_out.append(row)

    # ---- summary of road errors (n >= 3)
    summ = {}
    for arm in ARMS:
        e = [r[arm]["error_min"] for r in road_out if arm in r and r[arm].get("error_min") is not None]
        miss = sum(1 for r in road_out if arm in r and r[arm]["status"].startswith("MISS"))
        at = sum(1 for r in road_out if arm in r and r[arm]["status"].startswith("closed at issue"))
        summ[arm] = {"n_compared": len(e), "n_miss": miss, "n_closed_at_issue": at,
                     "n_not_compared": sum(1 for r in road_out if "status" in r),
                     "median_abs_error_min": statistics.median(map(abs, e)) if len(e) >= 3 else None,
                     "median_error_min": statistics.median(e) if len(e) >= 3 else None,
                     "within_30": sum(abs(x) <= 30 for x in e) if len(e) >= 3 else None,
                     "within_60": sum(abs(x) <= 60 for x in e) if len(e) >= 3 else None}
    res = {"label": LABEL, "roads": road_out, "roads_excluded": ROAD_EXCLUDED, "road_error_summary": summ,
           "evacuation": evac_out, "evacuation_excluded": EVAC_EXCLUDED, "burned_area": burn_out,
           "village_accounts": va_out,
           "place_town": {p: list(v) for p, v in place_town.items()}}
    (out / "validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))

    # ---- the one validation table (CSV)
    with open(out / "validation_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([f"# {LABEL} Records are REPORTED (news; search snippets unless stated). Error = model - recorded, minutes."])
        w.writerow(["id", "kind", "what", "recorded_kst", "flag", "source_outlet", "source_url", "source_access",
                    "retrieved", "issue_used_kst", "location / n places"]
                   + [f"{a}_model_kst" for a in ARMS] + [f"{a}_error_min_or_status" for a in ARMS]
                   + ["reconstruction_kst", "reconstruction_error_min", "choi_toa_kst", "choi_toa_error_min"])
        for r in road_out + va_out:
            so = r["source"] if isinstance(r["source"], dict) else {"outlet": r["source"]}
            arms = [r.get(a, {}) for a in ARMS]
            w.writerow([r["id"], r["kind"], r["what"], r["recorded_kst"], r["flag"], so.get("outlet"), so.get("url"),
                        so.get("access", "snippet/as in SOURCES.md"), so.get("retrieved", "2026-11-16 (SOURCES.md)"),
                        r.get("issue_kst", ""), r.get("location", r.get("n_places", "")) if "status" not in r else r["status"]]
                       + [a.get("model_kst", "") for a in arms]
                       + [a.get("error_min") if a.get("error_min") is not None else a.get("status", "") for a in arms]
                       + [r.get("reconstruction_kst", ""), r.get("reconstruction_error_min", ""), r.get("toa_kst", ""),
                          r.get("toa_error_min", "")])
        for r in evac_out:
            so = r["source"]
            arms = [r.get(a, {}) for a in ARMS]
            w.writerow([r["id"], r["kind"], r["what"], r["recorded_kst"], r["flag"], so.get("outlet"), so.get("url"),
                        so.get("access"), so.get("retrieved"), r["issue_kst"], r["n_places"]]
                       + [a.get("median_T_road_kst", "") for a in arms]
                       + [(f"order - median T_road = {a['order_minus_median_T_road_min']} min (n cut {a['n_cut']}); steps {a['steps']}"
                           if a else "") for a in arms]
                       + ["", "", "", ""])
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:7])
