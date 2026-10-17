"""Inspectable PNG sheets for audit items: what the video shows around a detection or a label.

An item is a frame and a position in a run's coordinates (inside the ROI crop, pixel
centres at integers, as in detections.parquet), with an optional track id, a category
(for example the audit status) and an id. The frames come from the run's own video,
decoded as `process` decodes it (FileSource from the run's segment start, then the ROI
crop), so frame indices and times are the run's; the video's SHA-256 must equal the run's
input.sha256.

One sheet per item: frames t-2 .. t+2 (the run's frame indices f-2 .. f+2), each as a
64 px crop enlarged 4x by nearest neighbour (left untouched apart from ticks on its
border that point at the item) above a 192 px crop at full resolution with marks: a yellow
ring around the item, the track's measured point in that frame (green ring; a green cross
when it coasted) and its path over the five frames, and the other detections of the frame
(small cyan crosses). A caption gives the clip, its credit line (data/clips.csv, found by
the video's SHA-256, or a given string), the item, its frame and time and the track. One
contact sheet per category shows the items' centre-frame crops side by side. A PNG larger
than max_kb is written as JPEG at quality 85 instead.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np

from wfglink import PROJECT_ROOT

CLIPS_CSV = PROJECT_ROOT / "data" / "clips.csv"
YELLOW, GREEN, CYAN, GREY = (0, 220, 255), (60, 220, 60), (255, 220, 0), (150, 150, 150)
_FONT = cv2.FONT_HERSHEY_SIMPLEX


@dataclass
class SheetItem:
    frame: int
    x: float
    y: float
    track_id: int | None = None
    item_id: str = ""
    category: str = "items"
    note: str = ""


def items_from_table(df, category_col: str | None = None, limit: int | None = None,
                     categories: Iterable[str] | None = None) -> list[SheetItem]:
    """Items from a table with frame, x, y and optional track_id, item_id, category (or
    status, as in the audit table) and note columns."""
    import pandas as pd

    col = category_col or ("category" if "category" in df else "status" if "status" in df else None)
    if categories is not None and col is not None:
        df = df[df[col].isin(list(categories))]
    out = []
    for i, r in enumerate(df.itertuples(index=False)):
        d = r._asdict()
        tid = d.get("track_id")
        tid = None if tid is None or (isinstance(tid, float) and np.isnan(tid)) or str(tid) == "<NA>" else int(tid)
        iid = d.get("item_id")
        if iid is None or str(iid) in ("", "nan", "<NA>"):
            # Audit rows: named by tile and detection row (d) or label row (l), else by position.
            pre = f"{d.get('tile_id')}_" if d.get("tile_id") is not None else ""
            dr, lr = d.get("det_row"), d.get("label_row")
            iid = (f"{pre}d{int(dr)}" if dr is not None and not pd.isna(dr) else
                   f"{pre}l{int(lr)}" if lr is not None and not pd.isna(lr) else f"{pre}{i:04d}")
        out.append(SheetItem(int(d["frame"]), float(d["x"]), float(d["y"]), tid, str(iid),
                             str(d.get(col)) if col else "items", str(d.get("note") or "")))
    if limit is not None:
        per: dict[str, int] = {}
        keep = []
        for it in out:
            per[it.category] = per.get(it.category, 0) + 1
            if per[it.category] <= limit:
                keep.append(it)
        out = keep
    return out


def credit_line(video_sha256: str | None = None, clip_id: str | None = None,
                clips_csv: str | Path = CLIPS_CSV) -> tuple[str, str | None]:
    """(credit line, clip id) from data/clips.csv: the row with this video SHA-256, else
    the row with this clip id; ("", clip_id) when there is none."""
    p = Path(clips_csv)
    if not p.exists():
        return "", clip_id
    with open(p, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for key, val in (("sha256", video_sha256), ("clip_id", clip_id)):
        if val:
            for r in rows:
                if (r.get(key) or "").strip() == val:
                    return (r.get("credit_line") or "").strip(), r.get("clip_id") or clip_id
    return "", clip_id


def _ascii(text: str) -> str:
    return str(text).encode("ascii", "replace").decode("ascii")


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", str(text)).strip("_") or "item"


def write_image(img: np.ndarray, path: Path, max_kb: float = 300.0, jpeg_quality: int = 85) -> Path:
    """PNG, or JPEG at jpeg_quality when the PNG would be larger than max_kb. Returns the path written."""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError(f"cannot encode {path.name}")
    if len(buf) > max_kb * 1024:
        path = path.with_suffix(".jpg")
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)])
    else:
        path = path.with_suffix(".png")
    path.write_bytes(buf.tobytes())
    return path


def crop_at(img: np.ndarray, cx: int, cy: int, size: int, fill: int = 60) -> np.ndarray:
    """size x size crop whose pixel (size // 2, size // 2) is image pixel (cx, cy); pixels
    outside the image are fill."""
    h, w = img.shape[:2]
    half = size // 2
    out = np.full((size, size) + img.shape[2:], fill, img.dtype)
    x0, y0 = cx - half, cy - half
    a, b = max(0, x0), max(0, y0)
    c, d = min(w, x0 + size), min(h, y0 + size)
    if c > a and d > b:
        out[b - y0:d - y0, a - x0:c - x0] = img[b:d, a:c]
    return out


def run_source(run_dir: str | Path, clip: str | Path | None = None) -> dict[str, Any]:
    """The video, segment start, ROI and clip of a run (summary.json), checked by SHA-256."""
    from wfglink.provenance import sha256_file

    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    inp = summary.get("input") or {}
    video, clip_id = Path(str(inp.get("path") or "")), None
    if clip is not None:
        c = Path(clip)
        if c.suffix in (".yaml", ".yml"):
            from wfglink.validate.clips import clip_id as _cid
            from wfglink.validate.clips import load_clip_settings

            cc, video, _ = load_clip_settings(c)
            clip_id = _cid(cc, video)
        else:
            video = c
    if not video.is_file():
        raise ValueError(f"the run's video {video} is not there; pass the clip (video or settings file)")
    sha = sha256_file(video)
    if inp.get("sha256") and sha != inp["sha256"]:
        raise ValueError(f"{video} (SHA-256 {sha[:12]}) is not the video the run analysed ({str(inp['sha256'])[:12]})")
    W, H = inp.get("source_size") or [inp.get("width"), inp.get("height")]
    roi = inp.get("roi_px") or [0, 0, W, H]
    return {"video": video, "sha256": sha, "start_s": float((inp.get("segment_s") or [0.0])[0] or 0.0),
            "roi": tuple(int(v) for v in roi), "clip_id": clip_id, "summary": summary}


def _border_ticks(cell: np.ndarray, px: float, py: float, colour, n: int = 7) -> None:
    """Ticks on the four borders of an enlarged crop pointing at (px, py) in cell pixels."""
    h, w = cell.shape[:2]
    xi, yi = int(round(px)), int(round(py))
    if 0 <= xi < w:
        cell[:n, max(0, xi - 1):xi + 2] = colour
        cell[h - n:, max(0, xi - 1):xi + 2] = colour
    if 0 <= yi < h:
        cell[max(0, yi - 1):yi + 2, :n] = colour
        cell[max(0, yi - 1):yi + 2, w - n:] = colour


def _text(img: np.ndarray, text: str, org: tuple[int, int], scale: float = 0.45, colour=(20, 20, 20)) -> None:
    cv2.putText(img, _ascii(text), org, _FONT, scale, colour, 1, cv2.LINE_AA)


def render_sheets(run_dir: str | Path, items: list[SheetItem], out_dir: str | Path, clip: str | Path | None = None,
                  credit: str | None = None, offsets: Iterable[int] = (-2, -1, 0, 1, 2), zoom_px: int = 64,
                  context_px: int = 192, scale: int = 4, max_kb: float = 300.0, contact_cols: int = 6,
                  contact_page: int = 36) -> dict[str, Any]:
    """Write one sheet per item and a contact sheet per category (see the module notes)."""
    import pandas as pd

    from wfglink.io.sources import FileSource
    from wfglink.validate.plausibility import read_table

    run_dir, out = Path(run_dir), Path(out_dir)
    src = run_source(run_dir, clip)
    cr, cid = credit_line(src["sha256"], src["clip_id"])
    credit = cr if credit is None else credit
    clip_id = cid or src["clip_id"] or src["video"].stem
    offsets = list(offsets)
    want: dict[int, list[int]] = {}
    for i, it in enumerate(items):
        for o in offsets:
            if it.frame + o >= 0:
                want.setdefault(it.frame + o, []).append(i)
    summary = src["summary"]
    frames_tab = read_table(run_dir, "frames", summary)
    run_t = dict(zip(frames_tab["frame"].astype(int), frames_tab["t"].astype(float))) if frames_tab is not None else {}
    dets = read_table(run_dir, "detections", summary)
    det_by = {}
    if dets is not None and len(dets):
        d = dets[dets["frame"].isin(set(want))]
        det_by = {int(k): g[["x", "y"]].to_numpy(float) for k, g in d.groupby("frame")}
    tids = {it.track_id for it in items if it.track_id is not None}
    trk: dict[int, Any] = {}
    if tids:
        pts = read_table(run_dir, "track_points", summary)
        if pts is not None and len(pts):
            pts = pts[pts["track_id"].isin(tids)]
            trk = {int(k): g.set_index("frame") for k, g in pts.groupby("track_id")}

    # One decoding pass; keep only the crops (small) of the frames wanted.
    x0r, y0r, x1r, y1r = src["roi"]
    zoom: dict[tuple[int, int], np.ndarray] = {}
    ctx: dict[tuple[int, int], np.ndarray] = {}
    t_of: dict[int, float] = {}
    mismatch = []
    last = max(want) if want else -1
    fs = FileSource(src["video"], start_s=src["start_s"])
    fs.open()
    try:
        while last >= 0 and (f := fs.read()) is not None:
            if f.index > last:
                break
            if f.index not in want:
                continue
            img = f.image[y0r:y1r, x0r:x1r]
            t_of[int(f.index)] = float(f.t)
            if int(f.index) in run_t and abs(run_t[int(f.index)] - float(f.t)) > 1e-6:
                mismatch.append(int(f.index))
            for i in want[int(f.index)]:
                cx, cy = int(round(items[i].x)), int(round(items[i].y))
                zoom[(i, int(f.index))] = crop_at(img, cx, cy, zoom_px)
                ctx[(i, int(f.index))] = crop_at(img, cx, cy, context_px)
    finally:
        fs.close()
    if mismatch:
        raise ValueError(f"frames {mismatch[:5]} decode at other times than the run names them")

    out.mkdir(parents=True, exist_ok=True)
    cell = zoom_px * scale
    gap, head, lab_h = 8, 74, 18
    rows = []
    for i, it in enumerate(items):
        W = gap + len(offsets) * (cell + gap)
        sheet = np.full((head + 2 * (lab_h + cell) + 2 * gap, W, 3), 245, np.uint8)
        t_c = t_of.get(it.frame, run_t.get(it.frame))
        _text(sheet, f"{clip_id}   {credit}", (gap, 18), 0.5)
        _text(sheet, f"item {it.item_id}   {it.category}   frame {it.frame}   t {t_c:.3f} s   x {it.x:.1f}   y {it.y:.1f}"
              f"   track {it.track_id if it.track_id is not None else 'none'}" if t_c is not None else
              f"item {it.item_id}   {it.category}   frame {it.frame} (not decoded)", (gap, 40), 0.5)
        _text(sheet, f"{it.note}   run {run_dir.name}   video {src['sha256'][:12]}   zoom {zoom_px} px x{scale}, "
              f"context {context_px} px x1 (ROI coordinates)", (gap, 62), 0.4)
        tr = trk.get(it.track_id) if it.track_id is not None else None
        path_pts = []
        if tr is not None:
            for o in offsets:
                if it.frame + o in tr.index:
                    r = tr.loc[it.frame + o]
                    path_pts.append((float(r["x"]), float(r["y"])))
        for j, o in enumerate(offsets):
            fr = it.frame + o
            x = gap + j * (cell + gap)
            yz, yc = head + lab_h, head + 2 * lab_h + cell + gap
            label = f"{o:+d}  frame {fr}" + (f"  t {t_of[fr]:.3f}" if fr in t_of else "  (no frame)")
            _text(sheet, label, (x, head + 13), 0.42)
            if (i, fr) not in zoom:
                sheet[yz:yz + cell, x:x + cell] = 200
                sheet[yc:yc + cell, x:x + cell] = 200
                continue
            z = cv2.resize(zoom[(i, fr)], (cell, cell), interpolation=cv2.INTER_NEAREST)
            half = zoom_px // 2
            px = (it.x - (round(it.x) - half) + 0.5) * scale - 0.5
            py = (it.y - (round(it.y) - half) + 0.5) * scale - 0.5
            _border_ticks(z, px, py, YELLOW)
            sheet[yz:yz + cell, x:x + cell] = z
            c = ctx[(i, fr)].copy()
            ch = context_px // 2
            ox, oy = round(it.x) - ch, round(it.y) - ch          # crop origin in ROI pixels

            def to_c(p):
                return int(round(p[0] - ox)), int(round(p[1] - oy))

            zh = zoom_px // 2
            cv2.rectangle(c, (ch - zh, ch - zh), (ch + zh - 1, ch + zh - 1), GREY, 1)
            dd = det_by.get(fr)
            if dd is not None:
                for p in dd:
                    q = to_c(p)
                    if 0 <= q[0] < context_px and 0 <= q[1] < context_px and np.hypot(p[0] - it.x, p[1] - it.y) > 2:
                        cv2.line(c, (q[0] - 2, q[1]), (q[0] + 2, q[1]), CYAN, 1)
                        cv2.line(c, (q[0], q[1] - 2), (q[0], q[1] + 2), CYAN, 1)
            if len(path_pts) > 1:
                cv2.polylines(c, [np.array([to_c(p) for p in path_pts], np.int32)], False, GREEN, 1, cv2.LINE_AA)
            if tr is not None and fr in tr.index:
                r = tr.loc[fr]
                if bool(r["coasted"]) or not np.isfinite(r["x_meas"]):
                    q = to_c((r["x"], r["y"]))
                    cv2.drawMarker(c, q, GREEN, cv2.MARKER_TILTED_CROSS, 7, 1)
                else:
                    cv2.circle(c, to_c((r["x_meas"], r["y_meas"])), 5, GREEN, 1, cv2.LINE_AA)
            cv2.circle(c, to_c((it.x, it.y)), 10, YELLOW, 1, cv2.LINE_AA)
            pad = (cell - context_px) // 2
            sheet[yc:yc + cell, x:x + cell] = 30
            sheet[yc + pad:yc + pad + context_px, x + pad:x + pad + context_px] = c
        name = f"{_safe(it.category)}_{_safe(it.item_id)}"
        path = write_image(sheet, out / name, max_kb)
        rows.append({"item_id": it.item_id, "category": it.category, "frame": it.frame, "t": t_c, "x": it.x, "y": it.y,
                     "track_id": it.track_id, "note": it.note, "sheet": path.name})

    # Contact sheets: the centre frame's enlarged crop of every item of a category.
    contacts = []
    for cat in dict.fromkeys(it.category for it in items):
        idx = [i for i, it in enumerate(items) if it.category == cat]
        for page in range(0, len(idx), contact_page):
            sel = idx[page:page + contact_page]
            ncol = min(contact_cols, len(sel))
            nrow = -(-len(sel) // ncol)
            img = np.full((30 + nrow * (cell + lab_h + gap) + gap, max(720, gap + ncol * (cell + gap)), 3), 245,
                          np.uint8)
            _text(img, f"{clip_id}   {credit}   {cat}: items {page + 1} to {page + len(sel)} of {len(idx)}",
                  (gap, 20), 0.5)
            for k, i in enumerate(sel):
                it = items[i]
                x, y = gap + (k % ncol) * (cell + gap), 30 + (k // ncol) * (cell + lab_h + gap)
                _text(img, f"{it.item_id}  f{it.frame}  tr {it.track_id if it.track_id is not None else '-'}",
                      (x, y + 13), 0.4)
                if (i, it.frame) in zoom:
                    z = cv2.resize(zoom[(i, it.frame)], (cell, cell), interpolation=cv2.INTER_NEAREST)
                    half = zoom_px // 2
                    _border_ticks(z, (it.x - (round(it.x) - half) + 0.5) * scale - 0.5,
                                  (it.y - (round(it.y) - half) + 0.5) * scale - 0.5, YELLOW)
                    img[y + lab_h:y + lab_h + cell, x:x + cell] = z
            p = write_image(img, out / f"contact_{_safe(cat)}_{page // contact_page:02d}", max_kb)
            contacts.append(p.name)
    man = pd.DataFrame(rows, columns=["item_id", "category", "frame", "t", "x", "y", "track_id", "note", "sheet"])
    man["track_id"] = pd.array(man["track_id"].tolist(), dtype="Int64")
    man.to_csv(out / "sheets.csv", index=False)
    rec = {"run_dir": str(run_dir), "video": str(src["video"]), "video_sha256": src["sha256"], "clip_id": clip_id,
           "credit_line": credit, "start_s": src["start_s"], "roi_px": list(src["roi"]), "offsets": offsets,
           "zoom_px": zoom_px, "context_px": context_px, "scale": scale, "max_kb": max_kb, "items": len(items),
           "sheets": [r["sheet"] for r in rows], "contact_sheets": contacts,
           "marks": "yellow: item (ring in the context crop, border ticks on the zoom); green: the track's measured "
                    "point (ring), coasted prediction (cross) and path; cyan: other detections; grey box: the zoom area"}
    (out / "sheets.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec
