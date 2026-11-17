"""Step 3: radar effect of a flame on echoes behind it, fused (AND) with the thermal camera (DESIGN.md section 6.3).

Radar: TI IWR6843AOP EVM, stock out-of-box demo (60-64 GHz, wavelength ~4.9 mm). Per frame the laptop gets the
static azimuth heatmap (TLV 4: complex [range bins, virtual azimuth antennas]) and/or the log-magnitude range profile
(TLV 2, dB). See `wfgvu.protocol` for the wire format; `frame_from_reading` decodes lazily.

What the radar is used for, and the physics assumed (NOT verified on hardware; all tests here are synthetic):
- A vegetation flame is weakly attenuating at 60 GHz (order of 1-3 dB through a flame zone, reported values vary;
  soot and hot-gas absorption are small at mm-wave). The more robust signature expected is SCINTILLATION: turbulent
  hot gas has fluctuating refractive index, so echoes from static objects BEHIND the flame (road furniture, trees,
  a far bank, a vehicle) show frame-to-frame phase jitter (path-length changes of a fraction of 4.9 mm are enough)
  and some amplitude flicker. Smoke particles are far smaller than the wavelength: smoke alone has no measurable
  radar effect (the assumption behind the smoke-only test). Water mist gives a small loss and amplitude flicker.
- Everything is relative to a BASELINE of the same static scene captured with no flame, from the same vehicle
  position. Vehicle motion changes every echo phase (a 2.5 mm move is half a wavelength): the detector reports
  UNKNOWN while `moving=True`, and the baseline must be recaptured after the vehicle moves (pipeline's job).
- The window MAX amplitude per bin is used for the "is there an echo behind the flame" question: intermittent gaps
  in a flame give clear looks, so the strongest echo over the window is the best evidence of a far reflector.
  Consequence: with gaps, the window max hides attenuation; the phase flicker statistic carries detection then.
- A radar effect on its own is never a flame (mist, exhaust plumes, rain on the radome, multipath from a passing
  vehicle can all produce it). FLAME needs the radar effect AND flame-temperature pixels at the same bearing.
- Noise floor (heatmap): from frame-to-frame complex DIFFERENCES of the no-flame baseline (static echoes cancel), so
  ground clutter in every bin does not bias it; anything that moves an echo only raises it (conservative). The level
  estimate (25th percentile of per-bin medians) is kept for the range profile, which has no phase.
- Effects are only attributed to the flame if they are absent on CONTROL echoes in front of the flame (vibration,
  interference and radome water affect those too) and have held for >= min_effect_s (a window that is mostly
  pre-flame frames is not accepted). Every such doubt gives UNKNOWN, never FLAME_EFFECT.
- The first SOLID echo beyond the flame is a persistent, point-like, static echo >= 12 dB above its local clutter
  (`first_solid_echo`), never just the first clutter bin past the near edge.

Range of bin b is b * range_res_m (TI demo convention). Amplitudes are in the dB units of their source (arbitrary
reference); only differences against the baseline of the SAME source are meaningful.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

DEFAULT_BEARINGS = tuple(float(b) for b in range(-30, 31, 5))
_TINY = 1e-12


# --- frames ---------------------------------------------------------------------------------------------------
@dataclass
class RadarFrame:
    """One decoded radar frame. t: laptop monotonic s; iq: complex [bins, ant] or None; range_profile_db: [bins]
    or None; range_res_m: m per bin."""
    t: float
    range_res_m: float
    iq: Optional[np.ndarray] = None
    range_profile_db: Optional[np.ndarray] = None
    frame_ok: bool = True
    sim: bool = False

    @property
    def n_bins(self) -> int:
        if self.iq is not None:
            return int(self.iq.shape[0])
        if self.range_profile_db is not None:
            return int(len(self.range_profile_db))
        return 0

    @property
    def usable(self) -> bool:
        return bool(self.frame_ok) and (self.iq is not None or self.range_profile_db is not None)


def frame_from_reading(data: dict, t: float, sim: bool = False) -> RadarFrame:
    """Build a RadarFrame from a protocol `radar` reading's `data`. The heatmap is decoded with
    wfgvu.protocol.decode_iq (sensor-head code, imported lazily)."""
    iq = None
    if data.get("az_heatmap"):
        from crossing import _repo
        _repo.vu()
        from wfgvu.protocol import decode_iq
        iq = np.asarray(decode_iq(data["az_heatmap"]), dtype=np.complex64)
    rp = data.get("range_profile_db")
    rp = None if rp is None else np.asarray(rp, dtype=float)
    return RadarFrame(t=float(t), range_res_m=float(data["range_res_m"]), iq=iq, range_profile_db=rp,
                      frame_ok=bool(data.get("frame_ok", True)), sim=sim)


# --- beamforming ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ArrayGeometry:
    """Azimuth positions of the virtual antennas in wavelengths. Default: uniform linear 4 elements at lambda/2
    (the AOP azimuth row as exported by the demo heatmap; the true AOP virtual array is 2-D and its column order in
    TLV 4 must be checked on the device). `sign` flips the steering direction if the export order is reversed."""
    positions_lambda: tuple = (0.0, 0.5, 1.0, 1.5)
    sign: float = 1.0

    def steering(self, bearing_deg: float, n_ant: Optional[int] = None) -> np.ndarray:
        p = np.asarray(self.positions_lambda, dtype=float)
        if n_ant is not None and n_ant != p.size:
            p = 0.5 * np.arange(n_ant)                      # fall back to uniform lambda/2 for that count
        return np.exp(1j * 2.0 * math.pi * self.sign * p * math.sin(math.radians(bearing_deg)))


DEFAULT_ARRAY = ArrayGeometry()


def beam(iq, bearing_deg: float, geometry: ArrayGeometry = DEFAULT_ARRAY) -> np.ndarray:
    """Conventional (delay-and-sum) beam: y[b] = sum_n conj(a_n(theta)) x[b, n] / N. Bearing + right of boresight
    (with the default sign). Returns complex [bins]."""
    x = np.asarray(iq)
    if x.ndim != 2:
        raise ValueError("iq must be [bins, ant]")
    a = geometry.steering(bearing_deg, x.shape[1])
    return (x @ np.conj(a)) / x.shape[1]


def _db(y) -> np.ndarray:
    return 20.0 * np.log10(np.abs(y) + _TINY)


def amp_flicker_db(amp_db_frames, pair_ok) -> np.ndarray:
    """Amplitude flicker per bin: std of frame-to-frame differences of LINEAR amplitude over consecutive pairs,
    divided by the mean linear amplitude and expressed in dB-equivalent (x 20/ln 10 = 8.686). Computed in the
    linear domain because log-amplitude noise of an echo 15-25 dB above the floor has a long lower tail (deep fades)
    that inflates a dB-domain std and its false-alarm rate; for small flicker both agree."""
    lin = 10.0 ** (np.asarray(amp_db_frames, dtype=float) / 20.0)
    d = np.diff(lin, axis=0)[pair_ok]
    return 8.685889638 * d.std(axis=0, ddof=1) / np.maximum(lin.mean(axis=0), _TINY)


def _circ_std(phases, axis=0) -> np.ndarray:
    """Circular standard deviation sqrt(-2 ln R), radians."""
    r = np.abs(np.mean(np.exp(1j * np.asarray(phases)), axis=axis))
    return np.sqrt(-2.0 * np.log(np.clip(r, _TINY, 1.0)))


def _pair_ok(t: np.ndarray, max_dt: float) -> np.ndarray:
    return np.diff(t) <= max_dt


# --- noise ----------------------------------------------------------------------------------------------------
RAYLEIGH_MEDIAN_DB = 20.0 * math.log10(math.sqrt(math.log(2.0)))     # median |n| / rms |n| of complex noise, dB
NOISE_QUANTILE = 0.6                       # quantile over bins of the temporal residual (above the median: conservative)


def noise_floor_db(amp_db_frames) -> float:
    """LEVEL noise floor: 25th percentile over bins of the per-bin median amplitude (dB). Assumes most range bins hold
    no strong echo. Static clutter in every bin biases it HIGH (by the clutter-to-noise ratio, ~13 dB in the step 8
    virtual unit); that is the conservative direction. Still used for the range profile (no phase) and as a guard on
    the temporal estimate below."""
    A = np.asarray(amp_db_frames, dtype=float)
    return float(np.percentile(np.median(A, axis=0), 25))


def residual_power_db(t, y, max_pair_dt_s: float = 0.5) -> np.ndarray:
    """Per-bin TEMPORAL residual power, dB: 10 log10(mean |y_i - y_{i-1}|^2 / 2) over consecutive frame pairs (dt <=
    max_pair_dt_s) of a complex beam y [frames, bins]. A static echo cancels in the difference, so in a static scene
    this is the receiver noise power of the bin whatever the clutter (E|n_i - n_{i-1}|^2 = 2 sigma^2). Anything that
    moves the echo between frames (flame scintillation, vibration, wind-blown vegetation, oscillator phase noise on a
    strong echo) only ADDS to it."""
    t = np.asarray(t, dtype=float)
    Y = np.asarray(y)
    ok = _pair_ok(t, max_pair_dt_s)
    d = np.diff(Y, axis=0)[ok]
    if d.shape[0] < 1:
        raise ValueError("residual needs consecutive frame pairs")
    p = np.mean(np.abs(d) ** 2, axis=0) / 2.0
    return 10.0 * np.log10(np.maximum(p, _TINY ** 2))


def temporal_noise_db(t, y, max_pair_dt_s: float = 0.5) -> float:
    """Clutter-independent noise floor of a complex beam, in the same convention as `noise_floor_db` (median of the
    Rayleigh-distributed noise amplitude, RAYLEIGH_MEDIAN_DB below the rms): the NOISE_QUANTILE (60th percentile)
    over ALL bins of `residual_power_db`, + RAYLEIGH_MEDIAN_DB.

    Why this direction is safe: every non-noise fluctuation raises a bin's residual, so in expectation each bin's value
    is >= the true noise. On pure synthetic noise the MEDIAN over bins came out -0.02 to -0.09 dB (100-1000 bins,
    30-100 frames, 20 draws each); the 60th percentile is used so that the sampling scatter of single bins pushes the
    estimate up (about +0.1 to +0.3 dB), not down. An over-estimate hides flicker (no FLAME,
    CLOSED); an under-estimate would lower the thermal sigma floor and let ordinary noise look like flicker. Only a
    degenerate residual (frozen or coarsely quantised IQ, consecutive frames identical) can under-estimate; the
    baseline guards that with `BeamStats.from_series(max_level_gap_db=...)`."""
    return float(np.percentile(residual_power_db(t, y, max_pair_dt_s), 100.0 * NOISE_QUANTILE)) + RAYLEIGH_MEDIAN_DB


def thermal_noise_diff_std(mean_db, noise_db):
    """Theoretical floor for the frame-to-frame noise of a static echo in complex Gaussian noise.

    With noise_db in the Rayleigh-median convention (RAYLEIGH_MEDIAN_DB below the rms noise amplitude) the
    echo-to-noise power ratio is rho = 10^((mean_db - noise_db + RAYLEIGH_MEDIAN_DB)/10). At high rho the per-frame
    amplitude noise is 8.686/sqrt(2 rho) dB and the phase noise 1/sqrt(2 rho) rad; differences of two independent
    frames are sqrt(2) larger: 8.686/sqrt(rho) dB and 1/sqrt(rho) rad. Used as a lower bound on the baseline's
    empirical values so that an unluckily quiet baseline capture does not make ordinary noise look like flicker.
    Valid for the coherent heatmap beam only. Returns (amp_db, phase_rad) arrays.
    """
    rho = 10.0 ** ((np.asarray(mean_db, dtype=float) - noise_db + RAYLEIGH_MEDIAN_DB) / 10.0)
    rho = np.maximum(rho, 1e-6)
    return 8.685889638 / np.sqrt(rho), 1.0 / np.sqrt(rho)


# --- baseline -------------------------------------------------------------------------------------------------
@dataclass
class BeamStats:
    """Per-bin statistics of one source (heatmap beam at one bearing, or range profile) over no-flame frames.
    dB arrays [bins]; phase arrays in rad (None for the range profile, which has no phase). diff_amp_std_db is the
    `amp_flicker_db` statistic of the baseline frames; diff_phase_std_rad the circular std of frame-to-frame phase
    differences.

    noise_db: the noise floor used for thresholds (Rayleigh-median convention). Heatmap: `temporal_noise_db`
    (noise_method "temporal"; clutter does not bias it), but never below level_db - max_level_gap_db ("temporal+guard"
    when the guard binds). Range profile (no phase): `noise_floor_db` (noise_method "level", biased high by clutter).
    level_db: `noise_floor_db` of the same frames (reported; guard). resid_db: per-bin `residual_power_db` (heatmap
    only), the reference for the window's noise-rise test. Baselines saved before these fields existed load with
    noise_method "level" and resid_db None (their noise_db was the level estimate, the conservative one)."""
    mean_db: np.ndarray
    std_db: np.ndarray
    diff_amp_std_db: np.ndarray
    phase_std_rad: Optional[np.ndarray]
    diff_phase_std_rad: Optional[np.ndarray]
    noise_db: float
    n_frames: int
    n_pairs: int
    level_db: Optional[float] = None
    resid_db: Optional[np.ndarray] = None
    noise_method: str = "level"

    MAX_LEVEL_GAP_DB = 20.0

    @classmethod
    def from_series(cls, t, amp_db, phase=None, max_pair_dt_s: float = 0.5,
                    max_level_gap_db: float = MAX_LEVEL_GAP_DB) -> "BeamStats":
        t = np.asarray(t, dtype=float)
        A = np.asarray(amp_db, dtype=float)
        ok = _pair_ok(t, max_pair_dt_s)
        dA = np.diff(A, axis=0)[ok]
        if dA.shape[0] < 2:
            raise ValueError("baseline needs consecutive frame pairs")
        level = noise_floor_db(A)
        ph_std = dph_std = None
        resid = None
        noise = level
        method = "level"
        if phase is not None:
            P = np.asarray(phase, dtype=float)
            dP = np.angle(np.exp(1j * np.diff(P, axis=0)))[ok]
            ph_std = _circ_std(P, axis=0)
            dph_std = _circ_std(dP, axis=0)
            y = 10.0 ** (A / 20.0) * np.exp(1j * P)
            resid = residual_power_db(t, y, max_pair_dt_s)
            noise = float(np.percentile(resid, 100.0 * NOISE_QUANTILE)) + RAYLEIGH_MEDIAN_DB
            method = "temporal"
            if noise < level - max_level_gap_db:
                noise, method = level - max_level_gap_db, "temporal+guard"
        return cls(mean_db=A.mean(axis=0), std_db=A.std(axis=0, ddof=1), diff_amp_std_db=amp_flicker_db(A, ok),
                   phase_std_rad=ph_std, diff_phase_std_rad=dph_std, noise_db=float(noise),
                   n_frames=int(A.shape[0]), n_pairs=int(dA.shape[0]), level_db=float(level), resid_db=resid,
                   noise_method=method)

    def to_dict(self) -> dict:
        def arr(x):
            return None if x is None else [float(v) for v in x]
        return {"mean_db": arr(self.mean_db), "std_db": arr(self.std_db), "diff_amp_std_db": arr(self.diff_amp_std_db),
                "phase_std_rad": arr(self.phase_std_rad), "diff_phase_std_rad": arr(self.diff_phase_std_rad),
                "noise_db": float(self.noise_db), "n_frames": self.n_frames, "n_pairs": self.n_pairs,
                "level_db": None if self.level_db is None else float(self.level_db), "resid_db": arr(self.resid_db),
                "noise_method": self.noise_method}

    @classmethod
    def from_dict(cls, d: dict) -> "BeamStats":
        def arr(x):
            return None if x is None else np.asarray(x, dtype=float)
        lv = d.get("level_db")
        return cls(mean_db=arr(d["mean_db"]), std_db=arr(d["std_db"]), diff_amp_std_db=arr(d["diff_amp_std_db"]),
                   phase_std_rad=arr(d.get("phase_std_rad")), diff_phase_std_rad=arr(d.get("diff_phase_std_rad")),
                   noise_db=float(d["noise_db"]), n_frames=int(d["n_frames"]), n_pairs=int(d["n_pairs"]),
                   level_db=None if lv is None else float(lv), resid_db=arr(d.get("resid_db")),
                   noise_method=str(d.get("noise_method", "level")))


@dataclass
class RadarBaseline:
    """No-flame reference of the static scene, captured from >= 20 frames (operator action) at one vehicle position.

    heatmap: bearing (deg) -> BeamStats of the beam at that bearing (default grid -30..30 step 5 deg);
    profile: BeamStats of the range profile (no phase). Either may be None if that source was absent.
    """
    n_bins: int
    range_res_m: float
    heatmap: Dict[float, BeamStats]
    profile: Optional[BeamStats]
    n_frames: int
    geometry: ArrayGeometry = DEFAULT_ARRAY
    meta: dict = field(default_factory=dict)

    MIN_FRAMES = 20

    @classmethod
    def capture(cls, frames: Sequence[RadarFrame], bearings_deg=DEFAULT_BEARINGS,
                geometry: ArrayGeometry = DEFAULT_ARRAY, max_pair_dt_s: float = 0.5, meta: Optional[dict] = None):
        good = [f for f in frames if f.usable]
        if len(good) < cls.MIN_FRAMES:
            raise ValueError(f"baseline needs >= {cls.MIN_FRAMES} usable frames, got {len(good)}")
        n_bins = good[0].n_bins
        res = good[0].range_res_m
        if any(f.n_bins != n_bins or abs(f.range_res_m - res) > 1e-9 for f in good):
            raise ValueError("baseline frames disagree on bin count or range resolution")
        heat: Dict[float, BeamStats] = {}
        hf = [f for f in good if f.iq is not None]
        if len(hf) >= cls.MIN_FRAMES:
            t = np.array([f.t for f in hf])
            for b in bearings_deg:
                y = np.stack([beam(f.iq, b, geometry) for f in hf])
                heat[float(b)] = BeamStats.from_series(t, _db(y), np.angle(y), max_pair_dt_s)
        pf = [f for f in good if f.range_profile_db is not None]
        prof = None
        if len(pf) >= cls.MIN_FRAMES:
            prof = BeamStats.from_series(np.array([f.t for f in pf]), np.stack([f.range_profile_db for f in pf]),
                                         None, max_pair_dt_s)
        if not heat and prof is None:
            raise ValueError("baseline: neither source has enough frames")
        return cls(n_bins=n_bins, range_res_m=res, heatmap=heat, profile=prof, n_frames=len(good),
                   geometry=geometry, meta=dict(meta or {}))

    def stats_for(self, source: str, bearing_deg: float, tol_deg: float) -> Optional[BeamStats]:
        if source == "profile":
            return self.profile
        if not self.heatmap:
            return None
        b = min(self.heatmap, key=lambda k: abs(k - bearing_deg))
        return self.heatmap[b] if abs(b - bearing_deg) <= tol_deg else None

    def to_dict(self) -> dict:
        return {"n_bins": self.n_bins, "range_res_m": self.range_res_m, "n_frames": self.n_frames,
                "geometry": {"positions_lambda": list(self.geometry.positions_lambda), "sign": self.geometry.sign},
                "heatmap": {str(k): v.to_dict() for k, v in self.heatmap.items()},
                "profile": None if self.profile is None else self.profile.to_dict(), "meta": self.meta}

    @classmethod
    def from_dict(cls, d: dict) -> "RadarBaseline":
        g = d.get("geometry") or {}
        return cls(n_bins=int(d["n_bins"]), range_res_m=float(d["range_res_m"]), n_frames=int(d["n_frames"]),
                   heatmap={float(k): BeamStats.from_dict(v) for k, v in d["heatmap"].items()},
                   profile=None if d.get("profile") is None else BeamStats.from_dict(d["profile"]),
                   geometry=ArrayGeometry(tuple(g.get("positions_lambda", DEFAULT_ARRAY.positions_lambda)),
                                          float(g.get("sign", 1.0))),
                   meta=d.get("meta") or {})

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, path) -> "RadarBaseline":
        return cls.from_dict(json.loads(Path(path).read_text()))


# --- first solid echo -----------------------------------------------------------------------------------------
def cfar_clutter_db(level_db, range_res_m: float, halfwidth_m: float = 2.0, guard_m: float = 0.3,
                    min_cells: int = 4) -> np.ndarray:
    """Local clutter level per bin (order-statistic CFAR): median of `level_db` over the bins within +-halfwidth_m,
    excluding the bin itself and +-guard_m around it (the target's own range spread). NaN where fewer than
    `min_cells` reference bins exist (array edges): such a bin cannot be shown to stand above its clutter."""
    L = np.asarray(level_db, dtype=float)
    n = L.size
    W = max(1, int(math.ceil(halfwidth_m / range_res_m - 1e-9)))
    G = max(0, int(math.ceil(guard_m / range_res_m - 1e-9)))
    G = min(G, W)
    pad = np.pad(np.where(np.isfinite(L), L, np.nan), W, mode="constant", constant_values=np.nan)
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * W + 1).copy()      # [n, 2W+1], centre at index W
    win[:, W - G:W + G + 1] = np.nan
    cnt = np.isfinite(win).sum(axis=1)
    out = np.full(n, np.nan)
    good = cnt >= min_cells
    if good.any():
        out[good] = np.nanmedian(win[good], axis=1)
    return out


def first_solid_echo(window_max_db, noise_db, near_edge_m: Optional[float], range_res_m: float,
                     min_snr_db: float = 12.0, persist: float = 0.5, present_frac=None, reference_db=None,
                     reference_std_db=None, clutter_margin_db: float = 12.0, cfar_halfwidth_m: float = 2.0,
                     cfar_guard_m: float = 0.3, max_reference_std_db: float = 2.0,
                     min_range_m: float = 0.0) -> Optional[float]:
    """Range (m) of the first SOLID echo beyond the near edge, or None.

    A bin b (range r_b) is a solid echo when ALL hold:
    1. beyond: r_b > near edge (and r_b >= min_range_m);
    2. seen through the window: window-max amplitude >= noise + min_snr_db (the max, because gaps in a flame give clear
       looks), and present (>= noise + present_snr_db, computed by the caller) in >= `persist` of the window's frames
       (`present_frac`; skipped if None);
    3. point-like and clearly above clutter: its level stands >= clutter_margin_db above the local clutter
       (`cfar_clutter_db`: median over +-cfar_halfwidth_m excluding +-cfar_guard_m) and is the local maximum within
       +-cfar_guard_m. The level is `reference_db` (the detector passes the no-flame BASELINE mean, so the flame
       cannot disturb this test) or, if None, `window_max_db`;
    4. non-flickering (static object): when `reference_std_db` is given (the baseline's per-frame dB std), it is
       <= max_reference_std_db. Phase flicker in the WINDOW is allowed: it is what the flame does to a solid echo
       behind it, and the window amplitude may dip while the flame is on (rule 2 uses the max).
    Ground clutter is not a solid echo: it is not >= 12 dB above its neighbours. A single Rayleigh clutter bin beats
    the median of its neighbours by 12 dB with probability ~2e-5. `noise_db` may be a scalar or per-bin array.
    This is the echo the decision's CLOSED rule needs beyond the flame, and the far end of the radar ceiling (depth
    estimator c). It can still be an object INSIDE the flame zone (a post, a rock), so the ceiling is only ever an
    upper-bound candidate and never lowers the depth unless calibration trusts it (depth.combine)."""
    wm = np.asarray(window_max_db, dtype=float)
    r = np.arange(wm.size) * range_res_m
    ne = near_edge_m if near_edge_m is not None else 0.0
    beyond = (r > ne) & (r >= min_range_m)
    ok = beyond & np.isfinite(wm) & (wm >= np.asarray(noise_db, dtype=float) + min_snr_db)
    if present_frac is not None:
        ok &= np.asarray(present_frac, dtype=float) >= persist
    if not ok.any():
        return None
    level = wm if reference_db is None else np.asarray(reference_db, dtype=float)
    clutter = cfar_clutter_db(level, range_res_m, cfar_halfwidth_m, cfar_guard_m)
    ok &= np.isfinite(clutter) & (level >= np.nan_to_num(clutter, nan=np.inf) + clutter_margin_db)
    G = max(0, int(math.ceil(cfar_guard_m / range_res_m - 1e-9)))
    if G > 0:
        pad = np.pad(level, G, mode="constant", constant_values=-np.inf)
        win = np.lib.stride_tricks.sliding_window_view(pad, 2 * G + 1)
        ok &= level >= win.max(axis=1)
    if reference_std_db is not None:
        ok &= np.asarray(reference_std_db, dtype=float) <= max_reference_std_db
    idx = np.flatnonzero(ok)
    return None if idx.size == 0 else float(r[idx[0]])


# --- effect duration ------------------------------------------------------------------------------------------
def effect_duration_s(t_start, t_end, flagged, min_frac: float = 0.5, max_gap_s: float = 1.0):
    """Longest time (s) over which an effect HOLDS, from per-pair flags (pair j covers [t_start[j], t_end[j]],
    in time order). A candidate run starts and ends on flagged pairs, has no gap > max_gap_s between consecutive
    flagged pairs, and has >= min_frac of its pairs flagged in EACH half of its span (so one stray flag before the
    onset cannot stretch a short effect). Returns (duration_s, n_flagged_in_that_run); (0.0, 0) when nothing holds."""
    ts = np.asarray(t_start, dtype=float)
    te = np.asarray(t_end, dtype=float)
    f = np.asarray(flagged, dtype=bool)
    idx = np.flatnonzero(f)
    if idx.size == 0:
        return 0.0, 0
    seg = np.zeros(idx.size, int)
    for k in range(1, idx.size):
        seg[k] = seg[k - 1] + (1 if ts[idx[k]] - te[idx[k - 1]] > max_gap_s + 1e-9 else 0)
    best = (0.0, 0)
    for a in range(idx.size):
        for b in range(idx.size - 1, a - 1, -1):
            if seg[b] != seg[a]:
                continue
            i, j = idx[a], idx[b]
            span = float(te[j] - ts[i])
            if span <= best[0]:
                break
            mid = 0.5 * (ts[i] + te[j])
            sel = np.arange(i, j + 1)
            first = sel[te[sel] <= mid + 1e-9]
            second = sel[te[sel] > mid + 1e-9]
            ok = all(h.size == 0 or f[h].mean() >= min_frac - 1e-12 for h in (first, second))
            if ok:
                best = (span, int(f[sel].sum()))
                break
    return best


# --- detector -------------------------------------------------------------------------------------------------
@dataclass
class RadarFlameConfig:
    """Placeholder thresholds (to be set from lab-flame and car tests). k_* are z-score thresholds; dB values relative
    to the source's own scale.

    present_snr_db: per-frame level above noise that counts an echo as "present" for the persistence test.
    max_noise_db: absolute ceiling for the window noise floor (None = off); max_noise_rise_db: ceiling on the rise of
    the window noise over the baseline (interference, radome water/ice, a failing radar). se_factor: the standard
    error of a sample std of frame-to-frame differences is ~ sigma*sqrt(se_factor/m) (0.75 accounts for the lag-1
    correlation of differences of white noise; 0.5 would be the independent-sample value). flicker_min_snr_db:
    flicker statistics are only evaluated on echoes at least this far above the noise floor (closer to the floor the
    dB and phase noise are strongly non-Gaussian and the z-scores are not trustworthy).
    Solid echo (`first_solid_echo`): solid_clutter_margin_db, cfar_halfwidth_m, cfar_guard_m, solid_max_std_db.
    Control bins: echoes (>= flicker_min_snr_db) in FRONT of the flame, from min_range_m to near edge -
    control_guard_m; the flame's line of sight does not reach them. An effect there means vibration, interference,
    radome water or a moving object, so an effect behind the flame is then not attributed to the flame (UNKNOWN), and
    with require_control an effect behind the flame with NO control echo is UNKNOWN too (cannot rule those out).
    Common-mode phase jitter estimated on control bins is added in quadrature to every bin's phase sigma.
    Effect duration: an effect is accepted only if it HOLDS for >= min_effect_s of frame pairs (`effect_duration_s`:
    per-pair flag = mean over the effect bins of the squared normalised step >= effect_pair_k^2, or per-frame loss
    z >= effect_pair_k and loss >= min_loss_db; >= min_effect_frac flagged in each half; gaps <= effect_max_gap_s).
    noise_min_bins: the window noise-rise test uses the control-region bins when at least this many exist (the flame
    cannot raise them), otherwise all bins.
    """
    window_s: float = 3.0
    min_window_s: float = 1.0
    min_frames: int = 5
    k_loss: float = 4.0
    min_loss_db: float = 1.0
    k_flicker: float = 4.0
    min_snr_db: float = 12.0
    persist: float = 0.5
    present_snr_db: float = 6.0
    max_noise_db: Optional[float] = None
    max_noise_rise_db: float = 10.0
    stale_s: float = 1.0
    max_pair_dt_s: float = 0.5
    bearing_tol_deg: float = 2.5
    min_range_m: float = 0.5
    std_floor_db: float = 0.05
    phase_floor_rad: float = 0.005
    se_factor: float = 0.75
    flicker_min_snr_db: float = 15.0
    solid_clutter_margin_db: float = 12.0
    cfar_halfwidth_m: float = 2.0
    cfar_guard_m: float = 0.3
    solid_max_std_db: float = 2.0
    control_guard_m: float = 2.0
    require_control: bool = True
    control_median_z: float = 1.5
    control_median_min_bins: int = 8
    min_effect_s: float = 2.0
    min_effect_frac: float = 0.5
    effect_pair_k: float = 2.5
    effect_max_gap_s: float = 1.0
    noise_min_bins: int = 16
    # TLV 2 range-profile-only frames (no heatmap): UNKNOWN unless enabled. The demo's profile is the sum over the
    # virtual antennas of log2|x| (TI documentation); the unit divides by n_virt, but no EVM capture has confirmed
    # that scaling, and every dB threshold above (solid echo, present, loss, noise rise) depends on it. Placeholder:
    # enable only after a real capture checks the profile against the heatmap.
    allow_profile_only: bool = False


@dataclass
class RadarState:
    """status in {"FLAME_EFFECT", "NO_EFFECT", "UNKNOWN"}. Scalars are maxima over the target bins (echoes in the
    baseline >= min_snr above noise, beyond the near edge). per_bin: arrays for the UI (lists).
    noise_db: noise floor used for the thresholds (baseline floor + any measured rise); noise_rise_db: window noise
    rise over the baseline; control_*: the control echoes in front of the flame; effect_s: how long the effect held
    (`effect_duration_s`); common_phase_rad: common-mode phase jitter estimated on the control echoes."""
    status: str
    reason: str
    loss_db: float = float("nan")
    flicker_phase_rad: float = float("nan")
    flicker_amp_db: float = float("nan")
    loss_z: float = float("nan")
    flicker_phase_z: float = float("nan")
    flicker_amp_z: float = float("nan")
    far_echo_m: Optional[float] = None
    source: Optional[str] = None
    noise_db: float = float("nan")
    n_frames: int = 0
    window_span_s: float = 0.0
    effect_ranges_m: List[float] = field(default_factory=list)
    per_bin: dict = field(default_factory=dict)
    noise_rise_db: float = float("nan")
    noise_method: Optional[str] = None
    n_control_bins: int = 0
    control_z_max: float = float("nan")
    control_z_median: float = float("nan")
    common_phase_rad: float = float("nan")
    effect_s: float = 0.0
    baseline_invalidated: bool = False

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        for k, v in list(d.items()):
            if isinstance(v, float) and not math.isfinite(v):
                d[k] = None
        return d


def _unknown(reason: str, **kw) -> RadarState:
    return RadarState(status="UNKNOWN", reason=reason, **kw)


def _nanmax(x) -> float:
    v = np.asarray(x, dtype=float)
    v = v[np.isfinite(v)]
    return float(v.max()) if v.size else float("nan")


class RadarFlameDetector:
    """Sliding-window radar flame effect against a baseline. `update(frame, t, ...)` = `push` + `evaluate`.

    Statistics per range bin over the window (target bins: beyond the near edge and >= min_snr_db above the baseline
    noise floor; flicker only on bins >= flicker_min_snr_db):
    - loss_db = baseline mean dB - window MAX dB; loss_z = loss_db / baseline amplitude std.
    - flicker_amp_db = `amp_flicker_db` of the window; flicker_phase_rad = circular std of frame-to-frame phase
      differences (heatmap only; the range profile has no phase).
    - flicker z-scores are log ratios against the baseline's own frame-to-frame noise sigma_b (floored by the
      thermal-noise value for the echo's SNR at the window's noise floor; phase sigma also includes the common-mode
      jitter seen on the control echoes): z = ln(s_window / sigma_b) / sqrt(se_factor/m_window +
      se_factor/m_baseline). The log makes the sampling distribution of a std close to Gaussian, so k = 4 means
      what it says per bin; the detection is the max over bins and statistics, so the per-window false-alarm rate
      is several times the per-bin rate (measured on synthetic noise in tests/test_radar_flame.py).

    Noise floor: heatmap = the baseline's temporal floor (clutter-independent, `temporal_noise_db`) plus the
    window's measured rise (median `residual_power_db` over the control-region bins, or all bins, vs the baseline's);
    range profile = the window's level floor (`noise_floor_db`), as before.

    evaluate(now, near_edge_m, bearing_deg, moving) returns UNKNOWN when: the vehicle is moving (moving=True also
    INVALIDATES the baseline: echo phases change with any motion, so the baseline must be recaptured once stopped);
    no baseline; the newest frame is older than stale_s; the newest frame had neither heatmap nor range profile; bin
    count / resolution differ from the baseline; no baseline stats for that bearing; < min_window_s (1 s) or <
    min_frames of usable frames in the window; < 2 consecutive pairs; the noise floor rose above the ceiling; no
    reference echo in the baseline beyond the near edge; no SOLID echo beyond the near edge (`first_solid_echo`:
    cannot look behind the flame); or an effect behind the near edge that (a) also appears on the control echoes in
    front of the flame, (b) has no control echo to compare with (require_control), or (c) has not held for
    min_effect_s. FLAME_EFFECT only when none of these apply.
    """

    def __init__(self, baseline: Optional[RadarBaseline], window_s: Optional[float] = None,
                 cfg: Optional[RadarFlameConfig] = None):
        self._baseline = baseline
        self.invalidated_reason: str = ""
        self.cfg = cfg if cfg is not None else RadarFlameConfig()
        if window_s is not None:
            self.cfg.window_s = float(window_s)
        self._frames: List[RadarFrame] = []
        self._last_t: Optional[float] = None
        self._last_bad: str = ""

    @property
    def baseline(self) -> Optional[RadarBaseline]:
        return self._baseline

    @baseline.setter
    def baseline(self, bl: Optional[RadarBaseline]) -> None:
        self._baseline = bl
        if bl is not None:
            self.invalidated_reason = ""

    def invalidate_baseline(self, reason: str) -> bool:
        """Drop the baseline and the window (frames from before a move are not comparable). True if one was held."""
        had = self._baseline is not None
        self._baseline = None
        self._frames.clear()
        if had:
            self.invalidated_reason = reason
        return had

    def push(self, frame: RadarFrame, t: Optional[float] = None) -> None:
        t = float(frame.t if t is None else t)
        self._last_t = t
        if not frame.usable:
            self._last_bad = "newest radar frame has neither heatmap nor range profile (or frame_ok false)"
        else:
            self._last_bad = ""
            if frame.t != t:
                frame = RadarFrame(t=t, range_res_m=frame.range_res_m, iq=frame.iq,
                                   range_profile_db=frame.range_profile_db, frame_ok=frame.frame_ok, sim=frame.sim)
            self._frames.append(frame)
        cut = t - self.cfg.window_s
        while self._frames and self._frames[0].t < cut - 1e-9:
            self._frames.pop(0)

    def update(self, frame: RadarFrame, t: Optional[float] = None, near_edge_m: Optional[float] = None,
               bearing_deg: float = 0.0, moving: bool = False) -> RadarState:
        self.push(frame, t)
        return self.evaluate(self._last_t, near_edge_m=near_edge_m, bearing_deg=bearing_deg, moving=moving)

    def evaluate(self, now: Optional[float] = None, near_edge_m: Optional[float] = None, bearing_deg: float = 0.0,
                 moving: bool = False) -> RadarState:
        c = self.cfg
        if moving:
            had = self.invalidate_baseline("invalidated: vehicle moving")
            return _unknown("vehicle moving: echo phases change, baseline not comparable"
                            + ("; radar baseline invalidated (recapture when stopped)" if had else ""),
                            baseline_invalidated=had)
        bl = self._baseline
        if bl is None:
            why = "no radar baseline (capture one with no flame present)"
            if self.invalidated_reason:
                why += "; previous baseline " + self.invalidated_reason
            return _unknown(why)
        if self._last_t is None:
            return _unknown("no radar frames")
        if now is not None and now - self._last_t > c.stale_s:
            return _unknown(f"radar stale ({now - self._last_t:.1f} s)")
        if self._last_bad:
            return _unknown(self._last_bad)
        if near_edge_m is not None and not math.isfinite(near_edge_m):
            return _unknown("near edge not finite")
        newest = self._frames[-1] if self._frames else None
        if newest is None:
            return _unknown("no usable radar frames in window")
        source = None
        stats = None
        if newest.iq is not None and bl.heatmap:
            source = "heatmap"
            stats = bl.stats_for("heatmap", bearing_deg, c.bearing_tol_deg)
            if stats is None:
                return _unknown(f"no baseline beam within {c.bearing_tol_deg} deg of bearing {bearing_deg:.1f}")
        elif newest.range_profile_db is not None and bl.profile is not None:
            if not c.allow_profile_only:
                return _unknown("range profile only (no heatmap): TLV 2 dB scaling UNVERIFIED on the EVM, profile "
                                "path disabled (allow_profile_only)", source="profile")
            source, stats = "profile", bl.profile
        else:
            return _unknown("newest frame's source has no baseline")
        if source == "heatmap":
            frames = [f for f in self._frames if f.iq is not None]
        else:
            frames = [f for f in self._frames if f.range_profile_db is not None]
        if any(f.n_bins != bl.n_bins or abs(f.range_res_m - bl.range_res_m) > 1e-9 for f in frames):
            return _unknown("radar bin count or range resolution differs from the baseline")
        t = np.array([f.t for f in frames])
        span = float(t[-1] - t[0]) if t.size else 0.0
        if t.size < c.min_frames or span < c.min_window_s:
            return _unknown(f"only {span:.2f} s / {t.size} frames in window (need {c.min_window_s} s)",
                            n_frames=int(t.size), window_span_s=span, source=source)
        y = None
        if source == "heatmap":
            y = np.stack([beam(f.iq, bearing_deg, bl.geometry) for f in frames])
            A = _db(y)
            P = np.angle(y)
        else:
            A = np.stack([np.asarray(f.range_profile_db, dtype=float) for f in frames])
            P = None
        if not np.all(np.isfinite(A)):
            return _unknown("non-finite radar amplitudes", source=source)
        n_bins = A.shape[1]
        r = np.arange(n_bins) * bl.range_res_m
        ne = near_edge_m if near_edge_m is not None else 0.0
        ok = _pair_ok(t, c.max_pair_dt_s)
        m_w = int(ok.sum())
        common = dict(source=source, n_frames=int(t.size), window_span_s=span, noise_method=stats.noise_method)
        if m_w < 2:
            return _unknown("too few consecutive radar frame pairs in window", **common)

        # ---- noise floor and noise-rise gate
        front = (r >= c.min_range_m) & (r < ne - c.control_guard_m)
        if source == "heatmap" and stats.resid_db is not None and stats.resid_db.size == n_bins:
            sel = front if int(front.sum()) >= c.noise_min_bins else np.ones(n_bins, bool)
            resid_w = residual_power_db(t, y, c.max_pair_dt_s)
            rise = float(np.median(resid_w[sel]) - np.median(stats.resid_db[sel]))
            noise = stats.noise_db + max(0.0, rise)
        else:
            noise = noise_floor_db(A)
            rise = float(noise - stats.noise_db)
        common.update(noise_db=noise, noise_rise_db=rise)
        ceiling = stats.noise_db + c.max_noise_rise_db
        if c.max_noise_db is not None:
            ceiling = min(ceiling, c.max_noise_db)
        if noise > ceiling or rise > c.max_noise_rise_db:
            where = ""
            if source == "heatmap" and stats.resid_db is not None:
                where = (" measured on the echoes in front of the flame: interference, or hot gas over the near "
                         "ground" if int(front.sum()) >= c.noise_min_bins else " measured on all bins")
            return _unknown(f"radar noise floor {noise:.1f} dB above ceiling {ceiling:.1f} dB "
                            f"(rise {rise:.1f} dB{where})", **common)

        wmax = A.max(axis=0)
        wmean = A.mean(axis=0)
        present = (A >= noise + c.present_snr_db).mean(axis=0)
        far = first_solid_echo(wmax, noise, ne, bl.range_res_m, c.min_snr_db, c.persist, present,
                               reference_db=stats.mean_db, reference_std_db=stats.std_db,
                               clutter_margin_db=c.solid_clutter_margin_db, cfar_halfwidth_m=c.cfar_halfwidth_m,
                               cfar_guard_m=c.cfar_guard_m, max_reference_std_db=c.solid_max_std_db,
                               min_range_m=c.min_range_m)
        snr_b = stats.mean_db - stats.noise_db
        beyond = (r > ne) & (r >= c.min_range_m)
        target = beyond & (snr_b >= c.min_snr_db)
        flick_elig = snr_b >= c.flicker_min_snr_db
        control = front & flick_elig if near_edge_m is not None else np.zeros(n_bins, bool)

        # loss: baseline mean - window max, z against the baseline's amplitude spread
        sd = np.sqrt(stats.std_db ** 2 + c.std_floor_db ** 2)
        loss = stats.mean_db - wmax
        loss_z = loss / sd
        rel_se = math.sqrt(c.se_factor / m_w + c.se_factor / max(stats.n_pairs, 1))
        th_amp, th_ph = thermal_noise_diff_std(stats.mean_db, noise) if source == "heatmap" else (0.0, 0.0)
        lin = 10.0 ** (A / 20.0)
        dlin = np.diff(lin, axis=0)
        mlin = np.maximum(lin.mean(axis=0), _TINY)
        famp = amp_flicker_db(A, ok)
        sb = np.maximum(np.maximum(stats.diff_amp_std_db, th_amp), c.std_floor_db)
        famp_z = np.log(np.maximum(famp, _TINY) / sb) / rel_se
        common_ph = float("nan")
        if P is not None and stats.diff_phase_std_rad is not None:
            dP = np.angle(np.exp(1j * np.diff(P, axis=0)))
            fph = _circ_std(dP[ok], axis=0)
            sp = np.maximum(np.maximum(stats.diff_phase_std_rad, th_ph), c.phase_floor_rad)
            fph_z_raw = np.log(np.maximum(fph, _TINY) / sp) / rel_se
            # common-mode phase jitter (platform vibration, oscillator): excess phase variance on the control echoes
            if control.any():
                common_ph = math.sqrt(max(0.0, float(np.median(fph[control] ** 2 - sp[control] ** 2))))
                sp_eff = np.sqrt(sp ** 2 + common_ph ** 2)
            else:
                sp_eff = sp
            fph_z = np.log(np.maximum(fph, _TINY) / sp_eff) / rel_se
        else:
            dP = None
            fph = np.full(n_bins, np.nan)
            fph_z_raw = fph_z = np.full(n_bins, np.nan)
            sp_eff = None

        def crit(lz, l, az, pz):
            return (((lz >= c.k_loss) & (l >= c.min_loss_db)) | (np.nan_to_num(az, nan=-np.inf) >= c.k_flicker)
                    | (np.nan_to_num(pz, nan=-np.inf) >= c.k_flicker))

        flick_ok = target & flick_elig
        famp_zt = np.where(flick_ok, famp_z, np.nan)
        fph_zt = np.where(flick_ok, fph_z, np.nan)
        # control echoes: raw z (no common-mode allowance), loss only where >= min_snr
        c_amp_z = np.where(control, famp_z, np.nan)
        c_ph_z = np.where(control, fph_z_raw, np.nan)
        c_eff = control & crit(loss_z, loss, c_amp_z, c_ph_z)
        cz = np.fmax(c_amp_z, c_ph_z) if P is not None else c_amp_z
        cz = cz[control]
        common.update(n_control_bins=int(control.sum()), control_z_max=_nanmax(cz),
                      control_z_median=float(np.nanmedian(cz)) if cz.size and np.isfinite(cz).any() else float("nan"),
                      common_phase_rad=common_ph)

        per_bin = {"range_m": r.tolist(), "window_max_db": wmax.tolist(), "window_mean_db": wmean.tolist(),
                   "baseline_db": stats.mean_db.tolist(), "loss_db": loss.tolist(), "loss_z": loss_z.tolist(),
                   "flicker_amp_db": famp.tolist(), "flicker_amp_z": famp_zt.tolist(),
                   "flicker_phase_rad": fph.tolist(), "flicker_phase_z": fph_zt.tolist(),
                   "present_frac": present.tolist(), "target": target.tolist(), "control": control.tolist()}
        common["per_bin"] = per_bin
        common["far_echo_m"] = far
        if not target.any():
            return _unknown("no reference echo in the baseline beyond the near edge", **common)
        if far is None:
            return _unknown("no solid echo beyond the near edge (a persistent, point-like echo >= "
                            f"{c.solid_clutter_margin_db:g} dB above its clutter): cannot look behind the flame",
                            **common)

        eff = target & crit(loss_z, loss, famp_zt, fph_zt)

        def tmax(x):
            return _nanmax(np.asarray(x)[target])

        scal = dict(loss_db=tmax(loss), flicker_phase_rad=tmax(fph), flicker_amp_db=tmax(famp), loss_z=tmax(loss_z),
                    flicker_phase_z=tmax(fph_zt), flicker_amp_z=tmax(famp_zt))
        if not eff.any():
            why = "echoes beyond the near edge match the baseline"
            if c_eff.any():
                why += f" (effect on {int(c_eff.sum())} control echo bin(s) in front of the flame: radar disturbed)"
            return RadarState(status="NO_EFFECT", reason=why, **scal, **common)
        n_eff = int(eff.sum())
        rng_eff = [float(v) for v in r[eff]]
        med_ok = cz.size >= c.control_median_min_bins and np.isfinite(cz).any()
        if c_eff.any() or (med_ok and float(np.nanmedian(cz)) >= c.control_median_z):
            return _unknown(f"effect on {n_eff} bin(s) behind the near edge but also on the control echoes in front "
                            "of the flame (vibration, interference, radome water or a moving object?): not attributed "
                            "to a flame", effect_ranges_m=rng_eff, **scal, **common)
        if not control.any() and c.require_control:
            return _unknown(f"effect on {n_eff} bin(s) behind the near edge, but no control echo (>= "
                            f"{c.flicker_min_snr_db:g} dB) in front of the flame to rule out vibration or interference",
                            effect_ranges_m=rng_eff, **scal, **common)
        # ---- duration: per pair, normalised step / loss on the effect bins
        okj = np.flatnonzero(ok) + 1                       # frame index j of pair (j-1, j)
        with np.errstate(invalid="ignore", divide="ignore"):
            terms = []
            if dP is not None:
                ph_e = eff & np.isfinite(fph_zt)
                if ph_e.any():
                    terms.append(np.mean((dP[okj - 1][:, ph_e] / sp_eff[ph_e]) ** 2, axis=1))
            am_e = eff & np.isfinite(famp_zt)
            if am_e.any():
                terms.append(np.mean((8.685889638 * dlin[okj - 1][:, am_e] / mlin[am_e] / sb[am_e]) ** 2, axis=1))
            k2 = c.effect_pair_k ** 2
            flag = np.zeros(okj.size, bool)
            for v in terms:
                flag |= v >= k2
            lz_f = np.mean((stats.mean_db[eff] - A[okj][:, eff]) / sd[eff], axis=1)
            l_f = np.mean(stats.mean_db[eff] - A[okj][:, eff], axis=1)
            flag |= (lz_f >= c.effect_pair_k) & (l_f >= c.min_loss_db)
        dur, n_flag = effect_duration_s(t[okj - 1], t[okj], flag, c.min_effect_frac, c.effect_max_gap_s)
        common["effect_s"] = dur
        if dur < c.min_effect_s - 1e-9:
            return _unknown(f"effect on {n_eff} bin(s) behind the near edge has held for only {dur:.1f} s of frames "
                            f"(need >= {c.min_effect_s:g} s): not confirmed", effect_ranges_m=rng_eff,
                            **scal, **common)
        return RadarState(status="FLAME_EFFECT", reason=f"effect on {n_eff} echo bin(s) beyond the near edge, held "
                          f"{dur:.1f} s", effect_ranges_m=rng_eff, **scal, **common)


# --- fusion ---------------------------------------------------------------------------------------------------
@dataclass
class FlameState:
    status: str                          # "FLAME" | "NO_FLAME" | "UNKNOWN"
    reason: str
    radar_status: Optional[str] = None
    thermal_flame: Optional[bool] = None


def fuse_flame(radar_state: Optional[RadarState], thermal_flame_at_bearing: Optional[bool]) -> FlameState:
    """AND rule. FLAME only if radar FLAME_EFFECT and thermal flame pixels at that bearing. UNKNOWN if the radar is
    UNKNOWN (or missing) or the thermal flag is unavailable (None). Everything else NO_FLAME (smoke, mist, exhaust,
    hot surfaces). NO_FLAME never permits a crossing: the decision needs FLAME to evaluate one at all."""
    rs = None if radar_state is None else radar_state.status
    if rs is None or rs == "UNKNOWN":
        why = "radar missing" if rs is None else f"radar UNKNOWN: {radar_state.reason}"
        return FlameState("UNKNOWN", why, rs, thermal_flame_at_bearing)
    if thermal_flame_at_bearing is None:
        return FlameState("UNKNOWN", "thermal flame flag unavailable", rs, None)
    if rs == "FLAME_EFFECT" and thermal_flame_at_bearing:
        return FlameState("FLAME", "radar effect behind the front AND flame-temperature pixels at the bearing", rs, True)
    if rs == "FLAME_EFFECT":
        return FlameState("NO_FLAME", "radar effect but no flame-temperature pixels (mist, exhaust, steam?)", rs, False)
    if thermal_flame_at_bearing:
        return FlameState("NO_FLAME", "flame-temperature pixels but no radar effect behind them", rs, True)
    return FlameState("NO_FLAME", "no radar effect and no flame-temperature pixels", rs, False)
