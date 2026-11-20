"""Step 9 client: live road state from the crossing app to the routing API (DESIGN.md section 10). Flag-guarded.

Only enabled with ``python -m crossing --sim-link ws://127.0.0.1:8765/v1/live/closures --region <id>`` (the API
side needs ``WFG_API_LIVE_CLOSURES=1``). Without ``--sim-link`` nothing in this module runs and nothing leaves the
laptop. Verdicts are ADVISORY for trained crews; every limit here is a PLACEHOLDER.

What may leave the app (and nothing else):
    {"event": "CLOSED" | "REOPENED", "region", "lat", "lon", "utc", "unit_id", "session_id", "verdict_id"}
plus, only when replay/simulated sending was explicitly allowed (``--sim-link-allow-replay``), an
``"origin": "replay" | "sim"`` tag. The routing API (api/live.py) does not accept ``origin`` as built, so it refuses
such frames (VALIDATION_ERROR, terminal, shown in the UI) and nothing replayed or simulated is applied: fail closed.
Plus the optional ``claim_token`` / ``closes_verdict_id`` on a REOPENED when the API issued a token (see below).

Rules (``SimLink.step``; as built after review findings R9-01 / R9-08 / R9-09, 2026-11-17):
- CLOSED is CLOSED's default for every non-go situation (no flame, link down, faults, expiry, moving ...), so a
  CLOSED verdict alone says nothing about a road. A CLOSED is sent only when it is FLAME-BACKED, judged on the RAW
  verdict of this tick (not ``effective()``: an expired verdict has lost its reasons): the raw verdict is CLOSED and
  not expired, its reasons include ``DOSE_OVER_LIMIT`` or ``NO_WATER_FOR_SPRAY``, the fused flame status is FLAME,
  the radar status is FLAME_EFFECT, and the flame has held for ``min_flame_evidence_s``. Faults or missing data
  (LINK_DOWN, VERDICT_EXPIRED, NO_VERDICT, VALUE_*, SENSOR_*, FLAME_UNKNOWN, NO_NEAR_EDGE ...) never send anything.
  Smoke never sends anything (FLAME needs radar FLAME_EFFECT). Startup sends nothing.
- The CLOSED location is the flame location the pipeline recorded THIS tick (``Pipeline.flame_ref``: vehicle GNSS
  position + near-edge distance along the GNSS course), never the vehicle position. No valid flame location: nothing
  is sent and nothing is left pending.
- State is kept per location, not as one global last state: every location this link closed is remembered; a new
  flame-backed CLOSED within ``MERGE_RADIUS_M`` (50 m, PLACEHOLDER) of one already closed is not sent again.
- REOPENED is sent only for a location this link closed earlier, with that stored location's coordinates (and the
  unit/session ids it was closed with), only when the raw REOPENED verdict is fresh, the reopen view confirmed the
  crossing (``crossing_in_view``) and the crossing the view looked at lies within ``MERGE_RADIUS_M`` of the stored
  location. The location is then forgotten, so later default CLOSEDs while driving on can never close it again.
- CROSS FAST and SPRAY THEN RE-CHECK never leave the app and never clear stored closures.
- ``utc`` is the GNSS UTC when it parses as ISO 8601, else the laptop UTC (always with a "Z" zone).

``SimLinkClient`` (I/O):
- Refuses to send replayed or simulated data unless ``allow_replay`` (CLI ``--sim-link-allow-replay``): a replay
  run, or any hello / reading envelope with ``sim: true``, disables the link for the rest of the run with a stated
  reason in ``status()`` (shown by the UI); nothing is queued.
- Keeps one ASSERTED claim per location (the latest of CLOSED / REOPENED, status pending / in flight / acked /
  refused) and sends stop-and-wait: one frame, then its ack (the API answers every frame with exactly one ack; acks
  are matched by ``verdict_id`` when the ack carries one). Only ``ok: true`` acks a claim.
- A REOPENED supersedes an unacked CLOSED of the same location (only the latest state is ever resent).
- After every (re)connect every CLOSED claim is asserted again, acked or not (the API keeps closures in memory only;
  its close() is idempotent per (unit_id, session_id) claim).
- Handshake (api/app.py ``live_handshake_refusal``): the client offers the subprotocol ``wfg-live.v1`` and, when a
  shared token is configured (``token=``; CLI: env ``WFG_SIM_LINK_TOKEN`` or the env var named by
  ``--sim-link-token-env``), ``wfg-token.<token>`` as well. The token is never logged, never put in ``status()``,
  the research log or error strings (scrubbed), and the websockets handshake logger is pinned above DEBUG so the
  request headers are never logged. A token with characters other than letters, digits, ``-`` and ``_`` disables
  the link (stated reason, nothing sent). A refused handshake (HTTP 403: token missing or wrong, Host or Origin not
  allowed) is retried with the reconnect backoff and shown (``status()["handshake_refused"]``).
- Transient failures are retried with backoff: no ack within ``ack_timeout_s`` (the connection is dropped and
  re-opened), INTERNAL_ERROR, DATA_UNAVAILABLE, RATE_LIMITED, unknown codes, or a connection drop before the ack.
  Terminal refusals (``TERMINAL_CODES``: VALIDATION_ERROR, UNKNOWN_EVENT, SNAP_TOO_FAR, UNKNOWN_REGION, NOT_CLOSED,
  CLOSED_BY_OTHER_UNIT, REOPEN_UNAUTHORIZED, REOPEN_TOO_FAR, REOPEN_NOT_ON_CLOSED_ROAD) are not retried with backoff
  and are logged (WARNING). A refused CLOSED stays a held claim: it is listed in
  ``status()["not_closed_in_routing"]`` until an ``ok: true`` ack (the UI shows "ROAD NOT CLOSED IN ROUTING") and it
  is still asserted again after every (re)connect and every ``REASSERT_EVERY_S`` (fail closed: a CLOSED is never given
  up). A refused REOPENED is not re-sent; the API leaves the road closed (safe), and the claim is listed in
  ``status()["reopen_refused_in_routing"]`` (the UI shows "REOPEN NOT APPLIED IN ROUTING").
- While connected, held CLOSED claims are also re-sent every ``REASSERT_EVERY_S`` (60 s, PLACEHOLDER).
- When a CLOSED ack carries a ``claim_token`` (newer API), the REOPENED of that location carries it back with
  ``closes_verdict_id``; without a token the plain message is sent (an older API rejects unknown keys).
- Nothing is ever dropped from the claims for lack of space; ``dropped`` stays 0 (kept for the State schema).
It never blocks the pipeline: ``offer_tick`` only updates memory and never raises.
"""
from __future__ import annotations

import asyncio
import collections
import json
import logging
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

from .decision import CLOSED, CROSS_FAST, REOPENED, SPRAY, Verdict, effective

log = logging.getLogger("crossing.simlink")

EVENTS = (CLOSED, REOPENED)
NEVER_SENT = (CROSS_FAST, SPRAY)
FIELDS = ("event", "region", "lat", "lon", "utc", "unit_id", "session_id", "verdict_id")
ORIGINS = ("live", "replay", "sim")
# CLOSED reasons that mean "a flame was measured and judged not crossable" (only reachable with every sensor fresh,
# FLAME + radar FLAME_EFFECT held, near edge observed, far echo, GNSS fix, valid depth and intensity; decision.py)
FLAME_CLOSE_REASONS = ("DOSE_OVER_LIMIT", "NO_WATER_FOR_SPRAY")
MERGE_RADIUS_M = 50.0          # PLACEHOLDER: one closed location per 50 m (merge on CLOSED, match on REOPENED)
REASSERT_EVERY_S = 60.0        # PLACEHOLDER: held CLOSED claims are also re-sent this often while connected
# Ack codes of the routing API (api/live.py, api/app.py). Terminal: the same frame would be refused again, so it is not
# retried with backoff (a CLOSED is still re-asserted after a reconnect and every REASSERT_EVERY_S). Retried: the frame
# was not applied for a passing reason. Any other (unknown) code is retried too.
TERMINAL_CODES = ("VALIDATION_ERROR", "UNKNOWN_EVENT", "SNAP_TOO_FAR", "UNKNOWN_REGION", "NOT_CLOSED",
                  "CLOSED_BY_OTHER_UNIT", "REOPEN_UNAUTHORIZED", "REOPEN_TOO_FAR", "REOPEN_NOT_ON_CLOSED_ROAD")
RETRY_CODES = ("INTERNAL_ERROR", "DATA_UNAVAILABLE", "RATE_LIMITED")
LIVE_SUBPROTOCOL = "wfg-live.v1"               # api/app.py LIVE_SUBPROTOCOL
TOKEN_SUBPROTOCOL_PREFIX = "wfg-token."        # api/app.py LIVE_TOKEN_PREFIX
TOKEN_ENV = "WFG_SIM_LINK_TOKEN"               # default env var holding the shared token (CLI)
_TOKEN_RE = re.compile(r"\A[A-Za-z0-9_-]{1,512}\Z")   # \Z: "$" would accept a trailing newline
# The websockets library logs every handshake header (the token subprotocol included) at DEBUG; its logger for this
# client is pinned to INFO so that never happens, whatever the app's log level.
_WS_LOG = logging.getLogger("crossing.simlink.ws")
_WS_LOG.setLevel(logging.INFO)
EARTH_R = 6371008.8


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _utc(value: Any) -> str:
    if isinstance(value, str) and value:
        try:
            t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if t.tzinfo is not None:
                return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def position_ok(position: Optional[dict]) -> bool:
    """A usable road position: finite lat in [-90, 90], lon in [-180, 180], and fix >= 1 when a fix is given."""
    if not isinstance(position, dict):
        return False
    lat, lon = position.get("lat"), position.get("lon")
    if not (_finite(lat) and _finite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return False
    fix = position.get("fix", 1)
    return isinstance(fix, int) and not isinstance(fix, bool) and fix >= 1


def distance_m(a: dict, b: dict) -> float:
    """Equirectangular distance between two {lat, lon} points [m] (fine at the <= 1 km scale used here)."""
    k = math.pi / 180.0 * EARTH_R
    lat0 = math.radians((a["lat"] + b["lat"]) / 2.0)
    return math.hypot((a["lon"] - b["lon"]) * k * math.cos(lat0), (a["lat"] - b["lat"]) * k)


def en_to_latlon(origin: Optional[Sequence[float]], e: float, n: float) -> Optional[dict]:
    """Inverse of ``Pipeline.en`` (local east/north metres about ``origin`` = (lat0, lon0), equirectangular)."""
    if origin is None or not (_finite(e) and _finite(n)):
        return None
    lat0, lon0 = float(origin[0]), float(origin[1])
    k = math.pi / 180.0 * EARTH_R
    c = math.cos(math.radians(lat0))
    if not (_finite(lat0) and _finite(lon0)) or c <= 0:
        return None
    return {"lat": lat0 + float(n) / k, "lon": lon0 + float(e) / (k * c)}


def make_message(state: str, region: str, unit_id: str, session_id: str, verdict_id: str,
                 position: dict, origin: str = "live") -> dict:
    """The exact wire message for one event. ``origin`` other than "live" adds the optional ``origin`` key (only
    ever used when replay/simulated sending was explicitly allowed); live messages carry exactly FIELDS."""
    if state not in EVENTS:
        raise ValueError("only CLOSED and REOPENED may leave the app, got %r" % (state,))
    if origin not in ORIGINS:
        raise ValueError("origin must be one of %s" % (ORIGINS,))
    msg = {"event": state, "region": str(region), "lat": float(position["lat"]), "lon": float(position["lon"]),
           "utc": _utc(position.get("utc")), "unit_id": str(unit_id), "session_id": str(session_id),
           "verdict_id": str(verdict_id)}
    if origin != "live":
        msg["origin"] = origin
    return msg


def _code(reason: Any) -> str:
    return str(reason).split(":", 1)[0]


@dataclass
class TickEvidence:
    """What one pipeline tick tells the link (built by ``tick_evidence``). Everything defaults to "not shown"."""
    state: Optional[str] = None                 # RAW verdict state of this tick
    reasons: List[str] = field(default_factory=list)
    verdict_id: str = "unknown"
    verdict_fresh: bool = False                 # effective(verdict, now) is the verdict itself (not expired)
    flame_status: Optional[str] = None
    radar_status: Optional[str] = None
    flame_held_s: Optional[float] = None
    min_flame_evidence_s: float = 3.0
    flame_location: Optional[dict] = None       # {"lat", "lon"} of the flame recorded THIS tick, else None
    crossing_in_view: bool = False
    view_points: List[dict] = field(default_factory=list)   # [{"lat", "lon"}] of the crossing the view confirmed
    utc: Optional[str] = None                   # GNSS UTC of this tick
    sim: bool = False
    mode: str = "live"


def flame_backed(ev: TickEvidence) -> bool:
    """True only for a fresh raw CLOSED that a measured flame justifies (see module docstring)."""
    if ev.state != CLOSED or ev.verdict_fresh is not True:
        return False
    codes = {_code(r) for r in (ev.reasons or [])}
    if not codes & set(FLAME_CLOSE_REASONS):
        return False
    if ev.flame_status != "FLAME" or ev.radar_status != "FLAME_EFFECT":
        return False
    return _finite(ev.flame_held_s) and _finite(ev.min_flame_evidence_s) and \
        ev.flame_held_s >= ev.min_flame_evidence_s


@dataclass
class Outgoing:
    loc_id: str
    message: dict


class SimLink:
    """Per-location transition logic (pure, no I/O). ``step(evidence)`` -> Outgoing or None."""

    def __init__(self, region: str, unit_id: str = "VU-unknown", session_id: str = "unknown",
                 merge_radius_m: float = MERGE_RADIUS_M, origin: str = "live"):
        if not region:
            raise ValueError("--region is required with --sim-link")
        self.region = region
        self.unit_id = unit_id
        self.session_id = session_id
        self.merge_radius_m = float(merge_radius_m)
        self.origin = origin
        self.closed: List[dict] = []                 # locations this link closed: {loc_id, lat, lon, unit_id, ...}
        self.last_state: Optional[str] = None        # event of the last message produced (display only)
        self.pending = None                          # kept for the State schema; nothing is ever left pending

    def outgoing(self, verdict: Any, position: Optional[dict] = None) -> Optional[dict]:
        """Backward-compatible signature of the pre-2026-11-17 API. A bare verdict and the VEHICLE position carry no
        flame location, so under the per-location rules nothing is ever produced from them (fail closed)."""
        return None

    def _near(self, point: dict) -> Optional[dict]:
        best = None
        for c in self.closed:
            d = distance_m(c, point)
            if d <= self.merge_radius_m and (best is None or d < best[0]):
                best = (d, c)
        return best[1] if best else None

    def step(self, ev: TickEvidence) -> Optional[Outgoing]:
        if not isinstance(ev, TickEvidence):
            return None
        if ev.state == CLOSED:
            if not flame_backed(ev):
                return None
            loc = ev.flame_location
            if not position_ok(dict(loc, fix=1) if isinstance(loc, dict) else None):
                return None                          # no flame location: nothing sent, nothing pending
            if self._near(loc) is not None:
                return None                          # this location is already closed by this link
            rec = {"loc_id": uuid.uuid4().hex[:12], "lat": float(loc["lat"]), "lon": float(loc["lon"]),
                   "unit_id": self.unit_id, "session_id": self.session_id, "verdict_id": ev.verdict_id}
            self.closed.append(rec)
            msg = make_message(CLOSED, self.region, rec["unit_id"], rec["session_id"], ev.verdict_id or "unknown",
                               {"lat": rec["lat"], "lon": rec["lon"], "utc": ev.utc}, self.origin)
            self.last_state = CLOSED
            return Outgoing(rec["loc_id"], msg)
        if ev.state == REOPENED:
            if ev.verdict_fresh is not True or ev.crossing_in_view is not True:
                return None
            match = None
            for p in ev.view_points or []:
                if position_ok(dict(p, fix=1) if isinstance(p, dict) else None):
                    c = self._near(p)
                    if c is not None and (match is None or distance_m(c, p) < distance_m(match, p)):
                        match = c
            if match is None:
                return None                          # not a location this link closed: nothing to reopen
            self.closed.remove(match)
            msg = make_message(REOPENED, self.region, match["unit_id"], match["session_id"],
                               ev.verdict_id or "unknown", {"lat": match["lat"], "lon": match["lon"], "utc": ev.utc},
                               self.origin)
            self.last_state = REOPENED
            return Outgoing(match["loc_id"], msg)
        return None                                  # CROSS FAST, SPRAY, non-verdicts: never sent, nothing cleared


def tick_evidence(pipe: Any, verdict: Any, now: float, inp: Any, flame_status: Optional[str],
                  radar_status: Optional[str], flame_held_s: Optional[float]) -> TickEvidence:
    """Evidence for one tick from the pipeline (called after the decision and the flame_ref update of the tick).
    The reopen view's crossing is ``Pipeline._crossing_patch()``; on a REOPENED tick the flame status is not FLAME, so
    flame_ref was not updated in that tick and the patch is the one the view used."""
    fresh = isinstance(verdict, Verdict) and effective(verdict, now) is verdict
    flame_loc = None
    fr = getattr(pipe, "flame_ref", None)
    origin = getattr(pipe, "origin", None)
    if isinstance(fr, dict) and fr.get("rx") == now and fr.get("pos") is not None:
        flame_loc = en_to_latlon(origin, fr["pos"][0], fr["pos"][1])
    in_view = getattr(inp, "crossing_in_view", None) is True
    points: List[dict] = []
    if in_view:
        patch = pipe._crossing_patch() if hasattr(pipe, "_crossing_patch") else None
        if isinstance(patch, dict):
            for key in ("near", "far"):
                pt = patch.get(key)
                if pt is not None:
                    ll = en_to_latlon(origin, pt[0], pt[1])
                    if ll is not None:
                        points.append(ll)
    try:
        min_ev = float(pipe.cfg.decision.min_flame_evidence_s)
    except Exception:  # noqa: BLE001 - unknown config: the default 3 s placeholder
        min_ev = 3.0
    return TickEvidence(state=getattr(verdict, "state", None), reasons=list(getattr(verdict, "reasons", None) or []),
                        verdict_id=str(getattr(verdict, "verdict_id", "") or "unknown"), verdict_fresh=fresh,
                        flame_status=flame_status, radar_status=radar_status, flame_held_s=flame_held_s,
                        min_flame_evidence_s=min_ev, flame_location=flame_loc, crossing_in_view=in_view,
                        view_points=points, utc=getattr(inp, "utc", None), sim=bool(getattr(pipe, "sim", False)),
                        mode=str(getattr(pipe, "mode", "live")))


# --------------------------------------------------------------------------------------------------- client
PENDING, IN_FLIGHT, ACKED, REFUSED = "pending", "in flight", "acked", "refused"


class SimLinkClient:
    """Sends SimLink claims to the routing API WebSocket (stop-and-wait with acks), reconnects with backoff."""

    def __init__(self, url: str, region: str, unit_id: str = "VU-unknown", session_id: str = "unknown",
                 maxsize: int = 100, reconnect_min_s: float = 0.5, reconnect_max_s: float = 10.0, *,
                 mode: str = "live", allow_replay: bool = False, ack_timeout_s: float = 5.0,
                 retry_min_s: float = 1.0, retry_max_s: float = 30.0, clock=time.monotonic,
                 token: Optional[str] = None):
        self.url = url
        self.mode = mode
        self.allow_replay = bool(allow_replay)
        origin = "live" if mode != "replay" else "replay"
        self.link = SimLink(region, unit_id, session_id, origin=origin)
        self.claims: "collections.OrderedDict[str, dict]" = collections.OrderedDict()
        self.maxsize = maxsize                       # kept for callers; claims are never dropped for space
        self.dropped = 0
        self.sent: Deque[dict] = collections.deque(maxlen=20)
        self.acks: Deque[dict] = collections.deque(maxlen=20)
        self.updates: Deque[dict] = collections.deque(maxlen=20)     # leave_by_update frames from the API
        self.connected = False
        self.connections = 0
        self.last_error = ""
        self.blocked_reason = ""
        self.handshake_refused = False
        self._token = None if token is None else str(token)
        if self._token is not None and not _TOKEN_RE.match(self._token):
            self.blocked_reason = ("sim-link token must be 1-512 letters, digits, '-' or '_' (value not shown); "
                                   "sim-link disabled")
            self._token = None
        if mode == "replay" and not self.allow_replay:
            self.blocked_reason = ("replay: recorded verdicts are not live road state; sim-link disabled "
                                   "(--sim-link-allow-replay sends them tagged origin=replay)")
        self._wake: Optional[asyncio.Event] = None
        self.reconnect_min_s = reconnect_min_s
        self.reconnect_max_s = reconnect_max_s
        self.ack_timeout_s = ack_timeout_s
        self.retry_min_s = retry_min_s
        self.retry_max_s = retry_max_s
        self.clock = clock

    # -- handshake
    def subprotocols(self) -> List[str]:
        """Subprotocols offered in the handshake (api/app.py ``live_handshake_refusal``). Contains the token: never log."""
        out = [LIVE_SUBPROTOCOL]
        if self._token:
            out.append(TOKEN_SUBPROTOCOL_PREFIX + self._token)
        return out

    def _scrub(self, text: Any) -> str:
        """``text`` with the shared token (if any) replaced by ***."""
        text = str(text)
        if self._token:
            text = text.replace(self._token, "***")
        return text

    def __repr__(self) -> str:
        return "SimLinkClient(url=%r, region=%r, token=%s)" % (self.url, self.link.region,
                                                               "set" if self._token else "none")

    # -- compatibility
    @property
    def queue(self) -> List[dict]:
        """Messages waiting to be sent (pending claims), oldest first."""
        return [c["msg"] for c in self.claims.values() if c["status"] == PENDING]

    def set_ids(self, unit_id: Optional[str], session_id: Optional[str]) -> None:
        if unit_id:
            self.link.unit_id = unit_id
        if session_id:
            self.link.session_id = session_id

    def offer(self, verdict: Any, position: Optional[dict] = None) -> Optional[dict]:
        """Pre-2026-11-17 signature: a bare verdict carries no flame evidence, so nothing is produced."""
        return None

    @property
    def blocked(self) -> bool:
        return bool(self.blocked_reason)

    def _block(self, reason: str) -> None:
        if not self.blocked_reason:
            self.blocked_reason = reason
            log.warning("sim-link disabled: %s", reason)
        self._kick()

    def _kick(self) -> None:
        if self._wake is not None:
            self._wake.set()

    def offer_tick(self, ev: TickEvidence) -> Optional[dict]:
        """Apply the per-location rules to one tick; record the claim if a message results. Never raises."""
        try:
            if isinstance(ev, TickEvidence):
                if ev.sim is True:
                    if not self.allow_replay:
                        self._block("simulated data (sim=true): never sent as road state; sim-link disabled "
                                    "(--sim-link-allow-replay sends it tagged origin=sim)")
                    else:
                        self.link.origin = "sim"
                if ev.mode == "replay":
                    if not self.allow_replay:
                        self._block("replay: recorded verdicts are not live road state; sim-link disabled")
                    elif self.link.origin == "live":
                        self.link.origin = "replay"
            if self.blocked:
                return None
            out = self.link.step(ev)
            if out is None:
                return None
            old = self.claims.pop(out.loc_id, None)  # a REOPENED supersedes the CLOSED of its location
            rec = {"loc_id": out.loc_id, "event": out.message["event"], "msg": dict(out.message),
                   "status": PENDING, "attempts": 0, "next_try": 0.0, "error": None, "code": None, "token": None,
                   "refused_code": None}
            if rec["event"] == REOPENED and old is not None:
                rec["closed_verdict_id"] = old["msg"]["verdict_id"]
                if old.get("token"):
                    self._attach_token(rec, old["token"])
            self.claims[out.loc_id] = rec
            self._prune()
            self._kick()
            return out.message
        except Exception as exc:  # noqa: BLE001 - the routing link must never break the pipeline
            self.last_error = "offer: %s: %s" % (type(exc).__name__, exc)
            return None

    @staticmethod
    def _attach_token(rec: dict, token: str) -> None:
        """An API that returns a ``claim_token`` in the CLOSED ack wants it (and the CLOSED's verdict_id) back in the
        REOPENED; an API that never returns one gets the plain message (it rejects unknown keys)."""
        rec["msg"]["claim_token"] = str(token)
        rec["msg"]["closes_verdict_id"] = rec.get("closed_verdict_id") or "unknown"

    def _prune(self) -> None:
        """Forget finished REOPENED claims beyond ``maxsize`` claims (never a CLOSED, never a pending one)."""
        extra = len(self.claims) - max(1, int(self.maxsize))
        for loc in [k for k, c in self.claims.items() if c["event"] == REOPENED and c["status"] in (ACKED, REFUSED)]:
            if extra <= 0:
                break
            self.claims.pop(loc, None)
            extra -= 1

    def _next_pending(self) -> Optional[dict]:
        now = self.clock()
        for c in self.claims.values():
            if c["status"] == PENDING and c["next_try"] <= now:
                return c
        return None

    def _retry_later(self, c: dict, why: str) -> None:
        c["status"] = PENDING
        c["error"] = why
        delay = min(self.retry_max_s, self.retry_min_s * (2.0 ** max(0, c["attempts"] - 1)))
        c["next_try"] = self.clock() + delay

    def reassert_closed(self) -> None:
        """After a (re)connect and every REASSERT_EVERY_S: every CLOSED claim is sent again (the API may have restarted
        and forgotten it). A refused CLOSED too: a CLOSED is never given up (its refusal stays shown until acked)."""
        for c in self.claims.values():
            if c["event"] == CLOSED and c["status"] in (ACKED, IN_FLIGHT, PENDING, REFUSED):
                c["status"] = PENDING
                c["next_try"] = 0.0

    def apply_ack(self, c: dict, ack: Any) -> str:
        """Classify one ack for claim ``c`` -> "acked" | "refused" | "retry" | "mismatch" | "ignored". ``ok: true``
        counts only with the claim's verdict_id; a refusal without a verdict_id is matched by order (stop-and-wait).
        A superseded claim (a newer state of its location replaced it) only has its ack logged."""
        current = self.claims.get(c["loc_id"]) is c
        if not isinstance(ack, dict):
            if current:
                self._retry_later(c, "malformed ack")
            return "retry"
        vid = ack.get("verdict_id")
        if ack.get("ok") is True and vid is None:
            return "ignored"                         # a success must name our verdict_id: not our ack, keep waiting
        if vid is not None and vid != c["msg"]["verdict_id"]:
            if current:
                self._retry_later(c, "ack for another verdict_id (%s)" % (vid,))
            return "mismatch"
        if ack.get("ok") is True:
            token = ack.get("claim_token")
            if c["event"] == CLOSED and isinstance(token, str) and token:
                c["token"] = token
                if not current:                      # superseded by a REOPENED: it carries the token instead
                    nxt = self.claims.get(c["loc_id"])
                    if nxt is not None and nxt["event"] == REOPENED and nxt["status"] == PENDING:
                        self._attach_token(nxt, token)
            if current:
                c.update(status=ACKED, error=None, code=None, ack=ack, refused_code=None)
            return "acked"
        code = str(ack.get("code") or "UNKNOWN")
        err = self._scrub("%s: %s" % (code, str(ack.get("error") or "")[:300]))
        if code in TERMINAL_CODES:
            if current:
                repeat = c.get("refused_code") == code      # a re-asserted CLOSED refused again: logged once
                c.update(status=REFUSED, error=err, code=code, ack=ack, refused_code=code)
                if not repeat and c["event"] == CLOSED:
                    log.warning("sim-link: CLOSED %s refused by the routing API (%s); ROAD NOT CLOSED IN ROUTING, "
                                "re-asserted after reconnects", c["msg"]["verdict_id"], err)
                elif not repeat:
                    log.warning("sim-link: REOPENED %s refused by the routing API (%s); not re-sent, the road may "
                                "still be closed in routing", c["msg"]["verdict_id"], err)
            return "refused"
        if current:
            self._retry_later(c, err)
        return "retry"

    async def run(self, stop: Optional[asyncio.Event] = None) -> None:
        from websockets.asyncio.client import connect
        try:
            from websockets.exceptions import InvalidStatus
        except ImportError:  # pragma: no cover - older websockets
            InvalidStatus = ()

        stop = stop or asyncio.Event()
        self._wake = asyncio.Event()
        backoff = self.reconnect_min_s
        while not stop.is_set():
            if self.blocked:
                await self._sleep(stop, 1.0)
                continue
            try:
                async with connect(self.url, open_timeout=3.0, close_timeout=1.0, subprotocols=self.subprotocols(),
                                   logger=_WS_LOG) as ws:
                    self.connected = True
                    self.connections += 1
                    self.handshake_refused = False
                    backoff = self.reconnect_min_s
                    self.reassert_closed()
                    await self._session(ws, stop)
            except Exception as exc:  # noqa: BLE001 - the routing API is optional; report and retry
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if InvalidStatus and isinstance(exc, InvalidStatus) and status in (401, 403):
                    if not self.handshake_refused:
                        log.warning("sim-link: the routing API refused the handshake (HTTP %s): token missing or "
                                    "wrong, or Host/Origin not allowed; nothing sent, retrying", status)
                    self.handshake_refused = True
                    self.last_error = ("handshake refused (HTTP %s): token missing or wrong, or Host/Origin not "
                                       "allowed (sim-link token %s)" % (status, "set" if self._token else "not set"))
                else:
                    self.last_error = self._scrub("%s: %s" % (type(exc).__name__, exc))[:500]
            self.connected = False
            for c in self.claims.values():           # a frame in flight when the connection died: send again
                if c["status"] == IN_FLIGHT:
                    self._retry_later(c, "connection lost before the ack")
            if stop.is_set():
                break
            await self._sleep(stop, backoff)
            backoff = min(self.reconnect_max_s, backoff * 2.0)

    async def _sleep(self, stop: asyncio.Event, s: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=s)
        except asyncio.TimeoutError:
            pass

    async def _session(self, ws, stop: asyncio.Event) -> None:
        acks: "asyncio.Queue[Any]" = asyncio.Queue()
        closed = object()

        async def reader():
            try:
                async for text in ws:
                    try:
                        obj = json.loads(text)
                    except ValueError:
                        obj = {"raw": str(text)[:500]}
                    if isinstance(obj, dict) and obj.get("type") is not None:
                        self.updates.append(obj)     # leave_by_update etc.: not an ack
                        continue
                    self.acks.append(obj)
                    await acks.put(obj)
            finally:
                await acks.put(closed)

        task = asyncio.ensure_future(reader())
        last_assert = self.clock()
        try:
            while not stop.is_set() and not self.blocked:
                if self.clock() - last_assert >= REASSERT_EVERY_S:
                    last_assert = self.clock()
                    self.reassert_closed()
                c = self._next_pending()
                if c is None:
                    self._wake.clear()
                    if task.done():
                        return
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=0.5)
                    except asyncio.TimeoutError:
                        pass
                    continue
                c["status"] = IN_FLIGHT
                c["attempts"] += 1
                await ws.send(json.dumps(c["msg"], allow_nan=False))
                self.sent.append(c["msg"])
                deadline = self.clock() + self.ack_timeout_s
                result = "ignored"
                while result == "ignored":
                    try:
                        ack = await asyncio.wait_for(acks.get(), timeout=max(0.0, deadline - self.clock()))
                    except asyncio.TimeoutError:
                        self._retry_later(c, "no ack within %.1f s" % self.ack_timeout_s)
                        self.last_error = "no ack within %.1f s: reconnecting" % self.ack_timeout_s
                        return                       # drop the connection: a late ack must not match a resend
                    if ack is closed:
                        self._retry_later(c, "connection lost before the ack")
                        return
                    result = self.apply_ack(c, ack)
                if result == "mismatch":
                    return
        finally:
            task.cancel()

    @staticmethod
    def _redact(obj: Any) -> Any:
        """A copy of a sent frame / ack for display with the per-closure ``claim_token`` masked."""
        if isinstance(obj, dict) and "claim_token" in obj:
            return dict(obj, claim_token="***")
        return obj

    def status(self) -> dict:
        claims = [{"loc_id": c["loc_id"], "event": c["event"], "lat": c["msg"]["lat"], "lon": c["msg"]["lon"],
                   "verdict_id": c["msg"]["verdict_id"], "status": c["status"], "attempts": c["attempts"],
                   "error": c["error"], "code": c.get("refused_code")} for c in self.claims.values()]
        # a CLOSED refused once stays listed until an ok:true ack, also while it is being re-asserted (fail closed)
        not_closed = [x for x in claims if x["event"] == CLOSED and (x["status"] == REFUSED or x["code"])]
        reopen_refused = [x for x in claims if x["event"] == REOPENED and x["status"] == REFUSED]
        return {"enabled": True, "blocked": self.blocked, "blocked_reason": self.blocked_reason,
                "url": self.url, "region": self.link.region, "mode": self.mode, "allow_replay": self.allow_replay,
                "origin": self.link.origin, "connected": self.connected, "connections": self.connections,
                "token": "set" if self._token else "not set", "handshake_refused": self.handshake_refused,
                "reopen_refused_in_routing": reopen_refused,
                "queued": sum(1 for c in self.claims.values() if c["status"] in (PENDING, IN_FLIGHT)),
                "dropped": self.dropped, "last_error": self.last_error, "last_state": self.link.last_state,
                "pending": None, "closures_held": len(self.link.closed), "claims": claims,
                "not_closed_in_routing": not_closed, "merge_radius_m": self.link.merge_radius_m,
                "merge_radius_placeholder": True,
                "last_sent": self._redact(self.sent[-1]) if self.sent else None,
                "last_ack": self._redact(self.acks[-1]) if self.acks else None}
