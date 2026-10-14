"""Pipeline: direct mode on the synthetic source, booth mode through codes and a filmed screen."""
import av
import cv2
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.io.frames import Frame
from wfglink.io.sources import FileSource
from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.pipeline import BoothContext, Pipeline
from wfglink.screen.booth_prep import load_sidecar, prepare
from wfglink.screen.codes import Layout
from wfglink.screen.rectify import ScreenRectifier


def test_direct_mode_on_synthetic_source():
    cfg = load_config()
    src = SyntheticLiveSource(width=960, height=540, realtime=False, seed=3)
    src.open()
    pipe = Pipeline(cfg, fps=30)
    st = None
    for _ in range(150):
        st = pipe.process(src.read())
    assert pipe.stats.frames_analysed == 150
    assert st.warm == 1.0
    assert st.cpc_gross is not None and st.cpc_gross > 0
    assert st.count_rate is not None and np.isfinite(st.count_rate)
    assert st.speed is not None and 20 < st.speed < 1000
    assert len(st.trails) > 3
    assert (st.field_uvn[..., 2] > 0).any()
    assert np.isfinite(st.sparkline).sum() >= 4


def test_repeated_frames_are_skipped():
    cfg = load_config()
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=5)
    src.open()
    pipe = Pipeline(cfg)
    for i in range(40):
        f = src.read()
        pipe.process(f)
        if i % 4 == 0:  # a repeated frame with a later timestamp (constant-frame-rate re-encode)
            pipe.process(Frame(f.image.copy(), f.t + 0.001, f.index, f.t_wall))
    assert pipe.stats.frames_duplicate == 10
    assert pipe.stats.frames_analysed == 40


@pytest.mark.slow
def test_booth_mode_through_a_filmed_screen(tmp_path):
    cfg = load_config()
    src = SyntheticLiveSource(width=960, height=540, realtime=False, seed=7)
    src.open()
    with av.open(str(tmp_path / "clip.mp4"), "w") as c:
        s = c.add_stream("libx264", rate=30)
        s.width, s.height, s.pix_fmt = 960, 540, "yuv420p"
        for _ in range(60):
            for p in s.encode(av.VideoFrame.from_ndarray(src.read().image, format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    meta = prepare(tmp_path / "clip.mp4", tmp_path / "booth", holds=(2,))
    lay = Layout(**{k: meta["layout"][k] for k in ("width", "height", "marker", "cell", "margin")})
    ctx = BoothContext(ScreenRectifier(lay, 960), load_sidecar(tmp_path / "booth" / "clip_codes.csv"))
    pipe = Pipeline(cfg, booth=ctx)
    quad = np.float32([[300, 160], [1620, 200], [1590, 920], [330, 880]])
    H = cv2.getPerspectiveTransform(np.float32([[0, 0], [959, 0], [959, 539], [0, 539]]), quad)
    rng = np.random.default_rng(0)
    prepared = FileSource(tmp_path / "booth" / "clip_hold2.mp4")
    prepared.open()
    frames = []
    while (f := prepared.read()) is not None:
        frames.append(f.image)
    prepared.close()
    n_cam = 0
    st = None
    for loop in range(2):
        prev = None
        for img in frames:
            cam = cv2.warpPerspective(img, H, (1920, 1080), flags=cv2.INTER_AREA)
            if prev is not None and n_cam % 7 == 3:   # a blended capture across a frame change
                cam = cv2.addWeighted(cam, 0.5, prev, 0.5, 0)
            prev = cv2.warpPerspective(img, H, (1920, 1080), flags=cv2.INTER_AREA)
            cam = np.clip(cam + rng.normal(0, 2, cam.shape), 0, 255).astype(np.uint8)
            st = pipe.process(Frame(cam, n_cam / 30, n_cam, 0.0))
            n_cam += 1
    s = pipe.stats
    assert s.loops == 1                                  # the replay looped once
    assert s.frames_blended > 0 and s.frames_unclean >= s.frames_blended
    assert s.frames_analysed + s.frames_duplicate + s.frames_unclean + s.frames_no_code == n_cam
    # Statistics run across loops: every source frame is analysed at most once per loop.
    assert s.frames_analysed <= 2 * 60
    assert s.frames_analysed > 2 * 40
    assert st.image is not None


def test_small_embers_on_a_static_night_scene_are_not_duplicates():
    cfg = load_config()
    pipe = Pipeline(cfg, fps=30)
    for i in range(30):
        img = np.full((360, 640, 3), 18, np.uint8)
        for k in range(3):                       # three small embers moving 4 px per frame
            x, y = 100 + 150 * k + 4 * i, 100 + 60 * k
            cv2.circle(img, (x, y), 1, (60, 160, 255), -1)
        pipe.process(Frame(img, i / 30, i, 0.0))
    assert pipe.stats.frames_duplicate == 0
