"""crossing.server: FastAPI endpoints and the State WebSocket via TestClient (no network port needed).

The data behind the live-replay test is SYNTHETIC (tests/test_pipeline.build_session)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from crossing import pipeline as pl
from crossing.config import load_config
from crossing.research_log import ResearchLog
from crossing.server import Runtime, create_app

from test_pipeline import TEST_VEHICLE, build_session, capture_at, items_of


def make_runtime(tmp_path, **kw):
    cfg = load_config(overrides={"paths": {"records_dir": str(tmp_path), "pairs_path": str(tmp_path / "p.jsonl"),
                                           "sim_pairs_path": str(tmp_path / "ps.jsonl")}})
    pipe = pl.Pipeline(cfg, "fire_engine", "DEFAULT", mode=kw.pop("mode", "idle"))
    return Runtime(pipe, **kw)


@pytest.fixture
def client(tmp_path):
    rt = make_runtime(tmp_path)
    with TestClient(create_app(rt, start_tasks=False)) as c:
        c.runtime = rt
        yield c


def test_health_and_state(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert h["ok"] and h["verdict_state"] == "CLOSED" and h["mode"] == "idle" and h["advisory"] is True
    assert set(h["health"]["sensors"]) >= {"thermal", "radar", "gnss"}
    s = client.get("/api/state").json()
    assert s["schema"] == pl.STATE_SCHEMA and s["verdict"]["state"] == "CLOSED"


def test_vehicles_and_fuels_lists(client):
    v = client.get("/api/vehicles").json()
    assert v["selected"] == "fire_engine" and "PLACEHOLDER" in v["placeholder_note"]
    assert {"fire_engine", "water_tanker", "pickup", "command_car", "evacuation_minibus", "custom"} <= set(v["vehicles"])
    f = client.get("/api/fuels").json()
    codes = {x["code"] for x in f["fuels"]}
    assert f["selected"] == "DEFAULT" and {"GR1", "C064_GRASS", "DEFAULT"} <= codes


def test_select_vehicle(client):
    r = client.post("/api/vehicle", json={"name": "pickup"})
    assert r.status_code == 200 and r.json()["vehicle"]["name"] == "pickup"
    assert client.runtime.pipeline.vehicle.name == "pickup"
    assert client.post("/api/vehicle", json={"name": "spaceship"}).status_code == 400
    r = client.post("/api/vehicle", json={"name": "custom", "custom": {"length_m": 6.0, "dose_limit_tdu": 300.0}})
    assert r.status_code == 200
    assert r.json()["vehicle"]["length_m"] == 6.0 and r.json()["vehicle"]["placeholder"] is True
    bad = client.post("/api/vehicle", json={"name": "custom", "custom": {"length_m": -1}})
    assert bad.status_code == 400
    assert client.get("/api/vehicles").json()["vehicles"]["custom"]["length_m"] == 6.0


def test_select_fuel(client):
    r = client.post("/api/fuel", json={"code": "GR2"})
    assert r.status_code == 200 and r.json()["fuel"]["code"] == "GR2"
    assert client.post("/api/fuel", json={"code": "NOPE"}).status_code == 400
    r = client.post("/api/fuel", json={"custom": {"code": "MYGRASS", "residence_s": 8.0,
                                                  "consumed_load_kg_m2": 0.4, "heat_kj_kg": 18000.0}})
    assert r.status_code == 200 and client.runtime.pipeline.fuel.code == "MYGRASS"
    assert client.post("/api/fuel", json={"custom": {"code": "GR1", "residence_s": 8.0,
                                                     "consumed_load_kg_m2": 0.4}}).status_code == 400
    assert client.post("/api/fuel", json={"custom": {"code": "X2", "residence_s": 8.0, "consumed_load_kg_m2": 0.4,
                                                     "evil": 1}}).status_code == 400


def test_baseline_and_mark_crossing_fail_closed_without_data(client):
    r = client.post("/api/baseline", json={"action": "capture"}).json()
    assert r["ok"] is False
    assert client.post("/api/baseline", json={"action": "clear"}).json()["ok"] is True
    assert client.post("/api/baseline", json={"action": "explode"}).status_code == 400
    r = client.post("/api/mark_crossing", json={}).json()
    assert r["ok"] is False
    assert client.post("/api/mark_crossing", json={"measured_m": "three"}).status_code == 400
    assert client.post("/api/mark_crossing", json={"lookback_s": 1}).status_code == 400


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_index_placeholder_when_web_missing(tmp_path):
    rt = make_runtime(tmp_path)
    with TestClient(create_app(rt, start_tasks=False, web_dir=tmp_path / "noweb")) as c:
        r = c.get("/")
        assert r.status_code == 200 and "Advisory only" in r.text


def test_ws_pushes_state(client):
    with client.websocket_connect("/ws") as ws:
        a = json.loads(ws.receive_text())
        b = json.loads(ws.receive_text())
    assert a["schema"] == pl.STATE_SCHEMA and b["verdict"]["state"] == "CLOSED"
    assert "LINK_DOWN" in " ".join(b["verdict"]["reasons"]) or b["verdict"]["reasons"]


def test_state_after_pipeline_activity_and_api_actions(tmp_path):
    """A pipeline fed with a synthetic session (virtual clock), then the API on top of it."""
    t_virtual = {"now": 0.0}
    rt = make_runtime(tmp_path, clock=lambda: t_virtual["now"])
    pipe = rt.pipeline
    pipe.set_vehicle(TEST_VEHICLE)
    hello, msgs = build_session("flame_front", duration=12.0)   # flame held >= 3 s by ~11 s (min evidence)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    t_virtual["now"] = 1000.0 + states[-1][0]
    with TestClient(create_app(rt, start_tasks=False)) as c:
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CROSS FAST" and s["sim"] is True
        assert s["flame"]["radar"]["baseline"]["present"] is True
        r = c.post("/api/mark_crossing", json={"measured_m": 2.0}).json()
        assert r["ok"] is True and r["sim"] is True
        assert c.post("/api/baseline", json={"action": "clear"}).json()["ok"]
        t_virtual["now"] += 5.01                               # no ticks for 5 s: the shown verdict expires
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CLOSED" and "VERDICT_EXPIRED" in s["verdict"]["reasons"]


def test_replay_mode_runs_tasks_in_real_time(tmp_path):
    """Start the server with a research-log replay at 20x speed and watch the State come alive, then stop."""
    root = tmp_path / "rec"
    cfg = load_config(overrides={"paths": {"records_dir": str(root), "sim_pairs_path": str(root / "ps.jsonl")}})
    log = ResearchLog(root, "CX-src")
    src = pl.Pipeline(cfg, TEST_VEHICLE, "DEFAULT", research_log=log)
    hello, msgs = build_session("smoke_only", duration=6.0)
    pl.run_virtual(src, items_of(hello, msgs))
    log.close(parquet=False)
    rt = make_runtime(tmp_path, replay_dir=str(log.dir), speed=20.0, mode="replay")
    with TestClient(create_app(rt, start_tasks=True)) as c:
        seen = []
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            s = c.get("/api/state").json()
            seen.append(s["unit"]["n_messages"])
            if s["unit"]["n_messages"] > 200 and s["sim"]:
                break
            time.sleep(0.05)
    assert max(seen) > 200
    assert s["sim"] is True and s["mode"] == "replay" and s["verdict"]["state"] == "CLOSED"


# --------------------------------------------------------------------------------------------- replay control
from crossing.server import REPLAY_SPEED_MAX, ReplayPlayer  # noqa: E402


def test_replay_route_absent_outside_replay(tmp_path):
    for kw, mode in (({}, "idle"), ({"pi_url": "ws://127.0.0.1:9/stream"}, "live")):
        rt = make_runtime(tmp_path, **kw)
        assert rt.replay is None
        with TestClient(create_app(rt, start_tasks=False)) as c:
            r = c.get("/api/replay")
            assert r.status_code == 404 and r.json()["mode"] == mode
            r = c.post("/api/replay", json={"action": "pause"})
            assert r.status_code == 404 and r.json()["mode"] == mode


def test_replay_player_clock_pause_and_speed(tmp_path):
    """Replay clock on a fake laptop clock: advances at `speed`, freezes while paused, re-anchors on a speed change.
    Pausing marks the pipeline link down ("replay paused"); playing restores the recorded link state."""
    now = {"t": 100.0}
    rt = make_runtime(tmp_path, replay_dir=str(tmp_path), speed=2.0, mode="replay", clock=lambda: now["t"])
    rp = rt.replay
    pipe = rt.pipeline
    pipe.set_connected(True, now["t"], "replay test")
    assert isinstance(rp, ReplayPlayer) and rp.t() == 0.0 and not rp.paused
    now["t"] += 1.5
    assert rp.t() == pytest.approx(3.0)
    rp.pause()
    assert rp.paused and pipe.link.connected is False
    assert "replay paused" in pipe.link.health(now["t"]).link_reason
    now["t"] += 10.0
    assert rp.t() == pytest.approx(3.0) and rp.status()["t"] == pytest.approx(3.0)
    rp.set_speed(4.0)                                     # while paused: the clock stays frozen
    assert rp.t() == pytest.approx(3.0)
    rp.play()
    assert not rp.paused and pipe.link.connected is True
    now["t"] += 0.5
    assert rp.t() == pytest.approx(5.0)
    rp.set_speed(1.0)                                     # while playing: re-anchored at the current replay time
    now["t"] += 1.0
    assert rp.t() == pytest.approx(6.0)
    for bad in (0, -1, 0.0, REPLAY_SPEED_MAX * 2, float("nan"), float("inf"), "2", True, None):
        with pytest.raises(ValueError):
            rp.set_speed(bad)
    assert rp.speed == 1.0
    # a session whose recorded link was down at the pause point stays down on play
    rp._link_up, rp._link_reason = False, "recorded link down"
    rp.pause()
    rp.play()
    assert pipe.link.connected is False
    with pytest.raises(ValueError):
        ReplayPlayer(pipe, str(tmp_path), speed=0.0)


def test_paused_replay_fails_closed(tmp_path):
    """A CROSS FAST State (SYNTHETIC session, virtual clock), then pause: the State shows CLOSED at once (LINK_DOWN,
    replay paused), stays CLOSED while paused, the undisturbed verdict would expire after 5 s anyway, and play does
    not bring a go verdict back without fresh readings."""
    t_virtual = {"now": 0.0}
    rt = make_runtime(tmp_path, replay_dir=str(tmp_path), mode="replay", clock=lambda: t_virtual["now"])
    pipe = rt.pipeline
    pipe.set_vehicle(TEST_VEHICLE)
    hello, msgs = build_session("flame_front", duration=12.0)   # flame held >= 3 s by ~11 s (min evidence)
    states = pl.run_virtual(pipe, items_of(hello, msgs), hooks=capture_at(4.5))
    t_virtual["now"] = 1000.0 + states[-1][0]
    with TestClient(create_app(rt, start_tasks=False)) as c:
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CROSS FAST" and s["sim"] is True and s["mode"] == "replay"
        r = c.post("/api/replay", json={"action": "pause"})
        assert r.status_code == 200 and r.json()["paused"] is True and r.json()["mode"] == "replay"
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CLOSED" and "LINK_DOWN" in s["verdict"]["reasons"]
        assert s["health"]["link_up"] is False and "replay paused" in s["health"]["link_reason"]
        for dt in (0.2, 1.0, 5.0, 30.0):                    # ticks while paused: CLOSED throughout
            pipe.tick(t_virtual["now"] + dt)
        t_virtual["now"] += 30.0
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CLOSED"
        assert c.get("/api/replay").json()["paused"] is True
        r = c.post("/api/replay", json={"action": "play"})
        assert r.status_code == 200 and r.json()["paused"] is False
        pipe.tick(t_virtual["now"] + 0.2)                   # link back, but no fresh readings: still CLOSED
        t_virtual["now"] += 0.2
        assert c.get("/api/state").json()["verdict"]["state"] == "CLOSED"
        r = c.post("/api/replay", json={"action": "speed", "speed": 2})
        assert r.status_code == 200 and r.json()["speed"] == 2.0
        for body in ({"action": "speed", "speed": 0}, {"action": "speed", "speed": "fast"},
                     {"action": "speed"}, {"action": "rewind"}, {}, {"action": "speed", "speed": 1e9}):
            assert c.post("/api/replay", json=body).status_code == 400, body
        assert c.post("/api/replay", json=[1, 2]).status_code == 400

    # without the handler's immediate tick and with no ticks at all, the last go verdict still expires after 5 s
    t_virtual["now"] = 0.0
    rt2 = make_runtime(tmp_path / "b", replay_dir=str(tmp_path), mode="replay", clock=lambda: t_virtual["now"])
    rt2.pipeline.set_vehicle(TEST_VEHICLE)
    states = pl.run_virtual(rt2.pipeline, items_of(hello, msgs), hooks=capture_at(4.5))
    t_virtual["now"] = 1000.0 + states[-1][0]
    assert rt2.snapshot()["verdict"]["state"] == "CROSS FAST"
    rt2.replay.pause()
    t_virtual["now"] += 5.01
    v = rt2.snapshot()["verdict"]
    assert v["state"] == "CLOSED" and "VERDICT_EXPIRED" in v["reasons"]


def test_replay_pause_play_speed_in_real_time(tmp_path):
    """Server with a research-log replay (SYNTHETIC smoke_only session) and its tasks running: pausing stops the
    feed and the link, play continues, speed 20 runs it to the end; the ended replay reports paused + ended."""
    root = tmp_path / "rec"
    cfg = load_config(overrides={"paths": {"records_dir": str(root), "sim_pairs_path": str(root / "ps.jsonl")}})
    log = ResearchLog(root, "CX-src")
    src = pl.Pipeline(cfg, TEST_VEHICLE, "DEFAULT", research_log=log)
    hello, msgs = build_session("smoke_only", duration=6.0)
    pl.run_virtual(src, items_of(hello, msgs))
    log.close(parquet=False)
    rt = make_runtime(tmp_path, replay_dir=str(log.dir), speed=1.0, mode="replay")

    def wait_for(pred, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if pred():
                return True
            time.sleep(0.02)
        return False

    with TestClient(create_app(rt, start_tasks=True)) as c:
        n = lambda: c.get("/api/state").json()["unit"]["n_messages"]  # noqa: E731
        assert wait_for(lambda: n() > 50, 5.0)
        st = c.get("/api/replay").json()
        assert st["paused"] is False and st["speed"] == 1.0 and st["sim"] is True and st["t_end"] is None
        r = c.post("/api/replay", json={"action": "pause"}).json()
        assert r["paused"] is True
        t_paused = r["t"]
        n0 = n()
        time.sleep(0.5)
        assert n() == n0                                    # nothing fed while paused
        s = c.get("/api/state").json()
        assert s["verdict"]["state"] == "CLOSED" and s["health"]["link_up"] is False
        assert c.get("/api/replay").json()["t"] == pytest.approx(t_paused)
        r = c.post("/api/replay", json={"action": "play"}).json()
        assert r["paused"] is False
        assert wait_for(lambda: n() > n0 + 20, 3.0)
        assert c.post("/api/replay", json={"action": "speed", "speed": 20}).json()["speed"] == 20.0
        assert wait_for(lambda: c.get("/api/replay").json()["ended"], 5.0)
        st = c.get("/api/replay").json()
        assert st["paused"] is True and st["t_end"] == pytest.approx(6.0, abs=0.5)
        assert wait_for(lambda: c.get("/api/state").json()["health"]["link_up"] is False, 1.0)   # next tick
        assert c.get("/api/state").json()["verdict"]["state"] == "CLOSED"
        r = c.post("/api/replay", json={"action": "play"}).json()                # starts the session again
        assert r["paused"] is False and r["ended"] is False and r["t"] < 1.0
        assert wait_for(lambda: c.get("/api/replay").json()["pass"] == 2, 2.0)
