#!/usr/bin/env python3
"""WildfireGuardian Route-Check API v1 -- MOCK server (Python standard library only).

Implements every path of the official contract ``planner/contract/wfg_api_v1.yaml`` (v1.5.0, base path ``/v1``) so
the village evacuation planner can be developed and demonstrated without the real API. Error codes, check order and
response shapes mirror the real implementation (origin/feat/api ``api/*.py``) wherever a mock can.

Honesty rule (planner/docs/ARCHITECTURE.md section 5.1): the mock computes nothing. It returns a recorded result only
when region, input_time, fire_input.scenario_set_id, start node, destination node, depart_offset_s, dwell_s,
destination_window (omitted = [valid_from, horizon_s]), policy, limits and incurred_dose_kj_m2 all equal one recorded
execution in ``fixtures/records/``. Every other request is ``unresolved`` (reason_code ``OTHER``, raw_status
``MOCK_NO_RECORDED_RESULT``) and every ``spread_zones`` request is ``unresolved`` (raw_status
``MOCK_SPREAD_ZONES_NOT_EVALUATED``) with an ``assumptions`` object saying so. ``/health`` reports ``"mode": "mock"``
and every provenance block carries ``"mock": true``. Jobs move queued -> running -> done over about 0.6 s of wall
clock (no sleeping threads); recorded ``compute_s`` values are served as recorded, never invented.

Contract v1.4 rules the mock applies to recorded results, exactly as the real API does:
* ``run_independent_check: true`` with policy ``full``: the mock never runs the offline independent checker, so the
  requested check did not complete and a recorded ``checked_route`` / ``model_no_route`` is served as ``unresolved``
  (``CHECK_NOT_FINISHED``, raw_reason ``INDEPENDENT_CHECK_MISSING``), as the frozen scorer requires. Other policies:
  the checker is not defined, a note says so and the verdict is unchanged.
* a reduced-policy route whose recorded full-hazard grade contradicts its own policy's enabled constraints is
  ``unresolved`` (``CHECK_FAILED``, raw_reason ``INDEPENDENT_CONTRADICTION``).

Usage:
    python3 planner/mock_api/server.py [--host 127.0.0.1] [--port 8765] [--fixtures DIR] [--quiet]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import signal
import statistics
import subprocess
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from xml.sax.saxutils import escape as _xml_escape

HERE = Path(__file__).resolve().parent
PLANNER = HERE.parent
CONTRACT_PATH = PLANNER / "contract" / "wfg_api_v1.yaml"

# ---------------------------------------------------------------------------------------------------- fixed facts
API_VERSION = "1.5.0"               # info.version of the contract copy this mock implements
PACKAGE = "wfg_latest"
PACKAGE_VERSION = "1.0.0"
KIT = "v3"
CHECKPOINT = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
DEFAULT_PEAK_KW_M2 = 10
DEFAULT_DOSE_KJ_M2 = 100
DEFAULT_DWELL_S = 120
DEFAULT_MARGIN_MIN = 60
SNAP_MAX_M = 300.0
BUDGET_S = 30.0
MAX_ORIGINS = 200
MAX_DISPATCH_ATTEMPTS = 4800        # origins x destinations x offsets per plan (contract v1.4, TOO_MANY_ATTEMPTS)
MOCK_WORKERS = 1
MAX_BODY_BYTES = 32 * 1024 * 1024
DEFAULT_QUEUED_S = 0.15             # queued while elapsed < 0.15 s
DEFAULT_DONE_S = 0.6                # running while elapsed < 0.6 s, then done
MAX_JOBS = 500_000                  # oldest jobs are forgotten beyond this (GET -> 404 JOB_NOT_FOUND)

POLICIES = ("full", "travel_only", "flame_only", "flame_peak", "flame_dose")
VERDICTS = ("checked_route", "model_no_route", "unresolved")
CHECKED, NO_ROUTE, UNRESOLVED = VERDICTS
REASON_CODES = ("TIMEOUT", "STATE_CAP", "MEMORY_CAP", "CHECK_NOT_FINISHED", "CHECK_FAILED", "WORKER_ERROR",
                "CLEANUP_UNCONFIRMED", "INTERNAL_ERROR", "OTHER",
                "INPUT_REJECTED", "AT_ISSUE_FAILURE", "DISCONNECTED")          # v1.1 pass-through decision statuses
# Constraints each reduced policy enforces (final-input ablation arm_transform.ENABLED for A0-A3; api/runner.py).
POLICY_ENABLED = {"travel_only": frozenset(), "flame_only": frozenset({"FLAME"}),
                  "flame_peak": frozenset({"FLAME", "PEAK"}), "flame_dose": frozenset({"FLAME", "DOSE"})}

RECORDED_CLOCK = "complete-request wall time recorded on the native campaign host"
NOTE_UNRESOLVED = "Unresolved is never safe: no checked route and no scoped refusal were established."
NOTE_NO_ROUTE = ("Scoped refusal: no route exists within this model, lattice, scenarios and policy; it is not proof "
                 "that every real-world escape is impossible.")
NOTE_NO_INDEPENDENT = ("run_independent_check was requested: the MOCK server never runs the offline independent "
                       "checker, so the requested check did not complete and, as the frozen scorer requires, the "
                       "result is unresolved (CHECK_NOT_FINISHED, INDEPENDENT_CHECK_MISSING).")
NODE_RULE = "at least one incoming and one outgoing road"
RECORDED_HOST = {"recorded": True, "machine": "Apple M5 Pro", "os": "macOS (native)"}
NOT_COMPUTED_HOST = {"recorded": False, "machine": None, "os": None,
                     "note": "MOCK: nothing was computed for this response"}
APPROXIMATION = "approximation, requires expert review"
MOCK_NO_RECORD = "MOCK_NO_RECORDED_RESULT"
MOCK_ZONES = "MOCK_SPREAD_ZONES_NOT_EVALUATED"
SPREAD_ZONES_TEXT = {
    "ko": "MOCK 서버는 사용자 입력 확산 구역으로 경로를 계산하지 않습니다. 실제 Route-Check API에 연결하면 API가 반환한 "
          "가정이 여기에 표시됩니다.",
    "en": "The MOCK server does not compute routes for user-drawn spread zones. With the real Route-Check API "
          "connected, the API's own assumptions appear here.",
}
SNAP_METHOD = "nearest allowed node of the MOCK node table by haversine distance on WGS84 (the real API measures in EPSG:5179)"

ENDPOINTS = [
    ("GET", "/v1/health", "getHealth", "서버 상태 / service health"),
    ("GET", "/v1/regions", "listRegions", "지역 목록 / list regions"),
    ("GET", "/v1/regions/{region}/forecast", "getRegionForecast", "기록된 1시간 신규 연소 확률 / recorded next-hour new-burn forecast"),
    ("POST", "/v1/route-checks", "createRouteCheck", "경로 점검 작업 생성 / submit a route check"),
    ("GET", "/v1/route-checks/{job_id}", "getRouteCheck", "경로 점검 결과 조회 / get route check status and result"),
    ("GET", "/v1/route-checks/{job_id}/export", "exportRouteCheck", "점검된 경로 내보내기 / export a checked route"),
    ("POST", "/v1/dispatch-plans", "createDispatchPlan", "대피 배차 계획 작업 생성 / submit a dispatch plan"),
    ("GET", "/v1/dispatch-plans/{job_id}", "getDispatchPlan", "배차 계획 결과 조회 / get dispatch plan status and result"),
]


# ---------------------------------------------------------------------------------------------------- errors
class ApiError(Exception):
    """Uniform error envelope {"error": {"code", "message", "details"}}."""

    def __init__(self, status: int, code: str, message: str, details=None, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}

    def body(self) -> dict:
        err = {"code": self.code, "message": self.message}
        if self.details is not None:
            err["details"] = self.details
        return {"error": err}


def _unprocessable(code, message, details=None):
    return ApiError(422, code, message, details)


# ---------------------------------------------------------------------------------------------------- time
_TAG_RE = re.compile(r"^\d{8}T\d{2}0000Z$")


def normalize_input_time(text) -> str:
    """'2022-03-04T03:00:00Z', '...+00:00' or '20220304T030000Z' -> tag '20220304T030000Z' (whole UTC hours)."""
    s = str(text).strip()
    if _TAG_RE.match(s):
        try:
            dt.datetime.strptime(s, "%Y%m%dT%H%M%SZ")
            return s
        except ValueError:
            pass
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        raise _unprocessable("INVALID_INPUT_TIME", "input_time must be an ISO 8601 UTC time such as 2022-03-04T03:00:00Z "
                             "or the compact form 20220304T030000Z", {"input_time": s})
    if t.tzinfo is None:
        raise _unprocessable("INVALID_INPUT_TIME", "input_time must carry a time zone (use Z for UTC)", {"input_time": s})
    t = t.astimezone(dt.timezone.utc)
    if t.minute or t.second or t.microsecond:
        raise _unprocessable("INVALID_INPUT_TIME", "input_time must be a whole UTC hour", {"input_time": s})
    return t.strftime("%Y%m%dT%H0000Z")


def tag_to_iso(tag: str) -> str:
    return "%s-%s-%sT%s:00:00Z" % (tag[0:4], tag[4:6], tag[6:8], tag[9:11])


def iso_ms(t: dt.datetime) -> str:
    t = t.astimezone(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (t.microsecond // 1000)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_utc(text):
    t = dt.datetime.fromisoformat(str(text).strip().replace("Z", "+00:00").replace("z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("no time zone")
    return t.astimezone(dt.timezone.utc)


# ---------------------------------------------------------------------------------------------------- numbers
def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def num_eq(a, b) -> bool:
    if not (_is_num(a) and _is_num(b)):
        return False
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def _num_out(v):
    """JSON number as recorded: integral values as int."""
    f = float(v)
    return int(f) if f.is_integer() else f


# ---------------------------------------------------------------------------------------------------- request schemas
# Mirror of the request-side component schemas of planner/contract/wfg_api_v1.yaml with annotation keywords
# (description, examples, default, discriminator) removed. tests/planner/test_mock_api.py asserts that these equal
# the contract after the same stripping, so a contract change that is not mirrored here fails the tests.
_S = "#/components/schemas/"
REQUEST_SCHEMAS = {
    "Location": {"oneOf": [{"$ref": _S + "LonLat"}, {"$ref": _S + "NodeRef"}]},
    "LonLat": {"type": "object", "required": ["lon", "lat"], "additionalProperties": False,
               "properties": {"lon": {"type": "number", "minimum": -180, "maximum": 180},
                              "lat": {"type": "number", "minimum": -90, "maximum": 90}}},
    "NodeRef": {"type": "object", "required": ["node_id"], "additionalProperties": False,
                "properties": {"node_id": {"type": "string"}}},
    "Policy": {"type": "string", "enum": list(POLICIES)},
    "Limits": {"type": "object", "additionalProperties": False,
               "properties": {"peak_kw_m2": {"type": "number", "exclusiveMinimum": 0},
                              "dose_kj_m2": {"type": "number", "exclusiveMinimum": 0}}},
    "FireInput": {"oneOf": [{"$ref": _S + "RecordedFireInput"}, {"$ref": _S + "SpreadZonesFireInput"}]},
    "RecordedFireInput": {"type": "object", "required": ["type", "scenario_set_id"], "additionalProperties": False,
                          "properties": {"type": {"type": "string", "const": "recorded"},
                                         "scenario_set_id": {"type": "string"}}},
    "SpreadZonesFireInput": {"type": "object", "required": ["type", "zones", "issued_at"], "additionalProperties": False,
                             "properties": {"type": {"type": "string", "const": "spread_zones"},
                                            "zones": {"$ref": _S + "ZoneCollection"},
                                            "issued_at": {"type": "string", "format": "date-time"},
                                            "margin_min": {"type": "number", "minimum": 0},
                                            "burning_scenario_set_id": {"type": ["string", "null"]}}},
    "ZoneCollection": {"type": "object", "required": ["type", "features"],
                       "properties": {"type": {"type": "string", "const": "FeatureCollection"},
                                      "features": {"type": "array", "items": {"$ref": _S + "ZoneFeature"}}}},
    "ZoneFeature": {"type": "object", "required": ["type", "geometry", "properties"],
                    "properties": {"type": {"type": "string", "const": "Feature"},
                                   "geometry": {"type": "object", "required": ["type", "coordinates"],
                                                "properties": {"type": {"type": "string", "enum": ["Polygon", "MultiPolygon"]},
                                                               "coordinates": {"type": "array"}}},
                                   "properties": {"type": "object", "required": ["arrival_h_max"],
                                                  "properties": {"arrival_h_max": {"type": "number", "exclusiveMinimum": 0}}}}},
    "RouteCheckRequest": {
        "type": "object", "required": ["region", "input_time", "start", "destination", "fire_input"],
        "additionalProperties": False,
        "properties": {
            "region": {"type": "string"},
            "input_time": {"type": "string"},
            "start": {"$ref": _S + "Location"},
            "destination": {"$ref": _S + "Location"},
            "depart_offset_s": {"type": "number", "minimum": 0},
            "dwell_s": {"type": "number", "minimum": 0},
            "destination_window": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 2, "maxItems": 2},
            "policy": {"$ref": _S + "Policy"},
            "limits": {"$ref": _S + "Limits"},
            "incurred_dose_kj_m2": {"type": "number", "minimum": 0},
            "fire_input": {"$ref": _S + "FireInput"},
            "run_independent_check": {"type": "boolean"},
            "client_ref": {"type": ["string", "null"], "maxLength": 200},
        }},
    "DispatchDestination": {"type": "object", "required": ["id", "location"], "additionalProperties": False,
                            "properties": {"id": {"type": "string"}, "location": {"$ref": _S + "Location"},
                                           "dwell_s": {"type": "number", "minimum": 0},
                                           "window": {"type": "array", "items": {"type": "number", "minimum": 0},
                                                      "minItems": 2, "maxItems": 2}}},
    "DispatchOrigin": {"type": "object", "required": ["id", "location"], "additionalProperties": False,
                       "properties": {"id": {"type": "string"}, "location": {"$ref": _S + "Location"}}},
    "DispatchPlanRequest": {
        "type": "object", "required": ["region", "input_time", "fire_input", "origins", "destinations", "depart_offsets_s"],
        "additionalProperties": False,
        "properties": {
            "region": {"type": "string"},
            "input_time": {"type": "string"},
            "fire_input": {"$ref": _S + "FireInput"},
            "origins": {"type": "array", "minItems": 1, "maxItems": MAX_ORIGINS, "items": {"$ref": _S + "DispatchOrigin"}},
            "destinations": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"$ref": _S + "DispatchDestination"}},
            "depart_offsets_s": {"type": "array", "minItems": 1, "maxItems": 24, "items": {"type": "number", "minimum": 0}},
            "dwell_s": {"type": "number", "minimum": 0},
            "policy": {"$ref": _S + "Policy"},
            "limits": {"$ref": _S + "Limits"},
            "client_ref": {"type": ["string", "null"], "maxLength": 200},
        }},
}
# Keywords the small validator below implements ('format' is an annotation, as in jsonschema's default mode).
SUPPORTED_KEYWORDS = frozenset({"$ref", "oneOf", "type", "const", "enum", "minimum", "maximum", "exclusiveMinimum",
                                "maxLength", "format", "minItems", "maxItems", "items", "required", "properties",
                                "additionalProperties"})


def _type_ok(v, t) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    return False


def _short(v) -> str:
    s = json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= 60 else s[:57] + "..."


def _check(v, s: dict, path: list, out: list) -> None:
    if "$ref" in s:
        _check(v, REQUEST_SCHEMAS[s["$ref"].rsplit("/", 1)[1]], path, out)
        return
    if "oneOf" in s:
        branches = []
        for sub in s["oneOf"]:
            errs: list = []
            _check(v, sub, path, errs)
            branches.append(errs)
        ok = [i for i, e in enumerate(branches) if not e]
        names = [sub.get("$ref", "").rsplit("/", 1)[-1] or str(i) for i, sub in enumerate(s["oneOf"])]
        if not ok:
            out.append({"path": "/".join(map(str, path)), "message": "%s is not valid under any of: %s" % (_short(v), ", ".join(names))})
            out.extend(min(branches, key=len))
        elif len(ok) > 1:
            out.append({"path": "/".join(map(str, path)), "message": "%s is valid under more than one of: %s" % (_short(v), ", ".join(names))})
    t = s.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_type_ok(v, x) for x in ts):
            out.append({"path": "/".join(map(str, path)), "message": "%s is not of type %s" % (_short(v), " or ".join(map(repr, ts)))})
            return
    p = "/".join(map(str, path))
    if "const" in s and not (type(v) is type(s["const"]) and v == s["const"]):
        out.append({"path": p, "message": "%r was expected" % (s["const"],)})
    if "enum" in s and not any(type(v) is type(e) and v == e for e in s["enum"]):
        out.append({"path": p, "message": "%s is not one of %s" % (_short(v), s["enum"])})
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if not math.isfinite(v):
            out.append({"path": p, "message": "%r is not a finite number" % (v,)})
        else:
            if "minimum" in s and v < s["minimum"]:
                out.append({"path": p, "message": "%s is less than the minimum of %s" % (v, s["minimum"])})
            if "maximum" in s and v > s["maximum"]:
                out.append({"path": p, "message": "%s is greater than the maximum of %s" % (v, s["maximum"])})
            if "exclusiveMinimum" in s and v <= s["exclusiveMinimum"]:
                out.append({"path": p, "message": "%s is less than or equal to the minimum of %s" % (v, s["exclusiveMinimum"])})
    if isinstance(v, str) and "maxLength" in s and len(v) > s["maxLength"]:
        out.append({"path": p, "message": "string is longer than %d characters" % s["maxLength"]})
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            out.append({"path": p, "message": "should have at least %d items" % s["minItems"]})
        if "maxItems" in s and len(v) > s["maxItems"]:
            out.append({"path": p, "message": "should have at most %d items" % s["maxItems"]})
        if "items" in s:
            for i, x in enumerate(v):
                _check(x, s["items"], path + [i], out)
    if isinstance(v, dict):
        for k in s.get("required", ()):
            if k not in v:
                out.append({"path": p, "message": "%r is a required property" % k})
        props = s.get("properties", {})
        for k, x in v.items():
            if k in props:
                _check(x, props[k], path + [k], out)
        if s.get("additionalProperties") is False:
            extra = [k for k in v if k not in props]
            if extra:
                out.append({"path": p, "message": "additional properties are not allowed (%s unexpected)" % ", ".join(map(repr, extra))})


def schema_errors(instance, component: str) -> list:
    """Validation errors of ``instance`` against a contract request component (subset validator, stdlib only)."""
    out: list = []
    _check(instance, {"$ref": _S + component}, [], out)
    return out


# ---------------------------------------------------------------------------------------------------- geo
EARTH_R_M = 6371008.8
M_PER_DEG = math.pi * EARTH_R_M / 180.0


def haversine_m(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(h)))


class NodeTable:
    """Compact node table (fixtures/nodes/<region>.json) with a bucket index for nearest-node snapping."""

    CELL_DEG = 0.0025                  # ~280 m x ~220 m buckets at Korean latitudes

    def __init__(self, doc: dict):
        ids, lon, lat, allowed = doc["ids"], doc["lon"], doc["lat"], doc["allowed"]
        if not (len(ids) == len(lon) == len(lat) == len(allowed)):
            raise ValueError("ids, lon, lat and allowed must have the same length")
        self.ids = list(ids)
        self.lon = [float(x) for x in lon]
        self.lat = [float(x) for x in lat]
        self.allowed = [bool(a) for a in allowed]
        self.allowed_rule = doc.get("allowed_rule")
        self.index = {n: i for i, n in enumerate(self.ids)}
        if len(self.index) != len(self.ids):
            raise ValueError("duplicate node ids")
        self._b_all: dict = {}
        self._b_allowed: dict = {}
        c = self.CELL_DEG
        for i in range(len(self.ids)):
            key = (math.floor(self.lon[i] / c), math.floor(self.lat[i] / c))
            self._b_all.setdefault(key, []).append(i)
            if self.allowed[i]:
                self._b_allowed.setdefault(key, []).append(i)
        self.allowed_count = sum(self.allowed)

    def __len__(self):
        return len(self.ids)

    def nearest(self, lon: float, lat: float, allowed_only: bool = True):
        """(index, distance_m) of the nearest (allowed) node, exact; None when the table is empty."""
        buckets = self._b_allowed if allowed_only else self._b_all
        if not buckets:
            return None
        c = self.CELL_DEG
        ix, iy = math.floor(lon / c), math.floor(lat / c)
        best_i, best_d = None, math.inf
        r = 0
        max_r = 80                                   # ~ 20 km; beyond that a full scan decides
        while r <= max_r:
            if r == 0:
                cells = [(ix, iy)]
            else:
                cells = [(ix + dx, iy + dy) for dx in range(-r, r + 1) for dy in (-r, r)]
                cells += [(ix + dx, iy + dy) for dx in (-r, r) for dy in range(-r + 1, r)]
            for key in cells:
                for i in buckets.get(key, ()):
                    d = haversine_m(lon, lat, self.lon[i], self.lat[i])
                    if d < best_d or (d == best_d and best_i is not None and self.ids[i] < self.ids[best_i]):
                        best_i, best_d = i, d
            # every node not yet visited lies at least r cells away in lon or lat
            coslat = math.cos(math.radians(min(89.0, abs(lat) + (r + 1) * c)))
            bound = r * c * M_PER_DEG * coslat * 0.99
            if best_i is not None and best_d <= bound:
                return best_i, best_d
            r += 1
        for key, idxs in buckets.items():               # far from every node: exact full scan
            for i in idxs:
                d = haversine_m(lon, lat, self.lon[i], self.lat[i])
                if d < best_d:
                    best_i, best_d = i, d
        return (best_i, best_d) if best_i is not None else None


# ---------------------------------------------------------------------------------------------------- fixtures
class Record:
    """One recorded execution (fixtures/records/<region>/<case>__<policy>.json, ARCHITECTURE.md section 4.1)."""

    __slots__ = ("doc", "path", "region", "case_id", "policy", "ssid", "tag", "start", "dest", "depart", "dwell",
                 "window", "peak", "dose", "incurred", "verdict", "source_arm", "repetition", "route", "fpa")

    def label(self) -> str:
        return "%s__%s" % (self.case_id, self.policy)


class Fixtures:
    """Loads the recorded fixture tree once at start-up (restart the server after regenerating fixtures)."""

    def __init__(self, root):
        self.root = Path(root)
        self.issues: list = []
        self.manifest = None
        self.regions_doc = {"regions": [], "provenance": {}}
        self.regions: dict = {}           # id -> Region dict (as in regions.json)
        self.sets: dict = {}              # region -> {scenario_set_id: ScenarioSet dict}
        self.set_tag: dict = {}           # (region, scenario_set_id) -> tag
        self.sets_at: dict = {}           # (region, tag) -> [ScenarioSet dict]
        self.nodes: dict = {}             # region -> NodeTable
        self.records: list = []
        self.by_key: dict = {}            # (region, ssid, policy, start, dest) -> [Record]
        self.by_mission: dict = {}        # (region, ssid, start, dest) -> [Record] (every policy)
        self.by_region: dict = {}         # region -> [Record]
        self.kit_candidate_id = None      # executed kit candidate named in the recorded source paths
        self.forecast_paths: dict = {}    # (region, tag) -> Path
        self._fc_cache: OrderedDict = OrderedDict()
        self._fc_lock = threading.Lock()
        self._load()

    # -------------------------------------------------------------------------------------------- loading
    def _issue(self, msg: str) -> None:
        self.issues.append(msg)

    def _read_json(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def _load(self) -> None:
        if not self.root.is_dir():
            self._issue("fixtures directory %s does not exist (the data builder generates planner/mock_api/fixtures/)" % self.root)
            return
        self._load_manifest()
        self._load_regions()
        for rid in self.regions:
            self._load_nodes(rid)
            self._find_forecasts(rid)
        self._load_records()

    def _load_manifest(self) -> None:
        mp = self.root / "MANIFEST.json"
        if not mp.is_file():
            self._issue("MANIFEST.json missing: fixture provenance cannot be verified")
            return
        try:
            self.manifest = self._read_json(mp)
        except (OSError, ValueError) as e:
            self._issue("MANIFEST.json unreadable: %s" % e)
            return
        bad = []
        for f in self.manifest.get("files") or []:
            rel = f.get("path") if isinstance(f, dict) else None
            if not rel:
                continue
            cands = [self.root / rel, PLANNER.parent / rel, PLANNER / rel]
            p = next((c for c in cands if c.is_file()), None)
            if p is None:
                bad.append("%s missing" % rel)
            elif isinstance(f.get("bytes"), int) and p.stat().st_size != f["bytes"]:
                bad.append("%s has %d bytes, MANIFEST says %d" % (rel, p.stat().st_size, f["bytes"]))
        if bad:
            self._issue("MANIFEST.json does not match the fixture files (%d): %s" % (len(bad), "; ".join(bad[:5])))

    def _load_regions(self) -> None:
        rp = self.root / "regions.json"
        if not rp.is_file():
            self._issue("regions.json missing: no region is served")
            return
        try:
            doc = self._read_json(rp)
            regions = doc["regions"]
            assert isinstance(regions, list)
        except Exception as e:  # noqa: BLE001 - reported, never served half-loaded
            self._issue("regions.json unreadable: %s: %s" % (type(e).__name__, e))
            return
        self.regions_doc = doc
        for r in regions:
            rid = r.get("id") if isinstance(r, dict) else None
            if not isinstance(rid, str):
                self._issue("regions.json has a region without an id")
                continue
            self.regions[rid] = r
            self.sets[rid] = {}
            for s in r.get("scenario_sets") or []:
                try:
                    tag = normalize_input_time(s["input_time"])
                    ssid = s["scenario_set_id"]
                    float(s["horizon_s"])
                except (KeyError, TypeError, ValueError, ApiError) as e:
                    self._issue("region %s: invalid scenario set %r (%s)" % (rid, s, e))
                    continue
                self.sets[rid][ssid] = s
                self.set_tag[(rid, ssid)] = tag
                self.sets_at.setdefault((rid, tag), []).append(s)
            for t in r.get("input_times") or []:
                try:
                    tag = normalize_input_time(t)
                except ApiError:
                    self._issue("region %s: invalid input time %r" % (rid, t))
                    continue
                if (rid, tag) not in self.sets_at:
                    self._issue("region %s: input time %s has no scenario set" % (rid, tag_to_iso(tag)))

    def _load_nodes(self, rid: str) -> None:
        p = self.root / "nodes" / ("%s.json" % rid)
        if not p.is_file():
            self._issue("nodes/%s.json missing: route checks in %s return 503 DATA_UNAVAILABLE" % (rid, rid))
            return
        try:
            self.nodes[rid] = NodeTable(self._read_json(p))
        except Exception as e:  # noqa: BLE001
            self._issue("nodes/%s.json unreadable: %s: %s" % (rid, type(e).__name__, e))

    def _find_forecasts(self, rid: str) -> None:
        tags = sorted({tag for (r, tag) in self.sets_at if r == rid})
        missing = []
        for tag in tags:
            p = self.root / "forecast" / rid / ("%s.json" % tag)
            if p.is_file():
                self.forecast_paths[(rid, tag)] = p
            else:
                missing.append(tag_to_iso(tag))
        if missing:
            self._issue("forecast fixtures missing for %s at %s" % (rid, ", ".join(missing)))

    def _load_records(self) -> None:
        rdir = self.root / "records"
        if not rdir.is_dir():
            self._issue("records/ missing: every route check is unresolved (%s)" % MOCK_NO_RECORD)
            return
        for path in sorted(rdir.rglob("*.json")):
            try:
                rec = self._parse_record(path, self._read_json(path))
            except Exception as e:  # noqa: BLE001
                self._issue("record %s skipped: %s: %s" % (path.relative_to(self.root), type(e).__name__, e))
                continue
            if rec is None:
                continue
            key = (rec.region, rec.ssid, rec.policy, rec.start, rec.dest)
            for other in self.by_key.get(key, []):
                if self._diff(other, self._rec_query(rec)) == []:
                    self._issue("records %s and %s describe the same request; %s is served"
                                % (other.label(), rec.label(), other.label()))
            self.records.append(rec)
            self.by_key.setdefault(key, []).append(rec)
            self.by_mission.setdefault((rec.region, rec.ssid, rec.start, rec.dest), []).append(rec)
            self.by_region.setdefault(rec.region, []).append(rec)
            if self.kit_candidate_id is None:
                for s in rec.doc.get("source_records") or []:
                    m = _KIT_RE.search(str((s or {}).get("path") or "")) if isinstance(s, dict) else None
                    if m:
                        self.kit_candidate_id = m.group(1)
                        break

    def recorded_missions(self, rid: str) -> list:
        """Recorded final-panel missions of a region (GET /regions ``recorded_missions``, as the real API lists them)."""
        keys = sorted({(r.case_id, r.tag) for r in self.by_region.get(rid, ())})
        return [{"mission": c, "input_time": tag_to_iso(t)} for c, t in keys]

    def _parse_record(self, path: Path, doc: dict):
        req, out = doc["request"], doc["outcome"]
        rec = Record()
        rec.doc, rec.path = doc, path
        rec.region, rec.case_id, rec.policy = doc["region_id"], str(doc["case_id"]), doc["policy"]
        rec.ssid = doc["scenario_set_id"]
        rec.tag = normalize_input_time(doc["input_time"])
        rec.source_arm, rec.repetition = doc.get("source_arm"), doc.get("repetition")
        if rec.policy not in POLICIES:
            raise ValueError("unknown policy %r" % rec.policy)
        if path.stem != rec.label():
            self._issue("record %s: file name does not match %s.json" % (path.relative_to(self.root), rec.label()))
        if rec.region not in self.regions:
            raise ValueError("region %r is not in regions.json" % rec.region)
        sset = self.sets[rec.region].get(rec.ssid)
        if sset is None:
            raise ValueError("scenario set %r is not in regions.json" % rec.ssid)
        if self.set_tag[(rec.region, rec.ssid)] != rec.tag:
            raise ValueError("scenario set %s is not recorded at %s" % (rec.ssid, tag_to_iso(rec.tag)))
        rec.start, rec.dest = req["origin_node"], req["destination_node"]
        rec.depart, rec.dwell = req["depart_offset_s"], req["dwell_s"]
        horizon = req.get("horizon_s", sset["horizon_s"])
        win = req.get("destination_window")
        rec.window = list(win) if win is not None else [_valid_from(sset), horizon]
        lim = req["limits"]
        rec.peak, rec.dose = lim["peak_kw_m2"], lim["dose_kj_m2"]
        rec.incurred = req.get("incurred_dose_kj_m2", 0)
        if rec.incurred is None:
            self._issue("record %s has incurred_dose_kj_m2 null (not uniform over members); no request can match it" % rec.label())
        for name in ("depart", "dwell", "peak", "dose"):
            if not _is_num(getattr(rec, name)):
                raise ValueError("request field %s is not a number" % name)
        rec.verdict = out["verdict"]
        if rec.verdict not in VERDICTS:
            raise ValueError("unknown verdict %r" % rec.verdict)
        if rec.verdict == CHECKED and not isinstance(doc.get("route"), dict):
            self._issue("record %s is checked_route but has no route" % rec.label())
        rec.route = None
        if rec.verdict == CHECKED and isinstance(doc.get("route"), dict):
            try:
                rec.route = served_route(doc["route"])
            except (KeyError, TypeError, ValueError) as e:
                rec.route = doc["route"]
                self._issue("record %s: route served as recorded (cannot apply the API vertex rule: %s)" % (rec.label(), e))
        rec.fpa = full_policy_assessment(rec) if rec.verdict == CHECKED and rec.policy != "full" else None
        if rec.region in self.nodes:
            table = self.nodes[rec.region]
            for role, nid in (("origin", rec.start), ("destination", rec.dest)):
                i = table.index.get(nid)
                if i is None:
                    self._issue("record %s: %s node %s is not in nodes/%s.json" % (rec.label(), role, nid, rec.region))
                elif not table.allowed[i]:
                    self._issue("record %s: %s node %s is not allowed (%s), so its request cannot be posed"
                                % (rec.label(), role, nid, table.allowed_rule or "node table"))
        return rec

    # -------------------------------------------------------------------------------------------- matching
    @staticmethod
    def _rec_query(rec: Record) -> dict:
        return {"region": rec.region, "tag": rec.tag, "ssid": rec.ssid, "policy": rec.policy, "start": rec.start,
                "dest": rec.dest, "depart": rec.depart, "dwell": rec.dwell, "window": rec.window, "peak": rec.peak,
                "dose": rec.dose, "incurred": rec.incurred}

    @staticmethod
    def _diff(rec: Record, q: dict) -> list:
        """Fields (name, requested, recorded) in which request q differs from recorded execution rec."""
        d = []
        if rec.tag != q["tag"]:
            d.append(("input_time", tag_to_iso(q["tag"]), tag_to_iso(rec.tag)))
        if rec.ssid != q["ssid"]:
            d.append(("fire_input.scenario_set_id", q["ssid"], rec.ssid))
        if rec.start != q["start"]:
            d.append(("start node", q["start"], rec.start))
        if rec.dest != q["dest"]:
            d.append(("destination node", q["dest"], rec.dest))
        if not num_eq(rec.depart, q["depart"]):
            d.append(("depart_offset_s", q["depart"], rec.depart))
        if not num_eq(rec.dwell, q["dwell"]):
            d.append(("dwell_s", q["dwell"], rec.dwell))
        if not (len(rec.window) == 2 and num_eq(rec.window[0], q["window"][0]) and num_eq(rec.window[1], q["window"][1])):
            d.append(("destination_window", list(q["window"]), list(rec.window)))
        if rec.policy != q["policy"]:
            d.append(("policy", q["policy"], rec.policy))
        if not (num_eq(rec.peak, q["peak"]) and num_eq(rec.dose, q["dose"])):
            d.append(("limits", {"peak_kw_m2": q["peak"], "dose_kj_m2": q["dose"]},
                      {"peak_kw_m2": rec.peak, "dose_kj_m2": rec.dose}))
        if not num_eq(rec.incurred, q["incurred"]):
            d.append(("incurred_dose_kj_m2", q["incurred"], rec.incurred))
        return d

    def match(self, q: dict):
        for rec in self.by_key.get((q["region"], q["ssid"], q["policy"], q["start"], q["dest"]), ()):
            if not self._diff(rec, q):
                return rec
        return None

    def mission_match(self, q: dict):
        """case_id of the recorded mission whose request q restates in every compared field except the policy: the
        real API's provenance.recorded_mission_match (its built request equals the mission's request file, which
        every policy shares), else None."""
        for rec in self.by_mission.get((q["region"], q["ssid"], q["start"], q["dest"]), ()):
            if all(name == "policy" for name, _, _ in self._diff(rec, q)):
                return rec.case_id
        return None

    def explain(self, q: dict) -> str:
        """Why request q matches no recorded execution (names the closest recorded execution and its differences)."""
        recs = self.by_region.get(q["region"], [])
        head = "MOCK: no recorded execution matches this request; nothing was computed. "
        if not recs:
            return head + "No recorded executions are loaded for region %s." % q["region"]
        scored = sorted(((self._diff(r, q), str(r.path)) for r in recs), key=lambda x: (len(x[0]), x[1]))
        diff, path = scored[0]
        closest = next(r for r in recs if str(r.path) == path)
        parts = ["%s (requested %s, recorded %s)" % (name, _short(a), _short(b)) for name, a, b in diff]
        return head + "Closest of the %d recorded executions for %s: %s, which differs in %s." % (
            len(recs), q["region"], closest.label(), "; ".join(parts))

    # -------------------------------------------------------------------------------------------- forecast
    def _north_up(self, rid: str, doc: dict) -> dict:
        """The fixture numbers ForecastCell rows from the SOUTH edge (graph cell convention, fixtures MANIFEST.json);
        the real API (api/forecast.py) numbers them north-up (row 0 = northern edge) and adds a ``grid`` block. Same
        cells, polygons and values: only ``row`` and ``id`` are re-numbered; ``cell`` keeps the graph index."""
        g = (self.regions.get(rid) or {}).get("grid") or {}
        try:
            h, w, res = int(g["height"]), int(g["width"]), float(g["resolution_m"])
            x0, y0 = float(g["x0"]), float(g["y0"])
        except (KeyError, TypeError, ValueError):
            self._issue("forecast for %s: regions.json grid incomplete; rows served as in the fixture" % rid)
            return doc
        feats = []
        for f in doc.get("features") or []:
            p = dict(f.get("properties") or {})
            if isinstance(p.get("row"), int) and isinstance(p.get("col"), int):
                p["row"] = h - 1 - p["row"]
                f = dict(f, id="r%dc%d" % (p["row"], p["col"]), properties=p)
            feats.append(f)
        out = dict(doc, features=feats)
        out["grid"] = {"crs": "EPSG:5179", "resolution_m": res, "rows": h, "cols": w,
                       "affine_transform": [res, 0.0, x0, 0.0, -res, y0 + h * res],
                       "row_order": "north-up (row 0 is the northern edge)",
                       "cell_index": "properties.cell (MOCK extension) is the graph cell row_south * cols + col"}
        return out

    def forecast_doc(self, rid: str, tag: str) -> dict:
        key = (rid, tag)
        with self._fc_lock:
            doc = self._fc_cache.get(key)
            if doc is not None:
                self._fc_cache.move_to_end(key)
                return doc
        doc = self._north_up(rid, self._read_json(self.forecast_paths[key]))
        with self._fc_lock:
            self._fc_cache[key] = doc
            while len(self._fc_cache) > 4:
                self._fc_cache.popitem(last=False)
        return doc


def _valid_from(sset: dict) -> float:
    for k in ("valid_from_s", "valid_from"):
        if _is_num(sset.get(k)):
            return sset[k]
    return 0


_KIT_RE = re.compile(r"(WFG-latest-completion-kit-[0-9]{8}-v[0-9]+)")
SERVED_VERTEX_RULE = ("Route-Check API vertex rule (api/runner.py route_feature): the origin, one vertex per EDGE leg "
                      "end, and one vertex at the end of each run of consecutive WAIT legs; node_ids has one entry per "
                      "vertex; segment_count counts EDGE legs, legs_total all legs. MOCK: re-expressed from the recorded "
                      "route (recorded positions and times; only intermediate 1 s wait vertices are dropped).")


def served_route(route: dict) -> dict:
    """A recorded route (ARCHITECTURE.md 4.1: one vertex per leg end, so a wait of n 1 s WAIT legs adds n vertices;
    node_ids either per vertex or the origin plus each EDGE leg's end node) in the real API's layout. Raises ValueError
    when the recorded vertices cannot be attributed to EDGE and WAIT legs unambiguously."""
    geom = route["geometry"]
    coords = geom["coordinates"]
    props = route["properties"]
    times = props["times_s"]
    ids = list(props.get("node_ids") or [])
    edges = list(props.get("edge_ids") or [])
    waits = [w for w in props.get("waits") or [] if isinstance(w, dict)]
    n = len(coords)
    if n == 0 or len(times) != n:
        raise ValueError("coordinates and times_s differ in length")

    def waiting(node, i) -> bool:
        return coords[i] == coords[i - 1] and any(w.get("node_id") == node and w["from_s"] < times[i] <= w["to_s"]
                                                  for w in waits)
    per_vertex = len(ids) == n
    if not per_vertex and len(ids) != len(edges) + 1:
        raise ValueError("node_ids is neither per vertex nor per EDGE leg end")
    out_c, out_t, out_n = [coords[0]], [times[0]], [ids[0]]
    cur, k, pending = ids[0], 0, None
    for i in range(1, n):
        if waiting(cur, i) and (not per_vertex or ids[i] == cur):
            pending = i                       # inside a run of WAIT legs: keep only its last vertex
            continue
        if pending is not None:
            out_c.append(coords[pending]); out_t.append(times[pending]); out_n.append(cur)
            pending = None
        k += 1
        if per_vertex:
            cur = ids[i]
        else:
            if k >= len(ids):
                raise ValueError("more EDGE vertices than recorded EDGE legs")
            cur = ids[k]
        out_c.append(coords[i]); out_t.append(times[i]); out_n.append(cur)
    if pending is not None:
        out_c.append(coords[pending]); out_t.append(times[pending]); out_n.append(cur)
    if not per_vertex and k != len(ids) - 1:
        raise ValueError("EDGE vertices do not match the recorded EDGE legs")
    legs_total = props.get("segment_count")
    p = dict(props)
    p.update({"times_s": out_t, "node_ids": out_n, "segment_count": k,
              "legs_total": legs_total if isinstance(legs_total, int) else n - 1, "vertex_rule": SERVED_VERTEX_RULE})
    if edges and len(edges) != k:
        raise ValueError("edge_ids do not match the EDGE vertices")
    return {"type": "Feature", "geometry": dict(geom, coordinates=out_c), "properties": p}


def full_policy_assessment(rec) -> dict:
    """The recorded full-hazard grade of a reduced-policy route in the real API's full_policy_assessment layout
    (api/runner.py), plus the record's own fields. Nothing is recomputed: violations are the recorded failure
    components (attributed to scenarios only where the recorded member values identify them), per_scenario is the
    recorded offline full-model centre check, and passes_selected_policy applies the API's rule to those components."""
    doc = rec.doc
    fpc = doc.get("full_policy_check") if isinstance(doc.get("full_policy_check"), dict) else {}
    fme = doc.get("full_model_exposure") if isinstance(doc.get("full_model_exposure"), dict) else {}
    members = [m for m in fme.get("members") or [] if isinstance(m, dict) and isinstance(m.get("scenario_id"), str)]
    comps = [str(c) for c in fpc.get("failure_components") or []]
    passed = fpc.get("pass") if isinstance(fpc.get("pass"), bool) else None
    violations = []
    for c in comps:
        if c == "FLAME":
            hit = [m["scenario_id"] for m in members if m.get("contact") is True]
        elif c == "PEAK":
            hit = [m["scenario_id"] for m in members if _is_num(m.get("peak_kw_m2")) and m["peak_kw_m2"] > rec.peak]
        elif c == "DOSE":
            hit = [m["scenario_id"] for m in members if _is_num(m.get("dose_kj_m2")) and m["dose_kj_m2"] > rec.dose]
        else:
            hit = []
        violations += [{"scenario_id": s, "constraint": c} for s in hit] or [{"scenario_id": None, "constraint": c}]
    if passed is True:
        passes_full = True
    elif passed is False and {"FLAME", "PEAK", "DOSE", "WHOLE_ROAD_CONTACT"} & set(comps):
        passes_full = False
    else:
        passes_full = None
    enabled = POLICY_ENABLED.get(rec.policy, frozenset())
    if passed is None:
        own = True if not enabled else None
    else:
        own = not (enabled & set(comps)) and not ("FLAME" in enabled and "WHOLE_ROAD_CONTACT" in comps)
    own_exposure = [m for m in doc.get("exposure") or [] if isinstance(m, dict)]
    return {"passes_full_centre_and_contact": passes_full, "grammar_ok": None,
            "whole_road_contact": fme.get("independent_contact_status"), "violations": violations,
            "per_scenario": {m["scenario_id"]: {"peak_kw_m2": m.get("peak_kw_m2"), "dose_kj_m2": m.get("dose_kj_m2"),
                                                "contact": m.get("contact")} for m in members},
            "scope": fme.get("scope"), "passes_selected_policy": own,
            "pass": passed, "failure_components": fpc.get("failure_components"), "source": fpc.get("source"),
            "full_model_exposure_scope": fme.get("scope"),
            "independent_contact_status": fme.get("independent_contact_status"),
            "full_whole_status": fme.get("full_whole_status"),
            "policy_exposure": {"scope": doc.get("exposure_scope"), "members": own_exposure},
            "recorded": True, "charged_to_compute_s": False,
            "note": "MOCK: recorded ablation dual-policy grade of this route (grammar_ok was not recorded: null)."}


# ---------------------------------------------------------------------------------------------------- jobs
class FireContext:
    """Resolved fire input shared by one route check or all attempts of one dispatch plan."""

    __slots__ = ("type", "sset", "tag", "horizon", "valid_from", "fire", "assumptions", "zones_sha256", "zones_count")


class RouteJob:
    __slots__ = ("job_id", "created", "created_wall", "start_after", "done_after", "request", "snap", "region",
                 "ctx", "query", "record", "mission", "parent", "provenance", "_reason", "_outcome")


class PlanJob:
    __slots__ = ("job_id", "created", "created_wall", "start_after", "done_after", "request", "region", "ctx",
                 "origins", "rejected", "dests", "attempt_jobs", "total", "provenance", "limits", "_result", "_lock")


class JobStore:
    def __init__(self, max_jobs: int = MAX_JOBS):
        self._lock = threading.Lock()
        self._jobs: OrderedDict = OrderedDict()
        self._max = max_jobs
        self.counts = {"route_check": 0, "dispatch_plan": 0}

    def add(self, job) -> None:
        self.add_many([job])

    def add_many(self, jobs) -> None:
        with self._lock:
            for job in jobs:
                self._jobs[job.job_id] = job
                self.counts["route_check" if isinstance(job, RouteJob) else "dispatch_plan"] += 1
            while len(self._jobs) > self._max:
                self._jobs.popitem(last=False)

    def get(self, job_id: str):
        with self._lock:
            return self._jobs.get(job_id)


def new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:20])


def _git_head() -> str:
    try:
        out = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        s = out.stdout.strip()
        return s if out.returncode == 0 and s else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


class Response:
    __slots__ = ("status", "ctype", "body", "headers")

    def __init__(self, status: int, ctype, body: bytes, headers=None):
        self.status, self.ctype, self.body, self.headers = status, ctype, body, headers or {}


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _json(status: int, obj, ctype="application/json; charset=utf-8", headers=None) -> Response:
    return Response(status, ctype, _json_bytes(obj), headers)


# ---------------------------------------------------------------------------------------------------- the mock API
class MockApi:
    def __init__(self, fixtures_dir=None, *, queued_s: float = DEFAULT_QUEUED_S, done_s: float = DEFAULT_DONE_S,
                 quiet: bool = False, max_jobs: int = MAX_JOBS):
        if not (0 <= queued_s <= done_s):
            raise ValueError("need 0 <= queued_s <= done_s")
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir is not None else HERE / "fixtures"
        self.fx = Fixtures(self.fixtures_dir)
        self.queued_s, self.done_s = float(queued_s), float(done_s)
        self.quiet = quiet
        self.jobs = JobStore(max_jobs)
        self.git_commit = _git_head()
        self.started_at = utc_now()

    # -------------------------------------------------------------------------------------------- logging
    def log(self, msg: str) -> None:
        if not self.quiet:
            sys.stderr.write("[wfg-mock] %s\n" % msg)
            sys.stderr.flush()

    # -------------------------------------------------------------------------------------------- routing
    def handle(self, method: str, raw_path: str, body: bytes = b"", headers=None) -> Response:
        try:
            return self._route(method, raw_path, body, headers or {})
        except ApiError as e:
            return self.error_response(e)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return self.error_response(ApiError(500, "INTERNAL_ERROR", "%s: %s" % (type(e).__name__, e)))

    def error_response(self, e: ApiError) -> Response:
        """Error envelope with provenance (contract v1.3: every response carries provenance)."""
        return _json(e.status, dict(e.body(), provenance=self._prov(host=NOT_COMPUTED_HOST)), headers=e.headers)

    @staticmethod
    def _query_error(loc: str, kind: str, msg: str, value):
        """422 for a bad query parameter, with the real API's (FastAPI/pydantic) details layout."""
        return _unprocessable("VALIDATION_ERROR", "invalid request parameters",
                              [{"type": kind, "loc": ["query", loc], "msg": msg, "input": value}])

    def _query_value(self, query: dict, name: str, required: bool = True):
        vals = query.get(name)
        if not vals:
            if required:
                raise self._query_error(name, "missing", "Field required", None)
            return None
        return vals[-1]

    def _query_bool(self, query: dict, name: str, default: bool) -> bool:
        raw = self._query_value(query, name, required=False)
        if raw is None:
            return default
        v = raw.lower()
        if v in ("1", "on", "t", "true", "y", "yes"):
            return True
        if v in ("0", "off", "f", "false", "n", "no"):
            return False
        raise self._query_error(name, "bool_parsing", "Input should be a valid boolean, unable to interpret input", raw)

    def _route(self, method: str, raw_path: str, body: bytes, headers) -> Response:
        parts = urlsplit(raw_path)
        segs = [unquote(s) for s in parts.path.split("/") if s != ""]
        query = parse_qs(parts.query, keep_blank_values=True)

        def allow(methods: tuple):
            if method == "OPTIONS":
                raise _Preflight()
            if method not in methods and not (method == "HEAD" and "GET" in methods):
                raise ApiError(405, "METHOD_NOT_ALLOWED", "%s is not allowed on %s" % (method, parts.path),
                               {"allowed": list(methods)}, headers={"Allow": ", ".join(methods + ("OPTIONS",))})

        try:
            if not segs or segs == ["v1"]:
                allow(("GET",))
                return _json(200, self.index())
            if segs in (["openapi.yaml"], ["v1", "openapi.yaml"]):
                allow(("GET",))
                if not CONTRACT_PATH.is_file():
                    raise ApiError(404, "NOT_FOUND", "contract copy not found")
                return Response(200, "application/yaml; charset=utf-8", CONTRACT_PATH.read_bytes())
            if segs[0] != "v1":
                raise ApiError(404, "NOT_FOUND", "no such path %s (the API lives under /v1)" % parts.path)
            rest = segs[1:]
            n = len(rest)
            if rest == ["health"]:
                allow(("GET",))
                return _json(200, self.health())
            if rest == ["regions"]:
                allow(("GET",))
                return _json(200, self.list_regions())
            if n == 3 and rest[0] == "regions" and rest[2] == "forecast":
                allow(("GET",))
                return self.forecast(rest[1], query, headers)
            if rest == ["route-checks"]:
                allow(("POST",))
                return _json(202, *self.create_route_check(self._parse_body(body)))
            if n == 2 and rest[0] == "route-checks":
                allow(("GET",))
                return _json(200, self.get_route_check(rest[1]))
            if n == 3 and rest[0] == "route-checks" and rest[2] == "export":
                allow(("GET",))
                return self.export(rest[1], query)
            if rest == ["dispatch-plans"]:
                allow(("POST",))
                return _json(202, *self.create_dispatch(self._parse_body(body)))
            if n == 2 and rest[0] == "dispatch-plans":
                allow(("GET",))
                return _json(200, self.get_dispatch(rest[1]))
            if method == "OPTIONS":
                raise _Preflight()
            raise ApiError(404, "NOT_FOUND", "no such path %s" % parts.path, {"endpoints": [p for _, p, _, _ in ENDPOINTS]})
        except _Preflight:
            return Response(204, None, b"")

    @staticmethod
    def _parse_body(body: bytes):
        def _reject(name):
            raise ValueError("%s is not valid JSON" % name)
        if not body:
            raise _unprocessable("VALIDATION_ERROR", "request body is required (JSON object)")
        try:
            return json.loads(body.decode("utf-8"), parse_constant=_reject)
        except (UnicodeDecodeError, ValueError) as e:
            raise _unprocessable("VALIDATION_ERROR", "request body is not valid JSON: %s" % e)

    @staticmethod
    def _validate(body, component: str) -> None:
        errs = schema_errors(body, component)
        if errs:
            raise _unprocessable("VALIDATION_ERROR", "request body does not match %s" % component, errs[:20])

    # -------------------------------------------------------------------------------------------- provenance
    def _prov(self, *, region_id=None, tag=None, fire_type=None, policy=None, scenario_set_id=None, scenario_ids=(),
              input_hashes=None, evaluated=None, approximation=None, clock=None, host=None, generated_at=None,
              extra=None) -> dict:
        region = self.fx.regions.get(region_id) or {}
        p = {"api_version": API_VERSION, "package": PACKAGE, "package_version": PACKAGE_VERSION, "kit": KIT,
             "kit_candidate_id": self.fx.kit_candidate_id,
             "checkpoint": CHECKPOINT, "git_commit": self.git_commit, "git_dirty": None,
             "region": region_id, "input_time": tag_to_iso(tag) if tag else None,
             "graph_id": region.get("graph_id") if region_id else None,
             "input_hashes": {k: v for k, v in (input_hashes or {}).items() if isinstance(v, str)},
             "scenario_set_id": scenario_set_id, "scenario_ids": [s for s in scenario_ids if isinstance(s, str)],
             "fire_input_type": fire_type, "policy": policy, "evaluated_configuration": evaluated,
             "approximation": approximation, "clock": clock, "host": host,
             "generated_at": iso_ms(generated_at or utc_now()), "mock": True}
        if region_id:
            p.update({"budget_s": BUDGET_S, "workers": MOCK_WORKERS})
        if extra:
            p.update(extra)
        return p

    @staticmethod
    def _default_limits(peak, dose, incurred) -> bool:
        return num_eq(peak, DEFAULT_PEAK_KW_M2) and num_eq(dose, DEFAULT_DOSE_KJ_M2) and num_eq(incurred, 0)

    def _job_prov(self, region_id: str, ctx, policy: str, peak, dose, incurred, generated_at=None) -> dict:
        """Provenance known when a job is accepted (contract v1.4; real API _job_prov): the inputs it will use.
        evaluated_configuration is true or null here; the finished result carries the full record."""
        recorded = ctx.type == "recorded"
        return self._prov(region_id=region_id, tag=ctx.tag, fire_type=ctx.type, policy=policy,
                          scenario_set_id=ctx.sset["scenario_set_id"] if recorded else None,
                          scenario_ids=(ctx.sset.get("scenario_ids") or ()) if recorded else (),
                          input_hashes=self._region_hashes(region_id, ctx.sset if recorded else None),
                          evaluated=(recorded and policy == "full" and self._default_limits(peak, dose, incurred)) or None,
                          approximation=APPROXIMATION if not recorded else None, clock=None, host=NOT_COMPUTED_HOST,
                          generated_at=generated_at)

    def _route_job_prov(self, job) -> dict:
        if job.provenance is None:
            q = job.query
            job.provenance = self._job_prov(job.region, job.ctx, job.request["policy"], q["peak"], q["dose"],
                                            q["incurred"], generated_at=job.created_wall)
        return job.provenance

    def _fixture_prov(self, base) -> dict:
        """Provenance stored in a fixture (regions.json, forecast) as served: api_version follows the contract version
        this mock serves (v1.3); the version recorded at fixture generation is kept as fixture_api_version."""
        p = self._prov(host=NOT_COMPUTED_HOST)
        if isinstance(base, dict):
            p.update(base)
            if base.get("api_version") not in (None, API_VERSION):
                p["fixture_api_version"] = base["api_version"]
        p["api_version"] = API_VERSION
        p["mock"] = True
        return p

    def _region_hashes(self, region_id: str, sset=None) -> dict:
        r = self.fx.regions.get(region_id) or {}
        h = {}
        if isinstance(r.get("graph_sha256"), str):
            h["graph"] = r["graph_sha256"]
        if sset is not None and isinstance(sset.get("hazard_sha256"), str):
            h["hazard"] = sset["hazard_sha256"]
        return h

    # -------------------------------------------------------------------------------------------- system
    def index(self) -> dict:
        return {"service": "WildfireGuardian Route-Check API (MOCK)", "mode": "mock", "mock": True,
                "api_version": API_VERSION, "base_path": "/v1",
                "contract": "planner/contract/wfg_api_v1.yaml (served at /openapi.yaml)",
                "endpoints": [{"method": m, "path": p, "operation_id": o, "summary": s} for m, p, o, s in ENDPOINTS],
                "honesty": "The MOCK computes nothing: it serves recorded results only for requests that exactly restate "
                           "a recorded execution; everything else is unresolved (never safe).",
                "fixtures": str(self.fixtures_dir)}

    def health(self) -> dict:
        fx = self.fx
        issues = list(fx.issues)
        graphs = {"%s/graph" % rid: r["graph_sha256"] for rid, r in sorted(fx.regions.items())
                  if isinstance(r.get("graph_sha256"), str)}
        return {"status": "ok" if fx.regions and not issues else "degraded", "api_version": API_VERSION,
                "package": PACKAGE, "package_version": PACKAGE_VERSION, "kit": KIT, "checkpoint": CHECKPOINT,
                "git_commit": self.git_commit, "regions": sorted(fx.regions), "workers": MOCK_WORKERS,
                "data_root": str(self.fixtures_dir), "issues": issues, "mode": "mock", "mock": True,
                "budget_s": BUDGET_S, "jobs": dict(self.jobs.counts), "queued_tasks": 0, "pool_restarts": 0,
                "kit_candidate_id": fx.kit_candidate_id, "git_dirty": None,
                "fixtures": {"manifest": fx.manifest is not None,
                             "generated_at": (fx.manifest or {}).get("generated_at"),
                             "records": len(fx.records),
                             "records_by_policy": {p: sum(r.policy == p for r in fx.records) for p in POLICIES},
                             "node_tables": sorted(fx.nodes), "forecasts": len(fx.forecast_paths)},
                "started_at": iso_ms(self.started_at),
                "provenance": self._prov(input_hashes=graphs, host=NOT_COMPUTED_HOST)}

    def _require_data(self) -> None:
        """503 DATA_UNAVAILABLE when no region is loaded (real API _require_data; contract v1.2 for the read paths)."""
        if not self.fx.regions:
            raise ApiError(503, "DATA_UNAVAILABLE", "no MOCK fixtures are loaded (planner/tools/build_fixtures.py "
                           "generates planner/mock_api/fixtures/)", {"issues": self.fx.issues})

    def list_regions(self) -> dict:
        self._require_data()
        doc = dict(self.fx.regions_doc)
        doc["regions"] = [dict(self.fx.regions[rid], recorded_missions=self.fx.recorded_missions(rid))
                          for rid in sorted(self.fx.regions)]
        doc["provenance"] = self._fixture_prov(self.fx.regions_doc.get("provenance"))
        return doc

    # -------------------------------------------------------------------------------------------- forecast
    def forecast(self, region_id: str, query: dict, headers) -> Response:
        fx = self.fx
        # real API order: query parameters (FastAPI) -> 503 -> 404 region -> input time -> 404 time -> 422 forecast
        raw_time = self._query_value(query, "input_time")
        only = self._query_bool(query, "only_nonzero", False)
        self._require_data()
        if region_id not in fx.regions:
            raise ApiError(404, "UNKNOWN_REGION", "region %r is not available" % region_id, {"available": sorted(fx.regions)})
        tag = normalize_input_time(raw_time)
        available = sorted(t for (r, t) in fx.sets_at if r == region_id)
        if tag not in available:
            raise ApiError(404, "INPUT_TIME_UNAVAILABLE", "no recorded input for %s at %s" % (region_id, tag_to_iso(tag)),
                           {"available": [tag_to_iso(t) for t in available]})
        if (region_id, tag) not in fx.forecast_paths:
            raise _unprocessable("FORECAST_UNAVAILABLE", "no recorded forecast fixture for %s at %s" % (region_id, tag_to_iso(tag)),
                                 {"available": [tag_to_iso(t) for (r, t) in sorted(fx.forecast_paths) if r == region_id]})
        doc = fx.forecast_doc(region_id, tag)
        out = dict(doc)
        feats = doc.get("features") or []
        if only:
            feats = [f for f in feats if (_is_num((f.get("properties") or {}).get("p_new_burn_1h"))
                                          and f["properties"]["p_new_burn_1h"] > 0)
                     or (f.get("properties") or {}).get("burning_now") is True]
        out["features"] = feats
        prov = self._fixture_prov(doc.get("provenance"))
        prov.setdefault("region", region_id)
        prov.setdefault("input_time", tag_to_iso(tag))
        out["provenance"] = prov
        accept = (headers.get("Accept") if hasattr(headers, "get") else None) or ""
        ctype = "application/json; charset=utf-8" if ("application/json" in accept and "geo+json" not in accept) \
            else "application/geo+json; charset=utf-8"
        return _json(200, out, ctype=ctype)

    # -------------------------------------------------------------------------------------------- shared checks
    def _require_region(self, region_id: str) -> dict:
        self._require_data()
        r = self.fx.regions.get(region_id)
        if r is None:
            raise _unprocessable("UNKNOWN_REGION", "region %r is not available" % region_id, {"available": sorted(self.fx.regions)})
        if region_id not in self.fx.nodes:
            raise ApiError(503, "DATA_UNAVAILABLE", "the MOCK node table for %s is not loaded" % region_id,
                           {"issues": [i for i in self.fx.issues if region_id in i]})
        return r

    def _fire_context(self, region_id: str, tag: str, fire: dict) -> FireContext:
        fx = self.fx
        here = fx.sets_at.get((region_id, tag))
        if not here:
            raise _unprocessable("INPUT_TIME_UNAVAILABLE", "no recorded input for %s at %s" % (region_id, tag_to_iso(tag)),
                                 {"available": [tag_to_iso(t) for (r, t) in sorted(fx.sets_at) if r == region_id]})
        ctx = FireContext()
        ctx.tag, ctx.fire = tag, dict(fire)
        ctx.assumptions = ctx.zones_sha256 = ctx.zones_count = None
        if fire["type"] == "recorded":
            want = fx.sets[region_id].get(fire["scenario_set_id"])
            if want is None:
                raise _unprocessable("UNKNOWN_SCENARIO_SET", "scenario set %r is not recorded for %s" % (fire["scenario_set_id"], region_id),
                                     {"available": sorted(fx.sets[region_id])})
            if fx.set_tag[(region_id, fire["scenario_set_id"])] != tag:
                raise _unprocessable("SCENARIO_SET_TIME_MISMATCH", "scenario set %s belongs to input_time %s, not %s" % (
                    fire["scenario_set_id"], tag_to_iso(fx.set_tag[(region_id, fire["scenario_set_id"])]), tag_to_iso(tag)),
                    {"scenario_sets_at_input_time": [s["scenario_set_id"] for s in here]})
            ctx.type, ctx.sset = "recorded", want
        else:
            # v1.1 scope: input_time is a recorded input time of the region (checked above); v1.3: burning cells always
            # come from that recorded input, and burning_scenario_set_id is only a consistency check against it.
            ctx.type, ctx.sset = "spread_zones", here[0]
            bsid = fire.get("burning_scenario_set_id")
            if bsid is not None and bsid not in [s["scenario_set_id"] for s in here]:
                raise _unprocessable("SCENARIO_SET_TIME_MISMATCH", "burning_scenario_set_id must be the recorded scenario "
                                     "set at input_time (%s)" % ", ".join(s["scenario_set_id"] for s in here),
                                     {"burning_scenario_set_id": bsid,
                                      "scenario_sets_at_input_time": [s["scenario_set_id"] for s in here]})
            try:
                _parse_utc(fire["issued_at"])
            except (ValueError, TypeError):
                raise _unprocessable("INVALID_ZONES", "issued_at must be an ISO 8601 time with a time zone",
                                     {"issued_at": fire["issued_at"]})
            ctx.zones_count = self._check_zones(fx.regions[region_id], fire["zones"])
            ctx.zones_sha256 = hashlib.sha256(json.dumps(fire["zones"], sort_keys=True, separators=(",", ":"),
                                                         ensure_ascii=False).encode("utf-8")).hexdigest()
            ctx.fire.setdefault("margin_min", DEFAULT_MARGIN_MIN)
            ctx.fire.setdefault("burning_scenario_set_id", None)
            ctx.assumptions = {"mock": True, "evaluated": False, "text": dict(SPREAD_ZONES_TEXT),
                               "zones_received": ctx.zones_count}
        ctx.horizon = ctx.sset["horizon_s"]
        ctx.valid_from = _valid_from(ctx.sset)
        return ctx

    @staticmethod
    def _check_zones(region: dict, zones: dict) -> int:
        """The real adapter's structural checks (api/adapters/spread_zones.py). An empty feature list is accepted, as
        there (only the recorded present fire would remain); 'outside' is judged on the region bbox here, on the
        rasterised region grid there."""
        feats = zones["features"]
        bbox = region.get("bbox")
        outside = []
        for i, f in enumerate(feats):
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            xs, ys = [], []
            if not polys:
                raise _unprocessable("INVALID_ZONES", "zones.features[%d] has an empty geometry" % i)
            for poly in polys:
                if not isinstance(poly, list) or not poly:
                    raise _unprocessable("INVALID_ZONES", "zones.features[%d] has an empty polygon" % i)
                for ring in poly:
                    if not isinstance(ring, list) or len(ring) < 3:
                        raise _unprocessable("INVALID_ZONES", "each polygon ring needs at least 3 finite [lon, lat] positions "
                                             "(zones.features[%d])" % i)
                    for pos in ring:
                        if not (isinstance(pos, list) and 2 <= len(pos) <= 3 and all(_is_num(c) for c in pos)):
                            raise _unprocessable("INVALID_ZONES", "zones.features[%d]: positions must be [lon, lat] numbers" % i)
                        if abs(pos[0]) > 180 or abs(pos[1]) > 90:
                            raise _unprocessable("INVALID_ZONES", "zone coordinates must be WGS84 [lon, lat]")
                        xs.append(pos[0])
                        ys.append(pos[1])
            if isinstance(bbox, list) and len(bbox) == 4:
                w, s, e, n = bbox
                if max(xs) < w or min(xs) > e or max(ys) < s or min(ys) > n:
                    outside.append(i)
        if outside:
            raise _unprocessable("ZONES_OUTSIDE_REGION", "zone(s) %s lie entirely outside the region bbox" % outside,
                                 {"zones_outside": outside, "region_bbox_wgs84": bbox})
        return len(feats)

    def _snap(self, region_id: str, loc: dict, role: str) -> dict:
        table = self.fx.nodes[region_id]
        if "node_id" in loc:
            nid = loc["node_id"]
            i = table.index.get(nid)
            if i is None:
                raise _unprocessable("UNKNOWN_NODE", "%s node %r is not in the %s road graph" % (role, nid, region_id),
                                     {"role": role, "node_id": nid})
            if not table.allowed[i]:
                raise _unprocessable("NODE_NOT_ALLOWED", "%s node %r needs %s" % (role, nid, NODE_RULE),
                                     {"role": role, "node_id": nid})
            return {"node_id": nid, "distance_m": 0.0, "lon": table.lon[i], "lat": table.lat[i], "input": "node_id"}
        found = table.nearest(float(loc["lon"]), float(loc["lat"]))
        if found is None:
            raise ApiError(503, "DATA_UNAVAILABLE", "the MOCK node table for %s has no allowed node" % region_id)
        i, d = found
        if d > SNAP_MAX_M:
            raise _unprocessable("SNAP_TOO_FAR", "%s is %.1f m from the nearest allowed road node (limit %.0f m)" % (role, d, SNAP_MAX_M),
                                 {"role": role, "distance_m": round(d, 3), "nearest_node_id": table.ids[i],
                                  "limit_m": SNAP_MAX_M, "method": SNAP_METHOD})
        return {"node_id": table.ids[i], "distance_m": round(d, 3), "lon": table.lon[i], "lat": table.lat[i], "input": "lonlat"}

    @staticmethod
    def _request_params(ctx: FireContext, start_node: str, dest_node: str, depart, dwell, window, peak, dose, incurred) -> dict:
        """The real API's request checks (1 s time lattice, horizon, window, distinct nodes, satisfiable window)."""
        def lattice(v, name):
            f = float(v)
            if not math.isfinite(f) or f < 0 or not f.is_integer():
                raise _unprocessable("NOT_ON_TIME_LATTICE", "%s must be a non-negative whole number of seconds on the 1 s lattice"
                                     % name, {"field": name, "value": v})
            return int(f)
        depart = lattice(depart, "depart_offset_s")
        dwell = lattice(dwell, "dwell_s")
        horizon, vf = float(ctx.horizon), float(ctx.valid_from)
        if window is None:
            open_s, close_s = _num_out(vf), _num_out(horizon)
        else:
            open_s, close_s = lattice(window[0], "destination_window[0]"), lattice(window[1], "destination_window[1]")
        if not (vf <= depart <= horizon):
            raise _unprocessable("DEPARTURE_OUTSIDE_HORIZON", "depart_offset_s must lie within the hazard horizon [%g, %g] s" % (vf, horizon),
                                 {"depart_offset_s": depart, "horizon_s": _num_out(horizon)})
        if not (0 <= open_s < close_s <= horizon):
            raise _unprocessable("INVALID_WINDOW", "destination_window must satisfy 0 <= open_s < close_s <= %g" % horizon,
                                 {"destination_window": [open_s, close_s], "horizon_s": _num_out(horizon)})
        if start_node == dest_node:
            raise _unprocessable("START_EQUALS_DESTINATION", "start and destination snap to the same road node %s" % start_node,
                                 {"node_id": start_node})
        if max(depart, open_s) + dwell > min(close_s, horizon):
            raise _unprocessable("WINDOW_UNSATISFIABLE", "no arrival can satisfy max(depart, open_s) + dwell_s <= min(close_s, horizon)",
                                 {"depart_offset_s": depart, "destination_window": [open_s, close_s], "dwell_s": dwell,
                                  "horizon_s": _num_out(horizon)})
        if not (peak > 0 and dose > 0 and incurred >= 0):
            raise _unprocessable("INVALID_LIMITS", "limits must be positive and incurred dose non-negative",
                                 {"peak_kw_m2": peak, "dose_kj_m2": dose, "incurred_dose_kj_m2": incurred})
        return {"depart": depart, "dwell": dwell, "window": [open_s, close_s], "peak": peak, "dose": dose, "incurred": incurred}

    def _new_route_job(self, *, request, snap, region_id, ctx, params, created, created_wall, start_after, done_after,
                       parent=None, job_id=None, register=True) -> RouteJob:
        job = RouteJob()
        job.job_id = job_id or new_id("rc")
        job.created, job.created_wall = created, created_wall
        job.start_after, job.done_after = start_after, done_after
        job.request, job.snap, job.region, job.ctx, job.parent = request, snap, region_id, ctx, parent
        job._reason = job._outcome = None
        job.query = {"region": region_id, "tag": ctx.tag, "ssid": ctx.sset["scenario_set_id"], "policy": request["policy"],
                     "start": snap["start"]["node_id"], "dest": snap["destination"]["node_id"], "depart": params["depart"],
                     "dwell": params["dwell"], "window": params["window"], "peak": params["peak"], "dose": params["dose"],
                     "incurred": params["incurred"]}
        job.record = self.fx.match(job.query) if ctx.type == "recorded" else None
        job.mission = job.record.case_id if job.record is not None else (
            self.fx.mission_match(job.query) if ctx.type == "recorded" else None)
        job.provenance = None
        if register:
            self.jobs.add(job)
        return job

    # -------------------------------------------------------------------------------------------- route checks
    def create_route_check(self, body):
        # real API order: JSON + schema -> 503 data -> region -> input_time -> fire input -> snaps -> request checks
        self._validate(body, "RouteCheckRequest")
        region_id = body["region"]
        self._require_region(region_id)
        tag = normalize_input_time(body["input_time"])
        ctx = self._fire_context(region_id, tag, body["fire_input"])
        snap = {"start": self._snap(region_id, body["start"], "start"),
                "destination": self._snap(region_id, body["destination"], "destination")}
        lim = body.get("limits") or {}
        peak = lim.get("peak_kw_m2", DEFAULT_PEAK_KW_M2)
        dose = lim.get("dose_kj_m2", DEFAULT_DOSE_KJ_M2)
        incurred = body.get("incurred_dose_kj_m2", 0)
        params = self._request_params(ctx, snap["start"]["node_id"], snap["destination"]["node_id"],
                                      body.get("depart_offset_s", 0), body.get("dwell_s", DEFAULT_DWELL_S),
                                      body.get("destination_window"), peak, dose, incurred)
        norm = dict(body)
        norm["input_time"] = tag_to_iso(tag)
        norm.setdefault("depart_offset_s", 0)
        norm.setdefault("dwell_s", DEFAULT_DWELL_S)
        norm.setdefault("policy", "full")
        norm.setdefault("run_independent_check", False)
        norm.setdefault("client_ref", None)
        norm["limits"] = {"peak_kw_m2": peak, "dose_kj_m2": dose}
        norm["incurred_dose_kj_m2"] = incurred
        norm["fire_input"] = ctx.fire
        job = self._new_route_job(request=norm, snap=snap, region_id=region_id, ctx=ctx, params=params,
                                  created=time.monotonic(), created_wall=utc_now(),
                                  start_after=self.queued_s, done_after=self.done_s)
        self.log("route check %s: %s -> %s, %s" % (job.job_id, snap["start"]["node_id"], snap["destination"]["node_id"],
                                                    ("recorded " + job.record.label()) if job.record else
                                                    (MOCK_ZONES if ctx.type == "spread_zones" else MOCK_NO_RECORD)))
        accepted = {"job_id": job.job_id, "status": "queued", "kind": "route_check", "snap": snap,
                    "provenance": self._route_job_prov(job), "links": self._links(job)}
        return accepted, "application/json; charset=utf-8", {"Location": "/v1/route-checks/%s" % job.job_id}

    @staticmethod
    def _links(job: RouteJob) -> dict:
        base = "/v1/route-checks/%s" % job.job_id
        links = {"self": base, "export_geojson": base + "/export?format=geojson", "export_kml": base + "/export?format=kml",
                 "export_csv": base + "/export?format=csv"}
        if job.parent:
            links["dispatch_plan"] = "/v1/dispatch-plans/%s" % job.parent
        return links

    def _state(self, job, now: float):
        el = now - job.created
        if el < job.start_after:
            return "queued", None, None
        started = iso_ms(job.created_wall + dt.timedelta(seconds=job.start_after))
        if el < job.done_after:
            return "running", started, None
        return "done", started, iso_ms(job.created_wall + dt.timedelta(seconds=job.done_after))

    def get_route_check(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if not isinstance(job, RouteJob):
            raise ApiError(404, "JOB_NOT_FOUND", "route check %r not found" % job_id)
        status, started, finished = self._state(job, time.monotonic())
        view = {"job_id": job.job_id, "kind": "route_check", "status": status, "created_at": iso_ms(job.created_wall),
                "started_at": started, "finished_at": finished, "request": job.request, "snap": job.snap,
                "result": self.route_result(job, finished) if status == "done" else None, "error": None,
                "provenance": self._route_job_prov(job), "links": self._links(job), "mock": True}
        if job.parent:
            view["parent_job_id"] = job.parent
        return view

    def _outcome(self, job: RouteJob) -> dict:
        """Verdict-level outcome of a route job (shared by results and dispatch attempts; cached per job). Recorded
        values are served as recorded; the contract v1.4 rules (independent check requested but not run, reduced-policy
        route contradicting its own policy) downgrade a recorded verdict to unresolved exactly as the real API would."""
        if job._outcome is not None:
            return job._outcome
        req, ctx, rec = job.request, job.ctx, job.record
        policy = req["policy"]
        out = {"verdict": UNRESOLVED, "reason_code": "OTHER", "raw_status": None, "raw_reason": None,
               "departure_s": job.query["depart"], "arrival_s": None, "lower_bound_L_s": None, "dwell_end_s": None,
               "route": None, "exposure": [], "fpa": None, "compute_s": None, "within_budget": False,
               "case_id": None, "independent": None, "notes": []}
        notes = out["notes"]
        if ctx.type == "spread_zones":
            out["raw_status"] = MOCK_ZONES
        elif rec is None:
            out["raw_status"] = MOCK_NO_RECORD
        else:
            o = rec.doc.get("outcome") or {}
            notes.append("MOCK: recorded result of case %s (%s rep %s) served without recomputation"
                         % (rec.case_id, rec.source_arm, rec.repetition))
            verdict, reason = rec.verdict, None
            if verdict == UNRESOLVED:
                reason = o.get("reason_code") if o.get("reason_code") in REASON_CODES else "OTHER"
                if o.get("reason_code") not in REASON_CODES and o.get("reason_code") is not None:
                    notes.append("Recorded reason code %r is not in contract v%s; served as OTHER."
                                 % (o.get("reason_code"), API_VERSION))
            compute_s = o.get("compute_s") if _is_num(o.get("compute_s")) else None
            within = o.get("within_budget")
            if not isinstance(within, bool):
                within = compute_s is not None and compute_s <= BUDGET_S
                notes.append("within_budget was not recorded for this execution; derived from compute_s." if compute_s is not None
                             else "Neither compute_s nor within_budget was recorded for this execution.")
            if compute_s is not None:
                notes.append("compute_s is the recorded complete-request wall time of this execution on the native campaign "
                             "host (Apple M5 Pro, macOS); the MOCK computed nothing.")
            else:
                notes.append("No wall time was recorded for this execution (compute_s null).")
            if o.get("raw_status") or o.get("raw_reason"):
                notes.append("Recorded kit result: primary status %s%s." % (
                    o.get("raw_status"), (" (%s)" % o["raw_reason"]) if o.get("raw_reason") else ""))
            checked = verdict == CHECKED
            exposure, fpa = [], None
            if checked:
                own = [m for m in rec.doc.get("exposure") or [] if isinstance(m, dict)]
                fme = rec.doc.get("full_model_exposure")
                if rec.policy == "full":
                    exposure = [dict(m, basis="centre_model", peak_upper_kw_m2=m.get("peak_upper_kw_m2"),
                                     dose_upper_kj_m2=m.get("dose_upper_kj_m2")) for m in own]
                    if any(e["peak_upper_kw_m2"] is None for e in exposure):
                        notes.append("The whole-road check upper bounds (peak_upper_kw_m2, dose_upper_kj_m2) were not "
                                     "recorded in the MOCK fixture (null).")
                elif isinstance(fme, dict) and isinstance(fme.get("members"), list) and fme["members"]:
                    # A reduced policy does not enforce (all of) the hazard; report the recorded full-hazard check.
                    exposure = [dict(m, basis="full_model_centre_check") for m in fme["members"] if isinstance(m, dict)]
                    notes.append("exposure is the recorded offline full-hazard centre-model check of this route (%s); the "
                                 "policy's own centre-model values are in full_policy_assessment.policy_exposure."
                                 % (fme.get("scope") or "full_model_exposure"))
                else:
                    exposure = own
                    notes.append("exposure is the policy's own centre model (%s); no full-hazard check was recorded."
                                 % (rec.doc.get("exposure_scope") or "recorded scope unknown"))
                fpa = rec.fpa
            if rec.policy != "full":
                notes.append("Policy %s is a recorded final-input ablation configuration (%s); a route found under it is not "
                             "guaranteed to pass the full hazard policy." % (rec.policy, rec.source_arm))
                fpc = rec.doc.get("full_policy_check")
                if isinstance(fpc, dict) and isinstance(fpc.get("pass"), bool):
                    comps = fpc.get("failure_components")
                    notes.append("Recorded full-policy check of this execution: %s." % (
                        "pass" if fpc["pass"] else "fail" + (" (%s)" % ", ".join(map(str, comps)) if comps else "")))
                if checked:
                    notes.append("Route checked under policy %s only (%s); exposure is reported against the unchanged full "
                                 "hazard. It is not a full-policy checked route." % (
                                     rec.policy, "flame contact not enforced" if rec.policy == "travel_only"
                                     else "thermal limits partly disabled"))
                    if fpa is not None and fpa.get("passes_full_centre_and_contact") is False:
                        notes.append("This route FAILS the full policy: %s." % ", ".join(
                            sorted({v["constraint"] for v in fpa["violations"]})))
            scope = rec.doc.get("refusal_scope")
            if verdict == NO_ROUTE and scope:
                notes.append("Recorded refusal scope: %s" % (scope if isinstance(scope, str) else json.dumps(scope, ensure_ascii=False)))
            reps = rec.doc.get("repetitions")
            if isinstance(reps, list) and len(reps) > 1:
                notes.append("Recorded repetitions: " + "; ".join(
                    "%s r%s %s (%s s)" % (r.get("arm"), r.get("rep"), r.get("verdict"), r.get("wall_s"))
                    for r in reps if isinstance(r, dict)))
            out.update({"verdict": verdict, "reason_code": reason,
                        "raw_status": o.get("authoritative_decision") or o.get("raw_status"),
                        "raw_reason": o.get("raw_reason") if verdict == UNRESOLVED else None,
                        "departure_s": o.get("departure_s") if _is_num(o.get("departure_s")) else job.query["depart"],
                        "arrival_s": o.get("arrival_s") if checked else None,
                        "lower_bound_L_s": o.get("lower_bound_L_s") if _is_num(o.get("lower_bound_L_s")) else None,
                        "dwell_end_s": o.get("dwell_end_s") if checked else None,
                        "route": rec.route if checked else None, "exposure": exposure, "fpa": fpa,
                        "compute_s": compute_s, "within_budget": within, "case_id": rec.case_id})
            if checked and fpa is not None and fpa.get("passes_selected_policy") is False:
                # v1.4: the ablation grader would not count this as a selected-policy route (api/runner.py)
                out.update(verdict=UNRESOLVED, reason_code="CHECK_FAILED", raw_reason="INDEPENDENT_CONTRADICTION",
                           arrival_s=None, dwell_end_s=None, route=None, exposure=[])
                notes.append("The recorded full-hazard grade contradicts this route's own policy %s (it enforces %s; "
                             "recorded failures %s), so the result is unresolved (CHECK_FAILED), as the API rule "
                             "requires." % (rec.policy, ", ".join(sorted(POLICY_ENABLED[rec.policy])),
                                            ", ".join(fpa.get("failure_components") or [])))
        if req.get("run_independent_check"):
            if policy == "full":
                out["independent"] = {"status": "NOT_RUN_MOCK", "classification": None, "verdict": None,
                                      "contradictions": None, "elapsed_s": None,
                                      "note": "The MOCK server does not run the offline independent checker."}
                if out["verdict"] in (CHECKED, NO_ROUTE):
                    out.update(verdict=UNRESOLVED, reason_code="CHECK_NOT_FINISHED", raw_reason="INDEPENDENT_CHECK_MISSING",
                               arrival_s=None, dwell_end_s=None, route=None, exposure=[])
                    notes.append(NOTE_NO_INDEPENDENT)
                else:
                    notes.append("run_independent_check was requested; the MOCK server does not run the offline "
                                 "independent checker.")
            else:
                notes.append("The offline independent checker is defined for the full policy only; it was not run for %s."
                             % policy)
        job._outcome = out
        return out

    def _evaluated(self, job: RouteJob) -> bool:
        """provenance.evaluated_configuration as the real API sets it: recorded input, policy full and the default limits
        (or a request identical to a recorded final-panel mission)."""
        q = job.query
        return (job.ctx.type == "recorded" and q["policy"] == "full"
                and (self._default_limits(q["peak"], q["dose"], q["incurred"]) or job.mission is not None))

    def route_result(self, job: RouteJob, finished_iso) -> dict:
        req, ctx, rec = job.request, job.ctx, job.record
        gen = _parse_utc(finished_iso) if finished_iso else utc_now()
        s = self._outcome(job)
        res = {"verdict": s["verdict"], "reason_code": s["reason_code"], "raw_status": s["raw_status"],
               "raw_reason": s["raw_reason"], "departure_s": s["departure_s"], "arrival_s": s["arrival_s"],
               "lower_bound_L_s": s["lower_bound_L_s"], "dwell_end_s": s["dwell_end_s"], "route": s["route"],
               "exposure": s["exposure"], "compute_s": s["compute_s"], "within_budget": s["within_budget"],
               "policy": req["policy"],
               "limits": {"peak_kw_m2": req["limits"]["peak_kw_m2"], "dose_kj_m2": req["limits"]["dose_kj_m2"],
                          "incurred_dose_kj_m2": req["incurred_dose_kj_m2"]},
               "independent_check": s["independent"], "assumptions": None, "notes": list(s["notes"])}
        if s["fpa"] is not None:
            res["full_policy_assessment"] = s["fpa"]
        if ctx.type == "spread_zones":
            res["raw_reason"] = ("MOCK: user-drawn spread zones are validated but never converted or evaluated by the "
                                 "mock server; nothing was computed.")
            res["assumptions"] = ctx.assumptions
            res["notes"] = ["MOCK: spread_zones input was not evaluated. Unresolved is never safe.",
                            SPREAD_ZONES_TEXT["en"]] + res["notes"]
            res["provenance"] = self._prov(
                region_id=job.region, tag=ctx.tag, fire_type="spread_zones", policy=req["policy"], scenario_set_id=None,
                scenario_ids=(), input_hashes={**self._region_hashes(job.region), "zones": ctx.zones_sha256},
                evaluated=False, approximation=APPROXIMATION, clock=None, host=NOT_COMPUTED_HOST, generated_at=gen,
                extra={"burning_scenario_set_id": ctx.fire.get("burning_scenario_set_id"), "recorded_mission_match": None})
        elif rec is None:
            if job._reason is None:
                job._reason = self.fx.explain(job.query)
            res["raw_reason"] = job._reason
            res["notes"] = ["MOCK: no recorded execution matches this request, so nothing is shown as checked.",
                            "The MOCK serves only recorded results (planner/docs/ARCHITECTURE.md 5.1); connect the real "
                            "Route-Check API to evaluate this request."] + res["notes"]
            res["provenance"] = self._prov(
                region_id=job.region, tag=ctx.tag, fire_type="recorded", policy=req["policy"],
                scenario_set_id=ctx.sset["scenario_set_id"], scenario_ids=ctx.sset.get("scenario_ids") or (),
                input_hashes=self._region_hashes(job.region, ctx.sset), evaluated=self._evaluated(job), clock=None,
                host=NOT_COMPUTED_HOST, generated_at=gen, extra={"recorded_mission_match": job.mission})
        else:
            o = rec.doc.get("outcome") or {}
            res["provenance"] = self._prov(
                region_id=job.region, tag=rec.tag, fire_type="recorded", policy=rec.policy, scenario_set_id=rec.ssid,
                scenario_ids=rec.doc.get("scenario_ids") or ctx.sset.get("scenario_ids") or (),
                input_hashes=rec.doc.get("input_hashes") or {}, evaluated=self._evaluated(job), clock=RECORDED_CLOCK,
                host=dict(RECORDED_HOST), generated_at=gen,
                extra={"recorded_mission_match": job.mission,
                       "recorded_execution": {"case_id": rec.case_id, "policy": rec.policy, "source_arm": rec.source_arm,
                                              "repetition": rec.repetition, "verdict": rec.verdict,
                                              "raw_primary_status": o.get("raw_status"),
                                              "raw_primary_reason": o.get("raw_reason"),
                                              "frozen_state": o.get("frozen_state"),
                                              "fixture": rec.path.relative_to(self.fixtures_dir).as_posix(),
                                              "source_records": rec.doc.get("source_records") or []}})
        if res["verdict"] == NO_ROUTE:
            res["notes"].append(NOTE_NO_ROUTE)
        elif res["verdict"] == UNRESOLVED:
            res["notes"].append(NOTE_UNRESOLVED)
        return res

    # -------------------------------------------------------------------------------------------- exports
    def export(self, job_id: str, query: dict) -> Response:
        fmt = self._query_value(query, "format")          # a missing parameter fails first (FastAPI query validation)
        job = self.jobs.get(job_id)
        if not isinstance(job, RouteJob):
            raise ApiError(404, "JOB_NOT_FOUND", "route check %r not found" % job_id)
        if fmt not in ("geojson", "kml", "csv"):
            raise _unprocessable("VALIDATION_ERROR", "format must be geojson, kml or csv", {"format": fmt})
        status, _, finished = self._state(job, time.monotonic())
        if status != "done":
            raise ApiError(409, "JOB_NOT_DONE", "route check is %s" % status, {"status": status})
        res = self.route_result(job, finished)
        if res["verdict"] != CHECKED or not res.get("route"):
            raise ApiError(409, "NO_CHECKED_ROUTE", "only checked routes are exported; this result is %s" % res["verdict"],
                           {"verdict": res["verdict"], "reason_code": res["reason_code"], "raw_status": res["raw_status"]})
        fname = "wfg_mock_route_%s" % job.job_id
        if fmt == "geojson":
            return _json(200, self._export_geojson(job, res), ctype="application/geo+json; charset=utf-8",
                         headers={"Content-Disposition": 'attachment; filename="%s.geojson"' % fname})
        prov_header = self._provenance_header(job, res)
        if fmt == "kml":
            return Response(200, "application/vnd.google-earth.kml+xml; charset=utf-8", self._export_kml(job, res).encode("utf-8"),
                            {"Content-Disposition": 'attachment; filename="%s.kml"' % fname, "X-WFG-Provenance": prov_header})
        return Response(200, "text/csv; charset=utf-8", self._export_csv(job, res).encode("utf-8"),
                        {"Content-Disposition": 'attachment; filename="%s.csv"' % fname, "X-WFG-Provenance": prov_header})

    @staticmethod
    def _label(res: dict) -> str:
        """Export label that never lets a reduced-policy or approximate route pass as a full checked route (as the real
        API's exports.py _label)."""
        prov = res.get("provenance") or {}
        parts = ["checked route" if res.get("policy") == "full" else
                 "route checked under policy %s only (NOT a full-policy route)" % res.get("policy")]
        if prov.get("approximation"):
            parts.append(prov["approximation"])
        fpa = res.get("full_policy_assessment")
        if fpa is not None and fpa.get("passes_full_centre_and_contact") is False:
            parts.append("FAILS the full hazard check")
        return "; ".join(parts)

    @staticmethod
    def _provenance_header(job: RouteJob, res: dict) -> str:
        """Compact ASCII provenance for the X-WFG-Provenance header of KML/CSV exports (contract v1.3)."""
        prov = res["provenance"]
        keep = ("api_version", "package", "package_version", "kit", "checkpoint", "git_commit", "region", "input_time",
                "scenario_set_id", "fire_input_type", "policy", "evaluated_configuration", "approximation")
        out = {k: prov.get(k) for k in keep}
        out["job_id"], out["verdict"] = job.job_id, res["verdict"]
        fpa = res.get("full_policy_assessment")
        out["full_policy_centre_and_contact_pass"] = None if fpa is None else fpa.get("passes_full_centre_and_contact")
        out["input_hashes"] = prov.get("input_hashes")
        out["recorded_mission_match"] = prov.get("recorded_mission_match")
        out["mock"] = True
        return json.dumps(out, separators=(",", ":"), ensure_ascii=True)

    def _export_common(self, job: RouteJob, res: dict) -> dict:
        prov = res["provenance"]
        fpa = res.get("full_policy_assessment")
        return {"job_id": job.job_id, "verdict": res["verdict"], "policy": res["policy"],
                "full_policy_route": res["policy"] == "full",
                "full_policy_centre_and_contact_pass": None if fpa is None else fpa.get("passes_full_centre_and_contact"),
                "fire_input_type": prov.get("fire_input_type"), "approximation": prov.get("approximation"),
                "evaluated_configuration": prov.get("evaluated_configuration"), "label": self._label(res),
                "mock": True, "case_id": (prov.get("recorded_execution") or {}).get("case_id")}

    def _export_geojson(self, job: RouteJob, res: dict) -> dict:
        route, snap = res["route"], job.snap
        common = self._export_common(job, res)
        feats = [
            {"type": "Feature", "geometry": route["geometry"],
             "properties": dict(route["properties"], **common, role="route", departure_s=res["departure_s"],
                                arrival_s=res["arrival_s"], dwell_end_s=res["dwell_end_s"],
                                lower_bound_L_s=res["lower_bound_L_s"], compute_s=res["compute_s"],
                                exposure=res["exposure"])},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [snap["start"]["lon"], snap["start"]["lat"]]},
             "properties": dict(common, role="start", node_id=snap["start"]["node_id"], time_s=res["departure_s"],
                                snap=snap["start"])},
            {"type": "Feature", "geometry": {"type": "Point",
                                             "coordinates": [snap["destination"]["lon"], snap["destination"]["lat"]]},
             "properties": dict(common, role="destination", node_id=snap["destination"]["node_id"],
                                arrival_s=res["arrival_s"], dwell_end_s=res["dwell_end_s"], snap=snap["destination"])},
        ]
        return {"type": "FeatureCollection", "name": "MOCK WildfireGuardian %s %s" % (common["label"], job.job_id),
                "features": feats, "provenance": res["provenance"]}

    def _export_kml(self, job: RouteJob, res: dict) -> str:
        route, snap, prov = res["route"], job.snap, res["provenance"]
        coords = route["geometry"]["coordinates"]
        rec = prov.get("recorded_execution") or {}
        label = self._label(res)
        full = res["policy"] == "full"

        def esc(v) -> str:
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False, sort_keys=True)
            return _xml_escape("" if v is None else str(v))

        def data(pairs) -> str:
            return "<ExtendedData>%s</ExtendedData>" % "".join(
                '<Data name="%s"><value>%s</value></Data>' % (esc(k), esc(v)) for k, v in pairs)

        route_data = [("mock", "true"), ("verdict", res["verdict"]), ("policy", res["policy"]), ("label", label),
                      ("departure_s", res["departure_s"]), ("arrival_s", res["arrival_s"]),
                      ("dwell_end_s", res["dwell_end_s"]), ("compute_s", res["compute_s"]), ("job_id", job.job_id),
                      ("case_id", rec.get("case_id"))]
        route_data += [("provenance_%s" % k, prov.get(k)) for k in
                       ("api_version", "package", "package_version", "kit", "checkpoint", "git_commit", "region",
                        "input_time", "graph_id", "scenario_set_id", "scenario_ids", "fire_input_type",
                        "evaluated_configuration", "recorded_mission_match", "clock", "host", "input_hashes",
                        "generated_at")]
        line = " ".join("%.7f,%.7f,0" % (c[0], c[1]) for c in coords)
        name = "MOCK — WildfireGuardian %s %s%s" % (label, job.job_id, (" (case %s)" % rec["case_id"]) if rec.get("case_id") else "")
        placemark = ("확인된 경로 / checked route (MOCK)" if full else
                     "정책 %s 한정 경로 — 전체 정책 경로 아님 / %s (MOCK)" % (res["policy"], label))
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<kml xmlns="http://www.opengis.net/kml/2.2">',
               "<Document>",
               "<name>%s</name>" % esc(name),
               "<description>%s</description>" % esc(
                   "MOCK server: recorded result served without recomputation. %s. 사전 계획 보조 도구입니다. 실시간 대피 "
                   "지휘·운영용이 아닙니다. / Planning aid only — not for live evacuation operations." % label),
               '<Style id="checked"><LineStyle><color>ff559e1a</color><width>4</width></LineStyle></Style>',
               '<Style id="reduced"><LineStyle><color>ff73706e</color><width>3</width></LineStyle></Style>',
               "<Placemark><name>%s</name><styleUrl>#%s</styleUrl>%s" % (esc(placemark), "checked" if full else "reduced",
                                                                       data(route_data)),
               "<LineString><tessellate>1</tessellate><coordinates>%s</coordinates></LineString></Placemark>" % line]
        for role, s, t in (("start", snap["start"], res["departure_s"]), ("destination", snap["destination"], res["arrival_s"])):
            out.append("<Placemark><name>%s</name>%s<Point><coordinates>%.7f,%.7f,0</coordinates></Point></Placemark>" % (
                esc("%s %s (MOCK)" % (role, s["node_id"])),
                data([("mock", "true"), ("role", role), ("node_id", s["node_id"]), ("time_s", t),
                      ("snap_distance_m", s["distance_m"]), ("snap_input", s["input"])]),
                s["lon"], s["lat"]))
        out += ["</Document>", "</kml>", ""]
        return "\n".join(out)

    def _vertex_node_ids(self, job: RouteJob, route: dict) -> list:
        """node id per vertex: the route's own node_ids when they are per vertex (the served layout), else attributed
        through the node table (fallback for a route served as recorded)."""
        coords = route["geometry"]["coordinates"]
        ids = list(route["properties"].get("node_ids") or [])
        if len(ids) == len(coords):
            return ids
        table = self.fx.nodes.get(job.region)

        def at(nid, c) -> bool:
            i = table.index.get(nid) if table else None
            return i is not None and haversine_m(c[0], c[1], table.lon[i], table.lat[i]) <= 1.0

        out, j = [], 0
        for c in coords:
            hit = ""
            for k in (j, j + 1):
                if k < len(ids) and at(ids[k], c):
                    hit, j = ids[k], k
                    break
            out.append(hit)
        return out

    def _export_csv(self, job: RouteJob, res: dict) -> str:
        """Plain table, header seq,node_id,lon,lat,time_s,event; events depart|pass|wait_end|arrive and a final
        dwell_end row, as the real API's exports.py to_csv."""
        route = res["route"]
        coords = route["geometry"]["coordinates"]
        times = list(route["properties"].get("times_s") or [])
        nids = self._vertex_node_ids(job, route)
        waits_end = {(w.get("node_id"), w.get("to_s")) for w in route["properties"].get("waits") or [] if isinstance(w, dict)}
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["seq", "node_id", "lon", "lat", "time_s", "event"])
        n = len(coords)
        for i, c in enumerate(coords):
            nid, t = nids[i] if i < len(nids) else "", times[i] if i < len(times) else ""
            if i == 0:
                ev = "depart"
            elif (nid, t) in waits_end and nids[i - 1] == nid:
                ev = "wait_end"
            elif i == n - 1:
                ev = "arrive"
            else:
                ev = "pass"
            w.writerow([i, nid, "%.7f" % c[0], "%.7f" % c[1], t, ev])
        w.writerow([n, nids[-1] if nids else "", "%.7f" % coords[-1][0], "%.7f" % coords[-1][1], res["dwell_end_s"],
                    "dwell_end"])
        return buf.getvalue()

    # -------------------------------------------------------------------------------------------- dispatch plans
    @staticmethod
    def _lattice_offset(v) -> int:
        f = float(v)
        if not math.isfinite(f) or f < 0 or not f.is_integer():
            raise _unprocessable("NOT_ON_TIME_LATTICE", "depart_offsets_s must be a non-negative whole number of seconds on "
                                 "the 1 s lattice", {"field": "depart_offsets_s", "value": v})
        return int(f)

    def create_dispatch(self, body):
        # real API order: JSON + schema (maxItems 200 origins) -> 503 data -> region -> input_time -> fire input ->
        # destination snaps -> DUPLICATE_ID -> origin snaps (rejected_origins) -> POLICY_NOT_ALLOWED -> offsets
        # (NOT_ON_TIME_LATTICE, DUPLICATE_OFFSET) -> per-attempt request checks -> TOO_MANY_ATTEMPTS
        self._validate(body, "DispatchPlanRequest")
        self._require_data()
        if len(body["origins"]) > MAX_ORIGINS:          # unreachable after the schema's maxItems, as in the real API
            raise _unprocessable("TOO_MANY_ORIGINS", "at most %d origins per dispatch plan; split the plan" % MAX_ORIGINS,
                                 {"max_origins": MAX_ORIGINS, "origins": len(body["origins"])})
        region_id = body["region"]
        self._require_region(region_id)
        tag = normalize_input_time(body["input_time"])
        ctx = self._fire_context(region_id, tag, body["fire_input"])
        dests = []
        for d in body["destinations"]:
            try:
                dests.append((d, self._snap(region_id, d["location"], "destination %s" % d["id"])))
            except ApiError as e:
                if isinstance(e.details, dict):
                    e.details["destination_id"] = d["id"]
                raise
        ids = [o["id"] for o in body["origins"]]
        dids = [d["id"] for d in body["destinations"]]
        if len(set(ids)) != len(ids) or len(set(dids)) != len(dids):
            raise _unprocessable("DUPLICATE_ID", "origin ids and destination ids must be unique",
                                 {"duplicate_origin_ids": sorted({i for i in ids if ids.count(i) > 1}),
                                  "duplicate_destination_ids": sorted({i for i in dids if dids.count(i) > 1})})
        origins, rejected = [], []
        for o in body["origins"]:
            try:
                origins.append((o, self._snap(region_id, o["location"], "origin %s" % o["id"])))
            except ApiError as e:
                if e.status != 422:
                    raise
                err = {"code": e.code, "message": e.message}
                if e.details is not None:
                    err["details"] = e.details
                rejected.append({"origin_id": o["id"], "error": err})
        policy = body.get("policy", "full")
        if policy != "full":
            raise _unprocessable("POLICY_NOT_ALLOWED", "dispatch plans use the full policy only; reduced policies may "
                                 "return routes that fail the full hazard model", {"policy": policy})
        offsets = [self._lattice_offset(x) for x in body["depart_offsets_s"]]
        if len(set(offsets)) != len(offsets):
            raise _unprocessable("DUPLICATE_OFFSET", "depart_offsets_s must not repeat a value",
                                 {"depart_offsets_s": body["depart_offsets_s"]})
        total = len(origins) * len(dests) * len(offsets)
        if total > MAX_DISPATCH_ATTEMPTS:
            raise _unprocessable("TOO_MANY_ATTEMPTS", "origins x destinations x offsets is %d; the limit is %d per plan"
                                 % (total, MAX_DISPATCH_ATTEMPTS),
                                 {"attempts": total, "limit": MAX_DISPATCH_ATTEMPTS, "origins": len(origins),
                                  "destinations": len(dests), "depart_offsets": len(offsets)})
        dwell_default = body.get("dwell_s", DEFAULT_DWELL_S)
        lim = body.get("limits") or {}
        peak, dose = lim.get("peak_kw_m2", DEFAULT_PEAK_KW_M2), lim.get("dose_kj_m2", DEFAULT_DOSE_KJ_M2)
        norm = dict(body)
        norm.update({"input_time": tag_to_iso(tag), "fire_input": ctx.fire, "depart_offsets_s": offsets,
                     "dwell_s": dwell_default, "policy": policy, "limits": {"peak_kw_m2": peak, "dose_kj_m2": dose},
                     "client_ref": body.get("client_ref")})
        plan = PlanJob()
        plan.job_id = new_id("dp")
        plan.created, plan.created_wall = time.monotonic(), utc_now()
        plan.start_after, plan.done_after = self.queued_s, self.done_s
        plan.request, plan.region, plan.ctx = norm, region_id, ctx
        plan.rejected, plan.dests = rejected, [(d["id"], s) for d, s in dests]
        plan.limits = {"peak_kw_m2": peak, "dose_kj_m2": dose, "incurred_dose_kj_m2": 0}
        plan.provenance = self._job_prov(region_id, ctx, policy, peak, dose, 0, generated_at=plan.created_wall)
        plan._result, plan._lock = None, threading.Lock()
        # pose every (origin, destination, offset); a combination the real API cannot pose (e.g. an unsatisfiable
        # window) is an unresolved attempt with reason_code INPUT_REJECTED and the request error code as raw_reason
        specs = []
        for o, osnap in origins:
            entries = []
            for d, dsnap in dests:
                for off in offsets:
                    dwell = d.get("dwell_s", dwell_default)
                    window = d.get("window")
                    try:
                        params = self._request_params(ctx, osnap["node_id"], dsnap["node_id"], off, dwell, window, peak, dose, 0)
                    except ApiError as e:
                        entries.append(("rejected", {
                            "destination_id": d["id"], "depart_offset_s": off, "verdict": UNRESOLVED,
                            "reason_code": "INPUT_REJECTED", "raw_reason": e.code, "arrival_s": None,
                            "lower_bound_L_s": None, "compute_s": None, "route_check_job_id": None,
                            "raw_message": e.message, "case_id": None}))
                        continue
                    req = {"region": region_id, "input_time": tag_to_iso(tag), "start": o["location"],
                           "destination": d["location"], "depart_offset_s": off, "dwell_s": dwell, "policy": policy,
                           "limits": {"peak_kw_m2": peak, "dose_kj_m2": dose}, "incurred_dose_kj_m2": 0,
                           "fire_input": ctx.fire, "run_independent_check": False,
                           "client_ref": "dispatch:%s:%s:%s:%s" % (plan.job_id, o["id"], d["id"], off)}
                    if window is not None:
                        req["destination_window"] = window
                    entries.append(("job", (req, {"start": osnap, "destination": dsnap}, params, d["id"], off)))
            specs.append((o["id"], osnap, entries))
        n_jobs = sum(1 for _, _, es in specs for kind, _ in es if kind == "job")
        plan.total = total
        plan.attempt_jobs = []
        plan.origins = []
        k = 0
        span = self.done_s - self.queued_s
        id_prefix = "rc_" + plan.job_id[3:15]           # attempt ids: rc_<12 hex of the plan id><8 hex counter>
        for oid, osnap, entries in specs:
            atts = []
            for kind, payload in entries:
                if kind == "rejected":
                    atts.append(("rejected", payload))
                    continue
                req, snap, params, did, off = payload
                k += 1
                job = self._new_route_job(request=req, snap=snap, region_id=region_id, ctx=ctx, params=params,
                                          created=plan.created, created_wall=plan.created_wall,
                                          start_after=self.queued_s, done_after=self.queued_s + span * k / n_jobs,
                                          parent=plan.job_id, job_id="%s%08x" % (id_prefix, k), register=False)
                plan.attempt_jobs.append(job)
                atts.append(("job", (job, did, off)))
            plan.origins.append((oid, osnap, atts))
        self.jobs.add_many(plan.attempt_jobs + [plan])
        self.log("dispatch plan %s: %d origins (%d rejected) x %d destinations x %d offsets = %d attempts" % (
            plan.job_id, len(origins), len(rejected), len(dests), len(offsets), plan.total))
        accepted = {"job_id": plan.job_id, "status": "queued", "kind": "dispatch_plan", "provenance": plan.provenance,
                    "links": {"self": "/v1/dispatch-plans/%s" % plan.job_id},
                    "progress": {"done": plan.total - n_jobs, "total": plan.total}}
        return accepted, "application/json; charset=utf-8", {"Location": "/v1/dispatch-plans/%s" % plan.job_id}

    def _progress(self, plan: PlanJob, now: float) -> dict:
        rejected = plan.total - len(plan.attempt_jobs)
        el = now - plan.created
        done = rejected + sum(1 for j in plan.attempt_jobs if el >= j.done_after)
        if el >= plan.done_after:
            done = plan.total
        return {"done": done, "total": plan.total}

    def get_dispatch(self, job_id: str) -> dict:
        plan = self.jobs.get(job_id)
        if not isinstance(plan, PlanJob):
            raise ApiError(404, "JOB_NOT_FOUND", "dispatch plan %r not found" % job_id)
        status, started, finished = self._state(plan, time.monotonic())
        result = None
        if status == "done":
            with plan._lock:
                if plan._result is None:
                    plan._result = self._plan_result(plan, finished)
                result = plan._result
        progress = self._progress(plan, time.monotonic()) if status != "done" else {"done": plan.total, "total": plan.total}
        return {"job_id": plan.job_id, "kind": "dispatch_plan", "status": status, "created_at": iso_ms(plan.created_wall),
                "started_at": started, "finished_at": finished, "request": plan.request, "progress": progress,
                "result": result, "error": None, "provenance": plan.provenance,
                "links": {"self": "/v1/dispatch-plans/%s" % plan.job_id}, "mock": True}

    def _attempt(self, job: RouteJob, did: str, off) -> dict:
        s = self._outcome(job)
        return {"destination_id": did, "depart_offset_s": off, "verdict": s["verdict"], "reason_code": s["reason_code"],
                "arrival_s": s["arrival_s"], "lower_bound_L_s": s["lower_bound_L_s"], "compute_s": s["compute_s"],
                "route_check_job_id": job.job_id, "raw_status": s["raw_status"], "case_id": s["case_id"]}

    @staticmethod
    def _contiguous_latest(attempts: list):
        """Largest requested offset t such that every requested offset <= t has a checked route (contract v1.4
        latest_contiguous_checked_depart_offset_s; real API dispatch.contiguous_latest); None when the earliest has none."""
        ok = {a["depart_offset_s"] for a in attempts if a["verdict"] == CHECKED}
        latest = None
        for t in sorted({a["depart_offset_s"] for a in attempts}):
            if t not in ok:
                break
            latest = t
        return latest

    def _plan_result(self, plan: PlanJob, finished_iso) -> dict:
        dest_order = {did: i for i, (did, _) in enumerate(plan.dests)}
        plans, all_attempts = [], []
        for order, (oid, osnap, atts) in enumerate(plan.origins):
            attempts = [p if kind == "rejected" else self._attempt(*p) for kind, p in atts]
            attempts.sort(key=lambda a: (a["depart_offset_s"], dest_order.get(a["destination_id"], 0)))
            all_attempts += attempts
            verdicts = [a["verdict"] for a in attempts]
            if CHECKED in verdicts:
                best_verdict = CHECKED
            elif verdicts and all(v == NO_ROUTE for v in verdicts):
                best_verdict = NO_ROUTE
            else:
                best_verdict = UNRESOLVED
            checked = [a for a in attempts if a["verdict"] == CHECKED]
            latest = max((a["depart_offset_s"] for a in checked), default=None)
            best = None
            if latest is not None:
                cands = [a for a in checked if a["depart_offset_s"] == latest]
                best = min(cands, key=lambda a: (a["arrival_s"] if _is_num(a["arrival_s"]) else math.inf,
                                                 dest_order.get(a["destination_id"], 0)))
            plans.append({"origin_id": oid, "urgency_rank": 0, "snap": osnap, "best_verdict": best_verdict,
                          "latest_checked_depart_offset_s": latest,
                          "latest_contiguous_checked_depart_offset_s": self._contiguous_latest(attempts),
                          "best": dict(best) if best else None, "attempts": attempts, "_order": order})
        group = {CHECKED: 0, NO_ROUTE: 1, UNRESOLVED: 2}

        def urgency(p):
            # real API dispatch.sort_by_urgency: checked origins by the conservative contiguous latest offset (an origin
            # whose earliest requested offset has no checked route ranks first), then model_no_route, then unresolved
            g = group[p["best_verdict"]]
            c = p["latest_contiguous_checked_depart_offset_s"]
            lat = (-math.inf if c is None else c) if g == 0 else 0
            arr = p["best"]["arrival_s"] if p["best"] and _is_num(p["best"]["arrival_s"]) else 0
            return (g, lat, arr, p["_order"])
        plans.sort(key=urgency)
        for rank, p in enumerate(plans, 1):
            p["urgency_rank"] = rank
            del p["_order"]
        cs = [a["compute_s"] for a in all_attempts if _is_num(a.get("compute_s"))]
        summary = {"origins": len(plans), "attempts": len(all_attempts),
                   "checked_route": sum(p["best_verdict"] == CHECKED for p in plans),
                   "model_no_route": sum(p["best_verdict"] == NO_ROUTE for p in plans),
                   "unresolved": sum(p["best_verdict"] == UNRESOLVED for p in plans),
                   "attempt_verdicts": {v: sum(a["verdict"] == v for a in all_attempts) for v in VERDICTS},
                   "median_compute_s": statistics.median(cs) if cs else None, "wall_s": None,
                   "rejected_origins": len(plan.rejected),
                   "recorded_attempts": sum(1 for a in all_attempts if a.get("case_id"))}
        ctx = plan.ctx
        recorded = [j.record for j in plan.attempt_jobs if j.record is not None]
        gen = _parse_utc(finished_iso) if finished_iso else utc_now()
        lim = plan.limits
        if ctx.type == "spread_zones":
            prov = self._prov(region_id=plan.region, tag=ctx.tag, fire_type="spread_zones", policy=plan.request["policy"],
                              scenario_set_id=None, scenario_ids=(),
                              input_hashes={**self._region_hashes(plan.region), "zones": ctx.zones_sha256},
                              evaluated=False, approximation=APPROXIMATION, clock=None, host=NOT_COMPUTED_HOST,
                              generated_at=gen, extra={"burning_scenario_set_id": ctx.fire.get("burning_scenario_set_id")})
        else:
            prov = self._prov(region_id=plan.region, tag=ctx.tag, fire_type="recorded", policy=plan.request["policy"],
                              scenario_set_id=ctx.sset["scenario_set_id"], scenario_ids=ctx.sset.get("scenario_ids") or (),
                              input_hashes=self._region_hashes(plan.region, ctx.sset),
                              evaluated=self._default_limits(lim["peak_kw_m2"], lim["dose_kj_m2"], 0),
                              clock=RECORDED_CLOCK if recorded else None,
                              host=dict(RECORDED_HOST) if recorded else NOT_COMPUTED_HOST, generated_at=gen,
                              extra={"recorded_cases": sorted({r.label() for r in recorded})})
        notes = ["MOCK: every attempt is a recorded result or unresolved; nothing was computed.",
                 "summary.checked_route / model_no_route / unresolved count origins by best_verdict; "
                 "summary.attempt_verdicts counts attempts.",
                 "summary.wall_s is null because the MOCK did not compute; median_compute_s is over recorded wall times only.",
                 "Urgency uses latest_contiguous_checked_depart_offset_s (contract v1.4); exposure while waiting at the "
                 "origin before departure is not checked."]
        return {"plans": plans, "summary": summary, "rejected_origins": plan.rejected,
                "assumptions": ctx.assumptions if ctx.type == "spread_zones" else None, "provenance": prov,
                "destinations": [{"id": did, "snap": s} for did, s in plan.dests], "notes": notes}


class _Preflight(Exception):
    pass


# ---------------------------------------------------------------------------------------------------- HTTP layer
class Handler(BaseHTTPRequestHandler):
    server_version = "WFG-RouteCheck-MOCK/" + API_VERSION
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 60                    # seconds an idle keep-alive connection is kept open

    def do_GET(self):
        self._handle("GET")

    def do_HEAD(self):
        self._handle("HEAD")

    def do_POST(self):
        self._handle("POST")

    def do_OPTIONS(self):
        self._handle("OPTIONS")

    def do_PUT(self):
        self._handle("PUT")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_DELETE(self):
        self._handle("DELETE")

    def log_message(self, fmt, *args):  # replaced by one concise line per request in _handle
        pass

    def _read_body(self):
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            data = bytearray()
            while True:
                line = self.rfile.readline(65537)
                size = int(line.split(b";")[0].strip() or b"0", 16)
                if size == 0:
                    while self.rfile.readline(65537) not in (b"\r\n", b"\n", b""):
                        pass
                    return bytes(data)
                data += self.rfile.read(size)
                self.rfile.readline(65537)
                if len(data) > MAX_BODY_BYTES:
                    raise ValueError("too large")
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > MAX_BODY_BYTES:
            raise ValueError("too large")
        return self.rfile.read(n) if n else b""

    def _handle(self, method: str):
        t0 = time.perf_counter()
        api: MockApi = self.server.api
        try:
            body = self._read_body()
        except ValueError:
            self.close_connection = True
            resp = api.error_response(ApiError(422, "VALIDATION_ERROR", "request body missing a valid Content-Length or "
                                               "larger than %d bytes" % MAX_BODY_BYTES))
        else:
            resp = api.handle(method, self.path, body, self.headers)
        try:
            self._send(resp, method)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        api.log("%s %s %s %d %.1f ms" % (self.client_address[0], method, self.path[:200], resp.status,
                                          (time.perf_counter() - t0) * 1000))

    def _send(self, resp: Response, method: str):
        self.send_response(resp.status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        req_headers = self.headers.get("Access-Control-Request-Headers")
        allowed = req_headers if req_headers and re.fullmatch(r"[A-Za-z0-9\-_, ]{1,512}", req_headers) else "Content-Type, Accept"
        self.send_header("Access-Control-Allow-Headers", allowed)
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Location, X-WFG-Mock, X-WFG-Provenance")
        self.send_header("X-WFG-Mock", "1")
        self.send_header("Cache-Control", "no-store")
        if resp.ctype:
            self.send_header("Content-Type", resp.ctype)
        if resp.status != 204:
            self.send_header("Content-Length", str(len(resp.body)))
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if method != "HEAD" and resp.status != 204 and resp.body:
            self.wfile.write(resp.body)


class MockHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False          # idle keep-alive connections must not block shutdown
    allow_reuse_address = True

    def __init__(self, address, api: MockApi):
        self.api = api
        super().__init__(address, Handler)


def make_server(api: MockApi, host: str = "127.0.0.1", port: int = 8765) -> MockHTTPServer:
    return MockHTTPServer((host, port), api)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="WildfireGuardian Route-Check API v1 MOCK server (stdlib only; serves "
                                             "recorded results only).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--fixtures", type=Path, default=HERE / "fixtures", help="fixture tree (default: %(default)s)")
    ap.add_argument("--quiet", action="store_true", help="no per-request log lines")
    ap.add_argument("--queued-s", type=float, default=DEFAULT_QUEUED_S, help=argparse.SUPPRESS)
    ap.add_argument("--done-s", type=float, default=DEFAULT_DONE_S, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    api = MockApi(a.fixtures, queued_s=a.queued_s, done_s=a.done_s, quiet=a.quiet)
    try:
        httpd = make_server(api, a.host, a.port)
    except OSError as e:
        print("[wfg-mock] cannot listen on %s:%d: %s" % (a.host, a.port, e), file=sys.stderr)
        return 1
    host, port = httpd.server_address[:2]
    h = api.health()
    print("[wfg-mock] WildfireGuardian Route-Check API v%s MOCK on http://%s:%d/v1 (status %s; %d regions, %d recorded "
          "executions; fixtures %s)" % (API_VERSION, host, port, h["status"], len(h["regions"]), len(api.fx.records),
                                        api.fixtures_dir), file=sys.stderr)
    for issue in h["issues"]:
        print("[wfg-mock] issue: %s" % issue, file=sys.stderr)
    print("[wfg-mock] honesty: recorded results only for exact restatements of recorded executions; everything else "
          "is unresolved. Ctrl-C to stop.", file=sys.stderr, flush=True)

    def _stop(signum, _frame):
        print("[wfg-mock] %s received, shutting down" % signal.Signals(signum).name, file=sys.stderr, flush=True)
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    try:
        httpd.serve_forever(poll_interval=0.25)
    finally:
        httpd.server_close()
        print("[wfg-mock] stopped", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
