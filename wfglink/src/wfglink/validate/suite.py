"""Evaluate the pipeline on synthetic suites against ground truth (plan sections 4.1 and 4.2).

Per clip, file mode with two passes:
1. Track without an exposure time and estimate T_exp from the track points (Deming fit
   of streak length on per-point track speed, robust, bootstrap over tracks).
2. Track again with that T_exp given to the tracker; every reported metric comes from
   this pass.

Scored frames start when the detector's background model is ready (the booth shows no
numbers before that either); every truth used for a score (detection, tracking, gate
crossings by their bracketing frames, the field) is restricted to the scored frames.
Metrics: detection precision, recall and F1; CLEAR MOT; track-speed and streak-speed
errors (separately), direction error; Cumulative Particle Count (gate) and Particle
Number Flux (projected) errors with interval coverage; the exposure estimate error; the
field errors. `score_clip` computes them from the recorded tables, so oracle inputs built
from the truth go through the same code (tests/test_validation_oracle.py). A suite summary
groups clips by case (one factor varied at a time) and pools the seeds.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.config import load_config
from wfglink.io.sources import FileSource
from wfglink.measure.exposure import estimate_exposure
from wfglink.measure.velocity import add_point_velocities
from wfglink.pipeline import Pipeline
from wfglink.validate.metrics import (detection_metrics, gate_metrics, load_truth, tracking_metrics,
                                      truth_field, velocity_metrics)


def run_pipeline(video: Path, cfg: dict, gate: dict | None, fps: float | None,
                 t_exp_hint: float | None = None) -> Pipeline:
    pipe = Pipeline(cfg, gate=gate, fps=fps, record=True, t_exp_hint=t_exp_hint)
    src = FileSource(video)
    src.open()
    try:
        while (f := src.read()) is not None:
            pipe.process(f)
    finally:
        src.close()
    pipe.finish()
    return pipe


def exposure_from_tracks(points, cfg: dict, fps: float):
    """T_exp estimate from a track-points table (pass 1)."""
    if points is None or len(points) == 0:
        return None
    pts = add_point_velocities(points, cfg)
    return estimate_exposure(pts["track_id"].to_numpy(), pts["t"].to_numpy(), pts["speed_poly"].to_numpy(),
                             pts["length"].to_numpy(), pts["flags"].to_numpy(), fps=fps, cfg=cfg,
                             interior=pts["interior"].to_numpy(dtype=bool))


def _first_gate(meta: dict) -> dict | None:
    gates = meta.get("gates") or []
    return {"p1": gates[0]["p1"], "p2": gates[0]["p2"], "name": gates[0]["name"]} if gates else None


def evaluate_clip(clip_dir: str | Path, cfg: dict | None = None) -> dict[str, Any]:
    """Run both pipeline passes on one synthetic clip and score them (`score_clip`)."""
    cfg = cfg or load_config()
    clip_dir = Path(clip_dir)
    meta = json.loads((clip_dir / "meta.json").read_text(encoding="utf-8"))
    video = clip_dir / meta.get("video", "video.mp4")
    fps = float(meta["fps"])
    gate = _first_gate(meta)
    t0 = time.perf_counter()

    p1 = run_pipeline(video, cfg, gate, fps)
    exposure = exposure_from_tracks(p1.tables()["tracks"], cfg, fps)
    t_exp = exposure.t_exp if exposure is not None and exposure.ok else None
    pipe = run_pipeline(video, cfg, gate, fps, t_exp_hint=t_exp)
    tabs = pipe.tables()
    seconds = time.perf_counter() - t0
    out: dict[str, Any] = {"clip": str(clip_dir), "seconds": round(seconds, 2),
                           "proc_ms_median": pipe.stats.as_dict()["proc_ms_median"]}
    out.update(score_clip(clip_dir, tabs, pipe.counter, exposure, cfg, meta=meta))
    return out


def score_clip(clip_dir: str | Path, tabs: dict, counter, exposure, cfg: dict,
               meta: dict | None = None, truth: dict | None = None) -> dict[str, Any]:
    """Every metric of one clip from the pipeline's recorded tables (pass 2).

    `tabs` holds detections, frames (frame, t, ready) and tracks as `Pipeline.tables()`
    writes them, `counter` is the pipeline's GateCounter (or None) and `exposure` the
    pass 1 estimate (or None). Kept apart from the pipeline runs so that oracle inputs
    built from the truth can be scored by exactly this code.
    """
    clip_dir = Path(clip_dir)
    if meta is None:
        meta = json.loads((clip_dir / "meta.json").read_text(encoding="utf-8"))
    truth = truth or load_truth(clip_dir)
    t_exp = exposure.t_exp if exposure is not None and exposure.ok else None
    frames = tabs["frames"]
    ready = frames[frames["ready"].astype(bool)]
    scored = sorted(set(ready["frame"].astype(int).tolist()))
    out: dict[str, Any] = {"frames": int(len(frames)), "frames_scored": len(scored)}
    out.update(frame_integrity(truth.get("frames"), frames["frame"].astype(int).tolist(), scored))
    parts = truth["particles"]
    out["detection"] = detection_metrics(parts, tabs["detections"], cfg, frames=scored)
    w, h = meta.get("frame_size", [0, 0])
    if scored and w and h:
        out["fp_per_mpx_frame"] = out["detection"]["fp"] / (len(scored) * w * h / 1e6)
    out["completeness"] = completeness_by_snr(parts, tabs["detections"], meta, scored, cfg)
    out["snr50"] = snr50(out["completeness"]) if out["completeness"] else None
    out["snr50_upper_bound"] = snr50_is_upper_bound(out["completeness"]) if out["completeness"] else None
    tracks = tabs["tracks"]
    # Static tracks (static lights, by the tracker's own flag) are never reported as embers.
    # The whole track is dropped; the gate counter keeps an ember's crossings from before
    # its slow window, which only matters for an ember that comes to rest.
    trk = tracks[~tracks["static"].astype(bool) & tracks["frame"].isin(scored)] if len(tracks) else tracks
    if scored:
        # Always scored: a clip whose tracker found nothing has MOTA 0, not a missing value.
        out["tracking"] = tracking_metrics(parts, trk, cfg, frames=scored)
        out["track_fp_per_frame"] = out["tracking"]["fp"] / len(scored)
    if len(trk):
        pv = add_point_velocities(trk, cfg, t_exp=t_exp)
        out["velocity_track"] = velocity_metrics(parts, pv, cfg, vx_col="vx_poly", vy_col="vy_poly",
                                                 x_col="x_meas", y_col="y_meas")
        if truth.get("frames") is not None:
            out["field"] = _field_scores(clip_dir, pv, parts, truth["frames"], scored, meta, cfg)
        if t_exp is not None and "speed_streak" in pv:
            out["velocity_streak"] = velocity_metrics(parts, pv, cfg, vx_col="vx_streak", vy_col="vy_streak",
                                                      speed_col="speed_streak", x_col="x_meas", y_col="y_meas")
    true_exp = float(meta.get("exposure_s", np.nan))
    ok = bool(exposure is not None and exposure.ok)
    out["exposure"] = {"true_s": true_exp, "ok": ok, "estimate_s": t_exp,
                       "ci_s": [exposure.ci_low, exposure.ci_high] if ok else None,
                       "rel_error": (t_exp / true_exp - 1) if t_exp is not None and true_exp > 0 else None,
                       "reason": None if exposure is None else exposure.reason}
    t_ready = float(ready["t"].iloc[0]) if scored else None
    if counter is not None and truth.get("gate") is not None and scored:
        # The counter runs on the PTS clock (exposure start) and the truth on exposure
        # midpoints, so the truth is selected by its bracketing frames, not by time.
        out["gate"] = gate_metrics(counter, truth["gate"], parts, t0=t_ready, cfg=cfg,
                                   frame_range=(scored[0], scored[-1]), truth_frames=truth.get("frames"))

    # Bright embers only (SNR >= validate.bright_snr): fainter embers become "don't care", so
    # these metrics describe the method where the detector can see, apart from its limit.
    # The gate estimate counts some fainter embers too, so the bright-ember truth is a lower
    # bound for it, as the all-visible truth is an upper bound.
    bright_snr = float(cfg.get("validate", {}).get("bright_snr", 20.0))
    psnr = particle_snr(parts, meta)
    if psnr is not None:
        bright_ids = psnr.index[psnr >= bright_snr]
        pb = parts.copy()
        pb["visible"] = pb["visible"] & pb["particle_id"].isin(bright_ids)
        out["detection_bright"] = detection_metrics(pb, tabs["detections"], cfg, frames=scored)
        if scored:
            out["tracking_bright"] = tracking_metrics(pb, trk, cfg, frames=scored)
        if "gate" in out:
            gb = truth["gate"][truth["gate"]["particle_id"].isin(bright_ids)]
            out["gate_bright"] = gate_metrics(counter, gb, pb, t0=t_ready, cfg=cfg,
                                              frame_range=(scored[0], scored[-1]), truth_frames=truth.get("frames"))
            n_est = out["gate"]["estimate"]["gross"]
            lo, hi = out["gate_bright"]["truth"]["gross"], out["gate"]["truth"]["gross"]
            out["gate_between_bounds"] = bool(lo <= n_est <= hi)
    return out


def frame_integrity(truth_frames, analysed: list[int], scored: list[int]) -> dict[str, int]:
    """Frames inside the scored span that the pipeline dropped although they were real
    (a false repeat), and repeated frames it analysed anyway.

    Dropped real frames are simply not scored, so their misses would not show anywhere
    else; an analysed repeat gives the tracker a zero displacement.
    """
    if truth_frames is None or not scored:
        return {}
    span = truth_frames[(truth_frames["frame"] >= scored[0]) & (truth_frames["frame"] <= scored[-1])]
    dup = span["duplicate"].to_numpy(dtype=bool)
    got = span["frame"].isin(set(analysed)).to_numpy()
    return {"frames_real_dropped": int(np.sum(~dup & ~got)), "frames_repeat_analysed": int(np.sum(dup & got))}


def _field_scores(clip_dir: Path, pv, parts, truth_frames, scored: list[int], meta: dict, cfg: dict) -> dict:
    """Field errors against the true field of the scored frames (not the whole clip's)."""
    import pandas as pd

    from wfglink.measure.field import estimate_field, field_errors

    fs = tuple(int(v) for v in meta.get("frame_size", [0, 0]))
    grid = tuple(int(v) for v in cfg.get("field", {}).get("grid", [16, 9]))
    tf = clip_dir / "truth_field.parquet"
    eulerian = pd.read_parquet(tf) if tf.exists() else None
    truth = truth_field(parts, truth_frames, fs, grid, frames=scored, eulerian=eulerian)
    est_field = estimate_field(pv.assign(static=False), fs, cfg)
    return field_errors(est_field, truth)


def particle_snr(parts, meta: dict):
    """Median SNR of each particle over its rows (the generator's definition), or None."""
    noise = float(meta.get("snr_model", {}).get("noise_luma_dn_ref", float("nan")))
    if not np.isfinite(noise) or len(parts) == 0:
        return None
    snr = parts["flux"] / (noise * 2 * np.sqrt(np.pi) * parts["sigma_px"])
    return snr.groupby(parts["particle_id"]).median()


SNR_BINS = (0, 5, 10, 15, 20, 30, 50, float("inf"))


def completeness_by_snr(parts, detections, meta: dict, frames: list[int], cfg: dict) -> dict[str, Any]:
    """Fraction of visible embers with a detection within the match radius, per SNR bin.

    SNR is the generator's definition (meta snr_model): integrated flux over the noise of a
    PSF-matched aperture, before compression. Not one-to-one: this measures how faint an
    ember can be and still be found, not precision.
    """
    from scipy.spatial import cKDTree

    sm = meta.get("snr_model", {})
    noise = float(sm.get("noise_luma_dn_ref", np.nan))
    v = parts[(parts["kind"] == "ember") & parts["visible"] & ~parts["in_large_region"] & parts["frame"].isin(frames)]
    if not np.isfinite(noise) or len(v) == 0:
        return {}
    snr = v["flux"].to_numpy() / (noise * 2 * np.sqrt(np.pi) * v["sigma_px"].to_numpy())
    vm = cfg.get("validate", {})
    rad = np.maximum(float(vm.get("match_radius_px", 3.0)),
                     float(vm.get("streak_radius_frac", 0.5)) * v["streak_length_px"].to_numpy())
    hit = np.zeros(len(v), bool)
    det_by = {f: g for f, g in detections.groupby("frame")} if len(detections) else {}
    fr = v["frame"].to_numpy()
    xy = v[["x_mid", "y_mid"]].to_numpy()
    for f in np.unique(fr):
        g = det_by.get(f)
        if g is None or len(g) == 0:
            continue
        sel = fr == f
        dist, _ = cKDTree(g[["x", "y"]].to_numpy()).query(xy[sel])
        hit[sel] = dist <= rad[sel]
    out = {}
    for lo, hi in zip(SNR_BINS[:-1], SNR_BINS[1:]):
        m = (snr > lo) & (snr <= hi)
        out[f"{lo:g}-{hi:g}"] = [int(hit[m].sum()), int(m.sum())]
    return out


SNR50_MIN_N = 20      # bins with fewer embers are too noisy for the 50% crossing


def _snr_curve(bins: dict[str, list[int]]) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for key, (h, n) in bins.items():
        lo, hi = (float(t) for t in key.split("-"))
        if n < SNR50_MIN_N:
            continue
        xs.append((lo + hi) / 2 if np.isfinite(hi) else lo * 1.25)
        ys.append(h / n)
    return xs, ys


def snr50_is_upper_bound(bins: dict[str, list[int]]) -> bool | None:
    """True when completeness is already at least 50% in the lowest usable bin.

    `snr50` then returns that bin's centre (or, when completeness dips below 50% in a
    higher bin, the crossing after the dip), while completeness first reaches 50% somewhere
    below it: the value is an upper bound, not a measurement (a perfect detector reports 2.5).
    """
    _, ys = _snr_curve(bins)
    return bool(ys[0] >= 0.5) if ys else None


def snr50(bins: dict[str, list[int]]) -> float | None:
    """SNR at 50% completeness, interpolated linearly between bin centres (None if never
    reached). When the lowest usable bin is already at 50% or more this is that bin's
    centre, an upper bound (`snr50_is_upper_bound`)."""
    xs, ys = _snr_curve(bins)
    for i in range(1, len(xs)):
        if ys[i - 1] < 0.5 <= ys[i]:
            return float(xs[i - 1] + (0.5 - ys[i - 1]) * (xs[i] - xs[i - 1]) / (ys[i] - ys[i - 1]))
    if ys and ys[0] >= 0.5:
        return float(xs[0])
    return None


def _job(args):
    clip_dir, cfg = args
    try:
        return evaluate_clip(clip_dir, cfg)
    except Exception as exc:  # one broken clip must not lose the suite
        return {"clip": str(clip_dir), "error": f"{type(exc).__name__}: {exc}"}


def evaluate_suite(root: str | Path, cfg: dict | None = None, workers: int = 1) -> dict[str, Any]:
    """Evaluate every clip in a generated suite (out_root with manifest.json)."""
    cfg = cfg or load_config()
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    jobs = [(root / e["path"], cfg) for e in manifest["clips"]]
    if workers > 1:
        import multiprocessing as mp

        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
            results = list(ex.map(_job, jobs))
    else:
        results = [_job(j) for j in jobs]
    for e, r in zip(manifest["clips"], results):
        r.update(case=e["case"], factor=e["factor"], label=e["label"], seed=e["seed"])
    return {"suite": manifest.get("suite"), "clips": results, "aliases": manifest.get("aliases", {}),
            "cases": summarize(results)}


def _get(d: dict, path: str):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


SUMMARY_KEYS = {
    "f1": "detection.f1", "precision": "detection.precision", "recall": "detection.recall",
    "mota": "tracking.mota", "id_switches": "tracking.id_switches",
    "track_speed_med_rel_err": "velocity_track.median_rel_speed_err",
    "track_speed_bias": "velocity_track.median_signed_rel_speed_err",
    "direction_med_err_deg": "velocity_track.median_angle_err_deg",
    "streak_speed_med_rel_err": "velocity_streak.median_rel_speed_err",
    "exposure_rel_err": "exposure.rel_error", "exposure_bias": "exposure.rel_error",
    "exposure_ok": "exposure.ok",
    "cpc_gross_rel_err": "gate.cpc_gross.rel_err", "cpc_gross_bias": "gate.cpc_gross.rel_err",
    "cpc_gross_in_ci": "gate.cpc_gross.in_ci",
    "pnf_rel_err": "gate.pnf.rel_err",
    "fp_per_mpx_frame": "fp_per_mpx_frame", "recall_bright": "detection_bright.recall",
    "track_fp_per_frame": "track_fp_per_frame",
    "gate_between_bounds": "gate_between_bounds",
    "field_rmse_ember_u": "field.rmse_ember_u", "field_rmse_air_u": "field.rmse_air_u",
    "field_rmse_ember_v": "field.rmse_ember_v", "field_ci_coverage": "field.ci_coverage_ember",
}
# Errors whose goal is on their size (plan 4.2): the median over seeds of the absolute
# per-clip error. A median of signed errors lets seeds at +20% and -20% report about 0;
# the signed medians are kept as *_bias.
SUMMARY_ABS = {"exposure_rel_err", "cpc_gross_rel_err", "pnf_rel_err"}
# Fractions of clips: the mean over seeds.
SUMMARY_MEAN = {"cpc_gross_in_ci", "gate_between_bounds", "exposure_ok"}


def summarize(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per case: the median over seeds of each metric (of its absolute value for the
    errors in SUMMARY_ABS, the mean for the fractions in SUMMARY_MEAN), the count of
    clips, and completeness and snr50 from the seeds pooled."""
    by: dict[str, list[dict]] = {}
    for r in results:
        by.setdefault(r.get("case", "?"), []).append(r)
    out = {}
    for case, rs in by.items():
        row: dict[str, Any] = {"clips": len(rs), "errors": sum(1 for r in rs if "error" in r)}
        for name, path in SUMMARY_KEYS.items():
            vals = [_get(r, path) for r in rs]
            vals = [float(v) for v in vals if v is not None and np.isfinite(float(v))]
            if name in SUMMARY_ABS:
                vals = [abs(v) for v in vals]
            agg = np.mean if name in SUMMARY_MEAN else np.median
            row[name] = float(agg(vals)) if vals else None
        pooled: dict[str, list[int]] = {}
        for r in rs:
            for k, (h, n) in (r.get("completeness") or {}).items():
                acc = pooled.setdefault(k, [0, 0])
                acc[0] += h
                acc[1] += n
        inci = [bool(_get(r, "gate.cpc_gross.in_ci")) for r in rs if _get(r, "gate.cpc_gross.in_ci") is not None]
        if inci:
            from wfglink.validate.metrics import coverage

            row["cpc_coverage"] = coverage(inci)        # k, n, fraction and its Clopper-Pearson interval
        row["completeness"] = {k: round(h / n, 3) if n else None for k, (h, n) in pooled.items()}
        row["snr50"] = snr50(pooled) if pooled else None
        row["snr50_upper_bound"] = snr50_is_upper_bound(pooled) if pooled else None
        out[case] = row
    return out
