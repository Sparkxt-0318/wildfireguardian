"""Live road state from crossing units (DESIGN step 9, hardware/vehicle-unit/DESIGN.md section 10).

Only active when ``WFG_API_LIVE_CLOSURES=1`` (``Settings.live_closures``). A crossing laptop sends one JSON text frame
per verdict transition on ``WS /v1/live/closures``::

    {"event": "CLOSED" | "REOPENED", "region", "lat", "lon", "utc", "unit_id", "session_id", "verdict_id"}
    optional (backward compatible): CLOSED  "ahead": [{"lat", "lon"}, ...]   flame point(s) ahead of the vehicle
                                     REOPENED "claim_token": "<token from the CLOSED ack>", "closes_verdict_id": "<id>"

This module holds the pure parts: strict message validation, the per-region closure state (closure records, tokens,
state versions, pending recomputes) and the derived road graph without closed edges. The FastAPI wiring (socket,
handshake checks, route-check inputs, dispatch-plan recompute) lives in ``api.app``.

Assumptions and limits (stated, not verified in the field; every number below is a PLACEHOLDER):
  * the GNSS point is matched to edge chords in EPSG:5179 (the study graphs carry no intermediate edge geometry),
    planar metres, limit 300 m (``config.SNAP_MAX_M``). A CLOSED closes the whole widened match
    (``GraphIndex.nearest_edge(..., margin_m=MATCH_MARGIN_M)``: every chord within dmin + 20 m and every edge at a
    junction within 20 m), plus the same for each ``ahead`` flame point, so GNSS error at a junction closes more
    roads, never fewer (fail closed). The edge ids are returned in the ack.
  * a closure is a record per (unit_id, session_id, verdict_id) holding a secret ``claim_token`` that is returned only
    in that CLOSED's ack. An edge is closed while any record names it. A REOPENED withdraws one record only when it
    carries that record's token (compared in constant time), its point is within REOPEN_RADIUS_M of the CLOSED point
    (or an ``ahead`` point) and its own widened match shares an edge or a node with the record. Anything else is
    refused and the road stays closed (fail closed). Holder ids are never echoed.
  * a repeated CLOSED with the same (unit_id, session_id, verdict_id) is idempotent: no new record, the same token.
    A CLOSED whose edges include every edge of an older record of the same unit/session supersedes that record (the
    ack lists ``superseded_verdict_ids``), so a CLOSED/CROSS FAST/CLOSED flicker at one crossing reopens with one
    REOPENED.
  * CROSS FAST and SPRAY THEN RE-CHECK are crossing-app verdicts and never road state: they are rejected, never applied.
  * the API does not judge freshness of the unit's ``utc``; it is recorded as sent. Closures live in memory only and are
    lost when the API restarts. The crossing client (apps/crossing/crossing/simlink.py) therefore resends every closure
    it still holds on each (re)connect and every 60 s, and shows "ROUTING NOT UPDATED" while a CLOSED is unconfirmed
    or refused; a REOPENED replayed after a restart gets NOT_CLOSED, which is harmless. Between an API restart and
    the unit's resend, routing runs without that closure.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import hmac
import re
import secrets
import threading
from collections import OrderedDict
from pathlib import Path

EVENTS = ("CLOSED", "REOPENED")
FIELDS = ("event", "region", "lat", "lon", "utc", "unit_id", "session_id", "verdict_id")
OPTIONAL_FIELDS = {"CLOSED": ("ahead",), "REOPENED": ("claim_token", "closes_verdict_id")}
MAX_FRAME_CHARS = 4096
MAX_AHEAD = 4

# PLACEHOLDER limits (not tuned, not field-verified; for the fire service / operator to set).
MATCH_MARGIN_M = 20.0        # a CLOSED also closes every chord within dmin + 20 m and every edge at a junction within 20 m
REOPEN_RADIUS_M = 50.0       # a REOPENED must be within 50 m of its CLOSED point (reopen_max_view_m 40 m + GNSS scatter)
RATE_PER_S = 20.0            # per-connection token bucket: refill per second
RATE_BURST = 60.0            # per-connection token bucket: size
RETRY_S = 5.0                # a failed or refused recompute is retried at most this often while changes are pending
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_ID_RE = re.compile(r"^[\x21-\x7e]{1,128}$")          # printable ASCII, no spaces/control characters
_REGION_RE = re.compile(r"^[a-z0-9_]{1,64}$")


class LiveEventError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _number(name: str, v, lo: float, hi: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise LiveEventError("VALIDATION_ERROR", "%s must be a number (degrees, WGS84)" % name)
    v = float(v)
    if not math.isfinite(v) or v < lo or v > hi:
        raise LiveEventError("VALIDATION_ERROR", "%s must be finite and within [%g, %g]" % (name, lo, hi))
    return v


def parse_event(text) -> dict:
    """Validate one frame strictly; return the normalised event or raise LiveEventError. Nothing is applied here."""
    if not isinstance(text, str):
        raise LiveEventError("VALIDATION_ERROR", "send one JSON object per text frame")
    if len(text) > MAX_FRAME_CHARS:
        raise LiveEventError("VALIDATION_ERROR", "frame longer than %d characters" % MAX_FRAME_CHARS)

    def _no_constant(tok):
        raise ValueError("non-finite number %s" % tok)
    try:
        msg = json.loads(text, parse_constant=_no_constant)
    except ValueError as exc:
        raise LiveEventError("VALIDATION_ERROR", "frame is not valid JSON: %s" % exc)
    if not isinstance(msg, dict):
        raise LiveEventError("VALIDATION_ERROR", "frame must be a JSON object")
    ev = msg.get("event")
    if ev not in EVENTS:      # checked first so CROSS_FAST etc. get the explicit message even with other faults
        raise LiveEventError("UNKNOWN_EVENT", "event %r is not road state; only CLOSED and REOPENED are accepted "
                                              "(CROSS FAST and SPRAY THEN RE-CHECK never leave the crossing app)" % (ev,))
    missing = [k for k in FIELDS if k not in msg]
    extra = sorted(k for k in msg if k not in FIELDS and k not in OPTIONAL_FIELDS[ev])
    if missing or extra:
        raise LiveEventError("VALIDATION_ERROR", "fields must be exactly %s plus optional %s for %s (missing %s, unknown %s)"
                             % (list(FIELDS), list(OPTIONAL_FIELDS[ev]), ev, missing, extra))
    region = msg["region"]
    if not isinstance(region, str) or not _REGION_RE.match(region):
        raise LiveEventError("VALIDATION_ERROR", "region must be a region id such as uljin_2022")
    lat = _number("lat", msg["lat"], -90.0, 90.0)
    lon = _number("lon", msg["lon"], -180.0, 180.0)
    utc = msg["utc"]
    if not isinstance(utc, str) or len(utc) > 64:
        raise LiveEventError("VALIDATION_ERROR", "utc must be an ISO 8601 time string")
    try:
        t = dt.datetime.fromisoformat(utc.strip().replace("Z", "+00:00"))
    except ValueError:
        raise LiveEventError("VALIDATION_ERROR", "utc must be an ISO 8601 time such as 2026-11-17T03:00:00Z")
    if t.tzinfo is None:
        raise LiveEventError("VALIDATION_ERROR", "utc must carry a time zone (use Z for UTC)")
    out = {"event": ev, "region": region, "lat": lat, "lon": lon,
           "utc": t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}
    for k in ("unit_id", "session_id", "verdict_id"):
        v = msg[k]
        if not isinstance(v, str) or not _ID_RE.match(v):
            raise LiveEventError("VALIDATION_ERROR", "%s must be 1-128 printable ASCII characters without spaces" % k)
        out[k] = v
    if "closes_verdict_id" in msg:
        v = msg["closes_verdict_id"]
        if not isinstance(v, str) or not _ID_RE.match(v):
            raise LiveEventError("VALIDATION_ERROR", "closes_verdict_id must be 1-128 printable ASCII characters without spaces")
        out["closes_verdict_id"] = v
    if "claim_token" in msg:
        v = msg["claim_token"]
        if not isinstance(v, str) or not _TOKEN_RE.match(v):
            raise LiveEventError("VALIDATION_ERROR", "claim_token must be the token returned in the CLOSED ack")
        out["claim_token"] = v
    if "ahead" in msg:
        pts = msg["ahead"]
        if not isinstance(pts, list) or len(pts) > MAX_AHEAD:
            raise LiveEventError("VALIDATION_ERROR", "ahead must be a list of at most %d {lat, lon} points" % MAX_AHEAD)
        ahead = []
        for p in pts:
            if not isinstance(p, dict) or set(p) != {"lat", "lon"}:
                raise LiveEventError("VALIDATION_ERROR", "each ahead point must be exactly {lat, lon}")
            ahead.append({"lat": _number("ahead lat", p["lat"], -90.0, 90.0),
                          "lon": _number("ahead lon", p["lon"], -180.0, 180.0)})
        out["ahead"] = ahead
    return out


def ids_of(text) -> dict:
    """Best-effort {"event", "verdict_id"} of a frame that failed validation, so the unit can match the error ack.
    Only short printable strings are echoed; anything else is left out."""
    out = {}
    try:
        msg = json.loads(text) if isinstance(text, str) and len(text) <= MAX_FRAME_CHARS else None
    except ValueError:
        msg = None
    if isinstance(msg, dict):
        for k in ("event", "verdict_id"):
            v = msg.get(k)
            if isinstance(v, str) and len(v) <= 128 and v.isprintable():
                out[k] = v
    return out


# ------------------------------------------------------------------------------------------------ derived graph
def derive_graph(graph: dict, closed) -> tuple:
    """Return (graph copy without the closed edges and without forbidden_turns pairs naming them, dropped turn count).
    Every other key (revision included) is unchanged, so hazard packets bound to the revision still apply."""
    closed = set(closed)
    g = dict(graph)
    g["edges"] = [e for e in graph["edges"] if e["id"] not in closed]
    turns = graph.get("forbidden_turns")
    dropped = 0
    if turns is not None:
        kept = [p for p in turns if not (p[0] in closed or p[1] in closed)]
        dropped = len(turns) - len(kept)
        g["forbidden_turns"] = kept
    return g, dropped


class DerivedGraphs:
    """Derived graph bytes keyed by (base graph SHA-256, closed edge ids); a dispatch plan of thousands of attempts
    re-serialises the graph once, not once per attempt."""

    def __init__(self, size: int = 4):
        self._cache: OrderedDict = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def bytes_for(self, base_path: Path, base_sha: str, closed: tuple) -> tuple:
        key = (base_sha, closed)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return hit
        g, dropped = derive_graph(json.loads(Path(base_path).read_text()), closed)
        data = json.dumps(g, separators=(",", ":"), allow_nan=False).encode()
        out = (data, hashlib.sha256(data).hexdigest(), dropped)
        with self._lock:
            self._cache[key] = out
            while len(self._cache) > self._size:
                self._cache.popitem(last=False)
        return out

    def write(self, base_path: Path, base_sha: str, closed: tuple, out_path: Path) -> tuple:
        """Write the derived graph to ``out_path``; return (sha256, dropped forbidden-turn pairs)."""
        data, sha, dropped = self.bytes_for(base_path, base_sha, closed)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".json.tmp")
        tmp.write_bytes(data)
        tmp.replace(out_path)
        return sha, dropped


# ------------------------------------------------------------------------------------------------ state
def new_token() -> str:
    return secrets.token_urlsafe(16)


def token_matches(given, stored) -> bool:
    return isinstance(given, str) and isinstance(stored, str) and hmac.compare_digest(given.encode(), stored.encode())


class LiveState:
    """Closure records per region plus what the recompute needs.

    ``records[region][(unit_id, session_id, verdict_id)]`` = {..., "edge_ids": [...], "claim_token": ...}. An edge is
    closed while any record names it. ``version[region]`` is a monotonic counter bumped (under the lock) whenever the
    set of closed edges changes, whoever changed it. ``pending[region]`` lists road-state changes no finished recompute
    has covered yet; ``running[region]`` is the one live recompute in flight (recomputes are coalesced per region).
    Tokens never leave this object except through ``close()`` (for the CLOSED ack)."""

    def __init__(self):
        self.lock = threading.RLock()
        self.records: dict = {}           # region -> {(unit, session, verdict): record}
        self.version: dict = {}           # region -> int
        self.last_plan: dict = {}         # region -> validated DispatchPlanRequest body
        self.origin_plan: dict = {}       # region -> {origin_id: dispatch plan job id}
        self.origin_version: dict = {}    # region -> {origin_id: state version of the newest live recompute covering it}
        self.pending: dict = {}           # region -> [{"seq", "edges", "all_origins", "trigger"}]
        self.pending_seq: dict = {}       # region -> int
        self.running: dict = {}           # region -> {"seq", "job_id", "version"}
        self.recompute_status: dict = {}  # region -> last recompute outcome (for GET /v1/live/state and acks)
        self.graphs = DerivedGraphs()

    # ---- road state
    def _closed(self, region: str) -> set:
        return {e for r in self.records.get(region, {}).values() for e in r["edge_ids"]}

    def closed_edges(self, region: str) -> tuple:
        with self.lock:
            return tuple(sorted(self._closed(region)))

    def state_version(self, region: str) -> int:
        with self.lock:
            return int(self.version.get(region, 0))

    def snapshot(self, region: str) -> tuple:
        """(closed edge ids, state version) read together."""
        with self.lock:
            return tuple(sorted(self._closed(region))), int(self.version.get(region, 0))

    def close(self, region: str, claim: tuple, verdict_id: str, edge_ids, record: dict) -> dict:
        """Add (or repeat) the record of one CLOSED. Returns {"newly": edges open before, "token", "duplicate",
        "superseded": verdict ids of older records of the same claim whose edges this one covers, "version"}."""
        edge_ids = sorted(set(edge_ids))
        key = (claim[0], claim[1], verdict_id)
        with self.lock:
            reg = self.records.setdefault(region, {})
            old = reg.get(key)
            if old is not None:
                return {"newly": [], "token": old["claim_token"], "duplicate": True, "superseded": [],
                        "edge_ids": list(old["edge_ids"]), "version": int(self.version.get(region, 0))}
            before = self._closed(region)
            superseded = [k for k, r in reg.items() if k[:2] == key[:2] and set(r["edge_ids"]) <= set(edge_ids)]
            for k in superseded:
                reg.pop(k)
            tok = new_token()
            reg[key] = dict(record, edge_ids=edge_ids, claim_token=tok)
            newly = sorted(set(edge_ids) - before)
            if newly:
                self.version[region] = int(self.version.get(region, 0)) + 1
            return {"newly": newly, "token": tok, "duplicate": False, "superseded": sorted(k[2] for k in superseded),
                    "edge_ids": edge_ids, "version": int(self.version.get(region, 0))}

    def records_of(self, region: str, claim: tuple) -> list:
        """Copies (without tokens) of every record this (unit_id, session_id) holds in the region."""
        with self.lock:
            return [{k: v for k, v in r.items() if k != "claim_token"}
                    for key, r in self.records.get(region, {}).items() if key[:2] == tuple(claim)]

    def find_by_token(self, region: str, claim: tuple, token) -> dict | None:
        """The record of this claim whose token matches (constant-time compare against each), as a copy without the
        token; None when none matches."""
        hit = None
        with self.lock:
            for key, r in self.records.get(region, {}).items():
                if key[:2] == tuple(claim) and token_matches(token, r["claim_token"]):
                    hit = {k: v for k, v in r.items() if k != "claim_token"}
        return hit

    def holder_count(self, region: str, edge_ids) -> dict:
        """{edge id: number of records holding it} for the given edges that are closed. No holder ids."""
        with self.lock:
            out = {}
            for r in self.records.get(region, {}).values():
                for e in r["edge_ids"]:
                    if e in edge_ids:
                        out[e] = out.get(e, 0) + 1
            return out

    def withdraw(self, region: str, claim: tuple, verdict_id: str) -> tuple:
        """Remove one record; return (edges that are now open, edges of the record still closed by other records)."""
        with self.lock:
            reg = self.records.get(region, {})
            rec = reg.pop((claim[0], claim[1], verdict_id), None)
            if rec is None:
                return [], []
            now = self._closed(region)
            reopened = sorted(e for e in rec["edge_ids"] if e not in now)
            still = sorted(e for e in rec["edge_ids"] if e in now)
            if reopened:
                self.version[region] = int(self.version.get(region, 0)) + 1
            return reopened, still

    # ---- dispatch plans the recompute reruns
    def remember_plan(self, region: str, body: dict):
        with self.lock:
            self.last_plan[region] = json.loads(json.dumps(body))

    def plan_body(self, region: str):
        with self.lock:
            b = self.last_plan.get(region)
            return json.loads(json.dumps(b)) if b is not None else None

    def note_plan_origins(self, region: str, job_id: str, origin_ids):
        with self.lock:
            m = self.origin_plan.setdefault(region, {})
            for o in origin_ids:
                m[o] = job_id

    def plan_of_origin(self, region: str, origin_id: str):
        with self.lock:
            return self.origin_plan.get(region, {}).get(origin_id)

    def note_origin_version(self, region: str, origin_ids, version: int):
        with self.lock:
            m = self.origin_version.setdefault(region, {})
            for o in origin_ids:
                m[o] = max(int(version), int(m.get(o, -1)))

    def origin_latest_version(self, region: str, origin_id: str):
        with self.lock:
            return self.origin_version.get(region, {}).get(origin_id)

    # ---- pending / coalesced recomputes
    def add_pending(self, region: str, edges, all_origins: bool, trigger: dict) -> int:
        with self.lock:
            seq = int(self.pending_seq.get(region, 0)) + 1
            self.pending_seq[region] = seq
            self.pending.setdefault(region, []).append({"seq": seq, "edges": sorted(set(edges)),
                                                        "all_origins": bool(all_origins), "trigger": dict(trigger)})
            return seq

    def pending_view(self, region: str) -> dict | None:
        """Union of what is pending: {"seq", "edges", "all_origins", "trigger", "count"} or None."""
        with self.lock:
            ents = self.pending.get(region) or []
            if not ents:
                return None
            return {"seq": max(e["seq"] for e in ents), "edges": sorted({x for e in ents for x in e["edges"]}),
                    "all_origins": any(e["all_origins"] for e in ents), "trigger": dict(ents[-1]["trigger"]),
                    "count": len(ents)}

    def clear_pending(self, region: str, up_to_seq: int):
        with self.lock:
            self.pending[region] = [e for e in self.pending.get(region) or [] if e["seq"] > up_to_seq]

    def pending_regions(self) -> list:
        with self.lock:
            return [r for r, ents in self.pending.items() if ents]
