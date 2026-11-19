"""Virtual 60 GHz radar paths through the FDS hot-gas field, and synthetic frames for crossing.radar_flame.

SIMULATED. FDS has no solid targets, so the echoes are invented: a virtual corner reflector placed beyond the
flame and ground clutter at every range bin on the centreline. Only the propagation PHASE through the gas is taken
from FDS. Assumptions (stated in REPORT.md):

Propagation
- Straight two-way path radar -> target -> radar (ray bending ignored; at these refractivity contrasts the bending
  is micro-radians).
- Excess phase phi = (4 pi / lambda) * integral of [(n - 1)(T) - (n - 1)(T_amb)] ds along the one-way path, with the
  dry-air refractivity (n - 1) = 77.6e-6 * P / T (P in hPa, T in K, P = 1013.25 hPa; FDS pressure perturbations are
  < 0.1 hPa and ignored). The ambient value is subtracted so that the no-fire scene has phi = 0 (a static offset
  does not matter to a detector that only looks at frame-to-frame changes).
- Optional wet term (sensitivity only): + 0.373 * e / T^2 with e = x_H2O * P (hPa), x_H2O = 0.21 * xi, xi the same
  temperature proxy as lwir (0.21 = stoichiometric H2O mole fraction of the C064 fuel C2.1H6.2O2.16 burnt in air).
  Ambient humidity is not modelled (it adds a static term only).
- lambda = c / f_centre of the config's sweep (`Scene.lambda_m`): default config 60.00-60.55 GHz -> 4.97 mm; the
  short config 60.0-63.6 GHz -> 4.85 mm (also the no-config default). Soot loss uses 4.85 mm (LAMBDA_M).
- FDS output is every ~1 s, so frame-to-frame differences here are over ~1 s, not the radar's 0.1 s; the turbulent
  structure below the 1 m cell size is absent from FDS. Both make the real flicker spectrum different (UNVERIFIED).
- Amplitude: no loss through the flame is applied (loss_db = 0). Soot absorption at 60 GHz is computed by
  `soot_loss_db_per_m` (Rayleigh, negligible); flame-plasma loss is NOT in FDS and is given only as an
  order-of-magnitude table by `plasma_loss_db_per_m` (Drude model, electron density and collision frequency are
  assumptions). See REPORT.md.

Echo scene (placeholders)
- Radar on the roof head at height 2.5 m facing -x, boresight beam only (all virtual antennas in phase).
- Ground clutter on the centreline at every range bin r > h: per-antenna SNR = G0 - 30 log10(r / 10 m), G0 = 25 dB,
  static random phase per bin (seeded).
- Corner reflector at height 1.0 m, SNR = 45 dB - 40 log10(r / 10 m).
- Complex Gaussian receiver noise of unit power per antenna, 4 virtual antennas, independent per antenna.
- Range bins: the MAIN case reads bin count, bin spacing, IF-limited maximum range and centre frequency from the
  unit's default CLI config `hardware/vehicle-unit/config/iwr6843aop_vu.cfg` (`Scene.from_cfg`, via
  wfgvu.drivers.radar_iwr6843.load_profile: 128 bins x 0.468 m, echoes only to 54.0 m, 60.00-60.55 GHz). Bins
  beyond the IF-limited range carry noise only. Side cases (labelled): `iwr6843aop_vu_short.cfg` (512 x 0.049 m,
  22.5 m), `iwr6843aop_vu_long_fine.cfg` (512 x 0.117 m, 54 m) and the earlier VIRTUAL 60 m range at 0.0488 m.
  `Scene()` without a config keeps the earlier defaults (0.0488 m, 61.8 GHz) for the synthetic tests.
- Ground clutter per bin scales with the bin length (distributed scatterers): `clutter_g0_db` is given for
  `CLUTTER_REF_RES_M` = 0.0488 m bins and `Scene.from_cfg` adds 10 log10(range_res / 0.0488) (+9.8 dB at 0.468 m)
  unless `scale_clutter=False`. The corner reflector and the receiver noise per bin are taken as unchanged between
  configs (the default config's 64 chirp loops are taken to recover the 6 dB its 4x shorter ADC window loses;
  UNVERIFIED, placeholder).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from crossing import _repo
from crossing import radar_flame as rf

from .fields import Field, Sampler

C_LIGHT = 2.99792458e8
F_CENTRE_HZ = 61.8e9
LAMBDA_M = C_LIGHT / F_CENTRE_HZ
P_HPA = 1013.25
N_DRY = 77.6e-6
RANGE_RES_M = 0.0488
COMMITTED_MAX_RANGE_M = 22.5
VIRTUAL_MAX_RANGE_M = 60.0
X_H2O_STOICH = 0.21
T_PROXY_REF_K = 1200.0
CLUTTER_REF_RES_M = 0.0488          # clutter_g0_db is per bin of this length
CFG_DIR = _repo.VU_ROOT / "config"
DEFAULT_CFG = CFG_DIR / "iwr6843aop_vu.cfg"
SHORT_CFG = CFG_DIR / "iwr6843aop_vu_short.cfg"
LONG_FINE_CFG = CFG_DIR / "iwr6843aop_vu_long_fine.cfg"


def cfg_geometry(path=DEFAULT_CFG) -> dict:
    """Bin count, bin spacing (m), IF-limited maximum range (m), sweep and centre frequency of a demo CLI config, as
    the unit's driver derives them (wfgvu.drivers.radar_iwr6843.load_profile). Raises if the config cannot be read
    (no silent fallback to the old defaults)."""
    _repo.vu()
    from wfgvu.drivers.radar_iwr6843 import load_profile
    from .fields import sha256
    p = load_profile(path)
    f_c = 0.5 * (p.start_ghz + p.sweep_end_ghz) * 1e9
    return {"cfg": str(path.relative_to(_repo.REPO)) if str(path).startswith(str(_repo.REPO)) else str(path),
            "sha256": sha256(path), "n_bins": int(p.n_bins), "range_res_m": float(p.range_res_m),
            "max_range_m": float(p.max_range_m), "fft_extent_m": float(p.n_bins * p.range_res_m),
            "start_ghz": float(p.start_ghz), "sweep_end_ghz": float(p.sweep_end_ghz), "f_centre_hz": f_c,
            "lambda_m": C_LIGHT / f_c, "frame_rate_hz": float(p.frame_rate_hz), "n_virt": int(p.n_virt)}


def refractivity(temp_k, t_amb_k: float, wet: bool = False) -> np.ndarray:
    """(n - 1) - (n - 1)_ambient for temperature temp_k (K)."""
    t = np.asarray(temp_k, dtype=float)
    out = N_DRY * P_HPA / t - N_DRY * P_HPA / t_amb_k
    if wet:
        xi = np.clip((t - t_amb_k) / (T_PROXY_REF_K - t_amb_k), 0.0, 1.0)
        e = X_H2O_STOICH * xi * P_HPA
        out = out + 0.373 * e / t ** 2
    return out


@dataclass
class Scene:
    """Radar at (x_r, 0, h_r) facing -x; reflector at (x_ref, 0, z_ref) or None."""
    x_r: float
    h_r: float = 2.5
    x_ref: Optional[float] = None
    z_ref: float = 1.0
    max_range_m: float = VIRTUAL_MAX_RANGE_M
    range_res_m: float = RANGE_RES_M
    clutter_g0_db: float = 25.0
    reflector_db_at_10m: float = 45.0
    ground_clutter: bool = True
    n_ant: int = 4
    n_bins_cfg: Optional[int] = None          # from a CLI config: fixed bin count; echoes only up to max_range_m
    lambda_m: float = LAMBDA_M
    label: str = "virtual (no config)"

    @classmethod
    def from_cfg(cls, geom: dict, scale_clutter: bool = True, label: Optional[str] = None, **kw) -> "Scene":
        """Scene with the bins of a CLI config (`cfg_geometry`): n_bins, spacing, IF-limited max range, lambda.
        Ground clutter per bin is scaled by the bin length relative to CLUTTER_REF_RES_M unless scale_clutter=False."""
        g0 = kw.pop("clutter_g0_db", 25.0)
        if scale_clutter:
            g0 = g0 + 10.0 * math.log10(geom["range_res_m"] / CLUTTER_REF_RES_M)
        return cls(max_range_m=geom["max_range_m"], range_res_m=geom["range_res_m"], n_bins_cfg=geom["n_bins"],
                   lambda_m=geom["lambda_m"], clutter_g0_db=g0, label=label or geom["cfg"], **kw)

    @property
    def n_bins(self) -> int:
        if self.n_bins_cfg is not None:
            return int(self.n_bins_cfg)
        return int(math.floor(self.max_range_m / self.range_res_m)) + 1

    @property
    def ranges(self) -> np.ndarray:
        return np.arange(self.n_bins) * self.range_res_m

    @property
    def reflector_range(self) -> Optional[float]:
        if self.x_ref is None:
            return None
        return float(math.hypot(self.x_r - self.x_ref, self.h_r - self.z_ref))

    @property
    def reflector_bin(self) -> Optional[int]:
        r = self.reflector_range
        if r is None:
            return None
        b = int(round(r / self.range_res_m))
        return b if (b < self.n_bins and r <= self.max_range_m) else None

    def snr_db(self) -> np.ndarray:
        """Per-antenna echo SNR per bin (dB); -inf where there is no echo."""
        r = self.ranges
        out = np.full(r.size, -np.inf)
        if self.ground_clutter:
            g = (r > self.h_r) & (r <= self.max_range_m)
            out[g] = self.clutter_g0_db - 30.0 * np.log10(r[g] / 10.0)
        return out


def excess_phase(f: Field, scene: Scene, wet: bool = False, n_samples: int = 240) -> dict:
    """Two-way excess phase (rad) per ground-clutter bin and for the reflector, from field f."""
    samp = Sampler(f, f.temp_k, outside=[f.t_ambient_k])
    r = scene.ranges
    o = np.array([scene.x_r, 0.0, scene.h_r])
    phase = np.zeros(r.size)
    g = r > scene.h_r
    if g.any():
        horiz = np.sqrt(r[g] ** 2 - scene.h_r ** 2)
        tgt = np.stack([scene.x_r - horiz, np.zeros(horiz.size), np.zeros(horiz.size)], axis=1)
        u = (np.arange(n_samples) + 0.5) / n_samples
        pts = o[None, None, :] + (tgt - o)[:, None, :] * u[None, :, None]
        T = samp.sample(pts[..., 0].ravel(), pts[..., 1].ravel(), pts[..., 2].ravel())[0].reshape(pts.shape[:2])
        dn = refractivity(T, f.t_ambient_k, wet)
        phase[g] = 4.0 * math.pi / scene.lambda_m * dn.mean(axis=1) * r[g]
    ref = None
    if scene.x_ref is not None:
        tgt = np.array([scene.x_ref, 0.0, scene.z_ref])
        n = max(n_samples, int(np.linalg.norm(tgt - o) / 0.05))
        u = (np.arange(n) + 0.5) / n
        pts = o[None, :] + (tgt - o)[None, :] * u[:, None]
        T = samp.sample(pts[:, 0], pts[:, 1], pts[:, 2])[0]
        dn = refractivity(T, f.t_ambient_k, wet)
        ref = float(4.0 * math.pi / scene.lambda_m * dn.mean() * np.linalg.norm(tgt - o))
    return {"bins": phase, "reflector": ref}


def synth_frames(t: Sequence[float], phases: Sequence[Optional[dict]], scene: Scene, seed: int = 0,
                 noise_offset: int = 1000) -> List[rf.RadarFrame]:
    """SYNTHETIC complex heatmap frames [bins, n_ant] (boresight: all antennas in phase) from per-frame excess
    phases (None = no fire, phi = 0). The static clutter / reflector phases depend only on `seed`, so a baseline and
    fire frames made with the same seed see the same scene; receiver noise is drawn from seed + noise_offset + i."""
    rs = np.random.default_rng(seed)
    nb = scene.n_bins
    theta = rs.uniform(-np.pi, np.pi, nb)
    th_ref = rs.uniform(-np.pi, np.pi)
    snr = scene.snr_db()
    amp = np.where(np.isfinite(snr), 10.0 ** (snr / 20.0), 0.0)
    rb = scene.reflector_bin
    a_ref = 0.0
    if rb is not None:
        a_ref = 10.0 ** ((scene.reflector_db_at_10m - 40.0 * math.log10(max(scene.reflector_range, 0.5) / 10.0)) / 20.0)
    out = []
    for i, (ti, ph) in enumerate(zip(t, phases)):
        nr = np.random.default_rng(seed + noise_offset + i)
        pb = np.zeros(nb) if ph is None else np.asarray(ph["bins"])[:nb]
        echo = amp * np.exp(1j * (theta + pb))
        if rb is not None:
            pr = 0.0 if ph is None or ph.get("reflector") is None else ph["reflector"]
            echo[rb] += a_ref * np.exp(1j * (th_ref + pr))
        noise = (nr.standard_normal((nb, scene.n_ant)) + 1j * nr.standard_normal((nb, scene.n_ant))) / math.sqrt(2.0)
        out.append(rf.RadarFrame(t=float(ti), range_res_m=scene.range_res_m,
                                 iq=(echo[:, None] + noise).astype(np.complex64), sim=True))
    return out


def detector_config(n_frames: int, dt: float = 1.0) -> rf.RadarFlameConfig:
    """Detector settings for ~1 s frames (FDS output interval): window covers the sequence, consecutive pairs
    up to 1.5 s apart count, staleness 2 s. Thresholds are the module defaults (k = 4)."""
    return rf.RadarFlameConfig(window_s=(n_frames - 1) * dt + 0.5, max_pair_dt_s=1.5 * dt, stale_s=2.0 * dt,
                               min_frames=5)


def baseline_frames(scene: Scene, n: int = 30, dt: float = 1.0, seed: int = 0) -> List[rf.RadarFrame]:
    """n no-fire (phi = 0) synthetic frames with the scene's static clutter phases for `seed`."""
    t = -dt * np.arange(n, 0, -1) - 100.0
    return synth_frames(t, [None] * n, scene, seed=seed, noise_offset=1000)


def baseline(scene: Scene, n: int = 30, dt: float = 1.0, seed: int = 0) -> rf.RadarBaseline:
    """No-fire baseline captured by crossing.radar_flame.RadarBaseline.capture from `baseline_frames`."""
    return rf.RadarBaseline.capture(baseline_frames(scene, n, dt, seed), bearings_deg=(0.0,), max_pair_dt_s=1.5 * dt,
                                    meta={"sim": True, "note": "virtual_fds synthetic baseline, phi = 0"})


def _circ_std(dp, axis=0):
    r = np.abs(np.mean(np.exp(1j * np.asarray(dp)), axis=axis))
    return np.sqrt(-2.0 * np.log(np.clip(r, 1e-12, 1.0)))


def oracle_flicker_z(frames: Sequence[rf.RadarFrame], base: Sequence[rf.RadarFrame], scene: Scene,
                     se_factor: float = 0.75, min_snr_db: float = 15.0, floor_rad: float = 0.005) -> np.ndarray:
    """LOCAL ADAPTER (not crossing code): the detector's phase-flicker z-score per bin, but with the TRUE beam SNR
    of the synthetic scene in place of crossing.radar_flame.noise_floor_db. That estimator takes the 25th
    percentile of per-bin medians as the noise floor, which distributed ground clutter in every bin biases high, so
    the detector stops scoring clutter bins beyond ~15 m. Same formula otherwise: z = ln(s_window / sigma_b) /
    sqrt(se/m_w + se/m_b), sigma_b = max(baseline frame-to-frame phase std, 1/sqrt(rho), floor). NaN where the true
    beam SNR is below min_snr_db."""
    def beam_phase(frs):
        return np.angle(np.stack([np.asarray(f.iq).mean(axis=1) for f in frs]))
    pw = beam_phase(frames); pb = beam_phase(base)
    dw = np.angle(np.exp(1j * np.diff(pw, axis=0))); db = np.angle(np.exp(1j * np.diff(pb, axis=0)))
    s_w = _circ_std(dw); s_b = _circ_std(db)
    snr = scene.snr_db()
    amp2 = np.where(np.isfinite(snr), 10.0 ** (snr / 10.0), 0.0)
    rb = scene.reflector_bin
    if rb is not None:
        amp2[rb] += 10.0 ** ((scene.reflector_db_at_10m - 40.0 * math.log10(max(scene.reflector_range, 0.5) / 10.0)) / 10.0)
    rho = amp2 * scene.n_ant                     # beam = mean over antennas: noise power 1/n_ant
    sig = np.maximum(np.maximum(s_b, 1.0 / np.sqrt(np.maximum(rho, 1e-12))), floor_rad)
    rel = math.sqrt(se_factor / dw.shape[0] + se_factor / db.shape[0])
    z = np.log(np.maximum(s_w, 1e-12) / sig) / rel
    return np.where(10.0 * np.log10(np.maximum(rho, 1e-12)) >= min_snr_db, z, np.nan)


@dataclass
class RadarRun:
    state: rf.RadarState
    flicker_phase_rad_true: np.ndarray        # circular std of frame-to-frame excess-phase differences (noise-free)
    oracle_z: np.ndarray                      # oracle_flicker_z (true-SNR adapter)
    reflector_phase_series: Optional[List[float]] = None
    near_edge_slant_m: Optional[float] = None
    scene: Optional[Scene] = None


def run_detector(t: Sequence[float], phases: Sequence[dict], scene: Scene, near_edge_slant_m: Optional[float],
                 seed: int = 0) -> RadarRun:
    """Baseline + window of fire frames through crossing.radar_flame.RadarFlameDetector; returns the final state,
    the noise-free flicker per bin and the oracle z-scores."""
    base = baseline_frames(scene, seed=seed)
    bl = rf.RadarBaseline.capture(base, bearings_deg=(0.0,), max_pair_dt_s=1.5,
                                  meta={"sim": True, "note": "virtual_fds synthetic baseline, phi = 0"})
    frames = synth_frames(t, phases, scene, seed=seed, noise_offset=5000)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    det = rf.RadarFlameDetector(bl, cfg=detector_config(len(t), dt))
    st = None
    for fr in frames:
        st = det.update(fr, fr.t, near_edge_m=near_edge_slant_m, bearing_deg=0.0, moving=False)
    P = np.array([np.asarray(p["bins"])[:scene.n_bins] for p in phases])
    true_flick = _circ_std(np.angle(np.exp(1j * np.diff(P, axis=0)))) if P.shape[0] >= 2 else np.zeros(scene.n_bins)
    return RadarRun(state=st, flicker_phase_rad_true=true_flick, oracle_z=oracle_flicker_z(frames, base, scene),
                    reflector_phase_series=[p.get("reflector") for p in phases],
                    near_edge_slant_m=near_edge_slant_m, scene=scene)


def soot_loss_db_per_m(fv: float, c_soot: float = 7.0, lambda_m: float = LAMBDA_M) -> float:
    """One-way soot absorption at mm-wave (Rayleigh: kappa = C f_v / lambda), dB/m. C = 6 pi E(m) ~ 7 assumed
    (E(m) of soot at 60 GHz is not known here; the order of magnitude is the point)."""
    return 10.0 * math.log10(math.e) * c_soot * fv / lambda_m


def plasma_loss_db_per_m(n_e_m3: float, nu_s: float, f_hz: float = F_CENTRE_HZ) -> float:
    """One-way attenuation of a weakly ionised collisional plasma (Drude, n ~ 1): alpha = w_p^2 nu / (2 c (w^2 + nu^2))
    Np/m, w_p^2 = n_e e^2 / (eps0 m_e). Returns dB/m. Inputs are assumptions; FDS has no ionisation."""
    e = 1.602176634e-19; eps0 = 8.8541878128e-12; me = 9.1093837015e-31
    wp2 = n_e_m3 * e * e / (eps0 * me)
    w = 2.0 * math.pi * f_hz
    alpha = wp2 * nu_s / (2.0 * C_LIGHT * (w * w + nu_s * nu_s))
    return 20.0 * math.log10(math.e) * alpha
