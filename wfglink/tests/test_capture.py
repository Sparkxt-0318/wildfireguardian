"""Source chain: fallback, reconnection with backoff, freeze detection and switch-back."""
import time

import av
import numpy as np
import pytest

from wfglink.io.capture import ChainConfig, SourceChain, SourceOption
from wfglink.io.fake import FakeCamera, FaultScript
from wfglink.io.sources import FileSource
from wfglink.io.synthetic_live import SyntheticLiveSource

FAST = ChainConfig(stale_s=0.3, freeze_s=0.6, freeze_dn=0.4, backoff_min_s=0.1, backoff_max_s=0.4,
                   switch_back_s=0.8, probe_every_s=0.3, open_timeout_s=2.0)


def _synthetic(seed):
    return SyntheticLiveSource(width=160, height=96, fps=30, rate_hz=30, seed=seed, realtime=True)


def _clip(path, n=45, fps=30):
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = 160, 96, "yuv420p"
        rng = np.random.default_rng(0)
        for i in range(n):
            img = (rng.integers(0, 40, (96, 160, 3)) + i).astype(np.uint8)
            for pkt in s.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return path


def _wait_for(chain, pred, timeout):
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        f, st = chain.latest()
        if pred(f, st):
            return f, st
        time.sleep(0.02)
    return chain.latest()


@pytest.mark.slow
def test_disconnect_falls_back_and_switches_back(tmp_path):
    t0 = time.monotonic()
    script = FaultScript([("disconnect", 1.0, 2.5)])
    opts = [
        SourceOption("iphone", lambda: FakeCamera(_synthetic(1), script, label="iphone", epoch=t0), True, "iPhone"),
        SourceOption("webcam", lambda: FakeCamera(_synthetic(2), FaultScript(), label="webcam", epoch=t0), True, "Webcam"),
    ]
    chain = SourceChain(opts, FAST)
    chain.start()
    try:
        f, st = _wait_for(chain, lambda f, st: st.key == "iphone" and f is not None, 2.0)
        assert st.key == "iphone" and st.state == "live"
        # Disconnect at 1.0 s: the webcam must take over quickly.
        f, st = _wait_for(chain, lambda f, st: st.key == "webcam" and f is not None, 2.0)
        assert st.key == "webcam"
        assert time.monotonic() - t0 < 2.4
        # The iPhone returns at 2.5 s and must win back after 0.8 s of sustained health.
        f, st = _wait_for(chain, lambda f, st: st.key == "iphone" and time.monotonic() - t0 > 2.5, 4.0)
        assert st.key == "iphone"
        assert st.failures.get("iphone", 0) >= 1
    finally:
        chain.stop()


@pytest.mark.slow
def test_frozen_camera_is_replaced_by_labelled_replay(tmp_path):
    t0 = time.monotonic()
    clip = _clip(tmp_path / "replay.mp4")
    script = FaultScript([("freeze", 0.8, 30.0)])
    opts = [
        SourceOption("iphone", lambda: FakeCamera(_synthetic(1), script, label="iphone", epoch=t0), True, "iPhone"),
        SourceOption("replay", lambda: FileSource(clip, loop=True, realtime=True), False, "Replay"),
    ]
    chain = SourceChain(opts, FAST)
    chain.start()
    try:
        f, st = _wait_for(chain, lambda f, st: st.key == "replay" and f is not None, 3.0)
        assert st.key == "replay"
        assert st.live is False and st.state == "replay"
        assert "frozen" in " ".join(e.get("reason", "") for e in chain.events)
    finally:
        chain.stop()


@pytest.mark.slow
def test_no_camera_at_all_uses_replay_and_keeps_retrying(tmp_path):
    t0 = time.monotonic()
    clip = _clip(tmp_path / "replay.mp4")
    never = FaultScript([("fail_open", 0.0, 60.0)])
    opts = [
        SourceOption("iphone", lambda: FakeCamera(_synthetic(1), never, label="iphone", epoch=t0), True),
        SourceOption("replay", lambda: FileSource(clip, loop=True, realtime=True), False),
    ]
    chain = SourceChain(opts, FAST)
    chain.start()
    try:
        f, st = _wait_for(chain, lambda f, st: st.key == "replay" and f is not None, 2.0)
        assert st.key == "replay"
        time.sleep(1.0)
        assert chain.status.failures.get("iphone", 0) >= 2  # retried with backoff
        f2, st2 = chain.latest()
        assert f2 is not None and f2.meta.get("loop", 0) >= 0
    finally:
        chain.stop()


def test_file_source_true_timestamps_and_loop(tmp_path):
    clip = _clip(tmp_path / "c.mp4", n=10, fps=25)
    src = FileSource(clip, loop=True)
    src.open()
    times = [src.read().t for _ in range(25)]
    src.close()
    d = np.diff(times)
    assert np.allclose(d, 1 / 25, atol=1e-6)  # strictly increasing across the loop seam
    assert times[0] == pytest.approx(0.0, abs=1e-6)
