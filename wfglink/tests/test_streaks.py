"""File-mode streak length methods: the oriented-window moment refinement and the edge
(error function) profile fit. Both recover the ends of long, faint streaks that the threshold
cuts off; the fit also works on gamma-encoded luma."""
import copy

import cv2
import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.detect.candidates import Detector
from wfglink.detect.streaks import _along, _sample, erf_streaks, measure_streaks, refine_streaks, streak_method
from wfglink.io.frames import Frame
from wfglink.pipeline import Pipeline
from wfglink.synth.render import draw_spots


def _streak_frame(rng, length=16.0, amp=900.0, sigma=1.2, theta=0.3, center=(320.0, 180.0)):
    img = np.full((360, 640), 20.0, np.float32)
    acc = np.zeros_like(img)
    n = 64
    for k in range(n):
        s = (k + 0.5) / n - 0.5
        x, y = center[0] + s * length * np.cos(theta), center[1] + s * length * np.sin(theta)
        xi, yi = int(x), int(y)
        fx, fy = x - xi, y - yi
        a = amp / n
        acc[yi, xi] += a * (1 - fx) * (1 - fy); acc[yi, xi + 1] += a * fx * (1 - fy)
        acc[yi + 1, xi] += a * (1 - fx) * fy; acc[yi + 1, xi + 1] += a * fx * fy
    img += cv2.GaussianBlur(acc, (0, 0), sigma) + rng.normal(0, 2.0, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def test_refinement_recovers_faint_streak_length():
    cfg = load_config()
    rng = np.random.default_rng(0)
    raw, ref = [], []
    det = Detector(cfg)
    for i in range(40):
        f = _streak_frame(rng, amp=600.0, center=(100.0 + 20 * (i - 20), 180.0)) if i >= 20 else np.clip(20 + rng.normal(0, 2.0, (360, 640)), 0, 255).astype(np.uint8)
        d = det.detect(f)
        if i >= 20 and len(d):
            k = int(np.argmax(d.flux))
            raw.append(d.length[k])
            ref.append(refine_streaks(d, det.state, cfg).length[k])
    assert len(raw) >= 12
    assert np.median(raw) < 15.2                    # the threshold cut the faint ends
    assert abs(np.median(ref) - 16.0) < 0.5 * abs(np.median(raw) - 16.0)   # the window recovers them


# Edge profile fit --------------------------------------------------------------------------
SHAPE = (360, 640)
BG_LIN, NOISE_LIN = 2.5, 0.75          # dark night sky, linear DN (as in the synthetic suite)


def _encode(lin, gamma=2.2):
    return np.clip(np.rint(255.0 * (np.clip(lin, 0, None) / 255.0) ** (1 / gamma)), 0, 255).astype(np.uint8)


def _render(rng, streaks, sigma, gamma):
    """Pixel-integrated segments (x, y, length, theta, flux) in linear light plus noise,
    encoded like a camera (power law, 8 bits)."""
    xs, ys, ws = [], [], []
    for x, y, length, theta, flux in streaks:
        n = max(16, int(4 * length))
        t = (np.arange(n) + 0.5) / n - 0.5
        xs.append(x + t * length * np.cos(theta))
        ys.append(y + t * length * np.sin(theta))
        ws.append(np.full(n, flux / n))
    x, y, w = np.concatenate(xs), np.concatenate(ys), np.concatenate(ws)
    lin = draw_spots(x, y, w, np.ones((x.size, 3)), np.full(x.size, sigma), (SHAPE[1], SHAPE[0]))[..., 0]
    return _encode(BG_LIN + lin + rng.normal(0, NOISE_LIN, SHAPE), gamma)


def _measure(length, snr, sigma=1.2, frames=3, gamma=2.2, cfg=None, seed=0, fit_gamma=None):
    """Grid of streaks at random angles; returns (truth length, detector length, erf length)
    for every streak found."""
    cfg = cfg or load_config()
    if fit_gamma is not None:
        cfg = copy.deepcopy(cfg)
        cfg["detect"]["streaks"]["erf"]["gamma"] = fit_gamma
    rng = np.random.default_rng(seed)
    det = Detector(cfg)
    for _ in range(12):                                   # background and noise maps
        det.detect(_encode(BG_LIN + rng.normal(0, NOISE_LIN, SHAPE), gamma))
    flux = snr * NOISE_LIN * 2 * np.sqrt(np.pi) * sigma    # point-source SNR, as in the synthetic suite
    out = []
    for _ in range(frames):
        gx, gy = np.meshgrid(np.arange(70, SHAPE[1] - 60, 70.0), np.arange(70, SHAPE[0] - 60, 70.0))
        cx, cy = gx.ravel() + rng.uniform(-3, 3, gx.size), gy.ravel() + rng.uniform(-3, 3, gx.size)
        th = rng.uniform(0, np.pi, cx.size)
        d = det.detect(_render(rng, [(a, b, length, t, flux) for a, b, t in zip(cx, cy, th)], sigma, gamma))
        fit = erf_streaks(d, det.state, cfg)
        for a, b in zip(cx, cy):
            k = int(np.argmin(np.hypot(d.x - a, d.y - b))) if len(d) else -1
            if k >= 0 and np.hypot(d.x[k] - a, d.y[k] - b) < 2.0:
                out.append((length, d.length[k], fit.length[k]))
    return np.array(out)


def test_edge_fit_recovers_long_faint_streaks_that_moments_cut_short():
    r = _measure(16.0, snr=35.0)
    assert len(r) >= 40
    mom, fit = np.median(r[:, 1]), np.median(r[:, 2])
    assert mom < 0.95 * 16.0                              # the threshold cut the faint ends off
    assert abs(fit / 16.0 - 1) < 0.05
    assert abs(fit - 16.0) < abs(mom - 16.0)


@pytest.mark.parametrize("length", [4.0, 8.0])
def test_edge_fit_is_proportional_on_bright_streaks(length):
    r = _measure(length, snr=60.0, sigma=1.0)
    assert len(r) >= 40
    assert abs(np.median(r[:, 2]) / length - 1) < 0.06


def test_decoding_the_tone_curve_matters():
    # A power-law tone curve compresses a bright streak's plateau relative to its edges, so
    # a fit to the encoded luma (gamma 1) comes out long.
    enc = _measure(8.0, snr=150.0, sigma=1.0, fit_gamma=1.0)
    dec = _measure(8.0, snr=150.0, sigma=1.0)
    assert np.median(enc[:, 2]) > np.median(dec[:, 2]) + 0.3
    assert abs(np.median(dec[:, 2]) / 8.0 - 1) < 0.03


def test_edge_fit_keeps_detector_length_when_the_window_leaves_the_frame():
    cfg = load_config()
    rng = np.random.default_rng(3)
    det = Detector(cfg)
    for _ in range(12):
        det.detect(_encode(BG_LIN + rng.normal(0, NOISE_LIN, SHAPE)))
    flux = 60 * NOISE_LIN * 2 * np.sqrt(np.pi)
    d = det.detect(_render(rng, [(3.0, 180.0, 8.0, 0.0, flux), (320.0, 180.0, 8.0, 0.0, flux)], 1.0, 2.2))
    fit = erf_streaks(d, det.state, cfg)
    edge = int(np.argmin(d.x))
    mid = int(np.argmax(d.x))
    assert fit.length[edge] == d.length[edge]             # window outside the frame: no fit
    assert abs(fit.length[mid] - 8.0) < 1.0
    assert np.all(fit.x == d.x) and np.all(fit.y == d.y)  # positions are never moved
    assert len(erf_streaks(d.subset(np.zeros(len(d), bool)), det.state, cfg)) == 0


def test_along_model_is_a_normalised_box_with_exact_derivatives():
    u = np.linspace(-15, 15, 301)[None, :]
    F, c, L, s, k = (np.array([[v]]) for v in (3.0, 0.4, 7.0, 1.3, 0.6))
    for kk in (None, k):
        mod, d = _along(u, F, c, L, s, kk)
        assert abs(mod.sum() * 0.1 - 3.0) < 1e-6           # integrates to F
        params = [F, c, L, s] + ([k] if kk is not None else [])
        for j in range(len(params)):
            q = [p.copy() for p in params]
            q[j] = q[j] + 1e-6
            num = (_along(u, *q[:4], q[4] if kk is not None else None)[0] - mod) / 1e-6
            assert np.max(np.abs(num - d[j])) < 1e-4
    # Centroid at c, and the variance of a box (L^2 / 12) plus the blur.
    mod, _ = _along(u, F, c, L, s)
    w = mod[0] / mod.sum()
    assert abs((w * u[0]).sum() - 0.4) < 1e-6
    assert abs((w * (u[0] - 0.4) ** 2).sum() - (49 / 12 + 1.3 ** 2)) < 1e-3


def test_method_selection():
    cfg = load_config()
    cfg["detect"]["streaks"]["method"] = "moments"
    cfg["detect"]["streaks"]["refine"] = False
    assert streak_method(cfg) is None
    cfg["detect"]["streaks"]["refine"] = True
    assert streak_method(cfg) == "moments_refined"
    cfg["detect"]["streaks"]["method"] = "erf"
    assert streak_method(cfg) == "erf"
    cfg["detect"]["streaks"]["method"] = "edges"
    with pytest.raises(ValueError):
        streak_method(cfg)
    assert streak_method({}) is None                      # no key: the detector's moments as today


def test_file_mode_pipeline_uses_the_method_and_live_mode_does_not():
    rng = np.random.default_rng(5)
    flux = 40 * NOISE_LIN * 2 * np.sqrt(np.pi) * 1.2
    frames = [_encode(BG_LIN + rng.normal(0, NOISE_LIN, SHAPE)) for _ in range(12)]
    frames.append(_render(rng, [(320.0, 180.0, 16.0, 0.4, flux)], 1.2, 2.2))
    out = {}
    for method in ("erf", "moments"):
        cfg = load_config()
        cfg["detect"]["streaks"]["method"] = method
        cfg["detect"]["streaks"]["refine"] = False
        assert Pipeline(cfg, record=False).refine is False    # live mode: the detector's moments
        p = Pipeline(cfg, record=True, fps=30.0)
        assert p.refine is (method == "erf")
        for i, img in enumerate(frames):
            p.process(Frame(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), i / 30.0, i, 0.0, {}))
        d = p.tables()["detections"]
        d = d[d.frame == len(frames) - 1]
        k = int(np.argmin(np.hypot(d.x - 320, d.y - 180)))
        out[method] = float(d.length.iloc[k])
    assert abs(out["erf"] - 16.0) < abs(out["moments"] - 16.0)
    assert abs(out["erf"] / 16.0 - 1) < 0.1


def test_measure_streaks_dispatches():
    cfg = load_config()
    rng = np.random.default_rng(1)
    det = Detector(cfg)
    for _ in range(12):
        det.detect(_encode(BG_LIN + rng.normal(0, NOISE_LIN, SHAPE)))
    d = det.detect(_render(rng, [(320.0, 180.0, 12.0, 0.2, 60.0)], 1.2, 2.2))
    cfg["detect"]["streaks"]["method"] = "moments"
    cfg["detect"]["streaks"]["refine"] = False
    assert measure_streaks(d, det.state, cfg) is d
    cfg["detect"]["streaks"]["method"] = "erf"
    assert np.allclose(measure_streaks(d, det.state, cfg).length, erf_streaks(d, det.state, cfg).length)


def test_sampling_handles_thousands_of_detections():
    # cv2.remap takes fewer than 32767 rows per call; a real clip flooded with detections
    # (compression flicker on a 4K frame) needs more rows than that in one frame.
    yy, xx = np.mgrid[0:200, 0:300].astype(np.float32)
    img = xx + 0.5 * yy                                   # bilinear sampling is exact on a ramp
    rng = np.random.default_rng(0)
    m = 5000
    xc, yc, th = rng.uniform(20, 280, m), rng.uniform(20, 180, m), rng.uniform(0, np.pi, m)
    U = np.broadcast_to(np.arange(-3.0, 4.0), (m, 7))
    V = np.broadcast_to(np.arange(-4.0, 5.0), (m, 9))     # 45000 rows of samples
    S = _sample((img, np.zeros_like(img)), 1.0, xc, yc, th, U, V)
    assert S.shape == (m, 9, 7)
    assert np.max(np.abs(S[:, 4, 3] - (xc + 0.5 * yc))) < 0.1    # centres, in the right order
