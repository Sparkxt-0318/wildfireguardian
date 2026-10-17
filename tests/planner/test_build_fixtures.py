"""Tests for planner/tools/build_fixtures.py outputs (ARCHITECTURE.md §4.1, official contract schemas).

Output-only checks run whenever the generated fixtures exist; checks that compare against the recorded
source data skip cleanly when the release extracts (planner/.assets/) are missing.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
PLANNER = REPO / "planner"
FIXTURES = PLANNER / "mock_api" / "fixtures"
PUBLIC = PLANNER / "public" / "data" / "regions"
CONTRACT = PLANNER / "contract" / "wfg_api_v1.yaml"
ASSETS = Path(os.environ.get("WFG_ASSETS_DIR", PLANNER / ".assets")) / "extracted"
INPUTS = ASSETS / "WFG-evaluated-routing-inputs-20261015"
FINAL = ASSETS / "WildfireGuardian_Latest_Independent_Final_20261015" / "WildfireGuardian_Latest_Independent_Final_20261015"
ABL = ASSETS / "WFG-final-input-routing-ablation-20261016-v1" / "routing_final_input_ablation_20261016_v1"
REGIONS = ["uljin_2022", "miryang_2022", "hongseong_2023", "uiseong_andong_2025", "yeongdeok_2025"]
POLICIES = ["full", "travel_only", "flame_only", "flame_peak", "flame_dose"]
VERDICTS = {"checked_route", "model_no_route", "unresolved"}
REASON_CODES = {"TIMEOUT", "STATE_CAP", "MEMORY_CAP", "CHECK_NOT_FINISHED", "CHECK_FAILED", "WORKER_ERROR",
                "CLEANUP_UNCONFIRMED", "INTERNAL_ERROR", "OTHER"}

if not (FIXTURES / "MANIFEST.json").is_file():
    pytest.skip("generated fixtures missing — run planner/tools/build_fixtures.py", allow_module_level=True)

needs_assets = pytest.mark.skipif(
    not ((INPUTS / "graphs").is_dir() and (FINAL / "INDEPENDENT_ROWS.csv").is_file() and (ABL / "analysis" / "ROWS.csv").is_file()),
    reason="planner/.assets release extracts missing — run planner/scripts/fetch_planner_assets.sh")


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def manifest():
    return load(FIXTURES / "MANIFEST.json")


@pytest.fixture(scope="module")
def regions():
    return load(FIXTURES / "regions.json")


@pytest.fixture(scope="module")
def records():
    out = {}
    for p in sorted((FIXTURES / "records").glob("*/*.json")):
        out[(p.parent.name, p.stem)] = load(p)
    return out


@pytest.fixture(scope="module")
def contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def validator_for(contract, name):
    from jsonschema import Draft202012Validator
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "$ref": f"#/components/schemas/{name}", "components": contract["components"]}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_TO_5179 = None


def to_5179(lon, lat):
    global _TO_5179
    if _TO_5179 is None:
        from pyproj import Transformer
        _TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    return _TO_5179.transform(lon, lat)


_GRAPHS = {}


def graph(region):
    if region not in _GRAPHS:
        g = load(INPUTS / "graphs" / region / "graph.json")
        g["_xy"] = {n["id"]: (n["x"], n["y"]) for n in g["nodes"]}
        g["_edges"] = {e["id"]: e for e in g["edges"]}
        _GRAPHS[region] = g
    return _GRAPHS[region]


# ---------------------------------------------------------------------------------------------
# Manifest, sizes, contract validation
# ---------------------------------------------------------------------------------------------

def test_manifest_files_exist_with_hashes(manifest):
    assert manifest["files"], "manifest lists no files"
    for f in manifest["files"]:
        p = FIXTURES / f["path"]
        assert p.is_file(), f["path"]
        assert p.stat().st_size == f["bytes"], f["path"]
        assert sha256(p) == f["sha256"], f["path"]
    for f in manifest["public_files"]:
        p = PLANNER / f["path"]
        assert p.is_file() and sha256(p) == f["sha256"], f["path"]
    listed = {f["path"] for f in manifest["files"]}
    on_disk = {str(p.relative_to(FIXTURES)) for p in FIXTURES.rglob("*.json") if p.name != "MANIFEST.json"}
    assert on_disk == listed, "fixture files on disk differ from MANIFEST.json"


def test_fixture_size_budget(manifest):
    total = sum(p.stat().st_size for p in FIXTURES.rglob("*") if p.is_file())
    assert total < 20_000_000, f"fixtures total {total} bytes >= 20 MB"
    assert all(p.stat().st_size < 50_000_000 for p in FIXTURES.rglob("*") if p.is_file())


def test_manifest_sources_are_the_pinned_release_assets(manifest):
    got = {(s["release_tag"], s["asset"], s["sha256"]) for s in manifest["sources"]}
    assert got == {
        ("research-final-20261015", "WFG-evaluated-routing-inputs-20261015.zip",
         "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"),
        ("research-final-20261015", "WildfireGuardian_Latest_Independent_Final_20261015.zip",
         "a3cd27b88d065883ce3d0534592d1406e3f9798c1abd98256c730f0cf3d60d3f"),
        ("routing-ablation-final-inputs-20261016", "WFG-final-input-routing-ablation-20261016-v1.zip",
         "661090bd059a862a9874c4e19977c105d1978bf32ee6d6d3cd7f6d40d244c006"),
    }


def test_regions_validate_against_contract(regions, contract):
    v = validator_for(contract, "RegionList")
    errors = sorted(v.iter_errors(regions), key=str)
    assert not errors, [e.message for e in errors[:5]]
    # The validator really resolves the $refs: a broken copy must fail.
    broken = json.loads(json.dumps(regions))
    del broken["regions"][0]["grid"]
    assert list(v.iter_errors(broken))
    broken = json.loads(json.dumps(regions))
    broken["provenance"]["package"] = "something_else"
    assert list(v.iter_errors(broken))


def test_regions_content(regions):
    assert [r["id"] for r in regions["regions"]] == REGIONS
    allowed_extra = {"fire_year"}
    region_keys = {"id", "name_ko", "name_en", "event_id", "bbox", "graph_id", "graph_sha256", "node_count",
                   "edge_count", "allowed_node_count", "crs", "grid", "input_times", "scenario_sets"}
    expected = {"uljin_2022": ("울진", "Uljin", "KFS_02", 2022), "miryang_2022": ("밀양", "Miryang", "KFS_11", 2022),
                "hongseong_2023": ("홍성", "Hongseong", "KFS_05", 2023),
                "uiseong_andong_2025": ("의성·안동", "Uiseong–Andong", "KFS_01", 2025),
                "yeongdeok_2025": ("영덕", "Yeongdeok", "KFS_01", 2025)}
    for r in regions["regions"]:
        assert set(r) <= region_keys | allowed_extra, set(r) - region_keys - allowed_extra
        assert (r["name_ko"], r["name_en"], r["event_id"], r["fire_year"]) == expected[r["id"]]
        assert r["crs"] == "EPSG:5179" and r["grid"]["resolution_m"] == 375
        assert len(r["scenario_sets"]) == 3, r["id"]
        assert [s["input_time"] for s in r["scenario_sets"]] == r["input_times"]
        for s in r["scenario_sets"]:
            assert len(s["scenario_ids"]) == 4
            assert s["scenario_ids"] == [f"{s['scenario_set_id']}:{i}" for i in range(4)]
            compact = s["input_time"].replace("-", "").replace(":", "")
            assert s["scenario_set_id"].startswith(f"ffb1:{compact}:")
            assert s["horizon_s"] == 3600
        assert 0 < r["allowed_node_count"] <= r["node_count"]
        w, s_, e, n = r["bbox"]
        assert w < e and s_ < n
    p = regions["provenance"]
    assert p["mock"] is True and p["scenario_ids"] == [] and p["kit"] == "v3"
    assert p["checkpoint"] == "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"


@needs_assets
def test_region_hashes_match_sources(regions):
    for r in regions["regions"]:
        g = INPUTS / "graphs" / r["id"] / "graph.json"
        assert sha256(g) == r["graph_sha256"]
        gj = load(g)
        assert gj["revision"] == r["graph_id"]
        assert len(gj["nodes"]) == r["node_count"] and len(gj["edges"]) == r["edge_count"]
        for s in r["scenario_sets"]:
            compact = s["input_time"].replace("-", "").replace(":", "")
            hz = INPUTS / "latest_inputs_try02" / "packets" / r["id"] / compact / "HAZARD.json"
            assert sha256(hz) == s["hazard_sha256"]
            h = load(hz)
            assert [m["id"] for m in h["members"]] == s["scenario_ids"]
            assert h["valid_until"] - h["valid_from"] == s["horizon_s"]


# ---------------------------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------------------------

def forecast_files():
    return sorted((FIXTURES / "forecast").glob("*/*.json"))


def test_forecast_files_validate_and_cover_grid(regions, contract):
    v = validator_for(contract, "ForecastCollection")
    by_id = {r["id"]: r for r in regions["regions"]}
    files = forecast_files()
    assert len(files) == 15
    for p in files:
        fc = load(p)
        errs = list(v.iter_errors(fc))
        assert not errs, (p.name, errs[0].message)
        r = by_id[p.parent.name]
        W, H = r["grid"]["width"], r["grid"]["height"]
        assert fc["region"] == r["id"]
        compact = fc["input_time"].replace("-", "").replace(":", "")
        assert p.stem == compact and fc["input_time"] in r["input_times"]
        assert set(fc) <= {"type", "region", "input_time", "bbox", "features", "provenance"}
        assert len(fc["features"]) == W * H
        ids = [f["id"] for f in fc["features"]]
        assert len(set(ids)) == len(ids)
        for f in fc["features"]:
            pr = f["properties"]
            assert f["id"] == f"r{pr['row']}c{pr['col']}"
            assert pr["cell"] == pr["row"] * W + pr["col"]
            assert 0 <= pr["row"] < H and 0 <= pr["col"] < W
            ring = f["geometry"]["coordinates"][0]
            assert len(ring) == 5 and ring[0] == ring[-1]
            if not pr["valid"]:
                assert pr["p_new_burn_1h"] == 0
        assert fc["provenance"]["mock"] is True
        assert fc["provenance"]["scenario_set_id"] in {s["scenario_set_id"] for s in r["scenario_sets"]}


def test_manifest_records_verified_orientation(manifest):
    go = manifest["conventions"]["grid_orientation"]
    assert go["verified"] is True
    assert "SOUTH" in go["summary"] and "north-up" in go["summary"]
    for region, c in go["edge_segment_checks"].items():
        assert c["pass"] and c["midpoint_cell_south_up_rows"] == c["segments"], region
        assert c["wgs84_sample_inside_assigned_cell"] == c["wgs84_polygon_sample"] > 0
    assert len(go["packet_export_checks"]) == 15
    assert all(c["pass"] for c in go["packet_export_checks"])


@needs_assets
def test_orientation_segment_midpoints_inside_published_cell_polygons(regions):
    """Independent re-check against the PUBLISHED forecast polygons: graph segment midpoints must fall
    inside the polygon of the cell index the graph assigns (and mostly not inside the row-flipped one)."""
    from shapely.geometry import Point, Polygon
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    rng = np.random.default_rng(7)
    for r in regions["regions"]:
        W, H = r["grid"]["width"], r["grid"]["height"]
        fc = load(sorted((FIXTURES / "forecast" / r["id"]).glob("*.json"))[0])
        poly = {f["properties"]["cell"]: Polygon(f["geometry"]["coordinates"][0]) for f in fc["features"]}
        g = graph(r["id"])
        segs = [(e, s) for e in g["edges"] for s in e["segments"]]
        idx = rng.choice(len(segs), size=min(1500, len(segs)), replace=False)
        inside = flipped = tested = 0
        for i in idx:
            e, s = segs[int(i)]
            (ux, uy), (vx, vy) = g["_xy"][e["u"]], g["_xy"][e["v"]]
            t = 0.5 * (s["start"] + s["end"])
            x, y = ux + t * (vx - ux), uy + t * (vy - uy)
            fx = (x - r["grid"]["x0"]) / 375.0 % 1.0
            fy = (y - r["grid"]["y0"]) / 375.0 % 1.0
            if min(fx, 1 - fx, fy, 1 - fy) < 0.01:      # within ~4 m of a cell edge: skip rounding ties
                continue
            lon, lat = tr.transform(x, y)
            pt = Point(lon, lat)
            tested += 1
            inside += poly[s["cell"]].contains(pt)
            row, col = divmod(s["cell"], W)
            flipped += poly[(H - 1 - row) * W + col].contains(pt)
        assert tested > 100
        assert inside == tested, (r["id"], inside, tested)
        assert flipped < 0.1 * tested, (r["id"], flipped, tested)


@needs_assets
def test_forecast_values_equal_packet_and_export_window(regions):
    for r in regions["regions"]:
        W, H = r["grid"]["width"], r["grid"]["height"]
        for s in r["scenario_sets"]:
            compact = s["input_time"].replace("-", "").replace(":", "")
            fc = load(FIXTURES / "forecast" / r["id"] / f"{compact}.json")
            pdir = INPUTS / "latest_inputs_try02" / "packets" / r["id"] / compact
            pk = np.load(pdir / "constructed_arrays.npz")
            P, V, B = pk["mask__constructed_probability"], pk["mask__probability_valid_native"], pk["current_active"]
            ex = np.load(INPUTS / "latest_inputs_try02" / "exports" / r["event_id"] / f"FORECAST_{compact}.npz")
            A = ex["affine_transform"]
            assert A[4] < 0  # export is north-up
            c0 = int(round((r["grid"]["x0"] - A[2]) / 375))
            r0 = int(round((A[5] - (r["grid"]["y0"] + H * 375)) / 375))
            EP = ex["new_burn_probability"][r0:r0 + H, c0:c0 + W]
            EV = ex["probability_valid"][r0:r0 + H, c0:c0 + W]
            assert (EV == V).all()
            assert np.allclose(np.where(V, P, 0), np.where(EV, EP, 0))
            got_p = np.zeros((H, W))
            got_v = np.zeros((H, W), bool)
            got_b = np.zeros((H, W), bool)
            for f in fc["features"]:
                pr = f["properties"]
                nrow = H - 1 - pr["row"]
                got_p[nrow, pr["col"]] = pr["p_new_burn_1h"]
                got_v[nrow, pr["col"]] = pr["valid"]
                got_b[nrow, pr["col"]] = pr["burning_now"]
            assert np.allclose(got_p, P, rtol=1e-5, atol=1e-12)
            assert (got_v == V).all() and (got_b == B).all()


# ---------------------------------------------------------------------------------------------
# Node tables
# ---------------------------------------------------------------------------------------------

def test_node_tables(regions):
    for r in regions["regions"]:
        t = load(FIXTURES / "nodes" / f"{r['id']}.json")
        n = len(t["ids"])
        assert n == r["node_count"] == len(t["lon"]) == len(t["lat"]) == len(t["allowed"])
        assert set(t["allowed"]) <= {0, 1}
        assert sum(t["allowed"]) == r["allowed_node_count"] == t["allowed_count"]
        assert t["allowed_rule"] == "largest strongly connected component (mock assumption)"
        lon0, lat0, lon1, lat1 = r["bbox"]
        assert min(t["lon"]) >= lon0 - 1e-5 and max(t["lon"]) <= lon1 + 1e-5
        assert min(t["lat"]) >= lat0 - 1e-5 and max(t["lat"]) <= lat1 + 1e-5
        ids = set(t["ids"])
        assert len(ids) == n
        assert len(t["recorded_mission_nodes"]) >= 4
        for e in t["recorded_mission_nodes"]:
            assert e["node_id"] in ids


# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------

def test_record_set_complete(records):
    assert len(records) == 100
    full = {k: v for k, v in records.items() if v["policy"] == "full"}
    assert len(full) == 20
    cases = {(k[0], v["case_id"]) for k, v in full.items()}
    for (region, case_id) in cases:
        for pol in POLICIES:
            assert (region, f"{case_id}__{pol}") in records


def test_full_policy_verdict_split_15_5(records):
    full = [v for v in records.values() if v["policy"] == "full"]
    verdicts = [v["outcome"]["verdict"] for v in full]
    assert verdicts.count("checked_route") == 15
    assert verdicts.count("model_no_route") == 5
    assert all(v["source_arm"] == "RDA_CAND" and v["repetition"] == 1 for v in full)


@needs_assets
def test_full_split_matches_final_review(records):
    fr = load(FINAL / "FINAL_REVIEW.json")["by_arm"]["RDA_CAND"]
    full = [v for v in records.values() if v["policy"] == "full"]
    assert sum(v["outcome"]["verdict"] == "checked_route" for v in full) == fr["both_repetitions_checked_route_missions"]
    assert sum(v["outcome"]["verdict"] == "model_no_route" for v in full) == fr["both_repetitions_scoped_refusal_missions"]


def test_repetitions_agree_for_full(records):
    for v in records.values():
        reps = v["repetitions"]
        assert [x["rep"] for x in reps] == [1, 2]
        if v["policy"] == "full":
            assert reps[0]["verdict"] == reps[1]["verdict"] == v["outcome"]["verdict"]
            assert reps[0]["arrival_s"] == reps[1]["arrival_s"]
            assert v["repetitions_agree"] is True
        assert reps[0]["wall_s"] == v["outcome"]["compute_s"]


def test_outcome_fields_and_nulls(records):
    for k, v in records.items():
        o = v["outcome"]
        assert o["verdict"] in VERDICTS
        if o["verdict"] == "unresolved":
            assert o["reason_code"] in REASON_CODES
        else:
            assert o["reason_code"] is None
        assert o["within_budget"] == (o["compute_s"] is not None and o["compute_s"] <= 30)
        if o["verdict"] == "checked_route":
            assert v["route"] is not None and len(v["exposure"]) == 4
            assert o["arrival_s"] is not None and o["lower_bound_L_s"] is not None
            assert o["lower_bound_L_s"] <= o["arrival_s"]
            assert o["dwell_end_s"] == o["arrival_s"] + v["request"]["dwell_s"]
            assert all(e["contact"] is False for e in v["exposure"])
            assert v["refusal_scope"] is None
        else:
            assert v["route"] is None and v["exposure"] == []
            assert o["arrival_s"] is None and o["lower_bound_L_s"] is None and o["dwell_end_s"] is None
        if o["verdict"] == "model_no_route":
            assert v["refusal_scope"]["complete"] is True and v["refusal_scope"]["scope"]
        assert v["scenario_ids"] == [f"{v['scenario_set_id']}:{i}" for i in range(4)]
        assert [e["scenario_id"] for e in v["exposure"]] in ([], v["scenario_ids"])
        assert v["provenance"]["mock"] is True and v["provenance"]["policy"] == v["policy"]


def test_records_validate_contract_pieces(records, contract):
    route_v = validator_for(contract, "RouteFeature")
    exp_v = validator_for(contract, "ScenarioExposure")
    prov_v = validator_for(contract, "Provenance")
    verdict_v = validator_for(contract, "Verdict")
    reason_v = validator_for(contract, "ReasonCode")
    limits_v = validator_for(contract, "Limits")
    for k, v in records.items():
        assert not list(prov_v.iter_errors(v["provenance"])), k
        assert not list(verdict_v.iter_errors(v["outcome"]["verdict"])), k
        assert not list(reason_v.iter_errors(v["outcome"]["reason_code"])), k
        assert not list(limits_v.iter_errors(v["request"]["limits"])), k
        if v["route"] is not None:
            assert not list(route_v.iter_errors(v["route"])), k
        for e in v["exposure"]:
            assert not list(exp_v.iter_errors(e)), k


def test_route_times_monotone_and_aligned(records):
    for k, v in records.items():
        r = v["route"]
        if r is None:
            continue
        coords, times = r["geometry"]["coordinates"], r["properties"]["times_s"]
        assert len(coords) == len(times)
        assert all(b >= a for a, b in zip(times, times[1:])), k
        assert times[0] == v["request"]["depart_offset_s"] == v["outcome"]["departure_s"]
        assert times[-1] == v["outcome"]["arrival_s"]
        p = r["properties"]
        assert len(coords) == p["segment_count"] + 1
        assert p["node_ids"][0] == v["request"]["origin_node"]
        assert p["node_ids"][-1] == v["request"]["destination_node"]
        assert len(p["edge_ids"]) == len(p["node_ids"]) - 1
        assert p["length_m"] > 0
        for w in p["waits"]:
            assert w["to_s"] > w["from_s"] and w["node_id"] in p["node_ids"]
        lo, hi = v["request"]["destination_window"]
        assert lo <= v["outcome"]["arrival_s"] <= hi


@needs_assets
def test_route_endpoints_and_geometry_match_graph(records):
    for k, v in records.items():
        r = v["route"]
        if r is None:
            continue
        g = graph(v["region_id"])
        coords = r["geometry"]["coordinates"]
        for (lon, lat), node in ((coords[0], v["request"]["origin_node"]), (coords[-1], v["request"]["destination_node"])):
            x, y = to_5179(lon, lat)
            nx, ny = g["_xy"][node]
            assert math.hypot(x - nx, y - ny) < 0.5, (k, node)
        # every edge chains u->v and the summed chord length matches
        length = 0.0
        prev = v["request"]["origin_node"]
        for eid in r["properties"]["edge_ids"]:
            e = g["_edges"][eid]
            assert e["u"] == prev, (k, eid)
            (ux, uy), (vx, vy) = g["_xy"][e["u"]], g["_xy"][e["v"]]
            length += math.hypot(vx - ux, vy - uy)
            prev = e["v"]
        assert prev == v["request"]["destination_node"]
        assert abs(length - r["properties"]["length_m"]) < 0.11


@needs_assets
def test_records_match_recorded_sources(records):
    final_rows = {}
    with open(FINAL / "INDEPENDENT_ROWS.csv", newline="") as f:
        for row in csv.DictReader(f):
            final_rows[(row["region"], row["case_id"], row["arm"], int(row["rep"]))] = row
    abl_rows = {}
    with open(ABL / "analysis" / "ROWS.csv", newline="") as f:
        for row in csv.DictReader(f):
            abl_rows[(row["cohort"], row["case_id"], row["policy"], int(row["rep"]))] = row
    arm_of = {"travel_only": "A0", "flame_only": "A1", "flame_peak": "A2", "flame_dose": "A3"}
    for k, v in records.items():
        region, case_id = v["region_id"], v["case_id"]
        for x in v["repetitions"]:
            if v["policy"] == "full":
                row = final_rows[(region, case_id, "RDA_CAND", x["rep"])]
                assert x["frozen_state"] == row["state"]
            else:
                row = abl_rows[(region, case_id, arm_of[v["policy"]], x["rep"])]
                assert v["source_arm"] == arm_of[v["policy"]]
            assert x["wall_s"] == float(row["wall_s"])
            arr = row["arrival"]
            assert x["arrival_s"] == (int(arr) if arr else None)
        for s in v["source_records"]:
            root = FINAL.parent if s["asset"].startswith("WildfireGuardian_Latest") else ABL.parent
            assert sha256(root / s["path"]) == s["sha256"], s["path"]
        res = load((FINAL.parent if v["policy"] == "full" else ABL.parent) / v["source_records"][0]["path"])
        assert res["case_id"] == case_id and res["repetition"] == 1
        assert v["input_hashes"]["hazard"] == res["identities"]["hazard_path"]["sha256"]
        assert v["input_hashes"]["request"] == res["identities"]["request_path"]["sha256"]
        # never null -> 0 and never invented: exposure equals the recorded per-member values
        for e in v["exposure"]:
            pm = res["result"]["per_member"][e["scenario_id"]]
            assert e["peak_kw_m2"] == pm["peak"] and e["dose_kj_m2"] == pm["dose"]
        if v["policy"] != "full":
            row = abl_rows[(region, case_id, arm_of[v["policy"]], 1)]
            fp = {"True": True, "False": False, "": None}[row["full_policy_pass"]]
            assert v["full_policy_check"]["pass"] == fp
            comps = row["full_failure_components"]
            assert v["full_policy_check"]["failure_components"] == (comps.split("|") if comps else None)


@needs_assets
def test_full_records_use_the_packet_and_request_files(records, regions):
    hz = {s["scenario_set_id"]: s["hazard_sha256"] for r in regions["regions"] for s in r["scenario_sets"]}
    for v in records.values():
        if v["policy"] != "full":
            continue
        assert v["input_hashes"]["hazard"] == hz[v["scenario_set_id"]]
        req = INPUTS / "latest_inputs_try02" / "requests" / v["region_id"] / f"{v['case_id']}.json"
        assert v["input_hashes"]["request"] == sha256(req)
        q = load(req)
        assert v["request"]["origin_node"] == q["position"]["node"]
        assert v["request"]["destination_node"] == q["destinations"][0]["node"]
        assert v["request"]["depart_offset_s"] == q["departure"]
        assert v["request"]["destination_window"] == q["destinations"][0]["open_intervals"][0]
        assert v["request"]["limits"]["peak_kw_m2"] == q["budgets"]["peak"]
        assert v["request"]["incurred_per_member"] == q["incurred"]


@needs_assets
def test_ablation_policy_mapping_verified():
    transforms = load(ABL / "POLICY_TRANSFORMS.json")
    expected = {"A0": set(), "A1": {"FLAME"}, "A2": {"FLAME", "PEAK"}, "A3": {"FLAME", "DOSE"},
                "A4": {"FLAME", "PEAK", "DOSE"}}
    for t in transforms:
        assert set(t["enabled"]) == expected[t["arm"]]


# ---------------------------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------------------------

def test_footprints(regions):
    for r in regions["regions"]:
        fc = load(PUBLIC / r["id"] / "footprints.geojson")
        assert fc["type"] == "FeatureCollection" and fc["features"]
        times = set()
        for f in fc["features"]:
            p = f["properties"]
            assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
            assert p["area_km2"] > 0
            assert p["note"] == "recorded burned footprint at input time (preset for user-drawn zones only)"
            times.add(p["input_time"])
        # every recorded scenario input time of the region has a footprint preset
        assert set(r["input_times"]) <= times
