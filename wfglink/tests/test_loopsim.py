"""Camera-in-the-loop simulator: exact blend weights, scan tears, faults, and the booth path.

The slow tests film a small prepared clip (640x360, 3 s) through LoopSimSource and the
booth pipeline. They run the camera at 29 fps instead of the default 29.97 so its phase
sweeps the whole content period several times within a few seconds; at 29.97 the phase
moves 0.03 ms per frame and a short run measures one phase only (yields of 0.56 to 1.0
for the same settings, depending on the seed).
"""
import json
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
