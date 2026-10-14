"""LED turntable validation (plan section 4.4): measured speed against omega times radius.

Three diffused LEDs ride a turntable filmed from straight above. The truth is the image
speed of each LED, |omega| * r_eff, where omega comes from the stopwatch (30 revolutions)
and r_eff from an ellipse fitted to that LED's ring in the image. No metric scale is
needed: everything is in px/s. The method under test is the normal detector and tracker,
then the per-point local polynomial velocity with the known circular-motion gain divided
out, using the angular rate measured from the track itself (never the truth).

Per device the report gives:
- median and p90 relative track-speed error over tracks (and per speed);
- LED detection precision and recall per frame (a detection within max(3 px, L/2) of a
  ring counts once for that ring);
- the exposure estimate (Deming fit of streak length on track speed) and the duty cycle;
- the ring axis ratio (camera tilt) and a stopwatch versus video check of omega.

LED clips are never used for tuning: every threshold here is fixed before the clips arrive.
"""
from __future__ import annotations

import copy
import math
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.config import load_config
from wfglink.detect.candidates import Detector
from wfglink.io.sources import FileSource
from wfglink.measure.exposure import estimate_exposure
from wfglink.measure.velocity import correct_circular_speed, estimate_angular_rate, track_point_velocities
from wfglink.track.tracker import CONFIRMED, Tracker

# Recording steps of sitting 1, per device: (step id, stopwatch input key, speed label).
DEVICE_STEPS = {
    "iphone": [("iph_led_s1", "t30_s1", "speed1"), ("iph_led_s2", "t30_s2", "speed2")],
    "dashcam": [("dc_led_s1", "dc_t30_s1", "speed1"), ("dc_led_s2", "dc_t30_s2", "speed2")],
}


def _led_cfg(cfg: dict) -> dict:
    v = cfg.get("validate", {}).get("led", {})
    return {
        "n_leds": int(v.get("n_leds", 3)),
        "max_seconds": float(v.get("max_seconds", 60.0)),
        "min_points": int(v.get("min_track_points", 8)),
        "ring_tol_px": float(v.get("ring_tol_px", 3.0)),
        "ring_gap_frac": float(v.get("ring_gap_frac", 0.08)),
        "omega_disagree_pct": float(v.get("omega_disagree_pct", 3.0)),
    }


# Tracking a clip --------------------------------------------------------------------------
def track_clip(paths: list[Path], cfg: dict, max_seconds: float | None = None,
               t_exp_hint: float | None = None) -> dict[str, Any]:
    """Detect and track every file (each with its own tracker); keep tracks and detections.

    t_exp_hint is the exposure time passed to the tracker, which then searches as far as a
    streak of that exposure implies when starting tracks (see Tracker.set_exposure_hint).
    """
    tracks: list[dict[str, np.ndarray]] = []
    frames: list[tuple[float, np.ndarray, np.ndarray, np.ndarray]] = []   # t, x, y, length
    dts: list[float] = []
    n_frames = 0
    t_start = time.perf_counter()
    size = None
    for fi, path in enumerate(paths):
        det = Detector(cfg)
        src = FileSource(path)
        src.open()
        trk = None
        last_t = None
        try:
            while (f := src.read()) is not None:
                if max_seconds is not None and f.t > max_seconds:
                    break
                if trk is None:
                    fps = src.fps if getattr(src, "fps", None) else None
                    trk = Tracker(cfg, fps=fps, keep_history=True)
                    if t_exp_hint:
                        trk.set_exposure_hint(t_exp_hint)
                if last_t is not None:
                    if f.t <= last_t:
                        continue
                    dts.append(f.t - last_t)
                last_t = f.t
                size = f.image.shape[1], f.image.shape[0]
                d = det.detect(f.image)
                n_frames += 1
                if not det.ready:
                    continue
                trk.update(d, f.t, f.index)
                frames.append((f.t + 1e4 * fi, d.x.copy(), d.y.copy(), d.length.copy()))
        finally:
            src.close()
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


# One clip ----------------------------------------------------------------------------------
def analyse_led_clip(paths: list[Path], omega_rad_s: float, cfg: dict | None = None) -> dict[str, Any]:
    """Speed error, detection precision and recall, exposure and tilt for one LED speed.

    Two passes, as in file mode: the first tracks without an exposure time, so a fast LED
    with a short streak (short exposure) may not be picked up; its exposure estimate from
    the LEDs it did track then goes to the tracker for the second pass, whose results are
    reported. When the first pass cannot estimate the exposure, its results stand.
    """
    cfg = cfg or load_config()
    lc = _led_cfg(cfg)
    first = _measure(track_clip(paths, cfg, lc["max_seconds"]), paths, omega_rad_s, cfg, lc)
    t_exp = first.get("exposure", {}).get("t_exp_ms")
    if not t_exp:
        first["passes"] = 1
        return first
    second = _measure(track_clip(paths, cfg, lc["max_seconds"], t_exp_hint=t_exp / 1000.0), paths, omega_rad_s, cfg, lc)
    second["passes"] = 2
    second["first_pass"] = {k: first.get(k) for k in ("tracks_used", "rings", "median_speed_error_pct", "exposure")}
    second["seconds_processing"] = round(first["seconds_processing"] + second["seconds_processing"], 2)
    return second


def _measure(run: dict[str, Any], paths: list[Path], omega_rad_s: float, cfg: dict, lc: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"files": [Path(p).name for p in paths], "omega_stopwatch_rad_s": round(omega_rad_s, 5),
                           "frames": run["n_frames"], "seconds_processing": run["seconds_processing"],
                           "frame_interval_s": round(run["dt"], 6) if np.isfinite(run["dt"]) else None}
    good = [a for a in run["tracks"] if not a["static"][0]
            and np.count_nonzero(np.isfinite(a["x_meas"])) >= lc["min_points"]]
    out["tracks_used"] = len(good)
    out["tracks_static"] = sum(1 for a in run["tracks"] if a["static"][0])
    if not good:
        out["problem"] = "no usable tracks; LEDs not tracked"
        return out
    vcfg = cfg.get("velocity", {})
    window, order = int(vcfg.get("savgol_window", 5)), int(vcfg.get("savgol_order", 2))
    dt = run["dt"]

    # Rings: shared centre, per-track radii, groups, then one ellipse per ring.
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
        _, _, a, b = ellipse_coords(pts[:1, 0].astype(float), pts[:1, 1].astype(float), ell)
        rings.append({"tracks": g, "ellipse": ell, "a": a, "b": b, "points": int(weights[g].sum())})
    rings.sort(key=lambda r: max(r["a"], r["b"]))
    out["center_px"] = [round(float(center[0]), 1), round(float(center[1]), 1)]
    out["rings"] = [{"radius_px": round(float(math.sqrt(r["a"] * r["b"])), 1),
                     "axis_ratio": round(float(min(r["a"], r["b"]) / max(r["a"], r["b"])), 4),
                     "track_points": r["points"], "tracks": int(len(r["tracks"]))} for r in rings]
    if len(rings) != lc["n_leds"]:
        out.setdefault("warnings", []).append(f"{len(rings)} rings found, expected {lc['n_leds']}")

    # Speeds: per point, interior only, circular gain removed with the track's own angular rate.
    per_track, all_t, all_v, all_l, all_f, all_id, all_int = [], [], [], [], [], [], []
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
            phi, _, ea, eb = ellipse_coords(a["x_meas"], a["y_meas"], r["ellipse"])
            truth = expected_speed(phi, ea, eb, omega_rad_s)
            ratio = sp[use] / truth[use]
            ratio_raw = sp_raw[use] / truth[use]
            per_track.append({"ring": ri, "points": int(np.count_nonzero(use)),
                              "error": float(np.median(ratio) - 1), "error_uncorrected": float(np.median(ratio_raw) - 1),
                              "omega_video": om})
            omegas.append(abs(om))
            w_omega.append(np.count_nonzero(use))
            all_t.append(a["t"][use]); all_v.append(sp[use]); all_l.append(a["length"][use])
            all_f.append(a["flags"][use]); all_id.append(np.full(np.count_nonzero(use), len(per_track)))
            all_int.append(np.ones(np.count_nonzero(use), bool))
    if not per_track:
        out["problem"] = "no track had enough interior points"
        return out
    err = np.array([p["error"] for p in per_track])
    err_raw = np.array([p["error_uncorrected"] for p in per_track])
    w = np.array([p["points"] for p in per_track], float)
    out["tracks_measured"] = len(per_track)
    out["median_speed_error_pct"] = round(100 * float(np.median(err)), 2)
    out["p90_abs_speed_error_pct"] = round(100 * float(np.percentile(np.abs(err), 90)), 2)
    out["median_speed_error_uncorrected_pct"] = round(100 * float(np.median(err_raw)), 2)
    out["per_ring_median_error_pct"] = [round(100 * float(np.median(err[[p["ring"] == k for p in per_track]])), 2)
                                        if any(p["ring"] == k for p in per_track) else None for k in range(len(rings))]
    om_video = float(np.average(omegas, weights=w_omega))
    out["omega_video_rad_s"] = round(om_video, 5)
    out["omega_disagreement_pct"] = round(100 * (om_video / omega_rad_s - 1), 2)
    if abs(out["omega_disagreement_pct"]) > lc["omega_disagree_pct"]:
        out.setdefault("warnings", []).append("stopwatch and video disagree on the turntable speed; check the stopwatch value")
    out["weighted_speed_error_pct"] = round(100 * float(np.average(err, weights=w)), 2)

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


# Sitting 1 entry point ---------------------------------------------------------------------
def analyze_led_recordings(steps: dict[str, Any], upload_dir: Path, cfg: dict | None = None) -> dict[str, Any]:
    """All LED clips of sitting 1, per device, plus the side-by-side table (plan 4.4)."""
    cfg = cfg or load_config()
    upload_dir = Path(upload_dir)
    out: dict[str, Any] = {}
    for device, specs in DEVICE_STEPS.items():
        speeds: dict[str, Any] = {}
        for rid, t30_key, label in specs:
            st = steps.get(rid, {})
            files = [upload_dir / f["file"] for f in st.get("files", [])]
            t30 = (st.get("inputs") or {}).get(t30_key)
            if not files:
                continue
            if not t30:
                speeds[label] = {"status": "no stopwatch time"}
                continue
            omega = 2 * math.pi * 30.0 / float(t30)
            res = analyse_led_clip(files, omega, cfg)
            res["standin"] = any("_standins" in str(f.get("original", "")) for f in st.get("files", []))
            speeds[label] = res
        if not speeds:
            continue
        out[device] = _device_summary(speeds)
    if out:
        out["table"] = comparison_table(out)
    return out


def _device_summary(speeds: dict[str, Any]) -> dict[str, Any]:
    res: dict[str, Any] = {"speeds": speeds}
    measured = [s for s in speeds.values() if "median_speed_error_pct" in s]
    if not measured:
        return res
    errs = [s["median_speed_error_pct"] for s in measured]
    res["median_speed_error_pct"] = round(float(np.median(errs)), 2)
    res["p90_abs_speed_error_pct"] = round(float(max(s["p90_abs_speed_error_pct"] for s in measured)), 2)
    pr = [s for s in measured if s.get("detection_precision") is not None]
    if pr:
        res["detection_precision"] = round(float(np.mean([s["detection_precision"] for s in pr])), 4)
        res["detection_recall"] = round(float(np.mean([s["detection_recall"] for s in pr])), 4)
    exps = [s["exposure"]["t_exp_ms"] for s in measured if "t_exp_ms" in s.get("exposure", {})]
    if exps:
        res["exposure_ms"] = exps
    ratios = [r["axis_ratio"] for s in measured for r in s.get("rings", [])[-1:]]
    if ratios:
        res["outer_axis_ratio"] = round(float(min(ratios)), 4)
    res["standin"] = any(s.get("standin") for s in measured)
    return res


def comparison_table(results: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per device: the columns of the dashcam versus iPhone table in plan 4.4."""
    rows = []
    for device in ("iphone", "dashcam"):
        r = results.get(device)
        if not isinstance(r, dict):
            continue
        rows.append({"device": device,
                     "detection_precision": r.get("detection_precision"),
                     "detection_recall": r.get("detection_recall"),
                     "median_speed_error_pct": r.get("median_speed_error_pct"),
                     "p90_abs_speed_error_pct": r.get("p90_abs_speed_error_pct"),
                     "exposure_ms": r.get("exposure_ms"),
                     "false_tracks_per_min_night_drive": None,
                     "standin": r.get("standin")})
    return rows
