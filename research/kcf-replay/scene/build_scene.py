"""Build planner/public/kcf-scene/data/scene.js = window.KCF.scene (schema "kcf-scene/1", scene/DESIGN.md).

Every number written comes from a file in the repository (or from the SHA-pinned routing graph / the run files that
committed code re-makes); every file read is listed in built.inputs with its byte size and SHA-256.

Re-runnable: a stand-in's witness routes are included only when all 26 run files (2 regions x 13 issue hours, 8 h)
exist and parse; run it again when out/runs/ gains WORST / ORDINARY. Before using a stand-in's runs it ASSERTS that
the runs reproduce per_place.csv exactly (state, step, latest safe departure, last departure, shelter, arrival,
distance, pieces, OSM ways) and that its own closure seconds equal the runs' close_s.

Usage (from the repository root): python3 research/kcf-replay/scene/build_scene.py [--runs research/kcf-replay/out/runs]
"""
from __future__ import annotations

import argparse, csv, hashlib, io, json, math, re, subprocess, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

HERE = Path(__file__).resolve().parent            # research/kcf-replay/scene
KCF = HERE.parent                                 # research/kcf-replay
ROOT = KCF.parents[1]                             # repository root
sys.path.insert(0, str(KCF))
import replay   # noqa: E402  (frozen rule: STANDINS, closure_s, Region.cell_distance, ISSUES, HORIZONS, DWELL)
import analyze  # noqa: E402  (kst() formatting used by per_place.csv)

SCHEMA = "kcf-scene/1"
OUT = ROOT / "planner/public/kcf-scene/data/scene.js"
REGIONS = ["yeongdeok_2025", "uiseong_andong_2025"]
HZ = "8h"
H = replay.HORIZONS[HZ]
T0 = datetime(2025, 3, 25, 3, 0, tzinfo=timezone.utc)
TR = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
NAMED = ["화매리", "지품리", "옥류리", "매정리", "노물리", "강구리"]   # RESULTS.md section 4, in table order

# RESULTS.md section 4 "documented" column -> SOURCES.md rows. Keys: ("county", KST) = a row of the 뉴스로 county action
# log table; ("village", Place cell, KST) = a row of the "Village-level times" table. Checked below in both directions
# against the RESULTS.md cell: every HH:MM in the cell is covered by a row here, every row's HH:MM and outlet occur in it.
REPORTED_MAP = {
    # "~18:00 이장 voice message; ~18:00 flames at the village edge (매일신문)": one 매일신문 row carries both.
    "화매리": [("village", "화매리 (영양군 석보면)", "~18:00")],
    # "18:00 지품면 order and CBS; 18:25 황장재 restriction CBS; 18:58 Route 34 (구미~황장) closed;
    #  19:04 도계→영양 road closed; 20:25 power cut (뉴스로). No documented fire-arrival time": five 뉴스로 rows.
    "지품리": [("county", "18:00"), ("county", "18:25"), ("county", "18:58"), ("county", "19:04"), ("county", "20:25")],
    # "18:00 지품면 order; 18:52 옥류리 CBS (뉴스로). No documented fire-arrival time": two 뉴스로 rows.
    "옥류리": [("county", "18:00"), ("county", "18:52")],
    # "19:30 order for all 9 읍·면; 21:00 county CBS (뉴스로); ~20:40 fire in the village, one resident's account
    #  (한국일보)": two 뉴스로 rows + the 한국일보 ~20:40 row (the other 매정리 rows are not cited there).
    "매정리": [("county", "19:30"), ("county", "21:00"), ("village", "매정리", "~20:40")],
    # "19:30, 21:00 (뉴스로); residents aware ~24:00 (대구신문)": two 뉴스로 rows + the 대구신문 row.
    "노물리": [("county", "19:30"), ("county", "21:00"), ("village", "노물리", "~24:00")],
    # "21:58 Route 7 controlled at 송라 지경삼거리 (뉴스로); 00:07 text, fire ~00:37, 00:41 second text (경향신문,
    #  면-level)": one 뉴스로 row + the three 경향신문 강구면·남정면 rows.
    "강구리": [("county", "21:58"), ("village", "강구면·남정면", "00:07 (26 Mar)"),
              ("village", "강구면·남정면", "~00:37 (26 Mar)"), ("village", "강구면·남정면", "00:41 (26 Mar)")],
}


class Inputs:
    """Every file read, with its repository-relative path, byte size, SHA-256 and whether git tracks it."""

    def __init__(self):
        self.files = {}
        out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, cwd=ROOT, check=True).stdout
        self.tracked = set(out.decode().split("\0"))

    def read(self, path: Path) -> bytes:
        b = Path(path).read_bytes()
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
        self.files[rel] = {"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                           "committed": rel in self.tracked}
        return b

    def text(self, path):
        return self.read(path).decode("utf-8")

    def json(self, path):
        return json.loads(self.read(path))


def rel(p: Path) -> str:
    return Path(p).resolve().relative_to(ROOT).as_posix()


def ll(x, y):
    lon, lat = TR.transform(x, y)
    return [round(lon, 6), round(lat, 6)]


def issue_label(k):
    """'12:00' ... '24:00' (DESIGN.md), checked against analyze.kst of the same issue time."""
    lab = f"{12 + k:02d}:00"
    s = analyze.kst(replay.ISSUES[k])
    assert s[6:] == (lab if lab != "24:00" else "00:00"), (k, s, lab)
    return lab


def md_cells(line):
    assert line.startswith("|") and line.rstrip().endswith("|"), line
    return [c.strip() for c in line.strip()[1:-1].split("|")]


def unbold(s):
    return s.replace("**", "")


def md_tables(lines, heading):
    """(1-based line number, cells) for every data row of the first table after the heading line."""
    i = next(i for i, l in enumerate(lines) if l.strip() == heading)
    rows, started = [], False
    for j in range(i + 1, len(lines)):
        l = lines[j]
        if l.startswith("|"):
            if not started:
                started = True
                head = md_cells(l)
                assert set(md_cells(lines[j + 1])[0]) <= set("-: "), lines[j + 1]
                continue
            if set(md_cells(l)[0]) <= set("-: ") and md_cells(l)[0]:
                continue
            rows.append((j + 1, md_cells(l)))
        elif started:
            break
    return head, rows


def section(lines, prefix):
    i = next(i for i, l in enumerate(lines) if l.startswith(prefix))
    j = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
    return i, j


def normalize(o):
    """Integral floats -> int (JS does not distinguish; keeps the file small). Everything else unchanged."""
    if isinstance(o, float):
        assert math.isfinite(o)
        return int(o) if o.is_integer() else o
    if isinstance(o, dict):
        return {k: normalize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [normalize(v) for v in o]
    return o


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", default=str(KCF / "out/runs"))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    runs_dir = Path(a.runs).resolve()
    inp = Inputs()
    report = {}

    # ---------------------------------------------------------------- time
    issues = replay.ISSUES
    assert len(issues) == 13 and issues[0] == T0 and all((issues[k] - T0).total_seconds() == 3600 * k for k in range(13))
    issue_kst_csv = [analyze.kst(T) for T in issues]                       # "03-25 12:00" .. "03-26 00:00"
    issue_kst = [issue_label(k) for k in range(13)]
    issue_utc = [T.strftime("%Y-%m-%dT%H:%M:%SZ") for T in issues]

    # ---------------------------------------------------------------- per_place.csv (8 h rows)
    pp_path = KCF / "per_place.csv"
    pp_rows = list(csv.DictReader(io.StringIO(inp.text(pp_path), newline="")))
    assert len(pp_rows) == 13572, len(pp_rows)
    csv_by = {}
    for n, r in enumerate(pp_rows, 1):
        if r["horizon"] != HZ:
            continue
        key = (r["standin"], r["place_id"], r["issue_kst"])
        assert key not in csv_by, key
        csv_by[key] = (n, r)
    assert {k[2] for k in csv_by} == set(issue_kst_csv), sorted({k[2] for k in csv_by})
    standin_names = sorted({k[0] for k in csv_by})
    assert set(standin_names) == set(replay.STANDINS), standin_names
    place_region = {}
    for (_, pid, _), (_, r) in csv_by.items():
        assert place_region.setdefault(pid, r["region"]) == r["region"], pid
    assert len(place_region) == 174, len(place_region)
    hourly = {}
    for st in standin_names:
        hourly[st] = {}
        for pid in sorted(place_region):
            lst = []
            for k in range(13):
                n, r = csv_by[(st, pid, issue_kst_csv[k])]
                lst.append({"step": r["government_step"], "state": r["departure_state"],
                            "lsd": r["latest_safe_departure_kst"], "last": r["last_departure_in_horizon_kst"],
                            "shelter": r["shelter_id"], "arr": r["arrival_kst"], "d_km": r["dist_known_fire_km"],
                            "cut_before": r["route_cut_before_departure"],
                            "first_cut": r["route_first_cut_by_reconstruction_kst"],
                            "pieces": r["departure_set_pieces"], "row": n})
            hourly[st][pid] = lst
    assert sum(len(v) for st in hourly for v in hourly[st].values()) == len(csv_by) == 3 * 174 * 13

    # ---------------------------------------------------------------- regions, places, shelters
    idx = inp.json(ROOT / "planner/public/data/regions/index.json")
    idx = {e["region_id"]: e for e in idx}
    feats = {}
    for region in REGIONS:
        gj = inp.json(ROOT / f"planner/public/data/regions/{region}/places.geojson")
        assert gj["region_id"] == region
        for f in gj["features"]:
            assert f["properties"]["id"] not in feats, f["properties"]["id"]
            feats[f["properties"]["id"]] = (region, f)
    named_ids = []
    for nm in NAMED:
        ids = sorted({pid for (_, pid, _), (_, r) in csv_by.items() if r["name"] == nm})
        assert len(ids) == 1 and place_region[ids[0]] == "yeongdeok_2025", (nm, ids)
        named_ids.append(ids[0])
    places = []
    for pid in sorted(place_region):
        region, f = feats[pid]
        p = f["properties"]
        assert region == place_region[pid] and p["role"] == "origin" and p["checkable"], pid
        places.append({"id": pid, "region": region, "name": p.get("name"), "category": p["category"],
                       "vulnerable": bool(p.get("vulnerable")), "sigungu": (p.get("sigungu") or {}).get("ko", ""),
                       "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                       "entry": [p["entry"]["lon"], p["entry"]["lat"]], "named": pid in named_ids})
    named = [{"id": pid, "name": nm, "order": i + 1} for i, (nm, pid) in enumerate(zip(NAMED, named_ids))]

    # ---------------------------------------------------------------- graphs
    graphs = {}
    for region in REGIONS:
        raw = inp.json(ROOT / f"data/routing/graphs/{region}/graph.json")
        graphs[region] = {"raw": raw, "g": raw["grid"], "edges": {e["id"]: e for e in raw["edges"]},
                          "nodes": {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}}

    def shelter_cell(region, shelter_id):
        """analyze.py main(): the shelter's entry node -> cell, float floor division as written there."""
        G = graphs[region]; g = G["g"]
        sxy = G["nodes"][feats[shelter_id][1]["properties"]["entry"]["node"]]
        return int((sxy[1] - g["y0"]) // g["resolution"]) * g["width"] + int((sxy[0] - g["x0"]) // g["resolution"])

    # ---------------------------------------------------------------- runs (gitignored; re-made by replay.py)
    runs, runs_state = {}, {}
    for st in replay.STANDINS:
        files = [runs_dir / f"{region}__{st}__{HZ}__{T.strftime('%H')}.json" for region in REGIONS for T in issues]
        ok = all(p.is_file() for p in files)
        docs = {}
        if ok:
            for p in files:
                try:
                    docs[p] = json.loads(p.read_bytes())
                except (ValueError, OSError):
                    ok = False
                    break
        runs_state[st] = "complete" if ok else "absent"
        if ok:
            runs[st] = {}
            for p in files:
                job = inp.json(p)    # re-read through the recorder (same bytes)
                region, k = job["region"], issues.index(datetime.fromisoformat(job["issue_utc"]))
                assert (job["standin"], job["horizon"]) == (st, HZ) and p.name.startswith(region)
                runs[st][(region, k)] = job

    # ---------------------------------------------------------------- exact reproduction of per_place.csv by the runs
    repro = Counter()
    for st, jobs in runs.items():
        for (region, k), job in sorted(jobs.items()):
            T = issues[k]
            G = graphs[region]
            assert {r["place_id"] for r in job["rows"]} == {p for p, rg in place_region.items() if rg == region}
            for r in job["rows"]:
                n, c = csv_by[(st, r["place_id"], issue_kst_csv[k])]
                assert c["region"] == region
                ld = r.get("ld_s")
                inside = r["dist_known_fire_m"] == 0.0
                if ld is None:
                    state = "INSIDE_KNOWN_FIRE_AREA" if inside else "NO_SAFE_DEPARTURE"
                elif r["cut_within_H"]:
                    state = "LATEST_SAFE_DEPARTURE"
                else:
                    state = "NOT_CUT_WITHIN_H"
                want = {
                    "departure_state": state,
                    "government_step": r["step"],
                    "latest_safe_departure_kst": analyze.kst(T + timedelta(seconds=ld)) if state == "LATEST_SAFE_DEPARTURE" else "",
                    "last_departure_in_horizon_kst": analyze.kst(T + timedelta(seconds=ld)) if ld is not None else "",
                    "shelter_id": r.get("shelter_id") or "",
                    "arrival_kst": analyze.kst(T + timedelta(seconds=r["arrival_s"])) if r.get("arrival_s") is not None else "",
                    "dist_known_fire_km": "" if r["dist_known_fire_m"] is None else str(round(r["dist_known_fire_m"] / 1000, 2)),
                    "departure_set_pieces": str(r.get("pieces") or ""),
                    "route_osm_ways": " ".join(dict.fromkeys(str(G["edges"][e]["source_way"]) for e in r.get("route_edges", []))),
                }
                for f, v in want.items():
                    assert c[f] == v, (st, region, k, r["place_id"], f, c[f], v, n)
                    repro[f"{st}:{f}"] += 1
                repro[f"{st}:rows"] += 1
    report["reproduction"] = dict(sorted(repro.items()))

    # ---------------------------------------------------------------- witness routes and route edges
    edge_ids = {region: set() for region in REGIONS}
    for st, jobs in runs.items():
        for (region, k), job in jobs.items():
            for r in job["rows"]:
                if r.get("ld_s") is not None:
                    assert r["route_edges"], (st, region, k, r["place_id"])
                    edge_ids[region].update(r["route_edges"])
    route_edges, eidx = {}, {}
    for region in REGIONS:
        G = graphs[region]
        lst = []
        for eid in sorted(edge_ids[region]):
            e = G["edges"][eid]
            lst.append({"id": eid, "D": e["travel_ticks"], "seg": [[s["cell"], s["end"]] for s in e["segments"]],
                        "c": [ll(*G["nodes"][e["u"]]), ll(*G["nodes"][e["v"]])]})
        route_edges[region] = lst
        eidx[region] = {e["id"]: i for i, e in enumerate(lst)}
    routes = {}
    recheck = Counter()
    sh_cells = {region: set() for region in REGIONS}
    for st, jobs in runs.items():
        routes[st] = {pid: [None] * 13 for pid in sorted(place_region)}
        for (region, k), job in sorted(jobs.items()):
            G = graphs[region]
            for r in job["rows"]:
                if r.get("ld_s") is None:
                    continue
                sc = shelter_cell(region, r["shelter_id"])
                sh_cells[region].add(sc)
                ok, arr = analyze.recheck(r["route_edges"], G["edges"], job["close_s"], r["ld_s"], r["arrival_s"], sc, H)
                recheck["ok" if ok and arr == r["arrival_s"] else "FAIL"] += 1
                routes[st][r["place_id"]][k] = {"ld": r["ld_s"], "arr": r["arrival_s"], "sh": r["shelter_id"],
                                                "e": [eidx[region][e] for e in r["route_edges"]], "sh_cell": sc}
    assert recheck.get("FAIL", 0) == 0, recheck
    report["builder_witness_recheck"] = dict(recheck)

    # ---------------------------------------------------------------- road cells
    road_cells = {}
    cell_pos = {}
    for region in REGIONS:
        G = graphs[region]; g = G["g"]
        cells = {s["cell"] for e in G["raw"]["edges"] for s in e["segments"]}
        cells |= {c for e in route_edges[region] for c, _ in e["seg"]} | sh_cells[region]
        cells = sorted(cells)
        assert all(0 <= c < g["width"] * g["height"] for c in cells)
        rings = []
        for c in cells:
            row, col = divmod(c, g["width"])
            x0, y0, res = g["x0"] + col * g["resolution"], g["y0"] + row * g["resolution"], g["resolution"]
            corners = [(x0, y0), (x0 + res, y0), (x0 + res, y0 + res), (x0, y0 + res), (x0, y0)]
            rings.append([ll(x, y) for x, y in corners])
        road_cells[region] = {"cells": cells, "ring": rings}
        cell_pos[region] = {c: i for i, c in enumerate(cells)}

    # ---------------------------------------------------------------- closures (replay.py's own code)
    discs_path = KCF / "fire_discs.json"
    discs_doc = inp.json(discs_path)
    replay.init(REGIONS, str(discs_path))       # builds replay.REG (Region per region) and replay.DISCS exactly as run_one sees them
    close = {st: {region: [] for region in REGIONS} for st in replay.STANDINS}
    close_cmp = Counter()
    for region in REGIONS:
        R = replay.REG[region]
        assert (R.grid.W, R.grid.H) == (graphs[region]["g"]["width"], graphs[region]["g"]["height"])
        for k, T in enumerate(issues):
            dist = R.cell_distance(replay.DISCS, datetime.fromisoformat(T.isoformat()))
            for st in replay.STANDINS:
                full = {}
                for c in range(len(dist)):
                    if np.isfinite(dist[c]):
                        s = replay.closure_s(st, float(dist[c]))
                        if s <= H:
                            full[c] = int(math.ceil(s))
                close[st][region].append([full.get(c, -1) for c in road_cells[region]["cells"]])
                if st in runs:
                    job = runs[st][(region, k)]
                    got = {int(c): v for c, v in job["close_s"].items()}
                    for c in road_cells[region]["cells"]:
                        assert full.get(c, -1) == got.get(c, -1), (st, region, k, c, full.get(c), got.get(c))
                        close_cmp[f"{st}:road_cells"] += 1
                    assert full == got, (st, region, k, "full-grid close_s differs")
                    close_cmp[f"{st}:grid_cells"] += len(dist)
    report["close_compared"] = dict(close_cmp)

    # ---------------------------------------------------------------- discs and counts
    rows = []
    for d in discs_doc["discs"]:
        t = datetime.fromisoformat(d["t_utc"])
        sec = (t - T0).total_seconds()
        assert sec == int(sec) and t.microsecond == 0, d["t_utc"]
        rows.append([int(sec), *ll(d["x"], d["y"]), d["r_m"], d["src"]])
    rows.sort(key=lambda r: (r[0], r[4], r[1], r[2]))
    disc_counts = []
    for T in issues:
        before = [d for d in discs_doc["discs"] if datetime.fromisoformat(d["t_utc"]) < T]
        c = {"total": len(before), "AHI": sum(d["src"] == "AHI" for d in before),
             "FIRMS": sum(d["src"].startswith("FIRMS-") for d in before)}
        assert c["AHI"] + c["FIRMS"] == c["total"]
        disc_counts.append(c)

    # ---------------------------------------------------------------- planner cache (RUNNING, 8 h)
    cache_dir = KCF / "planner_cache/RUNNING_8h"
    planner = {pid: [None] * 13 for pid in sorted(place_region)}
    shelter_ids = {r["shelter_id"] for r in pp_rows if r["shelter_id"]}
    geo = Counter()
    for region in REGIONS:
        for k, T in enumerate(issues):
            compact = T.strftime("%Y%m%dT%H%M%SZ")
            p = cache_dir / region / f"RUNNING_8h_{compact}.json"
            doc = inp.json(p)
            assert doc["region_id"] == region and doc["input_time"] == issue_utc[k]
            step = doc["generator"]["step_min"] * 60
            for job in doc["plans"]:
                req = job["request"]
                offs = req["depart_offsets_s"]
                assert offs == list(range(0, H - replay.DWELL, step)), offs
                (plan,) = job["result"]["plans"]
                pid = plan["origin_id"]
                assert place_region[pid] == region and planner[pid][k] is None
                verdict = {}
                for at in plan["attempts"]:
                    key = (at["destination_id"], at["depart_offset_s"])
                    assert key not in verdict
                    verdict[key] = "1" if at["verdict"] == "checked_route" else "0"
                dests = [d["id"] for d in req["destinations"]]
                assert len(verdict) == len(dests) * len(offs)
                shelter_ids.update(dests)
                b = plan["best"]
                planner[pid][k] = {"file": rel(p), "offsets_step_s": step,
                                   "shelters": [[d, "".join(verdict[(d, o)] for o in offs)] for d in dests],
                                   "contiguous_s": plan["latest_contiguous_checked_depart_offset_s"],
                                   "best": None if b is None else {"shelter": b["destination_id"], "off_s": b["depart_offset_s"],
                                                                   "arr_s": b["arrival_s"]}}
                if "RUNNING" in routes:
                    w = routes["RUNNING"][pid][k]
                    if b is None:
                        geo["no_cache_best_with_witness" if w else "no_cache_best_no_witness"] += 1
                        continue
                    if w is None:
                        geo["mismatch"] += 1
                        continue
                    coords = doc["route_checks"][b["route_check_job_id"]]["result"]["route"]["geometry"]["coordinates"]
                    E = route_edges[region]
                    chain = [E[w["e"][0]]["c"][0]] + [E[i]["c"][1] for i in w["e"]]
                    for i, j in zip(w["e"], w["e"][1:]):
                        assert E[i]["c"][1] == E[j]["c"][0]
                    same = coords == chain and b["destination_id"] == w["sh"]
                    geo["match" if same else "mismatch"] += 1
    assert all(v is not None for lst in planner.values() for v in lst)
    if "RUNNING" in routes:
        assert geo["mismatch"] == 0, geo
    report["planner_geometry"] = dict(geo)

    shelters = {}
    for sid in sorted(shelter_ids):
        region, f = feats[sid]
        p = f["properties"]
        assert p["role"] == "destination", sid
        shelters[sid] = {"name": p.get("name"), "region": region, "category": p["category"],
                         "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                         "entry": [p["entry"]["lon"], p["entry"]["lat"]]}

    # ---------------------------------------------------------------- documented ("reported") times
    sources_path = KCF / "SOURCES.md"
    src_lines = inp.text(sources_path).split("\n")
    results_path = KCF / "RESULTS.md"
    res_lines = inp.text(results_path).split("\n")
    # county log (뉴스로)
    head, county = md_tables(src_lines, "## Official alerts, orders and road closures, 영덕군, 25 March 2025")
    assert head[:2] == ["KST", "Entry (quoted)"], head
    srcline_no = next(i for i, l in enumerate(src_lines, 1) if l.startswith("Source: 뉴스로"))
    m = re.match(r'^Source: (.+?), (https?://\S+), block "(.+)"$', src_lines[srcline_no - 1])
    assert m, src_lines[srcline_no - 1]
    county_source, county_url = m.group(1), m.group(2)
    assert "every row is **SINGLE**" in src_lines[srcline_no]
    county_log = [{"kst": c[0], "entry": unbold(c[1]), "line": n} for n, c in county]
    county_source_obj = {"line": srcline_no, "text": src_lines[srcline_no - 1], "source": county_source, "url": county_url,
                         "block": m.group(3), "flag": "SINGLE"}
    # village-level table
    vhead, village = md_tables(src_lines, "## Village-level times")
    assert vhead == ["Place", "KST", "What (quoted / paraphrased)", "Source", "Flag"], vhead
    vrows, prev = [], None
    for n, c in village:
        s = c[3]
        if s == "same":
            assert prev is not None
            source, url = prev
        else:
            mm = re.match(r"^(.+?), (https?://\S+)$", s)
            source, url = (mm.group(1), mm.group(2)) if mm else (s, None)
        prev = (source, url)
        vrows.append({"place": c[0], "kst": c[1], "what": unbold(c[2]), "source": source, "url": url,
                      "flag": unbold(c[4]), "line": n})
    # RESULTS.md section 4 "documented" cells
    i4, j4 = section(res_lines, "## 4 ")
    rhead, rrows = md_tables(res_lines[:j4], next(l for l in res_lines[i4:j4] if l.startswith("Latest safe departure shown")))
    assert rhead[0] == "place" and rhead[-1] == "documented", rhead
    documented_cell = {}
    for n, c in rrows:
        documented_cell[c[0].split(" ")[0]] = (n, c[-1])
    assert list(documented_cell) == NAMED, list(documented_cell)
    nt_path = KCF / "named_places_timeline.csv"
    nt = list(csv.DictReader(io.StringIO(inp.text(nt_path), newline="")))
    reported = {}
    for nm, pid in zip(NAMED, named_ids):
        docs = {r["documented"] for r in nt if r["place"] == nm}
        assert len(docs) == 1, (nm, docs)
        cell = documented_cell[nm][1]
        out_rows = []
        for key in REPORTED_MAP[nm]:
            if key[0] == "county":
                (hit,) = [x for x in county_log if x["kst"] == key[1]]
                row = {"place": "영덕군", "kst": hit["kst"], "what": hit["entry"], "source": county_source,
                       "url": county_url, "flag": "SINGLE", "line": hit["line"]}
            else:
                (row,) = [dict(x) for x in vrows if x["place"] == key[1] and x["kst"] == key[2]]
            hhmm = re.search(r"\d\d:\d\d", row["kst"]).group(0)
            assert hhmm in cell, (nm, hhmm, cell)
            assert row["source"].split(" ")[0] in cell, (nm, row["source"], cell)
            assert row["url"], (nm, row)
            out_rows.append(row)
        covered = {re.search(r"\d\d:\d\d", r["kst"]).group(0) for r in out_rows}
        assert set(re.findall(r"\d\d:\d\d", cell)) == covered, (nm, cell, covered)
        reported[pid] = {"documented": docs.pop(), "rows": out_rows}

    # ---------------------------------------------------------------- stand-ins, score, regions
    i2, j2 = section(res_lines, "## 2 ")
    shead, srows = md_tables(res_lines[:j2], res_lines[i2].strip())
    assert shead == ["label", "R(h)", "basis"], shead
    basis = {c[0]: c[2] for _, c in srows}
    standins = {}
    for st, (a_m, v) in replay.STANDINS.items():
        lab = f"{st} · " + (f"{a_m / 1000:g} km + " if a_m else "") + f"{v / 1000:g} km/h"
        standins[st] = {"a_m": a_m, "v_m_per_h": v, "label": lab, "basis": basis[st],
                        "src": "research/kcf-replay/HOTSPOT_RULE.md"}
    score_path = KCF / "score.json"
    score = inp.json(score_path)["score"]
    regions = {}
    for region in REGIONS:
        g = graphs[region]["g"]
        e = idx[region]
        regions[region] = {"name_ko": e["name"]["ko"], "name_en": e["name"]["en"], "bbox": e["bbox"],
                           "grid": {"x0": g["x0"], "y0": g["y0"], "res": g["resolution"], "w": g["width"],
                                    "h": g["height"], "crs": graphs[region]["raw"]["crs"]}}
        assert regions[region]["grid"]["crs"] == "EPSG:5179"

    # ---------------------------------------------------------------- sources the UI may cite
    fr = (ROOT / "tools/fetch_routing_inputs.py")
    frt = inp.text(fr)
    tag = re.search(r"^TAG='([^']+)'", frt, re.M).group(1)
    sha = re.search(r"^SHA='([0-9a-f]{64})'", frt, re.M).group(1)
    url = re.search(r"^URL='([^']+)'\+TAG\+'([^']+)'", frt, re.M)
    for p in [KCF / "HOTSPOT_RULE.md", KCF / "replay.py", KCF / "analyze.py", KCF / "make_planner_cache.py"]:
        inp.read(p)
    src = {
        "per_place": rel(pp_path), "named_timeline": rel(nt_path), "sources_md": rel(sources_path),
        "results_md": rel(results_path), "fire_discs": rel(discs_path), "hotspot_rule": "research/kcf-replay/HOTSPOT_RULE.md",
        "replay_py": "research/kcf-replay/replay.py", "analyze_py": "research/kcf-replay/analyze.py",
        "make_planner_cache": "research/kcf-replay/make_planner_cache.py",
        "planner_cache_dir": rel(cache_dir), "score": rel(score_path),
        "places_geojson": {r: f"planner/public/data/regions/{r}/places.geojson" for r in REGIONS},
        "regions_index": "planner/public/data/regions/index.json",
        "graph": {r: f"data/routing/graphs/{r}/graph.json" for r in REGIONS},
        "graph_release": {"tag": tag, "zip": url.group(2).lstrip("/"), "sha256": sha, "url": url.group(1) + tag + url.group(2),
                          "script": "tools/fetch_routing_inputs.py"},
        "runs_dir": "research/kcf-replay/out/runs",
        "design": "research/kcf-replay/scene/DESIGN.md",
        "scene_js": rel(Path(a.out)) if Path(a.out).resolve().is_relative_to(ROOT) else str(a.out),
        "build_scene": rel(Path(__file__)), "verify_scene": "research/kcf-replay/scene/verify_scene.py",
    }

    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
    scene = {
        "schema": SCHEMA,
        "built": {"script": rel(Path(__file__)), "commit": commit,
                  "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "inputs": [inp.files[k] for k in sorted(inp.files)], "runs": runs_state},
        "t0_utc": T0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues_s": [int((T - T0).total_seconds()) for T in issues], "issue_kst": issue_kst, "issue_utc": issue_utc,
        "horizon": HZ, "horizon_s": H, "dwell_s": replay.DWELL,
        "standins": standins, "default_standin": "RUNNING",
        "regions": regions, "places": places, "named": named, "shelters": shelters,
        "hourly": hourly, "routes": routes, "routeEdges": route_edges, "roadCells": road_cells, "close": close,
        "discs": {"fields": ["s", "lon", "lat", "r_m", "src"], "rows": rows}, "discCounts": disc_counts,
        "planner": planner, "reported": reported, "countyLog": county_log, "countyLogSource": county_source_obj,
        "score": score, "src": src,
    }
    payload = json.dumps(normalize(scene), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    text = f"// generated by research/kcf-replay/scene/build_scene.py (schema {SCHEMA}); do not edit\n" \
           f"(window.KCF=window.KCF||{{}}).scene={payload};\n"
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="ascii")
    parts = {k: len(json.dumps(normalize(v), sort_keys=True, separators=(",", ":"), ensure_ascii=True)) for k, v in scene.items()}
    report.update({"out": str(out), "bytes": len(text.encode()), "sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "runs": runs_state, "inputs": len(inp.files),
                   "counts": {"places": len(places), "shelters": len(shelters), "named": len(named),
                              "routes": {st: sum(x is not None for v in routes[st].values() for x in v) for st in routes},
                              "routeEdges": {r: len(route_edges[r]) for r in REGIONS},
                              "roadCells": {r: len(road_cells[r]["cells"]) for r in REGIONS},
                              "discs": len(rows), "countyLog": len(county_log),
                              "reported_rows": {pid: len(v["rows"]) for pid, v in reported.items()}},
                   "bytes_by_key": dict(sorted(parts.items(), key=lambda kv: -kv[1]))})
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
