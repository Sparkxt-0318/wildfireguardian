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
