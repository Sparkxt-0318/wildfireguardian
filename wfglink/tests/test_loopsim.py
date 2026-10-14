"""Camera-in-the-loop simulator: exact blend weights, LCD response, scan tears, the reader's
view of the codes, camera phases, faults, and the booth path.

The slow tests film a small prepared clip (640x360, 3 s) through LoopSimSource and the
booth pipeline. They run the camera at 29 fps instead of the default 30.0009 (30 ppm
against the panel, like two quartz clocks) so its phase sweeps the whole content period
several times within a few seconds; at the default the phase hardly moves in a short run,
which then measures one phase only (at hold 2 the yield is then close to 0.5 or to 1.0).

The pause tests check the plan's source health rule (section 7): a camera filming a paused
iPad, or no iPad at all, shows "iPad paused" or "iPad screen not found" and becomes
unhealthy after capture.freeze_s, and the chain falls back and comes back.
"""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import av
import cv2
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.io.fake import FakeClock, FaultScript
from wfglink.io.sources import SourceError
from wfglink.pipeline import BoothContext, Pipeline
from wfglink.screen.booth_prep import load_sidecar, prepare
from wfglink.screen.codes import Layout
from wfglink.screen.loopsim import LoopSimSource, hold_from_name
from wfglink.screen.rectify import ScreenRectifier

QUIET = dict(read_noise_dn=0.0, shot_noise=0.0, defocus_px=0.0, ae_amp=0.0, size=(480, 270))


def _levels_clip(path: Path, n_source: int = 20, hold: int = 2, size=(160, 90)) -> Path:
    """Uniform gray frames, about level 20 + 10 m for source frame m, each written `hold` times."""
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = size[0], size[1], "yuv420p"
        s.options = {"crf": "0", "preset": "ultrafast"}
        for m in range(n_source):
            img = np.full((size[1], size[0], 3), 20 + 10 * m, np.uint8)
            for _ in range(hold):
                for p in s.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                    c.mux(p)
        for p in s.encode():
            c.mux(p)
    return path


def _level(src: LoopSimSource, m: int) -> float:
    """Mean decoded level of uniform source frame m (the YUV round trip shifts it a little)."""
    return float(src._clip.get(m).astype(float).mean())


def _lit(src: LoopSimSource, v: float) -> float:
    """Camera level of panel level v with gain 1 and no noise."""
    return src.black_dn + (src.white_dn - src.black_dn) * v / 255.0


def _cam_point(src: LoopSimSource, x: float, y: float) -> tuple[int, int]:
    p = cv2.perspectiveTransform(np.float32([[[x, y]]]), src.H)[0, 0]
    return int(round(p[0])), int(round(p[1]))


def test_hold_from_name():
    assert hold_from_name("data/booth/C1_timber_hold2.mp4") == 2
    assert hold_from_name("x_hold3.mp4") == 3
    assert hold_from_name("plain.mp4") == 1


def test_weights_are_exact_and_the_panel_scan_tears(tmp_path):
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    src = LoopSimSource(clip, exp_s=0.0005, camera_fps=30.0, phase_s=0.0, **QUIET)
    src.open()
    assert src.info["n_source"] == 20 and src.info["hold"] == 2
    # Weights over every contributing source frame add up to 1 at every pixel.
    for s in np.linspace(0.0, 0.5, 23):
        w = src._weights(float(s))
        total = sum(np.broadcast_to(v, (90, 160)) for v in w.values())
        assert np.allclose(total, 1.0, atol=1e-6)
    # Source frame 1 is written by the refresh starting at 4/60 s; the scan reaches the
    # middle of the panel half a refresh later. A short exposure then shows frame 1 above
    # the scan line and frame 0 below it: a tear without any blend.
    s = 4 / 60 + 0.5 / 60
    img, truth = src.render(s)
    assert truth["torn"] and set(truth["sources"]) == {0, 1}
    top = img[_cam_point(src, 80, 5)[::-1]].astype(float).mean()
    bottom = img[_cam_point(src, 80, 85)[::-1]].astype(float).mean()
    assert top == pytest.approx(_lit(src, _level(src, 1)), abs=1.5)
    assert bottom == pytest.approx(_lit(src, _level(src, 0)), abs=1.5)


def test_exposure_across_a_change_blends_in_proportion(tmp_path):
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    src = LoopSimSource(clip, exp_s=1 / 60, scan_s=0.0, camera_fps=30.0, phase_s=0.0, **QUIET)
    src.open()
    img, truth = src.render(4 / 60 - 0.25 / 60)        # a quarter of the exposure before the change
    assert truth["mixed"] and not truth["torn"]
    assert truth["sources"][0] == pytest.approx(0.25, abs=1e-3) and truth["sources"][1] == pytest.approx(0.75, abs=1e-3)
    v = img[_cam_point(src, 80, 45)[::-1]].astype(float).mean()
    assert v == pytest.approx(_lit(src, 0.25 * _level(src, 0) + 0.75 * _level(src, 1)), abs=1.5)


def test_lcd_response_weights_match_a_first_order_panel(tmp_path):
    # A panel whose pixels follow each new level with a first-order lag: the closed-form
    # weights must equal a direct integration of tau dL/dt = drive - L over the exposure.
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    tau, e = 0.006, 1 / 60
    src = LoopSimSource(clip, exp_s=e, scan_s=0.0, response_s=tau, camera_fps=30.0, phase_s=0.0, **QUIET)
    src.open()
    levels = {m: _level(src, m) for m in range(20)}
    dt = 1e-5
    for s in (4 / 60 - 0.3 / 60, 4 / 60 + 0.2 / 60, 9 / 60, 0.41):
        w = src._weights(s)
        total = sum(float(np.mean(v)) for v in w.values())
        assert total == pytest.approx(1.0, abs=1e-9)
        got = sum(levels[m] * float(np.mean(v)) for m, v in w.items())
        t = np.arange(s - 12 * tau, s + e, dt)
        drive = np.array([levels[(src._video_at(u) % src._clip.n_video) // 2] for u in t])
        lev = np.empty_like(drive)
        lev[0] = drive[0]
        for i in range(1, len(t)):
            lev[i] = lev[i - 1] + (drive[i] - lev[i - 1]) * (1 - np.exp(-dt / tau))
        want = float(lev[t >= s].mean())
        assert got == pytest.approx(want, abs=0.05), s
    # A slow panel still shows the previous frame partly, where an instant one is clean.
    fast = LoopSimSource(clip, exp_s=0.004, scan_s=0.0, camera_fps=30.0, phase_s=0.0, **QUIET)
    fast.open()
    s = 4 / 60 + 0.001
    assert len(fast._weights(s)) == 1 and len(src._weights(s)) == 2


def test_pillarboxed_clip_keeps_the_panel_aspect(tmp_path):
    clip = _levels_clip(tmp_path / "narrow_hold2.mp4", size=(120, 90))     # 4:3, narrower than the iPad
    src = LoopSimSource(clip, scan="right", camera_fps=30.0, phase_s=0.0, **QUIET)
    src.open()
    pw = 90 * src.panel_aspect
    x_off = (pw - 120) / 2
    # The first video column sits x_off into the panel, so the scan reaches it that much later.
    assert -float(src._offset[0, 0]) / src.scan_s == pytest.approx((0.5 + x_off) / pw, abs=1e-9)


def test_reopen_starts_a_new_camera_phase(tmp_path):
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    src = LoopSimSource(clip, camera_fps=30.0, phase_s=0.0, reopen_s=1.0, **QUIET)
    src.open()
    s0 = [src.read().meta["loopsim"]["s"] for _ in range(3)]
    src.close()
    src.open()
    s1 = [src.read().meta["loopsim"]["s"] for _ in range(3)]
    frame = 1 / 30.0
    assert s1[0] >= s0[-1] + 1.0 and s1[0] < s0[-1] + 1.0 + frame
    d = abs((s1[0] - s0[0]) / frame) % 1.0
    assert min(d, 1 - d) > 1e-3                      # a different phase within the frame period
    # In real time the camera's frame clock starts when it is opened (plus a fixed delay).
    clock = FakeClock(50.0)
    rt = LoopSimSource(clip, camera_fps=30.0, phase_s=0.25, realtime=True, clock=clock, epoch=50.0, **QUIET)
    rt.open()
    assert rt.info["grid0_s"] == pytest.approx(0.25)
    rt.close()
    clock.advance(3.0123)
    rt.open()
    assert rt.info["grid0_s"] == pytest.approx(3.2623)


def test_faults_follow_their_own_clock(tmp_path):
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    clock = FakeClock(100.0)
    script = FaultScript([("disconnect", 1.0, 2.0), ("stall", 3.0, 4.0), ("freeze", 5.0, 6.0)])
    src = LoopSimSource(clip, faults=script, clock=clock, epoch=100.0, **QUIET)
    src.open()
    f0 = src.read()
    assert f0 is not None and f0.index == 0
    clock.advance(1.5)
    with pytest.raises(SourceError):
        src.read()
    with pytest.raises(SourceError):
        LoopSimSource(clip, faults=script, clock=clock, epoch=100.0, **QUIET).open()   # a reconnect fails too
    clock.advance(2.0)                                  # t = 3.5: stall
    assert src.read() is None
    clock.advance(1.0)                                  # t = 4.5: running again
    f1 = src.read()
    clock.advance(1.0)                                  # t = 5.5: frozen on the last frame
    f2 = src.read()
    assert f2.meta.get("frozen") and np.array_equal(f2.image, f1.image) and f2.index > f1.index


def test_pause_holds_the_picture_then_plays_on(tmp_path):
    clip = _levels_clip(tmp_path / "lv_hold2.mp4")
    kw = dict(camera_fps=30.0, phase_s=0.0, exp_s=1 / 120, **QUIET)
    plain = LoopSimSource(clip, **kw)
    src = LoopSimSource(clip, faults=FaultScript([("pause", 0.31, 0.72)]), **kw)
    plain.open()
    src.open()
    assert src._pauses == [(19 / 60, 44 / 60)]           # moved to panel refreshes
    frames = [src.read() for _ in range(30)]
    ref = [plain.read() for _ in range(30)]
    truth = [f.meta["loopsim"] for f in frames]
    for f, g in zip(frames[:10], ref[:10]):             # before the pause: the same camera frames
        assert np.array_equal(f.image, g.image) and f.meta["loopsim"] == g.meta["loopsim"]
    held = [k for k, tr in enumerate(truth) if tr["paused"]]
    assert held == list(range(10, 22))                  # s = 1/3 .. 0.7 (mid-exposure inside the window)
    # The panel holds the video frame shown when the pause began; no noise here, so the picture repeats exactly.
    assert {truth[k]["video_index"] for k in held} == {truth[9]["video_index"]}
    assert all(truth[k]["sources"] == truth[9]["sources"] for k in held)
    assert all(np.array_equal(frames[k].image, frames[9].image) for k in held)
    # Then it plays on from where it stopped, one video frame per camera frame again.
    after = [tr["video_index"] for tr in truth[23:]]
    assert after[0] == truth[9]["video_index"] + 1 and np.all(np.diff(after) == 1)
    for tr in truth:                                    # weights still add up to 1 everywhere
        w = src._weights(tr["s"])
        assert np.allclose(sum(np.broadcast_to(v, (90, 160)) for v in w.values()), 1.0, atol=1e-6)


@pytest.mark.qt
def test_build_options_offers_loopsim_sources(tmp_path):
    from wfglink.ui.booth_app import build_options

    cfg = load_config()
    path = str(tmp_path / "clip_hold2.mp4")
    assert [o.key for o in build_options(cfg, f"loopsim:{path}")] == ["loopsim", "synthetic"]
    opts = build_options(cfg, f"loopsim-unplug:{path}")
    assert [o.key for o in opts] == ["loopsim", "replay", "synthetic"]
    assert [o.live for o in opts] == [True, False, False]
    chained = build_options({**cfg, "camera": {**cfg["camera"], "chain": [f"loopsim-unplug:{path}"]}}, "auto")
    assert [o.key for o in chained] == ["loopsim", "synthetic"]
    paused = build_options({**cfg, "booth": {**cfg["booth"], "sim_pause_s": [2, 4]}}, f"loopsim-pause:{path}")
    assert [o.key for o in paused] == ["loopsim", "replay", "synthetic"]
    sim = paused[0].factory()
    assert sim._pauses == [(2.0, 4.0)] and sim.realtime


# Paused or absent iPad: booth status, screen check, and the chain ------------------------------

@pytest.fixture(scope="module")
def small_booth(tmp_path_factory):
    """A 640x360 clip of 40 source frames prepared at hold 2 (a 2.7 s loop on the iPad)."""
    from wfglink.io.synthetic_live import SyntheticLiveSource

    d = tmp_path_factory.mktemp("pause")
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=5)
    src.open()
    with av.open(str(d / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        s.options = {"crf": "18", "preset": "veryfast"}
        for _ in range(40):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    prepare(d / "clip.mp4", d / "booth", holds=(2,))
    return d / "booth"


def _booth_cfg(booth: Path, **capture) -> dict:
    return load_config(overrides={"booth": {"replay_clip": str(booth / "clip_hold2.mp4")}, "capture": capture})


@pytest.mark.qt
def test_paused_and_absent_screen_status_and_camera_health(small_booth):
    """Pipeline booth status, the capture thread's screen check and camera health, frame by frame.

    The simulated iPad pauses from 1.0 to 2.6 s on the panel clock; from 4.0 s the camera
    films the black cloth instead of the iPad. Frame wall times are the panel clock (plus an
    offset, because a wall time of 0 means unset), so the test does not depend on how fast
    this machine renders.
    """
    from wfglink.io.capture import ChainConfig, CaptureWorker, SourceOption
    from wfglink.ui.booth_app import load_booth_meta, make_booth_context, screen_check_factory

    freeze = 0.8
    cfg = _booth_cfg(small_booth, freeze_s=freeze)
    meta = load_booth_meta(cfg)
    assert meta is not None
    pipe = Pipeline(cfg, booth=make_booth_context(meta, cfg), downscale=True)
    make = screen_check_factory(meta, cfg)
    assert make(SourceOption("replay", lambda: None, False)) is None      # replay and synthetic are never checked
    cam = CaptureWorker(SourceOption("loopsim", lambda: None, True), make(SourceOption("loopsim", lambda: None, True)))
    src = LoopSimSource(small_booth / "clip_hold2.mp4", size=(960, 540), camera_fps=29.0, exp_s=1 / 250, phase_s=0.0,
                        faults=FaultScript([("pause", 1.0, 2.6)]))
    src.open()
    ccfg = ChainConfig.from_config(cfg)
    t0 = 1000.0
    cam.opened.set()
    cam.t_open = cam.t_last_change = cam.t_last_hook_ok = t0
    rows = []
    for _ in range(int(5.2 * 29)):
        f = src.read()
        s = f.meta["loopsim"]["s"]
        now = f.t_wall = t0 + s
        if s >= 4.0:
            f.image = np.full_like(f.image, 6)
        pipe.process(f)
        cam._observe(f, now)                              # what the capture thread does with every frame
        cam.t_last_frame, cam.frames = now, cam.frames + 1
        rows.append((s, f.meta["loopsim"]["paused"], pipe.screen_status(now), cam.health(ccfg, now)))

    def window(t0, t1):
        return [r for r in rows if t0 <= r[0] < t1]

    for s, paused, st, (ok, why) in window(0.0, 1.0):     # playing
        assert st == "ok" and ok, (s, st, why)
    assert cam.confirmed
    for s, paused, st, (ok, why) in window(1.0, 1.0 + freeze):
        assert st == "ok" and paused                      # frames still arrive; not yet freeze_s
    for s, paused, st, (ok, why) in window(1.0 + freeze + 0.15, 2.6):
        assert st == "paused", (s, st)
    for s, paused, st, (ok, why) in window(1.0 + freeze + 0.5, 2.6):
        assert not ok and why == "screen paused", (s, why)
    for s, paused, st, (ok, why) in window(2.8, 4.0):     # playing again
        assert st == "ok" and ok, (s, st, why)
    for s, paused, st, (ok, why) in window(4.0 + freeze + 0.15, 9.0):
        assert st == "no_screen", (s, st)
    for s, paused, st, (ok, why) in window(4.0 + freeze + 0.5, 9.0):
        assert not ok and why == "no screen markers", (s, why)
    assert not any(st == "paused" for s, _, st, _ in window(3.5, 9.0))   # turning away is never "paused"
    assert pipe.stats.frames_analysed > 30


@pytest.mark.slow
@pytest.mark.qt
def test_chain_falls_back_when_the_ipad_pauses_and_comes_back(small_booth):
    """Real time: the iPad pauses from 1.5 to 3.5 s; the camera fails its screen check, labelled
    replay takes over (with the note), and the camera returns once the iPad plays again."""
    from wfglink.io.capture import ChainConfig, SourceChain, SourceOption
    from wfglink.io.sources import FileSource
    from wfglink.ui.booth_app import load_booth_meta, screen_check_factory, screen_note

    clip = small_booth / "clip_hold2.mp4"
    cfg = _booth_cfg(small_booth, stale_s=0.5, freeze_s=0.8, backoff_min_s=0.1, backoff_max_s=0.4,
                     switch_back_s=0.8, probe_every_s=0.3, open_timeout_s=3.0)
    meta = load_booth_meta(cfg)
    epoch = time.monotonic()
    faults = FaultScript([("pause", 1.5, 3.5)])
    opts = [SourceOption("loopsim", lambda: LoopSimSource(clip, size=(960, 540), camera_fps=29.0, exp_s=1 / 250,
                                                          faults=faults, epoch=epoch, realtime=True), True, "sim"),
            SourceOption("replay", lambda: FileSource(clip, loop=True, realtime=True), False, "replay")]
    chain = SourceChain(opts, ChainConfig.from_config(cfg), hook_factory=screen_check_factory(meta, cfg))
    chain.start()
    notes = set()
    try:
        while time.monotonic() - epoch < 7.0:
            f, st = chain.latest()
            if st.key == "replay":
                notes.add(screen_note(chain, st.key))
            if st.key == "loopsim" and time.monotonic() - epoch > 4.0 and len(chain.events) > 2:
                break
            time.sleep(0.02)
    finally:
        chain.stop()
    ev = [(e["t"] - epoch, e["event"], e.get("key"), e.get("reason", "")) for e in chain.events]
    fails = [e for e in ev if e[1] == "failed"]
    assert fails and all(e[2] == "loopsim" and e[3] == "screen paused" for e in fails), ev
    # freeze_s after the last pass: the first check that read the held code, which can come up to
    # one source frame (1/15 s at hold 2) before the pause began
    assert 1.5 + 0.8 - 0.1 <= fails[0][0] < 1.5 + 0.8 + 1.0, ev
    fallback = next(e for e in ev if e[1] == "activated" and e[2] == "replay")
    assert fallback[0] >= fails[0][0]
    back = [e for e in ev if e[1] == "activated" and e[2] == "loopsim" and e[0] > fallback[0]]
    assert back and back[0][0] > 3.5 + 0.8, ev                            # after the resume and switch_back_s
    assert "switched back" in back[0][3]
    assert notes == {"paused"}


# The frame-code reader against the light at its cells ---------------------------------------

def _prepared(d: Path, n: int, seed: int = 7) -> Path:
    from wfglink.io.synthetic_live import SyntheticLiveSource

    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=seed)
    src.open()
    with av.open(str(d / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for _ in range(n):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    prepare(d / "clip.mp4", d / "booth", holds=(2, 3))
    return d / "booth"


@pytest.fixture(scope="module")
def small_booth(tmp_path_factory):
    return _prepared(tmp_path_factory.mktemp("loopsim_small"), 24)


def test_code_truth_matches_the_reader(small_booth):
    # truth["code"] puts the integrated light at each code cell through the reader itself;
    # on the rendered camera frame (optics, warp, noise) the reader must report the same,
    # except for cells within a few percent of its gray-band limits.
    meta = json.loads((small_booth / "clip_booth.json").read_text())
    lay = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})
    checked = picture_torn = code_torn = 0
    for kw in (dict(scan="right", exp_s=1 / 60, readout_s=0.012, response_s=0.005),
               dict(scan="up", exp_s=0.004, readout_s=0.02)):
        src = LoopSimSource(small_booth / "clip_hold2.mp4", camera_fps=29.0, size=(960, 540), seed=2, **kw)
        src.open()
        rect = ScreenRectifier(lay, 640)
        for _ in range(36):
            f = src.read()
            truth = f.meta["loopsim"]
            code = rect.process(f.image).code
            picture_torn += truth["torn"]
            code_torn += truth["code"]["torn"]
            if code is None or truth["code"]["margin"] < 0.06:
                continue
            exp = truth["code"]
            assert (code.clean, code.blended, code.torn) == (exp["clean"], exp["blended"], exp["torn"]), (truth, code)
            if exp["clean"]:
                assert code.index == exp["index"]
            checked += 1
    assert checked >= 40
    # The whole-picture flag counts every frame in which the scan crossed the picture.
    assert picture_torn > code_torn


# Through the booth pipeline (slow) -------------------------------------------------------------

@dataclass
class Run:
    stats: dict
    codes: list = field(default_factory=list)
    truths: list = field(default_factory=list)
    analysed: list = field(default_factory=list)     # (loop, source index) of every analysed frame

    @property
    def dominant(self) -> list[int]:
        return [max(t["sources"], key=t["sources"].get) for t in self.truths]

    def coverage(self) -> float:
        shown = set(self.dominant)
        return len(shown & {i for _, i in self.analysed}) / len(shown)


@pytest.fixture(scope="module")
def booth_clip(tmp_path_factory):
    from wfglink.io.synthetic_live import SyntheticLiveSource

    d = tmp_path_factory.mktemp("loopsim")
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=7)
    src.open()
    with av.open(str(d / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 640, 360, "yuv420p"
        for _ in range(90):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    prepare(d / "clip.mp4", d / "booth", holds=(2, 3))
    return d / "booth"


_RUNS: dict = {}


def run_loop(booth: Path, hold: int, n: int, **kw) -> Run:
    key = (str(booth), hold, n, tuple(sorted(kw.items())))
    if key in _RUNS:
        return _RUNS[key]
    meta = json.loads((booth / "clip_booth.json").read_text())
    lay = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})
    ctx = BoothContext(ScreenRectifier(lay, 960), load_sidecar(booth / "clip_codes.csv"))
    pipe = Pipeline(load_config(), booth=ctx)
    run = Run(stats={})
    rect = ctx.rectifier.process

    def rect_spy(img):
        r = rect(img)
        run.codes.append(r.code)
        return r

    ctx.rectifier.process = rect_spy
    prep = pipe._prepare

    def prep_spy(frame):
        out = prep(frame)
        if out[0] is not None:
            run.analysed.append((pipe.stats.loops, out[3]["source_index"]))
        return out

    pipe._prepare = prep_spy
    src = LoopSimSource(booth / f"clip_hold{hold}.mp4", **kw)
    src.open()
    for _ in range(n):
        f = src.read()
        run.truths.append(f.meta["loopsim"])
        pipe.process(f)
    run.stats = pipe.stats.as_dict()
    _RUNS[key] = run
    return run


def _no_wrong_frames(run: Run) -> None:
    """Every clean frame decodes to the source frame that dominated the exposure."""
    for code, dom in zip(run.codes, run.dominant):
        if code is not None and code.clean:
            assert code.index == dom


SHORT = dict(exp_s=1 / 250, camera_fps=29.0)


@pytest.mark.slow
def test_a_hold2_short_exposure_yield(booth_clip):
    # A phone camera whose rolling shutter runs the same way as the panel scan (both top to
    # bottom) follows the scan line, so almost every short exposure is clean.
    phone = run_loop(booth_clip, 2, 150, readout_s=0.016, **SHORT)
    assert phone.stats["clean_frame_yield"] >= 0.8, phone.stats
    # A global shutter cannot follow the scan: an exposure taken while the panel writes new
    # content shows new rows above the scan line and old rows below it. That costs about
    # 12 ms of every 67 ms content period at hold 2 (yield near 0.78), yet every source frame
    # is still captured cleanly at least once, because two camera frames see each one.
    glob = run_loop(booth_clip, 2, 150, **SHORT)
    assert 0.70 <= glob.stats["clean_frame_yield"] < 0.86, glob.stats
    assert glob.stats["frames_torn"] > 0
    for r in (phone, glob):
        assert r.coverage() >= 0.97
        assert r.stats["frames_no_code"] <= 1
        _no_wrong_frames(r)


@pytest.mark.slow
def test_b_long_exposure_lowers_the_yield_through_blends(booth_clip):
    short = run_loop(booth_clip, 2, 150, **SHORT)
    long = run_loop(booth_clip, 2, 150, exp_s=1 / 30, camera_fps=29.0)
    n = long.stats["frames_in"]
    assert long.stats["clean_frame_yield"] < short.stats["clean_frame_yield"] - 0.1, (short.stats, long.stats)
    assert long.stats["frames_blended"] >= 0.25 * n
    assert long.stats["frames_blended"] > 2 * short.stats["frames_blended"]
    assert sum(t["mixed"] for t in long.truths) > 0.6 * n
    _no_wrong_frames(long)


@pytest.mark.slow
def test_c_rolling_shutter_tears_are_flagged(booth_clip):
    # A panel that switches all at once (scan_s = 0) isolates the camera: a global shutter
    # never tears, a 30 ms rolling readout does, and the code reader flags exactly those.
    glob = run_loop(booth_clip, 2, 120, scan_s=0.0, **SHORT)
    roll = run_loop(booth_clip, 2, 120, scan_s=0.0, readout_s=0.030, **SHORT)
    assert glob.stats["frames_torn"] == 0 and not any(t["torn"] for t in glob.truths)
    n = roll.stats["frames_in"]
    assert roll.stats["frames_torn"] >= 0.1 * n, roll.stats
    for code, truth in zip(roll.codes, roll.truths):
        if code is not None and code.torn:
            assert truth["torn"]                      # no false tears
        if not truth["torn"] and not truth["mixed"]:
            assert code is not None and code.clean    # untouched frames stay clean
    _no_wrong_frames(roll)


@pytest.mark.slow
def test_d_analysed_indices_increase_strictly_within_a_loop(booth_clip):
    run = run_loop(booth_clip, 2, 230, camera_fps=29.0)   # 7.9 s of camera time over a 6 s loop
    assert run.stats["loops"] == 1
    by_loop: dict[int, list[int]] = {}
    for loop, idx in run.analysed:
        by_loop.setdefault(loop, []).append(idx)
    assert set(by_loop) == {0, 1}
    for idx in by_loop.values():
        assert all(b > a for a, b in zip(idx, idx[1:])), idx      # no repeats, never backwards
    assert run.stats["frames_analysed"] == len(run.analysed)
    assert run.coverage() >= 0.97
    _no_wrong_frames(run)


@pytest.mark.slow
def test_e_hold2_coverage_holds_at_every_phase_but_the_yield_does_not(booth_clip):
    # The sitting 2 hold rule on simulated cameras, each window a camera restart (a new phase).
    # Global shutter: at hold 2 every window covers every source frame, while the yield of a
    # window is close to 0.5 or to 1.0 depending on its phase. A long exposure with a rolling
    # shutter across a sideways panel scan leaves no spare clean view at hold 2, so hold 3 wins.
    from wfglink.sitting.sitting2 import choose_hold_coverage, coverage_ok, coverage_summary, measure_windows

    meta = json.loads((booth_clip / "clip_booth.json").read_text())
    lay = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})

    def windows(hold: int, **kw) -> dict:
        src = LoopSimSource(booth_clip / f"clip_hold{hold}.mp4", size=(960, 540), seed=4, **kw)
        wins = measure_windows(lambda: src, ScreenRectifier(lay, 640), 8, 1.2, fps=30.0, pause_s=0.0,
                               clock=lambda: 0.0)
        assert all(w["dropped"] == 0 for w in wins)
        return coverage_summary(wins)

    good = windows(2, exp_s=0.008)
    assert good["windows_used"] == 8 and good["coverage_worst"] >= 0.98, good
    assert good["spare_windows"] >= 1 and coverage_ok(good, 0.98)
    assert good["yield_min"] < 0.65 and good["yield_max"] > 0.9, good
    bad2 = windows(2, scan="right", exp_s=0.033, readout_s=0.02, response_s=0.005)
    bad3 = windows(3, scan="right", exp_s=0.033, readout_s=0.02, response_s=0.005)
    assert bad2["spare_windows"] == 0 and not coverage_ok(bad2, 0.98), bad2
    assert coverage_ok(bad3, 0.98), bad3
    assert choose_hold_coverage(good, None, 0.98)["hold_factor"] == 2
    assert choose_hold_coverage(bad2, bad3, 0.98)["hold_factor"] == 3
