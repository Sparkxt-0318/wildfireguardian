"""File mode: process one clip at full quality and write tables, a summary and an overlay video.

Two passes, as in the validation runner:
1. Track without an exposure time and estimate T_exp from the tracks (streak length against
   track speed). Skipped when T_exp is given.
2. Track again with T_exp given to the tracker. Everything written comes from this pass.

Outputs in the output folder (plan section 6):
- detections.parquet: one row per detection (frame, t, x, y, area, peak, flux, length,
  width, theta, saturated fraction, color score, flags).
- frames.parquet: one row per decoded frame (frame, t, duplicate, ready, detections, active
  tracks, count rate, Cumulative Particle Count gross and net, Particle Number Flux, ms).
- track_points.parquet: one row per track point, with per-point track and streak velocities.
- tracks.parquet: one row per track (times, points, track, streak and fused speeds,
  direction, straight-line residual, static flag, gate crossings).
- field.parquet: the ember velocity field per cell, for the whole clip and for windows of
  field.window_s (u, v in px/s, tracks, display status, bootstrap interval).
- summary.json: input hash and metadata, config hash, git commit, versions, units and
  calibration state, totals with intervals, exposure estimate, warnings.
- overlay.mp4: H.264 drawn by the same renderer as the booth screen (optional).
CSV instead of Parquet with outputs.table_format: csv.
"""
from __future__ import annotations

import json
import platform
import time
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
        import av
        from PySide6.QtGui import QGuiApplication

        from wfglink.ui.fonts import load_fonts

        QGuiApplication.instance() or QGuiApplication([])
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


def process_clip(clip: str | Path, out_dir: str | Path, cfg: dict | None = None, gate: dict | None = None,
                 t_exp: float | None = None, overlay: bool | None = None, lang: str = "ko",
                 overlay_size: tuple[int, int] = (1920, 1080), max_seconds: float | None = None,
                 m_per_px: float | None = None, distance_m: float | None = None,
                 start_s: float = 0.0, roi: tuple[float, float, float, float] | None = None) -> dict[str, Any]:
    from wfglink.sitting.recordings import probe_video

    cfg = cfg or load_config()
    clip = Path(clip)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ocfg = cfg.get("outputs", {})
    fmt = ocfg.get("table_format", "parquet")
    overlay = bool(ocfg.get("overlay_video", True)) if overlay is None else overlay
    meta = probe_video(clip)
    fps = meta.get("fps") or None
    crop = None
    if roi is not None:   # x0, y0, x1, y1 in fractions of the frame (or pixels when any value exceeds 1)
        W, H = int(meta["width"]), int(meta["height"])
        r = [float(v) for v in roi]
        if max(r) <= 1.0:
            r = [r[0] * W, r[1] * H, r[2] * W, r[3] * H]
        crop = (int(round(r[0])), int(round(r[1])), int(round(r[2])), int(round(r[3])))
        meta = {**meta, "width": crop[2] - crop[0], "height": crop[3] - crop[1], "roi_px": list(crop)}
    warnings: list[str] = []
    t0 = time.perf_counter()

    def run(t_hint, writer=None, rows=None):
        pipe = Pipeline(cfg, gate=gate, fps=fps, record=True, t_exp_hint=t_hint, m_per_px=m_per_px,
                        distance_m=distance_m)
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
                st = pipe.process(f)
                if rows is not None:
                    rows.append({"frame": int(f.index), "t": float(f.t), "duplicate": pipe.stats.frames_duplicate > dup0,
                                 "ready": bool(pipe.detector.ready), "detections": int(len(st.detections)),
                                 "active_tracks": int(len(st.trails)), "count_rate": st.count_rate,
                                 "cpc_gross": st.cpc_gross, "cpc_net": st.cpc_net, "pnf": st.pnf,
                                 "ms": round((time.perf_counter() - ta) * 1000, 2)})
                if writer is not None:
                    st.source_state, st.source_label = "file", clip.name
                    writer.write(st)
        finally:
            src.close()
        pipe.finish()
        return pipe

    exp_info: dict[str, Any] = {"source": "given" if t_exp else "estimated"}
    t_exp_sd = 0.0
    if not t_exp:
        p1 = run(None)
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
    writer = None
    if overlay:
        writer = OverlayWriter(out / "overlay.mp4", overlay_size, fps or 30.0, int(ocfg.get("overlay_crf", 20)), lang)
    try:
        pipe = run(t_exp, writer, rows)
    finally:
        if writer is not None:
            writer.close()

    import pandas as pd

    tabs = pipe.tables()
    points = tabs["tracks"]
    if len(points):
        points = add_point_velocities(points, cfg, t_exp=t_exp)
    files = {"detections": _write_table(tabs["detections"], out / "detections.parquet", fmt),
             "frames": _write_table(pd.DataFrame(rows), out / "frames.parquet", fmt),
             "track_points": _write_table(points, out / "track_points.parquet", fmt)}
    tracks = _track_table(points, pipe.counter, cfg, t_exp, t_exp_sd) if len(points) else pd.DataFrame()
    files["tracks"] = _write_table(tracks, out / "tracks.parquet", fmt)
    if len(points) and meta.get("width"):
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

    import av
    import cv2
    import scipy

    summary = {
        "schema_version": 1,
        "created": now_shanghai(),
        "input": {"path": str(clip), "sha256": sha256_file(clip), "segment_s": [start_s, max_seconds], **meta},
        "config_sha256": sha256_json(cfg),
        **git_state(),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                     "opencv": cv2.__version__, "av": av.__version__, "pandas": pd.__version__},
        "units": {"position": "px", "speed": "px/s" if m_per_px is None else "px/s (m/s = px/s x m_per_px)",
                  "calibrated": m_per_px is not None, "m_per_px": m_per_px, "distance_m": distance_m},
        "exposure": exp_info,
        "totals": totals,
        "warnings": warnings,
        "outputs": {k: v.name for k, v in files.items()} | ({"overlay": "overlay.mp4"} if overlay else {}),
        "seconds": round(time.perf_counter() - t0, 1),
        "labels": {"pnf": "Particle Number Flux (projected, 2D): crossings per unit gate length in the picture; "
                          "analogous to, not comparable with, NIST PNF (per square meter)",
                   "cpc": "Cumulative Particle Count (gate): tracks crossing the gate line; a lower bound, "
                          "only glowing, visible embers count"},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return summary
