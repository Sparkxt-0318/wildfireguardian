"""Real-clip plausibility checks (plan section 4.5) on a finished file-mode run.

A real clip has no ground truth, so these checks only ask whether a run is technically and
physically plausible. Each check returns a status, "pass", "flag" or "not applicable", a
one-line reason and the values it measured. A pass means that the check ran in full and
found nothing; a check that could run only in part flags and says what was not tested.
`run_plausibility` runs them all on a run folder (summary.json and the tables of
`process`) with the clip settings file, writes plausibility.json next to summary.json and
copies the statuses into summary.json. All thresholds are under `plausibility` in the
config.

1. Timing: frame interval median and spread, gaps longer than timing.gap_factor median
   intervals, a variable frame rate (spread of the intervals), timestamps that do not
   increase, and repeated frames (the pipeline's duplicate flag). When the clip file is
   the run's input (same SHA-256), the frame times are also matched to the container's
   packet times in the run's segment, so a frame lost in decoding shows up.
2. Exposure: only when T_exp is known (estimated and accepted, or given); when the
   estimator declined, the check is not applicable and says why. T_exp must be no longer
   than one frame interval (exposure.frame_tol allows for rounding). When the clip has
   repeated frames, that interval is the source camera's: the mean interval between frames
   that are not repeats. An estimated T_exp must also be stable over time: the estimator
   runs again in consecutive windows of the run's track points, and the intervals of the
   windows must share a point (a lenient test: with equal errors, two estimates about 2.8
   standard errors of their difference apart still share one). Windows with too few
   tracks are skipped and counted. A window that the estimator declines for a reason that
   speaks against a proportional, stable estimate (streak length not proportional to
   speed, a fit that depends on its start) flags the check; one declined for lack of data
   in the window is only counted.
   With fewer than two windows that give an interval, stability is not tested, and the
   check flags with a reason that starts with "stability not tested".
3. Static lights: tracks flagged static must never keep a counted gate crossing.
4. Speed: with a peak gust (peak_gust_ms, gust_source), a distance interval
   (z_interval_m) and a focal length (focal_px, or hfov_deg over the full frame width) in
   the clip settings, a track is implausible when it is faster than
   speed.gust_factor x gust + speed.margin_ms at both Z_min and Z_max, that is at Z_min,
   which gives the lower speed.
5. Direction: with a hand-annotated drift direction (drift_deg, in the image axes of
   direction_deg: 0 = right, +90 = down; drift_basis says what was annotated), the
   speed-weighted circular mean direction of the moving tracks must lie within
   drift_tolerance_deg (or direction.tolerance_deg) of it. With a mean resultant length
   under direction.min_resultant there is no dominant direction to compare, and the check
   flags (an addition to the plan).
6. Determinism: process_clip runs twice on determinism.seconds of the clip, from the run's
   first frame with a ready detector (so a clip that opens on a still picture is not
   compared on empty tables), with the run's ROI, gate, exposure and scale and without the
   overlay, into temporary folders. A run with a known T_exp gives it to the reruns, so
   they run the tracking pass that wrote the run's tables (one pass each); otherwise each
   rerun estimates again. Detections, frames (without timing columns), track points,
   tracks and the field must be exactly equal. A rerun without any detection is not
   applicable. The overlay video is never compared (font rendering differs between
   machines).

The clip settings must belong to the run: when the clip file exists and its SHA-256 differs
from the run's input, speed and direction (which use the settings' gust and drift) are not
applicable, and so are the container times and the determinism reruns.
"""
from __future__ import annotations

import json
import math
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.config import load_config

PASS, FLAG, NA = "pass", "flag", "not applicable"
TABLES = ("detections", "frames", "track_points", "tracks", "field")

# The exposure estimator's messages for a window without enough tracks to fit: skipped and
# counted. Matched exactly ("too few tracks to check the speed cut" had enough to fit).
_TOO_FEW = ("no points", "too few tracks")
# Parts of the estimator's messages that speak against a stable estimate proportional to
# speed. Its other declines mean that the window had too little data to confirm one.
_AGAINST = ("not proportional", "estimate depends on the starting value", "does not grow with speed",
            "fit failed")


@dataclass
class Check:
    status: str
    reason: str
    values: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason, "values": self.values}


def _pcfg(cfg: dict) -> dict:
    return cfg.get("plausibility", {})


def _num(v) -> float | None:
    """A finite float, or None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def read_table(run_dir: Path, name: str, summary: dict | None = None):
    """A run table by name (parquet or csv as `process` wrote it), or None when absent."""
    import pandas as pd

    names = []
    if summary:
        names.append((summary.get("outputs") or {}).get(name))
    names += [f"{name}.parquet", f"{name}.csv"]
    for n in names:
        if not n:
            continue
        p = Path(run_dir) / n
        if p.exists():
            return pd.read_csv(p) if p.suffix == ".csv" else pd.read_parquet(p)
    return None


# 1. Timing --------------------------------------------------------------------------------

def packet_times(path: str | Path) -> np.ndarray:
    """Sorted presentation times (s) of the video packets in a file, read without decoding."""
    import av

    with av.open(str(path)) as c:
        s = c.streams.video[0]
        tb = s.time_base
        t = [float(p.pts * tb) for p in c.demux(s) if p.pts is not None]
    return np.sort(np.asarray(t, dtype=np.float64))


def _match_times(a: np.ndarray, b: np.ndarray, tol: float) -> np.ndarray:
    """For each time in a, whether b (sorted) has a time within tol."""
    if b.size == 0:
        return np.zeros(a.size, dtype=bool)
    i = np.clip(np.searchsorted(b, a), 1, b.size) - 1
    j = np.clip(i + 1, 0, b.size - 1)
    return (np.abs(b[i] - a) <= tol) | (np.abs(b[j] - a) <= tol)


def check_timing(frames, cfg: dict, packets: np.ndarray | None = None,
                 segment: tuple[float, float | None] = (0.0, None), fps_nominal: float | None = None) -> Check:
    """Frame timing of a run from frames.parquet, and (optional) the container packet times."""
    c = _pcfg(cfg).get("timing", {})
    gap_factor = float(c.get("gap_factor", 1.5))
    max_gaps = int(c.get("max_gaps", 0))
    vfr_max = float(c.get("vfr_spread_max", 0.1))
    rep_max = float(c.get("repeat_max_fraction", 0.0))
    tol = float(c.get("pts_match_s", 0.001))
    start_eps = float(c.get("start_eps_s", 1e-6))
    if frames is None or len(frames) < 3:
        return Check(NA, "fewer than 3 frames in frames.parquet")
    t = frames["t"].to_numpy(dtype=np.float64)
    dt = np.diff(t)
    pos = dt[dt > 0]
    if pos.size < 2:
        return Check(FLAG, "frame times do not increase", {"frames": int(len(t))})
    med = float(np.median(pos))
    p5, p95 = (float(v) for v in np.percentile(pos, [5, 95]))
    spread = (p95 - p5) / med
    gaps = int(np.count_nonzero(dt > gap_factor * med))
    non_inc = int(np.count_nonzero(dt <= 0))
    repeats = int(frames["duplicate"].astype(bool).sum()) if "duplicate" in frames else 0
    rep_frac = repeats / len(t)
    v: dict[str, Any] = {
        "frames": int(len(t)), "interval_median_s": med, "interval_p5_s": p5, "interval_p95_s": p95,
        "interval_min_s": float(pos.min()), "interval_max_s": float(pos.max()),
        "interval_mad_s": float(1.4826 * np.median(np.abs(pos - med))), "interval_spread": spread,
        "fps_from_median": 1.0 / med, "fps_from_span": (len(t) - 1) / float(t[-1] - t[0]) if t[-1] > t[0] else None,
        "fps_nominal": fps_nominal, "gap_factor": gap_factor,
        "gaps": gaps, "largest_gap_s": float(dt.max()), "variable_frame_rate": bool(spread > vfr_max),
        "timestamps_not_increasing": non_inc, "repeated_frames": repeats, "repeated_fraction": rep_frac}
    problems = []
    if gaps > max_gaps:
        problems.append(f"{gaps} gaps longer than {gap_factor:g} median intervals (largest {dt.max():.3f} s)")
    if spread > vfr_max:
        problems.append(f"variable frame rate (interval spread {spread:.2f} of the median)")
    if non_inc:
        problems.append(f"{non_inc} timestamps do not increase")
    if rep_frac > rep_max:
        problems.append(f"{repeats} repeated frames ({100 * rep_frac:.0f} percent; skipped by the pipeline)")
    if packets is not None:
        a, b = segment
        rel = packets - a
        sel = rel >= -start_eps     # the decoder's own rule for the first frame of a segment
        if b is not None:
            sel &= packets <= b - tol    # the last frame at the segment's end may fall either side
        rel = rel[sel]
        seen = _match_times(rel, np.sort(t), tol)
        extra = ~_match_times(t, np.sort(rel), tol)
        if b is not None:
            extra &= t + a <= b - tol
        v.update(container_frames_in_segment=int(rel.size), container_frames_missing=int((~seen).sum()),
                 frames_without_container_time=int(extra.sum()))
        if (~seen).any():
            problems.append(f"{int((~seen).sum())} container frames missing from the run")
        if extra.any():
            problems.append(f"{int(extra.sum())} run frames without a container time")
    else:
        v["container_frames_in_segment"] = None
    if problems:
        return Check(FLAG, "; ".join(problems), v)
    return Check(PASS, f"steady frame interval {1000 * med:.2f} ms, {gaps} gaps, {repeats} repeated frames", v)


# 2. Exposure ------------------------------------------------------------------------------

def frame_interval(frames, fps: float | None) -> dict[str, Any]:
    """The frame interval an exposure must fit in, with its basis.

    Without repeated frames: the median decoded interval. With repeats (a re-encode at a
    higher rate than the camera's), the source camera's interval: the mean interval between
    the frames that are not repeats, from the first frame with a ready detector on (content
    repeats are only found once there are tracks), that is one over the rate of new
    pictures. 1 / fps when frames.parquet is missing.
    """
    out: dict[str, Any] = {"decoded_s": 1.0 / fps if fps else None, "unique_s": None, "repeated_frames": 0,
                           "interval_s": 1.0 / fps if fps else None, "basis": "nominal frame rate"}
    if frames is None or len(frames) < 3:
        return out
    t = frames["t"].to_numpy(dtype=np.float64)
    d = np.diff(t)
    if (d > 0).any():
        out.update(decoded_s=float(np.median(d[d > 0])), basis="decoded frames")
        out["interval_s"] = out["decoded_s"]
    dup = frames["duplicate"].to_numpy(dtype=bool) if "duplicate" in frames else np.zeros(t.size, bool)
    out["repeated_frames"] = int(dup.sum())
    if dup.any():
        keep = ~dup
        if "ready" in frames and frames["ready"].astype(bool).any():
            keep &= np.arange(t.size) >= int(np.argmax(frames["ready"].to_numpy(dtype=bool)))
        tu = t[keep]
        if tu.size >= 3 and tu[-1] > tu[0]:
            out.update(unique_s=float((tu[-1] - tu[0]) / (tu.size - 1)), unique_median_s=float(np.median(np.diff(tu))),
                       basis="frames that are not repeats (one over the rate of new pictures)")
            out["interval_s"] = out["unique_s"]
    return out


def window_kind(ok: bool, ci: list, reason: str) -> str:
    """accepted, no interval, too few tracks, inconclusive (declined for lack of data) or declined."""
    if ok:
        return "accepted" if ci[0] is not None and ci[1] is not None else "no interval"
    if reason in _TOO_FEW:
        return "too few tracks"
    if any(k in reason for k in _AGAINST):
        return "declined"
    return "inconclusive"


def exposure_windows(points, cfg: dict, fps: float, window_s: float) -> list[dict[str, Any]]:
    """T_exp estimated separately in consecutive windows of the track points (static tracks left out).

    The span of the points is cut into round(span / window_s) equal windows (at least one).
    Each window is estimated by `estimate_exposure` with the window as its time window.
    """
    from wfglink.measure.exposure import estimate_exposure
    from wfglink.measure.velocity import add_point_velocities

    if points is None or len(points) == 0:
        return []
    pts = points
    if "static" in pts:
        pts = pts[~pts["static"].astype(bool)]
    if not {"speed_poly", "interior"} <= set(pts.columns):
        pts = add_point_velocities(pts, cfg)
    if len(pts) == 0:
        return []
    t = pts["t"].to_numpy(dtype=np.float64)
    t0, t1 = float(np.nanmin(t)), float(np.nanmax(t))
    n = max(1, int(round((t1 - t0) / window_s)))
    edges = np.linspace(t0, t1, n + 1)
    out = []
    for k in range(n):
        a = edges[k] - (1e-9 if k == 0 else 0.0)        # the estimator's window is (t_end - window_s, t_end]
        b = float(edges[k + 1])
        wcfg = {**cfg, "velocity": {**cfg.get("velocity", {}),
                                    "exposure": {**cfg.get("velocity", {}).get("exposure", {}), "window_s": b - a}}}
        est = estimate_exposure(pts["track_id"].to_numpy(), t, pts["speed_poly"].to_numpy(dtype=np.float64),
                                pts["length"].to_numpy(dtype=np.float64), pts["flags"].to_numpy(),
                                fps=fps, cfg=wcfg, t_now=b, interior=pts["interior"].to_numpy(dtype=bool))
        ci = [_num(est.ci_low), _num(est.ci_high)]
        out.append({"t0": float(edges[k]), "t1": b, "ok": bool(est.ok), "t_exp_s": _num(est.t_exp),
                    "ci_s": ci, "tracks": int(est.n_tracks), "reason": est.reason,
                    "kind": window_kind(bool(est.ok), ci, est.reason)})
    return out


def check_exposure(summary: dict, points, frames, cfg: dict, fps: float | None = None) -> Check:
    c = _pcfg(cfg).get("exposure", {})
    frame_tol = float(c.get("frame_tol", 0.05))
    window_s = float(c.get("window_s", 3.0))
    exp = summary.get("exposure") or {}
    t_exp = _num(exp.get("t_exp_s"))
    if t_exp is None:
        why = str(exp.get("status") or "no exposure time in summary.json")
        return Check(NA, f"estimator declined: {why.removeprefix('not estimated: ')}",
                     {"source": exp.get("source"), "estimator_reason": why})
    fps = fps or _num((summary.get("input") or {}).get("fps")) or 30.0   # as the run's own estimate used it
    fi = frame_interval(frames, fps)
    frame_dt = float(fi["interval_s"])
    v: dict[str, Any] = {"source": exp.get("source"), "t_exp_s": t_exp, "ci_s": exp.get("ci_s"),
                         "frame_interval_s": frame_dt, "frame_interval_basis": fi["basis"],
                         "decoded_interval_s": fi["decoded_s"], "unique_interval_s": fi["unique_s"],
                         "repeated_frames": fi["repeated_frames"], "frame_tol": frame_tol,
                         "limit_s": frame_dt * (1 + frame_tol), "duty": t_exp / frame_dt}
    problems = []
    within = f"T_exp {1000 * t_exp:.1f} ms within one frame interval ({1000 * frame_dt:.1f} ms"
    within += ", between frames that are not repeats)" if fi["unique_s"] is not None else ")"
    if t_exp > frame_dt * (1 + frame_tol):
        problems.append(f"T_exp {1000 * t_exp:.1f} ms is longer than one frame interval ({1000 * frame_dt:.1f} ms"
                        + (", between frames that are not repeats)" if fi["unique_s"] is not None else ")"))
    if exp.get("source") == "given":
        v.update(stability="not applicable (exposure given, not estimated)", stability_tested=False)
        if problems:
            return Check(FLAG, "; ".join(problems), v)
        return Check(PASS, f"given {within}; stability not applicable (not estimated)", v)

    wins = exposure_windows(points, cfg, fps, window_s)
    kinds = [w["kind"] for w in wins]
    n = {k: kinds.count(k) for k in ("accepted", "no interval", "too few tracks", "inconclusive", "declined")}
    acc = [w for w in wins if w["kind"] == "accepted"]
    v.update(windows=wins, window_s=window_s, windows_accepted=n["accepted"], windows_without_interval=n["no interval"],
             windows_too_few_tracks=n["too few tracks"], windows_inconclusive=n["inconclusive"],
             windows_declined=n["declined"])
    counted = ", ".join(f"{n[k]} {label}" for k, label in (
        ("too few tracks", "with too few tracks"), ("inconclusive", "declined for lack of data"),
        ("declined", "declined against a stable estimate"), ("no interval", "without an interval")) if n[k])
    stab: list[str] = []
    if len(acc) >= 2:
        lo = max(w["ci_s"][0] for w in acc)
        hi = min(w["ci_s"][1] for w in acc)
        v["common_interval_s"] = [lo, hi] if lo <= hi else None
        tested = True
        if lo <= hi:
            stability = f"stable over {len(acc)} of {len(wins)} windows"
        else:
            stability = f"unstable: the intervals of {len(acc)} windows do not overlap"
            stab.append(stability)
    else:
        tested = False
        stability = ("stability not tested: no track points" if not wins else
                     f"stability not tested: {len(acc)} of {len(wins)} windows gave an estimate with an interval"
                     + (f" ({counted})" if counted else ""))
        stab.append(stability)
    if n["declined"]:
        why = "; ".join(sorted({w["reason"] for w in wins if w["kind"] == "declined"})[:2])
        stab.append(f"{n['declined']} of {len(wins)} windows declined against a stable estimate ({why})" if tested
                    else f"why declined: {why}")
    v.update(stability=stability, stability_tested=tested)
    problems = stab + problems
    if problems:
        return Check(FLAG, "; ".join(problems), v)
    rest = f" ({counted})" if counted else ""
    return Check(PASS, f"{within}; {stability}{rest}", v)


# 3. Static lights -------------------------------------------------------------------------

def check_static(tracks) -> Check:
    if tracks is None or len(tracks) == 0:
        return Check(NA, "no tracks")
    if "static" not in tracks:
        return Check(NA, "the tracks table has no static column", {"tracks": int(len(tracks))})
    st = tracks[tracks["static"].astype(bool)]
    cr = (st["crossings_pos"].fillna(0) + st["crossings_neg"].fillna(0)).astype(int) if len(st) else np.zeros(0, int)
    n_cross = int(np.count_nonzero(np.asarray(cr) > 0))
    total = int(np.sum(cr))
    v = {"tracks": int(len(tracks)), "static_tracks": int(len(st)), "static_tracks_with_crossings": n_cross,
         "static_crossings": total,
         "track_ids": [int(i) for i in st["track_id"].to_numpy()[np.asarray(cr) > 0][:50]] if len(st) else []}
    if total:
        return Check(FLAG, f"{n_cross} static tracks keep {total} counted gate crossings", v)
    if len(st) == 0:
        return Check(PASS, "no static tracks", v)
    return Check(PASS, f"{len(st)} static tracks, none counted at the gate", v)


# 4. Speed ---------------------------------------------------------------------------------

def _moving(tracks):
    return tracks[~tracks["static"].astype(bool)] if "static" in tracks else tracks


def _track_speeds(tracks) -> tuple[np.ndarray, np.ndarray]:
    """(track ids, best speed in px/s; the track speed where no best speed exists)."""
    best = tracks["best_speed_px_s"].to_numpy(dtype=np.float64) if "best_speed_px_s" in tracks else None
    trk = tracks["track_speed_px_s"].to_numpy(dtype=np.float64)
    sp = trk if best is None else np.where(np.isfinite(best), best, trk)
    return tracks["track_id"].to_numpy(), sp


def check_speed(tracks, cc: dict, cfg: dict, frame_width: int | None = None) -> Check:
    """Speed against the peak gust, at the clip's assumed distance interval."""
    from wfglink.measure.calibration import EmberScale, focal_from_hfov

    c = _pcfg(cfg).get("speed", {})
    gust = _num(cc.get("peak_gust_ms"))
    z = cc.get("z_interval_m")
    focal = _num(cc.get("focal_px"))
    hfov = _num(cc.get("hfov_deg"))
    missing = []
    if gust is None:
        missing.append("peak_gust_ms")
    if not cc.get("gust_source"):
        missing.append("gust_source")
    if not z:
        missing.append("z_interval_m")
    if focal is None and hfov is None:
        missing.append("focal_px or hfov_deg")
    if missing:
        return Check(NA, "clip settings lack " + ", ".join(missing), {"missing": missing})
    if gust < 0:
        return Check(NA, "peak_gust_ms must not be negative", {"peak_gust_ms": gust})
    try:
        z_min, z_max = (float(v) for v in z)
    except (TypeError, ValueError):
        return Check(NA, "z_interval_m must be [z_min, z_max]", {"z_interval_m": z})
    if not 0 < z_min <= z_max:
        return Check(NA, "z_interval_m must satisfy 0 < z_min <= z_max", {"z_interval_m": z})
    if focal is not None and not focal > 0:
        return Check(NA, "focal_px must be positive", {"focal_px": focal})
    focal_src = "focal_px"
    if focal is None:
        if not 0 < hfov < 180:
            return Check(NA, "hfov_deg must lie between 0 and 180", {"hfov_deg": hfov})
        if not frame_width:
            return Check(NA, "hfov_deg given but the full frame width is unknown", {"hfov_deg": hfov})
        focal = focal_from_hfov(int(frame_width), hfov)
        focal_src = f"hfov_deg {hfov:g} over {int(frame_width)} px"
    scale = EmberScale(focal, z_min, z_max)
    m_lo, m_hi = scale.m_per_px
    factor = float(c.get("gust_factor", 1.5))
    margin = float(c.get("margin_ms", 8.0))
    limit = factor * gust + margin
    v: dict[str, Any] = {"peak_gust_ms": gust, "gust_source": cc.get("gust_source"), "limit_ms": limit,
                         "z_interval_m": [z_min, z_max], "focal_px": focal, "focal_source": focal_src}
    if tracks is None or len(tracks) == 0:
        return Check(NA, "no tracks", v)
    ids, sp = _track_speeds(_moving(tracks))
    ok = np.isfinite(sp)
    ids, sp = ids[ok], sp[ok]
    if sp.size == 0:
        return Check(NA, "no moving track with a speed", v)
    lo, hi = sp * m_lo, sp * m_hi
    flagged = (lo > limit) & (hi > limit)       # the same as lo > limit, since Z_min <= Z_max
    frac = float(flagged.mean())
    pct = float(c.get("percentile", 99))
    p = float(np.percentile(sp, pct))
    v.update(tracks=int(sp.size), flagged=int(flagged.sum()), flagged_fraction=frac,
             flagged_track_ids=[int(i) for i in ids[flagged][:50]], percentile=pct,
             speed_percentile_ms=[p * m_lo, p * m_hi], speed_max_ms=[float(sp.max() * m_lo), float(sp.max() * m_hi)])
    if frac > float(c.get("max_flagged_fraction", 0.0)):
        return Check(FLAG, f"{int(flagged.sum())} of {sp.size} tracks faster than {limit:.1f} m/s even at "
                           f"Z_min = {z_min:g} m", v)
    return Check(PASS, f"no track faster than {limit:.1f} m/s at Z_min = {z_min:g} m; "
                       f"p{pct:g} speed {p * m_lo:.1f} to {p * m_hi:.1f} m/s", v)


# 5. Direction -----------------------------------------------------------------------------

def circular_mean_deg(deg: np.ndarray, weights: np.ndarray | None = None) -> tuple[float, float]:
    """Weighted circular mean (degrees, in (-180, 180]) and mean resultant length R in [0, 1]."""
    a = np.radians(np.asarray(deg, dtype=np.float64))
    w = np.ones_like(a) if weights is None else np.asarray(weights, dtype=np.float64)
    sw = float(w.sum())
    if a.size == 0 or not sw > 0:
        return float("nan"), float("nan")
    c, s = float((w * np.cos(a)).sum() / sw), float((w * np.sin(a)).sum() / sw)
    return float(np.degrees(np.arctan2(s, c))), float(math.hypot(c, s))


def angle_diff_deg(a: float, b: float) -> float:
    """a - b wrapped to (-180, 180]."""
    d = (a - b) % 360.0
    return d - 360.0 if d > 180.0 else d


def check_direction(tracks, cc: dict, cfg: dict) -> Check:
    c = _pcfg(cfg).get("direction", {})
    drift = _num(cc.get("drift_deg"))
    missing = [k for k, ok in (("drift_deg", drift is not None), ("drift_basis", bool(cc.get("drift_basis")))) if not ok]
    if missing:
        return Check(NA, "clip settings lack " + ", ".join(missing), {"missing": missing})
    tol = _num(cc.get("drift_tolerance_deg"))
    tol_src = "drift_tolerance_deg"
    if tol is None:
        tol, tol_src = float(c.get("tolerance_deg", 45.0)), "plausibility.direction.tolerance_deg"
    min_r = float(c.get("min_resultant", 0.3))
    v: dict[str, Any] = {"drift_deg": drift, "drift_basis": cc.get("drift_basis"), "tolerance_deg": tol,
                         "tolerance_source": tol_src, "convention": "image axes: 0 = right, +90 = down"}
    if tracks is None or len(tracks) == 0:
        return Check(NA, "no tracks", v)
    mv = _moving(tracks)
    d = mv["direction_deg"].to_numpy(dtype=np.float64)
    w = mv["track_speed_px_s"].to_numpy(dtype=np.float64)    # the speed of the same straight-line fit
    ok = np.isfinite(d) & np.isfinite(w) & (w > 0)
    if not ok.any():
        return Check(NA, "no moving track with a direction", v)
    mean, r = circular_mean_deg(d[ok], w[ok])
    diff = angle_diff_deg(mean, drift)
    spread = float(np.degrees(math.sqrt(-2.0 * math.log(r)))) if r > 0 else float("inf")
    v.update(tracks=int(ok.sum()), mean_direction_deg=mean, resultant_length=r, circular_spread_deg=spread,
             difference_deg=diff, min_resultant=min_r)
    if r < min_r:
        return Check(FLAG, f"no dominant direction (resultant length {r:.2f}, spread {spread:.0f} deg)", v)
    if abs(diff) > tol:
        return Check(FLAG, f"mean direction {mean:.0f} deg differs from the annotated {drift:.0f} deg "
                           f"({cc.get('drift_basis')}) by {diff:+.0f} deg (tolerance {tol:g})", v)
    return Check(PASS, f"mean direction {mean:.0f} deg within {tol:g} deg of the annotated {drift:.0f} deg "
                       f"({diff:+.0f} deg, spread {spread:.0f} deg)", v)


# 6. Determinism ---------------------------------------------------------------------------

def _first_difference(x, y) -> int | None:
    """Index of the first element where two columns differ (NaN equals NaN), None when equal."""
    import pandas as pd

    a, b = pd.Series(x).reset_index(drop=True), pd.Series(y).reset_index(drop=True)
    if a.equals(b):
        return None
    same = (a == b) | (a.isna() & b.isna())
    bad = np.flatnonzero(~same.to_numpy(dtype=bool))
    return int(bad[0]) if bad.size else 0     # equal values with different dtypes: report row 0


def compare_tables(a: dict, b: dict, ignore: dict[str, list[str]] | None = None) -> dict[str, Any] | None:
    """First difference between two sets of run tables, or None when they are exactly equal."""
    ignore = ignore or {}
    for name in a:
        da, db = a[name], b.get(name)
        if da is None or db is None:
            if da is None and db is None:
                continue
            return {"table": name, "column": None, "detail": "table missing in one run"}
        skip = set(ignore.get(name, []))
        ca = [col for col in da.columns if col not in skip]
        cb = [col for col in db.columns if col not in skip]
        if ca != cb:
            return {"table": name, "column": None, "detail": f"columns differ: {sorted(set(ca) ^ set(cb))}"}
        if len(da) != len(db):
            return {"table": name, "column": None, "detail": f"{len(da)} rows against {len(db)}"}
        for col in ca:
            i = _first_difference(da[col], db[col])
            if i is not None:
                return {"table": name, "column": col, "row": i,
                        "detail": f"row {i}: {da[col].iloc[i]!r} against {db[col].iloc[i]!r}"}
    return None


def run_settings(summary: dict, cc: dict) -> dict[str, Any]:
    """The run's own ROI, gate, exposure and scale (from summary.json), for a rerun.

    The run's T_exp, given or estimated and accepted, goes to the reruns, so they run the
    tracking pass that wrote the run's tables.
    """
    inp = summary.get("input") or {}
    roi = inp.get("roi_px") or cc.get("roi")
    g = (summary.get("totals") or {}).get("gate")
    gate = {"p1": list(g["p1"]), "p2": list(g["p2"]), "name": g.get("name", "gate")} if g else (
        {"p1": cc["gate"][:2], "p2": cc["gate"][2:], "name": "gate"} if cc.get("gate") else None)
    exp = summary.get("exposure") or {}
    t_exp = _num(exp.get("t_exp_s"))
    units = summary.get("units") or {}
    seg = inp.get("segment_s") or [0.0, None]
    return {"roi": roi, "gate": gate, "t_exp": t_exp,
            "t_exp_from": None if t_exp is None else f"the run ({exp.get('source') or 'estimated'})",
            "m_per_px": units.get("m_per_px"), "distance_m": units.get("distance_m"),
            "start_s": float(seg[0] or 0.0), "end_s": None if seg[1] is None else float(seg[1])}


def check_determinism(video: Path, summary: dict, cc: dict, cfg: dict, seconds: float | None = None,
                      work_dir: str | Path | None = None, frames=None) -> Check:
    """Two reruns of process_clip on a short segment must write identical tables.

    The segment starts where the run's detector was first ready (frames.parquet), so a clip
    that opens on a still picture is not compared on frames without any detection.
    """
    from wfglink.outputs import process as proc
    from wfglink.provenance import sha256_json

    c = _pcfg(cfg).get("determinism", {})
    seconds = float(c.get("seconds", 2.0)) if seconds is None else float(seconds)
    if not seconds > 0:
        return Check(NA, "determinism rerun switched off (0 seconds)")
    if not Path(video).exists():
        return Check(NA, f"clip file not found: {video}")
    rs = run_settings(summary, cc)
    start = rs["start_s"]
    if frames is not None and len(frames) and "ready" in frames:
        ready = frames[frames["ready"].astype(bool)]
        if len(ready):
            start += float(ready["t"].iloc[0])
    end = start + seconds
    if rs["end_s"] is not None:
        end = min(end, rs["end_s"])
    v: dict[str, Any] = {"segment_s": [start, end], "tables": list(TABLES),
                         "ignored_columns": c.get("ignore_columns", {"frames": ["ms"]}), "overlay": False,
                         "t_exp_s": rs["t_exp"],
                         "t_exp_from": rs["t_exp_from"]
                         or "estimated again by each rerun (the run's estimate declined)",
                         "config_is_run_config": sha256_json(cfg) == summary.get("config_sha256")}
    base = Path(tempfile.mkdtemp(prefix="wfglink_determinism_", dir=work_dir))
    try:
        runs = []
        for k in range(2):
            out = base / f"run{k}"
            proc.process_clip(video, out, cfg, gate=rs["gate"], t_exp=rs["t_exp"], overlay=False,
                              max_seconds=end, m_per_px=rs["m_per_px"], distance_m=rs["distance_m"],
                              start_s=start, roi=rs["roi"])
            s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            runs.append({name: read_table(out, name, s) for name in TABLES})
        v["rows"] = {name: (None if runs[0][name] is None else int(len(runs[0][name]))) for name in TABLES}
        diff = compare_tables(runs[0], runs[1], v["ignored_columns"])
    finally:
        shutil.rmtree(base, ignore_errors=True)
    v["first_difference"] = diff
    if diff is None and not v["rows"].get("detections"):
        return Check(NA, f"the rerun of {start:g} to {end:g} s has no detections; nothing to compare", v)
    if diff is None:
        return Check(PASS, f"identical tables on two reruns of {start:g} to {end:g} s", v)
    where = diff["table"] + (f".{diff['column']}" if diff.get("column") else "")
    return Check(FLAG, f"reruns differ first in {where}: {diff['detail']}", v)


# All checks -------------------------------------------------------------------------------

def _full_width(summary: dict, video: Path | None) -> int | None:
    inp = summary.get("input") or {}
    if inp.get("source_size"):
        return int(inp["source_size"][0])
    if not inp.get("roi_px"):
        return int(inp["width"]) if inp.get("width") else None
    if video is not None and Path(video).exists():
        from wfglink.sitting.recordings import probe_video

        return probe_video(Path(video)).get("width")
    return None


def _earlier_determinism(prev: dict | None, summary: dict, cfg_sha: str) -> Check | None:
    """The determinism result of an earlier plausibility.json of the same run and config, if any."""
    if not prev:
        return None
    old = (prev.get("checks") or {}).get("determinism") or {}
    same = (prev.get("input_sha256") == (summary.get("input") or {}).get("sha256")
            and prev.get("run_config_sha256") == summary.get("config_sha256") and prev.get("config_sha256") == cfg_sha)
    if not same or old.get("status") not in (PASS, FLAG):
        return None
    kept = {"created": prev.get("created"), "git_commit": prev.get("git_commit"), "git_dirty": prev.get("git_dirty")}
    vals = {k: val for k, val in (old.get("values") or {}).items() if k != "kept_from"}
    reason = old.get("reason", "")
    if not reason.startswith("kept from"):
        reason = f"kept from the check of {prev.get('created')} (rerun switched off now): {reason}"
    return Check(old["status"], reason, {**vals, "kept_from": (old.get("values") or {}).get("kept_from", kept)})


def run_plausibility(run_dir: str | Path, clip_settings: str | Path | dict, cfg: dict | None = None,
                     determinism_seconds: float | None = None, write: bool = True,
                     work_dir: str | Path | None = None) -> dict[str, Any]:
    """Every check on one run folder; writes plausibility.json next to summary.json (write=True).

    clip_settings is a clip settings file or an already loaded dict (then its `file` is
    resolved against the project folder). With write=True the statuses are also copied into
    summary.json (key "plausibility"). When the determinism rerun is switched off, a pass or
    flag from an earlier plausibility.json of the same run and config is kept and marked so.
    """
    from wfglink import PROJECT_ROOT
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.validate.clips import load_clip_settings

    cfg = cfg or load_config()
    cfg_sha = sha256_json(cfg)
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    inp = summary.get("input") or {}
    if isinstance(clip_settings, dict):
        cc, settings_path = clip_settings, None
        video = PROJECT_ROOT / cc["file"] if cc.get("file") else Path(inp["path"])
        settings_sha = sha256_json(cc)
    else:
        cc, video, settings_path = load_clip_settings(clip_settings)
        settings_sha = sha256_file(settings_path)
    # Do the settings belong to this run? By content when the clip file is here, else by name.
    if video.exists() and inp.get("sha256"):
        same_input = sha256_file(video) == inp["sha256"]
        settings_match, match_basis = same_input, "SHA-256 of the clip file"
    else:
        same_input = False
        settings_match = video.name == Path(str(inp.get("path", ""))).name
        match_basis = "file name only (clip file not found)"
    frames = read_table(run_dir, "frames", summary)
    tracks = read_table(run_dir, "tracks", summary)
    points = read_table(run_dir, "track_points", summary)
    seg = inp.get("segment_s") or [0.0, None]
    segment = (float(seg[0] or 0.0), None if seg[1] is None else float(seg[1]))
    fps = _num(inp.get("fps"))
    other = "the clip settings name another video than the run's input"
    checks = {
        "timing": check_timing(frames, cfg, packet_times(video) if same_input else None, segment, fps),
        "exposure": check_exposure(summary, points, frames, cfg, fps),
        "static_lights": check_static(tracks),
        "speed": check_speed(tracks, cc, cfg, _full_width(summary, video)) if settings_match else Check(NA, other),
        "direction": check_direction(tracks, cc, cfg) if settings_match else Check(NA, other),
    }
    prev = None
    if (run_dir / "plausibility.json").exists():
        try:
            prev = json.loads((run_dir / "plausibility.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prev = None
    secs = determinism_seconds
    if secs is None:
        secs = float(_pcfg(cfg).get("determinism", {}).get("seconds", 2.0))
    if not same_input:
        checks["determinism"] = Check(NA, "clip file missing or not the run's input (SHA-256 differs)")
        checks["timing"].values["container_note"] = ("clip file missing or not the run's input; "
                                                     "container times not compared")
    elif not float(secs) > 0 and (kept := _earlier_determinism(prev, summary, cfg_sha)) is not None:
        checks["determinism"] = kept
    else:
        checks["determinism"] = check_determinism(video, summary, cc, cfg, secs, work_dir, frames)
    out = {
        "schema_version": 1,
        "created": now_shanghai(),
        "run_dir": str(run_dir),
        "clip_settings": None if settings_path is None else str(settings_path),
        "clip_settings_sha256": settings_sha,
        "clip_id": cc.get("clip_id") or video.stem,
        "input_sha256": inp.get("sha256"),
        "clip_file_is_run_input": same_input,
        "clip_settings_match_run": settings_match,
        "clip_settings_match_basis": match_basis,
        "segment_s": list(segment),
        "config_sha256": cfg_sha,
        "run_config_sha256": summary.get("config_sha256"),
        **git_state(),
        "checks": {k: ch.as_dict() for k, ch in checks.items()},
        "flagged": [k for k, ch in checks.items() if ch.status == FLAG],
        "not_applicable": [k for k, ch in checks.items() if ch.status == NA],
    }
    if write:
        (run_dir / "plausibility.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                                                   encoding="utf-8")
        # Plan section 6: summary.json carries the plausibility flags (details in plausibility.json).
        summary["plausibility"] = {"file": "plausibility.json", "created": out["created"],
                                   "status": {k: ch.status for k, ch in checks.items()},
                                   "flagged": out["flagged"], "not_applicable": out["not_applicable"]}
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str),
                                              encoding="utf-8")
    return out
