"""Bunsen-flame versions of the three heat curves compared in test A (see A_PLAN.md sections 2 and 4).

Everything here is a MODEL of a laboratory flame. Nothing is fitted to a measurement.

Geometry (all curves): burner axis = z axis, flame = a cylinder of diameter D and height L standing on z = 0.
The plate is a vertical disc of radius Rp whose centre is at height L/2 and horizontal distance r from the axis,
its normal pointing at the axis. r is the "burner axis to plate face" distance of the distance jig.

Every curve is LINEAR IN chi (the radiant fraction) and in Q (burner power). The functions therefore return the
flux for chi = 1 and the caller multiplies by chi. This is the central fact of A_PLAN.md section 4: a free chi
absorbs any level difference between curves, so only the SHAPE of q(r) can discriminate.

Curves
------
``closed_form``   crossing-app version of the kcf-heat line-source law: q = chi*I/(2 pi s) * a/sqrt(a^2+s^2), the
                  law's own function (research/kcf-heat law.line_flux_s, loaded by file path). Mapping: the flame is
                  a VERTICAL line of length L (a = L/2), I = Q/L, s = r, receiver at mid-height. ``closed_form_repo``
                  is the mapping in the older a_flux_analyse (a = D/2, I = Q/D); it collapses onto the point source.
``voxel_sum``     what the kcf-heat voxel sum does to an HRR field (inverse square, receiver cosine, no absorption),
                  applied to a uniform emitting cylinder.
``fds_fit_transfer``  the voxel sum with the Beer-Lambert factor exp(-(kf*L_flame + ka*r)) fitted to FDS's radiometers
                  on C064 (research/kcf-heat b2_absorption_fit.jsonl: kf = 0.3 /m, ka = 0.03 /m), applied UNCHANGED.
                  This is NOT a scaling of the FDS radiometer curve (that cannot be scaled, A_PLAN.md 2.3); it is the
                  only statement the fit makes at another size, and it gives ~ the voxel sum.
``point``         chi*Q/(4 pi r^2), reference only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, Iterable, Sequence

import numpy as np

from .common import APP  # noqa: F401  (puts apps/crossing on sys.path)

KAPPA_FLAME_FIT = 0.3      # 1/m, b2_absorption_fit.jsonl best row (interpretation of FDS, UNVERIFIED)
KAPPA_PATH_FIT = 0.03      # 1/m, same row


@dataclass(frozen=True)
class Flame:
    q_kw: float                    # burner power, kW (flow x LHV x efficiency)
    height_m: float = 0.12         # L, visible flame height (photo)
    diameter_m: float = 0.02       # D, visible flame width (photo)
    plate_radius_m: float = 0.015  # 30 mm disc
    plate_z_m: float | None = None  # plate centre height; default L/2
    z_source_shift_m: float = 0.0  # sensitivity: emission centroid shifted by this much (m) along z

    @property
    def z0(self) -> float:
        return self.height_m / 2.0 if self.plate_z_m is None else self.plate_z_m


def power_kw(flow_l_min: float, lhv_mj_m3: float, efficiency: float = 1.0) -> float:
    """Q = flow x LHV x efficiency in kW (flow in L/min referred to the LHV's conditions)."""
    return flow_l_min / 1000.0 / 60.0 * lhv_mj_m3 * 1000.0 * efficiency


# ------------------------------------------------------------------------------------------ quadrature
def _plate_nodes(rp: float, nr: int = 4, nth: int = 12):
    """Equal-area ring quadrature on the disc: returns (dy, dz) arrays (m) with equal weights."""
    if rp <= 0:
        return np.zeros(1), np.zeros(1)
    rr = rp * np.sqrt((np.arange(nr) + 0.5) / nr)
    th = (np.arange(nth) + 0.5) * 2 * np.pi / nth
    R, T = np.meshgrid(rr, th, indexing="ij")
    return (R * np.cos(T)).ravel(), (R * np.sin(T)).ravel()


def _cyl_nodes(rad: float, height: float, nr: int = 4, nth: int = 12, nz: int = 24, shift: float = 0.0):
    """Midpoint nodes of a uniform cylinder, equal weights."""
    rr = rad * np.sqrt((np.arange(nr) + 0.5) / nr) if rad > 0 else np.zeros(1)
    th = (np.arange(nth) + 0.5) * 2 * np.pi / nth
    zz = (np.arange(nz) + 0.5) * height / nz + shift
    R, T, Z = np.meshgrid(rr, th, zz, indexing="ij")
    return (R * np.cos(T)).ravel(), (R * np.sin(T)).ravel(), Z.ravel()


def _chord_to_surface(ex, ey, px, py, rad):
    """Length from an emitter inside the cylinder (ex, ey) towards the receiver (px, py) to the cylinder wall,
    as a fraction of the emitter-receiver ray (horizontal projection), so the 3-D length is frac * r3d."""
    dx, dy = px - ex, py - ey
    a = dx * dx + dy * dy
    b = 2 * (ex * dx + ey * dy)
    c = ex * ex + ey * ey - rad * rad
    disc = np.maximum(b * b - 4 * a * c, 0.0)
    return np.clip((-b + np.sqrt(disc)) / (2 * a), 0.0, 1.0)


def _sum_curve(flame: Flame, r: float, mode: str, kf: float = 0.0, ka: float = 0.0, point: bool = False) -> float:
    """Disc-averaged flux (kW/m2) for chi = 1: sum of emitters Q/N * cos / (4 pi rho^2) [* attenuation]."""
    L, rad = flame.height_m, flame.diameter_m / 2.0
    if point:
        ex = np.zeros(1); ey = np.zeros(1); ez = np.full(1, L / 2.0 + flame.z_source_shift_m)
    elif mode == "line":
        ex = np.zeros(48); ey = np.zeros(48)
        ez = (np.arange(48) + 0.5) * L / 48 + flame.z_source_shift_m
    else:
        ex, ey, ez = _cyl_nodes(rad, L, shift=flame.z_source_shift_m)
    dy, dz = _plate_nodes(flame.plate_radius_m)
    PX = r
    total = 0.0
    for yy, zz in zip(dy, dz):
        rx, ry, rz = PX - ex, yy - ey, (flame.z0 + zz) - ez
        rho2 = rx * rx + ry * ry + rz * rz
        rho = np.sqrt(rho2)
        cos = np.clip(rx / rho, 0.0, None)          # plate normal points to -x; emitter at smaller x
        val = cos / (4 * np.pi * rho2)
        if kf or ka:
            frac = _chord_to_surface(ex, ey, PX, yy, rad)
            val = val * np.exp(-(kf * frac * rho + ka * rho))
        total += float(np.mean(val))
    return flame.q_kw * total / len(dy)


def point(r: float, flame: Flame) -> float:
    return _sum_curve(flame, r, "point", point=True)


def voxel_sum(r: float, flame: Flame) -> float:
    return _sum_curve(flame, r, "cyl")


def fds_fit_transfer(r: float, flame: Flame, kf: float = KAPPA_FLAME_FIT, ka: float = KAPPA_PATH_FIT) -> float:
    return _sum_curve(flame, r, "cyl", kf=kf, ka=ka)


def _law():
    from crossing import _repo
    return _repo.kcf_law()


def closed_form(r: float, flame: Flame) -> float:
    """kcf-heat law at the plate centre (vertical line of length L, receiver at mid-height) times the disc-average
    factor of the same thin line, so the finite 30 mm plate is treated like the other curves."""
    L = flame.height_m
    centre = float(_law().line_flux_s(r, 1.0, flame.q_kw / L, L / 2.0))
    thin_centre = _thin_line_centre(r, flame)
    thin_disc = _sum_curve(flame, r, "line")
    return centre * (thin_disc / thin_centre)


def _thin_line_centre(r: float, flame: Flame) -> float:
    """Numerical flux of the thin line at the plate centre (no disc average): equals the law's closed form when
    the plate is at mid-height (checked in the tests)."""
    return _sum_curve(replace(flame, plate_radius_m=0.0), r, "line")


def closed_form_repo(r: float, flame: Flame) -> float:
    """Mapping of the older a_flux_analyse: depth D, half-width a = D/2, I = Q/D, s = r (collapses to the point
    source for r >> D). Centre-point value, no disc average."""
    D = flame.diameter_m
    return float(_law().line_flux_s(r, 1.0, flame.q_kw / D, D / 2.0))


CURVES = {
    "closed_form": closed_form,
    "voxel_sum": voxel_sum,
    "fds_fit_transfer": fds_fit_transfer,
    "point": point,
    "closed_form_repo": closed_form_repo,
}
PRIMARY = ("closed_form", "voxel_sum", "fds_fit_transfer")


def curves(rs: Iterable[float], flame: Flame, names: Sequence[str] = tuple(CURVES)) -> Dict[str, np.ndarray]:
    """{name: flux for chi = 1 (kW/m2) at each r}."""
    rs = list(rs)
    return {n: np.array([CURVES[n](r, flame) for r in rs]) for n in names}


def local_exponent(fn, r: float, flame: Flame, h: float = 0.02) -> float:
    """-d ln q / d ln r by central difference."""
    lo, hi = r * (1 - h), r * (1 + h)
    return -(math.log(fn(hi, flame)) - math.log(fn(lo, flame))) / (math.log(hi) - math.log(lo))


# ------------------------------------------------------------------------------------ design calculations
def shape_separation(rs: Sequence[float], flame: Flame, a: str, b: str, sigma_ln: float) -> Dict[str, float]:
    """How far apart two curves are in SHAPE (chi free) for measurements with independent log-error sigma_ln at each
    distance: the chi-free chi^2 distance d2 = sum (delta_i - mean(delta))^2 / sigma^2, delta_i = ln(qa_i/qb_i).
    sqrt(d2) is the number of sigma at which one curve (with its best chi) is told from the other; 3 is the usual
    pre-registered threshold. Also returns the largest log difference after the best common factor."""
    qa = np.array([CURVES[a](r, flame) for r in rs]); qb = np.array([CURVES[b](r, flame) for r in rs])
    d = np.log(qa / qb)
    dev = d - d.mean()
    return {"sqrt_d2_sigma": float(math.sqrt(np.sum(dev ** 2)) / sigma_ln),
            "max_shape_diff_pct": float(100 * (np.exp(np.max(np.abs(dev))) - 1)),
            "level_ratio": float(np.exp(d.mean()))}


def optical_depth_fit(path_m: float, flame_depth_m: float) -> float:
    """Optical depth the fitted FDS absorption (kf, ka) assigns to a flame zone of depth D seen across a path r."""
    return KAPPA_FLAME_FIT * flame_depth_m + KAPPA_PATH_FIT * path_m
