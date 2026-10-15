"""Detector accuracy on rendered blobs and streaks with known geometry."""
import cv2
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.detect.candidates import FLAG_SATURATED, Detector


def _blob(img, x, y, amp, sigma=1.2):
    x0, y0 = int(x) - 8, int(y) - 8
    yy, xx = np.mgrid[y0:y0 + 17, x0:x0 + 17]
    img[y0:y0 + 17, x0:x0 + 17] += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))


def _streak(img, x0, y0, x1, y1, peak, n=40, sigma=1.2):
    """Uniform segment blurred by a Gaussian spot, with about `peak` DN along its axis."""
    length = np.hypot(x1 - x0, y1 - y0)
    amp = peak * (length / n) / (sigma * np.sqrt(2 * np.pi))
    for s in (np.arange(n) + 0.5) / n:
        _blob(img, x0 + (x1 - x0) * s, y0 + (y1 - y0) * s, amp, sigma)


def _run(frames_signal, shape=(360, 640), noise=2.0, base=30.0, extra=None, seed=0):
    rng = np.random.default_rng(seed)
    det = Detector(load_config())
    out = None
    for sig in frames_signal:
        lum = base + rng.normal(0, noise, shape) + sig + (extra if extra is not None else 0)
        out = det.detect(cv2.cvtColor(np.clip(lum, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR))
    return out


def _moving_scene(shape, n_frames, specs):
    """specs: list of (x0, y0, dx, dy, kind, size) with kind 'point' or 'streak' (size = length)."""
    frames = []
    for i in range(n_frames):
        sig = np.zeros(shape, np.float32)
        for x0, y0, dx, dy, kind, size in specs:
            x, y = x0 + dx * i, y0 + dy * i
            if kind == "point":
                _blob(sig, x, y, size)
            else:
                ang = np.arctan2(dy, dx)
                hx, hy = 0.5 * size * np.cos(ang), 0.5 * size * np.sin(ang)
                _streak(sig, x - hx, y - hy, x + hx, y + hy, 40.0)
        frames.append(sig)
    return frames


def test_positions_and_streak_lengths():
    shape = (360, 640)
    # Streak length never exceeds the per-frame displacement (exposure duty at most 1).
    specs = [(100, 100, 6, 0, "point", 100.0), (60, 200, 20, 0, "streak", 20.0),
             (400, 20, 0, 20, "streak", 10.0), (100, 30, 10, 10, "streak", 14.0)]
    frames = _moving_scene(shape, 16, specs)
    d = _run(frames, shape)
    assert len(d) == 4
    i = 15
    truth = [(x0 + dx * i, y0 + dy * i, size if kind == "streak" else 0.0) for x0, y0, dx, dy, kind, size in specs]
    for tx, ty, tl in truth:
        k = int(np.argmin(np.hypot(d.x - tx, d.y - ty)))
        assert np.hypot(d.x[k] - tx, d.y[k] - ty) < 0.5
        if tl > 0:
            assert abs(d.length[k] - tl) < 1.0
    horiz = int(np.argmin(np.hypot(d.x - truth[1][0], d.y - truth[1][1])))
    vert = int(np.argmin(np.hypot(d.x - truth[2][0], d.y - truth[2][1])))
    assert abs(np.degrees(d.theta[horiz])) < 4
    assert abs(abs(np.degrees(d.theta[vert])) - 90) < 4


def test_large_bright_region_is_excluded():
    shape = (360, 640)
    flame = np.zeros(shape, np.float32)
    cv2.circle(flame, (500, 180), 40, 150, -1)
    frames = _moving_scene(shape, 12, [(100, 100, 6, 0, "point", 100.0)])
    d = _run(frames, shape, extra=flame)
    assert len(d) == 1
    assert abs(d.x[0] - (100 + 6 * 11)) < 0.5


def test_pure_noise_gives_few_false_detections():
    shape = (360, 640)
    frames = [np.zeros(shape, np.float32)] * 30
    d = _run(frames, shape)
    assert len(d) <= 1


def test_global_exposure_step_does_not_flood():
    shape = (360, 640)
    frames = [np.zeros(shape, np.float32)] * 20 + [np.full(shape, 25.0, np.float32)]
    d = _run(frames, shape)
    assert len(d) <= 2


def test_saturated_blob_is_flagged():
    shape = (360, 640)
    frames = _moving_scene(shape, 10, [(100, 100, 6, 0, "point", 600.0)])
    d = _run(frames, shape)
    assert len(d) == 1
    assert d.flags[0] & FLAG_SATURATED


def test_clipped_red_channel_is_saturated_even_when_luma_is_not():
    det = Detector(load_config())
    rng = np.random.default_rng(2)
    d = None
    for i in range(10):
        img = np.clip(np.full((360, 640, 3), 20.0) + rng.normal(0, 2, (360, 640, 3)), 0, 255)
        if i == 9:
            img[200:204, 300:304] = (40, 160, 255)    # orange: red clipped, luma about 140
        d = det.detect(img.astype(np.uint8))
    assert len(d) == 1
    assert d.flags[0] & FLAG_SATURATED


def test_warm_color_score():
    shape = (360, 640)
    rng = np.random.default_rng(1)
    det = Detector(load_config())
    d = None
    for i in range(10):
        img = np.full(shape + (3,), 25, np.float32) + rng.normal(0, 2, shape + (3,))
        sig = np.zeros(shape, np.float32)
        _blob(sig, 100 + 6 * i, 100, 140, sigma=1.6)
        img[:, :, 2] += sig            # red
        img[:, :, 1] += 0.55 * sig     # some green: orange
        img[:, :, 0] += 0.1 * sig      # little blue
        d = det.detect(np.clip(img, 0, 255).astype(np.uint8))
    assert len(d) == 1
    assert d.color[0] > load_config()["detect"]["color"]["crcb_warm_min"]


@pytest.mark.parametrize("bad", [None])
def test_empty_frame_returns_empty(bad):
    det = Detector(load_config())
    assert len(det.detect(np.zeros((120, 160, 3), np.uint8))) == 0


# Mirror test (detect/mirror.py): compression error makes dark lobes as well as bright ones;
# embers make only bright ones.
def _h264(frames_bgr, crf, keyint=15):
    """Round trip through libx264 (one thread, fixed GOP: a keyframe every `keyint` frames)."""
    import io

    import av

    buf = io.BytesIO()
    c = av.open(buf, mode="w", format="mp4")
    s = c.add_stream("libx264", rate=30)
    s.width, s.height = frames_bgr[0].shape[1], frames_bgr[0].shape[0]
    s.pix_fmt = "yuv420p"
    s.options = {"crf": str(crf), "preset": "veryfast", "g": str(keyint), "keyint_min": str(keyint),
                 "sc_threshold": "0", "threads": "1"}
    for fr in frames_bgr:
        for p in s.encode(av.VideoFrame.from_ndarray(fr, format="bgr24")):
            c.mux(p)
    for p in s.encode():
        c.mux(p)
    c.close()
    buf.seek(0)
    d = av.open(buf)
    out = [f.to_ndarray(format="bgr24") for f in d.decode(video=0)]
    d.close()
    return out


def _detector(mirror: bool, **over):
    cfg = load_config()
    cfg["detect"]["mirror"] = {**cfg["detect"]["mirror"], "enabled": mirror, **over}
    return Detector(cfg)


def _track_ember(frames, xy, det, start):
    """Per analysed frame from `start` on: (ember found within 3 px, number of other detections)."""
    out = []
    for i, fr in enumerate(frames):
        d = det.detect(fr)
        if i < start:
            continue
        near = np.hypot(d.x - xy[i][0], d.y - xy[i][1]) <= 3 if len(d) else np.zeros(0, bool)
        out.append((bool(near.any()), len(d) - int(near.sum())))
    return out


def _textured_scene(h=240, w=320, seed=0):
    """A bright static scene with hard edges and fine texture, like a lit lab or street."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 120.0)
    for _ in range(40):
        x0, y0 = rng.integers(0, w - 20), rng.integers(0, h - 20)
        img[y0:y0 + rng.integers(8, 60), x0:x0 + rng.integers(8, 80)] = rng.uniform(40, 230)
    yy, xx = np.mgrid[0:h, 0:w]
    img += 25 * np.sin(xx / 2.3 + yy / 3.1) * (xx > w // 2)
    img += cv2.GaussianBlur(rng.normal(0, 40, (h, w)), (0, 0), 1.0) * (yy > h // 2)
    return np.clip(img, 0, 255)


def test_mirror_test_stops_quality_pumping_on_a_static_textured_scene():
    """H.264 with a keyframe every 15 frames re-quantises every edge at once: without the mirror
    test the detector floods at each keyframe and decays after it. With it the flood is gone,
    and a bright orange ember crossing the textured scene is still found."""
    rng = np.random.default_rng(1)
    base = _textured_scene()
    yy, xx = np.mgrid[0:base.shape[0], 0:base.shape[1]]
    frames, xy = [], []
    for i in range(46):
        bgr = cv2.cvtColor(np.clip(base + rng.normal(0, 1.0, base.shape), 0, 255).astype(np.uint8),
                           cv2.COLOR_GRAY2BGR).astype(np.float32)
        x, y = 20 + 6 * i, 60 + 2.5 * i
        g = np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.3 ** 2))
        bgr += g[..., None] * np.array([10.0, 60.0, 120.0])          # orange, about 70 DN of luma
        frames.append(np.clip(bgr, 0, 255).astype(np.uint8))
        xy.append((x, y))
    dec = _h264(frames, crf=28)
    off = _track_ember(dec, xy, _detector(False), 8)
    on = _track_ember(dec, xy, _detector(True), 8)
    fp_off = np.array([n for _, n in off])
    fp_on = np.array([n for _, n in on])
    assert fp_off.max() >= 30                       # the flood this test is about
    assert fp_on.max() <= 15
    assert fp_on.sum() <= 0.2 * fp_off.sum()
    found_off = sum(f for f, _ in off)
    found_on = sum(f for f, _ in on)
    assert found_on >= 0.85 * found_off and found_on >= 0.6 * len(on)


@pytest.mark.parametrize("compressed", [False, True])
def test_mirror_test_is_silent_on_sensor_noise_and_keeps_a_faint_ember(compressed):
    """A faint ember on a dark background with sensor noise, raw or through H.264: no block of
    the mirror test opens and the detections are exactly those without it."""
    rng = np.random.default_rng(3)
    h, w = 240, 320
    yy, xx = np.mgrid[0:h, 0:w]
    amp = 20.0 if compressed else 14.0
    frames, xy = [], []
    for i in range(40):
        x, y = 30 + 5 * i, 50 + 3 * i
        lum = 12 + rng.normal(0, 2.0, (h, w)) + amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.2 ** 2))
        frames.append(cv2.cvtColor(np.clip(lum, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR))
        xy.append((x, y))
    if compressed:
        frames = _h264(frames, crf=23)
    d_off, d_on = _detector(False), _detector(True)
    found = 0
    for i, fr in enumerate(frames):
        a, b = d_off.detect(fr), d_on.detect(fr)
        assert len(a) == len(b) and np.allclose(a.x, b.x) and np.allclose(a.y, b.y)
        if i >= 8:
            assert d_on.state.mirror_seed is None or not d_on.state.mirror_seed.any()
            found += bool(len(b) and (np.hypot(b.x - xy[i][0], b.y - xy[i][1]) <= 3).any())
    assert found >= 0.5 * (len(frames) - 8)


def test_mirror_test_ignores_an_overlay_that_vanished():
    """Bright strokes (a caption) that disappear leave strong dark structures in the residual
    until the background forgets them. They are a change of the scene, not compression error:
    above detect.mirror.cap_dn they are not counted and nearby embers are still found."""
    rng = np.random.default_rng(5)
    h, w = 240, 320
    yy, xx = np.mgrid[0:h, 0:w]
    frames, xy = [], []
    for i in range(40):
        lum = 25 + rng.normal(0, 1.0, (h, w))
        if i < 20:
            for k in range(12):
                x0 = 40 + 20 * k
                lum[100:130, x0:x0 + 3] = 220
                lum[100:103, x0:x0 + 12] = 220
        x, y = 30 + 6 * i, 85 + 1.0 * i
        lum = lum + 40 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.2 ** 2))
        frames.append(cv2.cvtColor(np.clip(lum, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR))
        xy.append((x, y))
    off = sum(f for f, _ in _track_ember(frames, xy, _detector(False), 20))
    on = sum(f for f, _ in _track_ember(frames, xy, _detector(True), 20))
    uncapped = sum(f for f, _ in _track_ember(frames, xy, _detector(True, cap_dn=255), 20))
    assert off >= 8 and on == off
    assert uncapped < on          # what the cap prevents: the vanished strokes would blind the test


def test_mirror_seed_levels_count_dark_lobes_per_neighbourhood():
    """Four dark lobes at the seed level in a 3 x 3 block neighbourhood set its seed level to
    ratio times the strongest; three do not; lobes below the seed level or above the cap do
    not count."""
    from wfglink.detect.mirror import MirrorTest

    cfg = load_config()
    cfg["detect"]["mirror"] = {"enabled": True, "block_px": 32, "count": 4, "ratio": 2.0, "cap_dn": 16}
    mt = MirrorTest(cfg)
    seed_thr = np.full((256, 256), 5, np.uint8)

    def neg_with(points):
        neg = np.zeros((256, 256), np.uint8)
        for x, y, v in points:
            neg[y:y + 2, x:x + 2] = v
        return neg

    four = [(40, 40, 6), (70, 40, 9), (40, 70, 7), (75, 75, 12)]        # in blocks (1, 1), (1, 2), (2, 1), (2, 2)
    seed, lobes = mt.seed_levels(neg_with(four), seed_thr)
    assert np.count_nonzero(lobes) == 4                                 # one pixel per lobe, wherever it falls
    assert (seed[1:3, 1:3] == 24).all()                                 # neighbourhoods holding all four: 2 x 12
    assert seed[0, 0] == 0 and seed[3, 3] == 0 and seed[6, 6] == 0     # holding fewer
    seed, _ = mt.seed_levels(neg_with(four[:3]), seed_thr)
    assert not seed.any()
    seed, _ = mt.seed_levels(neg_with(four[:3] + [(75, 75, 4)]), seed_thr)   # below the seed level
    assert not seed.any()
    seed, _ = mt.seed_levels(neg_with(four[:3] + [(75, 75, 40)]), seed_thr)  # above the cap: a scene change
    assert not seed.any()


def test_mirror_seed_level_never_exceeds_ratio_times_cap():
    """The mirror test never asks more than ratio x cap_dn of a seed, so an ember at least that
    bright passes it however much compression error surrounds it. A boolean mask works too, and
    the masked rows contribute no dark lobes."""
    from wfglink.detect.mirror import MirrorTest

    cfg = load_config()
    cfg["detect"]["mirror"] = {**cfg["detect"]["mirror"], "enabled": True}
    mt = MirrorTest(cfg)
    ceiling = int(np.ceil(mt.ratio * mt.cap))
    rng = np.random.default_rng(2)
    seed_thr = np.full((200, 300), 4, np.uint8)
    gy, gx = np.nonzero(np.ones((200, 300), bool))
    for spread in (3.0, 8.0, 30.0):     # at 30 DN nearly every lobe is above the cap and none counts
        neg = np.clip(rng.normal(0, spread, (200, 300)), 0, 255).astype(np.uint8)
        seed, lobes = mt.seed_levels(neg, seed_thr)
        assert (seed.any() or spread > mt.cap) and seed.max() <= ceiling and lobes.max() <= mt.cap
        assert mt.seed_ok(np.full(gy.size, ceiling, np.uint8), gy, gx, seed).all()
    det = Detector(cfg)
    mask = np.zeros((120, 160), bool)
    mask[:40] = True
    ran = False
    for i in range(12):
        img = np.clip(30 + rng.normal(0, 3, (120, 160, 3)), 0, 255).astype(np.uint8)
        img[70:73, 10 + 8 * i:13 + 8 * i] = 120       # something bright, so the seed test runs
        det.detect(img, mask)
        if det.state.dark_lobes is not None:
            ran = True
            assert not det.state.dark_lobes[:19].any()
    assert ran
