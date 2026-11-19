"""Step 9 live road state: WS /v1/live/closures behind WFG_API_LIVE_CLOSURES=1 (hardware/vehicle-unit/DESIGN.md s10).

The data tests use the recorded Hongseong road graph and a SYNTHETIC job scheduler: route-check and dispatch-plan jobs
are recorded and answered at once with synthetic results (no kit launch). They check the API's wiring (matching,
closure state, derived graph, provenance, recompute selection, socket pushes), not routing results.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from tests.api.conftest import DATA, _settings, needs_data, scenario_set_for

REGION = "hongseong_2023"
INPUT_TIME = "2023-04-02T07:00:00Z"
DEST_NODE = "osm:6430106206"          # destination used by the existing dispatch tests


# ------------------------------------------------------------------------------------------------ no data needed
def _tiny_graph(tmp_path: Path, with_reverse: bool = True) -> Path:
    """Synthetic EPSG:5179 graph: A-B-C two-way (f/r pairs), C->D one-way; 1 km chords near Hongseong."""
    x0, y0 = 950000.0, 1830000.0
    nodes = [{"id": "A", "x": x0, "y": y0}, {"id": "B", "x": x0 + 1000, "y": y0},
             {"id": "C", "x": x0 + 1000, "y": y0 + 1000}, {"id": "D", "x": x0 + 2000, "y": y0 + 1000}]
    edges = [{"id": "ab:f", "u": "A", "v": "B", "travel_ticks": 90, "reverse_edge": "ab:r"},
             {"id": "ab:r", "u": "B", "v": "A", "travel_ticks": 90, "reverse_edge": "ab:f"},
             {"id": "bc:f", "u": "B", "v": "C", "travel_ticks": 90, "reverse_edge": "bc:r"},
             {"id": "bc:r", "u": "C", "v": "B", "travel_ticks": 90, "reverse_edge": "bc:f"},
             {"id": "cd:f", "u": "C", "v": "D", "travel_ticks": 90}]
    if not with_reverse:
        for e in edges:
            e.pop("reverse_edge", None)
    g = {"revision": "tiny-1", "crs": "EPSG:5179", "grid": {"x0": x0 - 500, "y0": y0 - 500, "resolution": 500.0, "width": 6,
                                                           "height": 4},
         "nodes": nodes, "edges": edges, "forbidden_turns": [["ab:f", "ab:r"], ["bc:f", "cd:f"]], "mid_edge_reversal": False}
    p = tmp_path / ("graph%s.json" % ("" if with_reverse else "_norev"))
    p.write_text(json.dumps(g))
    return p


def _lonlat(x, y):
    from api.regions import to_wgs84
    lon, lat = to_wgs84(x, y)
    return float(lon), float(lat)


def test_nearest_edge_on_tiny_synthetic_graph(tmp_path):
    from api.errors import APIError
    from api.regions import GraphIndex
    gi = GraphIndex.load("tiny", _tiny_graph(tmp_path))
    x0, y0 = 950000.0, 1830000.0
    m = gi.nearest_edge(*_lonlat(x0 + 400, y0 + 50))            # 50 m north of A-B, 40 % along
    assert m["edge_id"] == "ab:f" and m["edge_ids"] == ["ab:f", "ab:r"] and m["reverse_edge_id"] == "ab:r"
    assert abs(m["distance_m"] - 50.0) < 0.5 and abs(m["fraction"] - 0.4) < 1e-3
    m = gi.nearest_edge(*_lonlat(x0 + 1060, y0 + 700))           # 60 m east of B-C
    assert m["edge_ids"] == ["bc:f", "bc:r"] and abs(m["distance_m"] - 60.0) < 0.5
    m = gi.nearest_edge(*_lonlat(x0 + 1500, y0 + 1100))          # one-way edge: no reverse
    assert m["edge_ids"] == ["cd:f"] and m["reverse_edge_id"] is None
    m = gi.nearest_edge(*_lonlat(x0 + 2250, y0 + 1000))          # beyond the end node: distance to the end point
    assert m["edge_id"] == "cd:f" and abs(m["distance_m"] - 250.0) < 0.5 and m["fraction"] == 1.0
    with pytest.raises(APIError) as e:
        gi.nearest_edge(*_lonlat(x0 + 400, y0 - 301))            # 301 m south of A-B
    assert e.value.code == "SNAP_TOO_FAR" and e.value.details["nearest_edge_id"] == "ab:f"
    assert gi.nearest_edge(*_lonlat(x0 + 400, y0 - 301), max_m=400)["edge_id"] == "ab:f"
    with pytest.raises(APIError):
        gi.nearest_edge(float("nan"), 36.5)
    # graph without reverse_edge fields: the opposite-direction edge on the same chord is matched instead
    gn = GraphIndex.load("tiny", _tiny_graph(tmp_path, with_reverse=False))
    assert gn.nearest_edge(*_lonlat(x0 + 400, y0 + 50))["edge_ids"] == ["ab:f", "ab:r"]


def test_nearest_edge_widens_at_a_junction(tmp_path):
    """R9-06: 5 m before junction B with 6 m lateral GNSS error the argmin chord is B-C, but the widened match
    (PLACEHOLDER margin 20 m) also holds A-B, the road the vehicle is on; at B itself both roads are matched."""
    from api.live import MATCH_MARGIN_M
    from api.regions import GraphIndex
    gi = GraphIndex.load("tiny", _tiny_graph(tmp_path))
    x0, y0 = 950000.0, 1830000.0
    m = gi.nearest_edge(*_lonlat(x0 + 995, y0 + 6))
    assert m["edge_ids"] == ["bc:f", "bc:r"] and m["close_edge_ids"] == ["bc:f", "bc:r"]     # margin 0: argmin only
    for pt in ((x0 + 995, y0 + 6), (x0 + 1000, y0)):
        m = gi.nearest_edge(*_lonlat(*pt), margin_m=MATCH_MARGIN_M)
        assert {"ab:f", "ab:r", "bc:f", "bc:r"} <= set(m["close_edge_ids"]), (pt, m)
        assert m["close_edge_ids"][:len(m["edge_ids"])] == m["edge_ids"] and "cd:f" not in m["close_edge_ids"]
    m = gi.nearest_edge(*_lonlat(x0 + 400, y0 + 50), margin_m=MATCH_MARGIN_M)    # mid-road: no junction, one road
    assert m["close_edge_ids"] == ["ab:f", "ab:r"]


def test_graph_with_an_unknown_node_still_loads(tmp_path):
    """R9-11: an edge naming a node missing from ``nodes`` must not stop the region loading (it did not before step 9);
    it is only left out of the chord table."""
    from api.regions import GraphIndex
    g = json.loads(_tiny_graph(tmp_path).read_text())
    g["edges"].append({"id": "zz:f", "u": "C", "v": "NOPE", "travel_ticks": 10})
    p = tmp_path / "graph_bad.json"
    p.write_text(json.dumps(g))
    gi = GraphIndex.load("tiny", p)
    assert "zz:f" in gi.edges and "zz:f" not in gi.edge_ids
    assert gi.nearest_edge(*_lonlat(950400.0, 1830050.0))["edge_id"] == "ab:f"


def test_handshake_rules():
    """R9-07: Origin (exact allow-list, "null" never, absent allowed), Host (loopback / bind host / listed) and the
    optional shared token offered as a subprotocol."""
    from api.app import live_handshake_refusal
    from api.config import Settings
    base = Settings(data_root=Path("/x"), runtime_dir=Path("/y"), workers=1, python="python", host="127.0.0.1", port=8765,
                    live_closures=True)
    ok_host = {"host": "127.0.0.1:8765"}
    assert live_handshake_refusal(ok_host, [], base) is None
    assert live_handshake_refusal({"host": "localhost:8765"}, [], base) is None
    assert live_handshake_refusal({"host": "[::1]:8765"}, [], base) is None
    assert live_handshake_refusal(dict(ok_host, origin="https://evil.example"), [], base) == "origin not allowed"
    assert live_handshake_refusal(dict(ok_host, origin="null"), [], base) == "origin not allowed"
    assert live_handshake_refusal({"host": "evil.example:8765"}, [], base) == "host not allowed"
    assert live_handshake_refusal({}, [], base) == "host not allowed"
    s2 = dataclasses.replace(base, live_origins=("http://127.0.0.1:8781",), live_hosts=("unit-laptop.local",))
    assert live_handshake_refusal(dict(ok_host, origin="http://127.0.0.1:8781"), [], s2) is None
    assert live_handshake_refusal(dict(ok_host, origin="http://127.0.0.1:8781/"), [], s2) == "origin not allowed"
    assert live_handshake_refusal({"host": "unit-laptop.local:8765"}, [], s2) is None
    tok = "T" * 22
    s3 = dataclasses.replace(base, live_token=tok)
    assert live_handshake_refusal(ok_host, [], s3) == "token missing or wrong"
    assert live_handshake_refusal(ok_host, ["wfg-live.v1", "wfg-token." + "U" * 22], s3) == "token missing or wrong"
    assert live_handshake_refusal(ok_host, ["wfg-live.v1", "wfg-token." + tok], s3) is None


def test_derived_graph_drops_closed_edges_and_their_turns(tmp_path):
    from api.live import DerivedGraphs, derive_graph
    g = json.loads(_tiny_graph(tmp_path).read_text())
    d, dropped = derive_graph(g, {"ab:f", "ab:r"})
    assert [e["id"] for e in d["edges"]] == ["bc:f", "bc:r", "cd:f"] and dropped == 1
    assert d["forbidden_turns"] == [["bc:f", "cd:f"]] and d["revision"] == g["revision"] and d["nodes"] == g["nodes"]
    assert len(g["edges"]) == 5                                   # the input is not modified
    out = tmp_path / "job" / "inputs" / "graph.json"
    sha, n = DerivedGraphs().write(tmp_path / "graph.json", "base", ("ab:f", "ab:r"), out)
    import hashlib
    assert n == 1 and hashlib.sha256(out.read_bytes()).hexdigest() == sha
    assert {e["id"] for e in json.loads(out.read_text())["edges"]} == {"bc:f", "bc:r", "cd:f"}


def _event(**kw):
    ev = {"event": "CLOSED", "region": REGION, "lat": 36.6, "lon": 126.6, "utc": "2026-11-17T03:00:00Z",
          "unit_id": "VU-01", "session_id": "S1", "verdict_id": "v1"}
    ev.update(kw)
    return ev


def test_parse_event_is_strict():
    from api.live import LiveEventError, parse_event
    ok = parse_event(json.dumps(_event(utc="2026-11-17T12:00:00+09:00")))
    assert ok["utc"] == "2026-11-17T03:00:00.000000Z" and ok["event"] == "CLOSED"
    bad = [_event(event="CROSS_FAST"), _event(event="CROSS FAST"), _event(event="SPRAY THEN RE-CHECK"), _event(event=None),
           _event(lat=True), _event(lat="36.6"), _event(lat=91.0), _event(utc="2026-11-17T03:00:00"), _event(utc="yesterday"),
           _event(unit_id=""), _event(unit_id="a b"), _event(region="../x"), dict(_event(), extra=1)]
    missing = _event(); missing.pop("verdict_id"); bad.append(missing)
    for b in bad:
        with pytest.raises(LiveEventError):
            parse_event(json.dumps(b))
    for raw in ('{"event":"CLOSED","lat":NaN}', "[1]", "not json", b"{}", "x" * 5000):
        with pytest.raises(LiveEventError):
            parse_event(raw)
    # optional fields (backward compatible): ahead on CLOSED, claim_token / closes_verdict_id on REOPENED; nowhere else
    tok = "A" * 22
    ok = parse_event(json.dumps(_event(ahead=[{"lat": 36.61, "lon": 126.6}])))
    assert ok["ahead"] == [{"lat": 36.61, "lon": 126.6}]
    ok = parse_event(json.dumps(_event(event="REOPENED", claim_token=tok, closes_verdict_id="v0")))
    assert ok["claim_token"] == tok and ok["closes_verdict_id"] == "v0"
    for b in (_event(claim_token=tok), _event(event="REOPENED", ahead=[]), _event(event="REOPENED", claim_token="short"),
              _event(event="REOPENED", claim_token=tok + " "), _event(ahead=[{"lat": 36.6}]),
              _event(ahead=[{"lat": 36.6, "lon": 126.6, "x": 1}]), _event(ahead=[{"lat": 99.0, "lon": 126.6}]),
              _event(ahead=[{"lat": 36.6, "lon": 126.6}] * 5), _event(ahead={"lat": 36.6, "lon": 126.6})):
        with pytest.raises(LiveEventError):
            parse_event(json.dumps(b))
    from api.live import ids_of
    assert ids_of(json.dumps(_event(lat="x", verdict_id="vv"))) == {"event": "CLOSED", "verdict_id": "vv"}
    assert ids_of("not json") == {} and ids_of(None) == {}
    with pytest.raises(LiveEventError) as e:
        parse_event(json.dumps(_event(event="CROSS_FAST")))
    assert e.value.code == "UNKNOWN_EVENT"


def test_flag_is_read_from_env_and_defaults_off():
    from api.config import Settings, live_closures_enabled
    assert not live_closures_enabled({}) and not live_closures_enabled({"WFG_API_LIVE_CLOSURES": "true"})
    assert live_closures_enabled({"WFG_API_LIVE_CLOSURES": "1"})
    s = Settings(data_root=Path("/x"), runtime_dir=Path("/y"), workers=1, python="python", host="127.0.0.1", port=8765)
    assert s.live_closures is False


def test_flag_off_has_no_live_socket(empty_client):
    from starlette.websockets import WebSocketDisconnect
    assert not any(getattr(r, "path", "") == "/v1/live/closures" for r in empty_client.app.routes)
    with pytest.raises(WebSocketDisconnect):
        with empty_client.websocket_connect("/v1/live/closures") as ws:
            ws.send_text(json.dumps(_event()))
            ws.receive_json()




def test_env_flag_registers_the_socket(monkeypatch):
    from api.app import create_app
    monkeypatch.setenv("WFG_API_LIVE_CLOSURES", "1")
    assert any(getattr(r, "path", "") == "/v1/live/closures" for r in create_app().routes)
    monkeypatch.setenv("WFG_API_LIVE_CLOSURES", "0")
    assert not any(getattr(r, "path", "") == "/v1/live/closures" for r in create_app().routes)


# ------------------------------------------------------------------------------------------------ socket, no data
TOKEN = "unit-test-token-0123456789"


@pytest.fixture()
def live_empty(tmp_path):
    """Live socket on an empty data root (every event is DATA_UNAVAILABLE) with a shared token configured."""
    from fastapi.testclient import TestClient
    from api.app import create_app
    s = dataclasses.replace(_settings(tmp_path / "nodata", tmp_path / "rt"), workers=1, live_closures=True,
                            live_token=TOKEN, live_hosts=("testserver",))
    with TestClient(create_app(s)) as c:
        yield c


def test_socket_refuses_bad_origin_host_or_token(live_empty):
    """R9-07: refused before accept (no frame is ever applied): any browser Origin not listed, no token, a wrong token.
    With the token offered as a subprotocol the socket accepts and answers wfg-live.v1 (never the token)."""
    from starlette.websockets import WebSocketDisconnect
    c = live_empty
    good = ["wfg-live.v1", "wfg-token." + TOKEN]
    for kw in ({"subprotocols": good, "headers": {"origin": "https://evil.example"}},
               {"subprotocols": good, "headers": {"origin": "null"}},
               {}, {"subprotocols": ["wfg-live.v1", "wfg-token.wrong-token-0000000000"]}):
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/v1/live/closures", **kw) as ws:
                ws.send_text(json.dumps(_event()))
                ws.receive_json()
    with c.websocket_connect("/v1/live/closures", subprotocols=good) as ws:
        assert ws.accepted_subprotocol == "wfg-live.v1"
        a = _send(ws, verdict_id="vx")
        assert a["ok"] is False and a["code"] == "DATA_UNAVAILABLE" and a["verdict_id"] == "vx" and a["event"] == "CLOSED"
        ws.send_text(json.dumps(_event(lat="bad", verdict_id="vy")))
        a = ws.receive_json()
        assert a["code"] == "VALIDATION_ERROR" and a["verdict_id"] == "vy"       # error acks carry the id when parseable


def test_socket_rate_limit(live_empty, monkeypatch):
    """R9-07: frames beyond the per-connection bucket get RATE_LIMITED and are not applied."""
    import api.live as LV
    monkeypatch.setattr(LV, "RATE_BURST", 3.0)
    monkeypatch.setattr(LV, "RATE_PER_S", 0.001)
    with live_empty.websocket_connect("/v1/live/closures", subprotocols=["wfg-token." + TOKEN]) as ws:
        codes = [_send(ws, verdict_id="r%d" % k)["code"] for k in range(5)]
    assert codes == ["DATA_UNAVAILABLE"] * 3 + ["RATE_LIMITED"] * 2


# ------------------------------------------------------------------------------------------------ recorded graph
class SyntheticScheduler:
    """Replaces JobManager.schedule: records each spec and answers with a SYNTHETIC result (no kit launch).
    A route check starting at ``uses_node`` reports a checked route over ``uses_edges``; every other one a checked route
    over an unrelated edge id. ``hold = True`` keeps the answers until ``release()`` (a recompute in flight);
    ``raise_next`` makes the next schedule() call raise."""

    def __init__(self):
        self.specs = []
        self.uses_node, self.uses_edges = None, []
        self.hold, self.held, self.raise_next = False, [], None

    def release(self):
        held, self.held = self.held, []
        for f in held:
            f()

    def __call__(self, kind, spec, on_start, on_done, priority=0):
        if self.raise_next is not None:
            e, self.raise_next = self.raise_next, None
            raise e
        self.specs.append((kind, spec))
        if kind != "route_check":
            on_done({"status": "failed", "error": {"code": "SYNTHETIC", "message": "not simulated"}}, None)
            return
        rp = spec["request_params"]
        edges = list(self.uses_edges) if rp["start_node"] == self.uses_node else ["synthetic:other"]
        res = {"verdict": "checked_route", "reason_code": "CHECKED", "raw_status": "SYNTHETIC", "raw_reason": None,
               "departure_s": rp["depart_offset_s"], "arrival_s": rp["depart_offset_s"] + 600, "lower_bound_L_s": None,
               "dwell_end_s": None, "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": []},
                                              "properties": {"edge_ids": edges}},
               "exposure": [], "compute_s": 0.0, "within_budget": True, "policy": spec["policy"], "limits": rp["limits"],
               "independent_check": None, "assumptions": None, "notes": ["SYNTHETIC test result"]}

        def answer():
            on_start()
            on_done({"status": "done", "result": res, "input_hashes": {"graph": "synthetic"}}, None)
        if self.hold:
            self.held.append(answer)
        else:
            answer()


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    from fastapi.testclient import TestClient
    from api.app import create_app
    s = dataclasses.replace(_settings(DATA, tmp_path_factory.mktemp("api_runtime_live")), workers=1, live_closures=True,
                            live_hosts=("testserver",))
    with TestClient(create_app(s)) as c:
        st = c.app.state.wfg
        sched = SyntheticScheduler()
        st.jobs.schedule = sched
        yield c, st, sched


def _pick_edge(st, skip=()):
    """First edge named in a forbidden turn whose chord midpoint matches back to it, with both end nodes allowed."""
    g = st.registry.region(REGION).graph
    raw = json.loads(Path(g.path).read_text())
    named = [e for pair in raw.get("forbidden_turns") or [] for e in pair]
    for eid in named + list(g.edge_ids):
        if eid in skip:
            continue
        u, v, _ = g.edges[eid]
        ku, kv = g.node_index[u], g.node_index[v]
        if not (g.allowed[ku] and g.allowed[kv]) or g.reverse_edges.get(eid) is None:
            continue
        mx, my = (g.xy[ku] + g.xy[kv]) / 2.0
        lon, lat = _lonlat(mx, my)
        m = g.nearest_edge(lon, lat)
        if set(m["edge_ids"]) == {eid, g.reverse_edges[eid]} and m["distance_m"] < 1.0:
            return eid, g.reverse_edges[eid], u, lon, lat, raw
    raise AssertionError("no usable edge")


def _send(ws, **kw):
    ws.send_text(json.dumps(_event(**kw)))
    return ws.receive_json()


def _frames(ws, n):
    return [ws.receive_json() for _ in range(n)]


@needs_data
def test_live_closures_end_to_end(live):
    c, st, sched = live
    eid, rev, u, lon, lat, raw = _pick_edge(st)
    sid = scenario_set_for(c, REGION, "20230402T070000Z")
    with c.websocket_connect("/v1/live/closures") as ws:
        # CROSS FAST is never road state
        a = _send(ws, event="CROSS_FAST", lat=lat, lon=lon)
        assert a["ok"] is False and a["code"] == "UNKNOWN_EVENT" and st.live.closed_edges(REGION) == ()
        # far point (> 300 m from every edge chord) is rejected
        a = _send(ws, lat=37.0, lon=127.0)
        assert a["ok"] is False and a["code"] == "SNAP_TOO_FAR" and st.live.closed_edges(REGION) == ()
        a = _send(ws, region="nowhere_2099", lat=lat, lon=lon)
        assert a["ok"] is False and a["code"] == "UNKNOWN_REGION"
        ws.send_bytes(b"{}")
        assert ws.receive_json()["ok"] is False

        # CLOSED at the edge midpoint closes the edge, its reverse and the widened match; no plan yet
        a = _send(ws, lat=lat, lon=lon, verdict_id="c1")
        closed = set(a["edge_ids"])
        tok1 = a["claim_token"]
        assert a["ok"] is True and {eid, rev} <= closed and a["distance_m"] < 1.0 and a["duplicate"] is False
        assert a["edge_ids"] == a["matched_edge_ids"] and a["placeholder_limits"] is True
        assert a["recompute"]["status"] == "no_previous_plan" and set(st.live.closed_edges(REGION)) == closed
        # FS-6 (API side): a repeated CLOSED (unit resend after a reconnect) is idempotent: same token, no new claim
        a = _send(ws, lat=lat, lon=lon, verdict_id="c1")
        assert a["ok"] is True and a["duplicate"] is True and a["claim_token"] == tok1
        assert len(st.live.records_of(REGION, ("VU-01", "S1"))) == 1

        # a new route check runs on a derived graph in its inputs dir, same revision, without the closed edges/turns
        body = {"region": REGION, "input_time": INPUT_TIME, "start": {"node_id": u}, "destination": {"node_id": DEST_NODE},
                "fire_input": {"type": "recorded", "scenario_set_id": sid}}
        r = c.post("/v1/route-checks", json=body)
        assert r.status_code == 202, r.text
        jid = r.json()["job_id"]
        kind, spec = sched.specs[-1]
        gp = Path(spec["graph_path"])
        assert kind == "route_check" and gp == st.jobs.job_dir(jid) / "inputs" / "graph.json"
        derived = json.loads(gp.read_text())
        ids = {e["id"] for e in derived["edges"]}
        assert not (ids & closed) and len(ids) == len(raw["edges"]) - len(closed)
        assert derived["revision"] == raw["revision"] and derived["nodes"] == raw["nodes"]
        assert not any(eid in p or rev in p for p in derived["forbidden_turns"])
        assert len(derived["forbidden_turns"]) < len(raw["forbidden_turns"])
        j = c.get("/v1/route-checks/" + jid).json()
        assert set(j["provenance"]["live_closures"]["closed_edge_ids"]) == closed
        assert j["provenance"]["input_hashes"]["graph"] == j["provenance"]["live_closures"]["derived_graph_sha256"]
        assert set(j["result"]["provenance"]["live_closures"]["closed_edge_ids"]) == closed
        # R9-10: a run on a derived graph is never the evaluated configuration
        assert j["provenance"]["evaluated_configuration"] is False
        assert j["result"]["provenance"]["evaluated_configuration"] is False

        # REOPENED from another unit does not reopen and never names who holds the road
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, unit_id="VU-02", verdict_id="o1")
        assert a["ok"] is False and a["code"] == "CLOSED_BY_OTHER_UNIT" and set(st.live.closed_edges(REGION)) == closed
        assert "VU-01" not in json.dumps(a) and "S1" not in json.dumps(a) and set(a["holder_count"]) <= closed
        # R9-03: the closing unit's ids without its token (forged), or with a wrong token, reopen nothing
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="forged")
        assert a["ok"] is False and a["code"] == "REOPEN_UNAUTHORIZED" and set(st.live.closed_edges(REGION)) == closed
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="forged", claim_token="W" * 22)
        assert a["ok"] is False and a["code"] == "REOPEN_UNAUTHORIZED" and set(st.live.closed_edges(REGION)) == closed
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r0", claim_token=tok1, closes_verdict_id="other")
        assert a["ok"] is False and a["code"] == "NOT_CLOSED" and set(st.live.closed_edges(REGION)) == closed

        # R9-02: a REOPENED of this unit on a different road 50-250 m away never reopens the closure (fail closed)
        g = st.registry.region(REGION).graph
        x, y = (g.xy[g.node_index[g.edges[eid][0]]] + g.xy[g.node_index[g.edges[eid][1]]]) / 2.0
        alt = None
        for e2 in g.edge_ids:
            ku, kv = g.node_index[g.edges[e2][0]], g.node_index[g.edges[e2][1]]
            mx, my = (g.xy[ku] + g.xy[kv]) / 2.0
            if 60.0 < float(np.hypot(mx - x, my - y)) < 250.0:
                m2 = g.nearest_edge(*_lonlat(mx, my))
                if not (set(m2["edge_ids"]) & closed):
                    alt = _lonlat(mx, my)
                    break
        assert alt is not None, "no neighbouring edge within 250 m in the recorded graph"
        a = _send(ws, event="REOPENED", lon=alt[0], lat=alt[1], verdict_id="r6", unit_id="VU-02")
        assert a["ok"] is False and a["code"] == "NOT_CLOSED"            # other unit: nothing of its own here
        a = _send(ws, event="REOPENED", lon=alt[0], lat=alt[1], verdict_id="r6", claim_token=tok1)
        assert a["ok"] is False and a["code"] == "REOPEN_TOO_FAR" and set(st.live.closed_edges(REGION)) == closed

        # linkage path: the closing unit with its token at the closed road reopens exactly that closure
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r1", claim_token=tok1, closes_verdict_id="c1")
        assert a["ok"] is True and set(a["edge_ids"]) == closed and a["reopened_verdict_id"] == "c1"
        assert st.live.closed_edges(REGION) == ()
        # a replay of the same REOPENED (e.g. resent after an API restart) is harmless
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r2", claim_token=tok1)
        assert a["ok"] is False and a["code"] == "NOT_CLOSED"
        r = c.post("/v1/route-checks", json=body)
        assert sched.specs[-1][1]["graph_path"] == str(st.registry.region(REGION).graph_path)
        assert "live_closures" not in r.json()["provenance"]

        # a dispatch plan (synthetic results): O1 starts at u and its route uses the edge, O2's does not
        o2 = next(n for k, n in enumerate(g.node_ids) if g.allowed[k] and n not in (u, DEST_NODE))
        sched.uses_node, sched.uses_edges = u, [eid]
        plan = {"region": REGION, "input_time": INPUT_TIME, "fire_input": {"type": "recorded", "scenario_set_id": sid},
                "origins": [{"id": "O1", "location": {"node_id": u}}, {"id": "O2", "location": {"node_id": o2}}],
                "destinations": [{"id": "D1", "location": {"node_id": DEST_NODE}}], "depart_offsets_s": [0, 60]}
        r = c.post("/v1/dispatch-plans", json=plan)
        assert r.status_code == 202 and "live_closures" not in r.json()["provenance"]
        assert c.get("/v1/dispatch-plans/" + r.json()["job_id"]).json()["status"] == "done"

        # CLOSED again: only O1 is rerun; the socket pushes the submission, then the finished summary
        a = _send(ws, lat=lat, lon=lon, verdict_id="c2")
        tok2 = a["claim_token"]
        assert a["ok"] is True and a["recompute"]["status"] == "submitted" and a["recompute"]["origins"] == ["O1"]
        sub, done = _frames(ws, 2)
        assert sub["type"] == "leave_by_update" and sub["status"] == "submitted" and sub["origins"] == ["O1"]
        assert sub["job_id"] == a["recompute"]["job_id"] and sub["state_version"] == a["state_version"]
        assert done["type"] == "leave_by_update" and done["status"] == "done" and done["summary"]["origins"] == 1
        assert [x["origin_id"] for x in done["leave_by"]] == ["O1"] and done["leave_by"][0]["leave_by_s"] == 60
        # R9-05: the frame says which road state the times were computed on, and whether that is still current
        assert set(done["closed_edge_ids"]) == closed and done["stale"] is False
        assert done["state_version"] == done["current_state_version"] == a["state_version"]
        dj = c.get("/v1/dispatch-plans/" + done["job_id"]).json()
        lc = dj["result"]["provenance"]["live_closures"]
        assert set(lc["closed_edge_ids"]) == closed and lc["recompute"]["event"] == "CLOSED"
        assert dj["result"]["provenance"]["evaluated_configuration"] is False
        rc_specs = [s for k, s in sched.specs[-2:] if k == "route_check"]
        assert all(Path(s["graph_path"]).parent.parent == st.jobs.job_dir(done["job_id"]) for s in rc_specs)

        # REOPENED: every origin of the last POSTed plan is rerun on the full graph again
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r3", claim_token=tok2)
        assert a["ok"] is True and a["recompute"]["origins"] == ["O1", "O2"]
        sub, done = _frames(ws, 2)
        assert sub["status"] == "submitted" and done["status"] == "done" and done["summary"]["origins"] == 2
        assert done["closed_edge_ids"] == [] and done["stale"] is False
        assert c.get("/v1/dispatch-plans/" + done["job_id"]).json()["provenance"]["live_closures"]["closed_edge_ids"] == []

        # closing again: O1's last plan (the REOPENED rerun) used the edge, so O1 is rerun
        sched.uses_node = None
        a = _send(ws, lat=lat, lon=lon, verdict_id="c3")
        tok3 = a["claim_token"]
        assert a["ok"] is True and a["recompute"]["origins"] == ["O1"]
        assert [f["status"] for f in _frames(ws, 2)] == ["submitted", "done"]
        # a second unit closing the same road changes nothing: no rerun
        a = _send(ws, lat=lat, lon=lon, verdict_id="c4", unit_id="VU-03")
        tok4 = a["claim_token"]
        assert a["ok"] is True and a["recompute"]["status"] == "not_needed" and tok4 != tok3
        # the first unit reopening leaves it closed by the second unit
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r4", claim_token=tok3)
        assert a["ok"] is True and a["edge_ids"] == [] and set(a["still_closed_by_other_units"]) == closed
        assert set(st.live.closed_edges(REGION)) == closed and a["recompute"]["status"] == "not_needed"
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r5", unit_id="VU-03", claim_token=tok4)
        assert a["ok"] is True and set(a["edge_ids"]) == closed and a["recompute"]["origins"] == ["O1", "O2"]
        assert [f["status"] for f in _frames(ws, 2)] == ["submitted", "done"]
        # now no origin's last checked route uses the edge: closing it needs no rerun
        a = _send(ws, lat=lat, lon=lon, verdict_id="c5")
        assert a["ok"] is True and a["recompute"]["status"] == "not_needed" and "no origin" in a["recompute"]["reason"]
        # a CLOSED/CROSS FAST/CLOSED flicker at the same crossing: the second CLOSED supersedes the first, one REOPENED
        a2 = _send(ws, lat=lat, lon=lon, verdict_id="c6")
        assert a2["superseded_verdict_ids"] == ["c5"] and len(st.live.records_of(REGION, ("VU-01", "S1"))) == 1
        a = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="r7", claim_token=a2["claim_token"])
        assert a["ok"] is True and st.live.closed_edges(REGION) == ()
        assert [f["status"] for f in _frames(ws, 2)] == ["submitted", "done"]
        state = c.get("/v1/live/state", params={"region": REGION}).json()
        assert state["closed_edge_ids"] == [] and state["recompute"]["pending"] is False
        assert "claim_token" not in json.dumps(state) and "VU-01" not in json.dumps(state)


@needs_data
def test_reopen_on_an_adjacent_edge_and_with_the_flame_point(live):
    """R9-02 positive cases: a REOPENED a few metres into the next edge at the closed edge's end node (shares that node,
    within the PLACEHOLDER 50 m) reopens the closure; a CLOSED carrying an ``ahead`` flame point also closes the road at
    that point, and a REOPENED near the flame point (beyond 50 m of the vehicle point) still reopens it."""
    c, st, sched = live
    g = st.registry.region(REGION).graph

    def length(e):
        return float(np.hypot(*(g.xy[g.node_index[g.edges[e][0]]] - g.xy[g.node_index[g.edges[e][1]]])))

    def unit(e, k_from):
        a, b = g.node_index[g.edges[e][0]], g.node_index[g.edges[e][1]]
        k_to = b if a == k_from else a
        v = g.xy[k_to] - g.xy[k_from]
        return v / np.hypot(*v), k_to

    pick = None
    incident = {}
    for e in g.edge_ids:
        for n in g.edges[e][:2]:
            incident.setdefault(n, []).append(e)
    for eid in g.edge_ids:                       # a corner: two roads > 60 m long meeting at u at more than 45 degrees
        rev = g.reverse_edges.get(eid)
        if rev is None or length(eid) < 60.0:
            continue
        u = g.edges[eid][0]
        ku = g.node_index[u]
        d1, kv = unit(eid, ku)
        for other in incident.get(u, []):
            if other in (eid, rev) or length(other) < 60.0:
                continue
            d2, ko = unit(other, ku)
            if float(np.dot(d1, d2)) < 0.7:
                pick = (eid, rev, u, ku, kv, ko)
                break
        if pick:
            break
    assert pick is not None, "no corner of two long roads in the recorded graph"
    eid, rev, u, ku, kv, ko = pick
    mx, my = (g.xy[ku] + g.xy[kv]) / 2.0
    lon, lat = _lonlat(mx, my)

    def along(k_from, k_to, d):
        v = g.xy[k_to] - g.xy[k_from]
        return g.xy[k_from] + v / np.hypot(*v) * d

    p_closed = _lonlat(*along(ku, kv, 5.0))           # on eid, 5 m from u
    p_reopen = _lonlat(*along(ku, ko, 25.0))          # on the adjacent edge, 25 m from u
    with c.websocket_connect("/v1/live/closures") as ws:
        a = _send(ws, lon=p_closed[0], lat=p_closed[1], verdict_id="adj-c", unit_id="VU-09", session_id="S9")
        assert a["ok"] is True and eid in a["edge_ids"]
        r = _send(ws, event="REOPENED", lon=p_reopen[0], lat=p_reopen[1], verdict_id="adj-r", unit_id="VU-09",
                  session_id="S9", claim_token=a["claim_token"])
        assert r["ok"] is True and set(r["edge_ids"]) == set(a["edge_ids"]) and st.live.closed_edges(REGION) == ()
        _drain_frames(ws, r)

        # vehicle 120 m before the flame on the adjacent edge; the flame point is on eid's midpoint
        far = _lonlat(*along(ku, ko, 120.0))
        a = ws.send_text(json.dumps(_event(lon=far[0], lat=far[1], verdict_id="ah-c", unit_id="VU-09", session_id="S9",
                                           ahead=[{"lat": lat, "lon": lon}])))
        a = ws.receive_json()
        assert a["ok"] is True and {eid, rev} <= set(a["edge_ids"]) and a["ahead"][0]["ok"] is True
        _drain_frames(ws, a)
        r = _send(ws, event="REOPENED", lon=lon, lat=lat, verdict_id="ah-r", unit_id="VU-09", session_id="S9",
                  claim_token=a["claim_token"])
        assert r["ok"] is True and st.live.closed_edges(REGION) == ()
        _drain_frames(ws, r)


def _drain_frames(ws, ack):
    if (ack.get("recompute") or {}).get("status") == "submitted":
        assert [f["status"] for f in _frames(ws, 2)][0] == "submitted"


@needs_data
def test_failed_recompute_stays_pending_and_reruns(live):
    """R9-04: launches paused (or any exception) after a closure is applied: the ack is ok with recompute failed and
    pending; /v1/live/state says the leave-by times are stale; the next event (a resend of the same CLOSED) reruns it."""
    c, st, sched = live
    eid, rev, u, lon, lat, raw = _pick_edge(st)
    sid = scenario_set_for(c, REGION, "20230402T070000Z")
    sched.uses_node, sched.uses_edges = u, [eid]
    plan = {"region": REGION, "input_time": INPUT_TIME, "fire_input": {"type": "recorded", "scenario_set_id": sid},
            "origins": [{"id": "P1", "location": {"node_id": u}}],
            "destinations": [{"id": "D1", "location": {"node_id": DEST_NODE}}], "depart_offsets_s": [0, 60]}
    assert c.post("/v1/dispatch-plans", json=plan).status_code == 202
    with c.websocket_connect("/v1/live/closures") as ws:
        st.jobs.paused = "TEST: launches paused"
        try:
            a = _send(ws, lat=lat, lon=lon, verdict_id="p1", unit_id="VU-P")
        finally:
            st.jobs.paused = None
        assert a["ok"] is True and a["recompute"]["status"] == "failed" and a["recompute"]["pending"] is True
        assert a["recompute"]["error"]["code"] == "LAUNCHES_PAUSED" and eid in st.live.closed_edges(REGION)
        state = c.get("/v1/live/state", params={"region": REGION}).json()
        assert state["recompute"]["pending"] is True and eid in state["recompute"]["pending_edge_ids"]
        assert "stale" in state["recompute"]["note"] or "assume" in state["recompute"]["note"]
        # an exception that is not an APIError: still ok:true (the closure stands), never INTERNAL_ERROR "not applied"
        sched.raise_next = RuntimeError("synthetic scheduler fault")
        a = _send(ws, lat=lat, lon=lon, verdict_id="p1", unit_id="VU-P")
        assert a["ok"] is True and a["duplicate"] is True and a["recompute"]["status"] == "failed"
        assert a["recompute"]["error"]["code"] == "INTERNAL_ERROR" and a["recompute"]["pending"] is True
        # the unit's resend reruns the pending change although the road state did not change now
        a = _send(ws, lat=lat, lon=lon, verdict_id="p1", unit_id="VU-P")
        assert a["ok"] is True and a["recompute"]["status"] == "submitted" and a["recompute"]["origins"] == ["P1"]
        sub, done = _frames(ws, 2)
        assert done["status"] == "done" and eid in done["closed_edge_ids"]
        assert c.get("/v1/live/state", params={"region": REGION}).json()["recompute"]["pending"] is False
        r = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="p2", unit_id="VU-P", claim_token=a["claim_token"])
        assert r["ok"] is True
        _drain_frames(ws, r)


@needs_data
def test_recomputes_are_coalesced_per_region(live):
    """R9-07 (4): while one live recompute is in flight, further changes are not queued as more jobs; they stay pending
    and rerun once, with the latest state, after it finishes (the socket's poll picks them up)."""
    c, st, sched = live
    eid, rev, u, lon, lat, raw = _pick_edge(st)
    sid = scenario_set_for(c, REGION, "20230402T070000Z")
    sched.uses_node, sched.uses_edges = u, [eid]
    plan = {"region": REGION, "input_time": INPUT_TIME, "fire_input": {"type": "recorded", "scenario_set_id": sid},
            "origins": [{"id": "Q1", "location": {"node_id": u}}],
            "destinations": [{"id": "D1", "location": {"node_id": DEST_NODE}}], "depart_offsets_s": [0, 60]}
    assert c.post("/v1/dispatch-plans", json=plan).status_code == 202
    with c.websocket_connect("/v1/live/closures") as ws:
        sched.hold = True
        a = _send(ws, lat=lat, lon=lon, verdict_id="q1", unit_id="VU-Q")
        assert a["recompute"]["status"] == "submitted"
        first = a["recompute"]["job_id"]
        assert ws.receive_json()["status"] == "submitted"
        r = _send(ws, event="REOPENED", lat=lat, lon=lon, verdict_id="q2", unit_id="VU-Q", claim_token=a["claim_token"])
        assert r["ok"] is True and r["recompute"]["status"] == "coalesced" and r["recompute"]["job_id"] == first
        n_dp = len([1 for k, _ in sched.specs if k == "route_check"])
        sched.hold = False
        sched.release()                                     # the first job finishes (CLOSED snapshot)
        f = ws.receive_json()
        assert f["job_id"] == first and f["status"] == "done" and f["stale"] is True   # road reopened since
        f2 = ws.receive_json()                               # the coalesced rerun, submitted by the poll
        assert f2["status"] == "submitted" and f2["job_id"] != first
        f3 = ws.receive_json()
        assert f3["status"] == "done" and f3["closed_edge_ids"] == [] and f3["stale"] is False
        assert len([1 for k, _ in sched.specs if k == "route_check"]) > n_dp


@needs_data
def test_leave_by_frames_mark_superseded_origins(live):
    """R9-05: two recompute jobs finishing in reverse order. The older one (all origins, version 5) arrives last; its
    O1 entry is superseded by the newer O1-only job (version 6) and has a null leave_by_s; O2 keeps its time. A job whose
    road state cannot be determined is sent with null times and status unknown_state."""
    c, st, sched = live

    def job(jid, version, origins, closed):
        return {"job_id": jid, "status": "done", "request": {"region": REGION},
                "provenance": {"live_closures": {"closed_edge_ids": closed, "state_version": version}},
                "result": {"summary": {}, "plans": [{"origin_id": o, "best_verdict": "checked_route",
                                                     "latest_contiguous_checked_depart_offset_s": 600,
                                                     "latest_checked_depart_offset_s": 600, "best": None} for o in origins]}}
    reg = "test_r905"
    old = dict(job("dp-old", 5, ["O1", "O2"], []), request={"region": reg})
    new = dict(job("dp-new", 6, ["O1"], ["e1"]), request={"region": reg})
    st.live.note_origin_version(reg, ["O1", "O2"], 5)
    st.live.note_origin_version(reg, ["O1"], 6)
    f_new = st.live_leave_by(new)
    assert f_new["status"] == "done" and f_new["leave_by"][0]["leave_by_s"] == 600
    f_old = st.live_leave_by(old)
    o1, o2 = f_old["leave_by"]
    assert o1["leave_by_s"] is None and o1["superseded_by_version"] == 6 and o2["leave_by_s"] == 600
    assert f_old["status"] == "done" and f_old["state_version"] == 5
    f_only = st.live_leave_by(dict(job("dp-o1", 5, ["O1"], []), request={"region": reg}))
    assert f_only["status"] == "superseded" and f_only["leave_by"][0]["leave_by_s"] is None
    unknown = st.live_leave_by({"job_id": "dp-x", "status": "done", "request": {"region": reg}, "provenance": {},
                                "result": {"plans": [{"origin_id": "O1", "best_verdict": "checked_route",
                                                      "latest_contiguous_checked_depart_offset_s": 600}]}})
    assert unknown["status"] == "unknown_state" and unknown["leave_by"][0]["leave_by_s"] is None
