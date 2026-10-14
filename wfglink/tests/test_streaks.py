"""Streak refinement recovers the ends of long, faint streaks that the threshold cuts off."""
import cv2
import numpy as np

from wfglink.config import load_config
from wfglink.detect.candidates import Detector
from wfglink.detect.streaks import refine_streaks


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
