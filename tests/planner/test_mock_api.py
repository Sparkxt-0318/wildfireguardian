"""Tests of the MOCK Route-Check API (planner/mock_api/server.py) against the official contract copy.

Every response body is validated with jsonschema against planner/contract/wfg_api_v1.yaml (OpenAPI 3.1 component
schemas resolved through a referencing Registry). Two fixture modes:

(a) a synthetic, obviously test-only fixture tree ("test:..." ids) written to a temporary directory following
    planner/docs/ARCHITECTURE.md section 4.1, exercising every endpoint, validation errors, snapping, the job state
    machine, the matching rule (section 5.1), dispatch aggregation and exports;
(b) the real recorded fixtures in planner/mock_api/fixtures/ (only when its MANIFEST.json exists): every recorded
    execution replays its recorded verdict for its exact request, and a request the record does not cover is unresolved.

The server runs in-process on 127.0.0.1 (port 0) in a background thread; nothing is imported from routing or
forecasting code.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import jsonschema
import pytest
import yaml
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = ROOT / "planner" / "mock_api" / "server.py"
# WFG_PLANNER_CONTRACT lets a newer contract (e.g. `git show origin/feat/api:contracts/wfg_api_v1.yaml`) be tried before
# planner/contract/ is refreshed; by default the official copy is used.
CONTRACT_PATH = Path(os.environ.get("WFG_PLANNER_CONTRACT") or ROOT / "planner" / "contract" / "wfg_api_v1.yaml")
REAL_FIXTURES = ROOT / "planner" / "mock_api" / "fixtures"


def _load_server_module():
    spec = importlib.util.spec_from_file_location("wfg_mock_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wfg_mock_server"] = mod
    spec.loader.exec_module(mod)
    return mod


S = _load_server_module()

# ------------------------------------------------------------------------------------------------ contract validation
SPEC = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))   # the first-line comment is ignored by YAML
URN = "urn:wfg:planner-contract"
REGISTRY = Registry().with_resource(URN, Resource.from_contents(SPEC, default_specification=DRAFT202012))
_VALIDATORS: dict = {}


def validate(instance, component: str) -> None:
    v = _VALIDATORS.get(component)
    if v is None:
        v = jsonschema.Draft202012Validator({"$ref": "%s#/components/schemas/%s" % (URN, component)}, registry=REGISTRY)
        _VALIDATORS[component] = v
    errors = sorted(v.iter_errors(instance), key=lambda e: list(e.absolute_path))
    assert not errors, "%s invalid:\n" % component + "\n".join(
        "  %s: %s" % ("/".join(map(str, e.absolute_path)), e.message[:300]) for e in errors[:10])


def assert_iso_z(value) -> None:
    assert isinstance(value, str) and value.endswith("Z"), value
    dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def check_timestamps(job: dict) -> None:
    assert_iso_z(job["created_at"])
    for k in ("started_at", "finished_at"):
        if job[k] is not None:
            assert_iso_z(job[k])
    res = job.get("result")
    if res:
        assert_iso_z(res["provenance"]["generated_at"])


# ------------------------------------------------------------------------------------------------ HTTP client
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never route 127.0.0.1 through a proxy


VALIDATED: dict = {}      # component -> number of response bodies validated (sanity check at the end)


def component_for(method: str, path: str, status: int):
    """Contract component that a mock response body must match (None: not a contract endpoint)."""
    p = path.split("?", 1)[0].rstrip("/")
    if status >= 400:
        return "Error"
    segs = [s for s in p.split("/") if s]
    if not segs or segs[0] != "v1":
        return None
    rest = segs[1:]
    if method == "GET" and rest == ["health"]:
        return "Health"
    if method == "GET" and rest == ["regions"]:
        return "RegionList"
    if method == "GET" and len(rest) == 3 and rest[0] == "regions" and rest[2] == "forecast":
        return "ForecastCollection"
    if method == "POST" and rest in (["route-checks"], ["dispatch-plans"]) and status == 202:
        return "JobAccepted"
    if method == "GET" and len(rest) == 2 and rest[0] == "route-checks":
        return "RouteCheckJob"
    if method == "GET" and len(rest) == 3 and rest[0] == "route-checks" and rest[2] == "export":
        return "RouteExportCollection"
    if method == "GET" and len(rest) == 2 and rest[0] == "dispatch-plans":
        return "DispatchPlanJob"
    return None


class Client:
    def __init__(self, base: str):
        self.base = base

    def raw(self, method: str, path: str, body=None, data: bytes | None = None, headers=None):
        if data is None and body is not None:
            data = json.dumps(body).encode("utf-8")
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        url = self.base + path
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with _OPENER.open(req, timeout=60) as r:
                out = r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
        except urllib.error.HTTPError as e:
            out = e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
        # every JSON body the mock sends is validated against the contract component of its endpoint
        status, hdrs, payload = out
        ctype = hdrs.get("content-type", "")
        if payload and ("json" in ctype):
            comp = component_for(method, urllib.parse.urlsplit(url).path, status)
            if comp is not None:
                validate(json.loads(payload), comp)
                VALIDATED[comp] = VALIDATED.get(comp, 0) + 1
        return out

    def call(self, method: str, path: str, body=None, **kw):
        status, headers, data = self.raw(method, path, body, **kw)
        return status, (json.loads(data) if data else None), headers

    def get(self, path: str):
        return self.call("GET", path)

    def post(self, path: str, body=None, **kw):
        return self.call("POST", path, body, **kw)

    def wait(self, path: str, timeout: float = 10.0) -> dict:
        t_end = time.monotonic() + timeout
        while True:
            status, job, _ = self.get(path)
            assert status == 200, job
            if job["status"] in ("done", "failed"):
                return job
            assert time.monotonic() < t_end, "job %s did not finish" % path
            time.sleep(0.02)

    def check(self, body: dict) -> dict:
        """POST a route check, wait for it and return the validated RouteCheckJob."""
        status, acc, headers = self.post("/route-checks", body)
        assert status == 202, acc
        validate(acc, "JobAccepted")
        assert headers.get("location") == "/v1/route-checks/%s" % acc["job_id"]
        job = self.wait("/route-checks/%s" % acc["job_id"])
        validate(job, "RouteCheckJob")
        check_timestamps(job)
        assert job["status"] == "done" and job["error"] is None
        assert job["snap"] == acc["snap"]
        return job

    def plan(self, body: dict) -> dict:
        status, acc, _ = self.post("/dispatch-plans", body)
        assert status == 202, acc
        validate(acc, "JobAccepted")
        assert acc["kind"] == "dispatch_plan"
        job = self.wait("/dispatch-plans/%s" % acc["job_id"])
        validate(job, "DispatchPlanJob")
        check_timestamps(job)
        assert job["status"] == "done"
        return job


def start_server(fixtures_dir, **kw):
    api = S.MockApi(fixtures_dir, quiet=True, **kw)
    httpd = S.make_server(api, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return api, httpd, Client("http://127.0.0.1:%d/v1" % httpd.server_address[1])


def stop_server(httpd) -> None:
    httpd.shutdown()
    httpd.server_close()


def expect_error(status_body_headers, status: int, code: str) -> dict:
    st, body, _ = status_body_headers
    assert st == status, (st, body)
    validate(body, "Error")
    assert body["error"]["code"] == code, body
    return body["error"]


# ================================================================================================ (a) synthetic fixtures
REGION = "test:alpha"
T0, TAG0 = "2025-01-01T00:00:00Z", "20250101T000000Z"
T1, TAG1 = "2025-01-01T03:00:00Z", "20250101T030000Z"
SSID0, SSID1 = "test:ss:%s" % TAG0, "test:ss:%s" % TAG1
SIDS0 = ["%s:%d" % (SSID0, i) for i in range(4)]
SIDS1 = ["%s:%d" % (SSID1, i) for i in range(4)]
BBOX = [127.99, 35.99, 128.03, 36.02]
NODES = {  # id: (lon, lat, allowed)
    "test:n1": (128.000, 36.000, 1),
    "test:n2": (128.010, 36.000, 1),
    "test:n3": (128.020, 36.000, 1),
    "test:n4": (128.002, 36.001, 0),   # not allowed, ~212 m from test:n1
    "test:n5": (128.000, 36.008, 1),
    "test:n6": (128.020, 36.008, 1),
    "test:n7": (128.015, 36.015, 0),   # outside the allowed rule but a recorded mission endpoint
}
EXPOSURE = [{"scenario_id": s, "peak_kw_m2": 0.001 * (i + 1), "dose_kj_m2": 0.01 * (i + 1), "contact": False}
            for i, s in enumerate(SIDS0)]


def ll(node: str):
    lon, lat, _ = NODES[node]
    return [lon, lat]


def make_record(case, policy, start, dest, verdict, *, depart=0, dwell=120, window=(0, 3600), peak=10, dose=100,
                incurred=0, outcome=None, route=None, fme=None, fpc=None, source_arm=None):
    o = {"verdict": verdict, "reason_code": None, "raw_status": None, "raw_reason": None, "frozen_state": None,
         "departure_s": depart, "arrival_s": None, "lower_bound_L_s": None, "dwell_end_s": None, "compute_s": 1.0,
         "within_budget": True}
    o.update(outcome or {})
    feature = None
    if route is not None:   # route = [(node, t), ...] ; node_ids per vertex unless route["distinct"]
        pts, distinct = route if isinstance(route, tuple) else (route, False)
        ids = [n for n, _ in pts]
        if distinct:
            ids = [n for k, n in enumerate(ids) if k == 0 or n != ids[k - 1]]
        feature = {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [ll(n) for n, _ in pts]},
                   "properties": {"times_s": [t for _, t in pts], "node_ids": ids, "segment_count": len(pts) - 1,
                                  "edge_ids": ["test:e%d" % k for k in range(len(pts) - 1)],
                                  "waits": [{"node_id": pts[k][0], "from_s": pts[k - 1][1], "to_s": pts[k][1]}
                                            for k in range(1, len(pts)) if pts[k][0] == pts[k - 1][0]],
                                  "length_m": 1000.0 * (len(pts) - 1)}}
    return {
        "case_id": case, "region_id": REGION, "policy": policy,
        "source_arm": source_arm or ("RDA_CAND" if policy == "full" else "A0"), "repetition": 1,
        "scenario_set_id": SSID0, "input_time": T0, "scenario_ids": SIDS0,
        "request": {"origin_node": start, "destination_node": dest, "depart_offset_s": depart, "dwell_s": dwell,
                    "destination_window": list(window), "horizon_s": 3600,
                    "limits": {"peak_kw_m2": peak, "dose_kj_m2": dose},
                    "incurred_dose_kj_m2": incurred, "incurred_per_member": {s: incurred for s in SIDS0}},
        "outcome": o,
        "route": feature,
        "exposure": EXPOSURE if verdict == "checked_route" else [],
        "full_model_exposure": fme,
        "refusal_scope": "test:scope" if verdict == "model_no_route" else None,
        "full_policy_check": fpc or {"pass": True, "failure_components": None},
        "repetitions": [{"arm": "RDA_CAND", "rep": 1, "frozen_state": "TEST", "verdict": verdict,
                         "wall_s": o["compute_s"], "arrival_s": o["arrival_s"]}],
        "input_hashes": {"graph": "test-graph-hash", "hazard": "test-hazard-hash", "request": "test-request-%s" % case},
        "source_records": [{"asset": "test-only", "path": "test/%s/RESULT.json" % case, "sha256": "0" * 64}],
    }


def checked(arrival, lb, compute):
    return {"raw_status": "CHECKED_ROUTE", "raw_reason": "TEST_CHECKED", "arrival_s": arrival, "lower_bound_L_s": lb,
            "dwell_end_s": arrival + 120, "compute_s": compute}


NO_ROUTE_OUTCOME = {"raw_status": "CERTIFIED_CENTRE_REFUSAL", "raw_reason": "TEST_REFUSAL", "departure_s": None,
                    "lower_bound_L_s": None, "compute_s": 3.2}

RECORDS = [
    # case1 full: n1 -> n2 (wait 60 s) -> n3, departs 0, arrives 260 (node_ids per vertex)
    make_record("test:case1", "full", "test:n1", "test:n3", "checked_route",
                outcome=checked(260, 250, 6.5),
                route=[("test:n1", 0), ("test:n2", 100), ("test:n2", 160), ("test:n3", 260)]),
    # case1 travel_only: direct-ish route, node_ids distinct-only, full-policy check fails
    make_record("test:case1", "travel_only", "test:n1", "test:n3", "checked_route", outcome=checked(200, 200, 0.4),
                route=(([("test:n1", 0), ("test:n2", 100), ("test:n2", 110), ("test:n3", 200)]), True),
                fme={"scope": "test full-model check", "members": [dict(m, contact=True, peak_kw_m2=12.5) for m in EXPOSURE],
                     "independent_contact_status": "DEFINITE_CONTACT", "full_whole_status": "DEFINITE_REJECT"},
                fpc={"pass": False, "failure_components": ["FLAME", "PEAK"]}),
    make_record("test:case2", "full", "test:n2", "test:n1", "model_no_route", depart=600, window=(0, 1800), incurred=5.0,
                outcome=NO_ROUTE_OUTCOME),
    make_record("test:case3", "full", "test:n3", "test:n2", "unresolved",
                outcome={"reason_code": "TIMEOUT", "raw_status": "TIMEOUT", "raw_reason": "DEADLINE_STOP",
                         "compute_s": 30.4, "within_budget": False}),
    make_record("test:case4", "full", "test:n1", "test:n3", "checked_route", depart=600, outcome=checked(900, 880, 7.0),
                route=[("test:n1", 600), ("test:n2", 750), ("test:n3", 900)]),
    make_record("test:case5", "full", "test:n2", "test:n3", "checked_route", outcome=checked(150, 150, 5.0),
                route=[("test:n2", 0), ("test:n3", 150)]),
    make_record("test:case6", "full", "test:n1", "test:n2", "checked_route", outcome=checked(100, 100, 4.0),
                route=[("test:n1", 0), ("test:n2", 100)]),
    make_record("test:case7", "full", "test:n5", "test:n3", "model_no_route", outcome=NO_ROUTE_OUTCOME),
    make_record("test:case8", "full", "test:n5", "test:n3", "model_no_route", depart=600, outcome=NO_ROUTE_OUTCOME),
]


def by_case(case, policy="full") -> dict:
    return next(r for r in RECORDS if r["case_id"] == case and r["policy"] == policy)


def forecast_doc():
    feats = []
    cells = [(0, 0, 0.25, True, False), (0, 1, 0.0, True, True), (1, 0, 0.0, True, False), (1, 1, None, False, False)]
    for row, col, p, valid, burning in cells:
        x0, y0 = 128.0 + col * 0.004, 36.0 + row * 0.004
        ring = [[x0, y0], [x0 + 0.004, y0], [x0 + 0.004, y0 + 0.004], [x0, y0 + 0.004], [x0, y0]]
        feats.append({"type": "Feature", "id": "r%dc%d" % (row, col), "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"row": row, "col": col, "p_new_burn_1h": p, "valid": valid, "burning_now": burning,
                                     "cell": row * 2 + col, "known_burned": False}})
    return {"type": "FeatureCollection", "region": REGION, "input_time": T0, "bbox": BBOX, "features": feats,
            "provenance": {"api_version": "1.0.0", "package": "wfg_latest", "package_version": "1.0.0", "kit": "v3",
                           "checkpoint": S.CHECKPOINT, "git_commit": "test", "input_hashes": {"forecast": "test-hash"},
                           "scenario_ids": SIDS0, "region": REGION, "input_time": T0}}


def write_synthetic_fixtures(root: Path) -> Path:
    def w(rel, obj):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    region = {"id": REGION, "name_ko": "테스트", "name_en": "Test", "event_id": "test:event", "fire_year": 2025,
              "bbox": BBOX, "graph_id": "test:graph", "graph_sha256": "test-graph-hash", "node_count": len(NODES),
              "edge_count": 0, "allowed_node_count": sum(a for _, _, a in NODES.values()), "crs": "EPSG:5179",
              "grid": {"x0": 0.0, "y0": 0.0, "resolution_m": 375, "width": 2, "height": 2},
              "input_times": [T0, T1],
              "scenario_sets": [
                  {"scenario_set_id": SSID0, "input_time": T0, "scenario_ids": SIDS0, "horizon_s": 3600.0,
                   "hazard_sha256": "test-hazard-hash"},
                  {"scenario_set_id": SSID1, "input_time": T1, "scenario_ids": SIDS1, "horizon_s": 3600.0,
                   "hazard_sha256": "test-hazard-hash-1"}]}
    w("regions.json", {"regions": [region], "provenance": {
        "api_version": "1.0.0", "package": "wfg_latest", "package_version": "1.0.0", "kit": "v3",
        "checkpoint": S.CHECKPOINT, "git_commit": "test", "input_hashes": {"graph": "test-graph-hash"},
        "scenario_ids": SIDS0 + SIDS1}})
    w("forecast/%s/%s.json" % (REGION, TAG0), forecast_doc())
    fc1 = forecast_doc()
    fc1["input_time"] = fc1["provenance"]["input_time"] = T1
    w("forecast/%s/%s.json" % (REGION, TAG1), fc1)
    ids = list(NODES)
    w("nodes/%s.json" % REGION, {"ids": ids, "lon": [NODES[i][0] for i in ids], "lat": [NODES[i][1] for i in ids],
                                 "allowed": [NODES[i][2] for i in ids], "allowed_rule": "test rule",
                                 "recorded_mission_nodes": [{"node_id": "test:n7", "in_largest_scc": False}]})
    for r in RECORDS:
        w("records/%s/%s__%s.json" % (REGION, r["case_id"], r["policy"]), r)
    files = []
    for p in sorted(root.rglob("*.json")):
        b = p.read_bytes()
        files.append({"path": p.relative_to(root).as_posix(), "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)})
    w("MANIFEST.json", {"generated_at": "2025-01-01T00:00:00Z", "generator": "tests/planner/test_mock_api.py (test-only)",
                        "sources": [], "conventions": {}, "files": files})
    return root


@pytest.fixture(scope="module")
def synth_dir(tmp_path_factory):
    return write_synthetic_fixtures(tmp_path_factory.mktemp("mock_fixtures"))


@pytest.fixture(scope="module")
def fast(synth_dir):
    api, httpd, client = start_server(synth_dir, queued_s=0.01, done_s=0.05)
    yield client
    stop_server(httpd)


@pytest.fixture(scope="module")
def slow(synth_dir):
    """Default state-machine timing (queued < 0.15 s, running < 0.6 s)."""
    api, httpd, client = start_server(synth_dir)
    yield client
    stop_server(httpd)


def body_for(rec: dict, **over) -> dict:
    q = rec["request"]
    b = {"region": rec["region_id"], "input_time": rec["input_time"], "start": {"node_id": q["origin_node"]},
         "destination": {"node_id": q["destination_node"]}, "depart_offset_s": q["depart_offset_s"],
         "dwell_s": q["dwell_s"], "destination_window": q["destination_window"], "policy": rec["policy"],
         "limits": dict(q["limits"]), "incurred_dose_kj_m2": q["incurred_dose_kj_m2"],
         "fire_input": {"type": "recorded", "scenario_set_id": rec["scenario_set_id"]}}
    for k, v in over.items():
        if v is None:
            b.pop(k, None)
        else:
            b[k] = v
    return b


def zone(coords, h=5):
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": {"arrival_h_max": h}}


ZONE_IN = zone([[128.0, 36.0], [128.01, 36.0], [128.01, 36.01], [128.0, 36.0]])
ZONE_OUT = zone([[129.0, 37.0], [129.01, 37.0], [129.01, 37.01], [129.0, 37.0]])


def spread(features, **over):
    f = {"type": "spread_zones", "zones": {"type": "FeatureCollection", "features": features}, "issued_at": T0}
    f.update(over)
    return f


# ------------------------------------------------------------------------------------------------ contract coverage
ANNOTATIONS = {"description", "examples", "default", "discriminator", "title", "summary"}


def _strip(node):
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k not in ANNOTATIONS}
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


def _keywords(node, out: set):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "properties":
                for sub in v.values():
                    _keywords(sub, out)
            else:
                out.add(k)
                _keywords(v, out)
    elif isinstance(node, list):
        for v in node:
            _keywords(v, out)


def test_request_schemas_mirror_contract():
    comps = SPEC["components"]["schemas"]
    for name, mine in S.REQUEST_SCHEMAS.items():
        assert name in comps, name
        assert _strip(comps[name]) == mine, "server.REQUEST_SCHEMAS[%r] differs from the contract" % name
        used: set = set()
        _keywords(mine, used)
        assert used <= S.SUPPORTED_KEYWORDS, used - S.SUPPORTED_KEYWORDS
    # every request schema the request bodies reference is mirrored
    refs: set = set()

    def walk(n):
        if isinstance(n, dict):
            if "$ref" in n:
                refs.add(n["$ref"].rsplit("/", 1)[1])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    for name in ("RouteCheckRequest", "DispatchPlanRequest"):
        walk(comps[name])
    assert refs <= set(S.REQUEST_SCHEMAS), refs - set(S.REQUEST_SCHEMAS)
    assert SPEC["info"]["version"] == S.API_VERSION
    assert set(comps["Policy"]["enum"]) == set(S.POLICIES)
    assert set(comps["ReasonCode"]["enum"]) - {None} == set(S.REASON_CODES)


def test_every_contract_path_is_served(fast):
    contract_ops = {(m.upper(), "/v1" + p) for p, item in SPEC["paths"].items() for m in item if m in ("get", "post")}
    mock_ops = {(m, p) for m, p, _, _ in S.ENDPOINTS}
    assert contract_ops == mock_ops
    status, index, _ = fast.get("")
    assert status == 200 and index["mode"] == "mock" and index["mock"] is True
    assert {(e["method"], e["path"]) for e in index["endpoints"]} == contract_ops
    for method, path in sorted(contract_ops):
        concrete = path.replace("{region}", REGION).replace("{job_id}", "rc_doesnotexist")[3:]
        st, _, _ = fast.raw(method, concrete, body={} if method == "POST" else None)
        assert st not in (404, 405) or "{job_id}" in path, (method, path, st)


def test_health(fast):
    status, h, headers = fast.get("/health")
    assert status == 200
    validate(h, "Health")
    assert h["status"] == "ok", h["issues"]
    assert h["mode"] == "mock" and h["mock"] is True
    assert h["regions"] == [REGION] and h["workers"] == 1 and h["issues"] == []
    assert h["checkpoint"] == S.CHECKPOINT and h["package"] == "wfg_latest" and h["kit"] == "v3"
    assert h["fixtures"]["records"] == len(RECORDS)
    assert headers["access-control-allow-origin"] == "*"


def test_health_degraded_without_fixtures(tmp_path):
    api, httpd, client = start_server(tmp_path / "missing")
    try:
        status, h, _ = client.get("/health")
        validate(h, "Health")
        assert h["status"] == "degraded" and h["issues"] and h["regions"] == []
        st, regions, _ = client.get("/regions")
        assert st == 200
        validate(regions, "RegionList")
        assert regions["regions"] == [] and regions["provenance"]["mock"] is True
        rec = by_case("test:case1")
        expect_error(client.post("/route-checks", body_for(rec)), 503, "DATA_UNAVAILABLE")
    finally:
        stop_server(httpd)


def test_health_degraded_on_bad_record(tmp_path):
    root = write_synthetic_fixtures(tmp_path / "fx")
    (root / "records" / REGION / "test:broken__full.json").write_text("{not json", encoding="utf-8")
    api = S.MockApi(root, quiet=True)
    h = api.health()
    validate(h, "Health")
    assert h["status"] == "degraded"
    assert any("test:broken__full.json" in i for i in h["issues"])
    assert len(api.fx.records) == len(RECORDS)


def test_forecast_fixture_missing(tmp_path):
    root = write_synthetic_fixtures(tmp_path / "fx")
    (root / "forecast" / REGION / ("%s.json" % TAG1)).unlink()
    api = S.MockApi(root, quiet=True)
    assert api.health()["status"] == "degraded"
    assert any("forecast fixtures missing" in i and T1 in i for i in api.fx.issues)
    r = api.handle("GET", "/v1/regions/%s/forecast?input_time=%s" % (REGION, T1))
    body = json.loads(r.body)
    validate(body, "Error")
    assert r.status == 422 and body["error"]["code"] == "FORECAST_UNAVAILABLE"
    assert body["error"]["details"]["available"] == [T0]


def test_regions(fast):
    status, doc, _ = fast.get("/regions")
    assert status == 200
    validate(doc, "RegionList")
    assert [r["id"] for r in doc["regions"]] == [REGION]
    assert doc["regions"][0]["fire_year"] == 2025
    assert doc["provenance"]["mock"] is True


# ------------------------------------------------------------------------------------------------ forecast
def test_forecast_full_and_only_nonzero(fast):
    for t in (T0, TAG0, "2025-01-01T00:00:00+00:00"):
        status, headers, raw = fast.raw("GET", "/regions/%s/forecast?input_time=%s" % (REGION, t.replace("+", "%2B")))
        assert status == 200, raw
        assert headers["content-type"].startswith("application/geo+json")
        doc = json.loads(raw)
        validate(doc, "ForecastCollection")
        assert len(doc["features"]) == 4
        assert doc["provenance"]["mock"] is True
    status, doc, _ = fast.get("/regions/%s/forecast?input_time=%s&only_nonzero=true" % (REGION, T0))
    validate(doc, "ForecastCollection")
    assert [(f["properties"]["row"], f["properties"]["col"]) for f in doc["features"]] == [(0, 0), (0, 1)]
    status, doc, _ = fast.get("/regions/%s/forecast?input_time=%s&only_nonzero=false" % (REGION, T0))
    assert len(doc["features"]) == 4


def test_forecast_errors(fast):
    err = expect_error(fast.get("/regions/test:nowhere/forecast?input_time=%s" % T0), 404, "UNKNOWN_REGION")
    assert err["details"]["available"] == [REGION]
    err = expect_error(fast.get("/regions/%s/forecast?input_time=2025-01-02T00:00:00Z" % REGION), 404, "INPUT_TIME_UNAVAILABLE")
    assert err["details"]["available"] == [T0, T1]
    status, doc, _ = fast.get("/regions/%s/forecast?input_time=%s" % (REGION, T1))
    assert status == 200 and doc["input_time"] == T1
    expect_error(fast.get("/regions/%s/forecast" % REGION), 422, "VALIDATION_ERROR")
    expect_error(fast.get("/regions/%s/forecast?input_time=yesterday" % REGION), 422, "INVALID_INPUT_TIME")
    expect_error(fast.get("/regions/%s/forecast?input_time=2025-01-01T00:30:00Z" % REGION), 422, "INVALID_INPUT_TIME")
    expect_error(fast.get("/regions/%s/forecast?input_time=%s&only_nonzero=maybe" % (REGION, T0)), 422, "VALIDATION_ERROR")


# ------------------------------------------------------------------------------------------------ route checks
def test_exact_match_returns_recorded_checked_route(fast):
    rec = by_case("test:case1")
    job = fast.check(body_for(rec))
    res = job["result"]
    o = rec["outcome"]
    assert res["verdict"] == "checked_route" and res["reason_code"] is None
    for k in ("raw_status", "raw_reason", "departure_s", "arrival_s", "lower_bound_L_s", "dwell_end_s", "compute_s",
              "within_budget"):
        assert res[k] == o[k], k
    assert res["route"] == rec["route"]
    assert [{k: e[k] for k in ("scenario_id", "peak_kw_m2", "dose_kj_m2", "contact")} for e in res["exposure"]] == EXPOSURE
    assert res["notes"][0] == "MOCK: recorded result of case test:case1 (RDA_CAND rep 1) served without recomputation"
    assert res["policy"] == "full" and res["assumptions"] is None and res["independent_check"] is None
    assert res["limits"] == {"peak_kw_m2": 10, "dose_kj_m2": 100, "incurred_dose_kj_m2": 0}
    p = res["provenance"]
    assert p["mock"] is True and p["evaluated_configuration"] is True
    assert p["host"] == {"recorded": True, "machine": "Apple M5 Pro", "os": "macOS (native)"}
    assert p["clock"] == "complete-request wall time recorded on the native campaign host"
    assert p["input_hashes"] == rec["input_hashes"]
    assert p["scenario_ids"] == SIDS0 and p["scenario_set_id"] == SSID0
    assert p["region"] == REGION and p["input_time"] == T0 and p["graph_id"] == "test:graph"
    assert p["fire_input_type"] == "recorded" and p["policy"] == "full" and p["approximation"] is None
    assert p["recorded_mission_match"] == "test:case1"
    assert p["git_commit"] and p["checkpoint"] == S.CHECKPOINT
    assert job["snap"]["start"] == {"node_id": "test:n1", "distance_m": 0.0, "lon": 128.0, "lat": 36.0, "input": "node_id"}


def test_defaults_restate_recorded_request(fast):
    rec = by_case("test:case1")
    body = {"region": REGION, "input_time": TAG0, "start": {"node_id": "test:n1"}, "destination": {"node_id": "test:n3"},
            "fire_input": {"type": "recorded", "scenario_set_id": SSID0}}
    job = fast.check(body)
    assert job["result"]["verdict"] == "checked_route"
    assert job["result"]["arrival_s"] == rec["outcome"]["arrival_s"]
    r = job["request"]
    assert (r["depart_offset_s"], r["dwell_s"], r["policy"], r["limits"], r["incurred_dose_kj_m2"], r["input_time"]) == \
           (0, 120, "full", {"peak_kw_m2": 10, "dose_kj_m2": 100}, 0, T0)


def test_lonlat_snaps_to_recorded_node(fast):
    # ~50 m north of test:n1
    start = {"lon": 128.0, "lat": 36.0 + 50 / 111195.0}
    job = fast.check(body_for(by_case("test:case1"), start=start))
    snap = job["snap"]["start"]
    assert snap["node_id"] == "test:n1" and snap["input"] == "lonlat"
    assert 49.0 < snap["distance_m"] < 51.0
    assert job["result"]["verdict"] == "checked_route"
    # a point closest to the not-allowed test:n4 snaps to an allowed node instead
    acc = fast.post("/route-checks", body_for(by_case("test:case1"), start={"lon": 128.0015, "lat": 36.0008}))[1]
    assert acc["snap"]["start"]["node_id"] == "test:n1" and 150 < acc["snap"]["start"]["distance_m"] < 175


@pytest.mark.parametrize("override, field", [
    ({"depart_offset_s": 60}, "depart_offset_s"),
    ({"dwell_s": 60}, "dwell_s"),
    ({"destination_window": [0, 1800]}, "destination_window"),
    ({"policy": "flame_only"}, "policy"),
    ({"incurred_dose_kj_m2": 1.0}, "incurred_dose_kj_m2"),
    ({"limits": {"peak_kw_m2": 10, "dose_kj_m2": 50}}, "limits"),
    ({"limits": {"peak_kw_m2": 5}}, "limits"),
    ({"destination": {"node_id": "test:n6"}}, "destination node"),
])
def test_unmatched_requests_are_unresolved(fast, override, field):
    job = fast.check(body_for(by_case("test:case1"), **override))
    res = job["result"]
    assert res["verdict"] == "unresolved" and res["reason_code"] == "OTHER"
    assert res["raw_status"] == "MOCK_NO_RECORDED_RESULT"
    assert field in res["raw_reason"] and "test:case1" in res["raw_reason"]
    assert res["compute_s"] is None and res["within_budget"] is True
    assert res["route"] is None and res["exposure"] == [] and res["arrival_s"] is None
    p = res["provenance"]
    assert p["mock"] is True and p["evaluated_configuration"] is False and p["host"]["recorded"] is False
    assert p["input_hashes"] == {"graph": "test-graph-hash", "hazard": "test-hazard-hash"}
    assert p["scenario_ids"] == SIDS0


def test_recorded_model_no_route_and_unresolved(fast):
    rec2 = by_case("test:case2")
    res = fast.check(body_for(rec2))["result"]
    assert res["verdict"] == "model_no_route" and res["reason_code"] is None
    assert res["route"] is None and res["exposure"] == [] and res["compute_s"] == 3.2
    assert res["limits"]["incurred_dose_kj_m2"] == 5.0
    assert any("refusal scope" in n for n in res["notes"])
    res = fast.check(body_for(rec2, incurred_dose_kj_m2=None))["result"]           # omitted incurred = 0 != 5
    assert res["verdict"] == "unresolved" and res["raw_status"] == "MOCK_NO_RECORDED_RESULT"
    assert "incurred_dose_kj_m2" in res["raw_reason"]
    res = fast.check(body_for(by_case("test:case3")))["result"]
    assert res["verdict"] == "unresolved" and res["reason_code"] == "TIMEOUT"
    assert res["compute_s"] == 30.4 and res["within_budget"] is False and res["raw_status"] == "TIMEOUT"


def test_ablation_record_reports_full_hazard_exposure(fast):
    rec = by_case("test:case1", "travel_only")
    res = fast.check(body_for(rec))["result"]
    assert res["verdict"] == "checked_route" and res["policy"] == "travel_only"
    assert res["notes"][0] == "MOCK: recorded result of case test:case1 (A0 rep 1) served without recomputation"
    assert res["provenance"]["evaluated_configuration"] is False
    assert res["provenance"]["recorded_mission_match"] is None
    assert all(e["contact"] is True and e["basis"] == "full_model_centre_check" for e in res["exposure"])
    fpa = res["full_policy_assessment"]
    assert fpa["pass"] is False and fpa["failure_components"] == ["FLAME", "PEAK"]
    assert fpa["policy_exposure"]["members"] == EXPOSURE
    assert any("not guaranteed to pass the full hazard policy" in n for n in res["notes"])


def test_run_independent_check_is_not_faked(fast):
    res = fast.check(body_for(by_case("test:case1"), run_independent_check=True))["result"]
    assert res["verdict"] == "checked_route"
    assert res["independent_check"]["status"] == "NOT_RUN_MOCK" and res["independent_check"]["verdict"] is None


def test_recorded_endpoint_outside_allowed_rule(fast):
    job = fast.check(body_for(by_case("test:case1"), destination={"node_id": "test:n7"}))
    assert job["snap"]["destination"]["node_id"] == "test:n7" and "note" in job["snap"]["destination"]
    assert job["result"]["verdict"] == "unresolved"
    # coordinates never snap to a node outside the allowed rule, even a recorded endpoint
    err = expect_error(fast.post("/route-checks", body_for(by_case("test:case1"), destination={"lon": 128.015, "lat": 36.015})),
                       422, "SNAP_TOO_FAR")
    assert err["details"]["nearest_node_id"] == "test:n6"


def test_spread_zones_are_never_evaluated(fast):
    body = body_for(by_case("test:case1"), fire_input=spread([ZONE_IN, dict(ZONE_IN, properties={"arrival_h_max": 8})],
                                                             burning_scenario_set_id=SSID0))
    job = fast.check(body)
    res = job["result"]
    assert res["verdict"] == "unresolved" and res["reason_code"] == "OTHER"
    assert res["raw_status"] == "MOCK_SPREAD_ZONES_NOT_EVALUATED"
    assert res["assumptions"] == {"mock": True, "evaluated": False, "text": S.SPREAD_ZONES_TEXT, "zones_received": 2}
    assert res["assumptions"]["text"]["ko"].startswith("MOCK 서버는 사용자 입력 확산 구역으로")
    assert res["route"] is None and res["exposure"] == [] and res["compute_s"] is None
    p = res["provenance"]
    assert p["approximation"] == "approximation, requires expert review"
    assert p["fire_input_type"] == "spread_zones" and p["evaluated_configuration"] is False and p["mock"] is True
    assert len(p["input_hashes"]["zones"]) == 64
    assert job["request"]["fire_input"]["margin_min"] == 60


@pytest.mark.parametrize("fire, status, code", [
    (spread([ZONE_OUT]), 422, "ZONES_OUTSIDE_REGION"),
    (spread([ZONE_IN, ZONE_OUT]), 422, "ZONES_OUTSIDE_REGION"),
    (spread([]), 422, "INVALID_ZONES"),
    (spread([zone([[128.0, 36.0], [128.01, 36.0]])]), 422, "INVALID_ZONES"),
    (spread([zone([[128.0, 36.0], [128.01, 36.0], [500, 36.0]])]), 422, "INVALID_ZONES"),
    (spread([zone([[128.0, 36.0], [128.01, 36.0], [128.01, 36.01]], h=0)]), 422, "VALIDATION_ERROR"),
    (spread([{"type": "Feature", "geometry": {"type": "Point", "coordinates": [128.0, 36.0]},
              "properties": {"arrival_h_max": 5}}]), 422, "VALIDATION_ERROR"),
    (spread([ZONE_IN], issued_at="soon"), 422, "INVALID_ZONES"),
    (spread([ZONE_IN], margin_min=-1), 422, "VALIDATION_ERROR"),
    (spread([ZONE_IN], burning_scenario_set_id="test:ss:none"), 422, "UNKNOWN_SCENARIO_SET"),
    (spread([ZONE_IN], burning_scenario_set_id=SSID1), 422, "SCENARIO_SET_TIME_MISMATCH"),
])
def test_spread_zones_validation(fast, fire, status, code):
    expect_error(fast.post("/route-checks", body_for(by_case("test:case1"), fire_input=fire)), status, code)


def test_spread_zones_need_recorded_input_time(fast):
    body = body_for(by_case("test:case1"), fire_input=spread([ZONE_IN]), input_time="2025-02-01T00:00:00Z")
    expect_error(fast.post("/route-checks", body), 422, "INPUT_TIME_UNAVAILABLE")


FAR = {"lon": 128.0, "lat": 35.99}     # ~1.1 km south of test:n1


@pytest.mark.parametrize("override, code", [
    ({"region": None}, "VALIDATION_ERROR"),
    ({"surprise": 1}, "VALIDATION_ERROR"),
    ({"start": {"lon": 128.0, "lat": 36.0, "node_id": "test:n1"}}, "VALIDATION_ERROR"),
    ({"start": {"lon": 200, "lat": 36.0}}, "VALIDATION_ERROR"),
    ({"start": {"lon": "128", "lat": 36.0}}, "VALIDATION_ERROR"),
    ({"depart_offset_s": -1}, "VALIDATION_ERROR"),
    ({"depart_offset_s": True}, "VALIDATION_ERROR"),
    ({"destination_window": [0]}, "VALIDATION_ERROR"),
    ({"policy": "fastest"}, "VALIDATION_ERROR"),
    ({"limits": {"peak_kw_m2": 0}}, "VALIDATION_ERROR"),
    ({"limits": {"peak": 10}}, "VALIDATION_ERROR"),
    ({"client_ref": "x" * 201}, "VALIDATION_ERROR"),
    ({"fire_input": {"type": "forecast"}}, "VALIDATION_ERROR"),
    ({"fire_input": {"type": "recorded"}}, "VALIDATION_ERROR"),
    ({"region": "test:nowhere"}, "UNKNOWN_REGION"),
    ({"input_time": "2025-01-02T00:00:00Z"}, "INPUT_TIME_UNAVAILABLE"),
    ({"input_time": "2025-01-01T00:30:00Z"}, "INVALID_INPUT_TIME"),
    ({"input_time": "2025-01-01T00:00:00"}, "INVALID_INPUT_TIME"),
    ({"fire_input": {"type": "recorded", "scenario_set_id": "test:ss:none"}}, "UNKNOWN_SCENARIO_SET"),
    ({"fire_input": {"type": "recorded", "scenario_set_id": SSID1}}, "SCENARIO_SET_TIME_MISMATCH"),
    ({"start": {"node_id": "test:nope"}}, "UNKNOWN_NODE"),
    ({"destination": {"node_id": "test:n4"}}, "NODE_NOT_ALLOWED"),
    ({"start": FAR}, "SNAP_TOO_FAR"),
    ({"depart_offset_s": 0.5}, "NOT_ON_TIME_LATTICE"),
    ({"depart_offset_s": 4000}, "DEPARTURE_OUTSIDE_HORIZON"),
    ({"destination_window": [100, 50]}, "INVALID_WINDOW"),
    ({"destination_window": [0, 4000]}, "INVALID_WINDOW"),
    ({"destination": {"node_id": "test:n1"}}, "START_EQUALS_DESTINATION"),
    ({"destination_window": [0, 100]}, "WINDOW_UNSATISFIABLE"),
])
def test_route_check_request_errors(fast, override, code):
    err = expect_error(fast.post("/route-checks", body_for(by_case("test:case1"), **override)), 422, code)
    if code == "VALIDATION_ERROR":
        assert isinstance(err["details"], list) and err["details"]
        assert all(set(e) == {"path", "message"} for e in err["details"])
    if code == "SNAP_TOO_FAR":
        assert err["details"]["role"] == "start" and err["details"]["distance_m"] > 300
        assert err["details"]["nearest_node_id"] == "test:n1" and err["details"]["limit_m"] == 300


@pytest.mark.parametrize("data", [b"", b"{not json", b"[]", b'{"a": NaN}', "ÿ".encode("latin-1")])
def test_malformed_bodies(fast, data):
    st, headers, raw = fast.raw("POST", "/route-checks", data=data)
    expect_error((st, json.loads(raw), headers), 422, "VALIDATION_ERROR")


# ------------------------------------------------------------------------------------------------ HTTP behaviour
def test_cors_preflight_and_methods(fast):
    status, headers, body = fast.raw("OPTIONS", "/route-checks", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type"})
    assert status == 204 and body == b""
    assert headers["access-control-allow-origin"] == "*"
    assert "POST" in headers["access-control-allow-methods"]
    assert "content-type" in headers["access-control-allow-headers"].lower()
    err = expect_error(fast.get("/route-checks"), 405, "METHOD_NOT_ALLOWED")
    assert err["details"]["allowed"] == ["POST"]
    expect_error(fast.post("/health", {}), 405, "METHOD_NOT_ALLOWED")
    expect_error(fast.get("/nope"), 404, "NOT_FOUND")
    st, _, raw = Client(fast.base[:-3]).raw("GET", "/v2/health")
    assert st == 404 and json.loads(raw)["error"]["code"] == "NOT_FOUND"
    st, headers, raw = Client(fast.base[:-3]).raw("GET", "/openapi.yaml")
    assert st == 200 and yaml.safe_load(raw)["openapi"] == "3.1.0"


def test_unknown_jobs(fast):
    expect_error(fast.get("/route-checks/rc_nope"), 404, "JOB_NOT_FOUND")
    expect_error(fast.get("/dispatch-plans/dp_nope"), 404, "JOB_NOT_FOUND")
    acc = fast.post("/route-checks", body_for(by_case("test:case1")))[1]
    expect_error(fast.get("/dispatch-plans/%s" % acc["job_id"]), 404, "JOB_NOT_FOUND")


def _state_for(lo: float, hi: float):
    """Expected job status when the server-side elapsed time lies in [lo, hi] (None if ambiguous)."""
    def st(t):
        return "queued" if t < 0.15 else ("running" if t < 0.6 else "done")
    return st(lo) if st(lo) == st(hi) else None


def test_job_state_machine(slow):
    t0 = time.monotonic()
    status, acc, _ = slow.post("/route-checks", body_for(by_case("test:case1")))
    t1 = time.monotonic()
    assert status == 202 and acc["status"] == "queued"
    seen = []
    for target in (0.0, 0.3, 0.75):
        while time.monotonic() - t1 < target:
            time.sleep(0.005)
        g0 = time.monotonic()
        st, job, _ = slow.get("/route-checks/%s" % acc["job_id"])
        g1 = time.monotonic()
        validate(job, "RouteCheckJob")
        check_timestamps(job)
        expected = _state_for(g0 - t1, g1 - t0)
        if expected is not None:
            assert job["status"] == expected, (job["status"], g0 - t1, g1 - t0)
        seen.append(job["status"])
        if job["status"] == "queued":
            assert job["started_at"] is None and job["finished_at"] is None and job["result"] is None
            expect_error(slow.get("/route-checks/%s/export?format=geojson" % acc["job_id"]), 409, "JOB_NOT_DONE")
        elif job["status"] == "running":
            assert job["started_at"] is not None and job["finished_at"] is None and job["result"] is None
            expect_error(slow.get("/route-checks/%s/export?format=csv" % acc["job_id"]), 409, "JOB_NOT_DONE")
        else:
            assert job["finished_at"] is not None and job["result"]["verdict"] == "checked_route"
            started = dt.datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
            created = dt.datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
            finished = dt.datetime.fromisoformat(job["finished_at"].replace("Z", "+00:00"))
            assert abs((started - created).total_seconds() - 0.15) < 0.002
            assert abs((finished - created).total_seconds() - 0.6) < 0.002
            # the recorded compute time is served, never the mock's own state-transition time
            assert job["result"]["compute_s"] == by_case("test:case1")["outcome"]["compute_s"]
    assert seen[-1] == "done"
    assert seen == sorted(seen, key=["queued", "running", "done"].index)


def test_dispatch_progress_state_machine(slow):
    body = {"region": REGION, "input_time": T0, "fire_input": {"type": "recorded", "scenario_set_id": SSID0},
            "origins": [{"id": "o%d" % i, "location": {"node_id": n}} for i, n in enumerate(["test:n1", "test:n2", "test:n5"])],
            "destinations": [{"id": "d1", "location": {"node_id": "test:n3"}}], "depart_offsets_s": [0, 600, 1200]}
    t0 = time.monotonic()
    status, acc, _ = slow.post("/dispatch-plans", body)
    t1 = time.monotonic()
    assert status == 202 and acc["progress"] == {"done": 0, "total": 9}
    dones, statuses = [], []
    while True:
        g0 = time.monotonic()
        st, job, _ = slow.get("/dispatch-plans/%s" % acc["job_id"])
        g1 = time.monotonic()
        validate(job, "DispatchPlanJob")
        expected = _state_for(g0 - t1, g1 - t0)
        if expected is not None:
            assert job["status"] == expected
        dones.append(job["progress"]["done"])
        statuses.append(job["status"])
        assert job["progress"]["total"] == 9
        if job["status"] != "done":
            assert job["result"] is None
        else:
            assert job["result"] is not None and job["progress"]["done"] == 9
            break
        assert g1 - t0 < 5
        time.sleep(0.03)
    assert dones == sorted(dones) and dones[-1] == 9
    assert "running" in statuses and any(0 < d < 9 for d in dones)


# ------------------------------------------------------------------------------------------------ exports
def test_exports_of_checked_route(fast):
    rec = by_case("test:case1")
    job = fast.check(body_for(rec))
    jid = job["job_id"]
    coords = rec["route"]["geometry"]["coordinates"]

    status, headers, raw = fast.raw("GET", "/route-checks/%s/export?format=geojson" % jid)
    assert status == 200 and headers["content-type"].startswith("application/geo+json")
    assert "attachment" in headers["content-disposition"] and ".geojson" in headers["content-disposition"]
    gj = json.loads(raw)
    validate(gj, "RouteExportCollection")
    roles = [f["properties"]["role"] for f in gj["features"]]
    assert roles == ["route", "origin", "destination"]
    assert gj["features"][0]["geometry"]["coordinates"] == coords
    assert gj["features"][1]["geometry"]["coordinates"] == coords[0]
    assert gj["features"][2]["geometry"]["coordinates"] == coords[-1]
    assert gj["features"][0]["properties"]["verdict"] == "checked_route"
    assert gj["provenance"]["mock"] is True
    validate(gj["provenance"], "Provenance")

    status, headers, raw = fast.raw("GET", "/route-checks/%s/export?format=kml" % jid)
    assert status == 200 and headers["content-type"].startswith("application/vnd.google-earth.kml+xml")
    root = ET.fromstring(raw)
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    assert root.tag == "{http://www.opengis.net/kml/2.2}kml"
    assert "MOCK" in root.find("k:Document/k:name", ns).text
    line = root.find(".//k:LineString/k:coordinates", ns).text.split()
    assert len(line) == len(coords)
    assert [tuple(float(v) for v in c.split(",")[:2]) for c in line] == [tuple(c) for c in coords]
    data = {d.get("name"): d.find("k:value", ns).text for d in root.find(".//k:Placemark/k:ExtendedData", ns)}
    assert data["verdict"] == "checked_route" and data["mock"] == "true" and data["arrival_s"] == "260"
    assert data["provenance_checkpoint"] == S.CHECKPOINT and "provenance_git_commit" in data
    assert len(root.findall(".//k:Placemark", ns)) == 3

    status, headers, raw = fast.raw("GET", "/route-checks/%s/export?format=csv" % jid)
    assert status == 200 and headers["content-type"].startswith("text/csv")
    text = raw.decode("utf-8")
    assert text.splitlines()[0] == "seq,node_id,lon,lat,time_s,event"
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == len(coords)
    assert [r["event"] for r in rows] == ["depart", "edge", "wait", "arrive"]
    assert [r["node_id"] for r in rows] == rec["route"]["properties"]["node_ids"]
    assert [int(r["seq"]) for r in rows] == list(range(len(coords)))
    assert [float(r["time_s"]) for r in rows] == rec["route"]["properties"]["times_s"]
    assert all(set(r["event"]) and r["event"] in ("depart", "edge", "wait", "arrive") for r in rows)


def test_csv_node_ids_when_record_lists_distinct_nodes(fast):
    rec = by_case("test:case1", "travel_only")
    job = fast.check(body_for(rec))
    text = fast.raw("GET", "/route-checks/%s/export?format=csv" % job["job_id"])[2].decode()
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["node_id"] for r in rows] == ["test:n1", "test:n2", "test:n2", "test:n3"]
    assert [r["event"] for r in rows] == ["depart", "edge", "wait", "arrive"]


def test_exports_refused_without_checked_route(fast):
    for body in (body_for(by_case("test:case2")), body_for(by_case("test:case1"), depart_offset_s=60),
                 body_for(by_case("test:case1"), fire_input=spread([ZONE_IN]))):
        job = fast.check(body)
        for fmt in ("geojson", "kml", "csv"):
            err = expect_error(fast.get("/route-checks/%s/export?format=%s" % (job["job_id"], fmt)), 409, "NO_CHECKED_ROUTE")
            assert err["details"]["verdict"] in ("model_no_route", "unresolved")
    job = fast.check(body_for(by_case("test:case1")))
    expect_error(fast.get("/route-checks/%s/export?format=shp" % job["job_id"]), 422, "VALIDATION_ERROR")
    expect_error(fast.get("/route-checks/%s/export" % job["job_id"]), 422, "VALIDATION_ERROR")
    expect_error(fast.get("/route-checks/rc_nope/export?format=csv"), 404, "JOB_NOT_FOUND")


# ------------------------------------------------------------------------------------------------ dispatch plans
def plan_body(origins, destinations, offsets, **over):
    b = {"region": REGION, "input_time": T0, "fire_input": {"type": "recorded", "scenario_set_id": SSID0},
         "origins": origins, "destinations": destinations, "depart_offsets_s": offsets}
    b.update(over)
    return b


def test_dispatch_aggregation_and_urgency(fast):
    origins = [{"id": "village-n1", "location": {"node_id": "test:n1"}},
               {"id": "village-n2", "location": {"node_id": "test:n2"}},
               {"id": "village-n4", "location": {"node_id": "test:n4"}},
               {"id": "village-n5", "location": {"lon": 128.0, "lat": 36.008}},
               {"id": "village-n6", "location": {"node_id": "test:n6"}},
               {"id": "village-far", "location": FAR}]
    job = fast.plan(plan_body(origins, [{"id": "shelter-n3", "location": {"node_id": "test:n3"}}], [600, 0, 600]))
    res = job["result"]
    validate(res, "DispatchPlanResult")
    assert job["request"]["depart_offsets_s"] == [0, 600]
    order = [(p["origin_id"], p["urgency_rank"], p["best_verdict"], p["latest_checked_depart_offset_s"]) for p in res["plans"]]
    assert order == [("village-n2", 1, "checked_route", 0), ("village-n1", 2, "checked_route", 600),
                     ("village-n5", 3, "model_no_route", None), ("village-n6", 4, "unresolved", None)]
    plans = {p["origin_id"]: p for p in res["plans"]}
    assert plans["village-n1"]["best"]["arrival_s"] == 900 and plans["village-n1"]["best"]["depart_offset_s"] == 600
    assert plans["village-n2"]["best"]["arrival_s"] == 150
    assert plans["village-n5"]["best"] is None and plans["village-n6"]["best"] is None
    assert plans["village-n5"]["snap"]["input"] == "lonlat" and plans["village-n5"]["snap"]["node_id"] == "test:n5"
    assert [(a["depart_offset_s"], a["verdict"]) for a in plans["village-n2"]["attempts"]] == [(0, "checked_route"), (600, "unresolved")]
    rejected = {r["origin_id"]: r["error"]["code"] for r in res["rejected_origins"]}
    assert rejected == {"village-n4": "NODE_NOT_ALLOWED", "village-far": "SNAP_TOO_FAR"}
    s = res["summary"]
    assert (s["origins"], s["attempts"], s["checked_route"], s["model_no_route"], s["unresolved"]) == (4, 8, 2, 1, 1)
    assert s["attempt_verdicts"] == {"checked_route": 3, "model_no_route": 2, "unresolved": 3}
    recorded_cs = [6.5, 7.0, 5.0, 3.2, 3.2]   # case1, case4, case5, case7, case8
    assert s["median_compute_s"] == statistics.median(recorded_cs) and s["wall_s"] is None
    assert job["progress"] == {"done": 8, "total": 8}
    assert res["assumptions"] is None and res["provenance"]["mock"] is True
    assert res["provenance"]["evaluated_configuration"] is False
    # every attempt is backed by a route-check job carrying its full result
    for p in res["plans"]:
        for a in p["attempts"]:
            rc = fast.get("/route-checks/%s" % a["route_check_job_id"])[1]
            validate(rc, "RouteCheckJob")
            assert rc["status"] == "done" and rc["parent_job_id"] == job["job_id"]
            assert rc["result"]["verdict"] == a["verdict"] and rc["result"]["arrival_s"] == a["arrival_s"]
            assert rc["result"]["compute_s"] == a["compute_s"]
            assert rc["request"]["depart_offset_s"] == a["depart_offset_s"]


def test_dispatch_best_is_earliest_arrival_at_latest_offset(fast):
    job = fast.plan(plan_body([{"id": "o", "location": {"node_id": "test:n1"}}],
                              [{"id": "far-shelter", "location": {"node_id": "test:n3"}},
                               {"id": "near-shelter", "location": {"node_id": "test:n2"}}], [0]))
    p = job["result"]["plans"][0]
    assert p["best_verdict"] == "checked_route" and p["latest_checked_depart_offset_s"] == 0
    assert p["best"]["destination_id"] == "near-shelter" and p["best"]["arrival_s"] == 100
    assert [a["destination_id"] for a in p["attempts"]] == ["far-shelter", "near-shelter"]


def test_dispatch_model_no_route_only_if_every_attempt(fast):
    dest = [{"id": "d", "location": {"node_id": "test:n3"}}]
    o = [{"id": "o", "location": {"node_id": "test:n5"}}]
    assert fast.plan(plan_body(o, dest, [0, 600]))["result"]["plans"][0]["best_verdict"] == "model_no_route"
    p = fast.plan(plan_body(o, dest, [0, 600, 1200]))["result"]["plans"][0]
    assert p["best_verdict"] == "unresolved" and p["latest_checked_depart_offset_s"] is None


def test_dispatch_rejected_attempts_and_all_rejected(fast):
    dest = [{"id": "d", "location": {"node_id": "test:n3"}, "window": [0, 100]}]   # unsatisfiable with dwell 120
    job = fast.plan(plan_body([{"id": "o", "location": {"node_id": "test:n1"}}], dest, [0]))
    a = job["result"]["plans"][0]["attempts"][0]
    assert a["verdict"] == "unresolved" and a["route_check_job_id"] is None and a["raw_status"] == "INPUT_REJECTED"
    assert job["progress"] == {"done": 1, "total": 1}
    job = fast.plan(plan_body([{"id": "far", "location": FAR}], [{"id": "d", "location": {"node_id": "test:n3"}}], [0]))
    assert job["result"]["plans"] == [] and job["result"]["summary"]["origins"] == 0
    assert job["result"]["rejected_origins"][0]["error"]["code"] == "SNAP_TOO_FAR"


def test_dispatch_spread_zones(fast):
    job = fast.plan(plan_body([{"id": "o", "location": {"node_id": "test:n1"}}],
                              [{"id": "d", "location": {"node_id": "test:n3"}}], [0, 600], fire_input=spread([ZONE_IN])))
    res = job["result"]
    assert res["assumptions"]["evaluated"] is False and res["assumptions"]["zones_received"] == 1
    assert res["provenance"]["approximation"] == "approximation, requires expert review"
    assert all(a["verdict"] == "unresolved" and a["raw_status"] == "MOCK_SPREAD_ZONES_NOT_EVALUATED"
               for p in res["plans"] for a in p["attempts"])
    assert res["summary"]["median_compute_s"] is None


def test_dispatch_request_errors(fast):
    o = [{"id": "o", "location": {"node_id": "test:n1"}}]
    d = [{"id": "d", "location": {"node_id": "test:n3"}}]
    many = [{"id": "o%d" % i, "location": {"node_id": "test:n1"}} for i in range(201)]
    err = expect_error(fast.post("/dispatch-plans", plan_body(many, d, [0])), 422, "TOO_MANY_ORIGINS")
    assert err["details"]["max_origins"] == 200
    expect_error(fast.post("/dispatch-plans", plan_body(o + o, d, [0])), 422, "DUPLICATE_ID")
    err = expect_error(fast.post("/dispatch-plans", plan_body(o, [{"id": "d", "location": FAR}], [0])), 422, "SNAP_TOO_FAR")
    assert err["details"]["destination_id"] == "d"
    expect_error(fast.post("/dispatch-plans", plan_body(o, d, list(range(0, 2500, 100)))), 422, "VALIDATION_ERROR")
    expect_error(fast.post("/dispatch-plans", plan_body(o, d * 21, [0])), 422, "VALIDATION_ERROR")
    expect_error(fast.post("/dispatch-plans", plan_body([], d, [0])), 422, "VALIDATION_ERROR")
    expect_error(fast.post("/dispatch-plans", plan_body(o, d, [0], region="test:nowhere")), 422, "UNKNOWN_REGION")
    expect_error(fast.post("/dispatch-plans", plan_body(o, d, [0], extra=True)), 422, "VALIDATION_ERROR")


def test_client_validates_every_json_response(fast):
    before = dict(VALIDATED)
    fast.get("/health")
    fast.get("/regions")
    fast.get("/regions/%s/forecast?input_time=%s&only_nonzero=true" % (REGION, T0))
    job = fast.check(body_for(by_case("test:case1")))
    fast.raw("GET", "/route-checks/%s/export?format=geojson" % job["job_id"])
    fast.plan(plan_body([{"id": "o", "location": {"node_id": "test:n1"}}], [{"id": "d", "location": {"node_id": "test:n3"}}], [0]))
    fast.get("/route-checks/rc_nope")
    for comp in ("Health", "RegionList", "ForecastCollection", "JobAccepted", "RouteCheckJob", "RouteExportCollection",
                 "DispatchPlanJob", "Error"):
        assert VALIDATED.get(comp, 0) > before.get(comp, 0), comp


# ================================================================================================ (b) real fixtures
REAL_AVAILABLE = (REAL_FIXTURES / "MANIFEST.json").is_file()
real = pytest.mark.skipif(not REAL_AVAILABLE, reason="planner/mock_api/fixtures/MANIFEST.json not generated yet")


@pytest.fixture(scope="module")
def real_server():
    api, httpd, client = start_server(REAL_FIXTURES, queued_s=0.0, done_s=0.0)
    yield api, client
    stop_server(httpd)


def real_records():
    if not REAL_AVAILABLE:
        return []
    out = []
    for p in sorted((REAL_FIXTURES / "records").rglob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


REAL_RECORDS = real_records()


@real
def test_real_health_and_regions(real_server):
    api, client = real_server
    status, h, _ = client.get("/health")
    validate(h, "Health")
    assert h["status"] == "ok", h["issues"]
    assert h["mode"] == "mock"
    assert set(h["regions"]) == {"uljin_2022", "miryang_2022", "hongseong_2023", "uiseong_andong_2025", "yeongdeok_2025"}
    status, doc, _ = client.get("/regions")
    validate(doc, "RegionList")
    for r in doc["regions"]:
        assert len(r["scenario_sets"]) == len(r["input_times"]) >= 1
        for s in r["scenario_sets"]:
            assert len(s["scenario_ids"]) == 4


@real
def test_real_forecasts_validate(real_server):
    api, client = real_server
    doc = client.get("/regions")[1]
    for r in doc["regions"]:
        for t in r["input_times"]:
            st, fc, _ = client.get("/regions/%s/forecast?input_time=%s&only_nonzero=true" % (r["id"], t))
            assert st == 200, fc
            validate(fc, "ForecastCollection")
            assert all((f["properties"]["p_new_burn_1h"] or 0) > 0 or f["properties"]["burning_now"] for f in fc["features"])
    r = doc["regions"][0]
    st, fc, _ = client.get("/regions/%s/forecast?input_time=%s" % (r["id"], r["input_times"][0]))
    validate(fc, "ForecastCollection")
    assert len(fc["features"]) == r["grid"]["width"] * r["grid"]["height"]


def _real_body(rec):
    return body_for(rec)


@real
def test_real_full_missions_replay_recorded_verdicts(real_server):
    api, client = real_server
    full = [r for r in REAL_RECORDS if r["policy"] == "full"]
    assert len(full) == 20
    counts = {"checked_route": 0, "model_no_route": 0, "unresolved": 0}
    for rec in full:
        job = client.check(_real_body(rec))
        res = job["result"]
        assert res["verdict"] == rec["outcome"]["verdict"], rec["case_id"]
        assert res["arrival_s"] == rec["outcome"]["arrival_s"] and res["compute_s"] == rec["outcome"]["compute_s"]
        assert res["notes"][0] == "MOCK: recorded result of case %s (RDA_CAND rep 1) served without recomputation" % rec["case_id"]
        assert res["provenance"]["evaluated_configuration"] is True and res["provenance"]["mock"] is True
        if res["verdict"] == "checked_route":
            assert res["route"] == rec["route"] and len(res["exposure"]) == 4
            assert all(e["contact"] is False for e in res["exposure"])
        counts[res["verdict"]] += 1
    assert counts == {"checked_route": 15, "model_no_route": 5, "unresolved": 0}


@real
@pytest.mark.parametrize("policy", ["travel_only", "flame_only", "flame_peak", "flame_dose"])
def test_real_ablation_records_replay(real_server, policy):
    api, client = real_server
    recs = [r for r in REAL_RECORDS if r["policy"] == policy]
    assert len(recs) == 20
    for rec in recs:
        res = client.check(_real_body(rec))["result"]
        assert res["verdict"] == rec["outcome"]["verdict"], rec["case_id"]
        assert res["policy"] == policy and res["provenance"]["evaluated_configuration"] is False
        assert res["compute_s"] == rec["outcome"]["compute_s"]
    if policy == "travel_only":
        assert {r["outcome"]["verdict"] for r in recs} <= {"checked_route", "model_no_route", "unresolved"}


@real
def test_real_lonlat_far_from_recorded_nodes_is_unresolved(real_server):
    api, client = real_server
    rec = next(r for r in REAL_RECORDS if r["policy"] == "full" and r["region_id"] == "uiseong_andong_2025"
               and r["outcome"]["verdict"] == "checked_route")
    nodes = json.loads((REAL_FIXTURES / "nodes" / "uiseong_andong_2025.json").read_text())
    ends = [(nodes["lon"][nodes["ids"].index(n)], nodes["lat"][nodes["ids"].index(n)])
            for r in REAL_RECORDS if r["region_id"] == "uiseong_andong_2025"
            for n in (r["request"]["origin_node"], r["request"]["destination_node"])]
    best, best_d = None, -1.0
    for k in range(0, len(nodes["ids"]), 97):
        if not nodes["allowed"][k]:
            continue
        d = min(S.haversine_m(nodes["lon"][k], nodes["lat"][k], x, y) for x, y in ends)
        if d > best_d:
            best, best_d = k, d
    assert best_d > 2000
    start = {"lon": nodes["lon"][best], "lat": nodes["lat"][best] + 15 / 111195.0}
    job = client.check(body_for(rec, start=start))
    assert job["snap"]["start"]["input"] == "lonlat" and job["snap"]["start"]["distance_m"] < 300
    res = job["result"]
    assert res["verdict"] == "unresolved" and res["raw_status"] == "MOCK_NO_RECORDED_RESULT"
    assert res["route"] is None and res["compute_s"] is None
    assert "start node" in res["raw_reason"]


@real
def test_real_exports(real_server):
    api, client = real_server
    rec = next(r for r in REAL_RECORDS if r["policy"] == "full" and r["outcome"]["verdict"] == "checked_route")
    job = client.check(_real_body(rec))
    coords = rec["route"]["geometry"]["coordinates"]
    gj = json.loads(client.raw("GET", "/route-checks/%s/export?format=geojson" % job["job_id"])[2])
    validate(gj, "RouteExportCollection")
    root = ET.fromstring(client.raw("GET", "/route-checks/%s/export?format=kml" % job["job_id"])[2])
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    assert len(root.find(".//k:LineString/k:coordinates", ns).text.split()) == len(coords)
    text = client.raw("GET", "/route-checks/%s/export?format=csv" % job["job_id"])[2].decode()
    rows = list(csv.DictReader(io.StringIO(text)))
    assert text.splitlines()[0] == "seq,node_id,lon,lat,time_s,event"
    assert len(rows) == len(coords) and rows[0]["event"] == "depart" and rows[-1]["event"] == "arrive"
    assert rows[0]["node_id"] == rec["request"]["origin_node"] and rows[-1]["node_id"] == rec["request"]["destination_node"]
    assert {r["event"] for r in rows} <= {"depart", "edge", "wait", "arrive"}
    assert all(r["node_id"] for r in rows)
    mnr = next(r for r in REAL_RECORDS if r["policy"] == "full" and r["outcome"]["verdict"] == "model_no_route")
    job = client.check(_real_body(mnr))
    expect_error(client.get("/route-checks/%s/export?format=csv" % job["job_id"]), 409, "NO_CHECKED_ROUTE")


@real
def test_real_dispatch_replays_recorded_mission(real_server):
    api, client = real_server
    rec = next(r for r in REAL_RECORDS if r["policy"] == "full" and r["request"]["incurred_dose_kj_m2"] == 0
               and r["request"]["depart_offset_s"] > 0)
    q = rec["request"]
    offsets = sorted({0, q["depart_offset_s"]})
    body = {"region": rec["region_id"], "input_time": rec["input_time"],
            "fire_input": {"type": "recorded", "scenario_set_id": rec["scenario_set_id"]},
            "origins": [{"id": "research-origin", "location": {"node_id": q["origin_node"]}}],
            "destinations": [{"id": "research-destination", "location": {"node_id": q["destination_node"]},
                              "dwell_s": q["dwell_s"], "window": q["destination_window"]}],
            "depart_offsets_s": offsets, "limits": q["limits"]}
    job = client.plan(body)
    p = job["result"]["plans"][0]
    by_off = {a["depart_offset_s"]: a for a in p["attempts"]}
    assert by_off[q["depart_offset_s"]]["verdict"] == rec["outcome"]["verdict"]
    assert by_off[q["depart_offset_s"]]["case_id"] == rec["case_id"]
    assert by_off[0]["verdict"] == "unresolved"
    expected = "checked_route" if rec["outcome"]["verdict"] == "checked_route" else "unresolved"
    assert p["best_verdict"] == expected
