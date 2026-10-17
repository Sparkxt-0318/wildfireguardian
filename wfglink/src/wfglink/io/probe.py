"""Decoded video metadata, read with PyAV without decoding the whole file.

    from wfglink.io.probe import probe_video
    probe_video("data/raw/C6_nist_dragon.mp4")   # {"width": 540, "height": 360, "fps": 29.969, ...}

Used by file mode (outputs/process.py) and the clip fetcher (scripts/fetch_clips.py). It
never raises: an unreadable file gives {"error": "..."}.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def probe_video(path: str | Path, max_frames: int = 0) -> dict[str, Any]:
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
