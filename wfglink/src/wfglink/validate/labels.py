"""Blind sample labels on real clips (plan section 4.5).

Protocol. Embers are labelled before any detection is seen, on enlarged tiles of randomly
sampled frames; the scores are tagged with who labelled them ("agent-labeled" for the
agent) and carry a bootstrap interval over frames. A second labeler labels the tiles of
the first labels.check_frames frames of the draw (marked in the manifest), which gives an
inter-labeler F1.

`make_tiles` never runs the detector and never reads a run folder. It decodes the clip
exactly as `process` does (FileSource from the start of the clip's first segment, the
only one `process` analyses, then the ROI crop), so a tile's frame index and time are the
ones the file-mode run gives that frame, and its x0, y0 are in the coordinates of
detections.parquet (inside the ROI crop).

Frames. The detector's background is seeded by the first detect.background.warmup_frames
frames that reach it, and it is ready from the next one. Pixel-repeated frames (the
pipeline's pixel test, which make_tiles runs too) never reach the detector. Content
repeats of a lossy re-encode do reach it: the pipeline finds them only after detecting,
from embers that did not move, so they need moving tracks and cannot occur before the
detector is ready. The warm-up found here is therefore the run's. The frames after the
warm-up plus labels.settle_s that are not pixel repeats are drawn in a random order
(fixed seed): labels.frames frames to score and labels.reserve_frames more in reserve.
Content repeats can only be found from detections, so the run skips some drawn frames on
a lossy re-encode, and the scores then take the next frames of the draw; fewer than
labels.frames frames are scored when the reserve runs out. Tile IDs follow the draw
order. Tile positions are uniform at random inside the ROI, without overlap within a
frame (so a small ROI may give a frame fewer than labels.tiles_per_frame tiles). A folder
that already holds a tile set is refused unless force is set, so that labels are never
scored against tiles they were not made on.

Tile folder (nothing in it comes from detections):
- tNNN.png: the tile enlarged labels.scale times by nearest neighbour, with a grid every
  labels.grid_step_px tile pixels (light on dark pixels, dark on bright ones), margin
  ticks every labels.tick_step_px and tick labels every labels.label_step_px. A grid line
  or tick marked k passes through the centre of tile pixel k, the convention of
  detections.parquet (pixel centres at integers). tNNN_prev1.png and tNNN_next1.png show
  the nearest changed frames before and after (labels.context_frames), so a moving ember
  can be told from a static light.
- raw/tNNN.png: the tile at 1x (lossless), for checks.
- manifest.csv: tile_id, frame, t (as the run names them), draw (rank in the random
  draw), reserve, check (for the second labeler), x0, y0, w, h, and more.
- labels_template.csv: tile_id, x, y (tile pixels), confidence, note.
- README.txt (the protocol) and tiles.json (settings, provenance and the tile set ID).

Label rows give an ember's centre (the middle of a streak) in tile pixels. A tile that was
looked at and holds no ember gets one row with x and y left empty. Tiles without any row
were not labelled and are left out. A label with a confidence below labels.min_confidence
is "don't care": it and the detection or label it matches count neither for nor against.

`score_labels` matches labels to the run's detections of the same frame inside the same
tile one to one (Hungarian assignment, the matcher of the synthetic validation, within
max(labels.match_px, labels.streak_radius_frac x the detection's length) source pixels)
and reports precision, recall and F1 with percentile bootstrap intervals over frames. A
detection just outside the tile may match a label inside it; unmatched detections count
as false only inside the tile. It refuses a run of another video than the tiles'.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.config import load_config

TAG = "agent-labeled"
LABEL_COLUMNS = ["tile_id", "x", "y", "confidence", "note"]
MANIFEST = "manifest.csv"
TEMPLATE = "labels_template.csv"
TILES_JSON = "tiles.json"
# Everything make_tiles writes; anything else in a tile folder is refused.
_ALLOWED = (MANIFEST, TEMPLATE, "README.txt", TILES_JSON)
_EMPTY = {"", "nan", "na", "none"}       # label cells read as empty

README = """Blind ember labels (wfglink, plan section 4.5). Tile set {tile_set_id}.

Label before you see any detection or score. Open each tNNN.png (the frame to label).
tNNN_prev1.png and tNNN_next1.png show the nearest changed frames before and after it, so
you can tell a moving ember from a static light; label only tNNN.png.

Write one row per ember to a copy of labels_template.csv:
  tile_id     as in the file name (t000, t001, ...)
  x, y        the ember's centre in tile pixels (for a streak, its middle), read from the
              grid: a grid line or tick marked k passes through the centre of tile pixel k;
              lines are {grid} tile pixels apart
  confidence  1 when sure, 0.5 when unsure (below {min_conf:g}: not counted either way)
  note        optional (for example: faint, streak, maybe a spark)
A tile that you looked at and that holds no ember gets one row with its tile_id and x, y
left empty. Tiles without any row count as not labelled. Keep your labels file outside this
folder: it holds only what label-tiles wrote.

Label the tiles in the order of their IDs, the reserve tiles too (manifest column reserve):
the run may skip some frames as repeats, and the scores then take the next frames in this
order. A second labeler labels only the tiles marked check in the manifest.

The tiles are enlarged {scale}x by nearest neighbour; each tile pixel is a {scale}x{scale} block.
Score with: python -m wfglink label-score <this folder> --labels <your csv> --run <run folder>
"""


def _lcfg(cfg: dict) -> dict:
    return cfg.get("labels", {})


# Tiles ------------------------------------------------------------------------------------

def render_tile(crop: np.ndarray, scale: int, grid_step: int, tick_step: int, label_step: int,
                title: str = "", alpha: float = 0.5, dark_dn: float = 110.0) -> np.ndarray:
    """Enlarge a BGR tile by nearest neighbour and add a grid, margin ticks and labels.

    The grid is drawn light on pixels darker than dark_dn and dark on brighter ones,
    blended with weight alpha, so it stays visible on bright lab scenes and dark night
    scenes alike.
    """
    h, w = crop.shape[:2]
    s = int(scale)
    big = cv2.resize(crop, (w * s, h * s), interpolation=cv2.INTER_NEAREST)
    c = s // 2                                 # the line through the centre of tile pixel k is at k s + s // 2
    line = np.zeros((h * s, w * s), dtype=bool)
    line[:, [k * s + c for k in range(0, w, grid_step)]] = True
    line[[k * s + c for k in range(0, h, grid_step)], :] = True
    dark_px = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY) < dark_dn
    ink = np.where(dark_px[..., None], np.array([255, 200, 120], np.uint8), np.array([110, 40, 0], np.uint8))
    blend = cv2.addWeighted(ink.astype(np.uint8), alpha, big, 1.0 - alpha, 0.0)
    big[line] = blend[line]
    left, top, right, bottom = 44, 46, 44, 30
    canvas = np.full((h * s + top + bottom, w * s + left + right, 3), 245, np.uint8)
    canvas[top:top + h * s, left:left + w * s] = big
    font, fs, ink_c = cv2.FONT_HERSHEY_SIMPLEX, 0.4, (20, 20, 20)
    for k in range(0, w, tick_step):
        x = left + k * s + c
        n = 9 if k % label_step == 0 else (6 if k % grid_step == 0 else 3)
        cv2.line(canvas, (x, top - 1), (x, top - 1 - n), ink_c, 1)
        cv2.line(canvas, (x, top + h * s), (x, top + h * s + n), ink_c, 1)
        if k % label_step == 0:
            (tw, _), _ = cv2.getTextSize(str(k), font, fs, 1)
            cv2.putText(canvas, str(k), (x - tw // 2, top - 13), font, fs, ink_c, 1, cv2.LINE_AA)
            cv2.putText(canvas, str(k), (x - tw // 2, top + h * s + 24), font, fs, ink_c, 1, cv2.LINE_AA)
    for k in range(0, h, tick_step):
        y = top + k * s + c
        n = 9 if k % label_step == 0 else (6 if k % grid_step == 0 else 3)
        cv2.line(canvas, (left - 1, y), (left - 1 - n, y), ink_c, 1)
        cv2.line(canvas, (left + w * s, y), (left + w * s + n, y), ink_c, 1)
        if k % label_step == 0:
            (tw, th), _ = cv2.getTextSize(str(k), font, fs, 1)
            cv2.putText(canvas, str(k), (left - 12 - tw, y + th // 2), font, fs, ink_c, 1, cv2.LINE_AA)
            cv2.putText(canvas, str(k), (left + w * s + 12, y + th // 2), font, fs, ink_c, 1, cv2.LINE_AA)
    if title:
        cv2.putText(canvas, title, (left, 14), font, 0.45, ink_c, 1, cv2.LINE_AA)
    return canvas


def _is_repeat(gray: np.ndarray, prev: np.ndarray | None, dn: int, max_px: int) -> bool:
    """The pipeline's pixel test for a repeated frame (Pipeline.process, frames.duplicate_*)."""
    if prev is None or prev.shape != gray.shape:
        return False
    return cv2.countNonZero(cv2.compare(cv2.absdiff(gray, prev), dn, cv2.CMP_GE)) <= max_px


def _scan(video: Path, start: float, end: float | None, crop: tuple[int, int, int, int], cfg: dict
          ) -> list[dict[str, Any]]:
    """Every frame of one segment as `process` names it: index, time, repeat flag."""
    from wfglink.io.sources import FileSource

    fr = cfg.get("frames", {})
    dn, max_px = int(fr.get("duplicate_dn", 6)), int(fr.get("duplicate_max_px", 2))
    rows: list[dict[str, Any]] = []
    src = FileSource(video, start_s=start)
    src.open()
    prev = None
    last_t = None
    try:
        while (f := src.read()) is not None:
            if end is not None and f.t > end - start:
                break
            img = f.image[crop[1]:crop[3], crop[0]:crop[2]]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rep = _is_repeat(gray, prev, dn, max_px) or (last_t is not None and f.t <= last_t)
            prev = gray
            if not rep:
                last_t = f.t
            rows.append({"frame": int(f.index), "t": float(f.t), "repeat": bool(rep)})
    finally:
        src.close()
    return rows


def detector_ready_time(rows: list[dict[str, Any]], cfg: dict) -> float | None:
    """Time of the first frame the run's detector is ready for, from a segment scan (`_scan`).

    Pixel-repeated frames never reach the detector, whose background is seeded by the first
    detect.background.warmup_frames frames it sees; it is ready from the next one. Content
    repeats (found by the pipeline only after detecting) need moving tracks, so none occur
    during the warm-up. None when the segment is too short.
    """
    warm = int(cfg.get("detect", {}).get("background", {}).get("warmup_frames", 5))
    new = [r for r in rows if not r["repeat"]]
    return new[warm]["t"] if len(new) > warm else None


def _place_tiles(rng: np.random.Generator, n: int, size: tuple[int, int], tile: tuple[int, int],
                 tries: int = 1000) -> list[tuple[int, int]]:
    """Up to n non-overlapping tile corners (x0, y0), uniform at random inside size (w, h)."""
    W, H = size
    tw, th = tile
    out: list[tuple[int, int]] = []
    for _ in range(tries):
        if len(out) == n:
            break
        x0, y0 = int(rng.integers(0, W - tw + 1)), int(rng.integers(0, H - th + 1))
        if all(abs(x0 - a) >= tw or abs(y0 - b) >= th for a, b in out):
            out.append((x0, y0))
    return out


def _check_tile_dir(out: Path, force: bool) -> None:
    """Refuse a folder that holds anything make_tiles did not write, and (without force) an
    earlier tile set. Reads only."""
    if not out.exists():
        return
    if not out.is_dir():
        raise ValueError(f"{out} is not a folder")
    for p in out.iterdir():
        ok = (p.name in _ALLOWED or (p.is_file() and p.suffix == ".png" and p.name.startswith("t"))
              or (p.is_dir() and p.name == "raw" and all(q.is_file() and q.suffix == ".png" for q in p.iterdir())))
        if not ok:
            raise ValueError(f"{out} holds {p.name}; a tile folder must be empty or an earlier tile folder "
                             "(nothing derived from detections may sit next to the tiles)")
    if not force and any(p.name != "raw" for p in out.iterdir()):
        raise ValueError(f"{out} already holds a tile set; labels made on it would be scored against new tiles. "
                         "Use another folder, or --force to replace it")


def _clear_tile_dir(out: Path) -> None:
    for p in [*out.glob("t*.png"), *(out / "raw").glob("*.png"), *(out / n for n in _ALLOWED)]:
        if p.is_file():
            p.unlink()


def make_tiles(clip_settings: str | Path, out_dir: str | Path, frames: int | None = None,
               tiles_per_frame: int | None = None, tile_px: int | None = None, scale: int | None = None,
               seed: int | None = None, cfg: dict | None = None, reserve: int | None = None,
               force: bool = False) -> dict[str, Any]:
    """Write blind label tiles for one clip (see the module notes). Returns the tiles.json record.

    Everything that can fail (the folder check, decoding, the warm-up) happens before the
    folder is touched.
    """
    import pandas as pd

    from wfglink.io.sources import FileSource
    from wfglink.outputs.process import roi_crop
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.io.probe import probe_video
    from wfglink.validate.clips import clip_id, load_clip_settings, segments

    cfg = cfg or load_config()
    lc = _lcfg(cfg)
    frames = int(lc.get("frames", 20) if frames is None else frames)
    reserve = int(lc.get("reserve_frames", 10) if reserve is None else reserve)
    tiles_per_frame = int(lc.get("tiles_per_frame", 2) if tiles_per_frame is None else tiles_per_frame)
    tile_px = int(lc.get("tile_px", 256) if tile_px is None else tile_px)
    scale = int(lc.get("scale", 4) if scale is None else scale)
    seed = int(lc.get("seed", 0) if seed is None else seed)
    n_check = min(int(lc.get("check_frames", 5)), frames)
    n_ctx = int(lc.get("context_frames", 1))
    settle = float(lc.get("settle_s", 0.5))
    warm = int(cfg.get("detect", {}).get("background", {}).get("warmup_frames", 5))
    if frames < 1 or tiles_per_frame < 1 or tile_px < 1 or scale < 1 or reserve < 0:
        raise ValueError("frames, tiles per frame, tile size and scale must be at least 1, the reserve at least 0")
    cc, video, settings_path = load_clip_settings(clip_settings)
    out = Path(out_dir)
    _check_tile_dir(out, force)
    meta = probe_video(video)
    if meta.get("error") or not meta.get("width"):
        raise ValueError(f"cannot read {video}: {meta.get('error')}")
    W, H = int(meta["width"]), int(meta["height"])
    crop = roi_crop(cc.get("roi"), W, H) or (0, 0, W, H)
    rw, rh = crop[2] - crop[0], crop[3] - crop[1]
    tw, th = min(tile_px, rw), min(tile_px, rh)

    # Frames of the segment `process` analyses (the first), then a random draw after the warm-up.
    segs = segments(cc)
    a, b = segs[0]
    rows = _scan(video, a, b, crop, cfg)
    t_ready = detector_ready_time(rows, cfg)
    if t_ready is None:
        raise ValueError(f"the segment {a:g} to {b} s has {sum(not r['repeat'] for r in rows)} changed frames; "
                         f"the detector's warm-up needs more than {warm}")
    pool = [r["frame"] for r in rows if not r["repeat"] and r["t"] >= t_ready + settle]
    if not pool:
        raise ValueError(f"no changed frame {settle:g} s after the detector's warm-up (ready at {t_ready:.3f} s "
                         f"after {a:g} s) in the segment {a:g} to {b} s")
    rng = np.random.default_rng(seed)
    n_draw = min(frames + reserve, len(pool))
    drawn = [pool[i] for i in rng.choice(len(pool), size=n_draw, replace=False)]   # in random order
    pos_of = {r["frame"]: k for k, r in enumerate(rows)}

    tiles = []
    for rank, fi in enumerate(drawn):
        pos = pos_of[fi]
        prev = [r["frame"] for r in reversed(rows[:pos]) if not r["repeat"]][:n_ctx]
        nxt = [r["frame"] for r in rows[pos + 1:] if not r["repeat"]][:n_ctx]
        for x0, y0 in _place_tiles(rng, tiles_per_frame, (rw, rh), (tw, th)):
            tiles.append({"frame": fi, "t": rows[pos]["t"], "draw": rank, "reserve": rank >= frames,
                          "check": rank < n_check, "x0": x0, "y0": y0, "prev": prev, "next": nxt})
    for k, tl in enumerate(tiles):
        tl["tile_id"] = f"t{k:03d}"

    # Second pass: crop (kept in memory, small), then render and write once nothing can fail.
    want: dict[int, list[tuple[dict, str]]] = {}
    for tl in tiles:
        want.setdefault(tl["frame"], []).append((tl, ""))
        for j, f in enumerate(tl["prev"]):
            want.setdefault(f, []).append((tl, f"_prev{j + 1}"))
        for j, f in enumerate(tl["next"]):
            want.setdefault(f, []).append((tl, f"_next{j + 1}"))
    last = max(want)
    crops: list[tuple[str, np.ndarray, str]] = []      # (file name, crop, title; no title for the 1x raw tile)
    src = FileSource(video, start_s=a)
    src.open()
    try:
        while (f := src.read()) is not None:
            if f.index > last:
                break
            for tl, suffix in want.get(int(f.index), []):
                x0, y0 = crop[0] + tl["x0"], crop[1] + tl["y0"]
                tile = np.ascontiguousarray(f.image[y0:y0 + th, x0:x0 + tw])
                role = ("LABEL THIS FRAME" + (" (reserve)" if tl["reserve"] else "") if not suffix else
                        f"context ({'previous' if 'prev' in suffix else 'next'} {suffix[-1]}), do not label")
                title = f"{tl['tile_id']}  {role}  frame {int(f.index)}  t {f.t:.3f} s  x0 {tl['x0']}  y0 {tl['y0']}"
                crops.append((f"{tl['tile_id']}{suffix}.png", tile, title))
                if not suffix:
                    crops.append((f"raw/{tl['tile_id']}.png", tile, ""))
                    tl["raw_sha256"] = hashlib.sha256(tile.tobytes()).hexdigest()
    finally:
        src.close()
    missing = [tl["tile_id"] for tl in tiles if "raw_sha256" not in tl]
    if missing:
        raise ValueError(f"frames of tiles {missing[:5]} were not decoded again; "
                         "the clip decodes differently on a rerun")

    out.mkdir(parents=True, exist_ok=True)
    _clear_tile_dir(out)                     # an earlier tile set (only with force; checked above)
    (out / "raw").mkdir(exist_ok=True)
    grid, ticks, tick_labels = (int(lc.get(k, d)) for k, d in (("grid_step_px", 8), ("tick_step_px", 4),
                                                                ("label_step_px", 32)))
    alpha, dark_dn = float(lc.get("grid_alpha", 0.5)), float(lc.get("grid_dark_dn", 110.0))
    for name, tile, title in crops:
        cv2.imwrite(str(out / name), render_tile(tile, scale, grid, ticks, tick_labels, title, alpha, dark_dn)
                    if title else tile)
    cid = clip_id(cc, video)
    man = pd.DataFrame([{
        "tile_id": tl["tile_id"], "clip_id": cid, "segment": 0, "run_start_s": a,
        "frame": tl["frame"], "t": tl["t"], "pts_s": a + tl["t"], "draw": tl["draw"], "reserve": tl["reserve"],
        "check": tl["check"], "x0": tl["x0"], "y0": tl["y0"], "w": tw, "h": th, "roi_x0": crop[0], "roi_y0": crop[1],
        "scale": scale, "png": f"{tl['tile_id']}.png", "raw_png": f"raw/{tl['tile_id']}.png",
        "context_frames": ";".join(str(f) for f in tl["prev"][::-1] + tl["next"]),
        "context_png": ";".join([f"{tl['tile_id']}_prev{j + 1}.png" for j in range(len(tl["prev"]))][::-1]
                                + [f"{tl['tile_id']}_next{j + 1}.png" for j in range(len(tl["next"]))]),
        "raw_sha256": tl["raw_sha256"]} for tl in tiles])
    man.to_csv(out / MANIFEST, index=False)
    tile_set_id = sha256_file(out / MANIFEST)[:16]
    pd.DataFrame(columns=LABEL_COLUMNS).to_csv(out / TEMPLATE, index=False)
    (out / "README.txt").write_text(README.format(scale=scale, tile_set_id=tile_set_id,
                                                  grid=grid,
                                                  min_conf=float(lc.get("min_confidence", 0.75))), encoding="utf-8")
    rec = {
        "schema_version": 2, "created": now_shanghai(), "tile_set_id": tile_set_id, "clip_id": cid,
        "clip_settings": str(settings_path), "video": str(video), "video_sha256": sha256_file(video),
        "roi_px": list(crop), "segment_s": [a, b], "segments_in_clip": len(segs),
        "segment_note": "process analyses only the first segment of segments_s; the tiles come from it",
        "frames_requested": frames, "reserve_frames": reserve, "frames_drawn": n_draw, "frames_in_pool": len(pool),
        "check_frames": n_check, "tiles": len(tiles), "tiles_reserve": sum(tl["reserve"] for tl in tiles),
        "detector_ready_s": t_ready, "tiles_per_frame": tiles_per_frame, "tile_px": [tw, th], "scale": scale,
        "seed": seed, "context_frames": n_ctx, "warmup_frames": warm, "settle_s": settle,
        "scoring_note": ("the run may skip drawn frames as content repeats (a lossy re-encode); the scores take the "
                         "first frames_requested frames of the draw that the run analysed"),
        "coordinates": "x0, y0 and labels: pixel centres at integers, inside the ROI crop, as in detections.parquet",
        "frame_naming": "frame and t as a file-mode run that starts at run_start_s names them",
        "labels_config": lc, "config_sha256": sha256_json(cfg), **git_state(),
    }
    (out / TILES_JSON).write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


# Scores -----------------------------------------------------------------------------------

def read_labels(labels) -> "Any":
    """Label rows as a DataFrame (tile_id, x, y, confidence, note); x, y NaN for 'no ember' rows.

    Raises ValueError for an empty file, a file without a tile_id column, and rows whose
    tile_id is empty, whose x, y or confidence is not a number, or that give only one of x
    and y, naming the rows (CSV line numbers), so that no label disappears silently.
    """
    import pandas as pd

    header = ",".join(LABEL_COLUMNS)
    if isinstance(labels, pd.DataFrame):
        df, name, line0 = labels.copy(), "labels", 0
    else:
        p = Path(labels)
        if not p.read_text(encoding="utf-8", errors="replace").strip():
            raise ValueError(f"{p} is empty; a labels file starts with the header {header}")
        df, name, line0 = pd.read_csv(p, dtype=str, keep_default_na=False), str(p), 2
    if "tile_id" not in df:
        raise ValueError(f"{name} has no tile_id column; the header is {header}")
    for col in LABEL_COLUMNS:
        if col not in df:
            df[col] = ""
    df = df.reset_index(drop=True)
    df["tile_id"] = df["tile_id"].map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v))
                                      else str(v).strip())
    problems = []
    num = {}
    for col in ("x", "y", "confidence"):
        txt = df[col].map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v).strip())
        blank = txt.str.lower().isin(_EMPTY)
        val = pd.to_numeric(txt.where(~blank), errors="coerce")
        bad = ~blank & ~np.isfinite(val.to_numpy(dtype=float))
        problems += [f"line {i + line0}: {col} {txt[i]!r} is not a number" for i in np.flatnonzero(bad)]
        num[col] = val.where(~bad)
    half = num["x"].isna() != num["y"].isna()
    problems += [f"line {i + line0}: only one of x and y given" for i in np.flatnonzero(half.to_numpy())]
    problems += [f"line {i + line0}: no tile_id" for i in np.flatnonzero((df["tile_id"] == "").to_numpy())]
    if problems:
        raise ValueError(f"{name}: {len(problems)} rows cannot be read: " + "; ".join(sorted(set(problems))[:10]))
    for col in ("x", "y", "confidence"):
        df[col] = num[col].astype(float)
    df["note"] = df["note"].map(lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
    return df[LABEL_COLUMNS]


def _points(df, min_conf: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """(label positions (n, 2), sure flags): rows with coordinates; a label below min_conf is
    not sure (don't care), and a missing confidence counts as sure."""
    x, y = df["x"].to_numpy(float), df["y"].to_numpy(float)
    keep = np.isfinite(x) & np.isfinite(y)
    conf = df["confidence"].to_numpy(float)[keep]
    return np.column_stack([x[keep], y[keep]]), ~(np.isfinite(conf) & (conf < min_conf))


def _in_tile(p: np.ndarray, x0: float, y0: float, w: float, h: float, pad: float = 0.0) -> np.ndarray:
    """Points (n, 2) inside a tile whose corner pixel centre is (x0, y0), widened by pad."""
    return ((p[:, 0] >= x0 - 0.5 - pad) & (p[:, 0] < x0 + w - 0.5 + pad)
            & (p[:, 1] >= y0 - 0.5 - pad) & (p[:, 1] < y0 + h - 0.5 + pad))


def _match_dont_care(ref: np.ndarray, ref_sure: np.ndarray, other: np.ndarray, other_sure: np.ndarray, radius
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One-to-one matches with don't-care points.

    Sure points of both sides are matched first (Hungarian, `match_points`); then the
    unmatched sure points of each side are matched to the other side's unsure points,
    which makes them don't care too. `radius` is per point of `ref` (scalar or (n,)).
    Returns (true matches as index pairs (k, 2) into ref and other, don't-care mask of
    ref, don't-care mask of other); unsure points are always don't care.
    """
    from wfglink.validate.match import match_points

    rad = np.broadcast_to(np.asarray(radius, dtype=np.float64), (len(ref),))
    rs, os_ = np.flatnonzero(ref_sure), np.flatnonzero(other_sure)
    gi, di, _ = match_points(ref[rs], other[os_], rad[rs])
    pairs = np.column_stack([rs[gi], os_[di]]).astype(np.int64) if gi.size else np.zeros((0, 2), np.int64)
    dc_ref, dc_other = ~ref_sure, ~other_sure
    free_r, unsure_o = np.setdiff1d(rs, pairs[:, 0]), np.flatnonzero(~other_sure)
    if free_r.size and unsure_o.size:
        gi, _, _ = match_points(ref[free_r], other[unsure_o], rad[free_r])
        dc_ref[free_r[gi]] = True
    free_o, unsure_r = np.setdiff1d(os_, pairs[:, 1]), np.flatnonzero(~ref_sure)
    if free_o.size and unsure_r.size:
        _, di, _ = match_points(ref[unsure_r], other[free_o], rad[unsure_r])
        dc_other[free_o[di]] = True
    return pairs, dc_ref, dc_other


def bootstrap_prf(tp, fp, fn, n_boot: int = 2000, seed: int = 0, ci: float = 0.95, min_frames: int = 5
                  ) -> dict[str, Any]:
    """Precision, recall and F1 from per-frame counts, with percentile bootstrap intervals over frames.

    Frames are resampled with replacement. With fewer than min_frames frames there is no
    interval (None): a bootstrap over one or two frames looks certain and is not.
    Replicates in which a measure is undefined (zero denominator) are left out of its
    interval and counted.
    """
    tp, fp, fn = (np.asarray(a, dtype=np.float64) for a in (tp, fp, fn))

    def prf(a, b, c):
        with np.errstate(divide="ignore", invalid="ignore"):
            return a / (a + b), a / (a + c), 2 * a / (2 * a + b + c)

    T, P, N = tp.sum(), fp.sum(), fn.sum()
    point = prf(T, P, N)
    out: dict[str, Any] = {}
    reps = None
    if tp.size >= max(1, int(min_frames)) and n_boot > 0:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, tp.size, size=(n_boot, tp.size))
        reps = prf(tp[idx].sum(1), fp[idx].sum(1), fn[idx].sum(1))
    a = (1.0 - ci) / 2
    undefined = {}
    for name, val, k in (("precision", point[0], 0), ("recall", point[1], 1), ("f1", point[2], 2)):
        lo = hi = None
        if reps is not None:
            ok = np.isfinite(reps[k])
            undefined[name] = int((~ok).sum())
            if ok.any():
                lo, hi = (float(q) for q in np.quantile(reps[k][ok], [a, 1 - a]))
        out[name] = {"value": float(val) if np.isfinite(val) else None, "ci": [lo, hi]}
    out.update(tp=int(T), fp=int(P), fn=int(N), frames=int(tp.size), bootstrap=int(n_boot), seed=int(seed), level=ci,
               min_frames_ci=int(min_frames), replicates_undefined=undefined if reps is not None else None)
    if reps is None:
        out["ci_note"] = (f"no interval: {tp.size} frames, fewer than {int(min_frames)}" if n_boot > 0
                          else "no interval: bootstrap switched off")
    return out


def _tiles_record(tile_dir: Path) -> dict[str, Any]:
    p = tile_dir / TILES_JSON
    if not p.exists():
        raise ValueError(f"{tile_dir} has no {TILES_JSON}; it is not a folder written by label-tiles")
    return json.loads(p.read_text(encoding="utf-8"))


def _read_manifest(path: Path):
    import pandas as pd

    if not Path(path).exists():
        raise ValueError(f"no manifest at {path}")
    return pd.read_csv(path, dtype={"tile_id": str})


def _file_sha(labels) -> str | None:
    from wfglink.provenance import sha256_file

    return sha256_file(labels) if isinstance(labels, (str, Path)) else None


def score_labels(tile_dir: str | Path, labels, run_dir: str | Path, cfg: dict | None = None,
                 match_px: float | None = None, tag: str = TAG) -> dict[str, Any]:
    """Precision, recall and F1 of a run's detections against blind labels (see the module notes)."""
    import pandas as pd

    from wfglink.validate.plausibility import read_table

    cfg = cfg or load_config()
    lc = _lcfg(cfg)
    m = float(lc.get("match_px", 3.0) if match_px is None else match_px)
    frac = float(lc.get("streak_radius_frac", 0.0))
    min_conf = float(lc.get("min_confidence", 0.75))
    tol = float(lc.get("time_tol_s", 1e-6))
    tile_dir, run_dir = Path(tile_dir), Path(run_dir)
    rec = _tiles_record(tile_dir)
    man = _read_manifest(tile_dir / MANIFEST)
    lab = read_labels(labels)
    unknown = sorted(set(lab["tile_id"]) - set(man["tile_id"]))
    if unknown:
        raise ValueError(f"labels name tiles that are not in the manifest: {unknown[:10]}")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    inp = summary.get("input") or {}
    if rec.get("video_sha256") and inp.get("sha256") != rec["video_sha256"]:
        raise ValueError(f"the run analysed another video (SHA-256 {str(inp.get('sha256'))[:12]}) than the tiles show "
                         f"({rec['video_sha256'][:12]})")
    roi = inp.get("roi_px") or [0, 0, inp.get("width"), inp.get("height")]
    if (int(man["roi_x0"].iloc[0]), int(man["roi_y0"].iloc[0])) != (int(roi[0]), int(roi[1])):
        raise ValueError(f"the run's ROI {roi} does not start where the tiles' ROI does "
                         f"({int(man['roi_x0'].iloc[0])}, {int(man['roi_y0'].iloc[0])})")
    tile_roi = [int(v) for v in rec.get("roi_px") or []]
    if tile_roi and [int(v) for v in roi] != tile_roi:
        # A smaller run ROI with the same origin would score tiles where no detection can exist.
        raise ValueError(f"the run's ROI {[int(v) for v in roi]} differs from the tiles' ROI {tile_roi}")
    run_start = float((inp.get("segment_s") or [0.0])[0] or 0.0)
    frames = read_table(run_dir, "frames", summary)
    dets = read_table(run_dir, "detections", summary)
    if frames is None or dets is None:
        raise ValueError(f"{run_dir} lacks frames or detections")
    fr = frames.set_index("frame")
    by_frame = {int(k): g for k, g in dets.groupby("frame")} if len(dets) else {}
    target = int(rec.get("frames_requested") or lc.get("frames", 20))

    labelled = set(lab["tile_id"])
    order = ["draw", "tile_id"] if "draw" in man else ["frame", "tile_id"]
    rows, skipped, outside, scored = [], [], 0, []
    for _, tl in man[man["tile_id"].isin(labelled)].sort_values(order).iterrows():
        tid, f = tl["tile_id"], int(tl["frame"])
        if abs(float(tl["run_start_s"]) - run_start) > tol:
            skipped.append({"tile_id": tid, "reason": "segment not in this run"})
            continue
        if f not in fr.index:
            skipped.append({"tile_id": tid, "reason": "frame not in the run"})
            continue
        if abs(float(fr.loc[f, "t"]) - float(tl["t"])) > tol:
            raise ValueError(f"tile {tid}: frame {f} has t = {float(fr.loc[f, 't'])} in the run but "
                             f"{float(tl['t'])} in the manifest; the run and the tiles name frames differently")
        if bool(fr.loc[f, "duplicate"]) or not bool(fr.loc[f, "ready"]):
            skipped.append({"tile_id": tid, "reason": "repeated frame" if bool(fr.loc[f, "duplicate"])
                            else "detector not ready"})
            continue
        if f not in scored:
            if len(scored) >= target:
                skipped.append({"tile_id": tid, "reason": "reserve not needed (enough frames scored)"})
                continue
            scored.append(f)
        x0, y0, w, h = (float(tl[k]) for k in ("x0", "y0", "w", "h"))
        pts, sure = _points(lab[lab["tile_id"] == tid], min_conf)
        ok = _in_tile(pts, 0.0, 0.0, w, h)
        outside += int((~ok).sum())                  # a typo, not an ember of this tile
        pts, sure = pts[ok] + [x0, y0], sure[ok]
        g = by_frame.get(f)
        d = g[["x", "y"]].to_numpy(float) if g is not None else np.zeros((0, 2))
        length = g["length"].to_numpy(float) if g is not None and "length" in g else np.zeros(len(d))
        rad = np.maximum(m, frac * np.nan_to_num(length, nan=0.0))
        near = _in_tile(d, x0, y0, w, h, float(rad.max()) if rad.size else m)
        d, rad = d[near], rad[near]
        inside = _in_tile(d, x0, y0, w, h)
        # Detections are the reference side, so that each carries its own radius.
        pairs, dc_det, _ = _match_dont_care(d, np.ones(len(d), bool), pts, sure, rad)
        matched = np.zeros(len(d), bool)
        matched[pairs[:, 0]] = True
        tp = int(len(pairs))
        rows.append({"tile_id": tid, "frame": f, "labels": int(sure.sum()), "unsure_labels": int((~sure).sum()),
                     "detections": int(inside.sum()), "tp": tp, "fn": int(sure.sum() - tp),
                     "fp": int((inside & ~matched & ~dc_det).sum()),
                     "dont_care_detections": int((inside & dc_det).sum())})
    cols = ["tile_id", "frame", "labels", "unsure_labels", "detections", "tp", "fn", "fp", "dont_care_detections"]
    per_tile = pd.DataFrame(rows, columns=cols)
    per_frame = per_tile.groupby("frame")[["tp", "fp", "fn"]].sum() if len(per_tile) else per_tile
    res = bootstrap_prf(per_frame["tp"], per_frame["fp"], per_frame["fn"], int(lc.get("bootstrap", 2000)),
                        int(lc.get("bootstrap_seed", 0)), float(lc.get("ci", 0.95)), int(lc.get("min_frames_ci", 5)))
    warnings = []
    if len(per_frame) < target:
        warnings.append(f"{len(per_frame)} frames scored, fewer than the {target} planned "
                        "(skipped frames, unlabelled tiles or too small a reserve)")
    res.update(tag=tag, match_px=m, streak_radius_frac=frac, min_confidence=min_conf, frames_target=target,
               tiles_scored=int(len(per_tile)), tiles_labelled=len(labelled), tiles_skipped=skipped,
               labels_outside_tile=outside, unsure_labels=int(per_tile["unsure_labels"].sum()),
               dont_care_detections=int(per_tile["dont_care_detections"].sum()), warnings=warnings,
               tile_set_id=rec.get("tile_set_id"), video_sha256=rec.get("video_sha256"),
               labels_sha256=_file_sha(labels), run_config_sha256=summary.get("config_sha256"),
               run_git_commit=summary.get("git_commit"), run_dir=str(run_dir), tile_dir=str(tile_dir),
               per_tile=per_tile.to_dict(orient="records"))
    return res


def inter_labeler_f1(labels_a, labels_b, match_px: float | None = None, cfg: dict | None = None,
                     manifest: str | Path | None = None, tags: tuple[str, str] = (TAG, "user-labeled")
                     ) -> dict[str, Any]:
    """Agreement of two labelers on the tiles both labelled: F1 = 2 matches / (labels of a + labels of b).

    Labels are matched one to one within labels.match_px tile pixels (tile pixels are source
    pixels); unsure labels (below labels.min_confidence) are don't care on either side. With
    the tile folder's manifest, tile IDs are checked against it, labels outside their tile
    are left out (and counted) as in score_labels, and the bootstrap is over frames;
    otherwise over tiles.
    """
    import pandas as pd

    cfg = cfg or load_config()
    lc = _lcfg(cfg)
    m = float(lc.get("match_px", 3.0) if match_px is None else match_px)
    mc = float(lc.get("min_confidence", 0.75))
    a, b = read_labels(labels_a), read_labels(labels_b)
    both = sorted(set(a["tile_id"]) & set(b["tile_id"]))
    unit = {t: t for t in both}
    box: dict[str, tuple[float, float]] = {}
    if manifest is not None:
        man = _read_manifest(Path(manifest)).set_index("tile_id")
        unknown = sorted((set(a["tile_id"]) | set(b["tile_id"])) - set(man.index))
        if unknown:
            raise ValueError(f"labels name tiles that are not in the manifest: {unknown[:10]}")
        start = man["run_start_s"] if "run_start_s" in man else pd.Series(0.0, index=man.index)
        unit = {t: f"{float(start[t]):g}:{int(man.loc[t, 'frame'])}" for t in both}
        if {"w", "h"} <= set(man.columns):
            box = {t: (float(man.loc[t, "w"]), float(man.loc[t, "h"])) for t in both}
    rows, outside = [], 0
    for t in both:
        pa, sa = _points(a[a["tile_id"] == t], mc)
        pb, sb = _points(b[b["tile_id"] == t], mc)
        if t in box:
            ka, kb = _in_tile(pa, 0.0, 0.0, *box[t]), _in_tile(pb, 0.0, 0.0, *box[t])
            outside += int((~ka).sum() + (~kb).sum())
            pa, sa, pb, sb = pa[ka], sa[ka], pb[kb], sb[kb]
        pairs, dc_a, dc_b = _match_dont_care(pa, sa, pb, sb, m)
        rows.append({"unit": unit[t], "tp": int(len(pairs)), "n_a": int((sa & ~dc_a).sum()),
                     "n_b": int((sb & ~dc_b).sum()), "unsure": int((~sa).sum() + (~sb).sum())})
    df = pd.DataFrame(rows, columns=["unit", "tp", "n_a", "n_b", "unsure"]).groupby("unit").sum()
    # F1 between labelers is the F1 of b scored against a: fp = n_b - tp, fn = n_a - tp.
    res = bootstrap_prf(df["tp"], df["n_b"] - df["tp"], df["n_a"] - df["tp"], int(lc.get("bootstrap", 2000)),
                        int(lc.get("bootstrap_seed", 0)), float(lc.get("ci", 0.95)), int(lc.get("min_frames_ci", 5)))
    return {"f1": res["f1"], "matches": res["tp"], "labels_a": int(df["n_a"].sum()), "labels_b": int(df["n_b"].sum()),
            "unsure_labels": int(df["unsure"].sum()), "labels_outside_tile": outside, "tiles": len(both),
            "units": int(len(df)), "bootstrap_over": "frames" if manifest is not None else "tiles",
            "ci_note": res.get("ci_note"), "replicates_undefined": res["replicates_undefined"],
            "labelers": list(tags), "tag": f"{tags[0]} vs {tags[1]}", "match_px": m, "min_confidence": mc,
            "labels_a_sha256": _file_sha(labels_a), "labels_b_sha256": _file_sha(labels_b)}
