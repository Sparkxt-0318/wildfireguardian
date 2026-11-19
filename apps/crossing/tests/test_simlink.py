"""crossing.simlink (step 9, DESIGN.md section 10), as rebuilt after review findings R9-01, R9-08 and R9-09.

R9-01: only a FLAME-BACKED CLOSED (raw verdict CLOSED, fresh, DOSE_OVER_LIMIT / NO_WATER_FOR_SPRAY, FLAME + radar
FLAME_EFFECT held long enough) leaves the app, at the recorded flame location, once per location; REOPENED only for a
location this link closed, at the stored location, when the reopen view confirmed it. Faults, expiry, startup, smoke,
CROSS FAST, SPRAY and driving on never send anything.
R9-08: replayed or simulated data never reaches the routing API as live state (CLI refusal and run-time block).
R9-09: claims are acked (stop-and-wait), re-asserted after every reconnect, retried on transient failures, refused
terminally (and shown) on terminal codes; a REOPENED supersedes an unacked CLOSED.
The socket-level tests use an in-process fake WebSocket (no port is opened)."""
import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

from crossing import decision as dc
from crossing import simlink as sl
from crossing.simlink import (FIELDS, MERGE_RADIUS_M, SimLink, SimLinkClient, TickEvidence, make_message,
                              position_ok)

POS = {"lat": 36.39, "lon": 128.70, "utc": "2026-11-17T10:15:00Z", "fix": 1}
POSITIONS = {"ok": POS, "none": None, "no_fix": dict(POS, fix=0), "nan": dict(POS, lat=float("nan")),
             "out_of_range": dict(POS, lon=200.0), "missing_lon": {"lat": 36.39, "fix": 1}}
DEPOT = {"lat": 36.60, "lon": 126.60}
FIRE = {"lat": 36.62, "lon": 126.62}
UTC = "2026-11-17T10:15:00Z"
FAULT_REASONS = (["LINK_DOWN"], ["VERDICT_EXPIRED"], ["NO_VERDICT"], ["VALUE_INVALID:tc_air_c"],
                 ["SENSOR_NOT_FRESH:radar"], ["SENSOR_FAULT:tc_plate"], ["FLAME_UNKNOWN", "RADAR_UNKNOWN"],
                 ["NO_NEAR_EDGE", "FLAME_NOT_CONFIRMED"], ["FLAME_EVIDENCE_TOO_SHORT"], ["INTERNAL_ERROR:X"])


def offset(p, de_m=0.0, dn_m=0.0):
    return sl.en_to_latlon((p["lat"], p["lon"]), de_m, dn_m)


def ev(state, reasons=(), *, fresh=True, flame="FLAME", radar="FLAME_EFFECT", held=5.0, loc=FIRE, in_view=False,
       view=(), sim=False, mode="live", vid="v1"):
    return TickEvidence(state=state, reasons=list(reasons), verdict_id=vid, verdict_fresh=fresh, flame_status=flame,
                        radar_status=radar, flame_held_s=held, min_flame_evidence_s=3.0, flame_location=loc,
                        crossing_in_view=in_view, view_points=list(view), utc=UTC, sim=sim, mode=mode)


def over_limit(**kw):
    return ev(dc.CLOSED, ["DOSE_OVER_LIMIT"], **kw)


def no_flame_closed(**kw):
    kw.setdefault("flame", "NO_FLAME")
    kw.setdefault("radar", "NO_EFFECT")
    kw.setdefault("loc", None)
    return ev(dc.CLOSED, ["FLAME_NOT_CONFIRMED"], **kw)


def msgs(link, evs):
    out = []
    for e in evs:
        o = link.step(e)
        if o is not None:
            out.append(o.message)
    return out


# ------------------------------------------------------------------------------------------------ R9-01 rules
def test_approach_fire_then_dose_over_limit_stop_sends_exactly_one_closed_at_the_flame():
    link = SimLink("hongseong_2023", "VU-01", "VU-01-S")
    seq = [no_flame_closed(vid="start"),                                   # startup at the depot: nothing
           ev(dc.CLOSED, ["FLAME_EVIDENCE_TOO_SHORT"], held=1.0, vid="a1"),  # flame seen, not long enough
           over_limit(vid="stop1"),                                        # stop: dose over the limit
           over_limit(vid="stop2", loc=offset(FIRE, 3.0, 2.0)),             # same flame, re-estimated a few m away
           over_limit(vid="stop3", loc=offset(FIRE, -10.0, 0.0))]
    out = msgs(link, seq)
    assert len(out) == 1
    m = out[0]
    assert set(m) == set(FIELDS) and m["event"] == dc.CLOSED
    assert (m["lat"], m["lon"]) == (FIRE["lat"], FIRE["lon"]) and m["verdict_id"] == "stop1"
    assert m["region"] == "hongseong_2023" and m["unit_id"] == "VU-01" and m["utc"].endswith("Z")
    assert len(link.closed) == 1


def test_no_water_for_spray_is_flame_backed_too():
    assert len(msgs(SimLink("r"), [ev(dc.CLOSED, ["DOSE_OVER_LIMIT", "NO_WATER_FOR_SPRAY"])])) == 1
    assert len(msgs(SimLink("r"), [ev(dc.CLOSED, ["NO_WATER_FOR_SPRAY"])])) == 1


@pytest.mark.parametrize("reasons", FAULT_REASONS)
def test_start_link_down_expiry_and_no_flame_closed_send_nothing(reasons):
    link = SimLink("r")
    seq = [no_flame_closed(vid="start"), ev(dc.CLOSED, reasons, loc=DEPOT), ev(dc.CLOSED, reasons, loc=None),
           ev(dc.CLOSED, reasons, flame="UNKNOWN", radar="UNKNOWN")]
    assert msgs(link, seq) == [] and link.closed == [] and link.pending is None


def test_expired_or_unbacked_dose_over_limit_sends_nothing():
    link = SimLink("r")
    seq = [over_limit(fresh=False),                         # raw verdict already expired
           over_limit(flame="NO_FLAME"), over_limit(flame="UNKNOWN"),
           over_limit(radar="NO_EFFECT"), over_limit(radar="UNKNOWN"),          # smoke: no radar effect
           over_limit(held=2.9), over_limit(held=None), over_limit(held=float("nan")),
           over_limit(loc=None), over_limit(loc={"lat": float("nan"), "lon": 1.0}), over_limit(loc={"lat": 1.0}),
           ev(dc.CROSS_FAST, ["DOSE_OVER_LIMIT"]), ev("SOMETHING", ["DOSE_OVER_LIMIT"]), None]
    assert msgs(link, seq) == [] and link.closed == []


def test_smoke_only_scene_never_sends():
    link = SimLink("r")
    for reasons in (["FLAME_NOT_CONFIRMED"], ["FLAME_UNKNOWN"], ["DOSE_OVER_LIMIT"]):
        for flame in ("NO_FLAME", "UNKNOWN"):
            assert link.step(ev(dc.CLOSED, reasons, flame=flame, radar="NO_EFFECT")) is None
    assert link.closed == []


def test_cross_fast_then_passing_through_then_fault_closed_sends_nothing():
    link = SimLink("r")
    seq = [ev(dc.CROSS_FAST, ["DOSE_WITHIN_LIMIT"]), ev(dc.SPRAY, ["DOSE_WITHIN_SPRAY_MARGIN"]),
           no_flame_closed(loc=offset(FIRE, 30.0, 0.0)),               # far side of the crossed road
           ev(dc.CLOSED, ["SENSOR_NOT_FRESH:thermal"], loc=offset(FIRE, 40.0, 0.0)),
           ev(dc.CLOSED, ["REOPEN_CROSSING_NOT_IN_VIEW", "REOPEN_HOLD_NOT_MET"], flame="NO_FLAME", radar="NO_EFFECT")]
    assert msgs(link, seq) == [] and link.closed == []


def test_closure_then_reopened_then_driving_on():
    link = SimLink("r", "VU-01", "S1")
    closed = msgs(link, [over_limit(vid="c1")])
    assert [m["event"] for m in closed] == [dc.CLOSED]
    link.unit_id, link.session_id = "VU-01", "S2"            # ids changed later: the REOPENED uses the closing ids
    near, far = offset(FIRE, 2.0, 1.0), offset(FIRE, 8.0, 1.0)
    seq = [ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=False, view=[near, far], flame="NO_FLAME",
              radar="NO_EFFECT"),                                          # view not confirmed: nothing
           ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[near, far], fresh=False),  # expired
           ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[near, far], vid="r1", flame="NO_FLAME",
              radar="NO_EFFECT", loc=None)]
    out = msgs(link, seq)
    assert len(out) == 1 and out[0]["event"] == dc.REOPENED
    assert (out[0]["lat"], out[0]["lon"]) == (FIRE["lat"], FIRE["lon"])    # the stored location, not the vehicle
    assert out[0]["session_id"] == "S1" and out[0]["verdict_id"] == "r1"
    assert link.closed == []
    # driving on: default CLOSEDs everywhere, and another REOPENED of the same crossing: nothing more
    drive = [no_flame_closed(loc=offset(FIRE, 60.0 + 10 * i, 0.0)) for i in range(5)]
    drive += [ev(dc.CLOSED, ["LINK_DOWN"]), ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True,
                                               view=[near, far])]
    assert msgs(link, drive) == []


def test_reopened_for_a_place_never_closed_sends_nothing():
    link = SimLink("r")
    msgs(link, [over_limit()])
    elsewhere = offset(FIRE, 500.0, 0.0)
    assert link.step(ev(dc.REOPENED, [], in_view=True, view=[elsewhere])) is None
    assert link.step(ev(dc.REOPENED, [], in_view=True, view=[])) is None
    assert len(link.closed) == 1


def test_cross_fast_and_spray_never_leave_and_never_clear_closures():
    link = SimLink("r")
    msgs(link, [over_limit()])
    for state in (dc.CROSS_FAST, dc.SPRAY):
        for _ in range(3):
            assert link.step(ev(state, ["DOSE_WITHIN_LIMIT"])) is None
        with pytest.raises(ValueError):
            make_message(state, "r", "u", "s", "v", POS)
    assert len(link.closed) == 1
    assert link.step(over_limit()) is None                 # still closed: no second CLOSED


def test_locations_merge_within_the_placeholder_radius_only():
    link = SimLink("r")
    inside = offset(FIRE, MERGE_RADIUS_M * 0.8, 0.0)
    outside = offset(FIRE, MERGE_RADIUS_M * 3.0, 0.0)
    out = msgs(link, [over_limit(), over_limit(loc=inside), over_limit(loc=outside, vid="v2")])
    assert [(m["lat"], m["lon"]) for m in out] == [(FIRE["lat"], FIRE["lon"]), (outside["lat"], outside["lon"])]


def test_old_signatures_send_nothing():
    link = SimLink("r")
    c = SimLinkClient("ws://127.0.0.1:1/x", "r")
    for state in (dc.CLOSED, dc.REOPENED, dc.CROSS_FAST, dc.SPRAY):
        v = dc.Verdict(state, ["DOSE_OVER_LIMIT"], 1.0, 6.0, details={"stamp": {"lat": 1.0, "lon": 2.0}})
        assert link.outgoing(v, POS) is None and c.offer(v, POS) is None
    assert c.queue == [] and link.closed == []


def test_utc_fallback_is_laptop_utc_with_zone():
    msg = make_message(dc.CLOSED, "r", "u", "s", "v", dict(POS, utc="not a time"))
    assert msg["utc"].endswith("Z") and "T" in msg["utc"]


def test_region_required():
    with pytest.raises(ValueError):
        SimLink("")


def test_position_ok_rules():
    assert position_ok(POS)
    for k, p in POSITIONS.items():
        assert position_ok(p) == (k == "ok"), k


def test_en_to_latlon_inverts_the_pipeline_frame():
    from crossing.pipeline import Pipeline
    p = Pipeline.__new__(Pipeline)
    p.origin = None
    e, n = Pipeline.en(p, 36.6, 126.6)
    assert (e, n) == (0.0, 0.0)
    e, n = Pipeline.en(p, 36.6012, 126.6034)
    back = sl.en_to_latlon(p.origin, e, n)
    assert abs(back["lat"] - 36.6012) < 1e-9 and abs(back["lon"] - 126.6034) < 1e-9
    assert sl.en_to_latlon(None, 1.0, 1.0) is None and sl.en_to_latlon((36.6, 126.6), float("nan"), 0.0) is None


def _api_live():
    live = Path(__file__).resolve().parents[3] / "api" / "live.py"
    if not live.exists():
        pytest.skip("api/live.py not present")
    spec = importlib.util.spec_from_file_location("api_live_by_path", live)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 - the API module may need its package context
        pytest.skip("api/live.py not importable standalone: %s" % exc)
    return mod


def test_messages_pass_the_routing_api_parser():
    mod = _api_live()
    for state in (dc.CLOSED, dc.REOPENED):
        msg = make_message(state, "hongseong", "VU-01", "VU-01-S", "abc123", POS)
        out = mod.parse_event(json.dumps(msg))
        assert out["event"] == state
    bad = dict(make_message(dc.CLOSED, "r", "u", "s", "v", POS), event="CROSS_FAST")
    with pytest.raises(Exception):
        mod.parse_event(json.dumps(bad))


# ------------------------------------------------------------------------------------------------ R9-08
def test_cli_refuses_sim_link_with_replay(tmp_path, capsys):
    from crossing.__main__ import main
    rc = main(["--replay", str(tmp_path), "--sim-link", "ws://127.0.0.1:8765/v1/live/closures", "--region", "r",
               "--loop", "--speed", "20", "--no-log"])
    assert rc == 2 and "refused" in capsys.readouterr().err
    assert main(["--sim-link-allow-replay", "--replay", str(tmp_path)]) == 2      # allow flag alone is an error


def test_replay_client_is_blocked_and_queues_nothing():
    c = SimLinkClient("ws://127.0.0.1:1/x", "r", mode="replay")
    assert c.blocked and "replay" in c.blocked_reason
    assert c.offer_tick(over_limit(mode="replay")) is None
    st = c.status()
    assert st["blocked"] is True and st["queued"] == 0 and st["claims"] == [] and c.link.closed == []


def test_sim_data_blocks_a_live_client_for_the_rest_of_the_run():
    c = SimLinkClient("ws://127.0.0.1:1/x", "r", mode="live")
    assert not c.blocked
    assert c.offer_tick(over_limit(sim=True)) is None
    assert c.blocked and "sim=true" in c.blocked_reason
    assert c.offer_tick(over_limit(sim=False, loc=offset(FIRE, 500.0, 0.0))) is None    # sticky
    assert c.queue == [] and c.status()["blocked_reason"]


def test_replay_sending_only_when_allowed_and_tagged():
    c = SimLinkClient("ws://127.0.0.1:1/x", "r", mode="replay", allow_replay=True)
    assert not c.blocked
    m = c.offer_tick(over_limit(mode="replay"))
    assert m is not None and m["origin"] == "replay"
    c2 = SimLinkClient("ws://127.0.0.1:1/x", "r", mode="live", allow_replay=True)
    m2 = c2.offer_tick(over_limit(sim=True))
    assert m2["origin"] == "sim"
    live = SimLinkClient("ws://127.0.0.1:1/x", "r").offer_tick(over_limit())
    assert "origin" not in live and set(live) == set(FIELDS)
    mod = _api_live()
    if "origin" not in getattr(mod, "FIELDS", ()) and "origin" not in str(getattr(mod, "OPTIONAL_FIELDS", "")):
        with pytest.raises(Exception):                       # an API without origin support refuses it: fail closed
            mod.parse_event(json.dumps(m))


def test_offer_tick_never_raises():
    c = SimLinkClient("ws://127.0.0.1:1/x", "r")
    assert c.offer_tick(None) is None and c.offer_tick("junk") is None
    bad = over_limit()
    bad.reasons = None
    assert c.offer_tick(bad) is None


# ------------------------------------------------------------------------------------------------ R9-09 (fake socket)
class FakeServer:
    """In-process stand-in for WS /v1/live/closures. ``behaviour(msg, conn_no, server)`` returns actions:
    ("ack", dict) | ("drop",) | ("silent",)."""

    def __init__(self, behaviour=None):
        self.received = []
        self.connections = 0
        self.closed = {}
        self.connect_kw = []                      # keyword arguments of every connect() (subprotocols etc.)
        self.behaviour = behaviour or self.default

    def default(self, msg, n, server):
        if msg["event"] == "CLOSED":
            self.closed[msg["verdict_id"]] = msg
        else:
            self.closed.pop(msg.get("closes_verdict_id", ""), None)
        return [("ack", {"ok": True, "event": msg["event"], "verdict_id": msg["verdict_id"]})]

    def connect(self, url, **kw):
        self.connect_kw.append(kw)
        return FakeConn(self)


class FakeConn:
    def __init__(self, server):
        self.server = server

    async def __aenter__(self):
        self.server.connections += 1
        self.ws = FakeWS(self.server, self.server.connections)
        return self.ws

    async def __aexit__(self, *a):
        self.ws.closed = True
        return False


class FakeWS:
    def __init__(self, server, n):
        self.server, self.n, self.closed = server, n, False
        self.q = asyncio.Queue()

    async def send(self, text):
        if self.closed:
            raise ConnectionError("closed")
        msg = json.loads(text)
        self.server.received.append((self.n, msg))
        for act in self.server.behaviour(msg, self.n, self.server):
            if act[0] == "ack":
                await self.q.put(json.dumps(act[1]))
            elif act[0] == "drop":
                self.closed = True
                await self.q.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.q.get()
        if item is None:
            raise StopAsyncIteration
        return item


def client(**kw):
    kw.setdefault("reconnect_min_s", 0.01)
    kw.setdefault("reconnect_max_s", 0.02)
    kw.setdefault("retry_min_s", 0.01)
    kw.setdefault("retry_max_s", 0.02)
    kw.setdefault("ack_timeout_s", 0.2)
    return SimLinkClient("ws://fake/v1/live/closures", "r", "VU-01", "S1", **kw)


def drive(c, until, timeout=4.0, during=None):
    async def main():
        stop = asyncio.Event()
        task = asyncio.ensure_future(c.run(stop))
        t0 = time.monotonic()
        while not until() and time.monotonic() - t0 < timeout:
            if during is not None:
                during()
            await asyncio.sleep(0.005)
        stop.set()
        c._kick()
        await asyncio.wait_for(task, 3.0)
    asyncio.run(main())


@pytest.fixture
def fake(monkeypatch):
    import websockets.asyncio.client as wac
    srv = FakeServer()
    monkeypatch.setattr(wac, "connect", srv.connect)
    return srv


def test_api_restart_gets_the_closed_reasserted(fake):
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"] and c.status()["claims"][0]["status"] == "acked")
    assert [m["event"] for _, m in fake.received] == ["CLOSED"]
    # the API restarts (state lost) and the connection drops; the client reconnects and asserts CLOSED again
    fake.closed.clear()
    fake.received.clear()
    drive(c, lambda: "c1" in fake.closed)
    assert "c1" in fake.closed and [m["event"] for _, m in fake.received] == ["CLOSED"]
    assert fake.connections == 2 and c.status()["claims"][0]["status"] == "acked"


def test_drop_after_send_before_ack_resends(fake):
    def behaviour(msg, n, srv):
        if n == 1:
            return [("drop",)]                    # frame received, connection lost before the ack
        return srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert [(n, m["event"]) for n, m in fake.received] == [(1, "CLOSED"), (2, "CLOSED")]
    assert c.status()["claims"][0]["attempts"] == 2


def test_no_ack_within_timeout_reconnects_and_resends(fake):
    def behaviour(msg, n, srv):
        return [("silent",)] if n == 1 else srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client(ack_timeout_s=0.05)
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert [n for n, _ in fake.received] == [1, 2] and fake.connections == 2


def test_snap_too_far_is_shown_and_not_retried(fake):
    fake.behaviour = lambda msg, n, srv: [("ack", {"ok": False, "code": "SNAP_TOO_FAR", "verdict_id": msg["verdict_id"],
                                                   "error": "point is 900 m from the nearest road edge"})]
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: False, timeout=0.4)
    assert len(fake.received) == 1
    st = c.status()
    assert st["claims"][0]["status"] == "refused" and "SNAP_TOO_FAR" in st["claims"][0]["error"]
    assert len(st["not_closed_in_routing"]) == 1 and st["queued"] == 0


def test_transient_error_is_retried_with_backoff(fake):
    def behaviour(msg, n, srv):
        if len(srv.received) < 3:
            return [("ack", {"ok": False, "code": "INTERNAL_ERROR", "error": "boom"})]
        return srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert len(fake.received) == 3 and fake.connections == 1


def test_closed_then_reopened_both_unacked_sends_only_reopened(fake):
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    c.offer_tick(ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[FIRE], vid="r1"))
    assert [m["event"] for m in c.queue] == ["REOPENED"]
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert [m["event"] for _, m in fake.received] == ["REOPENED"]
    assert (fake.received[0][1]["lat"], fake.received[0][1]["lon"]) == (FIRE["lat"], FIRE["lon"])


def test_reopened_carries_the_claim_token_when_the_api_issued_one(fake):
    def behaviour(msg, n, srv):
        out = srv.default(msg, n, srv)
        if msg["event"] == "CLOSED":
            out[0][1]["claim_token"] = "tok_0123456789abcdef"
        return out
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    c.offer_tick(ev(dc.REOPENED, [], in_view=True, view=[FIRE], vid="r1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    reo = [m for _, m in fake.received if m["event"] == "REOPENED"]
    assert len(reo) == 1 and reo[0]["claim_token"] == "tok_0123456789abcdef" and reo[0]["closes_verdict_id"] == "c1"
    assert "c1" not in fake.closed                     # the fake API withdrew the closure the token names


def test_reopened_without_token_is_the_plain_message(fake):
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    c.offer_tick(ev(dc.REOPENED, [], in_view=True, view=[FIRE], vid="r1"))
    drive(c, lambda: c.status()["claims"][0]["event"] == "REOPENED" and c.status()["claims"][0]["status"] == "acked")
    reo = [m for _, m in fake.received if m["event"] == "REOPENED"]
    assert len(reo) == 1 and set(reo[0]) == set(FIELDS)


def test_many_closures_are_never_dropped():
    c = client(maxsize=2)
    for i in range(6):
        c.offer_tick(over_limit(vid="c%d" % i, loc=offset(FIRE, 500.0 * i, 0.0)))
    assert len(c.queue) == 6 and c.dropped == 0 and all(m["event"] == "CLOSED" for m in c.queue)


def test_blocked_client_never_sends(fake):
    c = client(mode="replay")
    c.offer_tick(over_limit(mode="replay"))
    drive(c, lambda: False, timeout=0.3)
    assert fake.received == [] and fake.connections == 0


def test_success_without_our_verdict_id_is_not_an_ack(fake):
    """A frame saying ok:true without the claim's verdict_id (e.g. a greeting) never acks a CLOSED (fail closed)."""
    def behaviour(msg, n, srv):
        return [("ack", {"ok": True, "note": "hello"})] + srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert c.status()["claims"][0]["status"] == "acked" and len(fake.received) == 1
    st = SimLinkClient("ws://x", "r")
    st.offer_tick(over_limit(vid="c9"))
    claim = next(iter(st.claims.values()))
    assert st.apply_ack(claim, {"ok": True}) == "ignored" and claim["status"] == "pending"
    assert st.apply_ack(claim, {"ok": True, "verdict_id": "other"}) == "mismatch" and claim["status"] == "pending"
    assert st.apply_ack(claim, {"ok": False, "code": "SNAP_TOO_FAR"}) == "refused" and claim["status"] == "refused"


# ------------------------------------------------------------------------------------------------ handshake token
TOKEN = "e2e-test-token-0123456789"


def test_subprotocols_offer_the_token_only_when_configured(fake, caplog):
    """api/app.py live_handshake_refusal: the client offers wfg-live.v1 and, with a token, wfg-token.<token>. The token
    is never in status(), repr() or the logs."""
    import logging
    caplog.set_level(logging.DEBUG)
    plain = client()
    assert plain.subprotocols() == ["wfg-live.v1"] and plain.status()["token"] == "not set"
    c = client(token=TOKEN)
    assert c.subprotocols() == ["wfg-live.v1", "wfg-token." + TOKEN]
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    assert fake.connect_kw and all(kw.get("subprotocols") == ["wfg-live.v1", "wfg-token." + TOKEN]
                                   for kw in fake.connect_kw)
    st = c.status()
    assert st["token"] == "set" and TOKEN not in json.dumps(st, default=str) and TOKEN not in repr(c)
    assert TOKEN not in caplog.text
    # error text that happens to echo the token is scrubbed before it is stored
    assert c._scrub("unsupported subprotocol wfg-token." + TOKEN) == "unsupported subprotocol wfg-token.***"


@pytest.mark.parametrize("bad", ["", "has space", "semi;colon", "a" * 513, "tok\n"])
def test_a_malformed_token_disables_the_link(fake, bad):
    c = client(token=bad)
    assert c.blocked and "token" in c.blocked_reason and (not bad.strip() or bad not in c.blocked_reason)
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: False, timeout=0.2)
    assert fake.received == [] and fake.connections == 0


# ------------------------------------------------------------------------------------------------ API codes
def _api_live_codes():
    """Every ack code the live path of the routing API can return: refusals in api/app.py, LiveEventError codes in
    api/live.py, the inline {"ok": False, "code": ...} frames, and the APIError codes raised by the region lookup /
    edge matching before any state change."""
    import re
    api = Path(__file__).resolve().parents[3] / "api"
    if not (api / "app.py").exists() or not (api / "live.py").exists():
        pytest.skip("api/ not present")
    app_src, live_src = (api / "app.py").read_text(), (api / "live.py").read_text()
    live_part = app_src[app_src.index("def _register_live"):]
    codes = set(re.findall(r'refuse\("([A-Z_]+)"', live_part))
    codes |= set(re.findall(r'"ok": False, "code": "([A-Z_]+)"', live_part))
    codes |= set(re.findall(r'LiveEventError\("([A-Z_]+)"', live_src))
    raised = {"DATA_UNAVAILABLE", "UNKNOWN_REGION", "SNAP_TOO_FAR", "VALIDATION_ERROR", "INTERNAL_ERROR"}
    src = app_src + (api / "regions.py").read_text()
    assert all(('"%s"' % c) in src for c in raised), "an expected API code disappeared from api/"
    return codes | raised


def test_every_api_live_code_is_classified():
    codes = _api_live_codes()
    assert {"REOPEN_UNAUTHORIZED", "REOPEN_TOO_FAR", "REOPEN_NOT_ON_CLOSED_ROAD", "NOT_CLOSED", "CLOSED_BY_OTHER_UNIT",
            "RATE_LIMITED"} <= codes
    unclassified = codes - set(sl.TERMINAL_CODES) - set(sl.RETRY_CODES)
    assert not unclassified, "API ack codes the sim-link does not classify: %s" % sorted(unclassified)
    assert not set(sl.TERMINAL_CODES) & set(sl.RETRY_CODES)


@pytest.mark.parametrize("code", ["REOPEN_UNAUTHORIZED", "REOPEN_TOO_FAR", "REOPEN_NOT_ON_CLOSED_ROAD", "NOT_CLOSED",
                                  "CLOSED_BY_OTHER_UNIT"])
def test_refused_reopened_is_logged_shown_and_never_resent(fake, code, caplog):
    """A refused REOPENED leaves the road closed in routing (the safe side): not re-sent (also not after a reconnect),
    listed in reopen_refused_in_routing with its code, logged once at WARNING."""
    import logging
    caplog.set_level(logging.WARNING, logger="crossing.simlink")

    def behaviour(msg, n, srv):
        if msg["event"] == "REOPENED":
            return [("ack", {"ok": False, "code": code, "verdict_id": msg["verdict_id"], "event": "REOPENED",
                             "error": "the road stays closed"})]
        return srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    c.offer_tick(ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[FIRE], vid="r1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "refused")
    drive(c, lambda: False, timeout=0.3)                 # reconnects: nothing is re-sent
    events = [m["event"] for _, m in fake.received]
    assert events == ["CLOSED", "REOPENED"] and fake.connections >= 2
    st = c.status()
    assert [x["code"] for x in st["reopen_refused_in_routing"]] == [code] and st["not_closed_in_routing"] == []
    assert st["queued"] == 0 and code in st["claims"][0]["error"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "REOPENED r1 refused" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.parametrize("code", ["SNAP_TOO_FAR", "UNKNOWN_REGION", "VALIDATION_ERROR"])
def test_refused_closed_keeps_being_reasserted(fake, code):
    """A refused CLOSED is never given up: shown as not closed in routing and asserted again after every reconnect."""
    fake.behaviour = lambda msg, n, srv: [("ack", {"ok": False, "code": code, "verdict_id": msg["verdict_id"],
                                                   "error": "refused"})]
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "refused")
    drive(c, lambda: fake.connections >= 2 and len(fake.received) >= 2 and
          c.status()["claims"][0]["status"] == "refused")
    assert [m["event"] for _, m in fake.received] == ["CLOSED"] * len(fake.received) and len(fake.received) >= 2
    assert len({n for n, _ in fake.received}) == len(fake.received)    # once per connection, no backoff loop
    st = c.status()
    assert len(st["not_closed_in_routing"]) == 1 and st["not_closed_in_routing"][0]["code"] == code


@pytest.mark.parametrize("code", ["RATE_LIMITED", "DATA_UNAVAILABLE", "INTERNAL_ERROR", "SOMETHING_NEW"])
def test_retry_codes_resend_the_reopened(fake, code):
    """Transient refusals (and codes the client does not know) are retried with backoff, REOPENED included."""
    def behaviour(msg, n, srv):
        if msg["event"] == "REOPENED" and sum(1 for _, m in srv.received if m["event"] == "REOPENED") < 3:
            return [("ack", {"ok": False, "code": code, "verdict_id": msg["verdict_id"], "error": "later"})]
        return srv.default(msg, n, srv)
    fake.behaviour = behaviour
    c = client()
    c.offer_tick(over_limit(vid="c1"))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked")
    c.offer_tick(ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[FIRE], vid="r1"))
    drive(c, lambda: c.status()["claims"][0]["event"] == "REOPENED" and c.status()["claims"][0]["status"] == "acked")
    assert [m["event"] for _, m in fake.received] == ["CLOSED", "REOPENED", "REOPENED", "REOPENED"]
    assert c.status()["reopen_refused_in_routing"] == []


def test_cli_token_comes_from_the_environment_only(tmp_path, monkeypatch, capsys):
    from crossing.__main__ import main
    monkeypatch.delenv("WFG_TEST_TOKEN_UNSET", raising=False)
    rc = main(["--pi", "ws://127.0.0.1:1/stream", "--sim-link", "ws://127.0.0.1:1/v1/live/closures", "--region", "r",
               "--sim-link-token-env", "WFG_TEST_TOKEN_UNSET"])
    assert rc == 2 and "not set" in capsys.readouterr().err
    monkeypatch.setenv("WFG_TEST_TOKEN_BAD", "bad token!")
    rc = main(["--pi", "ws://127.0.0.1:1/stream", "--sim-link", "ws://127.0.0.1:1/v1/live/closures", "--region", "r",
               "--sim-link-token-env", "WFG_TEST_TOKEN_BAD"])
    err = capsys.readouterr().err
    assert rc == 2 and "bad token!" not in err


# ------------------------------------------------------------------------------------------------ real API end to end
REPO = Path(__file__).resolve().parents[3]
E2E_REGION = "hongseong_2023"
_PICK = r'''
import json, os, sys
from pathlib import Path
from api.regions import GraphIndex, to_wgs84
root = Path(os.environ.get("WFG_API_DATA_ROOT") or "data/routing")
g = GraphIndex.load(sys.argv[1], root / "graphs" / sys.argv[1] / "graph.json")
for eid in g.edge_ids:
    u, v, _ = g.edges[eid]
    ku, kv = g.node_index[u], g.node_index[v]
    if not (g.allowed[ku] and g.allowed[kv]) or g.reverse_edges.get(eid) is None:
        continue
    mx, my = (g.xy[ku] + g.xy[kv]) / 2.0
    lon, lat = (float(t) for t in to_wgs84(mx, my))
    m = g.nearest_edge(lon, lat)
    if eid in m["edge_ids"] and m["distance_m"] < 1.0:
        print(json.dumps({"lat": lat, "lon": lon, "edge_id": eid}))
        break
'''


def _api_python():
    import os
    py = Path(os.environ.get("WFG_API_TEST_PYTHON") or REPO / ".venv" / "bin" / "python")
    if not py.exists():
        pytest.skip("routing API interpreter not found (%s); set WFG_API_TEST_PYTHON" % py)
    return py


def _free_loopback_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    except OSError as exc:
        pytest.skip("loopback bind blocked here: %s" % exc)
    finally:
        s.close()


def _get_json(url, timeout=2.0):
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


@pytest.fixture(scope="module")
def routing_api(tmp_path_factory):
    """The real API app (api/__main__, uvicorn) on 127.0.0.1 with WFG_API_LIVE_CLOSURES=1 and WFG_API_LIVE_TOKEN set,
    run by the API's own interpreter. If that environment has no WebSocket implementation for uvicorn (a .venv built
    before api/requirements.txt pinned websockets==13.1), this test's copy of websockets 13.1 is put on its PYTHONPATH
    for this process only (nothing is installed)."""
    import os
    import subprocess
    import sys
    py = _api_python()
    data = Path(os.environ.get("WFG_API_DATA_ROOT") or REPO / "data" / "routing")
    if not (data / "graphs" / E2E_REGION / "graph.json").exists():
        pytest.skip("SKIPPED (data not in repo): recorded %s road graph missing" % E2E_REGION)
    port = _free_loopback_port()
    tmp = tmp_path_factory.mktemp("routing_api")
    env = dict(os.environ, WFG_API_LIVE_CLOSURES="1", WFG_API_LIVE_TOKEN=TOKEN, WFG_API_HOST="127.0.0.1",
               WFG_API_PORT=str(port), WFG_API_RUNTIME_DIR=str(tmp / "runtime"), WFG_API_WORKERS="1",
               WFG_API_DATA_ROOT=str(data), PYTHONDONTWRITEBYTECODE="1")
    env.pop("WFG_API_LIVE_ORIGINS", None)
    env.pop("WFG_API_LIVE_HOSTS", None)
    paths = [str(REPO)]
    has_ws = subprocess.run([str(py), "-c", "import websockets"], cwd=str(REPO), env=env,
                            capture_output=True).returncode == 0
    if not has_ws:
        import websockets
        shim = tmp / "ws_shim"
        shim.mkdir()
        (shim / "websockets").symlink_to(Path(websockets.__file__).resolve().parent)
        paths.insert(0, str(shim))
    env["PYTHONPATH"] = os.pathsep.join(paths)
    pick = subprocess.run([str(py), "-c", _PICK, E2E_REGION], cwd=str(REPO), env=env, capture_output=True, text=True,
                          timeout=120)
    if pick.returncode != 0 or not pick.stdout.strip():
        pytest.skip("could not pick a road point with the API interpreter: %s" % pick.stderr[-500:])
    point = json.loads(pick.stdout.strip().splitlines()[-1])
    log_path = tmp / "api.log"
    with open(log_path, "wb") as logf:
        proc = subprocess.Popen([str(py), "-m", "api"], cwd=str(REPO), env=env, stdout=logf, stderr=subprocess.STDOUT)
    base = "http://127.0.0.1:%d" % port
    try:
        t0 = time.monotonic()
        while True:
            try:
                _get_json(base + "/v1/live/state?region=" + E2E_REGION)
                break
            except Exception:  # noqa: BLE001 - not up yet
                if proc.poll() is not None or time.monotonic() - t0 > 120:
                    out = log_path.read_text(errors="replace")[-2000:]
                    if "Operation not permitted" in out or "PermissionError" in out:
                        pytest.skip("loopback serve blocked here: %s" % out[-300:])
                    pytest.fail("routing API did not come up (has websockets: %s):\n%s" % (has_ws, out))
                time.sleep(0.25)
        yield {"base": base, "url": "ws://127.0.0.1:%d/v1/live/closures" % port, "point": point,
               "log": log_path, "shimmed_websockets": not has_ws, "python": str(py), "sys": sys.version}
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:  # noqa: BLE001
            proc.kill()


def _e2e_client(api, **kw):
    kw.setdefault("reconnect_min_s", 0.05)
    kw.setdefault("reconnect_max_s", 0.2)
    kw.setdefault("retry_min_s", 0.05)
    kw.setdefault("retry_max_s", 0.2)
    kw.setdefault("ack_timeout_s", 10.0)
    return SimLinkClient(api["url"], E2E_REGION, "VU-E2E", kw.pop("session_id", "S-E2E"), **kw)


def test_end_to_end_against_the_routing_api(routing_api, caplog):
    """The real API (flag on, token set) and SimLinkClient over 127.0.0.1: no token -> handshake refused, nothing
    applied; with the token a flame-backed CLOSED closes the matched road, the REOPENED of the same claim (carrying the
    claim_token from the CLOSED ack) lifts it; CROSS FAST / SPRAY are never sent; a REOPENED without the claim token
    is refused (REOPEN_UNAUTHORIZED), shown, not re-sent, and the road stays closed (fail closed)."""
    import logging
    caplog.set_level(logging.DEBUG)
    api, point = routing_api, {"lat": routing_api["point"]["lat"], "lon": routing_api["point"]["lon"]}
    edge = routing_api["point"]["edge_id"]

    def closed_edges():
        return _get_json(api["base"] + "/v1/live/state?region=" + E2E_REGION)["closed_edge_ids"]

    assert closed_edges() == []
    # 1. no token: refused before accept, nothing applied
    c0 = _e2e_client(api, session_id="S-NOTOKEN")
    c0.offer_tick(over_limit(vid="e2e-c0", loc=point))
    drive(c0, lambda: c0.status()["handshake_refused"], timeout=10.0)
    assert c0.status()["handshake_refused"] is True and c0.connections == 0 and closed_edges() == []
    assert c0.status()["claims"][0]["status"] == "pending"

    # 2. with the token: CROSS FAST / SPRAY never leave, CLOSED is applied
    c = _e2e_client(api, token=TOKEN)
    assert c.offer_tick(ev(dc.CROSS_FAST, ["DOSE_WITHIN_LIMIT"], vid="e2e-x")) is None
    assert c.offer_tick(ev(dc.SPRAY, ["SPRAY_THEN_RECHECK"], vid="e2e-s")) is None
    c.offer_tick(over_limit(vid="e2e-c1", loc=point))
    drive(c, lambda: c.status()["claims"][0]["status"] == "acked", timeout=20.0)
    st = c.status()
    assert st["claims"][0]["status"] == "acked", st
    ack = c.acks[-1]
    assert ack["ok"] is True and ack["verdict_id"] == "e2e-c1" and isinstance(ack.get("claim_token"), str)
    assert edge in ack["edge_ids"] and st["last_ack"]["claim_token"] == "***"
    assert edge in closed_edges()

    # 3. REOPENED of the same claim lifts it
    c.offer_tick(ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[point], vid="e2e-r1",
                    flame="NO_FLAME", radar="NO_EFFECT"))
    drive(c, lambda: c.status()["claims"][0]["event"] == "REOPENED" and c.status()["claims"][0]["status"] == "acked",
          timeout=20.0)
    assert c.status()["claims"][0]["status"] == "acked", c.status()
    assert c.acks[-1]["ok"] is True and c.acks[-1].get("reopened_verdict_id") == "e2e-c1"
    assert closed_edges() == []
    reo = [m for m in c.sent if m["event"] == "REOPENED"]
    assert len(reo) == 1 and reo[0]["closes_verdict_id"] == "e2e-c1" and reo[0]["claim_token"] == ack["claim_token"]

    # 4. a REOPENED that lost its claim token (e.g. the CLOSED ack never arrived) is refused; the road stays closed
    c.offer_tick(over_limit(vid="e2e-c2", loc=point))
    drive(c, lambda: any(x["verdict_id"] == "e2e-c2" and x["status"] == "acked" for x in c.status()["claims"]),
          timeout=20.0)
    assert edge in closed_edges()
    for claim in c.claims.values():
        if claim["msg"]["verdict_id"] == "e2e-c2":
            claim["token"] = None
    c.offer_tick(ev(dc.REOPENED, ["REOPEN_CONDITIONS_HELD"], in_view=True, view=[point], vid="e2e-r2",
                    flame="NO_FLAME", radar="NO_EFFECT"))
    drive(c, lambda: any(x["verdict_id"] == "e2e-r2" and x["status"] == "refused" for x in c.status()["claims"]),
          timeout=20.0)
    drive(c, lambda: False, timeout=0.5)
    st = c.status()
    assert [x["code"] for x in st["reopen_refused_in_routing"]] == ["REOPEN_UNAUTHORIZED"], st
    assert edge in closed_edges()

    events = [m["event"] for m in c.sent]
    assert events.count("REOPENED") == 2 and set(events) == {"CLOSED", "REOPENED"}
    assert all(set(m) <= set(FIELDS) | {"claim_token", "closes_verdict_id"} for m in c.sent)
    # the shared token never reaches the State, the logs or the server's own log
    assert TOKEN not in json.dumps(c.status(), default=str) and TOKEN not in caplog.text
    assert TOKEN not in api["log"].read_text(errors="replace")
