"""Source chain: fallback, reconnection with backoff, freeze detection, health hooks and switch-back."""
import time

import av
import numpy as np
import pytest

from wfglink.io.capture import CaptureWorker, ChainConfig, SourceChain, SourceOption
from wfglink.io.fake import FakeCamera, FaultScript
from wfglink.io.frames import Frame
from wfglink.io.sources import FileSource, SourceError
from wfglink.io.synthetic_live import SyntheticLiveSource

FAST = ChainConfig(stale_s=0.3, freeze_s=0.6, freeze_dn=2, backoff_min_s=0.1, backoff_max_s=0.4,
                   switch_back_s=0.8, probe_every_s=0.3, open_timeout_s=2.0, hook_grace_s=0.6)


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


def test_dark_static_scene_with_small_embers_is_not_frozen():
    """Averaging into a thumbnail hid a few small moving embers; only exact repeats are frozen."""
    import cv2

    from wfglink.io.capture import CaptureWorker, SourceOption
    from wfglink.io.frames import Frame

    w = CaptureWorker(SourceOption("x", lambda: None, True, "x"))
    rng = np.random.default_rng(0)
    for i in range(10):
        img = np.full((540, 960, 3), 20, np.uint8)
        cv2.circle(img, (100 + 6 * i, 200), 1, (60, 160, 255), -1)
        w._observe(Frame(img, i / 30, i, 0.0), float(i))
        assert w.t_last_change == float(i)
    w._observe(Frame(img.copy(), 1.0, 10, 0.0), 10.0)       # an exact repeat
    assert w.t_last_change == 9.0
    noisy = np.clip(img + rng.normal(0, 1.0, img.shape), 0, 255).astype(np.uint8)
    w._observe(Frame(noisy, 1.1, 11, 0.0), 11.0)             # sensor noise alone is a new frame
    assert w.t_last_change == 11.0


# Health hooks (the booth's screen check) -----------------------------------------------------------

def _feed(w: CaptureWorker, now: float, seed: int) -> None:
    """One new frame at time now, handled as the capture thread handles it."""
    img = np.random.default_rng(seed).integers(0, 50, (48, 64, 3)).astype(np.uint8)
    w._observe(Frame(img, now, seed, now), now)
    w.t_last_frame, w.frames = now, w.frames + 1


def test_health_hook_results_and_failure_reason():
    """True passes, None says nothing, False or a reason fails; the source turns unhealthy only when
    no check has passed for freeze_s, and then reports the hook's own reason."""
    cfg = ChainConfig(stale_s=1.0, freeze_s=1.0)
    script = {0.0: None, 0.1: True, 0.5: None, 0.9: "screen paused", 1.2: None, 1.5: "screen paused",
              1.8: True, 2.0: False, 3.0: False}
    results = iter(script.values())
    w = CaptureWorker(SourceOption("cam", lambda: None, True), lambda f: next(results))
    w.opened.set()
    w.t_open = w.t_last_change = w.t_last_hook_ok = 0.0
    health = {}
    for k, now in enumerate(script):
        _feed(w, now, k)
        if now == 0.0:
            assert not w.confirmed                       # frames, but no check has passed yet
        health[now] = w.health(cfg, now)
    assert w.confirmed and w.hook_passed
    assert health[0.5] == (True, "ok") and health[0.9] == (True, "ok")    # the pass at 0.1 s holds until 1.1 s
    assert health[1.2] == (False, "screen paused") and health[1.5] == (False, "screen paused")
    assert health[1.8] == (True, "ok") and health[2.0] == (True, "ok")
    assert health[3.0] == (False, "booth check failed")  # a plain False gives a generic reason


def test_a_failing_hook_makes_the_source_unhealthy_instead_of_crashing():
    def broken(frame):
        raise RuntimeError("no layout")

    w = CaptureWorker(SourceOption("cam", lambda: None, True), broken)
    w.opened.set()
    w.t_open = w.t_last_change = w.t_last_hook_ok = 0.0
    for k, now in enumerate((0.0, 0.5, 1.0, 1.5)):
        _feed(w, now, k)
    ok, why = w.health(ChainConfig(stale_s=1.0, freeze_s=1.0), 1.5)
    assert not ok and why.startswith("booth check error") and "no layout" in why


def test_hook_factory_gives_every_attempt_its_own_hook():
    made = []

    def factory(option):
        made.append(option.key)
        return (lambda f: True) if option.live else None

    def unplugged():
        raise SourceError("not connected")

    opts = [SourceOption("cam", unplugged, True), SourceOption("replay", unplugged, False)]
    chain = SourceChain(opts, ChainConfig(), hook_factory=factory)
    workers = [chain._launch(o) for o in (opts[0], opts[0], opts[1])]
    for w in workers:
        w.join(2.0)
    assert made == ["cam", "cam", "replay"]
    assert workers[0].health_hook is not None and workers[0].health_hook is not workers[1].health_hook
    assert workers[2].health_hook is None
    assert not any(w.confirmed for w in workers)        # no frames at all
    bad = SourceChain(opts, ChainConfig(), hook_factory=lambda o: 1 / 0)
    w = bad._launch(opts[0])                             # a broken factory: the attempt runs unchecked
    w.join(2.0)
    assert w.health_hook is None and bad.events[-1]["event"] == "hook_error"


@pytest.mark.slow
def test_a_failing_screen_check_falls_back_and_switches_back_only_after_it_passes():
    """The iPhone's screen check fails from 1.0 s to 3.0 s (a paused iPad). switch_back_s is shorter
    than freeze_s here, so a probe that took over before its check had passed would come back
    during the pause, inside its grace period, and flap."""
    t0 = time.monotonic()
    cfg = ChainConfig(stale_s=0.3, freeze_s=0.6, freeze_dn=2, backoff_min_s=0.1, backoff_max_s=0.3,
                      switch_back_s=0.3, probe_every_s=0.2, open_timeout_s=2.0, hook_grace_s=0.6)

    def factory(option):
        if option.key != "iphone":
            return None
        return lambda f: "screen paused" if 1.0 <= time.monotonic() - t0 < 3.0 else True

    opts = [
        SourceOption("iphone", lambda: FakeCamera(_synthetic(1), label="iphone", epoch=t0), True, "iPhone"),
        SourceOption("webcam", lambda: FakeCamera(_synthetic(2), label="webcam", epoch=t0), True, "Webcam"),
    ]
    chain = SourceChain(opts, cfg, hook_factory=factory)
    chain.start()
    try:
        _wait_for(chain, lambda f, st: st.key == "iphone" and time.monotonic() - t0 > 3.6, 6.0)
    finally:
        chain.stop()
    ev = [(e["t"] - t0, e["event"], e.get("key"), e.get("reason", "")) for e in chain.events]
    fails = [e for e in ev if e[1] == "failed"]
    assert fails and all(e[2] == "iphone" and e[3] == "screen paused" for e in fails), ev
    # freeze_s after the last pass, which is the last frame before 1.0 s (up to a frame earlier)
    assert 1.0 + 0.6 - 0.1 <= fails[0][0] < 1.0 + 0.6 + 0.4, ev
    assert len(fails) >= 2, ev                           # probes during the pause fail too
    act = [e for e in ev if e[1] == "activated"]
    assert [e[2] for e in act] == ["iphone", "webcam", "iphone"], ev     # no flapping
    assert act[2][0] >= 3.0 + 0.3, ev                     # back only after the check passed again


def test_a_reopened_camera_gets_a_grace_period_before_its_first_screen_check_passes():
    """Exposure and focus settle after a reopen; only a check that has passed once uses freeze_s."""
    w = CaptureWorker(SourceOption("cam", lambda: None, True), lambda f: "no screen markers")
    w.opened.set()
    w.t_open = w.t_last_change = w.t_last_hook_ok = 0.0
    cfg = ChainConfig(stale_s=1.0, freeze_s=1.0, hook_grace_s=4.0)
    for k, now in enumerate((0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5)):
        _feed(w, now, k)
        ok, why = w.health(cfg, now)
        assert ok == (now <= 4.0), (now, why)
    w2 = CaptureWorker(SourceOption("cam", lambda: None, True), lambda f: True)
    w2.opened.set()
    w2.t_open = w2.t_last_change = w2.t_last_hook_ok = 0.0
    _feed(w2, 0.0, 0)
    w2.health_hook = lambda f: "screen paused"
    for k, now in enumerate((0.5, 1.0, 1.5), start=1):
        _feed(w2, now, k)
    assert not w2.health(cfg, 1.5)[0]          # it passed once, so the normal limit applies
