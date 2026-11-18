"""Recorder (files, flush, rotation, disk checks) and replay (load, merge, truncated files, timed playback).

All sessions here are synthetic test data written by the tests themselves.
"""
import gzip
import json
import threading
import time

import numpy as np
import pytest

from wfgvu import protocol, recorder, replay

CTX = protocol.Context("VU-01", "VU-01-20261117T101500Z", sim=True)


def tc(i, sensor="tc_plate", t=None):
    return CTX.make("reading", sensor=sensor, seq=i, data={"temp_c": 20.0 + i, "cj_c": 21.0, "fault": None},
                    t_mono=t if t is not None else 100.0 + 0.1 * i)


def hb(i, sensor="tc_plate", status="ok", t=None):
    return CTX.make("heartbeat", sensor=sensor, status=status, detail="", last_reading_seq=None, rate_hz=10.0,
                    seq=i, t_mono=t if t is not None else 100.05 + 0.5 * i)


def wait_for(pred, timeout=3.0):
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_recorder_layout_exact_text_and_session_json(tmp_path):
    events = []
    rec = recorder.Recorder(tmp_path, CTX.session_id, "VU-01", sim=True, config={"a": 1}, flush_s=0.05,
                            on_event=lambda k, d: events.append(k), free_mb_fn=lambda p: 1e6)
    sent = []

    def worker(sensor):
        for i in range(50):
            m = tc(i, sensor)
            text = protocol.dumps(m)
            sent.append(text)
            rec.write(m, text)

    threads = [threading.Thread(target=worker, args=(s,)) for s in ("tc_plate", "tc_air", "tc_housing")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rec.write(hb(0))
    rec.write(CTX.make("heartbeat", sensor="unit", status="ok", detail="", last_reading_seq=None, rate_hz=None,
                       seq=0))
    rec.write(CTX.make("event", kind="client_connected", detail="x"))
    rec.write(CTX.make("hello", sensors=[], version="0", config_digest="d"))       # not recorded
    rec.write_raw("radar_uart", b"\x02\x01\x04\x03\x06\x05\x08\x07abc")
    rec.close()
    d = tmp_path / CTX.session_id
    names = sorted(p.name for p in d.iterdir())
    assert names == ["events.jsonl.gz", "radar_uart.bin", "session.json", "tc_air.jsonl.gz",
                     "tc_housing.jsonl.gz", "tc_plate.jsonl.gz", "unit.jsonl.gz"]
    info = json.loads((d / "session.json").read_text())
    assert info["unit_id"] == "VU-01" and info["sim"] is True and info["config"] == {"a": 1}
    assert info["counts"]["tc_plate"] == 51 and info["dropped"] == 0 and info["ended_utc"]
    assert info["t_mono_first"] == pytest.approx(100.0)
    lines = []
    for s in ("tc_plate", "tc_air", "tc_housing"):
        with gzip.open(d / ("%s.jsonl.gz" % s), "rt") as fh:
            lines += [ln.rstrip("\n") for ln in fh if '"reading"' in ln]
    assert sorted(lines) == sorted(sent)                          # byte-exact wire text
    assert (d / "radar_uart.bin").read_bytes().endswith(b"abc")
    assert rec.rec_bytes > 0                                      # still readable after close


def test_recorder_flushes_while_open_and_survives_truncation(tmp_path):
    rec = recorder.Recorder(tmp_path, "S1", "VU-01", flush_s=0.1, free_mb_fn=lambda p: 1e6)
    for i in range(20):
        rec.write(tc(i))
    path = tmp_path / "S1" / "tc_plate.jsonl.gz"
    # still open: after one flush period the data is on disk and readable (Z_SYNC_FLUSH)
    assert wait_for(lambda: len(list(replay.iter_lines(path))) == 20)
    assert rec.rec_bytes > 0
    rec.close()
    # simulate a power cut mid-stream: cut the compressed file
    data = path.read_bytes()
    path.write_bytes(data[: len(data) * 2 // 3])
    s = replay.load(tmp_path / "S1")
    got = [m["seq"] for m in s.streams["tc_plate"]]
    assert 0 < len(got) < 20 and got == list(range(len(got)))


def test_recorder_rotation_and_replay_order(tmp_path):
    events = []
    rec = recorder.Recorder(tmp_path, "S2", "VU-01", flush_s=0.02, rotate_bytes=4000,
                            on_event=lambda k, d: events.append((k, d)), free_mb_fn=lambda p: 1e6)
    rng = np.random.default_rng(0)
    for i in range(30):
        m = CTX.make("reading", sensor="thermal", seq=i, t_mono=10.0 + i * 0.04,
                     data=protocol.encode_thermal(250 + 100 * rng.random((24, 32))))
        rec.write(m)
        time.sleep(0.01)
    rec.close()
    parts = replay.stream_files(tmp_path / "S2", "thermal")
    assert len(parts) >= 2 and parts[0].name == "thermal.jsonl.gz" and parts[1].name == "thermal.1.jsonl.gz"
    assert any(k == "record_rotated" for k, _ in events)
    s = replay.load(tmp_path / "S2")
    assert [m["seq"] for m in s.streams["thermal"]] == list(range(30))


def test_recorder_disk_low_pause_resume(tmp_path):
    free = {"mb": 150.0}
    events = []
    rec = recorder.Recorder(tmp_path, "S3", "VU-01", flush_s=0.05, disk_check_s=0.05, low_free_mb=1000,
                            stop_free_mb=200, on_event=lambda k, d: events.append(k),
                            free_mb_fn=lambda p: free["mb"])
    assert wait_for(lambda: "record_paused" in events and "disk_low" in events)
    rec.write(tc(0))
    assert wait_for(lambda: rec.dropped >= 1)
    free["mb"] = 5000.0
    assert wait_for(lambda: "record_resumed" in events)
    rec.write(tc(1))
    rec.close()
    s = replay.load(tmp_path / "S3")
    assert [m["seq"] for m in s.streams["tc_plate"]] == [1]


def test_recorder_queue_full_counts_drops(tmp_path):
    rec = recorder.Recorder(tmp_path, "S4", "VU-01", queue_max=1, free_mb_fn=lambda p: 1e6)
    oks = [rec.write(tc(i)) for i in range(2000)]
    rec.close()
    assert rec.dropped == oks.count(False)
    assert rec.dropped + json.loads((tmp_path / "S4" / "session.json").read_text())["counts"]["tc_plate"] == 2000


def test_write_session_and_replay_streams_merge_and_bad_lines(tmp_path):
    msgs = [tc(i, "tc_plate", t=100.0 + 0.1 * i) for i in range(10)]
    msgs += [tc(i, "tc_air", t=100.05 + 0.1 * i) for i in range(10)]
    msgs += [hb(i, "tc_air") for i in range(2)]
    msgs.append(CTX.make("event", kind="note", detail="synthetic", t_mono=100.0))
    d = recorder.write_session(tmp_path / "W", {"unit_id": "VU-01", "session_id": "W", "truth": {"x": 1}}, msgs)
    info = json.loads((d / "session.json").read_text())
    assert info["sim"] is True and info["truth"] == {"x": 1} and info["t_mono_last"] == pytest.approx(100.95)
    # append a corrupt line and a message for the wrong sensor to tc_air
    with gzip.open(d / "tc_air.1.jsonl.gz", "wt") as fh:
        fh.write("{not json\n")
        fh.write(protocol.dumps(tc(99, "tc_plate", t=101.0)) + "\n")
        fh.write(protocol.dumps(tc(10, "tc_air", t=101.05)) + "\n")
    s = replay.load(d)
    assert set(s.streams) == {"tc_plate", "tc_air"}
    air = list(s.streams["tc_air"])
    assert len(air) == 13 and s.streams["tc_air"].bad_lines == 2
    assert len(list(s.streams["tc_air"].readings())) == 11
    merged = [m["t_mono"] for m in s.merged()]
    assert merged == sorted(merged) and len(merged) == 10 + 13
    assert s.t0 == pytest.approx(100.0) and s.duration == pytest.approx(0.95)
    assert [e["kind"] for e in s.events()] == ["note"]
    with pytest.raises(FileNotFoundError):
        replay.load(tmp_path / "nope")
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        replay.load(tmp_path / "empty")


def test_duration_scanned_when_session_json_lacks_it(tmp_path):
    d = recorder.write_session(tmp_path / "X", {"unit_id": "VU-01", "session_id": "X", "t_mono_first": None,
                                                "t_mono_last": None}, [tc(i) for i in range(5)])
    s = replay.load(d)
    assert s.t0 == pytest.approx(100.0) and s.duration == pytest.approx(0.4)


def test_playback_timing_speed_and_loop(tmp_path):
    d = recorder.write_session(tmp_path / "P", {"unit_id": "VU-01", "session_id": "P"},
                               [tc(i, t=50.0 + 0.1 * i) for i in range(5)])
    s = replay.load(d)
    s.start(speed=2.0)
    t0 = time.monotonic()
    got = [(time.monotonic() - t0, m["seq"]) for m in s.streams["tc_plate"].play()]
    assert [g[1] for g in got] == [0, 1, 2, 3, 4]
    assert got[-1][0] == pytest.approx(0.2, abs=0.08)            # 0.4 s recorded at speed 2
    # loop: second pass offset by duration + gap, seq order repeats
    s2 = replay.load(d)
    s2.start(speed=20.0, loop=True)
    stop = threading.Event()
    out = []
    for m in s2.streams["tc_plate"].play(stop):
        out.append(m["seq"])
        if len(out) == 12:
            stop.set()
    assert out[:12] == [0, 1, 2, 3, 4] * 2 + [0, 1]
    timed = list(zip(range(7), s2.streams["tc_plate"].timed(loop=True)))
    assert timed[5][1][0] == pytest.approx(s2.duration + replay.LOOP_GAP_S)
    # stop interrupts a long wait
    s3 = replay.load(d)
    s3.start(speed=0.01)
    stop3 = threading.Event()
    threading.Timer(0.1, stop3.set).start()
    t = time.monotonic()
    assert [m["seq"] for m in s3.streams["tc_plate"].play(stop3)] == [0]
    assert time.monotonic() - t < 1.0
