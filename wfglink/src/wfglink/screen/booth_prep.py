"""Prepare a clip for the camera-in-the-loop booth.

For each hold factor (2 and 3 by default) this writes a constant 30 fps H.264 file in which
every source frame is repeated `hold` times and carries the corner codes (ArUco markers
and its Gray-coded source frame index), plus a sidecar CSV that maps the source frame
index to the true source timestamp. Velocities in booth mode use those timestamps, so the
slowed playback (0.5x for hold 2 on a 30 fps source) never changes the measured speeds.

Optional crop: a source rectangle (x, y, w, h) enlarged to the output size, to offset the
resolution lost when the iPhone films the iPad.
"""
from __future__ import annotations

import csv
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.io.sources import FileSource
from wfglink.provenance import run_record, sha256_file
from wfglink.screen.codes import Layout, draw_codes

OUT_FPS = 30


def _out_size(w: int, h: int, max_height: int) -> tuple[int, int]:
    if h > max_height:
        w, h = int(round(w * max_height / h)), max_height
    return w - (w % 2), h - (h % 2)


def prepare(clip: str | Path, out_dir: str | Path, holds: tuple[int, ...] = (2, 3), max_height: int = 1080,
            crop: tuple[int, int, int, int] | None = None, source_step: int | None = None,
            crf: int = 16, max_seconds: float | None = None) -> dict[str, Any]:
    clip, out_dir = Path(clip), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src = FileSource(clip)
    src.open()
    info = dict(src.info)
    fps_src = info.get("fps_nominal") or 30.0
    step = source_step or max(1, int(round(fps_src / OUT_FPS)))
    import av

    writers = {}
    try:
        n_src = 0
        rows = []
        while True:
            f = src.read()
            if f is None or (max_seconds and f.t > max_seconds):
                break
            if f.index % step:
                continue
            img = f.image
            if crop:
                x, y, w, h = crop
                img = img[y:y + h, x:x + w]
            if not writers:
                ow, oh = _out_size(img.shape[1], img.shape[0], max_height)
                layout = Layout.for_frame(ow, oh)
                for hold in holds:
                    path = out_dir / f"{clip.stem}_hold{hold}.mp4"
                    c = av.open(str(path), "w")
                    s = c.add_stream("libx264", rate=Fraction(OUT_FPS, 1))
                    s.width, s.height, s.pix_fmt = ow, oh, "yuv420p"
                    s.options = {"crf": str(crf), "preset": "medium"}
                    writers[hold] = (c, s, path)
            if img.shape[1] != ow or img.shape[0] != oh:
                img = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_AREA if img.shape[0] > oh else cv2.INTER_CUBIC)
            else:
                img = img.copy()
            draw_codes(img, n_src, layout)
            vf = av.VideoFrame.from_ndarray(img, format="bgr24")
            for hold, (c, s, _) in writers.items():
                for _ in range(hold):
                    for pkt in s.encode(vf):
                        c.mux(pkt)
            rows.append((n_src, f.t, f.index))
            n_src += 1
    finally:
        src.close()
        for c, s, _ in writers.values():
            for pkt in s.encode():
                c.mux(pkt)
            c.close()
    sidecar = out_dir / f"{clip.stem}_codes.csv"
    with open(sidecar, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["source_index", "source_t_s", "source_frame_in_file"])
        w.writerows(rows)
    duration = rows[-1][1] - rows[0][1] if len(rows) > 1 else 0.0
    meta = {
        "input": str(clip), "input_sha256": sha256_file(clip), "source": {k: v for k, v in info.items() if k != "metadata"},
        "source_step": step, "crop": crop, "out_fps": OUT_FPS, "frames_source_used": len(rows),
        "layout": {"width": layout.width, "height": layout.height, "marker": layout.marker, "cell": layout.cell,
                   "margin": layout.margin, "block": [layout.block_w, layout.block_h]},
        "outputs": {str(h): {"file": p.name, "playback_speed": round((OUT_FPS / h) / (fps_src / step), 4),
                             "sha256": sha256_file(p)} for h, (_, _, p) in writers.items()},
        "sidecar": sidecar.name, "source_duration_s": round(duration, 3),
        "provenance": run_record("wfglink.screen.booth_prep"),
    }
    (out_dir / f"{clip.stem}_booth.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


def load_sidecar(path: str | Path) -> np.ndarray:
    """Array of source timestamps indexed by source frame index."""
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = np.full(len(rows), np.nan)
    for r in rows:
        out[int(r["source_index"])] = float(r["source_t_s"])
    return out
