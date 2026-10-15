"""Pipeline: direct mode on the synthetic source, repeated frames, cuts in the booth playlist."""
import cv2
import numpy as np

from wfglink.config import load_config
from wfglink.io.frames import Frame
from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.pipeline import HEARTBEAT_COUNTERS, Pipeline, heartbeat_counters


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


def test_a_cut_restarts_tracks_and_background_but_keeps_the_counts():
    cfg = load_config()
    src = SyntheticLiveSource(width=960, height=540, realtime=False, seed=3)
    src.open()
    pipe = Pipeline(cfg, fps=30)
    for _ in range(150):
        f = src.read()
        pipe.process(f)
    cpc = pipe.counter.counts()["gross"]
    finished = pipe.stats.tracks_finished
    assert cpc > 0 and pipe.tracker.active_tracks()
    pipe.cut()
    assert not pipe.tracker.active_tracks() and not pipe.detector.ready
    assert pipe.stats.tracks_finished > finished          # the open tracks were finished, not lost
    other = SyntheticLiveSource(width=960, height=540, realtime=False, seed=9)
    other.open()
    for _ in range(30):
        g = other.read()
        st = pipe.process(Frame(g.image, f.t + 1.0 + g.t, g.index, 0.0))   # the next shot, later in time
    assert pipe.counter.counts()["gross"] >= cpc and st.cpc_gross >= cpc
    assert pipe.stats.frames_analysed == 180


def test_heartbeat_counters_are_the_frame_counts_only():
    pipe = Pipeline(load_config())
    assert HEARTBEAT_COUNTERS == ("frames_in", "frames_analysed", "frames_duplicate")
    assert heartbeat_counters("C6", pipe.stats) == {"key": "C6", "frames_in": 0, "frames_analysed": 0, "frames_duplicate": 0}
    assert heartbeat_counters("C6", {"frames_in": 5}) == {"key": "C6", "frames_in": 5, "frames_analysed": 0,
                                                          "frames_duplicate": 0}
    assert heartbeat_counters(None, None) is None


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


def test_trails_are_drawn_from_the_last_sharp_reversal():
    from wfglink.pipeline import _smooth_tail

    zigzag = np.array([[0, 0], [10, 0], [0, 1], [10, 2], [20, 2], [30, 3]], float)
    assert np.allclose(_smooth_tail(zigzag), zigzag[2:])
    smooth = np.array([[0, 0], [1, 0], [2, 0.1], [3, 0.3]])
    assert len(_smooth_tail(smooth)) == 4


def test_lossy_repeats_are_recognised_by_the_embers_not_moving():
    """A repeated frame stored by a lossy re-encode differs slightly in many pixels, so the pixel
    test misses it; the content test sees that the moving embers did not move."""
    cfg = load_config()
    src = SyntheticLiveSource(width=640, height=360, realtime=False, seed=11)
    src.open()
    pipe = Pipeline(cfg, fps=30)
    rng = np.random.default_rng(0)
    repeats = 0
    for i in range(60):
        f = src.read()
        pipe.process(f)
        if i >= 20 and i % 5 == 0:
            noisy = np.clip(f.image.astype(np.int16) + rng.integers(-4, 5, f.image.shape), 0, 255).astype(np.uint8)
            before = pipe.stats.frames_duplicate
            pipe.process(Frame(noisy, f.t + 1 / 60, f.index, f.t_wall))
            repeats += 1
            assert pipe.stats.frames_duplicate == before + 1, i
    assert pipe.stats.frames_analysed == 60
