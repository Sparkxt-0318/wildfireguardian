"""File mode: process one clip at full quality and write tables, a summary and an overlay video.

Two passes, as in the validation runner:
1. Track without an exposure time and estimate T_exp from the tracks (streak length against
   track speed). Skipped when T_exp is given.
2. Track again with T_exp given to the tracker. Everything written comes from this pass.

Outputs in the output folder (plan section 6):
- detections.parquet: one row per detection (frame, t, x, y, area, peak, flux, length,
  width, theta, saturated fraction, color score, flags, scale). Positions and sizes are in
  pixels of the analysed region at its native resolution; on large frames some detections
  come from a downscaled copy (detect/multiscale.py), and scale is that copy's factor
  (1 = native).
- frames.parquet: one row per decoded frame (frame, t, duplicate, ready, detections, active
  tracks, count rate, Cumulative Particle Count gross and net, Particle Number Flux, ms).
- track_points.parquet: one row per track point, with per-point track and streak velocities.
- tracks.parquet: one row per track (times, points, track, streak and fused speeds,
  direction, straight-line residual, static flag, gate crossings).
- field.parquet: the ember velocity field per cell, for the whole clip and for windows of
  field.window_s (u, v in px/s, tracks, display status, bootstrap interval).
- summary.json: input hash and metadata (with a ROI, input.width and height are the
  crop's, input.roi_px the crop and input.source_size the full frame), config hash, git
  commit, versions, units and calibration state, totals with intervals, exposure
  estimate, the analysis scales (analysis: the levels' factors and sizes and the detections
  each measured), warnings. `python -m wfglink plausibility` adds its statuses later.
- overlay.mp4: H.264 drawn by the same renderer as the booth screen (optional).
CSV instead of Parquet with outputs.table_format: csv.
"""
from __future__ import annotations

import json
import platform
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.config import load_config
from wfglink.io.frames import Frame
from wfglink.io.sources import FileSource
from wfglink.measure.velocity import add_point_velocities, summarize_track_speed
from wfglink.pipeline import Pipeline
from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
from wfglink.validate.suite import exposure_from_tracks


def _write_table(df, path: Path, fmt: str) -> Path:
    if fmt == "csv":
        path = path.with_suffix(".csv")
        df.to_csv(path, index=False)
    else:
        df.to_parquet(path, index=False)
    return path


class OverlayWriter:
    """Encode rendered LiveStates to H.264 with PyAV (QImage only, no QPixmap)."""

    def __init__(self, path: Path, size: tuple[int, int], fps: float, crf: int, lang: str):
        import os

        import av
        from PySide6.QtGui import QGuiApplication

        from wfglink.ui.fonts import load_fonts

        if QGuiApplication.instance() is None:
            # The overlay is drawn on a QImage and never shown, so file mode needs no display
            # (without this a headless machine aborts after the first pass).
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            QGuiApplication([])
        load_fonts()
        self.w, self.h = size
        self.lang = lang
        self.c = av.open(str(path), "w")
        rate = max(1, int(round(fps)))
        self.s = self.c.add_stream("libx264", rate=rate)
        self.s.width, self.s.height, self.s.pix_fmt = self.w, self.h, "yuv420p"
        self.s.options = {"crf": str(crf), "preset": "veryfast"}
        self.n = 0

    def write(self, state) -> None:
        import av

        from wfglink.render.scene import render_image

        img = render_image(self.w, self.h, state, self.lang)
        ptr = img.constBits()
        arr = np.frombuffer(ptr, np.uint8, count=img.sizeInBytes()).reshape(self.h, img.bytesPerLine())
        rgb = arr[:, : self.w * 3].reshape(self.h, self.w, 3)
        frame = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format="rgb24")
        for pkt in self.s.encode(frame):
            self.c.mux(pkt)
        self.n += 1

    def close(self) -> None:
        for pkt in self.s.encode():
            self.c.mux(pkt)
        self.c.close()


def roi_crop(roi, width: int, height: int) -> tuple[int, int, int, int] | None:
    """ROI x0, y0, x1, y1 in pixels of a width x height frame, from fractions of the frame (or
    pixels when any value exceeds 1); None without a ROI. Shared with the label tiles so that
    tile coordinates are those of detections.parquet."""
    if roi is None:
        return None
    r = [float(v) for v in roi]
    if max(r) <= 1.0:
        r = [r[0] * width, r[1] * height, r[2] * width, r[3] * height]
    return int(round(r[0])), int(round(r[1])), int(round(r[2])), int(round(r[3]))


def _track_table(points, counter, cfg: dict, t_exp: float | None, t_exp_sd: float):
    import pandas as pd

    crossings: dict[int, list] = {}
    if counter is not None:
        for e in counter.events:
            crossings.setdefault(int(e.track_id), []).append(int(e.direction))
    rows = []
    for tid, g in points.groupby("track_id"):
        g = g.sort_values("t")
        ss = summarize_track_speed(g["t"].to_numpy(), g["x_meas"].to_numpy(), g["y_meas"].to_numpy(),
                                   g["length"].to_numpy(), g["theta"].to_numpy(), g["flags"].to_numpy(), cfg,
                                   t_exp=t_exp, t_exp_sd=t_exp_sd)
        cr = crossings.get(int(tid), [])
        rows.append({"track_id": int(tid), "t_start": float(g["t"].iloc[0]), "t_end": float(g["t"].iloc[-1]),
                     "frame_start": int(g["frame"].iloc[0]), "frame_end": int(g["frame"].iloc[-1]),
                     "points": int(ss.n_points), "static": bool(g["static"].iloc[0]) if "static" in g else False,
                     "u_px_s": ss.u, "v_px_s": ss.v, "track_speed_px_s": ss.track_speed,
                     "track_speed_sd": ss.track_speed_sd, "streak_speed_px_s": ss.streak_speed,
                     "streak_points": ss.n_streak, "fused_speed_px_s": ss.fused_speed,
                     "best_speed_px_s": ss.best_speed, "best_source": ss.best_source,
                     "direction_deg": ss.direction_deg, "rms_resid_px": ss.rms_resid_px,
                     "crossings_pos": sum(1 for d in cr if d > 0), "crossings_neg": sum(1 for d in cr if d < 0),
                     "mean_color": float(np.nanmean(g["color"])) if np.isfinite(g["color"]).any() else np.nan})
    return pd.DataFrame(rows)


def _stat(v) -> dict[str, Any]:
    v = np.asarray(v, np.float64)
    v = v[np.isfinite(v)]
    return {"median": float(np.median(v)) if v.size else None, "p95": float(np.percentile(v, 95)) if v.size else None,
            "n": int(v.size)}


def _write_high_precision(out: Path, pipe, cfg: dict, summary: dict, *, points, rows, det_table, t_exp, t_exp_sd,
                          m_per_px, distance_m, overlay: bool) -> dict[str, Any]:
    """High-precision mode (wfglink/verify): write <out>/high_precision/ (the observer's tables as
    Parquet, hp_summary.json and the frame-level pseudo-run frame_level/, whose detections are the
    points drawn as accepted, so `label-score` scores them unchanged) and return the short block
    for summary.json. The legacy files are not touched.

    The track set of hp_tracks, hp_points, the delays and accepted_tracks is the tracks ever
    accepted (accepted now, or accepted and then revoked as static): they were drawn and
    counted while accepted, so the crossings in hp_tracks add up to the totals and every point
    of frame_level/ is in hp_points (accepted_at marks the points drawn while accepted)."""
    import pandas as pd

    from wfglink.measure.gate import garwood_interval
    from wfglink.verify.config import OVERLAY

    obs = pipe.observer
    hp_dir = out / "high_precision"
    hp_dir.mkdir(parents=True, exist_ok=True)
    tabs = obs.tables()
    dec = tabs["hp_decisions"]
    acc = dec[(dec["state"] == "method_accepted") | dec["revoked"].astype(bool)] if len(dec) else dec
    acc0 = acc[acc["epoch"] == 0] if len(acc) else acc
    acc_ids = set(acc0["track_id"].astype(int)) if len(acc0) else set()
    pts = points[points["track_id"].isin(acc_ids)] if len(points) and acc_ids else points.iloc[0:0]
    if len(pts):
        tt = _track_table(pts, obs.counter, cfg, t_exp, t_exp_sd)
        tabs["hp_tracks"] = tt.merge(tabs["hp_tracks"].drop(columns=["crossings_pos", "crossings_neg"]), on="track_id",
                                     how="left")
        # Drawn while accepted: from the acceptance on, and before the revocation of a revoked track.
        a = acc0.set_index("track_id")
        tid, tp = pts["track_id"], pts["t"].to_numpy()
        t_acc, t_dec = tid.map(a["t_accept"]).to_numpy(float), tid.map(a["t_decision"]).to_numpy(float)
        rev = tid.map(a["revoked"]).to_numpy(bool)
        tabs["hp_points"] = pts.assign(accepted_at=(tp >= t_acc - 1e-9) & (~rev | (tp < t_dec - 1e-9)))
    else:
        tabs["hp_points"] = pts.assign(accepted_at=pd.Series(dtype=bool))
    names = {}
    for name, df in tabs.items():
        df.to_parquet(hp_dir / f"{name}.parquet", index=False)
        names[name] = f"{name}.parquet"
    dump = obs.dump_arrays()
    if dump is not None:
        np.savez(hp_dir / "hp_patches.npz", **dump)
        names["hp_patches"] = "hp_patches.npz"

    # Totals from the high-precision counter, over the same span and with the same intervals as the
    # legacy totals; the bootstrap only when crossings were fed all the time.
    fr = pd.DataFrame(rows)
    ready = fr[fr["ready"] & ~fr["duplicate"]] if len(fr) else fr
    st = dict(obs.stats)
    scorer = obs.scorer
    available = bool(getattr(scorer, "available", True))
    totals: dict[str, Any] | None = None
    if obs.counting and obs.counter is not None and len(ready) > 1:
        c = obs.counter
        ta, tb = float(ready["t"].iloc[0]), float(ready["t"].iloc[-1])
        dur = tb - ta
        withheld = _withheld_in(tabs["hp_frames"], ta, tb)
        sup = max(dur - withheld, 0.0)
        cpc = c.cumulative_particle_count()
        if withheld <= 0:
            rg = c.rate_interval(ta, tb, net=False, cfg=cfg)
            rate_ci, how = [rg["lo"], rg["hi"]], "garwood and moving-block bootstrap (union)"
        else:
            lo, hi = garwood_interval(cpc["gross"])
            rate_ci = [lo / sup, hi / sup] if sup > 0 else [None, None]
            how = "garwood (time with camera motion excluded)"
        flux = c.particle_number_flux(sup, m_per_px=m_per_px, z_m=distance_m)
        totals = {"duration_s": round(dur, 3), "supported_s": round(sup, 3), "withheld_s": round(withheld, 3),
                  "cpc_gross": cpc["gross"],
                  "cpc_gross_ci": [cpc["gross_lo"], cpc["gross_hi"]], "cpc_net": cpc["net"],
                  "cpc_net_ci": [cpc["net_lo"], cpc["net_hi"]],
                  "count_rate_per_s": cpc["gross"] / sup if sup > 0 else None, "count_rate_ci": rate_ci,
                  "count_rate_ci_method": how,
                  "pnf": {"value": flux.value, "lo": flux.lo, "hi": flux.hi, "unit": flux.unit, "label": flux.label}}
    # The timebase comes first: on a clip that is not real time no method could decide.
    if obs.tracking_only:
        status, reason = "not_real_time", "metrics_scope tracking_only: the timebase is not real time"
    elif not available:
        status, reason = "unavailable", str(getattr(scorer, "reason", ""))
    elif st["withheld_s"] > 0 or st["over_budget_frames"] > 0 or st["dump_truncated"]:
        status, reason = "partial", "; ".join(r for r, on in (
            ("decisions withheld while the camera moved", st["withheld_s"] > 0),
            ("detections over the feature budget", st["over_budget_frames"] > 0),
            ("the feature dump was cut at its row limit", st["dump_truncated"])) if on)
    else:
        status, reason = "ok", ""
    accd = acc if len(acc) else None
    delays = {"confirm_to_decision_s": _stat([] if accd is None else accd["t_accept"] - accd["t_confirm"]),
              "first_to_decision_s": _stat([] if accd is None else accd["t_accept"] - accd["t_first"]),
              "tracks": "ever accepted (revoked ones included), from their acceptance time"}
    ms = obs.observer_ms()
    identity = {**scorer.identity(), "overlay": OVERLAY.name,
                "overlay_sha256": sha256_file(OVERLAY) if OVERLAY.exists() else None,
                "verify_sha256": sha256_json(cfg.get("verify")), "config_sha256": sha256_json(cfg)}

    # The frame-level pseudo-run: the legacy input block, and only the points drawn as accepted.
    fl = hp_dir / "frame_level"
    fl.mkdir(parents=True, exist_ok=True)
    shown = obs.shown_detections()
    det = det_table
    if len(det) and shown:
        j = det.groupby("frame").cumcount().to_numpy()
        key = pd.MultiIndex.from_arrays([det["frame"].to_numpy(np.int64), j])
        det = det[key.isin(pd.MultiIndex.from_tuples(shown))]
    else:
        det = det.iloc[0:0]
    det.to_parquet(fl / "detections.parquet", index=False)
    n_by = det.groupby("frame").size() if len(det) else pd.Series(dtype=np.int64)
    ffl = fr[["frame", "t", "duplicate", "ready"]].copy() if len(fr) else pd.DataFrame(
        columns=["frame", "t", "duplicate", "ready"])
    ffl["detections"] = ffl["frame"].map(n_by).fillna(0).astype(np.int64) if len(ffl) else pd.Series(dtype=np.int64)
    ffl.to_parquet(fl / "frames.parquet", index=False)
    fl_summary = {"schema_version": 1, "created": now_shanghai(), "input": summary["input"],
                  "config_sha256": sha256_json(cfg), **git_state(), "metrics_scope": summary.get("metrics_scope"),
                  "pseudo_run": {"of": "high_precision", "method": obs.method, "profile": obs.profile,
                                 "detections": "the measured points of tracks accepted at or before their frame"},
                  "outputs": {"detections": "detections.parquet", "frames": "frames.parquet"}}
    (fl / "summary.json").write_text(json.dumps(fl_summary, indent=2, ensure_ascii=False, default=str),
                                     encoding="utf-8")

    hp_summary = {
        "schema_version": 1, "created": now_shanghai(), "mode": obs.vcfg.mode, "method": obs.method,
        "profile": obs.profile, "status": status, "status_reason": reason,
        "scorer_status": "available" if available else str(getattr(scorer, "reason", "")),
        "observer_error": obs.failed,
        "scorer": identity, "decisions": obs.decision_counts(), "delays": delays, "totals": totals,
        "time": {"supported_s": round(float(st["supported_s"]), 3),
                 "motion_unsupported_s": round(float(st["motion_unsupported_s"]), 3),
                 "withheld_s": round(float(st["withheld_s"]), 3)},
        "frames": int(st["frames"]), "over_budget_frames": int(st["over_budget_frames"]),
        "dump": {k: st[k] for k in ("dump_rows", "dump_patches", "dump_windows", "dump_truncated")}
        if obs.vcfg.dump else None,
        "observer_ms": {"median": float(np.median(ms)) if ms.size else None,
                        "p95": float(np.percentile(ms, 95)) if ms.size else None},
        "raw_reference": summary.get("totals"),
        "outputs": {**names, "frame_level": "frame_level/"} | ({"overlay": "overlay.mp4"} if overlay else {}),
        "labels": {"accepted": "accepted by this method, not proven to be an ember"},
    }
    (hp_dir / "hp_summary.json").write_text(json.dumps(hp_summary, indent=2, ensure_ascii=False, default=str),
                                            encoding="utf-8")
    return {"method": obs.method, "profile": obs.profile, "status": status, "folder": "high_precision/",
            "accepted_tracks": int(len(acc)), "revoked_tracks": int(acc["revoked"].astype(bool).sum()) if len(acc) else 0,
            "cpc_gross": None if totals is None else totals["cpc_gross"]}


def _withheld_in(frames, ta: float, tb: float) -> float:
    """Seconds of [ta, tb] in which crossings were withheld (camera motion), from hp_frames: each
    withheld frame stands for the interval since the previous analysed frame."""
    if not len(frames):
        return 0.0
    t = frames["t"].to_numpy(float)
    t0 = np.concatenate([[t[0]], t[:-1]])
    lo, hi = np.maximum(t0, ta), np.minimum(t, tb)
    w = frames["withheld"].to_numpy(bool)
    return float(np.sum(np.clip(hi - lo, 0.0, None)[w]))


def _legacy_cfg(cfg: dict) -> dict:
    """The config without the opt-in verify section: what the legacy outputs depend on (and hash)."""
    return {k: v for k, v in cfg.items() if k != "verify"} if "verify" in cfg else cfg


def process_clip(clip: str | Path, out_dir: str | Path, cfg: dict | None = None, gate: dict | None = None,
                 t_exp: float | None = None, overlay: bool | None = None, lang: str = "ko",
                 overlay_size: tuple[int, int] = (1920, 1080), max_seconds: float | None = None,
                 m_per_px: float | None = None, distance_m: float | None = None,
                 start_s: float = 0.0, roi: tuple[float, float, float, float] | None = None,
                 metrics_scope: str = "all") -> dict[str, Any]:
    from wfglink.io.probe import probe_video

    cfg = cfg or load_config()
    tracking_only = metrics_scope == "tracking_only"
    clip = Path(clip)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ocfg = cfg.get("outputs", {})
    fmt = ocfg.get("table_format", "parquet")
    overlay = bool(ocfg.get("overlay_video", True)) if overlay is None else overlay
    if tracking_only:
        # A rerun into an earlier all-metrics folder must not leave those exports behind.
        for name in ("detections", "frames", "track_points", "tracks"):
            (out / f"{name}.{'parquet' if fmt == 'csv' else 'csv'}").unlink(missing_ok=True)
        for name in ("field.parquet", "field.csv", "overlay.mp4", "plausibility.json"):
            (out / name).unlink(missing_ok=True)
    meta = probe_video(clip)
    fps = meta.get("fps") or None
    crop = None
    if roi is not None:   # x0, y0, x1, y1 in fractions of the frame (or pixels when any value exceeds 1)
        W, H = int(meta["width"]), int(meta["height"])
        crop = roi_crop(roi, W, H)
        meta = {**meta, "width": crop[2] - crop[0], "height": crop[3] - crop[1], "roi_px": list(crop),
                "source_size": [W, H]}
    warnings: list[str] = []
    t0 = time.perf_counter()

    def run(t_hint, writer=None, rows=None, run_cfg=None, hp_writer=None):
        pipe = Pipeline(run_cfg or cfg, gate=gate, fps=fps, record=True, t_exp_hint=t_hint, m_per_px=m_per_px,
                        distance_m=distance_m)
        if pipe.observer is not None:
            pipe.observer.set_metrics_scope(metrics_scope)
        src = FileSource(clip, start_s=start_s)
        src.open()
        try:
            while (f := src.read()) is not None:
                if max_seconds is not None and f.t > max_seconds - start_s:   # max_seconds is clip time; f.t counts from start_s
                    break
                if crop is not None:
                    f = Frame(np.ascontiguousarray(f.image[crop[1]:crop[3], crop[0]:crop[2]]), f.t, f.index, f.t_wall, f.meta)
                dup0 = pipe.stats.frames_duplicate
                ta = time.perf_counter()
                st = hp_st = pipe.process(f)
                if pipe.observer is not None and pipe.observer.legacy_state is not None:
                    # High-precision mode: the legacy tables and overlay come from the legacy state.
                    st = pipe.observer.legacy_state
                    st.image = hp_st.image
                if rows is not None:
                    rows.append({"frame": int(f.index), "t": float(f.t), "duplicate": pipe.stats.frames_duplicate > dup0,
                                 "ready": bool(pipe.detector.ready), "detections": int(len(st.detections)),
                                 "active_tracks": int(len(st.trails)), "count_rate": st.count_rate,
                                 "cpc_gross": st.cpc_gross, "cpc_net": st.cpc_net, "pnf": st.pnf,
                                 "ms": round((time.perf_counter() - ta) * 1000, 2)})
                if writer is not None:
                    st.source_state, st.source_label = "file", clip.name
                    if tracking_only:
                        # Keep association geometry, but never present clip-time motion or
                        # crossings as measurements of a slow-motion recording.
                        st = replace(st, metrics_scope=metrics_scope, count_rate=None, cpc_gross=None,
                                     cpc_net=None, pnf=None, speed=None, direction_deg=None,
                                     field_uvn=None, gate=None, sparkline=np.zeros(0),
                                     calibrated=False, distance_m=None)
                    writer.write(st)
                if hp_writer is not None:
                    hp_st.source_state, hp_st.source_label = "file", clip.name
                    if tracking_only:
                        hp_st = replace(hp_st, metrics_scope=metrics_scope, count_rate=None, cpc_gross=None,
                                        cpc_net=None, pnf=None, speed=None, direction_deg=None, field_uvn=None,
                                        gate=None, sparkline=np.zeros(0), calibrated=False, distance_m=None)
                    hp_writer.write(hp_st)
        finally:
            src.close()
        pipe.finish()
        return pipe

    exp_info: dict[str, Any] = {"source": "given" if t_exp else "estimated"}
    t_exp_sd = 0.0
    if tracking_only:
        t_exp = None
        exp_info = {"status": "not reported: tracking_only; the timebase is not real time"}
    elif not t_exp:
        p1 = run(None, run_cfg=_legacy_cfg(cfg))   # the exposure pass needs no verifier
        tr = p1.tables()["tracks"]
        tr = tr[~tr["static"].astype(bool)] if len(tr) else tr
        est = exposure_from_tracks(tr, cfg, fps or 30.0)
        if est is not None and est.ok:
            t_exp, t_exp_sd = est.t_exp, est.sd
            exp_info.update(t_exp_s=est.t_exp, ci_s=[est.ci_low, est.ci_high], duty=est.duty,
                            tracks=est.n_tracks, points=est.n_points)
            if fps and est.t_exp > 1.05 / fps:
                warnings.append("exposure estimate longer than one frame interval: check the clip's timing")
        else:
            exp_info["status"] = f"not estimated: {est.reason if est is not None else 'no tracks'}"
            warnings.append("exposure time not estimated; streak speeds are not reported")
    else:
        exp_info["t_exp_s"] = t_exp

    rows: list[dict] = []
    writer = hp_writer = None
    high_precision = "verify" in cfg
    if overlay:
        writer = OverlayWriter(out / "overlay.mp4", overlay_size, fps or 30.0, int(ocfg.get("overlay_crf", 20)), lang)
        if high_precision:
            (out / "high_precision").mkdir(parents=True, exist_ok=True)
            hp_writer = OverlayWriter(out / "high_precision" / "overlay.mp4", overlay_size, fps or 30.0,
                                      int(ocfg.get("overlay_crf", 20)), lang)
    try:
        pipe = run(t_exp, writer, rows, hp_writer=hp_writer)
    finally:
        if writer is not None:
            writer.close()
        if hp_writer is not None:
            hp_writer.close()

    import pandas as pd

    tabs = pipe.tables()
    points = tabs["tracks"]
    if len(points) and not tracking_only:
        points = add_point_velocities(points, cfg, t_exp=t_exp)
    tracks = _track_table(points, pipe.counter, cfg, t_exp, t_exp_sd) if len(points) else pd.DataFrame()
    det_export, frame_export, point_export, track_export = tabs["detections"], pd.DataFrame(rows), points, tracks
    if tracking_only:
        det_export = det_export.drop(columns=["flux"], errors="ignore")
        frame_export = frame_export.drop(columns=["count_rate", "cpc_gross", "cpc_net", "pnf"], errors="ignore")
        point_export = point_export.drop(columns=["vx", "vy", "flux"], errors="ignore")
        track_export = track_export.drop(columns=["u_px_s", "v_px_s", "track_speed_px_s", "track_speed_sd",
                                                   "streak_speed_px_s", "fused_speed_px_s", "best_speed_px_s",
                                                   "best_source", "direction_deg", "crossings_pos", "crossings_neg"],
                                         errors="ignore")
    files = {"detections": _write_table(det_export, out / "detections.parquet", fmt),
             "frames": _write_table(frame_export, out / "frames.parquet", fmt),
             "track_points": _write_table(point_export, out / "track_points.parquet", fmt),
             "tracks": _write_table(track_export, out / "tracks.parquet", fmt)}
    if len(points) and meta.get("width") and not tracking_only:
        from wfglink.measure.field import estimate_field

        size = (int(meta["width"]), int(meta["height"]))
        win = float(cfg.get("field", {}).get("window_s", 10.0))
        t_lo, t_hi = float(points["t"].min()), float(points["t"].max())
        parts = [estimate_field(points, size, cfg).assign(window="all", t0=t_lo, t1=t_hi)]
        k = 0
        while t_hi - t_lo > win and t_lo + k * win < t_hi:
            a = t_lo + k * win
            parts.append(estimate_field(points, size, cfg, window=(a, a + win)).assign(window=f"w{k}", t0=a, t1=a + win))
            k += 1
        files["field"] = _write_table(pd.concat(parts, ignore_index=True), out / "field.parquet", fmt)

    # Totals over the analysed span (from the first frame with a ready background model).
    fr = pd.DataFrame(rows)
    ready = fr[fr["ready"] & ~fr["duplicate"]] if len(fr) else fr
    totals: dict[str, Any] = {"frames": int(len(fr)), "frames_duplicate": int(fr["duplicate"].sum()) if len(fr) else 0,
                              "tracks": int(len(tracks)),
                              "tracks_moving": int((~tracks["static"]).sum()) if len(tracks) else 0}
    if pipe.counter is not None and len(ready) > 1:
        ta, tb = float(ready["t"].iloc[0]), float(ready["t"].iloc[-1])
        dur = tb - ta
        cpc = pipe.counter.cumulative_particle_count()
        rg = pipe.counter.rate_interval(ta, tb, net=False, cfg=cfg)
        flux = pipe.counter.particle_number_flux(dur, m_per_px=m_per_px, z_m=distance_m)
        totals.update(duration_s=round(dur, 3), cpc_gross=cpc["gross"], cpc_gross_ci=[cpc["gross_lo"], cpc["gross_hi"]],
                      cpc_net=cpc["net"], cpc_net_ci=[cpc["net_lo"], cpc["net_hi"]],
                      count_rate_per_s=cpc["gross"] / dur if dur > 0 else None,
                      count_rate_ci=[rg["lo"], rg["hi"]],
                      pnf={"value": flux.value, "lo": flux.lo, "hi": flux.hi, "unit": flux.unit, "label": flux.label},
                      gate={"p1": list(pipe.counter.gate.p1), "p2": list(pipe.counter.gate.p2),
                            "length_px": pipe.counter.gate.length, "name": pipe.counter.gate.name})
    moving = tracks[~tracks["static"]] if len(tracks) else tracks
    if len(moving):
        sp = moving["best_speed_px_s"].to_numpy(dtype=float)
        sp = sp[np.isfinite(sp)]
        if sp.size:
            totals["speed_px_s"] = {"median": float(np.median(sp)), "p10": float(np.percentile(sp, 10)),
                                    "p90": float(np.percentile(sp, 90)), "tracks": int(sp.size)}
        ang = np.radians(moving["direction_deg"].to_numpy(dtype=float))
        ang = ang[np.isfinite(ang)]
        if ang.size:
            totals["direction_deg_circular_mean"] = float(np.degrees(np.arctan2(np.sin(ang).mean(), np.cos(ang).mean())))
    if totals.get("frames_duplicate"):
        warnings.append(f"{totals['frames_duplicate']} repeated frames skipped (constant-frame-rate re-encode?)")
    if len(fr) > 2:
        dt = np.diff(fr["t"].to_numpy())
        if dt.size and np.nanmax(dt) > 1.5 * np.nanmedian(dt):
            warnings.append("frame intervals vary (variable frame rate or dropped frames); true timestamps are used")

    # Analysis scales (detect/multiscale.py): the levels the detector used and how many of the
    # recorded detections each one measured.
    det_tab = tabs["detections"]
    shape = (int(meta.get("height") or 0), int(meta.get("width") or 0))   # the analysed region
    factors = [1, *(f for f, _ in pipe.detector.levels)]
    ms_cfg = cfg.get("detect", {}).get("multiscale", {}) or {}
    analysis = {"factors": factors, "sizes_px": [[int(shape[1]) // f, int(shape[0]) // f] for f in factors],
                "multiscale_enabled": bool(ms_cfg.get("enabled", False)),
                "min_frame_pixels": ms_cfg.get("min_frame_pixels"),
                "detections_by_scale": ({str(int(k)): int(v) for k, v in det_tab["scale"].value_counts().sort_index().items()}
                                        if len(det_tab) and "scale" in det_tab else {})}

    if tracking_only:
        # The clip's timebase is not real time (slow motion): speeds, rates, counts per second and
        # flux would be wrong by the slow-down factor, so only tracking quantities are reported.
        dropped = [k for k in ("speed_px_s", "count_rate_per_s", "count_rate_ci", "pnf", "cpc_gross", "cpc_gross_ci",
                               "cpc_net", "cpc_net_ci", "duration_s", "direction_deg_circular_mean", "gate") if k in totals]
        for k in dropped:
            totals.pop(k)
        totals["not_reported"] = {"quantities": dropped, "reason": "metrics_scope tracking_only: the timebase is not real time"}
        warnings.append("tracking only: speeds, counts and flux are not reported for this clip (its timebase is not real time)")

    import av
    import cv2
    import scipy

    summary = {
        "schema_version": 1,
        "created": now_shanghai(),
        "input": {"path": str(clip), "sha256": sha256_file(clip), "segment_s": [start_s, max_seconds], **meta},
        "config_sha256": sha256_json(_legacy_cfg(cfg)),
        **git_state(),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                     "opencv": cv2.__version__, "av": av.__version__, "pandas": pd.__version__},
        "units": {"position": "px", "time": "clip seconds (not real time)"} if tracking_only else
                 {"position": "px", "speed": "px/s" if m_per_px is None else "px/s (m/s = px/s x m_per_px)",
                  "calibrated": m_per_px is not None, "m_per_px": m_per_px, "distance_m": distance_m},
        "exposure": exp_info,
        "analysis": analysis,
        "metrics_scope": metrics_scope,
        "totals": totals,
        "warnings": warnings,
        "outputs": {k: v.name for k, v in files.items()} | ({"overlay": "overlay.mp4"} if overlay else {}),
        "seconds": round(time.perf_counter() - t0, 1),
        "labels": {"scope": "Slow-motion tracking only: positions and track identities; no speed, count or flux measurements"}
                  if tracking_only else
                  {"pnf": "Particle Number Flux (projected, 2D): crossings per unit gate length in the picture; "
                          "analogous to, not comparable with, NIST PNF (per square meter)",
                   "cpc": "Cumulative Particle Count (gate): tracks crossing the gate line; a lower bound, "
                          "only glowing, visible embers count"},
    }
    if pipe.observer is not None:
        summary["high_precision"] = _write_high_precision(
            out, pipe, cfg, summary, points=points, rows=rows, det_table=det_export, t_exp=t_exp, t_exp_sd=t_exp_sd,
            m_per_px=m_per_px, distance_m=distance_m, overlay=hp_writer is not None)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return summary
