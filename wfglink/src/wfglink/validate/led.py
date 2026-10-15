"""LED turntable validation (plan section 4.4, filmed with the dashcam): measured speed against omega times radius.

Three diffused LEDs ride a turntable filmed from straight above by the booth dashcam. The
truth is the image speed of each LED, |omega| * r_eff, where omega comes from the stopwatch
(omega = 2 pi turns_timed / time) and r_eff from an ellipse fitted to that LED's ring in the
image. No metric scale is needed: everything is in px/s. The method under test is the normal
detector and tracker, then the per-point local polynomial velocity with the known
circular-motion gain divided out, using the angular rate measured from the track itself
(never the truth).

Per clip the result gives:
- median and p90 relative track-speed error over tracks, signed and absolute;
- per ring: radius, axis ratio (camera tilt), fit spread, arc covered, measured and expected speed;
- LED detection precision and recall per frame (a detection within max(3 px, L/2) of a
  ring counts once for that ring);
- the exposure estimate (Deming fit of streak length on track speed) and the duty cycle;
- a stopwatch versus video check of omega, and the frame timing of the file.

metric_check adds the user's formula: true speed = 2 pi x radius x turns / time in mm/s
against the measured speed converted with a px per mm scale (from the rings and the measured
LED radii, or from the ruler).

A recording split across loop files is analysed part by part (each part tracked on its own,
results pooled). The dashcam's date stamp is masked from detection (validate/dashcam.py).
LED clips are never used for tuning: every threshold here is fixed before the clips arrive.
"""
from __future__ import annotations

import copy
import itertools
import math
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.config import load_config
from wfglink.io.sources import FileSource
from wfglink.measure.exposure import estimate_exposure
from wfglink.measure.velocity import correct_circular_speed, estimate_angular_rate, track_point_velocities
from wfglink.track.tracker import CONFIRMED, Tracker
from wfglink.validate.dashcam import MaskedDetector, files_cfg, read_frames, sharpness, timing_summary


def _led_cfg(cfg: dict) -> dict:
    v = cfg.get("validate", {}).get("led", {})
    return {
        "n_leds": int(v.get("n_leds", 3)),
        "max_seconds": float(v.get("max_seconds", 60.0)),
        "min_points": int(v.get("min_track_points", 8)),
        "ring_tol_px": float(v.get("ring_tol_px", 3.0)),
        "ring_gap_frac": float(v.get("ring_gap_frac", 0.08)),
        "omega_disagree_pct": float(v.get("omega_disagree_pct", 3.0)),
        "goal_pct": float(v.get("goal_median_error_pct", 5.0)),
        "scale_spread_pct": float(v.get("scale_spread_warn_pct", 5.0)),
        "axis_ratio_min": float(v.get("axis_ratio_min", 0.99)),
        "ring_min_arc_deg": float(v.get("ring_min_arc_deg", 180.0)),
        "still_every_s": float(v.get("still_every_s", 0.25)),
    }


# Tracking a clip --------------------------------------------------------------------------
def track_clip(paths: list[Path], cfg: dict, max_seconds: float | None = None,
               t_exp_hint: float | None = None, boxes=(), still: str | None = None) -> dict[str, Any]:
    """Detect and track every part (each with its own tracker); keep tracks and detections.

    max_seconds: analyse at most this many seconds of the recording, all parts together,
    from the start of the first part.
    t_exp_hint is the exposure time passed to the tracker, which then searches as far as a
    streak of that exposure implies when starting tracks (see Tracker.set_exposure_hint).
    boxes: regions (fractions of the frame) never detected in, such as the date stamp.
    still: keep one picture of the recording, sampled every validate.led.still_every_s:
    "max" the brightest value of each pixel (the LEDs draw their rings), "sharp" the
    sharpest frame (the ruler clip), None no picture.
    A frame that repeats the previous one (at most frames.duplicate_max_px pixels changed by
    frames.duplicate_dn) is skipped, as in file mode.
    """
    fr = cfg.get("frames", {})
    dup_dn, dup_max = int(fr.get("duplicate_dn", 6)), int(fr.get("duplicate_max_px", 2))
    still_every = float(cfg.get("validate", {}).get("led", {}).get("still_every_s", 0.25))
    tracks: list[dict[str, np.ndarray]] = []
    frames: list[tuple[float, np.ndarray, np.ndarray, np.ndarray]] = []   # t, x, y, length
    times: list[np.ndarray] = []
    dts: list[float] = []
    errors: list[str] = []
    n_frames = repeated = 0
    used_s = 0.0
    t_start = time.perf_counter()
    size = None
    picture, best = None, -1.0
    for fi, path in enumerate(paths):
        if max_seconds is not None and used_s >= max_seconds:
            break
        det = MaskedDetector(cfg, boxes)
        src = FileSource(path)
        src.open()
        trk = None
        last_t = first_t = None
        part_t: list[float] = []
        prev_gray = None
        next_still = 0.0
        try:
            for f in read_frames(src, errors):
                first_t = f.t if first_t is None else first_t
                if max_seconds is not None and used_s + (f.t - first_t) > max_seconds:
                    break
                part_t.append(f.t)
                if trk is None:
                    fps = src.fps if getattr(src, "fps", None) else None
                    trk = Tracker(cfg, fps=fps, keep_history=True)
                    if t_exp_hint:
                        trk.set_exposure_hint(t_exp_hint)
                if last_t is not None:
                    if f.t <= last_t:
                        continue
                gray = cv2.cvtColor(f.image, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None and prev_gray.shape == gray.shape:
                    changed = cv2.countNonZero(cv2.compare(cv2.absdiff(gray, prev_gray), dup_dn, cv2.CMP_GE))
                    if changed <= dup_max:
                        repeated += 1
                        continue
                prev_gray = gray
                if last_t is not None:
                    dts.append(f.t - last_t)
                last_t = f.t
                size = f.image.shape[1], f.image.shape[0]
                if still and f.t - first_t >= next_still:
                    next_still = f.t - first_t + still_every
                    if still == "max":
                        picture = f.image.copy() if picture is None else np.maximum(picture, f.image)
                    elif (s := sharpness(f.image)) > best:
                        picture, best = f.image.copy(), s
                d = det.detect(f.image)
                n_frames += 1
                if not det.ready:
                    continue
                trk.update(d, f.t, f.index)
                frames.append((f.t + 1e4 * fi, d.x.copy(), d.y.copy(), d.length.copy()))
        finally:
            src.close()
        times.append(np.array(part_t))
        if part_t:
            used_s += part_t[-1] - part_t[0] + (float(np.median(np.diff(part_t))) if len(part_t) > 1 else 0.0)
        if trk is None:
            continue
        trk.finish_all()
        for tr in trk.all_tracks(include_active=True):
            if tr.status == CONFIRMED or tr.n_points:
                a = tr.arrays()
                a["file"] = np.full(len(a["t"]), fi)
                a["static"] = np.full(len(a["t"]), bool(tr.static))
                tracks.append(a)
    dt = float(np.median(dts)) if dts else float("nan")
    return {"tracks": tracks, "frames": frames, "dt": dt, "n_frames": n_frames, "size": size,
            "times": times, "repeated": repeated, "parts_used": len(times), "still": picture, "decode_errors": errors,
            "seconds_processing": round(time.perf_counter() - t_start, 2)}


# Ring geometry ------------------------------------------------------------------------------
def shared_center_fit(tracks: list[dict[str, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    """Common centre and per-track radius: x^2 + y^2 = 2 cx x + 2 cy y + c_k (Kasa, shared centre)."""
    rows, rhs, cols = [], [], []
    for k, a in enumerate(tracks):
        ok = np.isfinite(a["x_meas"]) & np.isfinite(a["y_meas"])
        x, y = a["x_meas"][ok], a["y_meas"][ok]
        rows.append(np.column_stack([2 * x, 2 * y]))
        rhs.append(x * x + y * y)
        cols.append(np.full(len(x), k))
    xy = np.vstack(rows)
    b = np.concatenate(rhs)
    kk = np.concatenate(cols)
    n_tr = len(tracks)
    A = np.zeros((len(b), 2 + n_tr))
    A[:, :2] = xy
    A[np.arange(len(b)), 2 + kk] = 1.0
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:2]
    r2 = sol[2:] + c @ c
    return c, np.sqrt(np.maximum(r2, 0.0))


def group_rings(radii: np.ndarray, weights: np.ndarray, gap_frac: float) -> list[np.ndarray]:
    """Indices of tracks per ring: sorted radii split where the gap exceeds gap_frac * r (at least 6 px)."""
    order = np.argsort(radii)
    groups: list[list[int]] = [[int(order[0])]]
    for i in order[1:]:
        prev = radii[groups[-1][-1]]
        if radii[i] - prev > max(6.0, gap_frac * radii[i]):
            groups.append([int(i)])
        else:
            groups[-1].append(int(i))
    return [np.array(g) for g in groups]


def ellipse_coords(x: np.ndarray, y: np.ndarray, ell) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Parametric angle phi and normalised radius of points for a cv2.fitEllipse result."""
    (ex, ey), (w, h), ang = ell
    a, b = w / 2.0, h / 2.0
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    dx, dy = x - ex, y - ey
    u, v = dx * c + dy * s, -dx * s + dy * c
    phi = np.arctan2(v / b, u / a)
    rn = np.sqrt((u / a) ** 2 + (v / b) ** 2)
    return phi, rn, a, b


def expected_speed(phi: np.ndarray, a: float, b: float, omega: float) -> np.ndarray:
    """Image speed of a point moving uniformly in angle on the ellipse x = a cos phi, y = b sin phi."""
    return abs(omega) * np.sqrt((a * np.sin(phi)) ** 2 + (b * np.cos(phi)) ** 2)


def fit_rings(good: list[dict[str, np.ndarray]], lc: dict) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Shared centre, per-track radii, ring groups, then one ellipse per ring, smallest first.

    Each ring also gets its fit spread (robust sigma of the points' distance from the
    ellipse, px) and the arc its points cover (degrees, in 10 degree bins).
    """
    center, radii = shared_center_fit(good)
    weights = np.array([np.count_nonzero(np.isfinite(a["x_meas"])) for a in good], float)
    groups = group_rings(radii, weights, lc["ring_gap_frac"])
    total_w = weights.sum()
    rings = []
    for g in groups:
        if weights[g].sum() < 0.03 * total_w:
            continue   # a stray short track, not an LED ring
        pts = np.vstack([np.column_stack([good[i]["x_meas"], good[i]["y_meas"]]) for i in g])
        pts = pts[np.all(np.isfinite(pts), axis=1)].astype(np.float32)
        if len(pts) < 5:
            continue
        ell = cv2.fitEllipse(pts)
        phi, rn, a, b = ellipse_coords(pts[:, 0].astype(float), pts[:, 1].astype(float), ell)
        dev = np.abs(rn - 1)
        keep = dev * max(a, b) < max(lc["ring_tol_px"], 4 * 1.4826 * float(np.median(dev * max(a, b))))
        if keep.sum() >= 5 and not keep.all():
            ell = cv2.fitEllipse(pts[keep])
        phi, rn, a, b = ellipse_coords(pts[:, 0].astype(float), pts[:, 1].astype(float), ell)
        spread = 1.4826 * float(np.median(np.abs(rn - 1))) * math.sqrt(a * b)
        arc = 10.0 * len(np.unique(np.floor((np.degrees(phi) % 360) / 10)))
        rings.append({"tracks": g, "ellipse": ell, "a": a, "b": b, "points": int(weights[g].sum()),
                      "spread_px": spread, "arc_deg": arc})
    rings.sort(key=lambda r: max(r["a"], r["b"]))
    return center, rings


def ring_summary(r: dict[str, Any]) -> dict[str, Any]:
    (ex, ey), (ea, eb), ang = r["ellipse"]
    return {"radius_px": round(float(math.sqrt(r["a"] * r["b"])), 1),
            "axis_ratio": round(float(min(r["a"], r["b"]) / max(r["a"], r["b"])), 4),
            "fit_spread_px": round(r["spread_px"], 2), "arc_deg": round(r["arc_deg"]),
            "track_points": r["points"], "tracks": int(len(r["tracks"])),
            "ellipse_px": [round(float(ex), 1), round(float(ey), 1), round(float(ea), 1), round(float(eb), 1),
                           round(float(ang), 1)]}


# One clip ----------------------------------------------------------------------------------
def analyse_led_clip(paths: list[Path], omega_rad_s: float | None, cfg: dict | None = None, boxes=(),
                     still: str | None = None, max_seconds: float | None = None,
                     images: dict | None = None) -> dict[str, Any]:
    """Speed error, detection precision and recall, exposure and tilt for one LED recording.

    omega_rad_s is the stopwatch truth; None (a ruler clip without a known speed) reports the
    rings, the video's own omega and the detection scores but no speed error.
    Two passes, as in file mode: the first tracks without an exposure time, so a fast LED
    with a short streak (short exposure) may not be picked up; its exposure estimate from
    the LEDs it did track then goes to the tracker for the second pass, whose results are
    reported. When the first pass cannot estimate the exposure, its results stand.
    images: when a dict is given, images["still"] receives the picture asked for by `still`.
    """
    cfg = cfg or load_config()
    lc = _led_cfg(cfg)
    secs = lc["max_seconds"] if max_seconds is None else max_seconds
    run = track_clip(paths, cfg, secs, boxes=boxes, still=still)
    if images is not None:
        images["still"] = run["still"]
    first = _measure(run, paths, omega_rad_s, cfg, lc)
    t_exp = first.get("exposure", {}).get("t_exp_ms")
    if not t_exp:
        first["passes"] = 1
        return first
    run2 = track_clip(paths, cfg, secs, t_exp_hint=t_exp / 1000.0, boxes=boxes)
    second = _measure(run2, paths, omega_rad_s, cfg, lc)
    second["passes"] = 2
    second["first_pass"] = {k: first.get(k) for k in ("tracks_used", "rings", "median_speed_error_pct", "exposure")}
    second["seconds_processing"] = round(first["seconds_processing"] + second["seconds_processing"], 2)
    return second


def _measure(run: dict[str, Any], paths: list[Path], omega_rad_s: float | None, cfg: dict, lc: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"files": [Path(p).name for p in paths], "parts_used": run["parts_used"],
                           "omega_stopwatch_rad_s": round(omega_rad_s, 5) if omega_rad_s else None,
                           "frames": run["n_frames"], "seconds_processing": run["seconds_processing"],
                           "frame_interval_s": round(run["dt"], 6) if np.isfinite(run["dt"]) else None,
                           "timing": timing_summary(run["times"], files_cfg(cfg)["interval_tol_frac"], run["repeated"])}
    if run["size"]:
        out["size_px"] = list(run["size"])
    if run["decode_errors"]:
        out["warnings"] = list(run["decode_errors"])
    good = [a for a in run["tracks"] if not a["static"][0]
            and np.count_nonzero(np.isfinite(a["x_meas"])) >= lc["min_points"]]
    out["tracks_used"] = len(good)
    out["tracks_static"] = sum(1 for a in run["tracks"] if a["static"][0])
    out["n_rings"] = 0
    if not good:
        out["problem"] = ("no usable tracks; LEDs not tracked (in the still they should be small bright dots on a "
                          "dark turntable: a large glow is masked like a flame)")
        return out
    vcfg = cfg.get("velocity", {})
    window, order = int(vcfg.get("savgol_window", 5)), int(vcfg.get("savgol_order", 2))
    dt = run["dt"]

    center, rings = fit_rings(good, lc)
    # An LED goes round: a "ring" whose points cover a short arc is a stray light (a reflection,
    # an unmasked part of the date stamp) or an LED lost most of the time, and is not used.
    short = [r for r in rings if r["arc_deg"] < lc["ring_min_arc_deg"]]
    rings = [r for r in rings if r["arc_deg"] >= lc["ring_min_arc_deg"]]
    if short:
        out["rings_rejected"] = [ring_summary(r) for r in short]
        out.setdefault("warnings", []).append(
            f"{len(short)} ring(s) of radius {', '.join(f'{math.sqrt(r['a'] * r['b']):.1f}' for r in short)} px cover less "
            f"than {lc['ring_min_arc_deg']:g} degrees and are not used (a reflection, the date stamp, or an LED that "
            "was mostly lost)")
    out["center_px"] = [round(float(center[0]), 1), round(float(center[1]), 1)]
    out["rings"] = [ring_summary(r) for r in rings]
    out["n_rings"] = len(rings)
    if len(rings) != lc["n_leds"]:
        out.setdefault("warnings", []).append(f"{len(rings)} rings found, expected {lc['n_leds']}")
    if rings and min(r["axis_ratio"] for r in out["rings"]) < lc["axis_ratio_min"]:
        out.setdefault("warnings", []).append(
            f"ring axis ratio {min(r['axis_ratio'] for r in out['rings']):.3f} is below {lc['axis_ratio_min']:g}: "
            "the dashcam does not look straight down")

    # Speeds: per point, interior only, circular gain removed with the track's own angular rate.
    per_track, all_t, all_v, all_l, all_f, all_id, all_int = [], [], [], [], [], [], []
    ring_speeds: list[list[np.ndarray]] = [[] for _ in rings]
    omegas, w_omega = [], []
    for ri, r in enumerate(rings):
        for i in r["tracks"]:
            a = good[i]
            pv = track_point_velocities(a, cfg)
            vx, vy, interior = pv["vx_poly"], pv["vy_poly"], pv["interior"]
            use = interior & np.isfinite(vx)
            if np.count_nonzero(use) < 3:
                continue
            om = estimate_angular_rate(a["t"][use], vx[use], vy[use])
            sp_raw = np.hypot(vx, vy)
            sp = np.asarray(correct_circular_speed(sp_raw, om, dt, window, order)) if np.isfinite(om) else sp_raw
            entry = {"ring": ri, "points": int(np.count_nonzero(use)), "omega_video": om}
            if omega_rad_s:
                phi, _, ea, eb = ellipse_coords(a["x_meas"], a["y_meas"], r["ellipse"])
                truth = expected_speed(phi, ea, eb, omega_rad_s)
                entry["error"] = float(np.median(sp[use] / truth[use]) - 1)
                entry["error_uncorrected"] = float(np.median(sp_raw[use] / truth[use]) - 1)
            per_track.append(entry)
            ring_speeds[ri].append(sp[use])
            omegas.append(abs(om))
            w_omega.append(np.count_nonzero(use))
            all_t.append(a["t"][use]); all_v.append(sp[use]); all_l.append(a["length"][use])
            all_f.append(a["flags"][use]); all_id.append(np.full(np.count_nonzero(use), len(per_track)))
            all_int.append(np.ones(np.count_nonzero(use), bool))
    if not per_track:
        out["problem"] = "no track had enough interior points"
        return out
    for ri, ring in enumerate(out["rings"]):
        if ring_speeds[ri]:
            ring["speed_px_s"] = round(float(np.median(np.concatenate(ring_speeds[ri]))), 2)
        if omega_rad_s:
            ring["expected_px_s"] = round(abs(omega_rad_s) * ring["radius_px"], 2)
    out["tracks_measured"] = len(per_track)
    om_video = float(np.average(np.array(omegas)[np.isfinite(omegas)],
                                weights=np.array(w_omega)[np.isfinite(omegas)])) if np.isfinite(omegas).any() else float("nan")
    out["omega_video_rad_s"] = round(om_video, 5) if np.isfinite(om_video) else None
    if omega_rad_s:
        err = np.array([p["error"] for p in per_track])
        err_raw = np.array([p["error_uncorrected"] for p in per_track])
        w = np.array([p["points"] for p in per_track], float)
        out["median_speed_error_pct"] = round(100 * float(np.median(err)), 2)
        out["median_abs_speed_error_pct"] = round(100 * float(np.median(np.abs(err))), 2)
        out["p90_abs_speed_error_pct"] = round(100 * float(np.percentile(np.abs(err), 90)), 2)
        out["median_speed_error_uncorrected_pct"] = round(100 * float(np.median(err_raw)), 2)
        out["per_ring_median_error_pct"] = [round(100 * float(np.median(err[[p["ring"] == k for p in per_track]])), 2)
                                            if any(p["ring"] == k for p in per_track) else None for k in range(len(rings))]
        for ring, e in zip(out["rings"], out["per_ring_median_error_pct"]):
            ring["median_error_pct"] = e
        out["track_errors_pct"] = [round(100 * float(e), 3) for e in err]
        out["weighted_speed_error_pct"] = round(100 * float(np.average(err, weights=w)), 2)
        if out["omega_video_rad_s"] is not None:
            out["omega_disagreement_pct"] = round(100 * (om_video / omega_rad_s - 1), 2)
            if abs(out["omega_disagreement_pct"]) > lc["omega_disagree_pct"]:
                out.setdefault("warnings", []).append(
                    "stopwatch and video disagree on the turntable speed; check the stopwatch value")

    # Exposure: Deming fit of streak length on speed over all LED tracks of this clip.
    ecfg = copy.deepcopy(cfg)
    ecfg.setdefault("velocity", {}).setdefault("exposure", {}).update({"min_tracks": 2, "window_s": 1e9})
    fps = 1.0 / dt if np.isfinite(dt) and dt > 0 else 30.0
    est = estimate_exposure(np.concatenate(all_id), np.concatenate(all_t), np.concatenate(all_v),
                            np.concatenate(all_l), np.concatenate(all_f), fps=fps, cfg=ecfg,
                            interior=np.concatenate(all_int))
    out["exposure"] = ({"t_exp_ms": round(1000 * est.t_exp, 2), "ci_ms": [round(1000 * est.ci_low, 2), round(1000 * est.ci_high, 2)],
                        "duty": round(est.duty, 3), "points": est.n_points, "outliers": est.n_outliers}
                       if est.ok else {"status": f"not estimated: {est.reason}"})

    # Detection precision and recall per frame against the rings.
    out.update(_detection_pr(run["frames"], rings, lc["ring_tol_px"]))
    return out


def _detection_pr(frames, rings, tol_px: float) -> dict[str, Any]:
    if not rings:
        return {}
    tp_sum = det_sum = 0
    recalls = []
    for _, x, y, length in frames:
        hit = np.zeros(len(rings), bool)
        for k, r in enumerate(rings):
            if len(x) == 0:
                break
            _, rn, a, b = ellipse_coords(x.astype(float), y.astype(float), r["ellipse"])
            dist = np.abs(rn - 1) * math.sqrt(a * b)
            tol = np.maximum(tol_px, 0.5 * np.nan_to_num(length.astype(float), nan=0.0))
            hit[k] = bool(np.any(dist <= tol))
        tp_sum += int(hit.sum())
        det_sum += len(x)
        recalls.append(hit.mean())
    return {"detection_recall": round(float(np.mean(recalls)), 4) if recalls else None,
            "detection_precision": round(tp_sum / det_sum, 4) if det_sum else None,
            "frames_scored": len(recalls)}


def rings_in_tracks(tracks: list[dict[str, np.ndarray]], cfg: dict) -> list[dict[str, Any]]:
    """LED rings among the tracks of any clip (the room test): tight rings over a wide arc only.

    A ring counts when its points lie within validate.led.ring_tol_px of the ellipse (robust
    sigma) and cover at least validate.led.ring_min_arc_deg, so a few unrelated moving
    lights do not make a ring.
    """
    lc = _led_cfg(cfg)
    good = [a for a in tracks if not a["static"][0] and np.count_nonzero(np.isfinite(a["x_meas"])) >= lc["min_points"]]
    if not good:
        return []
    _, rings = fit_rings(good, lc)
    return [ring_summary(r) for r in rings if r["spread_px"] <= lc["ring_tol_px"] and r["arc_deg"] >= lc["ring_min_arc_deg"]]


# Metric check (the user's formula) ---------------------------------------------------------
def metric_check(rings: list[dict[str, Any]], radius_mm: list[float], omega_rad_s: float, cfg: dict,
                 ruler_px_per_mm: float | None = None) -> dict[str, Any]:
    """True speed 2 pi r turns / time (= omega r) in mm/s against the measured speed in mm/s.

    The measured image speed of each ring is converted with a px per mm scale: the median
    over rings of r_px / r_mm, or the ruler's when the notes give ruler_px_per_mm. Rings and
    the measured LED radii are paired by sorting both; with fewer rings than radii, the
    radii that keep the order and whose px per mm agree best (or agree with the ruler) are
    used. The spread of px per mm over the rings checks the tape-measured radii and that the
    dashcam looks straight down. With the rings' own scale this mostly checks the radii;
    with a ruler scale it checks the metric scale too.
    """
    lc = _led_cfg(cfg)
    mm = sorted(float(r) for r in radius_mm)
    rs = [r for r in rings if r.get("speed_px_s")]
    out: dict[str, Any] = {"scale_source": "ruler" if ruler_px_per_mm else "rings"}
    if not rs:
        return {**out, "status": "no ring with a measured speed"}
    if len(rs) > len(mm):
        return {**out, "status": f"{len(rs)} rings for {len(mm)} LED radii; they cannot be paired"}
    if len(rs) == 1 and len(mm) > 1 and not ruler_px_per_mm:
        return {**out, "status": "one ring only; which LED it is needs the ruler scale (ruler_px_per_mm)"}
    r_px = np.array([r["radius_px"] for r in rs], float)
    best = None
    for combo in itertools.combinations(range(len(mm)), len(rs)):
        k = r_px / np.array([mm[i] for i in combo])
        bad = (float(np.max(np.abs(k / ruler_px_per_mm - 1))) if ruler_px_per_mm
               else float((k.max() - k.min()) / np.median(k)))
        if best is None or bad < best[0]:
            best = (bad, combo, k)
    _, combo, k = best
    rings_scale = float(np.median(k))
    scale = float(ruler_px_per_mm) if ruler_px_per_mm else rings_scale
    pairs, errs = [], []
    for r, i, ki in zip(rs, combo, k):
        true = abs(omega_rad_s) * mm[i]
        meas = r["speed_px_s"] / scale
        errs.append(meas / true - 1)
        pairs.append({"radius_mm": mm[i], "radius_px": r["radius_px"], "px_per_mm": round(float(ki), 4),
                      "true_mm_s": round(true, 2), "measured_mm_s": round(meas, 2),
                      "error_pct": round(100 * errs[-1], 2)})
    out.update({"scale_px_per_mm": round(scale, 4), "rings_px_per_mm": round(rings_scale, 4),
                "scale_spread_pct": round(100 * float((k.max() - k.min()) / rings_scale), 2) if len(k) > 1 else None,
                "pairs": pairs, "median_error_pct": round(100 * float(np.median(errs)), 2),
                "median_abs_error_pct": round(100 * float(np.median(np.abs(errs))), 2)})
    if ruler_px_per_mm:
        out["rings_vs_ruler_pct"] = round(100 * (rings_scale / ruler_px_per_mm - 1), 2)
    if out["scale_spread_pct"] is not None and out["scale_spread_pct"] > lc["scale_spread_pct"]:
        out["warning"] = (f"px per mm differs by {out['scale_spread_pct']:.1f} % between the rings; check "
                          "led_radius_mm and that the dashcam looks straight down")
    return out
