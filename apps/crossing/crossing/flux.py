"""Step 2: thin-skin calorimeter on the roof flux plate, and thermal dose units (DESIGN.md section 6.1).

Sensor: a blackened copper plate (default 1 mm thick) with a K thermocouple read by a MAX31855 (0.25 C resolution,
~10 Hz), plus the `tc_air` thermocouple for the surrounding air temperature.

Physics (lumped / thin-skin calorimeter), per unit exposed area A of the plate:

    rho * cp * d * dT/dt = alpha * q_inc - loss(T)
    loss(T) = h * (T - Ta) + eps * sigma * (T^4 - Ta^4)          [W/m2], T and Ta in K

    =>  q_inc = (rho * cp * d * dT/dt + loss(T)) / alpha          [W/m2]; reported in kW/m2

Assumptions (all stated, none verified on hardware yet):
- Lumped plate: the Biot number h*d/k is tiny for 1 mm copper (k ~ 390 W/m/K), so the plate is isothermal and the
  thermocouple reads the plate temperature. Thermocouple contact lag and lead conduction are neglected.
- rho, cp are constant (copper cp rises ~10 % from 20 C to 500 C; the error goes straight into q).
- `loss(T)` lumps every loss path (front-face convection and re-radiation, back-face losses through the insulation,
  conduction to the mount) into one effective h and eps fitted from a cool-down curve recorded on the vehicle.
  The fit is therefore only valid for the airflow it was recorded in: a moving vehicle or wind changes h.
- The surroundings radiate at the air temperature Ta (no hot background apart from the flux being measured). Fire
  radiation is the incident flux q_inc; convective heating by hot gas reaching the plate is NOT separated and
  appears in q_inc, so inside a flame q_inc is the total (radiative + convective) heat flux to a cold-ish surface.
- Absorptivity alpha of the black coating is grey (same for the fire spectrum and for the room-temperature
  surroundings). Placeholder 0.95 for a high-temperature matt black paint; real coatings degrade with heat.
- The derivative of a quantised (0.25 C) and noisy signal is the dominant error: with a 1 s window at 10 Hz
  the noise on dT/dt is of order 0.1 K/s, i.e. about 0.35 kW/m2 on q for the default plate. The estimate lags the
  input by half the derivative window (it is evaluated at the window centre).
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np

SIGMA = 5.670374419e-8          # Stefan-Boltzmann constant, W/m2/K4
C_TO_K = 273.15
T_MIN_C = -20.0                 # valid plate temperature range (DESIGN 6.1)
T_MAX_C = 1000.0
MAX_GAP_S = 0.5                 # a gap between plate samples longer than this invalidates the estimate


@dataclass(frozen=True)
class PlateSpec:
    """Flux plate. SI units: thickness m, rho kg/m3, cp J/kg/K, area m2. Defaults: 1 mm copper, 5 x 5 cm.

    `absorptivity` divides the absorbed flux to give incident flux; `emissivity` is the default re-radiation
    emissivity of the coating (fixed in the cool-down fit unless fit_eps=True).
    """
    thickness_m: float = 0.001
    rho: float = 8960.0
    cp: float = 385.0
    absorptivity: float = 0.95
    emissivity: float = 0.95
    area_m2: float = 0.0025

    @property
    def heat_capacity_j_m2_k(self) -> float:
        """rho * cp * d: stored energy per unit area per kelvin, J/m2/K."""
        return self.rho * self.cp * self.thickness_m


@dataclass
class LossModel:
    """loss(T) = h*(T-Ta) + eps*sigma*(T^4-Ta^4) in W/m2 (T, Ta in K), fitted from a cool-down curve.

    h: effective convective coefficient W/m2/K (all loss paths lumped); eps: effective emissivity;
    rms_residual_w_m2: rms of (rho*cp*d*dT/dt + loss) over the fit points; n: points used;
    t_range_c: (min, max) plate temperature covered by the fit, C. Outside that range the model is extrapolated.
    """
    h: float
    eps: float
    rms_residual_w_m2: float = float("nan")
    n: int = 0
    t_range_c: tuple = (float("nan"), float("nan"))
    note: str = ""

    def loss_w_m2(self, t_k, ta_k):
        t_k = np.asarray(t_k, dtype=float)
        ta_k = np.asarray(ta_k, dtype=float)
        return self.h * (t_k - ta_k) + self.eps * SIGMA * (t_k ** 4 - ta_k ** 4)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["t_range_c"] = list(self.t_range_c)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LossModel":
        return cls(h=float(d["h"]), eps=float(d["eps"]), rms_residual_w_m2=float(d.get("rms_residual_w_m2", "nan")),
                   n=int(d.get("n", 0)), t_range_c=tuple(d.get("t_range_c", (float("nan"), float("nan")))),
                   note=str(d.get("note", "")))

    def save(self, path) -> None:
        """Write `plate_loss.json`."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "LossModel":
        return cls.from_dict(json.loads(Path(path).read_text()))


def derivative(t, y, window_s: float = 1.0, order: int = 2) -> np.ndarray:
    """dy/dt by a local least-squares polynomial (Savitzky-Golay style, works on uneven sampling).

    For each sample i a polynomial of `order` is fitted to the samples with |t - t_i| <= window_s/2 and its slope at
    t_i is returned. NaN where fewer than order+2 samples fall in the window or the window is one-sided by more than
    half (near the ends of the record). Units: y-units per second.
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if t.shape != y.shape or t.ndim != 1:
        raise ValueError("t and y must be 1-D arrays of equal length")
    n = t.size
    out = np.full(n, np.nan)
    half = window_s / 2.0
    lo = np.searchsorted(t, t - half, side="left")
    hi = np.searchsorted(t, t + half, side="right")
    for i in range(n):
        a, b = lo[i], hi[i]
        if b - a < order + 2:
            continue
        tt = t[a:b] - t[i]
        if tt[0] > -0.5 * half or tt[-1] < 0.5 * half:      # too one-sided: skip (end effects)
            continue
        yy = y[a:b]
        if not np.all(np.isfinite(yy)):
            continue
        # Vandermonde in powers of (t - t_i); slope at t_i is the linear coefficient.
        V = np.vander(tt, order + 1, increasing=True)
        coef, *_ = np.linalg.lstsq(V, yy, rcond=None)
        out[i] = coef[1]
    return out


def fit_cooldown(t_s, plate_c, air_c, spec: PlateSpec = PlateSpec(), fit_eps: bool = False,
                 window_s: float = 5.0, min_excess_k: float = 5.0) -> LossModel:
    """Fit loss(T) from a cool-down record (no external flux: q_inc = 0 is ASSUMED during the record).

    Energy balance with q_inc = 0:  rho*cp*d*dT/dt = -loss(T). Linear least squares on
    y = -rho*cp*d*dT/dt  against  h*(T-Ta) [+ eps*sigma*(T^4-Ta^4)]. With fit_eps=False eps is fixed at
    spec.emissivity and only h is fitted. Points with T - Ta < min_excess_k are dropped (the derivative there is
    mostly quantisation noise). dT/dt uses `derivative` with `window_s` (longer than the online estimator because a
    cool-down is slow and the fit benefits from less noise).

    t_s: seconds (monotonic); plate_c, air_c: C (air may be a scalar or an array). Returns LossModel.
    Raises ValueError if fewer than 20 usable points remain.
    """
    t = np.asarray(t_s, dtype=float)
    tp = np.asarray(plate_c, dtype=float) + C_TO_K
    ta = np.broadcast_to(np.asarray(air_c, dtype=float) + C_TO_K, tp.shape).astype(float)
    m = spec.heat_capacity_j_m2_k
    dTdt = derivative(t, tp, window_s=window_s, order=2)
    ok = np.isfinite(dTdt) & np.isfinite(tp) & np.isfinite(ta) & ((tp - ta) >= min_excess_k)
    if ok.sum() < 20:
        raise ValueError(f"cool-down fit needs >= 20 usable points, got {int(ok.sum())}")
    y = -m * dTdt[ok]
    xc = tp[ok] - ta[ok]
    xr = SIGMA * (tp[ok] ** 4 - ta[ok] ** 4)
    if fit_eps:
        A = np.column_stack([xc, xr])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        h, eps = float(coef[0]), float(coef[1])
    else:
        eps = float(spec.emissivity)
        h = float(np.dot(xc, y - eps * xr) / np.dot(xc, xc))
    resid = y - (h * xc + eps * xr)
    return LossModel(h=h, eps=eps, rms_residual_w_m2=float(np.sqrt(np.mean(resid ** 2))), n=int(ok.sum()),
                     t_range_c=(float(tp[ok].min() - C_TO_K), float(tp[ok].max() - C_TO_K)),
                     note="fit_eps" if fit_eps else "eps fixed from PlateSpec")


@dataclass
class FluxSample:
    """One flux estimate. t: s (the centre of the derivative window, so it lags the newest sample by window/2);
    q_kw_m2: incident flux (divided by absorptivity); q_abs_kw_m2: absorbed flux; dTdt: K/s."""
    t: float
    q_kw_m2: float
    q_abs_kw_m2: float
    dTdt: float
    valid: bool
    reason: str = ""


class FluxEstimator:
    """Online incident-flux estimator: q = (rho*cp*d*dT/dt + loss(T)) / alpha / 1000 [kW/m2].

    `update(t_s, plate_c, air_c, fault=None)` takes one plate sample (C) and the latest air temperature (C).
    Invalid (valid=False, q NaN) when: the thermocouple reports a fault or a None/NaN value; the gap since the
    previous sample exceeds 0.5 s (the buffer restarts); time goes backwards; T is outside [-20, 1000] C; the air
    temperature is missing; or the buffer does not yet span the derivative window.
    """

    def __init__(self, spec: PlateSpec = PlateSpec(), loss: Optional[LossModel] = None,
                 window_s: float = 1.0, order: int = 2):
        self.spec = spec
        self.loss = loss if loss is not None else LossModel(h=10.0, eps=spec.emissivity, note="unfitted default")
        self.window_s = float(window_s)
        self.order = int(order)
        self._t: list = []
        self._y: list = []
        self._air: list = []

    def reset(self) -> None:
        self._t.clear(); self._y.clear(); self._air.clear()

    @staticmethod
    def _bad(t, reason) -> FluxSample:
        return FluxSample(t=float(t) if t is not None else float("nan"), q_kw_m2=float("nan"),
                          q_abs_kw_m2=float("nan"), dTdt=float("nan"), valid=False, reason=reason)

    def update(self, t_s: float, plate_c: Optional[float], air_c: Optional[float],
               fault: Optional[str] = None) -> FluxSample:
        if t_s is None or not math.isfinite(float(t_s)):
            self.reset()
            return self._bad(float("nan"), "bad time")
        t_s = float(t_s)
        if fault:
            self.reset()
            return self._bad(t_s, f"thermocouple fault: {fault}")
        if plate_c is None or not math.isfinite(float(plate_c)):
            self.reset()
            return self._bad(t_s, "plate temperature missing")
        plate_c = float(plate_c)
        if not (T_MIN_C <= plate_c <= T_MAX_C):
            self.reset()
            return self._bad(t_s, f"plate temperature {plate_c:.1f} C outside [{T_MIN_C}, {T_MAX_C}] C")
        if self._t:
            dt = t_s - self._t[-1]
            if dt <= 0:
                self.reset()
                self._push(t_s, plate_c, air_c)
                return self._bad(t_s, "time not increasing")
            if dt > MAX_GAP_S:
                self.reset()
                self._push(t_s, plate_c, air_c)
                return self._bad(t_s, f"gap {dt:.2f} s > {MAX_GAP_S} s")
        self._push(t_s, plate_c, air_c)
        # keep a full window behind the newest sample: drop the oldest sample only while the NEXT one still reaches
        # back to t_s - window, so a filled buffer always spans >= window (up to window + one sample interval).
        # (Dropping every sample older than the window left a span of window - dt .. window, and with a few ms of
        # timestamp jitter at 10 Hz about half the samples then failed the 0.95*window check below.)
        while len(self._t) >= 2 and self._t[1] <= t_s - self.window_s + 1e-9:
            self._t.pop(0); self._y.pop(0); self._air.pop(0)
        if self._t[-1] - self._t[0] < self.window_s * 0.95 or len(self._t) < self.order + 2:
            return self._bad(t_s, "filling derivative window")
        ta = self._air[len(self._air) // 2]
        if ta is None or not math.isfinite(ta):
            return self._bad(t_s, "air temperature missing")
        t = np.asarray(self._t)
        y = np.asarray(self._y) + C_TO_K
        tc = 0.5 * (t[0] + t[-1])
        V = np.vander(t - tc, self.order + 1, increasing=True)
        coef, *_ = np.linalg.lstsq(V, y, rcond=None)
        T_c = float(coef[0])
        dTdt = float(coef[1])
        loss = float(self.loss.loss_w_m2(T_c, ta + C_TO_K))
        q_abs = (self.spec.heat_capacity_j_m2_k * dTdt + loss) / 1000.0
        q_inc = q_abs / self.spec.absorptivity
        if not (math.isfinite(q_inc)):
            return self._bad(tc, "non-finite flux")
        return FluxSample(t=tc, q_kw_m2=q_inc, q_abs_kw_m2=q_abs, dTdt=dTdt, valid=True, reason="")

    def _push(self, t, y, air):
        self._t.append(t)
        self._y.append(y)
        self._air.append(None if air is None or not math.isfinite(float(air)) else float(air))


# --- Thermal dose ---------------------------------------------------------------------------------------------
# REIMPLEMENTED on purpose, identical to research/kcf-heat/kcf_heat/exposure.py::tdu. Importing exposure.py pulls
# in kcf_heat/closure.py and, through it, the repository root package, which the laptop app must not import
# (DESIGN.md section 0). Keep this one line in step with the reference: sum(q**(4/3)*dt for q in qs if q > q0).
def tdu(q_series_kw_m2: Iterable[float], dt: float = 1.0, q0: float = 0.0) -> float:
    """Thermal dose units, (kW/m2)^(4/3) s, counted only while q > q0. Same as kcf_heat.exposure.tdu."""
    return float(sum((q ** (4.0 / 3.0)) * dt for q in q_series_kw_m2 if q > q0))


@dataclass
class RunningDose:
    """Running TDU integrated sample by sample with the actual dt (rectangle rule on the newer sample).

    `add(t, q_kw_m2, valid=True)`: the interval since the previous accepted sample is credited with q**(4/3)*dt if
    q > q0. An invalid sample or a gap > max_gap_s is not integrated; it adds its duration to `uncounted_s` and sets
    `complete = False`, so a consumer can see the dose is a lower bound.
    """
    q0: float = 0.0
    max_gap_s: float = MAX_GAP_S
    dose_tdu: float = 0.0
    uncounted_s: float = 0.0
    complete: bool = True
    _t_prev: Optional[float] = field(default=None, repr=False)

    def add(self, t: float, q_kw_m2: float, valid: bool = True) -> float:
        t = float(t)
        if self._t_prev is not None:
            dt = t - self._t_prev
            if dt <= 0:
                return self.dose_tdu
            if not valid or q_kw_m2 is None or not math.isfinite(q_kw_m2) or dt > self.max_gap_s:
                self.uncounted_s += dt
                self.complete = False
            elif q_kw_m2 > self.q0:
                self.dose_tdu += (q_kw_m2 ** (4.0 / 3.0)) * dt
        self._t_prev = t
        return self.dose_tdu
