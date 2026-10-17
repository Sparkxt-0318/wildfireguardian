"""Blind annotation windows: short space-time boxes of a video for labelling embers as tracks.

`make_windows` never runs the detector and never reads a run folder. It decodes the clip
as `process` does (FileSource from the start of the segment, then the ROI crop), so a
window's frame indices and times are the ones a file-mode run of that segment gives, and
its x0, y0 are in the coordinates of detections.parquet (inside the ROI crop).

Sampling (seeded, numpy default_rng(seed)):
- Time. The frames that are not pixel repeats (the pipeline's test, validate.labels) from
  the detector's warm-up plus labels.settle_s on are cut, in order, into consecutive
  blocks of k changed frames after a random offset in [0, k); n blocks are drawn without
  replacement, so no frame is in two windows. The window IDs follow the draw order.
- Space. One tile per window, its corner uniform at random so that the tile lies fully
  inside the ROI: 192 px for videos up to 1080 lines, 256 px for larger ones (smaller when
  the ROI is smaller).

Folder (nothing in it comes from detections):
- wNNN_kJ.png: frame J of window NNN, the tile enlarged `scale` times by nearest neighbour
  with a 1 px grid line every grid_px tile pixels (a line marked k passes through the
  centre of tile pixel k, the convention of detections.parquet) and the frame index.
- wNNN_context.png: the window's middle frame, the whole ROI reduced to at most
  context_width px wide, with the tile outlined.
- raw/wNNN_kJ.png: the tile at 1x (lossless); manifest raw_sha256 is the SHA-256 of its pixels.
- manifest.csv, windows.json (seed, rule, video SHA-256, settings), labels_template.csv
  and README.txt (the labelling protocol).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.config import load_config

MANIFEST = "manifest.csv"
WINDOWS_JSON = "windows.json"
TEMPLATE = "labels_template.csv"
LABEL_COLUMNS = ["window_id", "k", "x", "y", "confidence", "ember_id", "size_class", "note"]
_ALLOWED = (MANIFEST, WINDOWS_JSON, TEMPLATE, "README.txt")
RULE = ("time: the frames that are not pixel repeats, from the detector's warm-up plus settle_s on, cut in order into "
        "consecutive blocks of k after a random offset in [0, k); n blocks drawn without replacement (no frame in two "
        "windows), window IDs in draw order; space: one tile per window, corner uniform at random with the tile fully "
        "inside the ROI; numpy default_rng(seed), the offset drawn first, then per window the block and the corner")

README = """Blind ember windows (wfglink verify windows). Window set {set_id}.

Label before you see any detection, track or score. Each window is {k} consecutive frames of
one tile: wNNN_k0.png .. wNNN_k{k_last}.png, enlarged {scale}x by nearest neighbour (each tile
pixel is a {scale}x{scale} block), with a grid line every {grid} tile pixels; a line marked n
passes through the centre of tile pixel n. wNNN_context.png shows where the tile sits in the
whole picture (middle frame). Look at the frames of a window in order: an ember moves.

Write one row per ember per frame to a copy of labels_template.csv:
  window_id   wNNN
  k           the frame within the window (0 .. {k_last}), from the file name
  x, y        the ember's centre in tile pixels of the ORIGINAL resolution (for a streak, its
              middle; pixel centres at integers; the grid tells the position)
  confidence  1.0 when sure, 0.5 when unsure
  ember_id    a number that is the same for the same ember in every frame of the window
  size_class  s (a dot of a few pixels), m, or l (a long streak or a large blob)
  note        optional
A window you looked at that holds no ember gets one row: its window_id, x and y empty and
the note none. Windows without any row count as not labelled. Keep your labels file outside
this folder: it holds only what verify windows wrote.
"""


def tile_size_for(width: int, height: int) -> int:
    """192 px for videos up to 1080 lines, 256 px otherwise."""
    return 192 if min(width, height) <= 1080 else 256


def _check_dir(out: Path, force: bool) -> None:
    """Refuse a folder holding anything make_windows did not write and, without force, an earlier set."""
    if not out.exists():
        return
    if not out.is_dir():
        raise ValueError(f"{out} is not a folder")
    for p in out.iterdir():
        ok = (p.name in _ALLOWED or (p.is_file() and p.suffix == ".png" and p.name.startswith("w"))
              or (p.is_dir() and p.name == "raw" and all(q.is_file() and q.suffix == ".png" for q in p.iterdir())))
        if not ok:
            raise ValueError(f"{out} holds {p.name}; a window folder must be empty or an earlier window folder")
    if not force and any(True for _ in out.iterdir()):
        raise ValueError(f"{out} already holds a window set; use another folder or force to replace it")


def _clear_dir(out: Path) -> None:
    for p in [*out.glob("w*.png"), *(out / "raw").glob("*.png"), *(out / n for n in _ALLOWED)]:
        if p.is_file():
            p.unlink()


def _source(clip: str | Path, roi=None, segment: tuple[float | None, float | None] | None = None):
    """(video, clip id, settings path or None, ROI value, segment) from a clip settings file or a video.

    A None start or end in `segment` keeps the clip settings' value (for a video: 0 and the end)."""
    from wfglink.validate.clips import clip_id, load_clip_settings, segments

    c = Path(clip)
    if c.suffix in (".yaml", ".yml"):
        cc, video, sp = load_clip_settings(c)
        base = segments(cc)[0]
        cid, roi = clip_id(cc, video), (cc.get("roi") if roi is None else roi)
    else:
        video, cid, sp, base = c.resolve(), c.stem, None, (0.0, None)
    a, b = segment if segment is not None else (None, None)
    seg = (float(base[0]) if a is None else float(a), base[1] if b is None else float(b))
    return video, cid, sp, roi, seg


def make_windows(clip: str | Path, out_dir: str | Path, n: int = 20, k: int = 8, seed: int = 0,
                 tile_px: int | None = None, scale: int = 4, grid_px: int = 32, roi=None,
                 segment: tuple[float, float | None] | None = None, cfg: dict | None = None, force: bool = False,
                 context_width: int = 640) -> dict[str, Any]:
    """Write blind annotation windows for one clip (see the module notes). Returns the windows.json record.

    clip: a clip settings file (data/clips/<id>.yaml: ROI and first segment) or a video file.
    roi: x0, y0, x1, y1 in fractions of the frame (or pixels when any value exceeds 1).
    segment: (start, end) in clip seconds; a None start or end keeps the clip settings' one.
    Everything that can fail happens before the folder is touched.
    """
    import pandas as pd

    from wfglink.io.probe import probe_video
    from wfglink.io.sources import FileSource
    from wfglink.outputs.process import roi_crop
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.validate.labels import _scan, detector_ready_time, render_tile

    cfg = cfg or load_config()
    if n < 1 or k < 1 or scale < 1 or grid_px < 1:
        raise ValueError("n, k, scale and grid_px must be at least 1")
    video, cid, settings, roi, (a, b) = _source(clip, roi, segment)
    out = Path(out_dir)
    _check_dir(out, force)
    meta = probe_video(video)
    if meta.get("error") or not meta.get("width"):
        raise ValueError(f"cannot read {video}: {meta.get('error')}")
    W, H = int(meta["width"]), int(meta["height"])
    crop = roi_crop(roi, W, H) or (0, 0, W, H)
    rw, rh = crop[2] - crop[0], crop[3] - crop[1]
    side = int(tile_px or tile_size_for(W, H))
    tw, th = min(side, rw), min(side, rh)
    settle = float(cfg.get("labels", {}).get("settle_s", 0.5))
    warm = int(cfg.get("detect", {}).get("background", {}).get("warmup_frames", 5))

    rows = _scan(video, a, b, crop, cfg)
    t_ready = detector_ready_time(rows, cfg)
    if t_ready is None:
        raise ValueError(f"the segment has {sum(not r['repeat'] for r in rows)} changed frames; the detector's warm-up "
                         f"needs more than {warm}")
    pool = [r for r in rows if not r["repeat"] and r["t"] >= t_ready + settle]
    rng = np.random.default_rng(seed)
    offset = int(rng.integers(0, k))
    blocks = [pool[offset + i * k:offset + (i + 1) * k] for i in range(max(0, (len(pool) - offset) // k))]
    if not blocks:
        raise ValueError(f"{len(pool)} changed frames after the warm-up: too few for one window of {k}")
    n_draw = min(int(n), len(blocks))
    wins = []
    for j, bi in enumerate(rng.choice(len(blocks), size=n_draw, replace=False).tolist()):
        x0, y0 = int(rng.integers(0, rw - tw + 1)), int(rng.integers(0, rh - th + 1))
        blk = blocks[bi]
        wins.append({"window_id": f"w{j:03d}", "block": bi, "frames": [r["frame"] for r in blk],
                     "t": [r["t"] for r in blk], "x0": x0, "y0": y0})

    # Decode once: tile crops of every window frame and the middle frame for the context view.
    want: dict[int, list[tuple[dict, int]]] = {}
    for wd in wins:
        for kk, f in enumerate(wd["frames"]):
            want.setdefault(f, []).append((wd, kk))
    last = max(want)
    tiles: dict[tuple[str, int], np.ndarray] = {}
    context: dict[str, np.ndarray] = {}
    cs = min(1.0, float(context_width) / rw)
    src = FileSource(video, start_s=a)
    src.open()
    try:
        while (f := src.read()) is not None:
            if f.index > last:
                break
            for wd, kk in want.get(int(f.index), []):
                img = f.image[crop[1]:crop[3], crop[0]:crop[2]]
                tiles[(wd["window_id"], kk)] = np.ascontiguousarray(img[wd["y0"]:wd["y0"] + th, wd["x0"]:wd["x0"] + tw])
                if kk == len(wd["frames"]) // 2:
                    context[wd["window_id"]] = cv2.resize(img, (max(1, round(rw * cs)), max(1, round(rh * cs))),
                                                          interpolation=cv2.INTER_AREA) if cs < 1 else img.copy()
    finally:
        src.close()
    missing = [wd["window_id"] for wd in wins for kk in range(len(wd["frames"])) if (wd["window_id"], kk) not in tiles]
    if missing:
        raise ValueError(f"frames of windows {missing[:5]} were not decoded again; the clip decodes differently on a rerun")

    out.mkdir(parents=True, exist_ok=True)
    _clear_dir(out)
    (out / "raw").mkdir(exist_ok=True)
    man_rows = []
    for wd in wins:
        wid = wd["window_id"]
        pngs, raws, shas = [], [], []
        for kk, (f, t) in enumerate(zip(wd["frames"], wd["t"])):
            tile = tiles[(wid, kk)]
            title = f"{wid}  k {kk}  frame {f}  t {t:.3f} s  x0 {wd['x0']}  y0 {wd['y0']}"
            name = f"{wid}_k{kk}.png"
            cv2.imwrite(str(out / name), render_tile(tile, scale, grid_px, max(1, grid_px // 4), grid_px, title))
            cv2.imwrite(str(out / "raw" / name), tile)
            pngs.append(name)
            raws.append(f"raw/{name}")
            shas.append(hashlib.sha256(tile.tobytes()).hexdigest())
        ctx = context[wid].copy()
        p0 = (int(round(wd["x0"] * cs)), int(round(wd["y0"] * cs)))
        p1 = (int(round((wd["x0"] + tw) * cs)) - 1, int(round((wd["y0"] + th) * cs)) - 1)
        cv2.rectangle(ctx, p0, p1, (0, 220, 255), 2)
        bar = np.full((22, ctx.shape[1], 3), 245, np.uint8)
        cv2.putText(bar, f"{wid}  frame {wd['frames'][len(wd['frames']) // 2]}  tile {tw}x{th} at ({wd['x0']}, {wd['y0']})",
                    (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
        cv2.imwrite(str(out / f"{wid}_context.png"), np.vstack([bar, ctx]))
        man_rows.append({"window_id": wid, "clip_id": cid, "segment": 0, "run_start_s": a, "k": len(wd["frames"]),
                         "frames": ";".join(str(v) for v in wd["frames"]),
                         "t": ";".join(repr(float(v)) for v in wd["t"]),
                         "x0": wd["x0"], "y0": wd["y0"], "w": tw, "h": th, "roi_x0": crop[0], "roi_y0": crop[1],
                         "scale": scale, "grid_px": grid_px, "png": ";".join(pngs), "raw_png": ";".join(raws),
                         "context_png": f"{wid}_context.png", "raw_sha256": ";".join(shas)})
    man = pd.DataFrame(man_rows)
    man.to_csv(out / MANIFEST, index=False)
    set_id = sha256_file(out / MANIFEST)[:16]
    pd.DataFrame(columns=LABEL_COLUMNS).to_csv(out / TEMPLATE, index=False)
    (out / "README.txt").write_text(README.format(set_id=set_id, k=k, k_last=k - 1, scale=scale, grid=grid_px),
                                    encoding="utf-8")
    rec = {
        "schema_version": 1, "created": now_shanghai(), "window_set_id": set_id, "clip_id": cid,
        "clip_settings": str(settings) if settings else None, "video": str(video), "video_sha256": sha256_file(video),
        "source_size": [W, H], "roi_px": list(crop), "segment_s": [a, b], "seed": int(seed), "rule": RULE,
        "n_requested": int(n), "n_windows": len(wins), "k": int(k), "offset": offset, "blocks_available": len(blocks),
        "frames_in_pool": len(pool), "detector_ready_s": t_ready, "warmup_frames": warm, "settle_s": settle,
        "tile_px": [tw, th], "scale": scale, "grid_px": grid_px, "context_width": context_width,
        "manifest_sha256": sha256_file(out / MANIFEST),
        "coordinates": "x0, y0: ROI crop pixels as in detections.parquet; labels: tile pixels, pixel centres at integers",
        "frame_naming": "frame and t as a file-mode run that starts at segment_s[0] names them",
        "label_columns": LABEL_COLUMNS, "config_sha256": sha256_json(cfg), **git_state(),
    }
    (out / WINDOWS_JSON).write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


def read_manifest(windows_dir: str | Path):
    """The manifest with frames and t as lists."""
    import pandas as pd

    p = Path(windows_dir) / MANIFEST
    if not p.exists():
        raise ValueError(f"no {MANIFEST} in {windows_dir}; it is not a folder written by verify windows")
    man = pd.read_csv(p, dtype={"window_id": str})
    man["frames"] = man["frames"].map(lambda s: [int(v) for v in str(s).split(";")])
    man["t"] = man["t"].map(lambda s: [float(v) for v in str(s).split(";")])
    return man
