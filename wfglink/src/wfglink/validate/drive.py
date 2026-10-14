"""Night drive hard negative (plan section 4.4): false tracks and false gate counts per minute.

A dashcam night drive with no fire has no embers, so every moving confirmed track and every
gate crossing is a false alarm. The clips go through the same Pipeline as file mode (native
resolution, default gate), segment by segment, and the totals are divided by the analysed
minutes. Static tracks (streetlights, the dashcam's own clock overlay) are reported
separately because the pipeline already excludes them from counts.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from wfglink.config import load_config
from wfglink.io.sources import FileSource
from wfglink.pipeline import Pipeline


def false_tracks_per_minute(paths: list[Path], cfg: dict | None = None, max_seconds: float | None = None
                            ) -> dict[str, Any]:
    cfg = cfg or load_config()
    per_file = []
    tot = {"seconds": 0.0, "moving": 0, "static": 0, "gross": 0, "frames": 0}
    t0 = time.perf_counter()
    for path in paths:
        pipe = Pipeline(cfg, dedupe=True)
        src = FileSource(path)
        try:
            src.open()
        except Exception as exc:
            per_file.append({"file": Path(path).name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        first = last = None
        try:
            while (f := src.read()) is not None:
                if max_seconds is not None and f.t > max_seconds:
                    break
                first = f.t if first is None else first
                last = f.t
                pipe.process(f)
        finally:
            src.close()
        pipe.finish()
        secs = (last - first) if first is not None and last is not None else 0.0
        s = pipe.stats
        moving = s.tracks_finished - s.tracks_static
        gross = pipe.counter.counts()["gross"] if pipe.counter is not None else 0
        per_file.append({"file": Path(path).name, "seconds": round(secs, 2), "frames": s.frames_analysed,
                         "moving_tracks": moving, "static_tracks": s.tracks_static, "gate_crossings": gross})
        tot["seconds"] += secs
        tot["moving"] += moving
        tot["static"] += s.tracks_static
        tot["gross"] += gross
        tot["frames"] += s.frames_analysed
    minutes = tot["seconds"] / 60.0
    out: dict[str, Any] = {"files": per_file, "minutes": round(minutes, 3), "frames": tot["frames"],
                           "moving_tracks": tot["moving"], "static_tracks": tot["static"],
                           "gate_crossings": tot["gross"],
                           "seconds_processing": round(time.perf_counter() - t0, 1)}
    if minutes > 0:
        out["false_tracks_per_min"] = round(tot["moving"] / minutes, 2)
        out["false_gate_counts_per_min"] = round(tot["gross"] / minutes, 2)
    return out
