"""`python -m wfglink validate --suite ember`: how well phones are found, tracked and timed.

1. Synthetic scenes with ground truth (wfglink.ember.synth.SCENES, fixed seeds; made once
   into validate.ember.work_dir and made again when the generator or the settings change),
   plus a synthetic ruler move. The pipeline gets the synthetic camera's exact focal length,
   so the speed error is the tracker's, not the field of view's. Per frame, a phone is
   required when it faces the camera (turned less than validate.ember.facing_max_yaw_deg) and
   at least validate.ember.min_vis_frac of its disc is in the picture and not hidden; a phone
   turned up to validate.ember.dont_care_yaw_deg, or partly hidden, is neither required nor a
   false ember. The embers seen in a frame are matched to phones (Hungarian, within
   validate.ember.match_frac of the disc's apparent diameter, at least
   validate.ember.match_min_px). Reported per scene and pooled:
   - precision and recall, and recall after acquisition (each phone's first
     validate.ember.acquire_s in the clip left out: an ember shows only once it has moved);
   - MOTA = 1 - (misses + false embers + ID switches) / required phones;
   - ID switches per phone per minute (a phone's matched track changes), and the persistent
     ones: the same count after a phone's matched-track runs shorter than
     validate.ember.persistent_run_s are left out (a flip for a frame or two while two phones
     touch, which no visitor sees);
   - false tracks per minute, and those on static lights (a false track whose points stay
     within validate.ember.static_tol_px of a light's box);
   - speed error at the standing distance (phones within validate.ember.stand_tol_m of
     ember.distance_m, true speed at least validate.ember.min_speed_m_s): the screen speed (the
     least-squares speed over the last ember.track.speed_window_s) against the true speed at
     the middle of that window, and against the true speed at that moment (which adds the
     window's lag of half its length);
   - near_far: how phones at 1 m and 3 m read when speeds are measured at the standing
     distance (expected: standing distance / true distance; the stated limit).
2. data/raw/ember_free.*: the phone moved freely at the standing spot (no truth): tracks,
   most embers at once (against --phones), probable ID switches per minute (a new ember
   starting soon after and near where one ended), coverage (frames with an ember seen) and
   embers on static lights.
3. data/raw/ember_ruler.* (and the synthetic ruler): rest at the 0 mark, a move to the
   100 cm mark in about 1 s, rest. The move time comes from the video (the phone leaves
   validate.ember.ruler.move_tol_frac of the path from its first rest, and arrives within it
   of its second); true mean speed = path length / move time; compared with the screen's mean
   speed (its speeds integrated from the move's start to its end plus one speed window, over
   the move time) and with the measured displacement between the two rests.

The synthetic scenes are the set the detector and tracker were built on (their settings were
chosen while looking at them), so they are not held out: the report says so ("tuned_on": true)
and so does the summary. Goals (validate.ember.goals, fixed before measuring) are reported as
met or missed: on the synthetic scenes (recall, static-light tracks, ID switches, speed), on
ember_ruler (its displacement and mean speed errors against the speed goal) and on ember_free
(its probable ID switches against the ID-switch goal); n/a when a recording is missing.
Writes validate.ember.report (results/validation/ember_report.json) and prints a summary.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment

from wfglink import PROJECT_ROOT
from wfglink.ember import synth
from wfglink.ember.pipeline import EmberPipeline

VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm")


def _v(cfg: dict) -> dict[str, Any]:
    return ((cfg.get("validate") or {}).get("ember") or {})


def _path(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _num(x: Any, nd: int = 4) -> Any:
    if x is None:
        return None
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def run_pipeline(video: str | Path, cfg: dict, max_seconds: float | None = None) -> EmberPipeline:
    """Every frame of a file through the pipeline, recording each frame's embers."""
    from wfglink.io.sources import FileSource

    pipe = EmberPipeline(cfg)
    pipe.record()
    with FileSource(video) as src:
        while True:
            f = src.read()
            if f is None or (max_seconds is not None and f.t > max_seconds):
                break
            pipe.process(f)
    return pipe


# Synthetic scenes ------------------------------------------------------------------------------

def scene_clip(name: str, cfg: dict, work_dir: Path, seconds: float | None = None,
               size: tuple[int, int] | None = None) -> Path:
    """The scene's clip in work_dir, made when missing (or when its settings changed)."""
    v = _v(cfg)
    seconds = float(seconds or v.get("seconds", 20))
    size = tuple(size or v.get("size", [1280, 720]))
    fps, crf, hfov = float(v.get("fps", 30)), int(v.get("crf", 23)), float(v.get("hfov_deg", 70.0))
    seed = int(v.get("seed", 2026)) + sum(map(ord, name))
    spec = synth.SCENES.get(name, {"ruler": True})
    key = synth.scene_key(name, spec, size, fps, seconds, crf, seed, hfov)
    stem = f"{name}_{key}"
    video = work_dir / f"{stem}.mp4"
    if video.exists() and video.with_suffix(".json").exists():
        return video
    if name == "ruler":
        sc = synth.ruler_scene(size=size, fps=fps, seed=seed, hfov_deg=hfov)
    else:
        sc = synth.make_scene(name, size=size, fps=fps, seconds=seconds, seed=seed, hfov_deg=hfov)
    synth.write_scene_clip(sc, work_dir, crf=crf, stem=stem)
    return video


def _scene_cfg(cfg: dict, meta: dict) -> dict:
    """The config for a synthetic scene: its camera's exact focal length, and the scenes'
    standing distance (synth.STANDING_M), whatever this machine's booth uses."""
    c = copy.deepcopy(cfg)
    c.setdefault("camera", {})["focal_px"] = float(meta["focal_px"])
    c.setdefault("ember", {})["calibration"] = {"size": list(meta["size"]), "camera": None, "target": "synthetic"}
    c["ember"]["distance_m"] = synth.STANDING_M
    # The scenes test the tracker with up to six phones; the booth's own cap (ember.max_tracks) is lower.
    c["ember"]["max_tracks"] = max(int(c["ember"].get("max_tracks", 6)), int(_v(cfg).get("max_tracks", 6)))
    return c


def evaluate_scene(video: str | Path, cfg: dict) -> dict[str, Any]:
    """Run the pipeline on a synthetic clip and score it against its truth."""
    truth, meta = synth.load_truth(video)
    c = _scene_cfg(cfg, meta)
    pipe = run_pipeline(video, c)
    return score_scene(pipe, truth, meta, c)


def _boxes_mirrored(meta: dict, width: int) -> list[tuple[float, float, float, float]]:
    out = []
    for lt in meta.get("lights", []):
        x0, y0, x1, y1 = lt["box"]
        out.append((width - 1 - x1, y0, width - 1 - x0, y1))
    return out


def _dist_to_box(x: float, y: float, b: tuple[float, float, float, float]) -> float:
    dx = max(b[0] - x, 0.0, x - b[2])
    dy = max(b[1] - y, 0.0, y - b[3])
    return math.hypot(dx, dy)


def score_scene(pipe: EmberPipeline, truth: dict[str, np.ndarray], meta: dict, cfg: dict) -> dict[str, Any]:
    v = _v(cfg)
    W, H = (int(s) for s in meta["size"])
    fps = float(meta["fps"])
    window = float(((cfg.get("ember") or {}).get("track") or {}).get("speed_window_s", 0.2))
    hist = pipe.history or []
    n = min(len(hist), len(truth["t"]))
    P = truth["x"].shape[1] if truth["x"].ndim == 2 else 0
    xm = (W - 1) - truth["x"][:n] if P else np.zeros((n, 0))
    ym = truth["y"][:n] if P else np.zeros((n, 0))
    yaw = np.abs(truth["yaw"][:n]) if P else np.zeros((n, 0))
    vis = truth["vis"][:n] if P else np.zeros((n, 0))
    inside = (xm >= 0) & (xm < W) & (ym >= 0) & (ym < H)
    required = (yaw <= float(v.get("facing_max_yaw_deg", 45))) & (vis >= float(v.get("min_vis_frac", 0.7))) & inside
    dont_care = ~required & (vis > 0) & (yaw < float(v.get("dont_care_yaw_deg", 75)))
    radius = np.maximum(float(v.get("match_min_px", 12.0)), float(v.get("match_frac", 0.6)) * 2 * truth["r_px"][:n]) \
        if P else np.zeros((n, 0))
    acquire = float(v.get("acquire_s", 1.0))
    first_req = [float(truth["t"][np.argmax(required[:, j])]) if required[:, j].any() else math.inf for j in range(P)]
    tp = fn = fp = idsw = gt = 0
    tp_a = fn_a = 0
    last_id = [None] * P
    runs: list[list[list[Any]]] = [[] for _ in range(P)]      # per phone: [track_id, first t, last t]
    track_frames: dict[int, list[int]] = {}         # track_id -> [frames seen, frames matched to a phone]
    track_pts: dict[int, list[tuple[float, float]]] = {}
    speed_rows = []
    k_half = int(round(window / 2 * fps))
    vx_t, vy_t = (truth["vx"][:n], truth["vy"][:n]) if P else (None, None)
    z_t = truth["z"][:n] if P else None
    for i in range(n):
        dets = [e for e in hist[i]["embers"] if e.get("seen")]
        for e in dets:
            track_frames.setdefault(e["track_id"], [0, 0])[0] += 1
            track_pts.setdefault(e["track_id"], []).append((e["x"], e["y"]))
        cand = [j for j in range(P) if required[i, j] or dont_care[i, j]]
        gt += int(required[i].sum()) if P else 0
        matched_det: set[int] = set()
        matched_ph: dict[int, int] = {}
        if dets and cand:
            cost = np.full((len(cand), len(dets)), 1e9)
            for a, j in enumerate(cand):
                for b, e in enumerate(dets):
                    d = math.hypot(e["x"] - xm[i, j], e["y"] - ym[i, j])
                    if d <= radius[i, j]:
                        cost[a, b] = d
            rr, cc = linear_sum_assignment(cost)
            for a, b in zip(rr, cc):
                if cost[a, b] < 1e9:
                    matched_ph[cand[a]] = b
                    matched_det.add(b)
        for j in range(P):
            in_acq = truth["t"][i] < first_req[j] + acquire
            if required[i, j]:
                if j in matched_ph:
                    tp += 1
                    tp_a += 0 if in_acq else 1
                else:
                    fn += 1
                    fn_a += 0 if in_acq else 1
            if j in matched_ph:
                e = dets[matched_ph[j]]
                track_frames[e["track_id"]][1] += 1
                if last_id[j] is not None and last_id[j] != e["track_id"]:
                    idsw += 1
                last_id[j] = e["track_id"]
                ti = float(truth["t"][i])
                if runs[j] and runs[j][-1][0] == e["track_id"]:
                    runs[j][-1][2] = ti
                else:
                    runs[j].append([e["track_id"], ti, ti])
                if required[i, j] and e.get("speed_m_s") is not None:
                    ic = max(0, i - k_half)          # the middle of the speed window
                    vc = math.hypot(float(vx_t[ic, j]), float(vy_t[ic, j]))
                    vi = math.hypot(float(vx_t[i, j]), float(vy_t[i, j]))
                    speed_rows.append((float(z_t[i, j]), float(e["speed_m_s"]), vc, vi))
        fp += len(dets) - len(matched_det)
    minutes = n / fps / 60.0
    phone_minutes = float(required.sum()) / fps / 60.0 if P else 0.0
    idsw_long = persistent_switches(runs, float(v.get("persistent_run_s", 0.2)) - 0.5 / fps)
    boxes = _boxes_mirrored(meta, W)
    tol = float(v.get("static_tol_px", 30))
    false_tracks, static_tracks = [], []
    for tid, (seen, ok) in track_frames.items():
        if seen and ok / seen < 0.5:
            false_tracks.append(tid)
            pts = np.array(track_pts[tid])
            if boxes and all(min(_dist_to_box(x, y, b) for b in boxes) <= tol for x, y in pts):
                static_tracks.append(tid)
    out: dict[str, Any] = {
        "frames": n, "minutes": _num(minutes), "phones": P, "required": gt, "tp": tp, "fn": fn, "fp": fp,
        "tp_after_acquisition": tp_a, "fn_after_acquisition": fn_a, "phone_minutes": _num(phone_minutes),
        "precision": _num(tp / (tp + fp)) if tp + fp else None,
        "recall": _num(tp / (tp + fn)) if tp + fn else None,
        "recall_after_acquisition": _num(tp_a / (tp_a + fn_a)) if tp_a + fn_a else None,
        "mota": _num(1 - (fn + fp + idsw) / gt) if gt else None,
        "id_switches": idsw,
        "id_switches_per_phone_per_min": _num(idsw / phone_minutes) if phone_minutes else None,
        "id_switches_persistent": idsw_long,
        "id_switches_persistent_per_phone_per_min": _num(idsw_long / phone_minutes) if phone_minutes else None,
        "false_tracks": len(false_tracks), "false_tracks_per_min": _num(len(false_tracks) / minutes) if minutes else None,
        "static_light_tracks": len(static_tracks),
        "static_light_tracks_per_min": _num(len(static_tracks) / minutes) if minutes else None,
        "proc_ms_median": _num(pipe.stats.as_dict()["proc_ms_median"], 2),
        "proc_ms_p95": _num(pipe.stats.as_dict()["proc_ms_p95"], 2),
        "speed_rows": speed_rows,
    }
    return out


def persistent_switches(runs: list[list[list[Any]]], min_run_s: float) -> int:
    """ID switches that last: per phone, its runs of one matched track ([track_id, first t,
    last t] in order), with runs shorter than min_run_s left out and neighbours of the same
    track joined; then the number of changes."""
    n = 0
    for phone in runs:
        kept: list[Any] = []
        for tid, t0, t1 in phone:
            if t1 - t0 < min_run_s:
                continue
            if not kept or kept[-1] != tid:
                kept.append(tid)
        n += max(0, len(kept) - 1)
    return n


def speed_summary(rows: list[tuple[float, float, float, float]], z_center: float, z_tol: float,
                  min_speed: float) -> dict[str, Any]:
    sel = [r for r in rows if abs(r[0] - z_center) <= z_tol and r[2] >= min_speed]
    if not sel:
        return {"n": 0}
    a = np.array(sel)
    rel_w = (a[:, 1] - a[:, 2]) / a[:, 2]
    ok_i = a[:, 3] >= min_speed
    rel_i = (a[ok_i, 1] - a[ok_i, 3]) / a[ok_i, 3]
    return {"n": len(sel), "z_m": z_center,
            "median_abs_rel_err": _num(np.median(np.abs(rel_w))), "p90_abs_rel_err": _num(np.percentile(np.abs(rel_w), 90)),
            "median_rel_err_signed": _num(np.median(rel_w)),
            "median_ratio_measured_over_true": _num(np.median(a[:, 1] / a[:, 2])),
            "vs_instant_median_abs_rel_err": _num(np.median(np.abs(rel_i))) if rel_i.size else None,
            "vs_instant_p90_abs_rel_err": _num(np.percentile(np.abs(rel_i), 90)) if rel_i.size else None}


def pool(scenes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    keys = ("tp", "fn", "fp", "id_switches", "id_switches_persistent", "required", "false_tracks",
            "static_light_tracks", "frames", "tp_after_acquisition", "fn_after_acquisition")
    s = {k: sum(int(sc.get(k) or 0) for sc in scenes.values()) for k in keys}
    minutes = sum(float(sc.get("minutes") or 0) for sc in scenes.values())
    phone_min = sum(float(sc.get("phone_minutes") or 0) for sc in scenes.values())
    ta, fa = s["tp_after_acquisition"], s["fn_after_acquisition"]
    return {**s, "minutes": _num(minutes), "phone_minutes": _num(phone_min),
            "precision": _num(s["tp"] / (s["tp"] + s["fp"])) if s["tp"] + s["fp"] else None,
            "recall": _num(s["tp"] / (s["tp"] + s["fn"])) if s["tp"] + s["fn"] else None,
            "recall_after_acquisition": _num(ta / (ta + fa)) if ta + fa else None,
            "mota": _num(1 - (s["fn"] + s["fp"] + s["id_switches"]) / s["required"]) if s["required"] else None,
            "id_switches_per_phone_per_min": _num(s["id_switches"] / phone_min) if phone_min else None,
            "id_switches_persistent_per_phone_per_min": (_num(s["id_switches_persistent"] / phone_min)
                                                         if phone_min else None),
            "false_tracks_per_min": _num(s["false_tracks"] / minutes) if minutes else None,
            "static_light_tracks_per_min": _num(s["static_light_tracks"] / minutes) if minutes else None}


# Ruler move ------------------------------------------------------------------------------------

def screen_speeds(pts: np.ndarray, window_s: float, min_points: int) -> np.ndarray:
    """The screen's speed (px/s) at every point: the least-squares line through the points of
    the trailing window, as the tracker computes it live (NaN with too few points)."""
    out = np.full(len(pts), np.nan)
    for k in range(len(pts)):
        sel = pts[(pts[:, 0] >= pts[k, 0] - window_s - 1e-9) & (pts[:, 0] <= pts[k, 0])]
        if len(sel) < min_points:
            continue
        tt = sel[:, 0] - sel[:, 0].mean()
        den = float((tt * tt).sum())
        if den > 0:
            out[k] = math.hypot((tt * sel[:, 1]).sum() / den, (tt * sel[:, 2]).sum() / den)
    return out


def ruler_analysis(pts: np.ndarray, m_per_px: float, path_m: float, cfg: dict) -> dict[str, Any]:
    """Rest, move, rest on one track's points (t, x, y); see the module docstring."""
    r = _v(cfg).get("ruler") or {}
    tc = (cfg.get("ember") or {}).get("track") or {}
    window = float(tc.get("speed_window_s", 0.2))
    min_pts = int(tc.get("speed_min_points", 3))
    if len(pts) < 10:
        return {"status": "no track", "reason": "the phone was not tracked long enough"}
    t, xy = pts[:, 0], pts[:, 1:3]
    # Resting: a centred speed over about 0.1 s below the threshold (m/s at the standing distance).
    k = 2
    sp = np.full(len(t), np.inf)
    for i in range(k, len(t) - k):
        sp[i] = math.hypot(*(xy[i + k] - xy[i - k])) / max(t[i + k] - t[i - k], 1e-6) * m_per_px
    rest = sp < float(r.get("rest_speed_m_s", 0.08))
    segs = []
    i = 0
    while i < len(t):
        if rest[i]:
            j = i
            while j + 1 < len(t) and rest[j + 1]:
                j += 1
            if t[j] - t[i] >= float(r.get("rest_min_s", 0.3)):
                segs.append((i, j))
            i = j + 1
        else:
            i += 1
    best = None
    for (a0, a1), (b0, b1) in zip(segs, segs[1:]):
        p0 = np.median(xy[max(a0, a1 - 15):a1 + 1], axis=0)
        p1 = np.median(xy[b0:min(b1, b0 + 15) + 1], axis=0)
        d = float(np.hypot(*(p1 - p0)))
        if best is None or d > best[0]:
            best = (d, a1, b0, p0, p1)
    if best is None:
        return {"status": "no move", "reason": "no rest, move, rest found (rest at each end for at least "
                                               f"{float(r.get('rest_min_s', 0.3)):g} s)", "rests": len(segs)}
    d_px, a1, b0, p0, p1 = best
    tol = float(r.get("move_tol_frac", 0.01)) * d_px
    d0 = np.hypot(xy[:, 0] - p0[0], xy[:, 1] - p0[1])
    d1 = np.hypot(xy[:, 0] - p1[0], xy[:, 1] - p1[1])
    i0 = a1
    while i0 + 1 <= b0 and d0[i0 + 1] <= tol:
        i0 += 1
    i1 = b0
    while i1 - 1 >= i0 and d1[i1 - 1] <= tol:
        i1 -= 1
    # Interpolate the crossing times between frames.
    def cross(i_in: int, i_out: int, dist: np.ndarray) -> float:
        a, b = dist[i_in], dist[i_out]
        if b == a:
            return float(t[i_in])
        return float(t[i_in] + (tol - a) / (b - a) * (t[i_out] - t[i_in]))
    t0 = cross(i0, min(i0 + 1, len(t) - 1), d0)
    t1 = cross(i1, max(i1 - 1, 0), d1)
    move_s = t1 - t0
    lo, hi = float(r.get("min_move_s", 0.2)), float(r.get("max_move_s", 5.0))
    if not (lo <= move_s <= hi):
        return {"status": "no move", "reason": f"the move took {move_s:.2f} s, outside {lo:g} to {hi:g} s"}
    v_screen = screen_speeds(pts, window, min_pts) * m_per_px
    sel = (t >= t0) & (t <= t1 + window) & np.isfinite(v_screen)
    ts, vs = t[sel], v_screen[sel]
    screen_dist = float(np.trapezoid(vs, ts)) if len(ts) >= 2 else float("nan")
    disp_m = d_px * m_per_px
    true_mean = path_m / move_s
    screen_mean = screen_dist / move_s
    return {"status": "ok", "path_m": path_m, "move_s": _num(move_s), "t_start_s": _num(t0), "t_end_s": _num(t1),
            "true_mean_speed_m_s": _num(true_mean), "screen_mean_speed_m_s": _num(screen_mean),
            "screen_speed_rel_err": _num(screen_mean / true_mean - 1),
            "displacement_m": _num(disp_m), "displacement_rel_err": _num(disp_m / path_m - 1),
            "displacement_mean_speed_m_s": _num(disp_m / move_s),
            "screen_peak_speed_m_s": _num(float(np.nanmax(vs)) if len(vs) else None),
            "m_per_px": _num(m_per_px, 7)}


def _longest_shown(pipe: EmberPipeline) -> Any:
    tracks = [tr for tr in pipe.all_tracks() if tr.shown]
    return max(tracks, key=lambda tr: tr.travel, default=None)


def ruler_clip(video: str | Path, cfg: dict, path_m: float) -> dict[str, Any]:
    pipe = run_pipeline(video, cfg)
    tr = _longest_shown(pipe)
    if tr is None:
        return {"status": "no track", "reason": "no ember was shown"}
    out = ruler_analysis(np.array(tr.pts), pipe.m_per_px, path_m, cfg)
    out.update({"calibrated": pipe.calibrated, "scale": pipe.scale_source, "measured_at_m": pipe.distance_m})
    return out


# Free motion (no truth) ------------------------------------------------------------------------

def free_clip(video: str | Path, cfg: dict, phones: int) -> dict[str, Any]:
    v = _v(cfg).get("free") or {}
    pipe = run_pipeline(video, cfg)
    hist = pipe.history or []
    if not hist:
        return {"status": "empty", "reason": "no frame decoded"}
    t = np.array([h["t"] for h in hist])
    skip = float(v.get("skip_s", 1.0))
    seen_n = np.array([sum(1 for e in h["embers"] if e.get("seen")) for h in hist])
    after = t >= t[0] + skip
    minutes = (t[-1] - t[0]) / 60.0 if len(t) > 1 else 0.0
    tracks = [tr for tr in pipe.all_tracks() if tr.shown]
    px_per_m = 1.0 / pipe.m_per_px
    gap, reach = float(v.get("fragment_gap_s", 1.5)), float(v.get("fragment_reach_m", 0.6)) * px_per_m
    frag = 0
    for a in tracks:
        for b in tracks:
            if b is a or b.shown_t is None:
                continue
            ta = a.last_t
            first = next(((tt, x, y) for tt, x, y in b.pts if tt >= b.shown_t), None)
            if first is None:
                continue
            if 0 <= b.t0 - ta <= gap and math.hypot(first[1] - a.x, first[2] - a.y) <= reach:
                frag += 1
                break
    statics = [(tr.x, tr.y) for tr in pipe.all_tracks() if tr.static and not tr.shown]
    statics += [(tr.x, tr.y) for tr in pipe.tracker.static_tracks()]
    tol = float(_v(cfg).get("static_tol_px", 30))
    on_static = 0
    for tr in tracks:
        pts = np.array([(x, y) for _, x, y in tr.pts])
        if statics and len(pts) and np.mean([min(math.hypot(x - sx, y - sy) for sx, sy in statics) <= tol
                                             for x, y in pts]) >= 0.8:
            on_static += 1
    speeds = [e["speed_m_s"] for h in hist for e in h["embers"] if e.get("seen") and e.get("speed_m_s") is not None]
    return {"status": "ok", "seconds": _num(t[-1] - t[0], 2), "frames": len(hist), "phones": phones,
            "tracks_shown": len(tracks), "most_at_once": int(seen_n.max()),
            "frames_with_more_than_phones": _num(float(np.mean(seen_n[after] > phones))) if after.any() else None,
            "coverage": _num(float(np.mean(seen_n[after] >= 1))) if after.any() else None,
            "probable_id_switches": frag,
            "probable_id_switches_per_phone_per_min": _num(frag / max(phones, 1) / minutes) if minutes else None,
            "static_lights_found": len(statics), "tracks_on_static_lights": on_static,
            "speed_median_m_s": _num(float(np.median(speeds))) if speeds else None,
            "speed_p95_m_s": _num(float(np.percentile(speeds, 95))) if speeds else None,
            "calibrated": pipe.calibrated, "scale": pipe.scale_source, "measured_at_m": pipe.distance_m,
            "proc_ms_median": _num(pipe.stats.as_dict()["proc_ms_median"], 2)}


def find_recording(raw: Path, name: str) -> Path | None:
    hits = sorted(p for p in raw.glob(f"{name}.*") if p.suffix.lower() in VIDEO_SUFFIXES)
    return hits[0] if hits else None


# The suite -------------------------------------------------------------------------------------

def run_suite(cfg: dict, *, raw: str | Path | None = None, out: str | Path | None = None, phones: int = 1,
              path_m: float = 1.0, work_dir: str | Path | None = None, scenes: list[str] | None = None,
              seconds: float | None = None, size: tuple[int, int] | None = None, synthetic: bool = True,
              log=print) -> dict[str, Any]:
    v = _v(cfg)
    work = _path(work_dir or v.get("work_dir", "data/synthetic/ember"))
    raw_dir = _path(raw or v.get("raw_dir", "data/raw"))
    goals = dict(v.get("goals") or {})
    from wfglink.config import config_hash
    from wfglink.provenance import git_state, now_shanghai

    report: dict[str, Any] = {"suite": "ember", "created": now_shanghai(), **git_state(),
                              "config_sha256": config_hash(cfg), "goals": goals,
                              "settings": {"persistent_run_s": float(v.get("persistent_run_s", 0.2))},
                              "synthetic": None,
                              "ember_free": None, "ember_ruler": None}
    z_stand = synth.STANDING_M
    if synthetic:
        names = list(scenes or synth.SUITE_SCENES)
        per: dict[str, dict[str, Any]] = {}
        rows: list[tuple] = []
        for name in names:
            log(f"ember suite: scene {name} ...")
            video = scene_clip(name, cfg, work, seconds=seconds, size=size)
            res = evaluate_scene(video, cfg)
            rows += res.pop("speed_rows")
            per[name] = res
            log(f"  {name}: precision {res['precision']}, recall {res['recall']}, MOTA {res['mota']}, "
                f"ID switches {res['id_switches']}, false tracks {res['false_tracks']} "
                f"(static lights {res['static_light_tracks']})")
        z_tol = float(v.get("stand_tol_m", 0.1))
        vmin = float(v.get("min_speed_m_s", 0.2))
        pooled = pool(per)
        speed = {"standing": speed_summary(rows, z_stand, z_tol, vmin),
                 "at_1m": speed_summary(rows, 1.0, 0.15, vmin), "at_3m": speed_summary(rows, 3.0, 0.15, vmin)}
        speed["at_1m"]["expected_ratio"] = _num(z_stand / 1.0)
        speed["at_3m"]["expected_ratio"] = _num(z_stand / 3.0)
        ruler_video = scene_clip("ruler", cfg, work, size=size)
        truth_meta = json.loads(ruler_video.with_suffix(".json").read_text(encoding="utf-8"))
        ruler = ruler_clip(ruler_video, _scene_cfg(cfg, truth_meta), float(truth_meta["ruler"]["path_m"]))
        ruler["true_move_s_minimum_jerk"] = truth_meta["ruler"]["move_s"]
        report["synthetic"] = {"tuned_on": True, "scenes": per, "pooled": pooled, "speed": speed, "ruler": ruler,
                               "settings": {k: v.get(k) for k in ("seconds", "fps", "size", "crf", "hfov_deg", "seed")}}
    free = find_recording(raw_dir, "ember_free")
    if free is not None:
        log(f"ember suite: {free.name} ...")
        report["ember_free"] = {"file": str(free), **free_clip(free, cfg, phones)}
    else:
        report["ember_free"] = {"status": "missing", "reason": f"no {raw_dir}/ember_free.* (python -m wfglink record ember_free)"}
    rul = find_recording(raw_dir, "ember_ruler")
    if rul is not None:
        log(f"ember suite: {rul.name} ...")
        report["ember_ruler"] = {"file": str(rul), **ruler_clip(rul, cfg, path_m)}
    else:
        report["ember_ruler"] = {"status": "missing",
                                 "reason": f"no {raw_dir}/ember_ruler.* (python -m wfglink record ember_ruler)"}
    report["goal_check"] = goal_check(report, goals)
    out_path = _path(out or v.get("report", "results/validation/ember_report.json"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=_num, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def goal_check(report: dict[str, Any], goals: dict[str, Any]) -> dict[str, Any]:
    s = report.get("synthetic") or {}
    p = s.get("pooled") or {}
    sp = ((s.get("speed") or {}).get("standing") or {})
    checks = {}

    def add(name: str, value: Any, goal: Any, ok: bool | None) -> None:
        checks[name] = {"value": value, "goal": goal, "status": "n/a" if ok is None else ("met" if ok else "missed")}

    g = goals.get("recall_facing")
    val = p.get("recall_after_acquisition")
    add("recall_facing", val, g, None if val is None or g is None else val >= g)
    g = goals.get("static_light_tracks_per_min")
    val = p.get("static_light_tracks_per_min")
    add("static_light_tracks_per_min", val, g, None if val is None or g is None else val <= g)
    g = goals.get("id_switches_per_phone_per_min")
    val = p.get("id_switches_per_phone_per_min")
    add("id_switches_per_phone_per_min", val, g, None if val is None or g is None else val <= g)
    g = goals.get("speed_median_rel_err")
    val = sp.get("median_abs_rel_err")
    add("speed_median_rel_err", val, g, None if val is None or g is None else val <= g)
    # Your recordings: the ruler's displacement and mean speed against the speed goal, and the
    # free motion's probable ID switches against the ID-switch goal (n/a without the recording).
    r = report.get("ember_ruler") or {}
    ok_r = r.get("status") == "ok"
    for key in ("displacement_rel_err", "screen_speed_rel_err"):
        val = r.get(key) if ok_r else None
        add(f"ember_ruler_{key}", val, g, None if val is None or g is None else abs(val) <= g)
    f = report.get("ember_free") or {}
    g = goals.get("id_switches_per_phone_per_min")
    val = f.get("probable_id_switches_per_phone_per_min") if f.get("status") == "ok" else None
    add("ember_free_probable_id_switches_per_phone_per_min", val, g, None if val is None or g is None else val <= g)
    return checks


def _run_s(report: dict[str, Any]) -> Any:
    return (report.get("settings") or {}).get("persistent_run_s", 0.2)


def summary_lines(report: dict[str, Any]) -> list[str]:
    lines = []
    s = report.get("synthetic")
    if s:
        p = s["pooled"]
        lines.append(f"synthetic ({len(s['scenes'])} scenes, {p['minutes']} min; the scenes the detector and tracker "
                     f"were tuned on, not held out): precision {p['precision']}, "
                     f"recall {p['recall']} (after acquisition {p.get('recall_after_acquisition')}), MOTA {p['mota']}, "
                     f"ID switches {p['id_switches_per_phone_per_min']} per phone per min "
                     f"({p.get('id_switches_persistent_per_phone_per_min')} lasting {_run_s(report)} s or more), "
                     f"false tracks {p['false_tracks_per_min']} per min (static lights {p['static_light_tracks_per_min']})")
        st = s["speed"]["standing"]
        lines.append(f"speed at the standing distance: median error {st.get('median_abs_rel_err')} "
                     f"(p90 {st.get('p90_abs_rel_err')}, n {st.get('n')}) against the true speed at the middle of the "
                     f"speed window; against the true speed at that moment {st.get('vs_instant_median_abs_rel_err')} "
                     "(the screen lags by half the window)")
        for key in ("at_1m", "at_3m"):
            a = s["speed"][key]
            lines.append(f"phones {key[3:]} away read {a.get('median_ratio_measured_over_true')} x their true speed "
                         f"(expected {a.get('expected_ratio')}, measured at the standing distance)")
        r = s["ruler"]
        lines.append(f"synthetic ruler: {r.get('status')}, move {r.get('move_s')} s (between the 1 percent "
                     f"thresholds), screen speed error "
                     f"{r.get('screen_speed_rel_err')}, displacement error {r.get('displacement_rel_err')}")
    for key in ("ember_free", "ember_ruler"):
        r = report.get(key) or {}
        if r.get("status") != "ok":
            lines.append(f"{key}: {r.get('status')}: {r.get('reason', '')}")
        elif key == "ember_free":
            lines.append(f"ember_free: {r['tracks_shown']} tracks, most at once {r['most_at_once']} "
                         f"(phones {r['phones']}), coverage {r['coverage']}, probable ID switches "
                         f"{r['probable_id_switches_per_phone_per_min']} per min, on static lights "
                         f"{r['tracks_on_static_lights']} ({'calibrated' if r['calibrated'] else 'nominal field of view'})")
        else:
            lines.append(f"ember_ruler: move {r['move_s']} s (between the 1 percent thresholds), mean speed over it "
                         f"{r['true_mean_speed_m_s']} m/s, screen mean "
                         f"{r['screen_mean_speed_m_s']} m/s (error {r['screen_speed_rel_err']}), displacement "
                         f"{r['displacement_m']} m (error {r['displacement_rel_err']}) "
                         f"({'calibrated' if r['calibrated'] else 'nominal field of view'})")
    for name, c in (report.get("goal_check") or {}).items():
        lines.append(f"goal {name}: {c['value']} against {c['goal']}: {c['status']}")
    return lines
