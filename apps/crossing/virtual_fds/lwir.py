"""Virtual TC001 thermal camera: 8-14 um band radiance ray-marched through an FDS temperature / soot field.

SIMULATED. Model (every constant is an assumption, stated here and in REPORT.md):

Radiative transfer along each pixel's central ray (no scattering, local thermodynamic equilibrium, refraction
ignored), front to back from the camera:
    L_b = sum_k tau_k * B_b(T_k) * (1 - exp(-kappa_b,k ds)) + tau_end * L_b,background,   tau_{k+1} = tau_k exp(-kappa_b,k ds)
in three grey sub-bands b = 8-10, 10-12, 12-14 um. B_b(T) is the Planck radiance integrated over the sub-band
(W m-2 sr-1). The camera's band is taken as flat 8-14 um (real microbolometer response and lens transmission vary).

Absorption coefficient kappa_b [1/m] = soot + hot-product gas:
- soot (Rayleigh limit, particles << wavelength): kappa_soot = C_SOOT * f_v / lambda_b, with C_SOOT = 7.0
  (= 6 pi E(m) with E(m) ~ 0.37; literature values of E(m) span about 0.2-0.4, so +-50 %), lambda_b the sub-band
  centre (9, 11, 13 um), soot volume fraction f_v = rho_soot / 1850 kg/m3. For reference, the same C gives the
  broadband Planck-mean kappa_P = 3.72 * C / c2 * f_v * T ~ 1810 f_v T [1/m] (often quoted as ~1862 f_v T).
  The band value is much smaller than the broadband one at flame temperature (at 1200 K: C/lambda = 6.4e5 f_v in
  the 10-12 um band, 7.8e5 f_v in the 8-10 um band, vs 2.2e6 f_v broadband) because soot absorbs less at long
  wavelengths.
- hot combustion products (H2O continuum and weak CO2/H2O lines inside the 8-14 um window): a grey placeholder
  kappa_gas = KAPPA_GAS0 * xi, xi = clip((T - T_amb) / (T_GAS_REF - T_amb), 0, 1), a temperature proxy for the
  product mole fraction (FDS volume output here has no species). KAPPA_GAS0 = 0.10 1/m default with sensitivity
  runs at 0.03 and 0.30; T_GAS_REF = 1200 K. This is NOT a fitted band model.
- FDS smears the 0.2 m grass bed into the lowest 1 m cell; burning or unburnt grass blades are not represented
  as an LWIR emitter in the gas. Instead the ground (z = 0) is an opaque surface of emissivity GROUND_EPS = 0.95 at
  the temperature of the lowest gas cell above it (bilinear in x, y), reflecting ambient: a stand-in for burning
  fuel bed, hot ash and unburnt grass. Rays leaving the domain upward see a clear sky of SKY_BT_K = 253 K; rays
  leaving through a side see ambient (distant terrain, haze); rays meeting the ground outside the domain see
  ambient ground.

Camera: one ray per pixel centre (no pixel footprint averaging, no optics blur, no noise, no NUC/shutter effects).
Apparent temperature = inversion of the band radiance with the camera emissivity setting CAMERA_EPS = 0.95 and the
reflected temperature at ambient: L = eps B(T_app) + (1 - eps) B(T_amb). Then clipped to the TC001 low-gain range
-20 .. 550 C (anything above reads 550 C: saturation). Atmospheric absorption of clear air over <= 60 m is ignored.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

import numpy as np

from crossing.geometry import CameraPose, level_from_camera
from crossing.thermal import DEFAULT_CAMERA, CameraModel

from .fields import Field, Sampler

H_PLANCK = 6.62607015e-34
C_LIGHT = 2.99792458e8
K_BOLTZ = 1.380649e-23
C2 = H_PLANCK * C_LIGHT / K_BOLTZ               # m K
SUB_BANDS_UM = ((8.0, 10.0), (10.0, 12.0), (12.0, 14.0))
SOOT_DENSITY = 1850.0                            # kg/m3
C_SOOT = 7.0
KAPPA_GAS0 = 0.10                                # 1/m, placeholder
T_GAS_REF = 1200.0                               # K
GROUND_EPS = 0.95
SKY_BT_K = 253.0
CAMERA_EPS = 0.95
TC001_MIN_C = -20.0
TC001_MAX_C = 550.0


@lru_cache(maxsize=1)
def band_tables() -> Tuple[np.ndarray, np.ndarray]:
    """(T grid K, B [3, nT] band radiance W m-2 sr-1) for the three sub-bands, trapezoid over 81 points each."""
    T = np.arange(150.0, 2601.0, 1.0)
    out = []
    for lo, hi in SUB_BANDS_UM:
        lam = np.linspace(lo, hi, 81) * 1e-6
        x = C2 / (lam[:, None] * T[None, :])
        bl = 2.0 * H_PLANCK * C_LIGHT ** 2 / lam[:, None] ** 5 / np.expm1(x)
        out.append(np.trapz(bl, lam, axis=0))
    return T, np.array(out)


def band_radiance(t_k) -> np.ndarray:
    """[3, ...] sub-band radiances of a blackbody at t_k (K)."""
    T, B = band_tables()
    t = np.clip(np.asarray(t_k, dtype=float), T[0], T[-1])
    return np.stack([np.interp(t, T, B[i]) for i in range(3)])


def apparent_temperature_k(total_band_radiance, eps: float = CAMERA_EPS, t_refl_k: float = 305.15) -> np.ndarray:
    """Invert total 8-14 um radiance to the camera's displayed temperature (K), before range clipping."""
    T, B = band_tables()
    L = B.sum(axis=0)
    lr = float(np.interp(t_refl_k, T, L))
    lbb = (np.asarray(total_band_radiance, dtype=float) - (1.0 - eps) * lr) / eps
    return np.interp(lbb, L, T, left=T[0], right=T[-1])


@dataclass(frozen=True)
class OpticsParams:
    kappa_gas0: float = KAPPA_GAS0
    t_gas_ref_k: float = T_GAS_REF
    c_soot: float = C_SOOT
    ground_eps: float = GROUND_EPS
    sky_bt_k: float = SKY_BT_K
    camera_eps: float = CAMERA_EPS
    ds_m: float = 0.5


def kappa_fields(f: Field, p: OpticsParams = OpticsParams()) -> np.ndarray:
    """[3, z, y, x] band absorption coefficients (1/m)."""
    fv = np.maximum(f.soot, 0.0) / SOOT_DENSITY
    xi = np.clip((f.temp_k - f.t_ambient_k) / (p.t_gas_ref_k - f.t_ambient_k), 0.0, 1.0)
    out = []
    for lo, hi in SUB_BANDS_UM:
        lam = 0.5 * (lo + hi) * 1e-6
        out.append(p.c_soot * fv / lam + p.kappa_gas0 * xi)
    return np.array(out, dtype=np.float32)


def camera_rays(model: CameraModel, pose: CameraPose, imu=None) -> np.ndarray:
    """[h*w, 3] unit rays in the vehicle-level frame (x forward, y left, z up) for every pixel centre."""
    rows, cols = np.mgrid[0:model.h, 0:model.w]
    v = np.stack([np.ones(rows.size), -(cols.ravel() - model.ppx) / model.fx, -(rows.ravel() - model.ppy) / model.fy])
    r = level_from_camera(pose, imu) @ v
    return (r / np.linalg.norm(r, axis=0)).T


def level_to_world(rays_level: np.ndarray, facing: str = "-x") -> np.ndarray:
    """Vehicle-level (forward, left, up) to FDS world (x, y, z) for a vehicle facing -x: forward = -x, left = -y."""
    if facing != "-x":
        raise ValueError("only a vehicle facing -x (towards the approaching C064 head) is implemented")
    w = rays_level.copy()
    w[:, 0] = -rays_level[:, 0]
    w[:, 1] = -rays_level[:, 1]
    return w


def _slab(o, d, lo, hi):
    """Ray-box intersection (t_enter, t_exit) for origin o (3,) and directions d (N, 3)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / d
        t1 = (lo[None, :] - o[None, :]) * inv
        t2 = (hi[None, :] - o[None, :]) * inv
    tmin = np.where(np.isfinite(t1), np.minimum(t1, t2), -np.inf)
    tmax = np.where(np.isfinite(t2), np.maximum(t1, t2), np.inf)
    # zero direction components: inside the slab -> unbounded, outside -> empty
    zero = d == 0
    outside = zero & ((o[None, :] < lo[None, :]) | (o[None, :] > hi[None, :]))
    tmin = np.where(zero, -np.inf, tmin); tmax = np.where(zero, np.inf, tmax)
    t_in = tmin.max(axis=1); t_out = tmax.min(axis=1)
    t_out = np.where(outside.any(axis=1), -np.inf, t_out)
    return np.maximum(t_in, 0.0), t_out


@dataclass
class Render:
    temps_k: np.ndarray           # [h, w] apparent temperature after TC001 clipping (K)
    unclipped_k: np.ndarray       # [h, w] apparent temperature before clipping (K)
    ground_hit: np.ndarray        # [h, w] bool: the ray met the ground inside the domain
    max_optical_depth: float      # largest 10-12 um optical depth along any ray
    origin: tuple


def render(f: Field, cam_xyz, model: CameraModel = DEFAULT_CAMERA, pose: CameraPose = CameraPose(), imu=None,
           params: OpticsParams = OpticsParams()) -> Render:
    """Render one virtual TC001 frame from a camera at world point cam_xyz (x, y, z m) facing -x."""
    o = np.asarray(cam_xyz, dtype=float)
    dirs = level_to_world(camera_rays(model, pose, imu))
    n = dirs.shape[0]
    kap = kappa_fields(f, params)
    src = band_radiance(f.temp_k).astype(np.float32)                       # [3, z, y, x]
    samp = Sampler(f, np.concatenate([kap, src]), outside=[0, 0, 0] + list(band_radiance(f.t_ambient_k)))
    # march only through the part of the grid that is not ambient (kappa > 0 there)
    active = (kap.max(axis=0) > 1e-6)
    if active.any():
        kz, ky, kx = np.nonzero(active)
        dx, dy, dz = f.d
        lo = np.array([f.x[kx.min()] - dx, f.y[ky.min()] - dy, max(f.z[kz.min()] - dz, 0.0)])
        hi = np.array([f.x[kx.max()] + dx, f.y[ky.max()] + dy, f.z[kz.max()] + dz])
        t_in, t_out = _slab(o, dirs, lo, hi)
    else:
        t_in = np.zeros(n); t_out = np.full(n, -np.inf)
    # ground: z = 0
    with np.errstate(divide="ignore", invalid="ignore"):
        t_ground = np.where(dirs[:, 2] < 0, -o[2] / dirs[:, 2], np.inf)
    t_stop = np.minimum(t_out, t_ground)
    L = np.zeros((3, n)); tau = np.ones((3, n)); od = np.zeros(n)
    ds = params.ds_m
    span = np.maximum(t_stop - t_in, 0.0)
    nsteps = int(np.ceil(span.max() / ds)) if span.max() > 0 else 0
    for k in range(nsteps):
        idx = np.flatnonzero(span > k * ds)
        if idx.size == 0:
            break
        seg = np.minimum(ds, span[idx] - k * ds)
        tm = t_in[idx] + k * ds + 0.5 * seg
        p = o[None, :] + dirs[idx] * tm[:, None]
        v = samp.sample(p[:, 0], p[:, 1], p[:, 2])
        a = np.exp(-v[:3] * seg[None, :])
        L[:, idx] += tau[:, idx] * v[3:] * (1.0 - a)
        tau[:, idx] *= a
        od[idx] += v[1] * seg
    # background
    b_amb = band_radiance(f.t_ambient_k)
    b_sky = band_radiance(params.sky_bt_k)
    bg = np.empty((3, n))
    hit = np.isfinite(t_ground)
    xg = o[0] + dirs[:, 0] * np.where(hit, t_ground, 0.0)
    yg = o[1] + dirs[:, 1] * np.where(hit, t_ground, 0.0)
    gs = Sampler(f, f.temp_k, outside=[f.t_ambient_k])
    tg = gs.sample(xg, yg, np.full(n, f.z[0]))[0]
    inside_xy = (xg >= gs.lo[0]) & (xg <= gs.hi[0]) & (yg >= gs.lo[1]) & (yg <= gs.hi[1])
    tg = np.where(hit & inside_xy, tg, f.t_ambient_k)
    bg[:, hit] = params.ground_eps * band_radiance(tg[hit]) + (1 - params.ground_eps) * b_amb[:, None]
    up = ~hit
    # rays leaving upward: sky if they exit through the top of the grid region or are steep; else ambient
    _, t_exit_full = _slab(o, dirs, gs.lo, gs.hi)
    z_exit = o[2] + dirs[:, 2] * np.where(np.isfinite(t_exit_full), t_exit_full, 0.0)
    top_exit = up & (dirs[:, 2] > 0) & (z_exit >= gs.hi[2] - 1e-6)
    bg[:, up] = b_amb[:, None]
    bg[:, top_exit] = b_sky[:, None]
    L += tau * bg
    t_app = apparent_temperature_k(L.sum(axis=0), params.camera_eps, f.t_ambient_k).reshape(model.h, model.w)
    clipped = np.clip(t_app, TC001_MIN_C + 273.15, TC001_MAX_C + 273.15)
    return Render(temps_k=clipped.astype(np.float32), unclipped_k=t_app.astype(np.float32),
                  ground_hit=(hit & inside_xy).reshape(model.h, model.w), max_optical_depth=float(od.max()),
                  origin=tuple(float(v) for v in o))


def soot_band_kappa_per_fv(lambda_um: float = 11.0, c_soot: float = C_SOOT) -> float:
    """kappa_soot / f_v at wavelength lambda (1/m)."""
    return c_soot / (lambda_um * 1e-6)


def soot_planck_mean_per_fv_t(c_soot: float = C_SOOT) -> float:
    """Broadband Planck-mean kappa_soot / (f_v T) = 3.72 C / c2 (1/(m K))."""
    return 3.72 * c_soot / C2
