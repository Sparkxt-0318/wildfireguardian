"""WebSocket server in-process on an ephemeral loopback port: sim mode end to end, live no_device, slow clients.

The session replayed here is synthetic test data written by this file.
"""
import asyncio
import gzip
import time

import numpy as np
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from wfgvu import __main__ as cli
from wfgvu import protocol, recorder
from wfgvu.drivers import base
from wfgvu.server import ClientQueue, UnitServer

SCTX = protocol.Context("VU-01", "VU-01-SYNTH", sim=True)


def _loopback_bind_allowed() -> bool:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
        return True
    except OSError:
        return False


# Tests that open a real loopback socket skip (not fail) where the environment forbids binding (e.g. a sandbox).
needs_loopback = pytest.mark.skipif(not _loopback_bind_allowed(), reason="binding a loopback port is not permitted")


def make_session(path, dur=4.0):
    """tc_plate 10 Hz and imu 20 Hz for ``dur`` s; tc_housing stops after 0.5 s; thermal 10 Hz (small frames)."""
    rng = np.random.default_rng(7)
    msgs = []
    t0 = 500.0
    for i in range(int(dur * 10)):
        t = t0 + 0.1 * i
        msgs.append(SCTX.make("reading", sensor="tc_plate", seq=i, t_mono=t,
                              data={"temp_c": 20.0 + 0.01 * i, "cj_c": 21.0, "fault": None}))
        msgs.append(SCTX.make("reading", sensor="thermal", seq=i, t_mono=t + 0.01,
                              data=protocol.encode_thermal(290 + 5 * rng.random((12, 16)))))
        if t - t0 < 0.5:
            msgs.append(SCTX.make("reading", sensor="tc_housing", seq=i, t_mono=t + 0.02,
                                  data={"temp_c": 30.0, "cj_c": 21.0, "fault": None}))
    for i in range(int(dur * 20)):
        msgs.append(SCTX.make("reading", sensor="imu", seq=i, t_mono=t0 + 0.05 * i,
                              data={"roll_deg": 0.0, "pitch_deg": 0.5, "heading_deg": 0.0, "grav": [0, 0, 9.81],
                                    "calib": {"sys": 3, "gyro": 3, "accel": 3, "mag": 3}}))
    msgs.sort(key=lambda m: m["t_mono"])
    return recorder.write_session(path, {"unit_id": "VU-01", "session_id": "VU-01-SYNTH"}, msgs)


async def collect(url, seconds, on_msg=None):
    out = []
    async with connect(url) as ws:
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            try:
                text = await asyncio.wait_for(ws.recv(), timeout=max(0.01, t_end - time.monotonic()))
            except asyncio.TimeoutError:
                break
            m = protocol.parse(text)
            out.append((time.monotonic(), m))
            if on_msg is not None:
                await on_msg(m)
    return out


@needs_loopback
def test_sim_server_end_to_end(tmp_path):
    sess = make_session(tmp_path / "session")
    cfg = cli.load_config()
    server = cli.build(cfg, sim_dir=sess, speed=1.0, record=True, host="127.0.0.1", port=0,
                       records_dir=tmp_path / "records")
    stop_report = {}

    async def scenario():
        await server.start()
        try:
            url = "ws://127.0.0.1:%d/stream" % server.port

            async def stop_tc_plate_later():
                await asyncio.sleep(2.0)
                drv = [d for d in server.drivers if d.name == "tc_plate"][0]
                stop_report["t"] = time.monotonic()
                await asyncio.to_thread(drv.stop)

            stopper = asyncio.ensure_future(stop_tc_plate_later())
            msgs = await collect(url, 3.3)
            await stopper
            return msgs
        finally:
            await server.stop()

    msgs = asyncio.run(scenario())
    first = msgs[0][1]
    assert first["type"] == "hello" and first["sim"] is True
    assert set(first["sensors"]) == {"thermal", "tc_plate", "tc_housing", "imu"}
    assert first["config_digest"] == protocol.config_digest(cfg) and first["thermal_wire_hz"] == 4.0
    body = [m for _, m in msgs[1:]]
    assert all(m["sim"] is True and m["session_id"] == server.ctx.session_id for m in body)

    def readings(s):
        return [m for m in body if m["type"] == "reading" and m["sensor"] == s]

    def heartbeats(s):
        return [m for m in body if m["type"] == "heartbeat" and m["sensor"] == s]

    assert len(readings("tc_plate")) >= 15 and len(readings("imu")) >= 40
    assert any(h["status"] == "ok" for h in heartbeats("tc_plate"))
    assert any(h["status"] == "ok" for h in heartbeats("unit"))
    # heartbeats every 0.5 s per sensor
    t_imu = [h["t_mono"] for h in heartbeats("imu")]
    assert len(t_imu) >= 5 and max(np.diff(t_imu)) < 0.7
    # thermal: ~4 Hz on the wire, seq advances by the decimation step
    th = readings("thermal")
    span = th[-1]["t_mono"] - th[0]["t_mono"]
    assert 2.5 <= (len(th) - 1) / span <= 5.5
    assert all(b - a >= 2 for a, b in zip([m["seq"] for m in th], [m["seq"] for m in th][1:]))
    # tc_housing stopped delivering after 0.5 s of recorded time -> stale within 1.5 s of its last reading
    last_h = readings("tc_housing")[-1]["t_mono"]
    stale = [h for h in heartbeats("tc_housing") if h["status"] == "stale" and h["t_mono"] > last_h]
    assert stale and stale[0]["t_mono"] - last_h <= 1.5
    # tc_plate driver stopped mid-run -> no_device heartbeat received within 1.5 s
    nd = [(t, m) for t, m in msgs if m["type"] == "heartbeat" and m["sensor"] == "tc_plate"
          and m["status"] in ("no_device", "stale") and t >= stop_report["t"]]
    assert nd and nd[0][0] - stop_report["t"] <= 1.5
    assert any(e["kind"] == "client_connected" for e in body if e["type"] == "event")

    # the recorder kept every thermal frame, the wire only a quarter-ish of them
    rec_dir = tmp_path / "records" / server.ctx.session_id
    with gzip.open(rec_dir / "thermal.jsonl.gz", "rt") as fh:
        rec_th = [protocol.parse(ln) for ln in fh]
    rec_th = [m for m in rec_th if m["type"] == "reading"]
    assert len(rec_th) >= 2 * len(th)
    assert [m["seq"] for m in rec_th] == list(range(len(rec_th)))
    assert (rec_dir / "session.json").exists() and (rec_dir / "unit.jsonl.gz").exists()


class AbsentDriver(base.Driver):
    def open(self):
        raise base.DeviceUnavailable("no /dev/ttyACM0")


@needs_loopback
def test_live_missing_device_reports_no_device_and_wrong_path_closed(tmp_path):
    ctx = protocol.Context("VU-01", "VU-01-LIVE-TEST", sim=False)
    server = UnitServer(ctx, {"x": 1}, None, host="127.0.0.1", port=0)
    server.add_driver(AbsentDriver("gnss", {"retry_s": 0.3}, server.emit, ctx=ctx))

    async def scenario():
        await server.start()
        try:
            msgs = await collect("ws://127.0.0.1:%d/stream" % server.port, 1.2)
            closed = None
            async with connect("ws://127.0.0.1:%d/other" % server.port) as ws:
                try:
                    await asyncio.wait_for(ws.recv(), 2.0)
                except ConnectionClosed as exc:
                    closed = exc.rcvd.code if exc.rcvd else None
            return msgs, closed
        finally:
            await server.stop()

    msgs, closed = asyncio.run(scenario())
    assert closed == 1008
    hbs = [m for _, m in msgs if m["type"] == "heartbeat" and m["sensor"] == "gnss"]
    assert hbs and all(h["status"] == "no_device" for h in hbs) and "ttyACM0" in hbs[-1]["detail"]
    assert all(m["sim"] is False for _, m in msgs)
    assert not [m for _, m in msgs if m["type"] == "reading"]


def test_client_queue_drops_oldest():
    async def go():
        q = ClientQueue(maxsize=3)
        for i in range(10):
            q.put(str(i))
        assert q.dropped == 7 and len(q) == 3
        assert [await q.get() for _ in range(3)] == ["7", "8", "9"]
        task = asyncio.ensure_future(q.get())
        await asyncio.sleep(0.01)
        assert not task.done()
        q.put("x")
        assert await asyncio.wait_for(task, 1.0) == "x"

    asyncio.run(go())


def test_slow_client_does_not_block_emit_and_drops_are_reported(tmp_path):
    """A client that never drains: ``emit`` from a driver thread stays fast; the drop count reaches the client
    as an ``event`` and the recorder."""
    ctx = protocol.Context("VU-01", "VU-01-SLOW", sim=True)
    rec = recorder.Recorder(tmp_path, ctx.session_id, "VU-01", sim=True, free_mb_fn=lambda p: 1e6)
    server = UnitServer(ctx, {}, rec, host="127.0.0.1", port=0, client_queue_max=5)

    async def scenario():
        server._loop = asyncio.get_running_loop()
        stuck = ClientQueue(5, name="stuck")
        server.clients[id(stuck)] = stuck
        reporter = asyncio.ensure_future(server._drop_reporter())

        def burst():
            t = time.monotonic()
            for i in range(500):
                server.emit(ctx.make("reading", sensor="tc_air", seq=i,
                                     data={"temp_c": 1.0, "cj_c": 1.0, "fault": None}))
            return time.monotonic() - t

        dt = await asyncio.to_thread(burst)
        await asyncio.sleep(1.2)
        reporter.cancel()
        items = list(stuck.q)
        server._loop = None
        return dt, stuck, items

    dt, stuck, items = asyncio.run(scenario())
    rec.close()
    assert dt < 2.0
    assert stuck.dropped >= 495
    kinds = [protocol.parse(t).get("kind") for t in items]
    assert "dropped" in kinds
    with gzip.open(tmp_path / ctx.session_id / "events.jsonl.gz", "rt") as fh:
        assert any('"dropped"' in ln for ln in fh)
    with gzip.open(tmp_path / ctx.session_id / "tc_air.jsonl.gz", "rt") as fh:
        assert sum(1 for _ in fh) == 500                          # recorder got everything


@needs_loopback
def test_cli_sim_runs_and_exits(tmp_path):
    sess = make_session(tmp_path / "s2", dur=0.6)
    t = time.monotonic()
    rc = cli.main(["--sim", str(sess), "--speed", "4", "--host", "127.0.0.1", "--port", "0", "--exit-on-end",
                   "--duration", "8", "--records", str(tmp_path / "rec")])
    assert rc == 0 and time.monotonic() - t < 6.0
    assert not (tmp_path / "rec").exists()                         # sim mode does not record by default
    assert cli.main(["--sim", str(tmp_path / "missing"), "--port", "0"]) == 2


@pytest.mark.parametrize("name", list(protocol.SENSORS))
def test_live_build_constructs_every_driver(tmp_path, name):
    cfg = cli.load_config()
    server = cli.build(cfg, record=False, host="127.0.0.1", port=0, records_dir=tmp_path)
    assert [d.name for d in server.drivers] == list(protocol.SENSORS)
    d = [x for x in server.drivers if x.name == name][0]
    assert d.sim is False and d.ctx.sim is False


def test_thermal_wire_decimation_keeps_rate_under_jitter():
    """Schedule-based decimation: jittered 4 Hz input passes whole; 25 Hz input comes out at 4 Hz on average."""
    rng = np.random.default_rng(3)
    data = protocol.encode_thermal(np.full((4, 4), 300.0))

    def run(rate_hz, n):
        server = UnitServer(SCTX, {}, None, host="127.0.0.1", port=0, thermal_wire_hz=4.0)
        t = 1000.0 + np.arange(n) / rate_hz + rng.normal(0.0, 0.004, n)
        for i, ti in enumerate(t):
            server.emit(SCTX.make("reading", sensor="thermal", seq=i, t_mono=float(ti), data=data))
        return n - server.thermal_decimated, float(t[-1] - t[0])

    sent, span = run(4.0, 200)
    assert sent == 200                                   # the old rule dropped about 30 % of these
    sent, span = run(25.0, 1000)
    assert abs(sent / span - 4.0) < 0.1


@needs_loopback
def test_stop_returns_with_a_client_connected(tmp_path):
    """Regression: stop() used to hang in wait_closed() while a client handler waited on an empty queue."""
    sess = make_session(tmp_path / "s3", dur=3.0)
    from wfgvu import replay
    session = replay.load(sess)
    ctx = protocol.Context("VU-01", "VU-01-STOP", sim=True)
    server = UnitServer(ctx, {}, None, host="127.0.0.1", port=0, session=session)
    for name, stream in session.streams.items():
        server.add_driver(cli.DRIVER_CLASSES[name](name, {}, server.emit, stream, ctx=ctx))

    async def scenario():
        await server.start()
        got = []
        closed = asyncio.Event()

        async def client():
            try:
                async with connect("ws://127.0.0.1:%d/stream" % server.port) as ws:
                    async for text in ws:
                        got.append(protocol.parse(text))
            except ConnectionClosed:
                pass
            closed.set()

        task = asyncio.ensure_future(client())
        await asyncio.sleep(0.8)
        t = time.monotonic()
        await asyncio.wait_for(server.stop(), 5.0)
        dt = time.monotonic() - t
        await asyncio.wait_for(closed.wait(), 5.0)
        await task
        return dt, got

    dt, got = asyncio.run(scenario())
    assert dt < 3.0
    assert any(m["type"] == "reading" for m in got)
    # the final "driver stopped" heartbeats were delivered before the socket closed
    assert any(m["type"] == "heartbeat" and m.get("detail") == "driver stopped" for m in got)


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@needs_loopback
@pytest.mark.parametrize("how", ["sigterm", "duration"])
def test_cli_exits_promptly_with_clients_connected(tmp_path, how):
    """Regression (step 9 report): ``python -m wfgvu --sim DIR`` logged 'server closing' but did not exit while a
    client was connected; SIGTERM needed SIGKILL. Root cause: a client that stops reading fills its TCP window and
    ``ws.send``/``ws.close`` wait forever in flow-control drain. Two clients here: one reading (must get close code
    1001) and one that never reads. The process must exit within 3 s of SIGTERM / the end of ``--duration``, and
    the recorder must have finalised session.json."""
    import os
    import signal
    import subprocess
    import sys
    from pathlib import Path

    vu = Path(cli.__file__).resolve().parents[1]
    sess = make_session(tmp_path / "s4", dur=30.0)
    port = _free_port()
    args = [sys.executable, "-m", "wfgvu", "--sim", str(sess), "--host", "127.0.0.1", "--port", str(port),
            "--record", "--records", str(tmp_path / "rec")]
    if how == "duration":
        args += ["--duration", "2.5"]
    env = dict(os.environ, PYTHONPATH=str(vu))
    proc = subprocess.Popen(args, cwd=str(vu), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    async def scenario():
        url = "ws://127.0.0.1:%d/stream" % port
        for _ in range(100):
            try:
                reader = await connect(url)
                break
            except OSError:
                await asyncio.sleep(0.1)
        else:
            raise AssertionError("server did not come up")
        stuck = await connect(url)
        stuck.transport.pause_reading()                   # never reads: its TCP window fills up
        got = []

        async def read():
            try:
                async for text in reader:
                    got.append(text)
            except ConnectionClosed:
                pass

        rtask = asyncio.ensure_future(read())
        await asyncio.sleep(1.5)
        t = time.monotonic()
        if how == "sigterm":
            proc.send_signal(signal.SIGTERM)
        else:
            t += 1.0                                       # --duration 2.5 ends about 1 s after this point
        while proc.poll() is None and time.monotonic() - t < 8.0:
            await asyncio.sleep(0.05)
        dt = time.monotonic() - t
        await asyncio.wait_for(rtask, 3.0)
        rcvd = reader.protocol.close_rcvd
        stuck.transport.abort()
        return dt, got, rcvd

    try:
        dt, got, rcvd = asyncio.run(scenario())
    finally:
        if proc.poll() is None:
            proc.kill()
        out = proc.communicate(timeout=5)[0].decode(errors="replace")
    assert proc.returncode == 0, out
    assert dt < 3.0, "exit took %.2f s\n%s" % (dt, out)
    assert got, out
    assert rcvd is not None and rcvd.code == 1001, out
    sess_dirs = [p for p in (tmp_path / "rec").iterdir() if p.is_dir()]
    assert len(sess_dirs) == 1
    import json
    info = json.loads((sess_dirs[0] / "session.json").read_text())
    assert info.get("ended_utc"), info                     # recorder flushed and finalised


def test_hello_carries_mount_live_and_sim(tmp_path):
    """The laptop takes the camera pitch from the unit: live hello = config/unit.yaml mount (camera 18 deg down by
    default); sim hello = the replayed session's own mount (synthetic samples are rendered with a level camera),
    never this unit's config."""
    from pathlib import Path
    cfg = cli.load_config()
    assert cfg["mount"]["camera_pitch_deg"] == pytest.approx(-18.0)
    live = cli.build(cfg, record=False, host="127.0.0.1", port=0, records_dir=tmp_path)
    h = protocol.parse(protocol.dumps(live.hello()))
    assert h["mount"]["camera_pitch_deg"] == pytest.approx(-18.0) and h["mount"]["camera_height_m"] == 2.6
    sample = Path(cli.__file__).resolve().parents[1] / "samples" / "flame_front"
    sim = cli.build(cfg, sim_dir=sample, host="127.0.0.1", port=0)
    h = protocol.parse(protocol.dumps(sim.hello()))
    assert h["sim"] is True and h["mount"]["camera_pitch_deg"] == 0.0
    # an older synthetic session with only truth.camera, and a session with no mount at all
    from wfgvu import replay
    s = replay.load(sample)
    s.info = {"truth": {"camera": {"height_m": 2.6, "mount_pitch_deg": -5.0, "mount_roll_deg": 0.0,
                                   "mount_yaw_deg": 0.0}}}
    assert cli.hello_mount(cfg, s)["camera_pitch_deg"] == -5.0
    s.info = {"config": {}}
    assert cli.hello_mount(cfg, s) is None
    srv = UnitServer(SCTX, {}, None, host="127.0.0.1", port=0)
    assert "mount" not in protocol.parse(protocol.dumps(srv.hello()))
