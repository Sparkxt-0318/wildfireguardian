"""Sitting 1 recordings: what to record, how to name it, and immediate quality checks.

Each recording is copied byte for byte (originals untouched) into the upload folder under
a fixed name, with its SHA-256 and decoded metadata. Quick checks run at once so a
problem (LEDs invisible, camera not straight above the turntable, HDR on, wrong frame
rate) is caught while the setup is still on the table.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.provenance import sha256_file

VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".ts", ".h264", ".h265", ".hevc"}


@dataclass
class RecordingSpec:
    rid: str                       # stable id used in the report
    filename: str                  # canonical upload name without extension
    title: str
    device: str                    # iphone, dashcam
    minutes: float                 # time budget
    instructions: list[str]
    seconds_min: float
    fps_range: tuple[float, float]
    check: str                     # led, ruler, panel, drive
    optional: bool = False
    inputs: list[tuple[str, str, float, float]] = field(default_factory=list)  # key, prompt, lo, hi
    min_width: int = 1280


IPHONE_SETUP = [
    "iPhone Settings > Camera > Record Video: 1080p at 30 fps. Turn HDR Video OFF.",
    "Settings > Camera > Formats: Most Compatible is easiest (High Efficiency also works).",
    "Room dark, three orange LEDs on, at about 3, 8 and 14 cm from the turntable center, tracing paper over each LED.",
    "iPhone on the tripod pointing straight DOWN at the turntable, about 40 cm above it; the whole turntable in view.",
    "In the Camera app, press and hold on the turntable until AE/AF LOCK appears.",
]

DASHCAM_SETUP = [
    "Mount the 블랙박스 pointing straight DOWN at the turntable at about the same height (tape it to the tripod head or a box edge).",
    "Power it from USB; let it record continuously (it saves 1-minute segments).",
    "Same LEDs, same dark room. Note the clock time when each speed starts, to find the right segment later.",
]

SITTING1: list[RecordingSpec] = [
    RecordingSpec("iph_led_s1", "S1_IPH_LED_SPEED1", "iPhone: LED turntable, speed 1", "iphone", 4,
                  IPHONE_SETUP + [
                      "Start the turntable at its slower speed (33 1/3 rpm on a record player). Wait 5 s for it to settle.",
                      "Record 20 s of video. Stop.",
                      "Stopwatch: time exactly 30 revolutions (watch one LED pass a fixed mark).",
                      "AirDrop the clip to this Mac (it lands in Downloads).",
                  ], 15, (28, 61), "led",
                  inputs=[("t30_s1", "Seconds for 30 revolutions at speed 1", 5, 300)]),
    RecordingSpec("iph_led_s2", "S1_IPH_LED_SPEED2", "iPhone: LED turntable, speed 2", "iphone", 3,
                  ["Same setup, faster speed (45 rpm). Wait 5 s.", "Record 20 s. Stop.",
                   "Stopwatch: time 30 revolutions.", "AirDrop the clip to this Mac."],
                  15, (28, 61), "led",
                  inputs=[("t30_s2", "Seconds for 30 revolutions at speed 2", 5, 300)]),
    RecordingSpec("iph_led_ruler", "S1_IPH_LED_RULER", "iPhone: ruler in the LED plane", "iphone", 3,
                  ["Stop the turntable. Lay a ruler flat across it, at LED height, through the center.",
                   "Turn on a dim light so both the ruler marks and the LEDs are visible.",
                   "Record 10 s without moving the iPhone. AirDrop it to this Mac."],
                  5, (28, 61), "ruler",
                  inputs=[("ruler_cm", "Length of ruler clearly visible end to end, in cm (for example 30)", 5, 100)]),
    RecordingSpec("dc_led_s1", "S1_DC_LED_SPEED1", "Dashcam: LED turntable, speed 1", "dashcam", 6,
                  DASHCAM_SETUP + ["Speed 1 for 90 s (the dashcam keeps recording).",
                                   "Stopwatch: time 30 revolutions again during those 90 s."],
                  15, (24, 61), "led",
                  inputs=[("dc_t30_s1", "Seconds for 30 revolutions at speed 1 (dashcam run)", 5, 300)]),
    RecordingSpec("dc_led_s2", "S1_DC_LED_SPEED2", "Dashcam: LED turntable, speed 2", "dashcam", 3,
                  ["Speed 2 for 90 s.", "Stopwatch: time 30 revolutions."],
                  15, (24, 61), "led",
                  inputs=[("dc_t30_s2", "Seconds for 30 revolutions at speed 2 (dashcam run)", 5, 300)]),
    RecordingSpec("dc_led_ruler", "S1_DC_LED_RULER", "Dashcam: ruler in the LED plane", "dashcam", 3,
                  ["Stop the turntable, ruler across it at LED height, dim light on, 30 s.",
                   "Then power off the dashcam, take out the SD card and put it in the card reader.",
                   "For each dashcam step, pick the segment(s) recorded at that time (originals, untouched)."],
                  5, (24, 61), "ruler"),
    RecordingSpec("panel_240", "S1_IPH_PANEL_240FPS", "iPhone slow motion of the iPad screen", "iphone", 5,
                  ["AirDrop PANEL_TEST.mp4 (in the upload folder) to the iPad and play it full screen on loop, brightness at maximum.",
                   "iPhone Settings > Camera > Record Slo-mo: 1080p at 240 fps.",
                   "Camera app, SLO-MO mode. Hold the iPhone about 30 cm from the iPad so the screen fills most of the picture.",
                   "Record 5 s. AirDrop the clip to this Mac."],
                  2, (200, 250), "panel", min_width=640),
    RecordingSpec("dc_night_drive", "S1_DC_NIGHT_DRIVE", "Dashcam: night drive (no fire)", "dashcam", 15,
                  ["At night, drive 2 to 5 minutes with streetlights and traffic, dashcam on the windshield as usual.",
                   "Copy the segments from the SD card. This step can be done later with: scripts/sitting1.sh --add night_drive"],
                  60, (24, 61), "drive", optional=True),
]


def probe_video(path: Path, max_frames: int = 0) -> dict[str, Any]:
    """Decoded metadata: size, fps, duration, codec, color transfer (HDR), creation time."""
    import av

    out: dict[str, Any] = {}
    try:
        with av.open(str(path)) as c:
            s = c.streams.video[0]
            cc = s.codec_context
            rate = s.average_rate or s.guessed_rate
            out.update({
                "width": cc.width, "height": cc.height, "codec": cc.name,
                "fps": round(float(rate), 3) if rate else None,
                "duration_s": round(float(s.duration * s.time_base), 3) if s.duration else (
                    round(c.duration / 1e6, 3) if c.duration else None),
                "frames_declared": int(s.frames) if s.frames else None,
                "color_trc": str(getattr(cc, "color_trc", "")),
                "creation_time": c.metadata.get("creation_time") or s.metadata.get("creation_time"),
                "make_model": " ".join(v for k, v in c.metadata.items() if "model" in k.lower() or "make" in k.lower())[:120],
            })
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def intake(files: list[Path], spec: RecordingSpec, upload_dir: Path) -> dict[str, Any]:
    """Copy files under canonical names, hash them, and read their metadata."""
    entries = []
    for i, src in enumerate(files):
        suffix = src.suffix.lower() or ".bin"
        name = f"{spec.filename}{'' if len(files) == 1 else f'_{i + 1:02d}'}{suffix}"
        dst = upload_dir / name
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        entries.append({"original": str(src), "file": name, "bytes": dst.stat().st_size,
                        "sha256": sha256_file(dst), "meta": probe_video(dst)})
    return {"files": entries}


def basic_checks(spec: RecordingSpec, entries: list[dict[str, Any]]) -> list[str]:
    """Human-readable problems; empty when everything looks right."""
    problems = []
    total = sum((e["meta"].get("duration_s") or 0) for e in entries)
    if total < spec.seconds_min:
        problems.append(f"too short: {total:.0f} s, need at least {spec.seconds_min:.0f} s")
    for e in entries:
        m = e["meta"]
        if "error" in m:
            problems.append(f"{e['file']}: cannot decode ({m['error']})")
            continue
        fps = m.get("fps") or 0
        if not (spec.fps_range[0] <= fps <= spec.fps_range[1]):
            problems.append(f"{e['file']}: {fps:g} fps, expected {spec.fps_range[0]:g} to {spec.fps_range[1]:g}")
        if (m.get("width") or 0) < spec.min_width:
            problems.append(f"{e['file']}: only {m.get('width')}x{m.get('height')}")
        if "b67" in (m.get("color_trc") or "").lower() or "2084" in (m.get("color_trc") or ""):
            problems.append(f"{e['file']}: recorded in HDR; please turn HDR Video off and record again if time allows")
    return problems


def led_quick_check(path: Path, seconds: float = 4.0, cfg: dict | None = None) -> dict[str, Any]:
    """LED visibility and camera alignment from the first seconds of an LED clip.

    Detections are grouped into rings by their distance from the common center; the
    outermost ring is fitted with an ellipse whose axis ratio shows how straight above the
    turntable the camera is (1.0 is perfect; the plan asks for at least 0.99).
    """
    import av

    from wfglink.config import load_config
    from wfglink.detect.candidates import Detector

    cfg = cfg or load_config()
    det = Detector(cfg)
    xs, ys, counts, sat = [], [], [], []
    try:
        with av.open(str(path)) as c:
            s = c.streams.video[0]
            s.thread_type = "AUTO"
            for vf in c.decode(s):
                if vf.time is not None and vf.time > seconds:
                    break
                d = det.detect(vf.to_ndarray(format="bgr24"))
                if det.ready:
                    counts.append(len(d))
                    xs.extend(d.x.tolist())
                    ys.extend(d.y.tolist())
                    sat.append(float(np.mean(d.flags & 1)) if len(d) else 0.0)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if not counts:
        return {"ok": False, "error": "no frames analysed"}
    out: dict[str, Any] = {"detections_per_frame_median": float(np.median(counts)),
                           "saturated_fraction": round(float(np.mean(sat)), 3)}
    if len(xs) < 30:
        return {**out, "ok": False, "problem": "LEDs not detected; check they are on, the room is dark and the lens is clean"}
    pts = np.column_stack([xs, ys]).astype(np.float32)
    center = np.median(pts, axis=0)
    fit = None
    for _ in range(3):  # outermost ring only, re-centred on the fitted ellipse each pass
        r = np.hypot(*(pts - center).T)
        outer = pts[r >= 0.85 * np.percentile(r, 98)]
        if len(outer) < 5:
            break
        fit = cv2.fitEllipse(outer)
        # Reject points off the fitted ellipse (stray detections), then refit.
        (ex, ey), (ea, eb), eang = fit
        c, s = np.cos(np.radians(eang)), np.sin(np.radians(eang))
        dx, dy = outer[:, 0] - ex, outer[:, 1] - ey
        u, v = dx * c + dy * s, -dx * s + dy * c
        rn = np.sqrt((u / max(ea / 2, 1e-6)) ** 2 + (v / max(eb / 2, 1e-6)) ** 2)
        dev = np.abs(rn - 1)
        keep = dev < max(0.02, 4 * 1.4826 * float(np.median(dev)))
        if keep.sum() >= 5 and not keep.all():
            outer = outer[keep]
            fit = cv2.fitEllipse(outer)
        center = np.array(fit[0], np.float32)
    if fit is not None:
        (cx, cy), (a, b), ang = fit
        ratio = float(min(a, b) / max(a, b)) if max(a, b) > 0 else 0.0
        out.update({"outer_ellipse_axes_px": [round(a, 1), round(b, 1)], "axis_ratio": round(ratio, 4),
                    "center_px": [round(cx, 1), round(cy, 1)], "outer_points": int(len(outer))})
    problems = []
    if out["detections_per_frame_median"] < 2.5:
        problems.append("fewer than 3 LEDs seen per frame")
    if out["detections_per_frame_median"] > 6:
        problems.append("more than 3 bright spots per frame; turn off other lights or cover reflections")
    if out.get("axis_ratio", 1.0) < 0.99:
        problems.append(f"camera is tilted (circle axis ratio {out.get('axis_ratio')}); aim straight down and record again")
    if out["saturated_fraction"] > 0.5:
        problems.append("LEDs are saturated; add a second layer of tracing paper or lower the exposure")
    out["problems"] = problems
    out["ok"] = not problems
    return out
