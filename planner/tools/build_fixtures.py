#!/usr/bin/env python3
"""Mock-API fixtures and burned-footprint presets for the village evacuation planner (ARCHITECTURE.md §4.1/§4.2).

Reads only recorded data from the verified release extracts (planner/.assets/extracted/):
graphs, packet HAZARD.json + constructed_arrays.npz, mission requests, event exports, final-panel
RESULT.json + INDEPENDENT_ROWS.csv and the ablation RESULT.json + analysis/ROWS.csv. It never imports
or runs forecasting/routing code and never fabricates values (absent values are null, never 0).

Writes:
  planner/mock_api/fixtures/MANIFEST.json
  planner/mock_api/fixtures/regions.json                        official RegionList
  planner/mock_api/fixtures/forecast/<region>/<input>.json      official ForecastCollection (all cells)
  planner/mock_api/fixtures/nodes/<region>.json                 compact node table for mock snapping
  planner/mock_api/fixtures/records/<region>/<case>__<policy>.json
  planner/public/data/regions/<region>/footprints.geojson

Usage: python3 planner/tools/build_fixtures.py               # everything above
       python3 planner/tools/build_fixtures.py --nodes-only  # only nodes/*.json (+ allowed_node_count in
                                                             # regions.json and their MANIFEST.json entries)
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import planner_common as pc  # noqa: E402

FIXTURES = pc.PLANNER / "mock_api" / "fixtures"
PUBLIC_REGIONS = pc.PLANNER / "public" / "data" / "regions"
FOOTPRINT_PAD_M = 2000.0
ORIENTATION_SAMPLE_PER_REGION = 3000

# Ablation arm -> contract policy. Verified at build time against POLICY_TRANSFORMS.json
# (enabled constraint sets) before any record is written.
ARM_POLICY = {"A0": "travel_only", "A1": "flame_only", "A2": "flame_peak", "A3": "flame_dose", "A4": "full"}
ARM_EXPECTED_ENABLED = {"A0": set(), "A1": {"FLAME"}, "A2": {"FLAME", "PEAK"}, "A3": {"FLAME", "DOSE"},
                        "A4": {"FLAME", "PEAK", "DOSE"}}
RECORDED_HOST = {"recorded": True, "machine": "Apple M5 Pro", "os": "macOS (native)",
                 "source": "WildfireGuardian_Latest_Independent_Final_20261015/REPORT.md (native Darwin arm64 Apple M5 Pro host)"}
CLOCK = "complete-request wall_s recorded for the execution (external launch to authoritative publication) on the recorded native host"
# Nodes allowed as a start or destination: the Route-Check API's own rule (origin/feat/api api/regions.py,
# GraphIndex.load: out_degree > 0 and in_degree > 0 over the graph's directed edges). The mock snaps with it.
ALLOWED_RULE = ("at least one incoming and one outgoing road edge (the Route-Check API rule, "
                "api/regions.py GraphIndex.load)")
ALLOWED_COUNT_RULE = ("allowed_node_count = number of nodes with at least one incoming and one outgoing edge of the "
                      "directed road graph (the Route-Check API rule, api/regions.py)")


class BuildError(SystemExit):
    pass


def check(cond, msg):
    if not cond:
        raise BuildError("CHECK FAILED: " + msg)


# ---------------------------------------------------------------------------------------------
# Verdict mapping (ARCHITECTURE.md §3)
# ---------------------------------------------------------------------------------------------

def verdict_from_frozen(state: str) -> str:
    if state in ("CHECKED_CENTRE_OPTIMUM", "CHECKED_ROUTE"):
        return "checked_route"
    if state == "CERTIFIED_CENTRE_REFUSAL":
        return "model_no_route"
    return "unresolved"


def verdict_from_ablation(own_outcome: str, decision: str) -> str:
    if own_outcome == "CHECKED_ROUTE" and decision == "CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN":
        return "checked_route"
    if own_outcome == "SCOPED_REFUSAL" and decision == "FULL_MODEL_REFUSAL_PROVEN":
        return "model_no_route"
    return "unresolved"


def reason_code(verdict: str, state: str, result: dict):
    if verdict != "unresolved":
        return None
    blob = " ".join(str(x) for x in (state, result.get("primary_status"), result.get("primary_reason"),
                                     (result.get("decision") or {}).get("unresolved_reason"))).upper()
    if "TIMEOUT" in blob or "MAX_LABELS" in blob or "TIME_CAP" in blob:
        return "TIMEOUT"
    if "REJECT" in blob or "CHECK_FAIL" in blob:
        return "CHECK_FAILED"
    return "OTHER"


def as_bool(s: str):
    if s == "True":
        return True
    if s == "False":
        return False
    return None


def as_float(s):
    if s is None or s == "":
        return None
    return float(s)


def as_int_or_none(v):
    if v is None or v == "":
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


# ---------------------------------------------------------------------------------------------
# Grid orientation (verified, not assumed)
# ---------------------------------------------------------------------------------------------

def cell_polygons(g: pc.Graph):
    """WGS84 ring per cell, row counted from the SOUTH edge (row 0 at grid.y0), cell = row*W + col."""
    G = g.grid
    W, H, res = G["width"], G["height"], G["resolution"]
    xs = G["x0"] + np.arange(W + 1) * res
    ys = G["y0"] + np.arange(H + 1) * res
    XX, YY = np.meshgrid(xs, ys)  # [row_s, col]
    lon, lat = pc.to_wgs84(XX.ravel(), YY.ravel())
    lon = np.round(np.asarray(lon).reshape(H + 1, W + 1), 6)
    lat = np.round(np.asarray(lat).reshape(H + 1, W + 1), 6)
    rings = {}
    for r in range(H):
        for c in range(W):
            rings[r * W + c] = [[float(lon[r, c]), float(lat[r, c])], [float(lon[r, c + 1]), float(lat[r, c + 1])],
                                [float(lon[r + 1, c + 1]), float(lat[r + 1, c + 1])], [float(lon[r + 1, c]), float(lat[r + 1, c])],
                                [float(lon[r, c]), float(lat[r, c])]]
    return rings


def orientation_checks(g: pc.Graph, rings: dict) -> dict:
    """(1) every edge segment midpoint (EPSG:5179) lies in cell row_s*W+col with row_s from the south;
    (2) for a sample, the WGS84 midpoint lies inside the published polygon of the graph's cell."""
    G = g.grid
    W, H, res = G["width"], G["height"], G["resolution"]
    mids_x, mids_y, cells = [], [], []
    for e in g.raw["edges"]:
        u, v = g.edges[e["id"]]
        for s in e["segments"]:
            t = 0.5 * (s["start"] + s["end"])
            mids_x.append(g.x[u] + t * (g.x[v] - g.x[u]))
            mids_y.append(g.y[u] + t * (g.y[v] - g.y[u]))
            cells.append(s["cell"])
    mx, my, cells = np.array(mids_x), np.array(mids_y), np.array(cells)
    col = np.floor((mx - G["x0"]) / res).astype(int)
    row_s = np.floor((my - G["y0"]) / res).astype(int)
    row_n = H - 1 - row_s
    south_ok = int(np.sum(row_s * W + col == cells))
    north_ok = int(np.sum(row_n * W + col == cells))
    # Sample test against the published WGS84 polygons (skip midpoints < 1 m from a cell boundary,
    # where 6-decimal rounding of the corners could flip the test).
    fx = (mx - G["x0"]) / res - col
    fy = (my - G["y0"]) / res - row_s
    margin = 1.0 / res
    interior = np.nonzero((fx > margin) & (fx < 1 - margin) & (fy > margin) & (fy < 1 - margin))[0]
    rng = np.random.default_rng(20261017)
    pick = rng.choice(interior, size=min(ORIENTATION_SAMPLE_PER_REGION, len(interior)), replace=False)
    lon, lat = pc.to_wgs84(mx[pick], my[pick])
    inside = 0
    inside_flipped = 0
    for k, i in enumerate(pick):
        p = Point(float(lon[k]), float(lat[k]))
        cell = int(cells[i])
        if Polygon(rings[cell]).contains(p):
            inside += 1
        r, c = divmod(cell, W)
        if Polygon(rings[(H - 1 - r) * W + c]).contains(p):
            inside_flipped += 1
    return {"segments": int(len(cells)), "midpoint_cell_south_up_rows": south_ok,
            "midpoint_cell_north_up_rows": north_ok, "wgs84_polygon_sample": int(len(pick)),
            "wgs84_sample_inside_assigned_cell": inside, "wgs84_sample_inside_if_rows_flipped": inside_flipped,
            "pass": south_ok == len(cells) and inside == len(pick) and len(pick) > 0}


def packet_export_check(pdir: Path, h: dict, pk, region: str) -> dict:
    ev = pc.packet_event_id(pdir)
    t = pdir.name
    G = h["grid"]
    W, H = G["width"], G["height"]
    exp_path = pc.INPUTS_ROOT / "latest_inputs_try02" / "exports" / ev / f"FORECAST_{t}.npz"
    with np.load(exp_path, allow_pickle=False) as ex:
        A = ex["affine_transform"]
        check(A[1] == 0 and A[3] == 0 and A[0] == 375 and A[4] == -375, f"export affine not north-up 375 m: {A}")
        c0 = int(round((G["x0"] - A[2]) / 375.0))
        r0 = int(round((A[5] - (G["y0"] + H * 375.0)) / 375.0))
        prob = ex["new_burn_probability"][r0:r0 + H, c0:c0 + W]
        valid = ex["probability_valid"][r0:r0 + H, c0:c0 + W]
        ev2 = str(ex["contract__event_id"])
    P = pk["mask__constructed_probability"]
    V = pk["mask__probability_valid_native"]
    same = bool((V == valid).all() and np.allclose(np.where(V, P, 0.0), np.where(valid, prob, 0.0), rtol=0, atol=0))
    flipped = bool((V[::-1] == valid).all() and np.allclose(np.where(V[::-1], P[::-1], 0.0), np.where(valid, prob, 0.0)))
    # HAZARD flat member arrays: present-fire cells (native north-up npz) must be flame@interval 0 at the
    # south-up flat index (H-1-r)*W + c.
    r, c = np.nonzero(pk["current_active"])
    hit_flip = hit_same = total = 0
    for m in h["members"]:
        f0 = np.asarray(m["flame"][0], dtype=bool)
        hit_flip += int(f0[(H - 1 - r) * W + c].sum())
        hit_same += int(f0[r * W + c].sum())
        total += len(r)
    return {"region": region, "input": t, "event_id": ev, "export_event_id": ev2,
            "export_window_rows_cols": [r0, c0],
            "packet_probability_equals_export_window_native_order": same,
            "packet_probability_equals_export_window_if_flipped": flipped,
            "hazard_flame0_at_current_active_south_up_index": [hit_flip, total],
            "hazard_flame0_at_current_active_same_order_index": [hit_same, total],
            "policy_zero_cells_have_zero_probability": bool(np.all(P[~V] == 0.0)),
            "pass": same and not flipped and hit_flip == total and (total == 0 or hit_same < total) and ev == ev2}


# ---------------------------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------------------------

def provenance(commit: str, generated_at: str, **kw) -> dict:
    p = dict(pc.PROVENANCE_BASE)
    p.update({"git_commit": commit, "git_dirty": None, "input_hashes": {}, "scenario_ids": [],
              "generated_at": generated_at, "mock": True})
    p.update(kw)
    return p


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------

def build_route(g: pc.Graph, result: dict, origin: str, destination: str, departure) -> dict:
    legs = result["legs"]
    check(legs, "checked route without legs")
    cur = g.index[origin]
    px, py = g.x[cur], g.y[cur]
    xs, ys, times = [px], [py], [legs[0]["start"]]
    check(legs[0]["start"] == departure, f"first leg start {legs[0]['start']} != departure {departure}")
    node_ids = [origin]
    edge_ids, waits = [], []
    length = 0.0
    for i, leg in enumerate(legs):
        check(leg["start"] == times[-1], f"leg {i} start {leg['start']} != previous end {times[-1]}")
        check(leg["end"] >= leg["start"], f"leg {i} ends before it starts")
        if leg["kind"] == "EDGE":
            u, v = g.edges[leg["edge"]]
            check(u == cur, f"leg {i} edge {leg['edge']} does not start at the current node")
            f0, f1 = leg["from_fraction"], leg["to_fraction"]
            check(f0 == 0 and f1 == 1, f"leg {i}: partial edge fractions {f0}..{f1} not supported")
            chord = math.hypot(g.x[v] - g.x[u], g.y[v] - g.y[u])
            length += chord * (f1 - f0)
            px = g.x[u] + f1 * (g.x[v] - g.x[u])
            py = g.y[u] + f1 * (g.y[v] - g.y[u])
            cur = v
            node_ids.append(g.node_ids[v])
            edge_ids.append(leg["edge"])
        elif leg["kind"] == "WAIT":
            check(g.index[leg["node"]] == cur, f"leg {i} waits at {leg['node']} away from the current node")
            if waits and waits[-1]["node_id"] == leg["node"] and waits[-1]["to_s"] == leg["start"]:
                waits[-1]["to_s"] = leg["end"]
            else:
                waits.append({"node_id": leg["node"], "from_s": leg["start"], "to_s": leg["end"]})
        else:
            raise BuildError(f"unknown leg kind {leg['kind']}")
        xs.append(px)
        ys.append(py)
        times.append(leg["end"])
    check(g.node_ids[cur] == destination, f"route ends at {g.node_ids[cur]}, expected {destination}")
    check(times[-1] == result["arrival"], f"last time {times[-1]} != arrival {result['arrival']}")
    lon, lat = pc.to_wgs84(np.array(xs), np.array(ys))
    coords = [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat)]
    return {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {"times_s": times, "node_ids": node_ids, "segment_count": len(legs),
                           "edge_ids": edge_ids, "waits": waits, "length_m": round(length, 1),
                           "vertex_rule": ("one vertex per leg end plus the origin; EDGE legs are straight "
                                           "chords u->v; a WAIT leg repeats the point with its end time; "
                                           "consecutive 1 s WAIT legs at one node are merged in waits[]")}}


def exposure_from_result(result: dict, scenario_ids):
    pm = result.get("per_member") or {}
    out = []
    for sid in scenario_ids:
        m = pm.get(sid)
        out.append({"scenario_id": sid,
                    "peak_kw_m2": None if m is None else m.get("peak"),
                    "dose_kj_m2": None if m is None else m.get("dose"),
                    "contact": False})
    return out


def exposure_from_grade(grade: dict, scenario_ids):
    pm = (grade.get("independent_centre") or {}).get("per_member") or {}
    out = []
    for sid in scenario_ids:
        m = pm.get(sid)
        out.append({"scenario_id": sid,
                    "peak_kw_m2": None if m is None else m.get("peak_kw_m2"),
                    "dose_kj_m2": None if m is None else m.get("dose_total_kj_m2"),
                    "contact": None if m is None else bool(m.get("flame_contact"))})
    return out


# ---------------------------------------------------------------------------------------------
# Node table (mock snapping)
# ---------------------------------------------------------------------------------------------

def allowed_mask(g: pc.Graph) -> np.ndarray:
    """Bool per node: allowed as a start or destination by the Route-Check API's rule (api/regions.py
    GraphIndex.load): the node has at least one outgoing and at least one incoming edge."""
    out_deg = np.zeros(g.node_count, dtype=np.int64)
    in_deg = np.zeros(g.node_count, dtype=np.int64)
    for e in g.raw["edges"]:
        out_deg[g.index[e["u"]]] += 1
        in_deg[g.index[e["v"]]] += 1
    return (out_deg > 0) & (in_deg > 0)


def node_table(region: str, g: pc.Graph, allowed: np.ndarray) -> dict:
    """fixtures/nodes/<region>.json: ids, WGS84 lon/lat (6 decimals) and the allowed flag of every graph node, plus
    the recorded mission endpoints (each must be allowed, or the recorded mission could not be posed to the API)."""
    lon, lat = pc.to_wgs84(g.x, g.y)
    recorded_nodes = {}
    for rp in pc.request_paths(region):
        req = json.loads(rp.read_bytes())
        for role, node in (("origin", req["position"]["node"]), ("destination", req["destinations"][0]["node"])):
            k = g.index[node]
            e = recorded_nodes.setdefault(node, {"node_id": node, "allowed": bool(allowed[k]),
                                                 "in_largest_scc": bool(g.scc_mask[k]), "uses": []})
            e["uses"].append(f"{rp.stem}:{role}")
    bad = sorted(n for n, e in recorded_nodes.items() if not e["allowed"])
    check(not bad, f"{region}: recorded mission endpoints not allowed by the API rule: {bad}")
    return {
        "region": region, "graph_id": g.revision, "graph_sha256": g.sha256, "crs_source": "EPSG:5179",
        "ids": g.node_ids,
        "lon": [round(float(v), 6) for v in lon], "lat": [round(float(v), 6) for v in lat],
        "allowed": [int(b) for b in allowed],
        "allowed_rule": ALLOWED_RULE,
        "allowed_count": int(allowed.sum()),
        "largest_scc_count": int(g.scc_mask.sum()),
        # indices into ids of the nodes outside the largest strongly connected component (the planner's entry points
        # are the nearest largest-SCC nodes, ARCHITECTURE.md 4.2; an allowed node outside it may be disconnected)
        "not_in_largest_scc": [int(i) for i in np.nonzero(~g.scc_mask)[0]],
        "recorded_mission_nodes": sorted(recorded_nodes.values(), key=lambda e: e["node_id"]),
        "recorded_mission_nodes_note": ("Recorded mission endpoints: allowed under allowed_rule (checked at build "
                                        "time) and whether each lies in the largest strongly connected component."),
    }


def build_nodes_only() -> dict:
    """Regenerate only fixtures/nodes/*.json. regions.json gets the new allowed_node_count (and the provenance text
    that defines it); MANIFEST.json gets the new entries for the changed files. Every other fixture is untouched."""
    pc.require_assets()
    at = pc.utc_now()
    regions_path, manifest_path = FIXTURES / "regions.json", FIXTURES / "MANIFEST.json"
    region_list = json.loads(regions_path.read_bytes())
    manifest = json.loads(manifest_path.read_bytes())
    by_id = {r["id"]: r for r in region_list["regions"]}
    before = {p: pc.sha256_file(p) for p in [regions_path] + sorted((FIXTURES / "nodes").glob("*.json"))}
    changed, counts = [], {}
    for meta in pc.REGIONS:
        region = meta["id"]
        g = pc.load_graph(region)
        r = by_id[region]
        check(r["graph_sha256"] == g.sha256 and r["node_count"] == g.node_count,
              f"{region}: regions.json describes another graph; run the full build")
        allowed = allowed_mask(g)
        path = FIXTURES / "nodes" / f"{region}.json"
        old = json.loads(path.read_bytes()) if path.is_file() else {}
        new = node_table(region, g, allowed)
        pc.write_json(path, new, compact=True)
        changed.append(path)
        counts[region] = {"allowed_rule_before": old.get("allowed_rule"), "allowed_count_before": old.get("allowed_count"),
                          "allowed_node_count_before": r["allowed_node_count"], "allowed_node_count": int(allowed.sum()),
                          "node_table_keys_added": sorted(set(new) - set(old))}
        r["allowed_node_count"] = int(allowed.sum())
    region_list["provenance"]["allowed_node_rule"] = ALLOWED_COUNT_RULE
    pc.write_json(regions_path, region_list, compact=False)
    changed.append(regions_path)
    if all(before.get(p) == pc.sha256_file(p) for p in changed):
        print("node tables and regions.json already current; MANIFEST.json unchanged")
        return manifest
    entries = {f["path"]: f for f in manifest["files"]}
    for p in changed:
        rel = str(p.relative_to(FIXTURES))
        check(rel in entries, f"MANIFEST.json has no entry for {rel}")
        entries[rel].update({"sha256": pc.sha256_file(p), "bytes": p.stat().st_size})
    manifest["total_fixture_bytes"] = sum(f["bytes"] for f in manifest["files"])
    manifest["conventions"]["allowed_nodes"] = ALLOWED_RULE
    manifest.setdefault("partial_regenerations", []).append({
        "at": at, "generator": "planner/tools/build_fixtures.py --nodes-only", "git_commit": pc.git_commit(),
        "files": [str(p.relative_to(FIXTURES)) for p in changed],
        "reason": "nodes-only regeneration: allowed nodes follow the Route-Check API rule; regions.json changed only in "
                  "allowed_node_count and provenance.allowed_node_rule",
        "regions": counts})
    pc.write_json(manifest_path, manifest, compact=False)
    for region, c in counts.items():
        print("%s: allowed_node_count %d (was %d)" % (region, c["allowed_node_count"], c["allowed_node_count_before"]))
    return manifest


# ---------------------------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------------------------

def load_rows():
    final_rows = {}
    with open(pc.FINAL_ROOT / "INDEPENDENT_ROWS.csv", newline="") as f:
        for r in csv.DictReader(f):
            final_rows[(r["region"], r["case_id"], r["arm"], int(r["rep"]))] = r
    abl_rows = {}
    with open(pc.ABLATION_ROOT / "analysis" / "ROWS.csv", newline="") as f:
        for r in csv.DictReader(f):
            abl_rows[(r["cohort"], r["case_id"], r["policy"], int(r["rep"]))] = r
    reviewed = {}
    p = pc.ABLATION_ROOT / "analysis" / "ROWS_REVIEWED.csv"
    if p.is_file():
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                reviewed[(r["cohort"], r["case_id"], r["policy"], int(r["rep"]))] = r
    return final_rows, abl_rows, reviewed


def verify_arm_mapping():
    transforms = json.loads((pc.ABLATION_ROOT / "POLICY_TRANSFORMS.json").read_text())
    seen = {}
    for t in transforms:
        seen.setdefault(t["arm"], set()).add(frozenset(t["enabled"]))
    for arm, exp in ARM_EXPECTED_ENABLED.items():
        check(seen.get(arm) == {frozenset(exp)}, f"POLICY_TRANSFORMS enabled set for {arm}: {seen.get(arm)} != {exp}")
    return {arm: {"policy": ARM_POLICY[arm], "enabled_constraints": sorted(ARM_EXPECTED_ENABLED[arm])}
            for arm in sorted(ARM_POLICY)}


def rel_in_asset(path: Path, root_parent: Path) -> str:
    return str(path.relative_to(root_parent))


def build():
    pc.require_assets()
    commit = pc.git_commit()
    generated_at = pc.utc_now()
    written = []  # (path, bytes)

    def out(path: Path, obj, compact=True):
        n = pc.write_json(path, obj, compact=compact)
        written.append(path)
        return n

    arm_map = verify_arm_mapping()
    final_rows, abl_rows, reviewed_rows = load_rows()
    final_review = json.loads((pc.FINAL_ROOT / "FINAL_REVIEW.json").read_text())
    final_asset_parent = pc.FINAL_ROOT.parent
    abl_asset_parent = pc.ABLATION_ROOT.parent
    rows_sha = pc.sha256_file(pc.FINAL_ROOT / "INDEPENDENT_ROWS.csv")
    abl_rows_sha = pc.sha256_file(pc.ABLATION_ROOT / "analysis" / "ROWS.csv")

    regions_out = []
    list_input_hashes = {}
    orientation = {}
    packet_checks = []
    record_summary = []
    footprint_summary = {}
    region_notes = {}
    for meta in pc.REGIONS:
        region = meta["id"]
        g = pc.load_graph(region)
        G = g.grid
        W, H = G["width"], G["height"]
        bbox = [round(v, 6) for v in g.wgs84_bbox()]
        rings = cell_polygons(g)
        orientation[region] = orientation_checks(g, rings)
        check(orientation[region]["pass"], f"grid orientation check failed for {region}: {orientation[region]}")
        list_input_hashes[f"graphs/{region}/graph.json"] = g.sha256

        # ---- scenario sets and forecasts (one per packet directory)
        scenario_sets, input_times, sets_by_time = [], [], {}
        for pdir in pc.packet_dirs(region):
            hz_bytes = (pdir / "HAZARD.json").read_bytes()
            h = json.loads(hz_bytes)
            check(h["grid"] == {"x0": G["x0"], "y0": G["y0"], "resolution": G["resolution"], "width": W, "height": H},
                  f"{pdir}: HAZARD grid differs from graph grid")
            check(h["graph_revision"] == g.revision, f"{pdir}: graph revision mismatch")
            check(h["provenance"].get("row_reversal") is True, f"{pdir}: row_reversal not true")
            check(h["provenance"]["identity"]["graph_file_sha256"] == g.sha256, f"{pdir}: graph sha mismatch")
            ssid, sids = pc.scenario_set_from_hazard(h)
            check(len(sids) == 4, f"{pdir}: expected 4 scenario members")
            t_iso = pc.iso_z(h["time_origin"])
            check(pc.compact_time(h["time_origin"]) == pdir.name, f"{pdir}: time_origin mismatch")
            hz_sha = pc.sha256_bytes(hz_bytes)
            npz_path = pdir / "constructed_arrays.npz"
            npz_sha = pc.sha256_file(npz_path)
            ev = pc.packet_event_id(pdir)
            check(ev == meta["expected_event"], f"{pdir}: event {ev} != expected {meta['expected_event']}")
            exp_path = pc.INPUTS_ROOT / "latest_inputs_try02" / "exports" / ev / f"FORECAST_{pdir.name}.npz"
            with np.load(npz_path, allow_pickle=False) as pk:
                pk = {k: pk[k] for k in pk.files}
            pchk = packet_export_check(pdir, h, pk, region)
            packet_checks.append(pchk)
            check(pchk["pass"], f"packet/export orientation check failed: {pchk}")
            horizon = float(h["valid_until"]) - float(h["valid_from"])
            sset = {"scenario_set_id": ssid, "input_time": t_iso, "scenario_ids": sids,
                    "horizon_s": horizon, "hazard_sha256": hz_sha}
            scenario_sets.append(sset)
            input_times.append(t_iso)
            sets_by_time[pdir.name] = sset
            list_input_hashes[f"packets/{region}/{pdir.name}/HAZARD.json"] = hz_sha

            P = pk["mask__constructed_probability"]
            V = pk["mask__probability_valid_native"]
            B = pk["current_active"]
            K = pk["mask__known_burned"]
            check(np.all(np.isfinite(P)), f"{pdir}: non-finite probability")
            feats = []
            for row in range(H):          # row counted from the south (graph / HAZARD cell convention)
                nrow = H - 1 - row        # native north-up row of the NPZ arrays
                for col in range(W):
                    cell = row * W + col
                    feats.append({"type": "Feature", "id": f"r{row}c{col}",
                                  "geometry": {"type": "Polygon", "coordinates": [rings[cell]]},
                                  "properties": {"row": row, "col": col,
                                                 "p_new_burn_1h": pc.sig6(P[nrow, col]),
                                                 "valid": bool(V[nrow, col]),
                                                 "burning_now": bool(B[nrow, col]),
                                                 "cell": cell, "known_burned": bool(K[nrow, col])}})
            fc = {"type": "FeatureCollection", "region": region, "input_time": t_iso, "bbox": bbox,
                  "features": feats,
                  "provenance": provenance(commit, generated_at, region=region, input_time=t_iso,
                                           graph_id=g.revision, scenario_set_id=ssid, scenario_ids=sids,
                                           fire_input_type="recorded", policy=None,
                                           input_hashes={"hazard": hz_sha, "constructed_arrays": npz_sha,
                                                         "forecast_export": pc.sha256_file(exp_path),
                                                         "graph": g.sha256},
                                           source="packet constructed_arrays.npz (mask__constructed_probability, "
                                                  "mask__probability_valid_native, current_active, mask__known_burned)")}
            out(FIXTURES / "forecast" / region / f"{pdir.name}.json", fc)

        # ---- node table
        allowed = allowed_mask(g)
        out(FIXTURES / "nodes" / f"{region}.json", node_table(region, g, allowed))

        # ---- records
        for rp in pc.request_paths(region):
            case_id = rp.stem
            req_bytes = rp.read_bytes()
            req = json.loads(req_bytes)
            sset = sets_by_time[case_id.split("_")[0]]
            sids = sset["scenario_ids"]
            dest = req["destinations"][0]
            check(len(req["destinations"]) == 1 and len(dest["open_intervals"]) == 1, f"{rp}: one destination/interval")
            check(set(req["incurred"]) == set(sids) and set(req["budgets"]["dose"]) == set(sids),
                  f"{rp}: member ids differ from the scenario set")
            inc = pc.single_value([req["incurred"][s] for s in sids])
            dose_budget = pc.single_value([req["budgets"]["dose"][s] for s in sids])
            request_block = {
                "origin_node": req["position"]["node"], "destination_node": dest["node"],
                "depart_offset_s": req["departure"], "dwell_s": dest["dwell"],
                "destination_window": list(dest["open_intervals"][0]), "horizon_s": req["horizon"],
                "limits": {"peak_kw_m2": req["budgets"]["peak"], "dose_kj_m2": dose_budget},
                "incurred_dose_kj_m2": inc,
                "incurred_per_member": {s: req["incurred"][s] for s in sids},
                "exposure_scope": req.get("exposure_scope"),
                "limits_note": ("limits are the recorded request budgets (dose budget per member, equal for all "
                                "members); FN/FX missions use mission-specific dose budgets, others 100 kJ/m²")
                if dose_budget is not None else "dose budgets differ between members (see the request file)",
            }
            if inc is None:
                request_block["incurred_note"] = "incurred dose differs between members; scalar is null"
            req_sha = pc.sha256_bytes(req_bytes)

            def load_result(root_parent, root, raw_rel, label):
                p = root / raw_rel / label / "RESULT.json"
                b = p.read_bytes()
                return json.loads(b), pc.sha256_bytes(b), rel_in_asset(p, root_parent)

            # -- policy full: final panel RDA_CAND (rep 1 authoritative, rep 2 recorded and compared)
            reps = []
            for rep in (1, 2):
                label = f"{region}__{case_id}__r{rep}__RDA_CAND"
                res, sha, path = load_result(final_asset_parent, pc.FINAL_ROOT, pc.FINAL_RAW_REL, label)
                row = final_rows[(region, case_id, "RDA_CAND", rep)]
                check(res["case_id"] == case_id and res["cohort"] == region and res["repetition"] == rep,
                      f"{label}: RESULT identity fields")
                verdict = verdict_from_frozen(row["state"])
                arr_row = as_int_or_none(row["arrival"])
                arr_res = res["result"].get("arrival")
                check(arr_row == arr_res, f"{label}: INDEPENDENT_ROWS arrival {arr_row} != RESULT {arr_res}")
                if verdict == "checked_route":
                    check(res["primary_status"] == "CHECKED_ROUTE" and row["route"] == "True", f"{label}: status")
                if verdict == "model_no_route":
                    check(res["primary_status"] == "PROVEN_INFEASIBLE" and (res.get("refusal_certificate") or {}).get("complete"),
                          f"{label}: refusal certificate")
                check(res["identities"]["hazard_path"]["sha256"] == sset["hazard_sha256"], f"{label}: hazard sha")
                check(res["identities"]["request_path"]["sha256"] == req_sha, f"{label}: request sha")
                check(res["identities"]["graph_path"]["sha256"] == g.sha256, f"{label}: graph sha")
                reps.append({"res": res, "sha": sha, "path": path, "row": row, "verdict": verdict,
                             "wall_s": float(row["wall_s"]), "arrival": arr_res, "state": row["state"], "rep": rep})
            check(reps[0]["verdict"] == reps[1]["verdict"] and reps[0]["arrival"] == reps[1]["arrival"],
                  f"{region} {case_id}: repetition 2 disagrees with repetition 1")
            records = [("full", "RDA_CAND", reps, None)]

            # -- ablation policies A0..A3 (A4 = full policy is cross-referenced only)
            abl = {}
            for arm in ("A0", "A1", "A2", "A3", "A4"):
                areps = []
                for rep in (1, 2):
                    label = f"{region}__{case_id}__r{rep}__{arm}"
                    res, sha, path = load_result(abl_asset_parent, pc.ABLATION_ROOT, pc.ABLATION_RAW_REL, label)
                    row = abl_rows[(region, case_id, arm, rep)]
                    # Ablation RESULT: "arm" is the solver arm (RDA_CAND), "policy" is the ablation arm A0..A4.
                    check(res["case_id"] == case_id and res["cohort"] == region and res["policy"] == arm
                          and res["arm"] == "RDA_CAND" and res["repetition"] == rep and res["job_id"] == label,
                          f"{label}: RESULT identity fields")
                    verdict = verdict_from_ablation(row["own_outcome"], row["authoritative_decision"])
                    check(as_int_or_none(row["arrival"]) == res["result"].get("arrival"), f"{label}: arrival")
                    check(row["primary_status"] == res["primary_status"], f"{label}: primary status")
                    grade_path = pc.ABLATION_ROOT / row["grade_path"] if row.get("grade_path") else None
                    grade = json.loads(grade_path.read_bytes()) if grade_path and grade_path.is_file() else None
                    areps.append({"res": res, "sha": sha, "path": path, "row": row, "verdict": verdict,
                                  "wall_s": float(row["wall_s"]), "arrival": res["result"].get("arrival"),
                                  "state": row["own_outcome"], "rep": rep, "grade": grade,
                                  "grade_rel": rel_in_asset(grade_path, abl_asset_parent) if grade else None,
                                  "grade_sha": pc.sha256_file(grade_path) if grade else None,
                                  "reviewed": reviewed_rows.get((region, case_id, arm, rep))})
                abl[arm] = areps
                if arm != "A4":
                    records.append((ARM_POLICY[arm], arm, areps, arm))

            for policy, arm, rr, abl_arm in records:
                r1 = rr[0]
                res = r1["res"]
                result = res["result"]
                verdict = r1["verdict"]
                rc = reason_code(verdict, r1["state"], res)
                arrival = result.get("arrival") if verdict == "checked_route" else None
                lb = (res.get("optimality_certificate") or {}).get("lower_bound_arrival") if verdict == "checked_route" else None
                dwell_end = None
                if verdict == "checked_route":
                    me = (((res.get("whole_road_check") or {}).get("mission") or {}).get("mission_end") or {})
                    frac = me.get("__wfg_fraction__") if isinstance(me, dict) else None
                    if frac:
                        num, den = int(frac["numerator"]), int(frac["denominator"])
                        dwell_end = num // den if num % den == 0 else num / den
                    elif isinstance(me, str):
                        dwell_end = as_int_or_none(me)
                    if dwell_end is not None:
                        check(dwell_end == arrival + dest["dwell"], f"{case_id} {policy}: mission_end != arrival+dwell")
                route = build_route(g, result, req["position"]["node"], dest["node"], req["departure"]) \
                    if verdict == "checked_route" else None
                exposure = exposure_from_result(result, sids) if verdict == "checked_route" else []
                refusal = None
                if verdict == "model_no_route":
                    rcert = res.get("refusal_certificate") or {}
                    refusal = {"relaxation_kind": rcert.get("relaxation_kind"), "stage": rcert.get("stage"),
                               "complete": rcert.get("complete"), "scope": rcert.get("scope"),
                               "result_status": result.get("status"), "result_reason": result.get("reason")}
                if abl_arm is None:
                    fpc = {"pass": True if verdict == "checked_route" else None, "failure_components": None,
                           "source": "final panel RDA_CAND: the full policy is the evaluated policy"}
                    frozen_source = "INDEPENDENT_ROWS.csv state"
                    compute_source = "INDEPENDENT_ROWS.csv wall_s (complete request)"
                else:
                    row = r1["row"]
                    comps = row["full_failure_components"]
                    fpc = {"pass": as_bool(row["full_policy_pass"]),
                           "failure_components": comps.split("|") if comps else None,
                           "source": "ablation analysis/ROWS.csv full_policy_pass / full_failure_components (dual-policy grade, repetition 1)"}
                    frozen_source = "ablation analysis/ROWS.csv own_outcome"
                    compute_source = "ablation analysis/ROWS.csv wall_s (complete request)"
                compute_s = r1["wall_s"]
                rec = {
                    "case_id": case_id, "region_id": region, "policy": policy,
                    "source_arm": arm, "repetition": 1,
                    "scenario_set_id": sset["scenario_set_id"], "input_time": sset["input_time"],
                    "scenario_ids": sids,
                    "request": request_block,
                    "outcome": {
                        "verdict": verdict, "reason_code": rc,
                        "raw_status": res.get("primary_status"), "raw_reason": res.get("primary_reason"),
                        "authoritative_decision": (res.get("decision") or {}).get("authoritative_status"),
                        "frozen_state": r1["state"], "frozen_state_source": frozen_source,
                        "departure_s": req["departure"], "arrival_s": arrival, "lower_bound_L_s": lb,
                        "dwell_end_s": dwell_end, "compute_s": compute_s, "compute_s_source": compute_source,
                        "within_budget": compute_s <= 30.0,
                    },
                    "route": route,
                    "exposure": exposure,
                    "exposure_scope": ("centre model of this execution's own policy (RESULT result.per_member; "
                                       "dose includes incurred)" + (
                                           "; this policy zeroes the radiant flux, so peak/dose are not physical "
                                           "exposure — see full_model_exposure" if abl_arm in ("A0", "A1") else "")),
                    "full_model_exposure": None,
                    "refusal_scope": refusal,
                    "full_policy_check": fpc,
                    "repetitions": [{"arm": arm, "rep": x["rep"], "frozen_state": x["state"], "verdict": x["verdict"],
                                     "wall_s": x["wall_s"], "arrival_s": x["arrival"], "result_sha256": x["sha"]}
                                    for x in rr],
                    "repetitions_agree": rr[0]["verdict"] == rr[1]["verdict"] and rr[0]["arrival"] == rr[1]["arrival"],
                    "input_hashes": {"graph": res["identities"]["graph_path"]["sha256"],
                                     "hazard": res["identities"]["hazard_path"]["sha256"],
                                     "request": res["identities"]["request_path"]["sha256"]},
                    "input_hashes_canonical": {
                        "graph": res["identities"]["graph_path"].get("canonical_sha256"),
                        "hazard": res["identities"]["hazard_path"].get("canonical_sha256"),
                        "request": res["identities"]["request_path"].get("canonical_sha256")},
                    "source_records": [{"asset": pc.FINAL_ASSET if abl_arm is None else pc.ABLATION_ASSET,
                                        "path": x["path"], "sha256": x["sha"], "role": f"RESULT.json repetition {x['rep']}"}
                                       for x in rr],
                    "provenance": provenance(commit, generated_at, region=region, input_time=sset["input_time"],
                                             graph_id=g.revision, scenario_set_id=sset["scenario_set_id"],
                                             scenario_ids=sids, fire_input_type="recorded", policy=policy,
                                             evaluated_configuration=(policy == "full"),
                                             input_hashes={"graph": res["identities"]["graph_path"]["sha256"],
                                                           "hazard": res["identities"]["hazard_path"]["sha256"],
                                                           "request": res["identities"]["request_path"]["sha256"]},
                                             host=RECORDED_HOST, clock=CLOCK),
                }
                if abl_arm is None:
                    rec["source_records"].append({"asset": pc.FINAL_ASSET,
                                                  "path": rel_in_asset(pc.FINAL_ROOT / "INDEPENDENT_ROWS.csv", final_asset_parent),
                                                  "sha256": rows_sha, "role": "frozen outcome and complete-request wall_s"})
                    a4 = abl["A4"][0]
                    rec["ablation_full_policy_cross_check"] = {
                        "arm": "A4", "verdict": a4["verdict"], "arrival_s": a4["arrival"], "wall_s": a4["wall_s"],
                        "agrees_with_final_panel": a4["verdict"] == verdict and a4["arrival"] == arrival,
                        "note": "separate execution of the full policy in the ablation study (not the evaluated record)"}
                else:
                    rec["source_records"].append({"asset": pc.ABLATION_ASSET,
                                                  "path": rel_in_asset(pc.ABLATION_ROOT / "analysis" / "ROWS.csv", abl_asset_parent),
                                                  "sha256": abl_rows_sha, "role": "outcome, full-policy grade and complete-request wall_s"})
                    if r1["grade"] is not None:
                        rec["source_records"].append({"asset": pc.ABLATION_ASSET, "path": r1["grade_rel"],
                                                      "sha256": r1["grade_sha"], "role": "dual-policy grade (full-model check of this route)"})
                    if verdict == "checked_route" and r1["grade"] is not None:
                        rec["full_model_exposure"] = {
                            "scope": ("offline full-policy centre-model check of this route (ablation dual-policy "
                                      "grade, independent_centre; not charged to the request); dose includes incurred"),
                            "members": exposure_from_grade(r1["grade"], sids),
                            "independent_contact_status": r1["row"]["independent_contact_status"] or None,
                            "full_whole_status": r1["row"]["full_whole_status"] or None}
                    if r1["reviewed"] is not None:
                        rec["independent_refusal_status"] = r1["reviewed"].get("independent_refusal_status") or None
                    rec["input_hashes_note"] = ("ablation inputs: the arm's planning hazard/request copies "
                                                "(see POLICY_TRANSFORMS.json); the API request carries the original "
                                                "mission limits shown in request")
                out(FIXTURES / "records" / region / f"{case_id}__{policy}.json", rec)
                record_summary.append({"region": region, "case_id": case_id, "policy": policy, "verdict": verdict,
                                       "arrival_s": arrival, "compute_s": compute_s,
                                       "repetitions_agree": rec["repetitions_agree"]})

        # ---- footprints (recorded burned area at each recorded input time of the event)
        footprint_summary[region] = write_footprints(region, meta["expected_event"], g, sets_by_time, out)

        regions_out.append({
            "id": region, "name_ko": meta["name_ko"], "name_en": meta["name_en"],
            "event_id": meta["expected_event"], "fire_year": meta["fire_year"],
            "bbox": bbox, "graph_id": g.revision, "graph_sha256": g.sha256,
            "node_count": g.node_count, "edge_count": g.edge_count,
            "allowed_node_count": int(allowed.sum()),
            "crs": "EPSG:5179",
            "grid": {"x0": G["x0"], "y0": G["y0"], "resolution_m": int(G["resolution"]) if float(G["resolution"]).is_integer() else G["resolution"],
                     "width": W, "height": H},
            "input_times": input_times,
            "scenario_sets": scenario_sets,
        })
        region_notes[region] = {"graph_snapshot": pc.graph_snapshot_date(g),
                                "scenario_windows": {s["input_time"]: [0.0, s["horizon_s"]] for s in scenario_sets}}

    # ---- panel assertions
    full = [r for r in record_summary if r["policy"] == "full"]
    check(len(full) == 20, f"expected 20 full-policy missions, got {len(full)}")
    n_checked = sum(1 for r in full if r["verdict"] == "checked_route")
    n_refusal = sum(1 for r in full if r["verdict"] == "model_no_route")
    cand = final_review["by_arm"]["RDA_CAND"]
    check(n_checked == 15 and n_refusal == 5, f"full verdict split {n_checked}/{n_refusal} != 15/5")
    check(cand["both_repetitions_checked_route_missions"] == n_checked
          and cand["both_repetitions_scoped_refusal_missions"] == n_refusal, "FINAL_REVIEW.json split mismatch")
    check(all(r["repetitions_agree"] for r in full), "full-policy repetitions disagree")
    check(len(record_summary) == 100, f"expected 100 records, got {len(record_summary)}")

    region_list = {"regions": regions_out,
                   "provenance": provenance(commit, generated_at, input_hashes=list_input_hashes, scenario_ids=[],
                                            allowed_node_rule=ALLOWED_COUNT_RULE)}
    out(FIXTURES / "regions.json", region_list, compact=False)

    # ---- manifest
    fixture_files = sorted(p for p in written if FIXTURES in p.parents)
    public_files = sorted(p for p in written if PUBLIC_REGIONS in p.parents)
    manifest = {
        "generated_at": generated_at,
        "generator": "planner/tools/build_fixtures.py",
        "git_commit": commit,
        "sources": pc.RELEASE_ASSETS,
        "conventions": {
            "grid_orientation": {
                "summary": ("Graph edge segments[].cell and HAZARD.json member arrays use cell = row*width + col "
                            "with row 0 at the SOUTH edge (grid.y0) and col 0 at grid.x0. constructed_arrays.npz and "
                            "the event export FORECAST_<t>.npz are native north-up rasters (row 0 at the north edge, "
                            "affine [375,0,x0,0,-375,y_top]); native row = height-1-row. HAZARD row_reversal: true "
                            "denotes exactly this reversal. ForecastCell row/col/cell/id use the south-up graph "
                            "convention; polygons are the cell's EPSG:5179 square [x0+col*375, y0+row*375] → WGS84."),
                "verified": True,
                "edge_segment_checks": orientation,
                "packet_export_checks": packet_checks,
            },
            "forecast_cell": {"p_new_burn_1h": "mask__constructed_probability (6 significant digits)",
                              "valid": "mask__probability_valid_native (false = policy zero, p = 0)",
                              "burning_now": "current_active", "known_burned": "mask__known_burned",
                              "coordinates": "WGS84, 6 decimals, ring SW→SE→NE→NW→SW"},
            "times": "seconds after input_time (UTC); route times_s absolute, one per vertex",
            "verdict_mapping": {"CHECKED_CENTRE_OPTIMUM/CHECKED_ROUTE": "checked_route",
                                "CERTIFIED_CENTRE_REFUSAL (PROVEN_INFEASIBLE, complete refusal certificate)": "model_no_route",
                                "anything else": "unresolved (TIMEOUT for worker MAX_LABELS/timeout, CHECK_FAILED for end-check rejection, OTHER otherwise)",
                                "ablation": "own_outcome CHECKED_ROUTE + CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN → checked_route; SCOPED_REFUSAL + FULL_MODEL_REFUSAL_PROVEN → model_no_route"},
            "policy_mapping_verified_from": "routing_final_input_ablation_20261016_v1/POLICY_TRANSFORMS.json enabled constraint sets",
            "policy_mapping": arm_map,
            "allowed_nodes": ALLOWED_RULE,
            "records": "full = final panel RDA_CAND repetition 1 (repetition 2 recorded); other policies = ablation repetition 1 (repetition 2 recorded)",
        },
        "panel_check": {"full_checked_route": n_checked, "full_model_no_route": n_refusal,
                        "final_review_RDA_CAND": {k: cand[k] for k in ("both_repetitions_checked_route_missions",
                                                                       "both_repetitions_scoped_refusal_missions")},
                        "repetitions_agree_full": True},
        "regions": region_notes,
        "records": record_summary,
        "footprints": footprint_summary,
        "files": [{"path": str(p.relative_to(FIXTURES)), "sha256": pc.sha256_file(p), "bytes": p.stat().st_size}
                  for p in fixture_files],
        "public_files": [{"path": str(p.relative_to(pc.PLANNER)), "sha256": pc.sha256_file(p), "bytes": p.stat().st_size}
                         for p in public_files],
    }
    manifest["total_fixture_bytes"] = sum(f["bytes"] for f in manifest["files"])
    pc.write_json(FIXTURES / "MANIFEST.json", manifest)
    print("fixtures: %d files, %.2f MB; public footprints %d files, %.2f MB" % (
        len(manifest["files"]), manifest["total_fixture_bytes"] / 1e6, len(manifest["public_files"]),
        sum(f["bytes"] for f in manifest["public_files"]) / 1e6))
    print("full policy: %d checked_route, %d model_no_route; repetitions agree" % (n_checked, n_refusal))
    return manifest


def write_footprints(region: str, event: str, g: pc.Graph, sets_by_time: dict, out) -> list:
    x0, y0, x1, y1 = g.grid_rect()
    window = box(x0 - FOOTPRINT_PAD_M, y0 - FOOTPRINT_PAD_M, x1 + FOOTPRINT_PAD_M, y1 + FOOTPRINT_PAD_M)
    exp_dir = pc.INPUTS_ROOT / "latest_inputs_try02" / "exports" / event
    feats, summary = [], []
    for npz in sorted(exp_dir.glob("FORECAST_*.npz")):
        t = npz.stem.split("_", 1)[1]
        with np.load(npz, allow_pickle=False) as ex:
            A = ex["affine_transform"]
            mask = ex["source_burned_area_valid"] & (ex["source_burned_area"] > 0)
            check(str(ex["contract__event_id"]) == event, f"{npz}: event id")
        rows, cols = np.nonzero(mask)
        cells = [box(A[2] + c * A[0], A[5] + (r + 1) * A[4], A[2] + (c + 1) * A[0], A[5] + r * A[4])
                 for r, c in zip(rows, cols)]
        geom = unary_union(cells).intersection(window) if cells else None
        if geom is None or geom.is_empty:
            summary.append({"input_time": pc.iso_z(t), "area_km2": 0.0, "written": False,
                            "reason": "no recorded burned cells inside the padded region window"})
            continue
        geom = geom.simplify(0)  # drops collinear vertices only (tolerance 0)
        area_km2 = geom.area / 1e6

        def tr(ring):
            xs, ys = np.asarray(ring.coords).T
            lon, lat = pc.to_wgs84(xs, ys)
            return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat)]

        polys = [geom] if geom.geom_type == "Polygon" else [p for p in geom.geoms if p.geom_type == "Polygon"]
        coords = [[tr(p.exterior)] + [tr(i) for i in p.interiors] for p in polys]
        gj = {"type": "MultiPolygon", "coordinates": coords} if len(coords) > 1 else {"type": "Polygon", "coordinates": coords[0]}
        feats.append({"type": "Feature", "geometry": gj, "properties": {
            "input_time": pc.iso_z(t), "area_km2": round(area_km2, 3),
            "note": "recorded burned footprint at input time (preset for user-drawn zones only)",
            "event_id": event, "region_scenario_input_time": t in sets_by_time,
            "source": f"latest_inputs_try02/exports/{event}/{npz.name} source_burned_area > 0 (valid cells), "
                      "375 m cells dissolved, clipped to the region grid padded 2 km",
            "source_sha256": pc.sha256_file(npz), "cells": int(len(cells))}})
        summary.append({"input_time": pc.iso_z(t), "area_km2": round(area_km2, 3), "written": True, "cells": int(len(cells))})
    out(PUBLIC_REGIONS / region / "footprints.geojson",
        {"type": "FeatureCollection", "region_id": region, "features": feats,
         "notes": ["Recorded burned footprint (source_burned_area) of the parent event at each recorded input time; "
                   "presets for user-drawn spread zones only, never a forecast."]})
    return summary


if __name__ == "__main__":
    if sys.argv[1:] == ["--nodes-only"]:
        build_nodes_only()
    elif sys.argv[1:]:
        raise SystemExit("usage: python3 planner/tools/build_fixtures.py [--nodes-only]")
    else:
        build()
