"""End to end over real loopback sockets, in one process: roof-unit sim server -> crossing app -> State WebSocket.

Everything here is SIMULATED: the session is written by ``wfgvu.synth`` (illustrative toy physics) into a temporary
directory; nothing touches hardware. The chain under test is the one used in the field:

    wfgvu.server.UnitServer (sim drivers, ws://127.0.0.1:<ephemeral>/stream)
      -> crossing.link.LinkClient -> crossing.pipeline.Pipeline (5 Hz) -> FastAPI app under uvicorn
      -> WS /ws (State JSON) read by a test client, POST /api/baseline and /api/vehicle as an operator would.

Scenario (one ~15 s session at real time, speed 1, so the laptop's freshness rules see real spacing):
  synth ``flame_front``: no flame until 3.5 s (radar baseline window), then a line fire 14 m ahead; radar readings
  stop at 11.5 s (``--fail radar@11.5``); at 13.5 s the Pi server is cut abruptly (transport abort, no closing
  handshake, as on a power loss). (FLAME needs about 2 s of radar effect and CROSS FAST another 3 s of continuous
  FLAME, min_flame_evidence_s, so the first go verdict comes about 5-6 s after onset.)
Checks: every State says sim; FLAME and a go verdict (CROSS FAST with a TEST-ONLY vehicle whose dose limit is 1e6
TDU, not a real limit) appear before the fault; CLOSED within 2 s of the last radar reading and never a go verdict
after it; LINK_DOWN within 2 s of the cut. Skips cleanly when binding a loopback port is not permitted.
"""
import asyncio
import json
import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VU = ROOT.parents[1] / "hardware" / "vehicle-unit"
for p in (str(ROOT), str(VU)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _loopback_ok() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _loopback_ok(), reason="binding a loopback port is not permitted here")

ONSET_S = 3.5
FAIL_S = 11.5
CUT_S = 13.5
DURATION_S = 15.0
GO = {"CROSS FAST", "SPRAY THEN RE-CHECK", "REOPENED"}


def _session(tmp_path):
    from wfgvu import synth
    return synth.generate("flame_front", tmp_path / "session", seed=1, duration=DURATION_S, onset_s=ONSET_S,
                          overlays=[synth.parse_overlay("fail", "radar@%g" % FAIL_S)])


async def _run(sess_dir, records):
    import httpx
    import uvicorn
    from websockets.asyncio.client import connect

    from crossing.config import load_config
    from crossing.pipeline import Pipeline
    from crossing.server import Runtime, create_app
    from wfgvu import __main__ as vu_cli

    # --- roof unit (sim) on an ephemeral port
    vcfg = vu_cli.load_config()
    unit = vu_cli.build(vcfg, sim_dir=sess_dir, record=False, host="127.0.0.1", port=0)
    await unit.start()
    t_unit0 = time.monotonic()

    # --- crossing app on an ephemeral port
    cfg = load_config(None, {"paths": {"records_dir": str(records)}, "server": {"port": 0}})
    pipe = Pipeline(cfg, "fire_engine", None, mode="live", source="test")
    runtime = Runtime(pipe, pi_url="ws://127.0.0.1:%d/stream" % unit.port)
    app = create_app(runtime)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", lifespan="on"))
    server.install_signal_handlers = lambda: None          # older uvicorn
    serve_task = asyncio.ensure_future(server.serve())
    while not server.started:
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = "http://127.0.0.1:%d" % port

    states = []           # (t since unit start, verdict state, reasons, flame status, sim)
    radar_rx = []         # receipt times of radar readings on a second Pi client (fault time reference)
    stop = asyncio.Event()

    async def watch_state():
        async with connect("ws://127.0.0.1:%d/ws" % port, max_size=2 ** 24) as ws:
            while not stop.is_set():
                st = json.loads(await ws.recv())
                v = st["verdict"]
                states.append((time.monotonic() - t_unit0, v["state"], list(v.get("reasons") or []),
                               st.get("flame", {}).get("status"), st.get("sim")))

    async def watch_pi():
        try:
            async with connect("ws://127.0.0.1:%d/stream" % unit.port, max_size=2 ** 22) as ws:
                async for text in ws:
                    m = json.loads(text)
                    if m.get("type") == "reading" and m.get("sensor") == "radar":
                        radar_rx.append(time.monotonic() - t_unit0)
        except Exception:  # noqa: BLE001 - the cut ends this client
            pass

    tasks = [asyncio.ensure_future(watch_state()), asyncio.ensure_future(watch_pi())]
    out = {}
    async with httpx.AsyncClient(timeout=5.0) as http:
        r = await http.post(base + "/api/vehicle", json={"name": "custom", "custom": {
            "dose_limit_tdu": 1.0e6, "max_safe_speed_m_s": 10.0}})       # TEST-ONLY limits, not real ones
        assert r.status_code == 200, r.text
        res = {"ok": False}
        while not res.get("ok") and time.monotonic() - t_unit0 < ONSET_S - 0.3:
            await asyncio.sleep(0.25)
            res = (await http.post(base + "/api/baseline", json={"action": "capture"})).json()
        out["baseline"] = res
        while time.monotonic() - t_unit0 < CUT_S:
            await asyncio.sleep(0.05)
        # abrupt cut: drop every TCP connection without a closing handshake, then stop the unit quietly
        for conn in list(unit._ws.connections):
            conn.transport.abort()
        out["t_cut"] = time.monotonic() - t_unit0
        for d in unit.drivers:
            d.emit = lambda msg: None
        await asyncio.sleep(2.6)
    stop.set()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await unit.stop()
    server.should_exit = True
    await asyncio.wait_for(serve_task, 10.0)
    out.update(states=states, radar_rx=radar_rx, research_log=str(pipe.rlog.dir) if pipe.rlog else None)
    return out


def test_sim_unit_to_crossing_app_over_sockets(tmp_path):
    sess = _session(tmp_path)
    out = asyncio.run(_run(sess, tmp_path / "records"))
    states, radar_rx = out["states"], out["radar_rx"]
    assert out["baseline"].get("ok"), out["baseline"]
    assert len(states) > 40
    assert all(s[4] is True for s in states if s[0] > 1.0)          # SIMULATED end to end

    # before the fault: flame confirmed (radar AND thermal) and a go verdict reached the State socket
    t_fault = radar_rx[-1]
    assert FAIL_S - 0.5 < t_fault < FAIL_S + 0.5
    pre = [s for s in states if ONSET_S < s[0] < t_fault]
    assert any(s[3] == "FLAME" for s in pre), [(round(s[0], 1), s[1], s[3]) for s in pre]
    assert any(s[1] == "CROSS FAST" for s in pre), [(round(s[0], 1), s[1], s[2][:2]) for s in pre]
    assert not any(s[1] in GO for s in states if s[0] < ONSET_S)     # nothing go before the flame exists
    first_flame = min(s[0] for s in pre if s[3] == "FLAME")
    assert min(s[0] for s in pre if s[1] == "CROSS FAST") - first_flame >= 3.0 - 0.25   # D4 (State push jitter)

    # radar stops: CLOSED within 2 s, never go again
    closed = [s for s in states if s[0] > t_fault and s[1] == "CLOSED"]
    assert closed and closed[0][0] - t_fault <= 2.0, closed[:1]
    assert not any(s[1] in GO for s in states if s[0] >= closed[0][0])
    assert any("radar" in r.lower() for r in closed[0][2]), closed[0][2]

    # link cut: LINK_DOWN within 2 s
    down = [s for s in states if s[0] > out["t_cut"] and "LINK_DOWN" in s[2]]
    assert down and down[0][0] - out["t_cut"] <= 2.0
    assert all(s[1] == "CLOSED" for s in states if s[0] > out["t_cut"])
    first_go = min(s[0] for s in pre if s[1] == "CROSS FAST")
    print("E2E (SIMULATED) first CROSS FAST %.2f s; radar last reading %.2f s -> CLOSED +%.2f s %s; cut %.2f s -> "
          "LINK_DOWN +%.2f s" % (first_go, t_fault, closed[0][0] - t_fault, closed[0][2][:2], out["t_cut"],
                                 down[0][0] - out["t_cut"]))
