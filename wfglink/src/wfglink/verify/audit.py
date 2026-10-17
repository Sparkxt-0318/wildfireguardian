"""Per-detection audit of a legacy run against blind label tiles (validate/labels.py).

`audit_labels` repeats the matching of `validate.labels.score_labels` tile by tile with the
same helpers (`_points`, `_in_tile`, `_match_dont_care`) and keeps what score_labels only
counts: the status of every detection near a scored tile and of every label. It first calls
score_labels itself and audits exactly the tiles it scored (its frame skips and reserve
rule are not repeated here), then checks that every tile's counts agree with
score_labels' and raises ValueError when they do not, so the table can never silently
disagree with `python -m wfglink label-score`.

Detection rows (kind "detection"), for the detections score_labels looks at: those inside
the tile widened by the largest match radius.
- status: tp (matched to a sure label, also just outside the tile, as in score_labels),
  fp (inside the tile, unmatched, not near an unsure label), dont_care (inside the tile,
  matched to an unsure label) or outside (outside the tile and unmatched; never counted).
- det_row: the row in detections.parquet; det_index: the detection's index within its
  frame, the index track_points.det_index refers to.
- matched_label: the row of the matched label in the labels file (0 based; the CSV line is
  that plus 2), its position and distance; nearest_label_px over every label of the tile.
- track columns from track_points (confirmed tracks only; a detection of a track that never
  got confirmed has none): track status and final static flag, records and hits, whether
  the track was confirmed at that frame (hits so far >= track.confirm_hits, the tracker's
  rule), whether it was flagged static by then (the tracker's static test replayed on the
  track's own records), whether the booth would draw it (`ui.booth_app.confirmed_points`:
  confirmed, not static, measured in this frame, not coasted) and its gate crossings
  (tracks.parquet crossings_pos, crossings_neg).

The track columns replay confirmation and the static test with the track settings of the
config given (by default configs/default.yaml). totals.config_matches_run records whether
that config is the run's (its legacy hash equals summary config_sha256); when it is not,
a warning is returned, or with strict_config a ValueError is raised. The tp, fp and fn
totals do not depend on it.

Label rows (kind "label"): fn (a sure label no detection matched), unsure (below
labels.min_confidence: don't care) and label_outside (outside its tile: a typo, left out
by score_labels too). Each has the distance to the nearest detection of its frame and the
nearest detection within +-2 frames (its frame, offset, row and track).
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.config import load_config

STATUSES_DET = ("tp", "fp", "dont_care", "outside")
STATUSES_LABEL = ("fn", "unsure", "label_outside")
WINDOW_FRAMES = 2            # FN rows: nearest detection within this many frames


def static_flag_frames(points, cfg: dict, fps: float | None, t_origin: float = 0.0,
                       frame_times: tuple[np.ndarray, np.ndarray] | None = None) -> dict[int, int]:
    """Frame at which each static track was flagged static, from its track_points records.

    Replays `Track._static_push` and `Track._static_check` (track/tracker.py) on the
    records of the tracks whose final static flag is set: measured points enter the
    trailing window, and from confirmation on, once the track has existed for
    track.static_seconds, the least-squares speed over the window is tested every frame.
    Running sums in the tracker's order give the same floating point result. t_origin is
    the time of the first analysed frame (the tracker's time origin). A track may be
    flagged while it coasts after its last hit, in frames whose records the tracker trims
    when it finishes; with frame_times (the analysed frames' indices and times) those up to
    track.max_coast frames are replayed as coasted frames too, and such a flag comes after
    every record of the track. Tracks the replay cannot place are left out (their final
    flag is then used for every frame).
    """
    t = cfg["track"]
    confirm = max(2, int(t["confirm_hits"]))
    max_coast = max(0, int(t["max_coast"]))
    window_s, thr = float(t["static_seconds"]), float(t["static_speed_px_s"])
    dt = 1.0 / float(fps) if fps else None
    if dt is None and len(points):
        ft = np.unique(points["t"].to_numpy(float))
        dt = float(np.median(np.diff(ft))) if ft.size > 1 else 0.0
    tol = 0.25 * (dt or 0.0)
    out: dict[int, int] = {}
    if not len(points) or "static" not in points:
        return out
    stat = points[points["static"].astype(bool)]
    for tid, g in stat.groupby("track_id", sort=False):
        g = g.sort_values("frame")
        fr, tt = g["frame"].to_numpy(np.int64), g["t"].to_numpy(float)
        xm, ym, co = g["x_meas"].to_numpy(float), g["y_meas"].to_numpy(float), g["coasted"].to_numpy(bool)
        if frame_times is not None and len(fr):
            fa, ta = frame_times
            k = (fa > fr[-1]) & (fa - fr[-1] <= max_coast)
            if k.any():
                n = int(k.sum())
                fr, tt = np.r_[fr, fa[k]], np.r_[tt, ta[k]]
                xm, ym, co = np.r_[xm, np.full(n, np.nan)], np.r_[ym, np.full(n, np.nan)], np.r_[co, np.ones(n, bool)]
        s = [0.0] * 7
        w: deque = deque()
        hits, t_first = 0, float(tt[0])
        for i in range(len(fr)):
            t_rel = float(tt[i]) - t_origin
            if not co[i]:
                hits += 1
                s[0] += 1.0
                s[1] += t_rel
                s[2] += t_rel * t_rel
                s[3] += xm[i]
                s[4] += ym[i]
                s[5] += t_rel * xm[i]
                s[6] += t_rel * ym[i]
                w.append((t_rel, xm[i], ym[i]))
            if hits < confirm or not float(tt[i]) - t_first >= window_s - tol:
                continue
            cutoff = t_rel - window_s
            while w and w[0][0] <= cutoff - tol:
                a, x, y = w.popleft()
                s[0] -= 1.0
                s[1] -= a
                s[2] -= a * a
                s[3] -= x
                s[4] -= y
                s[5] -= a * x
                s[6] -= a * y
            if s[0] < 3:
                continue
            den = s[0] * s[2] - s[1] * s[1]
            if den <= 0:
                continue
            ux = (s[0] * s[5] - s[1] * s[3]) / den
            uy = (s[0] * s[6] - s[1] * s[4]) / den
            if math.hypot(ux, uy) < thr:
                out[int(tid)] = int(fr[i])
                break
    return out


def _track_lookup(points, tracks, cfg: dict, fps: float | None, t_origin: float,
                  frame_times: tuple[np.ndarray, np.ndarray] | None = None):
    """Per measured record (frame, det_index): track columns, and per track: aggregates."""
    import pandas as pd

    confirm = max(2, int(cfg["track"]["confirm_hits"]))
    if points is None or not len(points):
        return pd.DataFrame(columns=["frame", "det_index", "track_id"]), {}
    p = points.sort_values(["track_id", "frame"], kind="stable")
    meas = ~p["coasted"].astype(bool).to_numpy()
    hits = pd.Series(meas.astype(np.int64), index=p.index).groupby(p["track_id"]).cumsum()
    flagged = static_flag_frames(p, cfg, fps, t_origin, frame_times)
    rec = pd.DataFrame({"frame": p["frame"].to_numpy(np.int64), "det_index": p["det_index"].to_numpy(np.int64),
                        "track_id": p["track_id"].to_numpy(np.int64), "hits_so_far": hits.to_numpy(np.int64)})
    rec = rec[meas & (rec["det_index"].to_numpy() >= 0)]
    agg = p.assign(_meas=meas).groupby("track_id").agg(track_records=("frame", "size"), track_hits=("_meas", "sum"),
                                                       track_status=("status", "first"),
                                                       track_static=("static", "first"))
    info = {int(k): dict(v) for k, v in agg.iterrows()}
    cr = {}
    if tracks is not None and len(tracks) and {"crossings_pos", "crossings_neg"} <= set(tracks.columns):
        cr = {int(r.track_id): (int(r.crossings_pos), int(r.crossings_neg)) for r in tracks.itertuples()}
    for tid, d in info.items():
        d["static_frame"] = flagged.get(tid)
        d["static_replayed"] = (tid in flagged) or not bool(d["track_static"])
        d["crossings_pos"], d["crossings_neg"] = cr.get(tid, (np.nan, np.nan)) if cr else (np.nan, np.nan)
    rec["confirmed_at_frame"] = rec["hits_so_far"].to_numpy() >= confirm
    return rec, info


def _nearest(xy: np.ndarray, pts: np.ndarray) -> tuple[float, int]:
    if not len(pts):
        return float("nan"), -1
    d = np.hypot(pts[:, 0] - xy[0], pts[:, 1] - xy[1])
    k = int(np.argmin(d))
    return float(d[k]), k


def config_matches_run(cfg: dict, summary: dict) -> bool | None:
    """True when cfg (without the verify section) is the config the run's summary hashed,
    None when the summary holds no config_sha256."""
    from wfglink.outputs.process import _legacy_cfg
    from wfglink.provenance import sha256_json

    want = summary.get("config_sha256")
    return None if not want else sha256_json(_legacy_cfg(cfg)) == want


def audit_labels(tile_dir: str | Path, labels, run_dir: str | Path, cfg: dict | None = None,
                 match_px: float | None = None, strict_config: bool = False) -> dict[str, Any]:
    """Audit table of a run against blind labels (see the module notes).

    Returns {"table": DataFrame, "totals": {...}, "score_labels": score_labels' result
    without per_tile, "reproduces_score_labels": True, "warnings": [...]}.
    """
    import pandas as pd

    from wfglink.validate import labels as L
    from wfglink.validate.plausibility import read_table

    cfg = cfg or load_config()
    run_summary = json.loads((Path(run_dir) / "summary.json").read_text(encoding="utf-8"))
    matches = config_matches_run(cfg, run_summary)
    warnings = []
    if matches is False:
        msg = ("the config given is not the run's (config_sha256 differs): confirmed_at_frame, static_at_frame and "
               "booth_drawn use its track settings; pass the run's config files")
        if strict_config:
            raise ValueError(msg)
        warnings.append(msg)
    lc = L._lcfg(cfg)
    m = float(lc.get("match_px", 3.0) if match_px is None else match_px)
    frac = float(lc.get("streak_radius_frac", 0.0))
    min_conf = float(lc.get("min_confidence", 0.75))
    tile_dir, run_dir = Path(tile_dir), Path(run_dir)
    score = L.score_labels(tile_dir, labels, run_dir, cfg, match_px=match_px)
    man = L._read_manifest(tile_dir / L.MANIFEST).set_index("tile_id", drop=False)
    lab = L.read_labels(labels)
    summary = run_summary
    frames = read_table(run_dir, "frames", summary)
    dets = read_table(run_dir, "detections", summary)
    points = read_table(run_dir, "track_points", summary)
    tracks = read_table(run_dir, "tracks", summary)
    analysed = frames[~frames["duplicate"].astype(bool)] if "duplicate" in frames else frames
    t_origin = float(analysed["t"].iloc[0]) if len(analysed) else 0.0
    ftimes = (analysed["frame"].to_numpy(np.int64), analysed["t"].to_numpy(float))
    rec, info = _track_lookup(points, tracks, cfg, (summary.get("input") or {}).get("fps"), t_origin, ftimes)
    rec_key = {(int(f), int(k)): (int(tid), int(h), bool(c)) for f, k, tid, h, c in
               zip(rec["frame"], rec["det_index"], rec["track_id"], rec["hits_so_far"], rec["confirmed_at_frame"])}
    by_frame = {int(k): g for k, g in dets.groupby("frame")} if len(dets) else {}
    t_of = dict(zip(frames["frame"].astype(int), frames["t"].astype(float)))

    def track_cols(f: int, k: int) -> dict[str, Any]:
        hit = rec_key.get((f, k))
        if hit is None:
            return {"track_id": pd.NA}
        tid, h, conf = hit
        d = info.get(tid, {})
        sf = d.get("static_frame")
        static_now = (sf is not None and f >= sf) if d.get("static_replayed") else bool(d.get("track_static"))
        cp, cn = d.get("crossings_pos", np.nan), d.get("crossings_neg", np.nan)
        return {"track_id": tid, "track_status": d.get("track_status"), "track_static": bool(d.get("track_static")),
                "track_records": int(d.get("track_records", 0)), "track_hits": int(d.get("track_hits", 0)),
                "hits_so_far": h, "confirmed_at_frame": conf, "static_at_frame": bool(static_now),
                "static_replayed": bool(d.get("static_replayed")),
                "booth_drawn": bool(conf and not static_now), "crossings_pos": cp, "crossings_neg": cn,
                "track_has_crossing": bool(np.nan_to_num(cp) + np.nan_to_num(cn) > 0)}

    def near_window(f: int, xy: np.ndarray) -> dict[str, Any]:
        best = (float("inf"), None, None)
        # Nearest over frames f - 2 .. f + 2; on a tie the frame closest to f wins.
        for df_ in sorted(range(-WINDOW_FRAMES, WINDOW_FRAMES + 1), key=abs):
            g = by_frame.get(f + df_)
            if g is None or not len(g):
                continue
            dist, k = _nearest(xy, g[["x", "y"]].to_numpy(float))
            if dist < best[0]:
                best = (dist, f + df_, k)
        if best[1] is None:
            return {"nearest_det_window_px": np.nan, "nearest_det_window_frame": pd.NA,
                    "nearest_det_window_offset": pd.NA, "nearest_det_window_row": pd.NA,
                    "nearest_det_window_track_id": pd.NA}
        g = by_frame[best[1]]
        tc = track_cols(best[1], best[2])
        return {"nearest_det_window_px": best[0], "nearest_det_window_frame": best[1],
                "nearest_det_window_offset": best[1] - f, "nearest_det_window_row": int(g.index[best[2]]),
                "nearest_det_window_track_id": tc["track_id"]}

    rows: list[dict[str, Any]] = []
    checks = []
    for pt in score["per_tile"]:
        tid, f = pt["tile_id"], int(pt["frame"])
        tl = man.loc[tid]
        x0, y0, w, h = (float(tl[k]) for k in ("x0", "y0", "w", "h"))
        sub = lab[lab["tile_id"] == tid]
        pts, sure = L._points(sub, min_conf)
        keep = np.isfinite(sub["x"].to_numpy(float)) & np.isfinite(sub["y"].to_numpy(float))
        lrows = sub.index.to_numpy()[keep]
        conf = sub["confidence"].to_numpy(float)[keep]
        if len(lrows) != len(pts):
            raise ValueError(f"tile {tid}: label rows and label points disagree")
        ok = L._in_tile(pts, 0.0, 0.0, w, h)
        g = by_frame.get(f)
        allxy = g[["x", "y"]].to_numpy(float) if g is not None else np.zeros((0, 2))
        base = {"tile_id": tid, "frame": f, "t": t_of.get(f, float(tl["t"]))}
        for i in np.flatnonzero(~ok):
            xy = pts[i] + [x0, y0]
            rows.append({**base, "kind": "label", "status": "label_outside", "label_row": int(lrows[i]),
                         "x": xy[0], "y": xy[1], "label_confidence": conf[i]})
        pts, sure, lrows, conf = pts[ok] + [x0, y0], sure[ok], lrows[ok], conf[ok]
        d = allxy
        length = g["length"].to_numpy(float) if g is not None and "length" in g else np.zeros(len(d))
        rad = np.maximum(m, frac * np.nan_to_num(length, nan=0.0))
        near = L._in_tile(d, x0, y0, w, h, float(rad.max()) if rad.size else m)
        idx = np.flatnonzero(near)
        d, rad, length = d[near], rad[near], length[near]
        inside = L._in_tile(d, x0, y0, w, h)
        pairs, dc_det, _ = L._match_dont_care(d, np.ones(len(d), bool), pts, sure, rad)
        partner = np.full(len(d), -1, np.int64)
        partner[pairs[:, 0]] = pairs[:, 1]
        matched = partner >= 0
        status = np.where(matched, "tp", np.where(inside & dc_det, "dont_care", np.where(inside, "fp", "outside")))
        for j in range(len(d)):
            k = int(idx[j])
            lab_j = int(partner[j])
            nd, _ = _nearest(d[j], pts)
            r = {**base, "kind": "detection", "status": str(status[j]), "det_row": int(g.index[k]), "det_index": k,
                 "x": d[j, 0], "y": d[j, 1], "length": length[j], "radius_px": rad[j], "inside_tile": bool(inside[j]),
                 "nearest_label_px": nd}
            if lab_j >= 0:
                r.update(matched_label=int(lrows[lab_j]), label_x=pts[lab_j, 0], label_y=pts[lab_j, 1],
                         label_dist_px=float(np.hypot(*(d[j] - pts[lab_j]))))
            r.update(track_cols(f, k))
            rows.append(r)
        hit_labels = set(partner[matched].tolist())
        for i in range(len(pts)):
            if sure[i] and i in hit_labels:
                continue
            nd, nk = _nearest(pts[i], allxy)
            r = {**base, "kind": "label", "status": "fn" if sure[i] else "unsure", "label_row": int(lrows[i]),
                 "x": pts[i, 0], "y": pts[i, 1], "label_confidence": conf[i], "nearest_det_px": nd,
                 "nearest_det_row": int(g.index[nk]) if nk >= 0 else pd.NA}
            r.update(near_window(f, pts[i]))
            rows.append(r)
        mine = {"tp": int(matched.sum()), "fp": int((status == "fp").sum()),
                "fn": int(sure.sum() - matched.sum()), "dont_care_detections": int((status == "dont_care").sum()),
                "detections": int(inside.sum()), "labels": int(sure.sum()), "unsure_labels": int((~sure).sum())}
        theirs = {k: int(pt[k]) for k in mine}
        if mine != theirs:
            checks.append(f"{tid}: audit {mine} but score_labels {theirs}")
    if checks:
        raise ValueError("the audit does not reproduce score_labels: " + "; ".join(checks[:5]))
    cols = ["kind", "tile_id", "frame", "t", "status", "det_row", "det_index", "x", "y", "length", "radius_px",
            "inside_tile", "matched_label", "label_x", "label_y", "label_dist_px", "nearest_label_px", "track_id",
            "track_status", "track_static", "track_records", "track_hits", "hits_so_far", "confirmed_at_frame",
            "static_at_frame", "static_replayed", "booth_drawn", "crossings_pos", "crossings_neg",
            "track_has_crossing", "label_row", "label_confidence", "nearest_det_px", "nearest_det_row",
            "nearest_det_window_px", "nearest_det_window_frame", "nearest_det_window_offset",
            "nearest_det_window_row", "nearest_det_window_track_id"]
    table = pd.DataFrame(rows, columns=cols)
    unknown = set(table["status"]) - set(STATUSES_DET + STATUSES_LABEL)
    if unknown:
        raise ValueError(f"audit statuses {sorted(unknown)} are not defined")
    for c in ("det_row", "det_index", "matched_label", "track_id", "track_records", "track_hits", "hits_so_far",
              "label_row", "nearest_det_row", "nearest_det_window_frame", "nearest_det_window_offset",
              "nearest_det_window_row", "nearest_det_window_track_id"):
        table[c] = pd.array(table[c].tolist(), dtype="Int64")
    for c in ("inside_tile", "track_static", "confirmed_at_frame", "static_at_frame", "static_replayed",
              "booth_drawn", "track_has_crossing"):
        table[c] = pd.array(table[c].tolist(), dtype="boolean")
    st = table["status"]
    det = table[table["kind"] == "detection"]
    fp = det[det["status"] == "fp"]
    totals = {"tp": int((st == "tp").sum()), "fp": int((st == "fp").sum()), "fn": int((st == "fn").sum()),
              "dont_care_detections": int((st == "dont_care").sum()), "outside_detections": int((st == "outside").sum()),
              "unsure_labels": int((st == "unsure").sum()), "labels_outside_tile": int((st == "label_outside").sum()),
              "tiles": len(score["per_tile"]), "frames": int(score["frames"]),
              "fp_with_track": int(fp["track_id"].notna().sum()),
              "fp_booth_drawn": int(fp["booth_drawn"].fillna(False).sum()),
              "fp_track_with_crossing": int(fp["track_has_crossing"].fillna(False).sum()),
              "tp_booth_drawn": int(det.loc[det["status"] == "tp", "booth_drawn"].fillna(False).sum()),
              "config_matches_run": matches}
    for k in ("tp", "fp", "fn", "dont_care_detections", "labels_outside_tile", "unsure_labels"):
        if totals[k] != int(score[k]):
            raise ValueError(f"the audit's {k} {totals[k]} differs from score_labels' {score[k]}")
    return {"table": table, "totals": totals, "score_labels": {k: v for k, v in score.items() if k != "per_tile"},
            "reproduces_score_labels": True, "warnings": warnings}


def write_audit(res: dict[str, Any], out: str | Path) -> Path:
    """Write the audit table (parquet, or csv by suffix) and a JSON of totals next to it."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".csv":
        res["table"].to_csv(out, index=False)
    else:
        out = out.with_suffix(".parquet")
        res["table"].to_parquet(out, index=False)
    meta = {"totals": res["totals"], "reproduces_score_labels": res["reproduces_score_labels"],
            "score_labels": res["score_labels"], "warnings": res.get("warnings", []), "table": out.name}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return out
