"""Generate synthetic ember clips with exact ground truth, and suites of them.

One clip (`generate_clip`):
1. Frame timing (degrade.make_timing): start times (PTS), exposures, duplicates, exposure
   steps and global flicker.
2. Air flow (flows.from_config), static background and haze (scene, degrade).
3. SNR model. The configured ember brightness is a point-source SNR: the integrated
   (luma) flux F of a static Gaussian spot of PSF sigma s divided by the noise of the
   optimal PSF-matched aperture,
       SNR = F / (sigma_n 2 sqrt(pi) s),
   where sigma_n is the BT.601 luma noise (DN, linear, before gamma) of the base case,
   the median over the frame of the per-pixel luma noise of the hazed background at the
   reference exposure and gain (degrade.Camera.luma_noise_sigma: per-channel variance
   B_c gain^2 / electrons_per_dn + read_noise^2, channels correlated by
   channel_noise_corr). So an ember with SNR q and PSF sigma s gets
   F = q sigma_n 2 sqrt(pi) s (output DN px^2 at the reference exposure). With the base
   camera (night background near 3 DN, electrons_per_dn 4, read noise 0.4 DN, channel
   correlation 0.5) sigma_n is about 0.8 linear DN, which is about 4 DN after gamma.
   Motion blur spreads the same flux over a streak, so moving embers have a lower
   matched-filter SNR (truth.matched_filter_area), which the truth's visible flag uses;
   flicker, fades, exposure steps and haze change the per-frame flux, which the truth
   records. Gamma encoding keeps the SNR of faint embers to first order because signal and
   noise scale by the same local slope. (The rendered spot is the Gaussian integrated over
   each pixel, of variance s^2 + 1/12, so its true matched-filter SNR is a little lower
   than the nominal one: by 9 percent at s = 0.6 px, 4 percent at s = 1 px.)
4. Particles (particles.simulate) with a warm-up before t = 0, scene distractors.
5. Per frame: render the exposure (render.render_exposure), add the background and flame,
   apply the camera (degrade.Camera), encode (H.264 via PyAV, PTS = exposure start), and
   collect the per-particle truth.
6. Write video.mp4, truth_particles.parquet, truth_frames.parquet, truth_gate.parquet,
   truth_field.parquet and meta.json (schemas in truth.py).

Determinism: the same config and seed give identical truth tables and identical 8-bit
frames before compression (meta.json frames_sha256). The libx264 bitstream is not
guaranteed bit for bit. A fixed encoder thread count removes the dependence on the
machine's core count, but the libx264 in the PyAV 19.0.1 wheel varies by itself: with
preset medium, even one encoder thread fed identical YUV frames, the first encode in a
process (or one after a decode) can differ from later ones. In ten-encode trials the
variation did not appear with psy-rd, trellis or mb-tree off, with ref 1, or with presets
veryfast and ultrafast, so it lies inside libx264, below this package. The decoded frames
then differ by coding noise only.

`run(config_paths, out_dir, seed)` merges YAML files over configs/synth/base.yaml (the
`flow` and `gates` sections are replaced as a whole, everything else is merged).
`run_suite(suite_path, out_root, workers)` generates a suite: a base case and
one-factor-at-a-time variants, each for several seeds (see configs/suites/core.yaml).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import multiprocessing as mp
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np
import pandas as pd
import yaml

from wfglink import PROJECT_ROOT
from wfglink.config import deep_merge
from wfglink.provenance import rel, run_record, sha256_json
from wfglink.synth import flows as flows_mod
from wfglink.synth import particles as particles_mod
from wfglink.synth import truth as truth_mod
from wfglink.synth.degrade import (LUMA_BGR, Camera, FrameTiming, VideoWriter, apply_haze, depth_map, make_timing,
                                   transmission)
from wfglink.synth.render import RenderSettings, render_exposure
from wfglink.synth.scene import Scene, make_background

BASE_CONFIG = PROJECT_ROOT / "configs" / "synth" / "base.yaml"
REPLACE_KEYS = ("flow", "gates")
VIDEO_NAME = "video.mp4"
SCHEMA_VERSION = 1


# Config helpers ---------------------------------------------------------------------------
def merge_synth(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Deep merge, except that top-level `flow` and `gates` are replaced as a whole."""
    out = deep_merge(base, {k: v for k, v in override.items() if k not in REPLACE_KEYS})
    for k in REPLACE_KEYS:
        if k in override:
            out[k] = copy.deepcopy(override[k])
    return out


def _resolve_path(p: str | Path, extra_dirs: Sequence[Path] = ()) -> Path:
    p = Path(p)
    if p.is_absolute() or p.exists():
        return p
    for d in (PROJECT_ROOT, *extra_dirs):
        if (d / p).exists():
            return d / p
    return p


def load_synth_config(paths: Sequence[str | Path] = (), overrides: Mapping[str, Any] | None = None,
                      base: str | Path | None = BASE_CONFIG, extra_dirs: Sequence[Path] = ()) -> dict[str, Any]:
    """configs/synth/base.yaml, then each YAML file in order, then explicit overrides."""
    cfg: dict[str, Any] = {}
    if base is not None:
        with open(base, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    for p in paths:
        with open(_resolve_path(p, extra_dirs), encoding="utf-8") as f:
            cfg = merge_synth(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = merge_synth(cfg, overrides)
    return cfg


def set_dotted(cfg: dict[str, Any], key: str, value: Any) -> dict[str, Any]:
    """Set cfg["a"]["b"]["c"] = value for key "a.b.c" (creating mappings as needed)."""
    parts = key.split(".")
    d = cfg
    for p in parts[:-1]:
        if not isinstance(d.get(p), dict):
            d[p] = {}
        d = d[p]
    d[parts[-1]] = copy.deepcopy(value)
    return cfg


def resolve_gates(cfg: Mapping[str, Any], frame_size: Sequence[int]) -> list[dict[str, Any]]:
    """Gates as [{name, p1, p2}] in px; config points may be p1/p2 (px) or p1_frac/p2_frac."""
    w, h = frame_size
    out = []
    for i, g in enumerate(cfg.get("gates") or []):
        pts = []
        for k in ("p1", "p2"):
            if g.get(f"{k}_frac") is not None:
                fx, fy = g[f"{k}_frac"]
                pts.append([float(fx) * w, float(fy) * h])
            else:
                pts.append([float(v) for v in g[k]])
        name = str(g.get("name", f"gate{i}"))
        if not math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) > 0:
            # A zero-length gate has no normal and would silently record no crossings.
            raise ValueError(f"gate {name!r} has zero length (p1 == p2)")
        out.append({"name": name, "p1": pts[0], "p2": pts[1]})
    names = [g["name"] for g in out]
    if len(set(names)) != len(names):
        raise ValueError(f"gate names must be unique, got {names}")
    return out


# Clip generation --------------------------------------------------------------------------
def _lookup(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    ix = np.clip(np.rint(x), 0, w - 1).astype(np.int64)
    iy = np.clip(np.rint(y), 0, h - 1).astype(np.int64)
    return img[iy, ix]


def _jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


@dataclass
class ClipSetup:
    """Everything needed to render a clip, built deterministically from (config, seed)."""

    cfg: dict[str, Any]
    seed: int
    frame_size: tuple[int, int]
    fps: float
    duration_s: float
    timing: FrameTiming
    flow: flows_mod.Flow
    camera: Camera
    readout_s: float
    settings: RenderSettings
    background: np.ndarray              # hazed background, scene DN (gain 1)
    t_background: np.ndarray | None     # haze transmission map of the background (None: no haze)
    t_particles: np.ndarray | float     # haze transmission of embers (map or constant)
    sigma_ref: float                    # base-case luma noise, linear DN
    flux_per_snr: float                 # output DN px^2 per unit SNR per px of PSF sigma
    system: particles_mod.EmberSystem
    levels: np.ndarray
    scene: Scene
    min_snr: float

    @property
    def sources(self) -> list[particles_mod.PointSources]:
        return [self.system, *self.scene.sources()]


def prepare_clip(config: Mapping[str, Any], seed: int | None = None) -> ClipSetup:
    """Resolve the config and build timing, flow, camera, background, particles and scene."""
    cfg = copy.deepcopy(dict(config))
    seed = int(seed if seed is not None else cfg.get("seed", 0))
    cfg["seed"] = seed
    w, h = (int(v) for v in cfg.get("frame_size", [1280, 720]))
    if w <= 0 or h <= 0 or w % 2 or h % 2:
        # The 4:2:0 video encoders reject odd sizes, and only when the clip is closed.
        raise ValueError(f"frame_size must be positive and even for 4:2:0 video, got {w} x {h}")
    fps = float(cfg.get("fps", 30.0))
    duration = float(cfg.get("duration_s", 5.0))
    frame_size = (w, h)

    timing = make_timing(cfg, seed)
    flow = flows_mod.from_config(cfg.get("flow", {"type": "uniform"}), frame_size, seed)
    camera = Camera(cfg, seed)
    readout = float((cfg.get("mismatch", {}) or {}).get("rolling_shutter_s", 0.0))
    settings = RenderSettings.from_config(cfg.get("render"))

    # Background, haze and the SNR model.
    bg = make_background((cfg.get("scene", {}) or {}).get("background"), frame_size, np.random.default_rng([seed, 201]))
    hz = cfg.get("haze", {}) or {}
    beta = float(hz.get("beta_per_m", 0.0))
    t_bg: np.ndarray | None = None
    t_part: np.ndarray | float = 1.0
    if beta > 0:
        dmap = depth_map(hz.get("depth"), frame_size)
        t_bg = transmission(dmap, beta)
        bg = apply_haze(bg, t_bg, hz.get("airlight_dn", [10.0, 14.0, 20.0]))
        pd_m = hz.get("particle_depth_m")
        t_part = transmission(float(pd_m), beta) if pd_m is not None else t_bg
    gain = camera.gain
    sigma_ref = float(np.median(camera.luma_noise_sigma(bg[::4, ::4], gain, gain)))
    flux_per_snr = sigma_ref * 2.0 * math.sqrt(math.pi)
    snr_pops = [k for k, p in particles_mod.population_configs(cfg) if p.get("flux") is None]
    if snr_pops and not sigma_ref > 1e-6:
        # A noise-free camera would make every SNR-defined ember (nearly) dark, yet all of
        # them would pass the visibility floor, which scales with the same noise.
        raise ValueError(f"brightness of {', '.join(snr_pops)} is given as an SNR but the camera noise is "
                         f"{sigma_ref:.3g} DN; add camera noise or set the population's flux instead")

    # Particles and distractors. Rendering is in scene DN (gain 1), hence flux / gain.
    # Simulate until one frame interval after the end of the last exposure (plus the
    # rolling-shutter readout): jittered frame intervals can push the last frames past
    # duration_s, and particles and lights would otherwise vanish from them.
    interval = float(np.max(np.diff(timing.t_start))) if timing.n > 1 else 1.0 / fps
    t_last = float(np.max(timing.t_end)) if timing.n else 0.0
    pad = max(t_last - duration, 0.0) + interval
    system = particles_mod.simulate(cfg, flow, frame_size=frame_size, fps=fps, duration_s=duration, seed=seed,
                                    flux_per_snr=flux_per_snr / gain, t_end_pad_s=pad + readout)
    levels = particles_mod.sigma_levels((cfg.get("embers", {}) or {}).get("sigma_px", [0.6, 2.0]),
                                        int((cfg.get("particles", {}) or {}).get("sigma_levels", 4)))
    t_range = (system.t0, duration + pad + readout)
    scene = Scene(cfg, frame_size, seed, levels=levels, pid_start=len(system), t_range=t_range, background=bg)
    return ClipSetup(cfg=cfg, seed=seed, frame_size=frame_size, fps=fps, duration_s=duration, timing=timing,
                     flow=flow, camera=camera, readout_s=readout, settings=settings, background=bg,
                     t_background=t_bg, t_particles=t_part, sigma_ref=sigma_ref, flux_per_snr=flux_per_snr,
                     system=system, levels=levels, scene=scene,
                     min_snr=float((cfg.get("truth", {}) or {}).get("visible_min_snr", 3.0)))


def generate_clip(config: Mapping[str, Any], out_dir: str | Path, seed: int | None = None) -> Path:
    """Render one clip and its ground truth into out_dir. Returns out_dir as a Path."""
    t_wall = time.perf_counter()
    setup = prepare_clip(config, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # meta.json marks a finished clip (run_suite skips such folders), so a stale one must
    # not survive a rerun that fails half way through rewriting the other files.
    (out / "meta.json").unlink(missing_ok=True)
    cfg, seed, frame_size = setup.cfg, setup.seed, setup.frame_size
    w, h = frame_size
    fps, duration, timing, flow, camera = setup.fps, setup.duration_s, setup.timing, setup.flow, setup.camera
    readout, settings, bg = setup.readout_s, setup.settings, setup.background
    t_bg, t_part, sigma_ref, flux_per_snr = setup.t_background, setup.t_particles, setup.sigma_ref, setup.flux_per_snr
    system, levels, scene, sources, min_snr = setup.system, setup.levels, setup.scene, setup.sources, setup.min_snr

    gates = resolve_gates(cfg, frame_size)          # validated before any rendering
    comp = cfg.get("compression", {}) or {}
    rows: list[dict[str, np.ndarray]] = []
    canvas = np.zeros((h, w, 3), np.float32)
    prev_img: np.ndarray | None = None
    prev_rows: dict[str, np.ndarray] | None = None
    n_sub_used: list[int] = []
    t_render = 0.0
    writer = VideoWriter(out / VIDEO_NAME, frame_size, fps, codec=str(comp.get("codec", "h264")),
                         crf=int(comp.get("crf", 23)), preset=str(comp.get("preset", "medium")),
                         time_base=int(comp.get("time_base", 90000)),
                         encoder_threads=int(comp.get("threads", 4)))
    frames_hash = hashlib.sha256()
    try:
        for i in range(timing.n):
            t0 = float(timing.t_start[i])
            if timing.duplicate[i] and prev_img is not None and prev_rows is not None:
                writer.write(prev_img, t0)
                frames_hash.update(prev_img.tobytes())
                dup = {k: v.copy() for k, v in prev_rows.items()}
                dup["frame"] = np.full(dup["frame"].size, i, np.int64)
                rows.append(dup)
                continue
            tr0 = time.perf_counter()
            exp = float(timing.exposure_s[i])
            canvas.fill(0.0)
            layer, tr, n_sub = render_exposure(sources, t0, exp, frame_size, settings, readout_s=readout, out=canvas)
            n_sub_used.append(n_sub)
            if isinstance(t_part, np.ndarray):
                scene_img = bg + layer * t_part[..., None]
            else:
                scene_img = cv2.scaleAdd(layer, float(t_part), bg)
            scene.add_flame(scene_img, t0 + 0.5 * exp, t_bg if t_bg is not None else 1.0)
            img = camera.process(scene_img, timing, i)
            t_render += time.perf_counter() - tr0
            writer.write(img, t0)
            frames_hash.update(img.tobytes())

            scale = camera.scale(timing, i)
            xm, ym, tm = tr["x_mid"], tr["y_mid"], tr["t_mid"]
            tp = _lookup(t_part, xm, ym) if isinstance(t_part, np.ndarray) else np.full(xm.size, float(t_part))
            flux = tr["flux"] * tp * scale
            sig_n = camera.luma_noise_sigma(_lookup(bg, xm, ym), scale, camera.gain_eff(timing, i))
            floor = min_snr * sig_n * np.sqrt(truth_mod.matched_filter_area(tr["sigma_px"], tr["streak_length_px"]))
            inside = (xm >= 0) & (xm <= w - 1) & (ym >= 0) & (ym <= h - 1)
            ua, va = flow.velocity(xm, ym, tm)
            fr_rows = {
                "frame": np.full(xm.size, i, np.int64), "t_mid": tm, "particle_id": tr["pid"],
                "kind": tr["kind"].astype(object), "x_mid": xm, "y_mid": ym,
                "x_start": tr["x_start"], "y_start": tr["y_start"], "x_end": tr["x_end"], "y_end": tr["y_end"],
                "u": tr["u"], "v": tr["v"], "ua": ua, "va": va, "flux": flux, "sigma_px": tr["sigma_px"],
                "visible": (tr["alive_frac"] >= 0.5) & inside & (flux >= floor),
                "in_large_region": scene.in_large_region(xm, ym, tm),
                "streak_length_px": tr["streak_length_px"], "alive_mid": tr["alive_mid"],
            }
            order = np.argsort(fr_rows["particle_id"], kind="stable")
            fr_rows = {k: v[order] for k, v in fr_rows.items()}
            rows.append(fr_rows)
            prev_img, prev_rows = img, fr_rows
    finally:
        writer.close()

    # Tables.
    if rows:
        allr = {k: np.concatenate([r[k] for r in rows]) for k in rows[0]}
    else:
        allr = {**truth_mod.empty_columns(truth_mod.PARTICLES_SCHEMA), "alive_mid": np.zeros(0, bool)}
    truth_mod.write_table(allr, truth_mod.PARTICLES_SCHEMA, out / "truth_particles.parquet")
    vis_emb = allr["visible"] & (allr["kind"] == "ember")
    n_vis = np.bincount(allr["frame"][vis_emb], minlength=timing.n)[:timing.n].astype(np.int64)
    frames_cols = {"frame": np.arange(timing.n, dtype=np.int64), "t_start": timing.t_start,
                   "t_mid": timing.t_mid, "t_end": timing.t_end, "exposure_s": timing.exposure_s,
                   "duplicate": timing.duplicate, "n_visible_embers": n_vis}
    truth_mod.write_table(frames_cols, truth_mod.FRAMES_SCHEMA, out / "truth_frames.parquet")
    rows_df = pd.DataFrame({k: allr[k] for k in ("frame", "particle_id", "kind", "t_mid", "x_mid", "y_mid",
                                                  "u", "v", "ua", "va", "visible", "alive_mid")})
    frames_df = pd.DataFrame(frames_cols)
    truth_mod.write_table(truth_mod.gate_truth(rows_df, frames_df, gates), truth_mod.GATE_SCHEMA,
                          out / "truth_gate.parquet")
    grid = [int(v) for v in cfg.get("field_grid", [16, 9])]
    truth_mod.write_table(truth_mod.field_truth(rows_df, frames_df, flow, frame_size, grid),
                          truth_mod.FIELD_SCHEMA, out / "truth_field.parquet")

    info = system.info
    meta = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "fps": fps,
        "exposure_s": timing.exposure_ref_s,
        "duty": float(cfg.get("duty", 0.5)),
        "px_per_m": float(cfg.get("px_per_m", 40.0)),
        "gates": gates,
        "field_grid": grid,
        "frame_size": [w, h],
        "video": VIDEO_NAME,
        "codec": str(comp.get("codec", "h264")),
        "crf": int(comp.get("crf", 23)),
        "n_frames": timing.n,
        "duration_s": duration,
        "config_sha256": sha256_json(cfg),
        "frames_sha256": frames_hash.hexdigest(),   # 8-bit frames before compression
        "snr_model": {
            "definition": "SNR = F / (sigma_n 2 sqrt(pi) s): integrated luma flux of a static Gaussian spot of "
                          "sigma s over the noise of the PSF-matched aperture, linear DN before gamma",
            "noise_luma_dn_ref": sigma_ref,
            "background_luma_dn_median": float(np.median(bg[::4, ::4] @ LUMA_BGR)),
            "flux_per_snr_per_sigma_px": flux_per_snr,
            "visible_min_snr": min_snr,
            "visible_floor": "flux >= visible_min_snr x local luma noise x sqrt(A), A = matched-filter noise area "
                             "of the row's streak (4 pi sigma_px^2 for a static point, larger for a streak)",
        },
        "particles": {"step_s": info.get("step_s"), "warmup_s": info.get("warmup_s"),
                      "n_particles": info.get("n_particles"), "populations": info.get("populations"),
                      "sigma_levels_px": [float(v) for v in levels]},
        "render": {"n_sub_min_used": int(min(n_sub_used)) if n_sub_used else None,
                   "n_sub_max_used": int(max(n_sub_used)) if n_sub_used else None},
        "stats": {"rows": int(allr["frame"].size), "mean_visible_embers": float(n_vis.mean()) if n_vis.size else 0.0,
                  "mean_embers_in_frame": float(np.sum((allr["kind"] == "ember") & (allr["x_mid"] >= 0)
                                                       & (allr["x_mid"] <= w - 1) & (allr["y_mid"] >= 0)
                                                       & (allr["y_mid"] <= h - 1)) / max(timing.n, 1)),
                  "duplicates": int(timing.duplicate.sum())},
        "timing_s": {"total": time.perf_counter() - t_wall, "render_and_camera": t_render},
        "config": cfg,
        "provenance": run_record("wfglink.synth.generate", cfg),
    }
    (out / "meta.json").write_text(json.dumps(_jsonable(meta), indent=2) + "\n", encoding="utf-8")
    return out


def run(config_paths: Sequence[str | Path], out_dir: str | Path, seed: int | None = None) -> Path:
    """Merge the YAML files over configs/synth/base.yaml and generate one clip."""
    return generate_clip(load_synth_config(list(config_paths)), out_dir, seed)


# Suites -----------------------------------------------------------------------------------
def suite_cases(suite: Mapping[str, Any], suite_dir: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Expand a suite into cases: the base case plus one-factor-at-a-time variants.

    Suite keys: configs (base case files over base.yaml), overrides (mapping), seeds,
    factors: {name: {key: dotted.config.key, values: list or {label: value}}
    or {configs: {label: [files]}}}; a variant's files are merged over the base case's
    files, then the overrides. Variants identical to the base case are not repeated;
    they are returned as aliases {variant name: "base"}.
    """
    extra = (suite_dir,) if suite_dir is not None else ()
    base_paths = list(suite.get("configs") or [])
    overrides = suite.get("overrides") or {}
    base_cfg = load_synth_config(base_paths, overrides, extra_dirs=extra)
    cases = [{"case": "base", "factor": None, "label": None, "config": base_cfg}]
    seen = {_canonical_hash(base_cfg): "base"}
    aliases: dict[str, str] = {}
    for fname, spec in (suite.get("factors") or {}).items():
        if "configs" in spec:
            items = list(spec["configs"].items())
        else:
            vals = spec["values"]
            items = list(vals.items()) if isinstance(vals, Mapping) else [(str(v), v) for v in vals]
        for label, value in items:
            if "configs" in spec:
                # The variant's files go over the base case's files, so only this factor changes.
                files = value if isinstance(value, (list, tuple)) else [value]
                cfg = load_synth_config(base_paths + list(files), overrides, extra_dirs=extra)
            else:
                cfg = set_dotted(copy.deepcopy(base_cfg), spec["key"], value)
            name = f"{fname}-{label}"
            h = _canonical_hash(cfg)
            if h in seen:
                aliases[name] = seen[h]
                continue
            seen[h] = name
            cases.append({"case": name, "factor": fname, "label": str(label), "config": cfg})
    return cases, aliases


def _canonical_hash(cfg: Mapping[str, Any]) -> str:
    """Config hash that treats 10 and 10.0 as equal (for finding variants equal to the base)."""
    return sha256_json(json.loads(json.dumps(cfg, default=str), parse_int=float))


def _suite_job(args: tuple[dict[str, Any], str, int]) -> str:
    cfg, out_dir, seed = args
    return str(generate_clip(cfg, out_dir, seed))


def _is_done(out_dir: Path, cfg: Mapping[str, Any], seed: int) -> bool:
    meta = out_dir / "meta.json"
    if not meta.exists():
        return False
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    c = copy.deepcopy(dict(cfg))
    c["seed"] = seed
    return m.get("config_sha256") == sha256_json(c) and (out_dir / "truth_field.parquet").exists()


def run_suite(suite_path: str | Path, out_root: str | Path, workers: int = 1, overwrite: bool = False) -> list[Path]:
    """Generate every clip of a suite under out_root/<case>/seed_<k>. Returns the clip dirs.

    Clips whose meta.json already matches the config and seed are kept unless overwrite.
    A manifest.json in out_root lists every clip with its case, factor, value and seed.
    """
    suite_path = _resolve_path(suite_path)
    with open(suite_path, encoding="utf-8") as f:
        suite = yaml.safe_load(f) or {}
    cases, aliases = suite_cases(suite, suite_path.parent)
    seeds = [int(s) for s in suite.get("seeds", [0])]
    root = Path(out_root)
    root.mkdir(parents=True, exist_ok=True)
    jobs, entries = [], []
    for c in cases:
        for s in seeds:
            d = root / c["case"] / f"seed_{s}"
            cfg_s = copy.deepcopy(c["config"])
            cfg_s["seed"] = s
            entries.append({"case": c["case"], "factor": c["factor"], "label": c["label"], "seed": s,
                            "path": str(d.relative_to(root)), "config_sha256": sha256_json(cfg_s)})
            if overwrite or not _is_done(d, c["config"], s):
                jobs.append((c["config"], str(d), s))
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn")) as ex:
            list(ex.map(_suite_job, jobs))
    else:
        for j in jobs:
            _suite_job(j)
    manifest = {"suite": suite.get("name", suite_path.stem), "suite_path": rel(suite_path), "seeds": seeds,
                "clips": entries, "aliases": aliases}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return [root / e["path"] for e in entries]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a synthetic ember clip or suite.")
    ap.add_argument("configs", nargs="*", help="YAML files merged over configs/synth/base.yaml")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--suite", default=None, help="suite YAML instead of single-clip configs")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)
    if args.suite:
        for p in run_suite(args.suite, args.out, workers=args.workers):
            print(p)
    else:
        print(run(args.configs, args.out, args.seed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
