"""Recorder failure handling (findings VU-R1, VU-R4, VU-R5, VU-R8) and replay of damaged files.

Every session here is synthetic test data written by the tests themselves; device errors are simulated by patching
the recorder's file layer.
"""
import asyncio
import errno
import gzip
import json
import shutil
import threading
import time
import zlib
from pathlib import Path

import pytest

from wfgvu import __main__ as cli
from wfgvu import protocol, recorder, replay
from wfgvu.server import UnitServer

CTX = protocol.Context("VU-01", "VU-01-20261117T101500Z", sim=True)
VU = Path(cli.__file__).resolve().parents[1]


def tc(i, sensor="tc_plate", t=None):
    return CTX.make("reading", sensor=sensor, seq=i, data={"temp_c": 20.0 + i, "cj_c": 21.0, "fault": None},
                    t_mono=t if t is not None else 100.0 + 0.1 * i)


def wait_for(pred, timeout=3.0):
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def seqs(session_dir, sensor="tc_plate"):
    return [m["seq"] for m in replay.load(session_dir).streams[sensor]]


# ------------------------------------------------------------------------------------------------ VU-R1
def test_rotation_open_failure_keeps_writer_alive_and_recovers(tmp_path, monkeypatch):
    """A rotation whose new part cannot be opened (USB SSD dropped: EIO) used to leave a closed GzipFile in place; the
    next write raised ValueError and killed the writer thread silently. Now: the writer stays alive, the error is an
    event and makes the unit heartbeat unhealthy, messages are dropped (counted) while the disk is gone, and writing
    resumes in a NEW part once the device is back; everything written before and after replays."""
    events = []
    real_open = recorder._Sink._open
    broken = {"on": False}

    def flaky_open(self):
        if broken["on"] and self.part > 0:
            raise OSError(errno.EIO, "Input/output error (simulated)")
        return real_open(self)

    monkeypatch.setattr(recorder._Sink, "_open", flaky_open)
    rec = recorder.Recorder(tmp_path, "R1", "VU-01", flush_s=0.02, rotate_bytes=200, error_event_s=0.0,
                            on_event=lambda k, d: events.append((k, d)), free_mb_fn=lambda p: 1e6)
    ok_before = [i for i in range(10) if rec.write(tc(i))]
    assert wait_for(lambda: rec.written >= 10)
    broken["on"] = True
    assert wait_for(lambda: any(k == "record_rotated" for k, _ in events) or rec.errors > 0)
    for i in range(10, 40):
        rec.write(tc(i))
        time.sleep(0.005)
    assert wait_for(lambda: rec.errors >= 1)
    assert rec.alive and not rec.failed                         # the old code: thread dead here
    assert any(k == "record_error" and "Input/output" in d for k, d in events)
    ok, why = rec.health()
    assert not ok and "record error" in why                    # unit heartbeat goes "error"
    st = rec.stats()
    assert st["alive"] is True and st["failed"] is False and st["paused"] is False
    broken["on"] = False                                        # device back
    time.sleep(0.1)
    for i in range(40, 60):
        rec.write(tc(i))
        time.sleep(0.005)
    assert wait_for(lambda: rec.written >= 10 + 20 - 1)
    t = time.monotonic()
    rec.close(timeout=3.0)
    assert time.monotonic() - t < 3.5
    got = seqs(tmp_path / "R1")
    assert got[:10] == ok_before
    assert set(range(40, 60)) <= set(got)                       # writes resumed after recovery
    assert len(got) == rec.written and rec.written + rec.dropped == 60
    info = json.loads((tmp_path / "R1" / "session.json").read_text())
    assert info["closed_cleanly"] is True and info["record_errors"] >= 1 and info["dropped"] == rec.dropped
    assert info["counts"]["tc_plate"] == rec.written


def test_writer_survives_unexpected_exception_and_reports_failed(tmp_path, monkeypatch):
    """Last-resort guard: an exception outside the per-item handling (here: in the flush pass) must not end the
    writer thread; it sets ``failed`` and the unit heartbeat reports the recorder as dead."""
    rec = recorder.Recorder(tmp_path, "G", "VU-01", flush_s=0.02, free_mb_fn=lambda p: 1e6)
    calls = {"n": 0}
    real = rec._flush_all

    def boom():
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated bug")
        real()

    rec._flush_all = boom
    assert wait_for(lambda: rec.failed)
    assert rec.alive
    rec.write(tc(0))
    assert wait_for(lambda: rec.written == 1)                   # still recording
    ok, why = rec.health()
    assert not ok and why.startswith("recorder dead") and "simulated bug" in why
    rec.close()
    info = json.loads((tmp_path / "G" / "session.json").read_text())
    assert info["closed_cleanly"] is False and "simulated bug" in info["writer_failed"]


def test_close_is_bounded_when_writer_hangs_with_a_full_queue(tmp_path, monkeypatch):
    """close() used to put the stop marker without a timeout: with a hung writer and a full queue it blocked
    forever and session.json was never finalised. Now it returns within its timeout and session.json says the
    recorder did not close cleanly."""
    release = threading.Event()
    real_write = recorder._Sink.write

    def hung_write(self, data):
        release.wait(10.0)
        return real_write(self, data)

    monkeypatch.setattr(recorder._Sink, "write", hung_write)
    rec = recorder.Recorder(tmp_path, "H", "VU-01", queue_max=5, free_mb_fn=lambda p: 1e6)
    for i in range(50):
        rec.write(tc(i))
    assert rec._q.full()
    t = time.monotonic()
    rec.close(timeout=0.6)
    dt = time.monotonic() - t
    release.set()
    assert dt < 1.5, dt
    info = json.loads((tmp_path / "H" / "session.json").read_text())
    assert info["closed_cleanly"] is False and info["writer_alive"] is True
    assert info["ended_utc"] and info["dropped"] >= 45
    assert wait_for(lambda: not rec.alive)


def test_queue_is_bounded_by_bytes(tmp_path):
    """Thermal frames are ~95 kB: a message-count bound alone allowed ~1.9 GB of queue on a 2-4 GB Pi."""
    release = threading.Event()
    rec = recorder.Recorder(tmp_path, "B", "VU-01", queue_max_mb=0.01, free_mb_fn=lambda p: 1e6)
    real = rec._write_item
    rec._write_item = lambda item: (release.wait(5.0), real(item))
    big = CTX.make("event", kind="note", detail="x" * 3000)
    oks = [rec.write(big) for _ in range(20)]
    assert oks.count(True) <= 5 and rec.dropped >= 15
    assert rec._q_bytes <= rec.queue_max_bytes
    release.set()
    rec.close()


def test_unit_heartbeat_reports_recorder_problems():
    """server.py used to send unit status "ok" whatever the recorder's state."""
    class FakeRec:
        dropped = 3

        def __init__(self, ok, why):
            self.state = (ok, why)

        def health(self):
            return self.state

    async def beats(rec):
        server = UnitServer(protocol.Context("VU-01", "VU-01-HB", sim=True), {}, rec, heartbeat_s=0.01)
        out = []
        server.emit = out.append
        task = asyncio.ensure_future(server._unit_heartbeat())
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return out

    for state, want in (((True, ""), "ok"), ((False, "recorder dead"), "error"),
                        ((False, "recording paused"), "error")):
        out = asyncio.run(beats(FakeRec(*state)))
        assert out and all(m["status"] == want for m in out), (state, out[0])
        if want == "error":
            assert state[1] in out[0]["detail"]
    out = asyncio.run(beats(None))
    assert out[0]["status"] == "ok"


def test_paused_recording_is_unhealthy(tmp_path):
    rec = recorder.Recorder(tmp_path, "P", "VU-01", flush_s=0.05, disk_check_s=0.05, free_mb_fn=lambda p: 10.0)
    assert wait_for(lambda: rec.paused)
    assert rec.health() == (False, "recording paused")
    rec.close()


# ------------------------------------------------------------------------------------------------ VU-R8
def test_server_stop_gives_the_recorder_its_own_budget():
    class FakeRec:
        dropped = 0
        budget = None

        def close(self, timeout=10.0):
            FakeRec.budget = timeout

    server = UnitServer(protocol.Context("VU-01", "VU-01-ST", sim=True), {}, FakeRec(), stop_timeout_s=0.5,
                        recorder_close_s=4.0)
    asyncio.run(server.stop())
    assert FakeRec.budget is not None and FakeRec.budget >= 4.0


def test_close_fsyncs_and_records_clean_close(tmp_path, monkeypatch):
    synced = []
    real = recorder.os.fsync
    monkeypatch.setattr(recorder.os, "fsync", lambda fd: (synced.append(fd), real(fd))[1])
    rec = recorder.Recorder(tmp_path, "C", "VU-01", free_mb_fn=lambda p: 1e6)
    n_start = len(synced)
    assert n_start >= 2                                         # session.json file + its directory
    rec.write(tc(0))
    rec.close()
    assert len(synced) >= n_start + 3                           # stream on close, session.json, directory
    info = json.loads((tmp_path / "C" / "session.json").read_text())
    assert info["closed_cleanly"] is True and info["writer_alive"] is False and "queue_left" not in info
    assert not (tmp_path / "C" / "session.json.tmp").exists()


# ------------------------------------------------------------------------------------------------ VU-R4
def test_same_session_id_twice_gets_separate_directories(tmp_path):
    """Two boots with the same restored wall clock give the same session id. The second recorder used to reuse the
    directory, overwrite session.json and append a gzip member after the first boot's power-cut stream, which made
    BOTH unreadable. Now each gets its own directory and both read back fully."""
    a = recorder.Recorder(tmp_path, CTX.session_id, "VU-01", flush_s=0.02, free_mb_fn=lambda p: 1e6)
    for i in range(5):
        a.write(tc(i))
    assert wait_for(lambda: len(list(replay.iter_lines(a.dir / "tc_plate.jsonl.gz"))) == 5)
    # power cut: the first recorder never closes (no gzip trailer, session.json not finalised)
    b = recorder.Recorder(tmp_path, CTX.session_id, "VU-01", flush_s=0.02, free_mb_fn=lambda p: 1e6)
    assert b.session_id == CTX.session_id + "-2" and b.dir != a.dir
    for i in range(5):
        b.write(tc(100 + i))
    b.close()
    assert seqs(a.dir) == list(range(5))
    assert seqs(b.dir) == list(range(100, 105))
    ia = json.loads((a.dir / "session.json").read_text())
    ib = json.loads((b.dir / "session.json").read_text())
    assert ia["session_id"] == CTX.session_id and ib["session_id"] == CTX.session_id + "-2"
    assert ib["session_id_requested"] == CTX.session_id
    for info in (ia, ib):
        assert "boot_id" in info and info["clock"]["synchronized"] in ("unsynchronized", "synchronized (NTP)")
        assert "no RTC" in info["clock"]["source"]
    c = recorder.Recorder(tmp_path, CTX.session_id, "VU-01", free_mb_fn=lambda p: 1e6)
    assert c.session_id == CTX.session_id + "-3"
    c.close()
    a.close()


def test_existing_stream_file_is_never_appended(tmp_path):
    """Stream files are opened "xb": a file already there is left untouched, record_error is raised and the stream
    continues in the next free part."""
    events = []
    rec = recorder.Recorder(tmp_path, "X", "VU-01", error_event_s=0.0, on_event=lambda k, d: events.append((k, d)),
                            free_mb_fn=lambda p: 1e6)
    foreign = b"not ours"
    (rec.dir / "tc_plate.jsonl.gz").write_bytes(foreign)
    rec.write(tc(0))
    rec.write(tc(1))
    rec.close()
    assert (rec.dir / "tc_plate.jsonl.gz").read_bytes() == foreign
    assert any(k == "record_error" and "not appended" in d for k, d in events)
    assert [m["seq"] for m in replay.SensorStream(None, "tc_plate", [rec.dir / "tc_plate.1.jsonl.gz"])] == [0, 1]


def test_main_build_uses_the_recorders_session_id(tmp_path, monkeypatch):
    """__main__ must put the id the recorder really used into the protocol context before anything is sent, or the
    laptop and the records would carry different ids."""
    monkeypatch.setattr(protocol, "make_session_id", lambda unit_id, ts=None: "%s-20261117T101500Z" % unit_id)
    cfg = cli.load_config()
    servers = [cli.build(cfg, record=True, host="127.0.0.1", port=0, records_dir=tmp_path) for _ in range(2)]
    try:
        assert servers[0].ctx.session_id == "VU-01-20261117T101500Z"
        assert servers[1].ctx.session_id == "VU-01-20261117T101500Z-2"
        for s in servers:
            assert s.recorder.session_id == s.ctx.session_id
            assert all(d.ctx.session_id == s.ctx.session_id for d in s.drivers)
            assert s.hello()["session_id"] == s.ctx.session_id
    finally:
        for s in servers:
            s.recorder.close()


def test_iter_lines_keeps_lines_before_a_corrupt_member(tmp_path):
    """Defence in depth: a gzip member appended after a power-cut (sync-flushed, no trailer) stream used to make
    the whole file read as empty; now the lines before the damage are returned."""
    p = tmp_path / "f.jsonl.gz"
    lines = [("line %d\n" % i).encode() for i in range(5)]
    with open(p, "wb") as raw:
        gz = gzip.GzipFile(fileobj=raw, mode="wb", mtime=0)
        for ln in lines:
            gz.write(ln)
        gz.flush(zlib.Z_SYNC_FLUSH)                           # power cut here: no trailer
        raw.flush()
    with open(p, "ab") as raw:                                  # what the old recorder did on the next boot
        raw.write(gzip.compress(b"later 0\nlater 1\n", mtime=0))
    assert list(replay.iter_lines(p)) == lines
    # a normal multi-member file still reads whole, and large files decode across chunk boundaries
    q = tmp_path / "g.jsonl.gz"
    body = [("%06d %s\n" % (i, "x" * (i % 300))).encode() for i in range(3000)]
    q.write_bytes(gzip.compress(b"".join(body[:1500]), mtime=0) + gzip.compress(b"".join(body[1500:]), mtime=0))
    assert list(replay.iter_lines(q, chunk_size=4096)) == body
    # truncated tail: up to the last complete line
    data = q.read_bytes()
    q.write_bytes(data[: len(data) // 3])
    got = list(replay.iter_lines(q))
    assert 0 < len(got) < 1500 and got == body[:len(got)]


# ------------------------------------------------------------------------------------------------ VU-R5
def _copy_sample(tmp_path, name="no_fire"):
    d = tmp_path / name
    shutil.copytree(VU / "samples" / name, d)
    return d


@pytest.mark.parametrize("content", [b"", b'{"unit_id": "VU-01", "sess', b"[1, 2]"])
def test_unreadable_session_json_does_not_stop_replay(tmp_path, content):
    """A power cut right after a session started can leave session.json empty; replay.load used to raise
    JSONDecodeError (and so did python -m wfgvu --sim and every laptop tool)."""
    d = _copy_sample(tmp_path)
    (d / "session.json").write_bytes(content)
    s = replay.load(d)
    assert s.info == {} and s.info_error == "session_json_unreadable"
    assert s.session_id == d.name and s.unit_id == "VU-01"
    assert s.sim is True                                        # the sample's messages say sim: never "real"
    assert len(list(s.streams["tc_plate"])) > 0 and s.duration > 0
    server = cli.build(cli.load_config(), d, record=False, host="127.0.0.1", port=0)
    assert server.ctx.sim is True and server.mount is None      # no mount invented for the replay
    good = replay.load(VU / "samples" / "no_fire")
    assert good.info_error is None and good.info


def test_unreadable_session_json_falls_back_to_directory_name(tmp_path):
    d = recorder.write_session(tmp_path / "VU-07-20261117T101500Z-2", {"unit_id": "VU-07", "session_id": "x"},
                               [tc(i) for i in range(3)])
    (d / "session.json").write_text("")
    s = replay.load(d)
    assert s.unit_id == "VU-07" and s.session_id == "VU-07-20261117T101500Z-2"
    (d / "session.json").unlink()
    assert replay.load(d).info_error == "session_json_missing"
