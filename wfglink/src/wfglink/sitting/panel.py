"""iPad panel test video and the analysis of its 240 fps slow-motion recording.

The test video alternates full black and full white every frame at 30 fps, with a thin
gray border. Filmed at 240 fps, each black-to-white change sweeps across the panel in its
scan order, so the time of the change at each image row and column reveals the scan
direction. Frame times ignore the camera's own row readout, so the reported sweep is the
panel scan time minus the camera readout along the same axis (a vertical panel scan of
15 ms filmed with a 3 ms readout appears as about 12 to 13 ms per screen height). The booth corner codes handle torn frames
regardless; this measurement confirms the assumption.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np


def write_panel_video(path: Path, seconds: float = 12.0, fps: int = 30, size: tuple[int, int] = (1920, 1080)) -> Path:
    import av

    w, h = size
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        s.options = {"crf": "12", "preset": "veryfast", "tune": "stillimage"}
        n = int(round(seconds * fps))
        for i in range(n):
            v = 255 if i % 2 else 0
            img = np.full((h, w, 3), v, np.uint8)
            cv2.rectangle(img, (0, 0), (w - 1, h - 1), (128, 128, 128), 12)
            cv2.putText(img, f"{i:04d}", (40, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (128, 128, 128), 3)
            for pkt in s.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return path


def analyse_panel_clip(path: Path, max_seconds: float = 4.0) -> dict[str, Any]:
    """Scan direction and sweep time from a slow-motion clip of the panel test video."""
    import av

    lumas, times = [], []
    try:
        with av.open(str(path)) as c:
            st = c.streams.video[0]
            st.thread_type = "AUTO"
            for vf in c.decode(st):
                if vf.time is None:
                    continue
                if times and vf.time - times[0] > max_seconds:
                    break
                g = vf.to_ndarray(format="gray")
                lumas.append(cv2.resize(g, (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32))
                times.append(float(vf.time))
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if len(lumas) < 40:
        return {"ok": False, "error": "too few frames"}
    stack = np.stack(lumas)                     # (T, 54, 96)
    t = np.array(times) - times[0]
    var = stack.std(axis=0)
    screen = var > max(10.0, 0.5 * var.max())   # the flickering panel
    if screen.sum() < 50:
        return {"ok": False, "error": "panel not found (is the test video playing full screen?)"}
    ys, xs = np.nonzero(screen)
    lo, hi = np.percentile(stack[:, screen], 10), np.percentile(stack[:, screen], 90)
    mid = 0.5 * (lo + hi)
    # Rising crossings per pixel: time where luma passes mid upward, linearly interpolated.
    rec = []
    for y, x in zip(ys, xs):
        s = stack[:, y, x]
        above = s > mid
        idx = np.nonzero(~above[:-1] & above[1:])[0]
        for k in idx:
            frac = (mid - s[k]) / max(s[k + 1] - s[k], 1e-6)
            rec.append((y, x, t[k] + frac * (t[k + 1] - t[k])))
    if len(rec) < 100:
        return {"ok": False, "error": "no clean black-to-white transitions"}
    rec = np.array(rec)
    # Group crossings into transition events (all pixels change within one sweep).
    order = np.argsort(rec[:, 2])
    rec = rec[order]
    events, current = [], [rec[0]]
    for row in rec[1:]:
        if row[2] - current[-1][2] > 0.012:
            events.append(np.array(current))
            current = [row]
        else:
            current.append(row)
    events.append(np.array(current))
    events = [e for e in events if len(e) > 0.5 * len(ys)]
    if not events:
        return {"ok": False, "error": "transitions too irregular"}
    slopes_y, slopes_x, r2 = [], [], []
    hy, hx = screen.any(axis=1).sum(), screen.any(axis=0).sum()
    for e in events:
        A = np.column_stack([e[:, 0] / max(hy, 1), e[:, 1] / max(hx, 1), np.ones(len(e))])
        coef, res, *_ = np.linalg.lstsq(A, e[:, 2], rcond=None)
        pred = A @ coef
        ss = float(np.sum((e[:, 2] - e[:, 2].mean()) ** 2)) or 1e-12
        slopes_y.append(coef[0] * 1000)
        slopes_x.append(coef[1] * 1000)
        r2.append(1 - float(np.sum((e[:, 2] - pred) ** 2)) / ss)
    sy, sx = float(np.median(slopes_y)), float(np.median(slopes_x))
    axis = "vertical (top-bottom in the picture)" if abs(sy) >= abs(sx) else "horizontal (left-right in the picture)"
    period = float(np.median(np.diff([e[:, 2].mean() for e in events]))) if len(events) > 1 else None
    return {"ok": True, "transitions": len(events),
            "apparent_sweep_ms_per_screen_height": round(sy, 2),
            "apparent_sweep_ms_per_screen_width": round(sx, 2),
            "note": "apparent sweep = panel scan time minus the camera's rolling-shutter readout along that axis",
            "scan_axis": axis, "fit_r2_median": round(float(np.median(r2)), 3),
            "transition_period_ms": round(period * 1000, 2) if period else None,
            "capture_fps_measured": round(float(1 / np.median(np.diff(t))), 1)}
