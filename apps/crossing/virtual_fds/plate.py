"""Virtual flux plate: FDS radiometer readings by distance, and the copper-plate calorimeter round trip.

SIMULATED. Three flux "truths" at a point ahead of the C064 head, facing the fire (-x), are compared:
(a) FDS gas-phase radiometers (RADIATIVE HEAT FLUX GAS, z = 1.5 m, y = 0, facing -x; x = 80, 90, 102, 105, 108 m;
    0.5 s output in research/kcf-heat/data/fds_rerun/C064_kcf_radiometers_devc.csv). A reading "at d" is the device
    value while the leading edge is d metres behind the device: d(t) = x_device - le(t), le(t) the 1 s leading-edge
    track of research/kcf-heat B.2 (the `le` of every sample in b2_fds_compare.json, 20 kW/m3 edge), linearly
    interpolated to the 0.5 s device times. Only the quasi-steady window 40-84 s and d >= 1 m are used (as B.2).
(b) the closed form (crossing.heat.closed_form_line_flux -> kcf-heat law.line_flux_s, s = d + D/2), C064 run-mean
    parameters, long front and finite front (half-width = mean effective width / 2).
(c) kcf_heat.voxel.voxel_flux on the 5 s volume (unattenuated voxel sum, chi * HRRPUV * dV, cosine, inverse square).

Plate round trip: the forward model is the energy balance that crossing.flux inverts,
    rho cp d dT/dt = alpha q(t) - [h (T - Ta) + eps sigma (T^4 - Ta^4)],
integrated with RK4 at 100 Hz (q linear between input samples), sampled at 10 Hz, plus Gaussian noise 0.12 C and
0.25 C quantisation (MAX31855 resolution), then fed to crossing.flux.FluxEstimator with the SAME loss model
(perfect cool-down calibration: the best case). The plate sees only the radiative flux given to it; convective
heating by hot gas reaching the plate is not included (the FDS gas temperature at the plate is reported beside it).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from crossing import _repo
from crossing.flux import C_TO_K, SIGMA, FluxEstimator, LossModel, PlateSpec

RADIOMETERS = {"RAD_X102": 102.0, "RAD_X105": 105.0, "RAD_X108": 108.0, "RAD_X080": 80.0, "RAD_X090": 90.0}
WINDOW_S = (40.0, 84.0)
RADIOMETER_Z_M = 1.5


def read_devc(path=_repo.C064_DEVC) -> Tuple[List[str], np.ndarray]:
    lines = open(path, "r", encoding="utf-8").read().splitlines()
    head = [h.strip() for h in lines[1].split(",")]
    a = np.array([[float(v) for v in l.split(",")] for l in lines[2:] if l.strip()])
    return head, a


def b2() -> dict:
    with open(_repo.B2_FDS_COMPARE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def le_track_b2(data: Optional[dict] = None) -> Tuple[np.ndarray, np.ndarray]:
    """(t, le) of the 1 s leading-edge track recorded in b2_fds_compare.json samples (20 kW/m3 edge)."""
    data = data or b2()
    tl = sorted({(round(s["t"], 4), s["le"]) for s in data["samples"]})
    t = np.array([a for a, _ in tl]); le = np.array([b for _, b in tl])
    return t, le


def radiometer_samples(head=None, a=None, t_le=None, le=None) -> List[dict]:
    """Every (device, t) with t in the window and d = x_dev - le(t) >= 1 m: {t, device, d, q}."""
    if head is None:
        head, a = read_devc()
    if t_le is None:
        t_le, le = le_track_b2()
    t = a[:, 0]
    sel = (t >= max(WINDOW_S[0], t_le[0])) & (t <= min(WINDOW_S[1], t_le[-1]))
    out = []
    for name, xr in RADIOMETERS.items():
        q = a[:, head.index(name)]
        for ti, qi in zip(t[sel], q[sel]):
            d = xr - float(np.interp(ti, t_le, le))
            if d >= 1.0:
                out.append({"t": float(ti), "device": name, "d": d, "q": float(qi)})
    return out


def radiometer_at(samples: Sequence[dict], d0: float, half_width: float = 2.0) -> dict:
    """Geometric mean, min, max and n of radiometer readings with |d - d0| <= half_width."""
    q = np.array([s["q"] for s in samples if abs(s["d"] - d0) <= half_width and s["q"] > 0])
    if q.size == 0:
        return {"d_m": d0, "n": 0, "geomean_kw_m2": None, "min_kw_m2": None, "max_kw_m2": None}
    return {"d_m": d0, "half_width_m": half_width, "n": int(q.size), "geomean_kw_m2": float(np.exp(np.log(q).mean())),
            "min_kw_m2": float(q.min()), "max_kw_m2": float(q.max()),
            "devices": sorted({s["device"] for s in samples if abs(s["d"] - d0) <= half_width})}


@dataclass
class PlateResult:
    t: np.ndarray            # 10 Hz sample times (s)
    q_true: np.ndarray       # input flux at the sample times (kW/m2)
    plate_true_c: np.ndarray
    plate_meas_c: np.ndarray
    q_est_t: np.ndarray      # FluxEstimator sample times (window centres)
    q_est: np.ndarray        # recovered incident flux (kW/m2), NaN where invalid


def simulate_plate(t_in: Sequence[float], q_in_kw_m2: Sequence[float], air_c: float = 32.0,
                   spec: PlateSpec = PlateSpec(), loss: Optional[LossModel] = None, fs_hz: float = 10.0,
                   noise_c: float = 0.12, quant_c: float = 0.25, seed: int = 0, t0_plate_c: Optional[float] = None,
                   window_s: float = 1.0) -> PlateResult:
    """Forward plate model + crossing.flux.FluxEstimator inversion (see module docstring)."""
    loss = loss or LossModel(h=12.0, eps=spec.emissivity, note="virtual_fds assumed loss model")
    t_in = np.asarray(t_in, dtype=float); q_in = np.asarray(q_in_kw_m2, dtype=float)
    ta = air_c + C_TO_K
    cap = spec.heat_capacity_j_m2_k

    def rhs(t, T):
        q = float(np.interp(t, t_in, q_in)) * 1000.0
        return (spec.absorptivity * q - (loss.h * (T - ta) + loss.eps * SIGMA * (T ** 4 - ta ** 4))) / cap

    dt = 0.01
    n = int(round((t_in[-1] - t_in[0]) / dt))
    T = (air_c if t0_plate_c is None else t0_plate_c) + C_TO_K
    every = int(round(1.0 / (fs_hz * dt)))
    ts, Ts = [], []
    t = float(t_in[0])
    for i in range(n + 1):
        if i % every == 0:
            ts.append(t); Ts.append(T)
        k1 = rhs(t, T); k2 = rhs(t + dt / 2, T + dt / 2 * k1); k3 = rhs(t + dt / 2, T + dt / 2 * k2)
        k4 = rhs(t + dt, T + dt * k3)
        T += dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        t += dt
    ts = np.array(ts); true_c = np.array(Ts) - C_TO_K
    rng = np.random.default_rng(seed)
    meas = np.round((true_c + rng.normal(0.0, noise_c, true_c.size)) / quant_c) * quant_c
    est = FluxEstimator(spec, loss, window_s=window_s)
    qt, qe = [], []
    for ti, yi in zip(ts, meas):
        s = est.update(ti, float(yi), air_c)
        qt.append(s.t); qe.append(s.q_kw_m2 if s.valid else np.nan)
    return PlateResult(t=ts, q_true=np.interp(ts, t_in, q_in), plate_true_c=true_c, plate_meas_c=meas,
                       q_est_t=np.array(qt), q_est=np.array(qe))


def recovered_at(res: PlateResult, t_c: float, half_s: float = 1.0) -> dict:
    """Mean recovered vs mean input flux within t_c +- half_s, and the per-sample rms error there."""
    m = (res.q_est_t >= t_c - half_s) & (res.q_est_t <= t_c + half_s) & np.isfinite(res.q_est)
    if not m.any():
        return {"t_s": t_c, "n": 0}
    q_true = np.interp(res.q_est_t[m], res.t, res.q_true)
    e = res.q_est[m] - q_true
    return {"t_s": t_c, "n": int(m.sum()), "q_input_kw_m2": float(q_true.mean()),
            "q_recovered_kw_m2": float(res.q_est[m].mean()), "rms_error_kw_m2": float(np.sqrt(np.mean(e ** 2))),
            "plate_c": float(np.interp(t_c, res.t, res.plate_true_c))}
