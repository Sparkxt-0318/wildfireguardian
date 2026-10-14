"""Evaluate the pipeline on synthetic suites against ground truth (plan sections 4.1 and 4.2).

Per clip, file mode with two passes:
1. Track without an exposure time and estimate T_exp from the track points (Deming fit
   of streak length on per-point track speed, robust, bootstrap over tracks).
2. Track again with that T_exp given to the tracker; every reported metric comes from
   this pass.

Scored frames start when the detector's background model is ready (the booth shows no
numbers before that either). Metrics: detection precision, recall and F1; CLEAR MOT;
track-speed and streak-speed errors (separately), direction error; Cumulative Particle
Count (gate) and Particle Number Flux (projected) errors with interval coverage; the
exposure estimate error. A suite summary groups clips by case (one factor varied at a
time) and pools the seeds.
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
                                      velocity_metrics)


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


def evaluate_clip(clip_dir: str | Path, cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    clip_dir = Path(clip_dir)
    meta = json.loads((clip_dir / "meta.json").read_text(encoding="utf-8"))
    truth = load_truth(clip_dir)
    video = clip_dir / meta.get("video", "video.mp4")
    fps = float(meta["fps"])
    gates = meta.get("gates") or []
    gate = {"p1": gates[0]["p1"], "p2": gates[0]["p2"], "name": gates[0]["name"]} if gates else None
    t0 = time.perf_counter()

    p1 = run_pipeline(video, cfg, gate, fps)
    est = exposure_from_tracks(p1.tables()["tracks"], cfg, fps)
    t_exp = est.t_exp if est is not None and est.ok else None
    pipe = run_pipeline(video, cfg, gate, fps, t_exp_hint=t_exp)
    tabs = pipe.tables()
    seconds = time.perf_counter() - t0

    frames = tabs["frames"]
    ready = frames[frames["ready"]]
    scored = ready["frame"].astype(int).tolist()
    out: dict[str, Any] = {"clip": str(clip_dir), "frames": int(len(frames)), "frames_scored": len(scored),
                           "seconds": round(seconds, 2), "proc_ms_median": pipe.stats.as_dict()["proc_ms_median"]}
    parts = truth["particles"]
    out["detection"] = detection_metrics(parts, tabs["detections"], cfg, frames=scored)
    out["completeness"] = completeness_by_snr(parts, tabs["detections"], meta, scored, cfg)
    out["snr50"] = snr50(out["completeness"]) if out["completeness"] else None
    tracks = tabs["tracks"]
    if len(tracks):
        tracks = tracks[~tracks["static"].astype(bool)]   # static lights are not reported as embers
        trk = tracks[tracks["frame"].isin(scored)]
        out["tracking"] = tracking_metrics(parts, trk, cfg, frames=scored)
        pv = add_point_velocities(trk, cfg, t_exp=t_exp)
        out["velocity_track"] = velocity_metrics(parts, pv, cfg, vx_col="vx_poly", vy_col="vy_poly",
                                                 x_col="x_meas", y_col="y_meas")
        if t_exp is not None and "speed_streak" in pv:
            out["velocity_streak"] = velocity_metrics(parts, pv, cfg, vx_col="vx_streak", vy_col="vy_streak",
                                                      speed_col="speed_streak", x_col="x_meas", y_col="y_meas")
    true_exp = float(meta.get("exposure_s", np.nan))
    out["exposure"] = {"true_s": true_exp, "ok": bool(est is not None and est.ok),
                       "estimate_s": t_exp, "ci_s": [est.ci_low, est.ci_high] if est is not None and est.ok else None,
                       "rel_error": (t_exp / true_exp - 1) if t_exp is not None and true_exp > 0 else None,
                       "reason": None if est is None else est.reason}
    if pipe.counter is not None and truth.get("gate") is not None and scored:
        t_ready = float(ready["t"].iloc[0])
        out["gate"] = gate_metrics(pipe.counter, truth["gate"], parts, t0=t_ready, cfg=cfg,
                                   frame_range=(scored[0], scored[-1]))
    return out


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


def snr50(bins: dict[str, list[int]]) -> float | None:
    """SNR at 50% completeness, interpolated linearly between bin centres (None if never reached)."""
    xs, ys = [], []
    for key, (h, n) in bins.items():
        lo, hi = (float(t) for t in key.split("-"))
        if n < 20:
            continue
        xs.append((lo + hi) / 2 if np.isfinite(hi) else lo * 1.25)
        ys.append(h / n)
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
    "exposure_rel_err": "exposure.rel_error",
    "cpc_gross_rel_err": "gate.cpc_gross.rel_err",
    "cpc_gross_in_ci": "gate.cpc_gross.in_ci",
    "pnf_rel_err": "gate.pnf.rel_err",
}


def summarize(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per case: the median over seeds of each metric (and the count of clips)."""
    by: dict[str, list[dict]] = {}
    for r in results:
        by.setdefault(r.get("case", "?"), []).append(r)
    out = {}
    for case, rs in by.items():
        row: dict[str, Any] = {"clips": len(rs), "errors": sum(1 for r in rs if "error" in r)}
        for name, path in SUMMARY_KEYS.items():
            vals = [_get(r, path) for r in rs]
            vals = [float(v) for v in vals if v is not None and np.isfinite(float(v))]
            row[name] = float(np.median(vals)) if vals else None
        pooled: dict[str, list[int]] = {}
        for r in rs:
            for k, (h, n) in (r.get("completeness") or {}).items():
                acc = pooled.setdefault(k, [0, 0])
                acc[0] += h
                acc[1] += n
        row["completeness"] = {k: round(h / n, 3) if n else None for k, (h, n) in pooled.items()}
        row["snr50"] = snr50(pooled) if pooled else None
        out[case] = row
    return out
