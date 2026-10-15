"""Dashcam scene clips (plan section 4.4): the night drive hard negative and the room test.

A dashcam night drive with no fire has no embers, so every moving confirmed track and every
gate crossing is a false alarm. The clips go through the same Pipeline as file mode (native
resolution, default gate), part by part, with the date stamp masked from detection, and the
totals are divided by the analysed minutes. Static tracks (streetlights, anything burnt into
the picture outside the mask) are reported separately because the pipeline already excludes
them from counts.

The room test is the same pass on a short clip of the room: it checks that the dashcam's files
decode and look sane (codec, size, frame rate, regular frame intervals, repeated frames) and
reports detections, moving tracks and gate crossings per minute and any LED rings it sees. It
has no pass or fail.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.config import load_config
from wfglink.io.sources import FileSource
from wfglink.validate.dashcam import MaskedPipeline, files_cfg, read_frames, sharpness, timing_summary


def scene_counts(paths: list[Path], cfg: dict | None = None, max_seconds: float | None = None, boxes=(),
                 keep_tracks: bool = False, images: dict | None = None) -> dict[str, Any]:
    """One file-mode pass over the parts of a recording: counts, timing and (optionally) tracks.

    max_seconds: at most this many seconds of the recording, all parts together.
    boxes: regions never detected in (the date stamp), fractions of the frame.
    keep_tracks: keep every track's points (out["_tracks"], arrays with a static column)
    for finding LED rings; images: a dict that receives the sharpest of a few frames as
    images["still"].
    """
    cfg = cfg or load_config()
    per_file = []
    tot = {"seconds": 0.0, "moving": 0, "static": 0, "gross": 0, "frames": 0, "detections": 0, "repeated": 0}
    times: list[np.ndarray] = []
    tracks: list[dict[str, np.ndarray]] = []
    errors: list[str] = []
    best = -1.0
    t0 = time.perf_counter()
    for path in paths:
        if max_seconds is not None and tot["seconds"] >= max_seconds:
            break
        pipe = MaskedPipeline(cfg, boxes, dedupe=True, record=keep_tracks)
        src = FileSource(path)
        try:
            src.open()
        except Exception as exc:
            per_file.append({"file": Path(path).name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        first = last = None
        part_t: list[float] = []
        n_det = 0
        next_still = 0.0
        try:
            for f in read_frames(src, errors):
                first = f.t if first is None else first
                if max_seconds is not None and tot["seconds"] + (f.t - first) > max_seconds:
                    break
                last = f.t
                part_t.append(f.t)
                done = pipe.stats.frames_analysed
                state = pipe.process(f)
                if pipe.stats.frames_analysed > done:
                    n_det += len(state.detections)
                if images is not None and f.t - first >= next_still:
                    next_still = f.t - first + 1.0
                    if (s := sharpness(f.image)) > best:
                        images["still"], best = f.image.copy(), s
        finally:
            src.close()
        pipe.finish()
        secs = (last - first) if first is not None and last is not None else 0.0
        s = pipe.stats
        moving = s.tracks_finished - s.tracks_static
        gross = pipe.counter.counts()["gross"] if pipe.counter is not None else 0
        per_file.append({"file": Path(path).name, "seconds": round(secs, 2), "frames": s.frames_analysed,
                         "repeated_frames": s.frames_duplicate, "detections": n_det,
                         "moving_tracks": moving, "static_tracks": s.tracks_static, "gate_crossings": gross})
        times.append(np.array(part_t))
        tot["seconds"] += secs
        tot["moving"] += moving
        tot["static"] += s.tracks_static
        tot["gross"] += gross
        tot["frames"] += s.frames_analysed
        tot["detections"] += n_det
        tot["repeated"] += s.frames_duplicate
        if keep_tracks:
            for tr in pipe.tracker.all_tracks(include_active=True):
                if tr.n_points:
                    a = tr.arrays()
                    a["static"] = np.full(len(a["t"]), bool(tr.static))
                    tracks.append(a)
    minutes = tot["seconds"] / 60.0
    out: dict[str, Any] = {"files": per_file, "minutes": round(minutes, 3), "frames": tot["frames"],
                           "detections": tot["detections"], "moving_tracks": tot["moving"],
                           "static_tracks": tot["static"], "gate_crossings": tot["gross"],
                           "timing": timing_summary(times, files_cfg(cfg)["interval_tol_frac"], tot["repeated"]),
                           "seconds_processing": round(time.perf_counter() - t0, 1)}
    if errors:
        out["warnings"] = errors
    if minutes > 0:
        out["detections_per_min"] = round(tot["detections"] / minutes, 2)
        out["moving_tracks_per_min"] = round(tot["moving"] / minutes, 2)
        out["gate_crossings_per_min"] = round(tot["gross"] / minutes, 2)
    if keep_tracks:
        out["_tracks"] = tracks
    return out


def false_tracks_per_minute(paths: list[Path], cfg: dict | None = None, max_seconds: float | None = None,
                            boxes=(), images: dict | None = None) -> dict[str, Any]:
    """Night drive hard negative: every moving track and gate crossing is a false count."""
    out = scene_counts(paths, cfg, max_seconds, boxes, images=images)
    if out["minutes"] > 0:
        out["false_tracks_per_min"] = out["moving_tracks_per_min"]
        out["false_gate_counts_per_min"] = out["gate_crossings_per_min"]
    return out


def room_check(paths: list[Path], cfg: dict | None = None, max_seconds: float | None = None, boxes=(),
               images: dict | None = None) -> dict[str, Any]:
    """Room test: decode and timing facts, counts per minute and any LED rings; no pass or fail."""
    from wfglink.validate.led import rings_in_tracks

    cfg = cfg or load_config()
    out = scene_counts(paths, cfg, max_seconds, boxes, keep_tracks=True, images=images)
    out["led_rings"] = rings_in_tracks(out.pop("_tracks"), cfg)
    return out
