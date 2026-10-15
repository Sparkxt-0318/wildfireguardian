"""Multi-scale detection (detect/multiscale.py): levels, source-pixel positions, merge by size."""
import cv2
import numpy as np

from wfglink.config import load_config
from wfglink.detect.candidates import Detections, Detector
from wfglink.detect.multiscale import MultiScaleDetector, downscale, level_factors, merge_levels, to_source
from wfglink.io.frames import Frame
from wfglink.pipeline import Pipeline


def _blob(img, x, y, amp, sigma):
    r = int(np.ceil(5 * sigma)) + 1
    x0, y0 = int(x) - r, int(y) - r
    yy, xx = np.mgrid[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1]
    img[y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1] += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))


def _ember(img, x, y, sigma, length, peak, angle=0.6, n=80):
    """A blob (length 0) or a streak of `length` px along `angle`, about `peak` DN on its axis."""
    if length <= 0:
        _blob(img, x, y, peak, sigma)
        return
    amp = peak * (length / n) / (sigma * np.sqrt(2 * np.pi))
    for s in (np.arange(n) + 0.5) / n - 0.5:
        _blob(img, x + s * length * np.cos(angle), y + s * length * np.sin(angle), amp, sigma)


def _frames(shape, n, embers, seed=0, noise=2.0, base=30.0):
    """n noisy grey frames; the embers (x, y, sigma, length, peak) appear in the last one."""
    rng = np.random.default_rng(seed)
    for i in range(n):
        lum = base + rng.normal(0, noise, shape).astype(np.float32)
        if i == n - 1:
            for e in embers:
                _ember(lum, *e)
        yield cv2.cvtColor(np.clip(lum, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def test_levels_depend_on_the_frame_size_only():
    cfg = load_config()
    assert level_factors((720, 1280), cfg) == []          # the 720p suites and the booth: one scale
    assert level_factors((360, 540), cfg) == []
    assert level_factors((1440, 2560), cfg) == [2, 4]
    assert level_factors((2160, 1920), cfg) == [2, 4]     # C5's left half of a 4K frame
    assert level_factors((2160, 3840), cfg) == [2, 4]
    one = load_config(overrides={"detect": {"multiscale": {"max_octaves": 1}}})
    assert level_factors((2160, 3840), one) == [2]
    off = load_config(overrides={"detect": {"multiscale": {"enabled": False}}})
    assert level_factors((2160, 3840), off) == []


def test_coarse_pixel_centres_map_to_source_pixels():
    img = np.zeros((64, 64), np.uint8)
    img[20:24, 36:40] = 200                               # a 4 x 4 square centred on (37.5, 21.5)
    for f in (2, 4):
        small = downscale(img, f)
        ys, xs = np.nonzero(small)
        w = small[ys, xs].astype(float)
        det = Detections(x=np.array([np.sum(w * xs) / w.sum()]), y=np.array([np.sum(w * ys) / w.sum()]),
                         area=np.ones(1), peak=np.ones(1), flux=np.ones(1), lam1=np.ones(1), lam2=np.ones(1),
                         theta=np.zeros(1), length=np.ones(1), width=np.ones(1), sat_frac=np.zeros(1),
                         color=np.zeros(1), flags=np.zeros(1, np.uint8))
        src = to_source(det, f)
        assert abs(src.x[0] - 37.5) < 1e-9 and abs(src.y[0] - 21.5) < 1e-9
        assert src.scale[0] == f and src.length[0] == f and src.lam2[0] == f * f


def test_known_embers_in_a_4k_frame_are_reported_at_their_source_positions():
    """A far ember (native), two near streaks (half and quarter scale) and one in between,
    which the native detector still measures whole: each is one detection in the recorded
    table, within 0.5 px of its source position."""
    shape = (2160, 3840)
    truth = [(2500.7, 1500.2, 1.0, 0.0, 60.0, 1.0),       # x, y, sigma, length, peak, expected scale
             (1234.3, 987.6, 4.0, 40.0, 60.0, 2.0),
             (600.2, 400.9, 5.0, 60.0, 50.0, 4.0),
             (3000.4, 300.3, 2.5, 20.0, 40.0, 1.0)]
    pipe = Pipeline(load_config(), fps=30.0, record=True)
    for i, img in enumerate(_frames(shape, 8, [t[:5] for t in truth])):
        pipe.process(Frame(img, i / 30.0, i))
    det = pipe.tables()["detections"]
    last = det[det["frame"] == 7]
    for x, y, sigma, length, _, scale in truth:
        d = np.hypot(last["x"] - x, last["y"] - y).to_numpy()
        near = np.flatnonzero(d < 1.5 * length + 10)
        assert near.size == 1, (x, y, last.iloc[near])
        k = near[0]
        assert d[k] < 0.5
        assert last["scale"].iloc[k] == scale
        if length > 0:   # lengths in source px
            assert abs(last["length"].iloc[k] - length) < 0.2 * length


def test_large_embers_are_missed_at_one_scale_on_4k():
    """The reason for the coarse levels: the native detector loses a wide near streak."""
    shape = (1080, 1920)
    det = Detector(load_config())
    out = None
    for img in _frames(shape, 8, [(900.3, 500.6, 4.0, 40.0, 60.0)]):
        out = det.detect(img)
    assert not (np.hypot(out.x - 900.3, out.y - 500.6) < 20).any()


def test_frames_of_720p_are_detected_exactly_as_before():
    shape = (720, 1280)
    embers = [(300.2, 200.7, 1.2, 0.0, 40.0), (700.5, 400.1, 1.5, 15.0, 30.0), (1000.0, 600.0, 4.0, 40.0, 60.0)]
    ms, one = MultiScaleDetector(load_config()), Detector(load_config())
    a = b = None
    for img in _frames(shape, 8, embers, seed=3):
        a, b = ms.detect(img), one.detect(img)
    assert not ms.levels and len(a) == len(b) > 0
    for k, v in b.as_dict().items():
        np.testing.assert_array_equal(a.as_dict()[k], v)


def _dets(xy, theta=0.0, length=0.0):
    n = len(xy)
    z = np.zeros(n)
    xy = np.asarray(xy, float)
    return Detections(x=xy[:, 0], y=xy[:, 1], area=z + 5, peak=z + 50, flux=z + 100, lam1=z + 1, lam2=z + 1,
                      theta=z + theta, length=z + length, width=z + 4, sat_frac=z, color=z, flags=z.astype(np.uint8))


def test_merge_keeps_one_detection_per_ember_by_size():
    cfg = load_config()
    # Native: two pieces of a wide streak along x around (100, 100), and a far ember at (100, 130).
    fine = _dets([(85.0, 101.0), (116.0, 99.0), (100.0, 130.0)])
    # Coarse (source px): the wide streak (sigma 4, length 40), the far ember seen again (sigma 1),
    # and an ember found only at the coarse scale (sigma 1.5).
    coarse = _dets([(100.0, 100.0), (100.5, 129.6), (400.0, 300.0)], length=0.0)
    coarse.length[:] = [40.0, 0.0, 0.0]
    coarse.flux[0] = 2000.0                  # the native pieces hold a tenth of the streak's light
    coarse.scale[:] = 2.0
    sigma = np.array([4.0, 1.0, 1.5])
    out = merge_levels(fine, coarse, sigma, coarse.length, cfg, finer_factor=1)
    got = sorted(zip(out.x.round(1), out.y.round(1), out.scale))
    assert got == [(100.0, 100.0, 2.0), (100.0, 130.0, 1.0), (400.0, 300.0, 2.0)]
    # Found only at the coarse scale but point-like at the native scale: the native verdict stands.
    out = merge_levels(fine, coarse, np.array([4.0, 1.0, 0.5]), coarse.length, cfg, finer_factor=1)
    assert sorted(zip(out.x.round(1), out.y.round(1))) == [(100.0, 100.0), (100.0, 130.0)]
    # A quarter-scale detection defers to the half scale up to twice the native limit.
    out = merge_levels(coarse.subset(np.array([True, False, False])), _dets([(100.0, 100.0)]),
                       np.array([3.5]), np.array([40.0]), cfg, finer_factor=2)
    assert len(out) == 1 and out.scale[0] == 2.0


def test_finer_detections_that_hold_the_light_stand_against_a_merged_coarse_blob():
    """Two embers side by side merge at a coarse scale into one wide blob; the finer level
    measured each whole (together they hold its light), so both stay."""
    cfg = load_config()
    fine = _dets([(100.0, 96.0), (100.0, 106.0)])            # flux 100 each
    blob = _dets([(100.0, 101.0)])
    blob.flux[0], blob.scale[0] = 210.0, 4.0
    out = merge_levels(fine, blob, np.array([6.0]), np.array([0.0]), cfg, finer_factor=2)
    assert len(out) == 2 and set(out.scale) == {1.0}
    blob.flux[0] = 1000.0                                    # pieces of one large ember: replaced
    out = merge_levels(fine, blob, np.array([6.0]), np.array([0.0]), cfg, finer_factor=2)
    assert len(out) == 1 and out.scale[0] == 4.0


def test_a_missing_half_level_cannot_make_native_fragments_complete():
    """The quarter level matches only incomplete native pieces; no half-level
    measurement exists to justify applying its larger size cutoff to those pieces."""
    cfg = load_config()
    fine = _dets([(85.0, 101.0), (116.0, 99.0)])
    coarse = _dets([(100.0, 100.0)], length=40.0)
    coarse.flux[0], coarse.scale[0] = 2000.0, 4.0
    out = merge_levels(fine, coarse, np.array([3.5]), coarse.length, cfg, finer_factor=2)
    assert len(out) == 1 and out.scale[0] == 4.0
    # A real half-level measurement of the same light retains the higher-resolution result.
    fine = _dets([(100.0, 100.0)], length=40.0)
    fine.scale[0] = 2.0
    out = merge_levels(fine, coarse, np.array([3.5]), coarse.length, cfg, finer_factor=2)
    assert len(out) == 1 and out.scale[0] == 2.0


def test_scale_round_trip_keeps_measurement_units_and_flags():
    from wfglink.detect.multiscale import from_source

    native = _dets([(10.25, 20.75)], theta=0.7, length=13.0)
    native.flags[:] = 1
    for factor in (2, 4):
        source = to_source(native, factor)
        restored = from_source(source, factor)
        for name, value in native.as_dict().items():
            if name != "scale":
                np.testing.assert_array_equal(restored.as_dict()[name], value)
        assert source.flux[0] == native.flux[0] * factor ** 2
        assert source.area[0] == native.area[0] * factor ** 2
        assert source.width[0] == native.width[0] * factor


def test_coarse_frames_average_source_once_and_keep_ignored_and_clipped_pixels(monkeypatch):
    """Rounding twice changes factor-four input; clipping/ignore decisions must retain
    original pixels even when the colour average hides them."""
    cfg = load_config(overrides={"detect": {"multiscale": {"min_frame_pixels": 1, "min_level_pixels": 1}}})
    rng = np.random.default_rng(8)
    image = rng.integers(20, 31, (273, 481, 3), dtype=np.uint8)
    image[100, 100:102, 2] = 255    # two clipped source pixels within one quarter-scale sample
    mask = np.zeros(image.shape[:2], np.uint8)
    mask[101, 101] = 1             # a single ignored pixel must survive the block average
    seen = []

    def capture(self, img, msk=None, **kwargs):
        seen.append((img.copy(), None if msk is None else msk.copy(), kwargs))
        return Detections()

    monkeypatch.setattr(Detector, "detect", capture)
    ms = MultiScaleDetector(cfg)
    ms.detect(image, mask)
    assert len(seen) == 3
    for factor, (img, ignored, kw) in zip((2, 4), seen[1:]):
        np.testing.assert_array_equal(img, downscale(image, factor))
        assert ignored[101 // factor, 101 // factor]
        assert kw["saturation_counts"][100 // factor, 100 // factor] == 2
        assert kw["pixels_per_sample"] == factor ** 2
        assert img.max() < cfg["detect"]["saturation"]["level_dn"]


def test_detector_flags_source_clipping_hidden_by_averaging():
    from wfglink.detect.candidates import FLAG_SATURATED

    cfg = load_config()
    detector = Detector(cfg)
    out = Detections()
    # An ordinary coarse-level streak, with two clipped source pixels within one
    # coarse sample. Its averaged colour channels themselves never reach saturation.
    for i, image in enumerate(_frames((270, 480), 8, [(240.0, 135.0, 1.5, 18.0, 45.0)])):
        counts = np.zeros(image.shape[:2], np.float32)
        if i == 7:
            counts[135, 240] = 2
        out = detector.detect(image, saturation_counts=counts, pixels_per_sample=16)
    k = int(np.argmin(np.hypot(out.x - 240, out.y - 135)))
    assert out.flags[k] & FLAG_SATURATED
    assert out.sat_frac[k] * out.area[k] * 16 == 2
    assert image.max() < cfg["detect"]["saturation"]["level_dn"]


def test_reset_and_shape_changes_restart_every_background_and_noise_map():
    cfg = load_config(overrides={"detect": {"multiscale": {"min_frame_pixels": 1, "min_level_pixels": 1}}})
    ms = MultiScaleDetector(cfg)
    for image in _frames((270, 480), 8, []):
        ms.detect(image)
    assert ms.ready and all(d.ready for _, d in ms.levels)
    ms.reset()
    assert not ms.ready and not ms.counts
    assert all(not d.ready for _, d in ms.levels)
    for image in _frames((270, 480), 8, []):
        ms.detect(image)
    assert ms.ready
    changed = list(_frames((288, 512), 8, []))
    ms.detect(changed[0])
    assert not ms.ready and ms.native.state.luma is None
    for image in changed[1:]:
        ms.detect(image)
    assert ms.ready and ms.native.state.sigma.shape == (288, 512)
    assert all(d.state.sigma.shape == (288 // f, 512 // f) for f, d in ms.levels)


def test_file_repeat_is_decided_before_streak_refinement(monkeypatch):
    """Oriented-window refinement can move a centroid; it must not turn a repeated
    frame into a new observation or spend fitting time on a frame already rejected."""
    cfg = load_config(overrides={"detect": {"multiscale": {"enabled": False}}})
    pipe = Pipeline(cfg, record=True, fps=30.0)
    positions = np.array([[100.0, 100.0], [200.0, 150.0]])
    pipe._moving_last = positions.copy()
    monkeypatch.setattr(pipe.detector.native, "detect", lambda image, mask: _dets(positions))

    def unexpected_measurement(*args):
        raise AssertionError("a repeated frame reached streak refinement")

    monkeypatch.setattr("wfglink.detect.streaks.measure_streaks", unexpected_measurement)
    pipe.process(Frame(np.zeros((270, 480, 3), np.uint8), 0.0, 0))
    assert pipe.stats.frames_duplicate == 1 and pipe.stats.frames_analysed == 0
    assert pipe.tables()["detections"].empty


def test_live_large_frames_never_add_coarse_levels_or_streak_fits(monkeypatch):
    cfg = load_config()
    pipe = Pipeline(cfg, record=False, fps=30.0)

    def unexpected_measurement(*args):
        raise AssertionError("live mode reached streak refinement")

    monkeypatch.setattr("wfglink.detect.streaks.measure_streaks", unexpected_measurement)
    pipe.process(Frame(np.zeros((1080, 1920, 3), np.uint8), 0.0, 0))
    assert not pipe.detector.levels and not pipe.detector.refine


def test_streak_measurement_uses_each_levels_residual_and_pixel_coordinates(monkeypatch):
    from dataclasses import replace

    cfg = load_config()
    ms = MultiScaleDetector(cfg, refine=True)
    ms._setup((2160, 3840))
    for factor, detector in [(1, ms.native), *ms.levels]:
        detector.state.luma = np.zeros((2160 // factor, 3840 // factor), np.uint8)
    rows = [to_source(_dets([(20.25, 30.5)], length=8.0), factor) for factor in (1, 2, 4)]
    from wfglink.detect.multiscale import concat

    merged = concat(concat(rows[0], rows[1]), rows[2])
    calls = []

    def fit(det, state, config):
        calls.append(state.luma.shape)
        np.testing.assert_array_equal(det.x, [20.25])
        np.testing.assert_array_equal(det.y, [30.5])
        return replace(det, length=np.array([11.0]), width=np.array([3.0]))

    monkeypatch.setattr("wfglink.detect.streaks.measure_streaks", fit)
    measured = ms.measure(merged)
    assert calls == [(2160, 3840), (1080, 1920), (540, 960)]
    np.testing.assert_array_equal(measured.length, [11, 22, 44])
    np.testing.assert_array_equal(measured.width, [3, 6, 12])
    np.testing.assert_array_equal(measured.x, merged.x)
    np.testing.assert_array_equal(measured.scale, [1, 2, 4])
