"""Step 6: verdict state machine (DESIGN.md section 8). Verdicts are ADVISORY for trained crews.

States: CLOSED (default), CROSS FAST, SPRAY THEN RE-CHECK, REOPENED. Every limit used here (vehicle dose limit,
max safe speed, intake air limit, spray margin, reopen hold, reopen flux) is a PLACEHOLDER for a fire service to
set. Nothing here has been validated on a real fire.

Fail closed: missing, stale, frozen, faulted, non-finite or out-of-range input, link loss, inputs older than
verdict_ttl_s, or a verdict older than verdict_ttl_s (``effective``) give CLOSED. Every CLOSED carries
machine-readable reason codes ("CODE" or "CODE:detail").

Every sensor of the unit (thermal, radar, tc_plate, tc_housing, tc_air, imu, gnss, pi) is REQUIRED for EVERY go
verdict (CROSS FAST, SPRAY THEN RE-CHECK, REOPENED): any single sensor not fresh (reading or Pi heartbeat older
than 2 s, frozen, Pi status not "ok"), missing, faulted or delivering a malformed value gives CLOSED
(orchestrator decision D1, 2026-11-17; earlier builds let REOPENED ignore radar/tc_air and every verdict ignore
tc_housing/pi).

Extra go conditions (as built 2026-11-17):
- CROSS FAST / SPRAY need the fused FLAME (thermal flame at the path bearing AND radar FLAME_EFFECT) to have held
  continuously for ``min_flame_evidence_s`` (3.0 s, placeholder; FLAME_EVIDENCE_TOO_SHORT) and the flame base to be
  observed in the image (``near_edge_observed``; a base cut off by the image bottom or side, or hidden behind
  terrain (geometry ``occluded``), gives NEAR_EDGE_NOT_OBSERVED).
- REOPENED needs the recorded crossing to be in the camera's current view (``crossing_in_view``, computed by the
  pipeline from GNSS position + heading; otherwise REOPEN_CROSSING_NOT_IN_VIEW: the crew must face the crossed
  road), the vehicle stopped or slow (``reopen_max_speed_m_s``), and zero flame-temperature pixels in the image
  columns covering the crossing (``crossing_hot_pixels``), all held for reopen_hold_s (``ReopenTracker``).

Dose model (closed form, kcf-heat law; see heat.py). At constant speed v [m/s]:
    time_in_flame = (depth_hi + vehicle.length_m) / v                                     [s]
      depth_hi = depth_hi_for_decision(depth) = depth.hi_decision_m (DEPTH-HI rule, depth.py: >= the largest
      valid non-experimental estimator upper end), not the displayed combined hi_m
    q_in  = chi * I_hi / (pi * depth_lo)                                                  [kW/m2]
    TDU(v) = q_in^(4/3) * time_in_flame + 2 * integral_0^approach_m q(d)^(4/3) dd / v      [(kW/m2)^(4/3) s]
with q(d) = chi * I_hi / (2 pi (d + depth_lo/2)) (approach and exit legs, symmetric) and only q > q0 counted
(same rule as kcf_heat.exposure.tdu). Conservative: time uses the depth UPPER end, flux the depth LOWER end and
the intensity UPPER end. Assumes the crew sees the flux the roof plate would see (no cab shielding model), a
straight crossing at constant speed, steady front, no water effect (SPRAY has no water model). The FDS C064
reference dose is computed the same way from heat.fds_reference and reported, never used to decide.
"""
from __future__ import annotations

import math
import numbers
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from . import heat
from .vehicles import Vehicle, from_mapping as _vehicle_from_mapping

CLOSED = "CLOSED"
CROSS_FAST = "CROSS FAST"
SPRAY = "SPRAY THEN RE-CHECK"
REOPENED = "REOPENED"
GO_STATES = (CROSS_FAST, SPRAY, REOPENED)

ALL_SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")
# D1 (2026-11-17): every sensor is required for every go verdict. The two names are kept for callers.
REQUIRED_CROSS = ALL_SENSORS
REQUIRED_REOPEN = ALL_SENSORS
FLAME_STATES = ("FLAME", "NO_FLAME", "UNKNOWN")
RADAR_STATES = ("FLAME_EFFECT", "NO_EFFECT", "UNKNOWN")
FUTURE_TOL_S = 0.5            # an input stamped later than now + this is malformed (laptop clock)
AGE_ROUNDING_TOL_S = 1e-3     # a health age this far below 0 is float rounding (same-instant receipt), not future
MAX_THERMAL_PIXELS = 256 * 192
# A tc_plate fault string starting with this code (set by the pipeline when the plate thermocouple reads >= the
# user-set flux.disc_max_c, 70 C: the copper disc sits on printed PETG tabs) also adds this reason code.
PLATE_DISC_OVER_TEMP = "PLATE_DISC_OVER_TEMP"


@dataclass
class DecisionConfig:
    """Global decision settings (DESIGN 8). All PLACEHOLDERS for a fire service to set."""
    stale_s: float = 2.0
    verdict_ttl_s: float = 5.0
    spray_margin: float = 0.25
    reopen_hold_s: float = 30.0
    reopen_flux_kw_m2: float = 1.0
    reopen_hot_pixels: int = 0
    q0_kw_m2: float = 0.0
    approach_m: float = 30.0
    min_flame_evidence_s: float = 3.0          # FLAME must have held this long before CROSS FAST / SPRAY
    reopen_max_speed_m_s: float = 1.0          # REOPENED only with the vehicle stopped or slow (GNSS speed)
    chi: float = heat.DEFAULT_CHI
    half_width_m: Optional[float] = None       # finite front half-width for the legs; None = long front
    speed_resolution_m_s: float = 0.1
    leg_points: int = 400


def coerce_config(cfg: Any = None) -> DecisionConfig:
    """DecisionConfig from None, a DecisionConfig, a mapping, or any object with matching attributes."""
    if isinstance(cfg, DecisionConfig):
        return cfg
    out = DecisionConfig()
    if cfg is None:
        return out
    for f in fields(DecisionConfig):
        if isinstance(cfg, Mapping):
            if f.name in cfg:
                setattr(out, f.name, cfg[f.name])
        elif hasattr(cfg, f.name):
            setattr(out, f.name, getattr(cfg, f.name))
    return out


def coerce_vehicle(vehicle: Any) -> Vehicle:
    if isinstance(vehicle, Vehicle):
        return vehicle
    if isinstance(vehicle, Mapping):
        return _vehicle_from_mapping(str(vehicle.get("name", "custom")), dict(vehicle))
    raise TypeError("vehicle must be a vehicles.Vehicle or a mapping")


@dataclass
class DecisionInputs:
    """Everything one decision uses. Times are laptop time.monotonic() seconds at receipt.

    health: sensor -> {"fresh": bool, "reason": str, "age_s": float} (link.Health snapshot), or sensor -> bool.
      Only ``fresh is True`` counts as fresh; a missing sensor is not fresh.
    faults: sensor -> fault string or None (e.g. MAX31855 "open"); any fault on a required sensor closes.
    input_times: sensor -> receipt time of the latest reading the inputs were derived from.
    flame_status: fused "FLAME"/"NO_FLAME"/"UNKNOWN"; radar_status: "FLAME_EFFECT"/"NO_EFFECT"/"UNKNOWN".
    near_edge_m / far_echo_m: near flame edge and first solid echo beyond it [m].
    depth: depth.DepthResult; intensity: depth.IntensityResult.
    tc_air_c / tc_plate_c / tc_housing_c [deg C]; plate_flux_kw_m2 [kW/m2]; flame_pixels (thermal pixels at flame
    temperature); imu_roll_deg / imu_pitch_deg; gnss_fix (0/1/2), lat, lon, utc, speed_m_s.
    passed: the GNSS track went past the far edge / recorded flame location (see ``has_passed``).
    reopen_quiet_s: how long the reopen conditions have held continuously (``ReopenTracker``).
    flame_held_s: how long the fused status has been FLAME continuously (``HoldTracker``); None = unknown.
    near_edge_observed: True only when the flame base on the path is inside the image (not cut off by the bottom
      row or the image side) and not occluded by terrain; None/False closes CROSS FAST / SPRAY
      (NEAR_EDGE_NOT_OBSERVED).
    crossing_in_view: True only when the recorded crossing lies inside the camera's current view (pipeline);
      crossing_view_reason says why not. crossing_hot_pixels: flame-temperature pixels in the image columns
      covering the crossing.
    """
    link_up: bool = False
    health: Any = field(default_factory=dict)
    faults: Mapping[str, Optional[str]] = field(default_factory=dict)
    input_times: Mapping[str, float] = field(default_factory=dict)
    flame_status: Optional[str] = None
    radar_status: Optional[str] = None
    near_edge_m: Optional[float] = None
    far_echo_m: Optional[float] = None
    depth: Any = None
    intensity: Any = None
    tc_air_c: Optional[float] = None
    tc_plate_c: Optional[float] = None
    tc_housing_c: Optional[float] = None
    plate_flux_kw_m2: Optional[float] = None
    flame_pixels: Optional[int] = None
    imu_roll_deg: Optional[float] = None
    imu_pitch_deg: Optional[float] = None
    gnss_fix: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    utc: Optional[str] = None
    speed_m_s: Optional[float] = None
    passed: bool = False
    reopen_quiet_s: Optional[float] = None
    flame_held_s: Optional[float] = None
    near_edge_observed: Optional[bool] = None
    crossing_in_view: Optional[bool] = None
    crossing_view_reason: str = ""
    crossing_hot_pixels: Optional[int] = None
    sim: bool = False


@dataclass
class Verdict:
    state: str
    reasons: List[str]
    issued_mono: float
    expires_mono: float
    min_speed_m_s: Optional[float] = None
    time_in_flame_s: Optional[float] = None
    dose_tdu: Optional[float] = None
    dose_limit_tdu: Optional[float] = None
    dose_fds_ref_tdu: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    verdict_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    advisory: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------------------------------- helpers
def _num(v) -> bool:
    """Finite real number (numpy scalars included, bool excluded)."""
    return isinstance(v, numbers.Real) and not isinstance(v, (bool, np.bool_)) and math.isfinite(float(v))


def _health_map(health) -> Dict[str, Any]:
    if health is None:
        return {}
    if isinstance(health, Mapping):
        return dict(health)
    for attr in ("as_dict", "to_dict"):
        f = getattr(health, attr, None)
        if callable(f):
            try:
                d = f()
            except Exception:  # noqa: BLE001 - a broken health object means not fresh
                return {}
            if isinstance(d, Mapping):
                return dict(d)
    s = getattr(health, "sensors", None)
    return dict(s) if isinstance(s, Mapping) else {}


def _fresh(hmap: Mapping[str, Any], sensor: str, stale_s: float) -> Tuple[bool, str]:
    h = hmap.get(sensor)
    if h is None:
        return False, "missing"
    if isinstance(h, bool):
        return h, "" if h else "not fresh"
    fresh = h.get("fresh") if isinstance(h, Mapping) else getattr(h, "fresh", None)
    reason = (h.get("reason") if isinstance(h, Mapping) else getattr(h, "reason", "")) or ""
    age = h.get("age_s") if isinstance(h, Mapping) else getattr(h, "age_s", None)
    if fresh is not True:
        return False, str(reason or "not fresh")
    # D6: an age a hair below zero is float rounding of a same-instant receipt (tolerated down to -1e-3 s); a
    # clearly future time is malformed and not fresh.
    if age is not None and not (_num(age) and -AGE_ROUNDING_TOL_S <= age <= stale_s):
        return False, "age %r" % (age,)
    return True, ""


def _sensor_checks(inp: DecisionInputs, required: Sequence[str], cfg: DecisionConfig, now: float) -> List[str]:
    out: List[str] = []
    hmap = _health_map(inp.health)
    faults = inp.faults if isinstance(inp.faults, Mapping) else {}
    times = inp.input_times if isinstance(inp.input_times, Mapping) else {}
    for s in required:
        ok, why = _fresh(hmap, s, cfg.stale_s)
        if not ok:
            out.append("SENSOR_NOT_FRESH:%s" % s)
        if faults.get(s):
            out.append("SENSOR_FAULT:%s" % s)
            if str(faults[s]).startswith(PLATE_DISC_OVER_TEMP):
                out.append(PLATE_DISC_OVER_TEMP)
        t = times.get(s)
        if t is None:
            out.append("INPUT_TIME_MISSING:%s" % s)
        elif not _num(t):
            out.append("VALUE_INVALID:input_time.%s" % s)
        elif now - t > cfg.verdict_ttl_s:
            out.append("INPUT_TOO_OLD:%s" % s)
        elif t > now + FUTURE_TOL_S:
            out.append("INPUT_TIME_IN_FUTURE:%s" % s)
    return out


# (field, lo, hi): a present value outside this range (or non-finite) is malformed input.
_RANGES = (("tc_air_c", -40.0, 1000.0), ("tc_plate_c", -40.0, 1100.0), ("tc_housing_c", -40.0, 300.0),
           ("plate_flux_kw_m2", -50.0, 500.0), ("near_edge_m", 0.0, 500.0), ("far_echo_m", 0.0, 500.0),
           ("imu_roll_deg", -45.0, 45.0), ("imu_pitch_deg", -45.0, 45.0), ("lat", -90.0, 90.0),
           ("lon", -180.0, 180.0), ("speed_m_s", 0.0, 100.0), ("reopen_quiet_s", 0.0, 1e7),
           ("flame_held_s", 0.0, 1e7))


def _value_checks(inp: DecisionInputs) -> List[str]:
    out = []
    for name, lo, hi in _RANGES:
        v = getattr(inp, name)
        if v is None:
            continue
        if not (_num(v) and lo <= v <= hi):
            out.append("VALUE_INVALID:%s" % name)
    for name in ("flame_pixels", "crossing_hot_pixels"):
        fp = getattr(inp, name)
        if fp is not None and not (_num(fp) and float(fp).is_integer() and 0 <= fp <= MAX_THERMAL_PIXELS):
            out.append("VALUE_INVALID:%s" % name)
    if inp.gnss_fix is not None and not (_num(inp.gnss_fix) and inp.gnss_fix in (0, 1, 2)):
        out.append("VALUE_INVALID:gnss_fix")
    if inp.flame_status is not None and inp.flame_status not in FLAME_STATES:
        out.append("VALUE_INVALID:flame_status")
    if inp.radar_status is not None and inp.radar_status not in RADAR_STATES:
        out.append("VALUE_INVALID:radar_status")
    if not isinstance(inp.passed, bool):
        out.append("VALUE_INVALID:passed")
    for name in ("near_edge_observed", "crossing_in_view"):
        if getattr(inp, name) is not None and not isinstance(getattr(inp, name), bool):
            out.append("VALUE_INVALID:%s" % name)
    return out


def _require(inp: DecisionInputs, names: Sequence[str]) -> List[str]:
    return ["VALUE_MISSING:%s" % n for n in names if getattr(inp, n) is None]


def depth_hi_for_decision(d) -> Optional[float]:
    """Depth upper end the dose uses: ``hi_decision_m`` (depth.combine, DEPTH-HI rule: >= the largest upper end of
    the valid non-experimental estimators) when the object carries one, else ``hi_m`` (an object built without it,
    e.g. a hand-made DepthResult). The displayed combined interval hi_m is NOT used when hi_decision_m exists."""
    hd = getattr(d, "hi_decision_m", None)
    return hd if hd is not None else getattr(d, "hi_m", None)


def _depth_ok(d) -> bool:
    if d is None or getattr(d, "valid", False) is not True:
        return False
    v, lo, hi = getattr(d, "depth_m", None), getattr(d, "lo_m", None), getattr(d, "hi_m", None)
    hd = depth_hi_for_decision(d)
    return all(_num(x) for x in (v, lo, hi, hd)) and 0 < lo <= v <= hi <= 1000.0 and v <= hd <= 1000.0


def _intensity_ok(i) -> bool:
    if i is None or getattr(i, "valid", False) is not True:
        return False
    v, hi = getattr(i, "i_kw_m", None), getattr(i, "hi", None)
    return _num(v) and _num(hi) and 0 < v <= hi <= 1e6


# ------------------------------------------------------------------------------------------------------- dose
@dataclass
class DoseModel:
    """Dose(v) = k_tdu_m / v. All conservative ends already applied."""
    depth_lo_m: float
    depth_hi_m: float
    intensity_hi_kw_m: float
    length_m: float
    q_in_kw_m2: float
    in_flame_rate: float          # q_in^(4/3) if q_in > q0 else 0     [(kW/m2)^(4/3)]
    leg_integral: float           # integral_0^A q(d)^(4/3) dd          [(kW/m2)^(4/3) m], one leg
    q_in_fds_kw_m2: float
    in_flame_rate_fds: float
    leg_integral_fds: float

    def time_in_flame(self, v: float) -> float:
        return (self.depth_hi_m + self.length_m) / v

    def dose(self, v: float) -> float:
        return (self.in_flame_rate * (self.depth_hi_m + self.length_m) + 2.0 * self.leg_integral) / v

    def dose_fds_ref(self, v: float) -> float:
        return (self.in_flame_rate_fds * (self.depth_hi_m + self.length_m) + 2.0 * self.leg_integral_fds) / v


def _leg_integral(flux_of_d, approach_m: float, q0: float, n: int) -> float:
    """Trapezoid of q(d)^(4/3) (q > q0 only) over d in [0, approach_m], grid dense near the flame."""
    if approach_m <= 0:
        return 0.0
    n = max(int(n), 20)
    ds = [approach_m * (k / n) ** 2 for k in range(n + 1)]
    vals = []
    for d in ds:
        q = flux_of_d(d)
        vals.append(q ** (4.0 / 3.0) if q > q0 else 0.0)
    return sum(0.5 * (vals[k] + vals[k + 1]) * (ds[k + 1] - ds[k]) for k in range(n))


def dose_model(depth_lo_m: float, depth_hi_m: float, intensity_hi_kw_m: float, length_m: float,
               cfg: Optional[DecisionConfig] = None) -> DoseModel:
    cfg = coerce_config(cfg)
    q_in = heat.in_flame_flux(depth_lo_m, intensity_hi_kw_m, cfg.chi)
    rate = q_in ** (4.0 / 3.0) if q_in > cfg.q0_kw_m2 else 0.0
    leg = _leg_integral(lambda d: heat.closed_form_line_flux(d, depth_lo_m, intensity_hi_kw_m, cfg.chi,
                                                             cfg.half_width_m),
                        cfg.approach_m, cfg.q0_kw_m2, cfg.leg_points)
    q_fds = heat.fds_in_flame_reference(intensity_hi_kw_m).q_kw_m2
    rate_fds = q_fds ** (4.0 / 3.0) if q_fds > cfg.q0_kw_m2 else 0.0
    leg_fds = _leg_integral(lambda d: heat.fds_reference(d, intensity_hi_kw_m).q_kw_m2, cfg.approach_m,
                            cfg.q0_kw_m2, cfg.leg_points)
    return DoseModel(depth_lo_m, depth_hi_m, intensity_hi_kw_m, length_m, q_in, rate, leg, q_fds, rate_fds,
                     leg_fds)


def min_speed(dose_fn, limit: float, v_max: float, resolution: float = 0.1) -> Optional[float]:
    """Smallest v <= v_max with dose_fn(v) <= limit (dose decreasing in v): bisection, rounded UP to resolution.

    Returns None when even v_max exceeds the limit. The rounded value is capped at v_max (still admissible).
    """
    if not (dose_fn(v_max) <= limit):
        return None
    lo, hi = 0.0, float(v_max)              # dose(lo) = inf > limit, dose(hi) <= limit
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if mid <= 0:
            break
        if dose_fn(mid) <= limit:
            hi = mid
        else:
            lo = mid
        if hi - lo < resolution * 1e-3:
            break
    v = math.ceil(hi / resolution - 1e-9) * resolution
    v = round(max(v, resolution), 6)
    while v < v_max and not (dose_fn(v) <= limit):     # guard against float rounding
        v = round(v + resolution, 6)
    return min(v, float(v_max))


# ----------------------------------------------------------------------------------------------------- decide
def _closed(reasons: List[str], now: float, cfg: DecisionConfig, **kw) -> Verdict:
    seen, rs = set(), []
    for r in reasons or ["UNSPECIFIED"]:
        if r not in seen:
            seen.add(r)
            rs.append(r)
    return Verdict(CLOSED, rs, now, now + cfg.verdict_ttl_s, **kw)


def decide(inputs: DecisionInputs, vehicle: Any, cfg: Any = None, now: Optional[float] = None) -> Verdict:
    """One verdict from one snapshot of inputs (DESIGN 8 order). Never raises on bad input: CLOSED instead."""
    try:
        c = coerce_config(cfg)
    except Exception:  # noqa: BLE001
        c = DecisionConfig()
    if now is None:
        now = time.monotonic()
    if not _num(now):
        return Verdict(CLOSED, ["VALUE_INVALID:now"], 0.0, 0.0)
    try:
        veh = coerce_vehicle(vehicle)
    except Exception:  # noqa: BLE001
        return _closed(["VEHICLE_INVALID"], now, c)
    if not isinstance(inputs, DecisionInputs):
        return _closed(["INPUTS_MALFORMED"], now, c)
    try:
        return _decide(inputs, veh, c, float(now))
    except Exception as exc:  # noqa: BLE001 - any unexpected failure is CLOSED, never a go state
        return _closed(["INTERNAL_ERROR:%s" % type(exc).__name__], now, c)


def _decide(inp: DecisionInputs, veh: Vehicle, c: DecisionConfig, now: float) -> Verdict:
    base: List[str] = []
    if inp.link_up is not True:
        base.append("LINK_DOWN")
    base += _value_checks(inp)
    if _num(inp.tc_air_c) and inp.tc_air_c > veh.intake_air_limit_c:
        base.append("INTAKE_AIR_OVER_LIMIT")
    details: Dict[str, Any] = {"vehicle": veh.name, "placeholder_limits": veh.placeholder, "sim": bool(inp.sim)}
    if base:
        return _closed(base, now, c, dose_limit_tdu=veh.dose_limit_tdu, details=details)

    # ---- crossing path (CROSS FAST / SPRAY THEN RE-CHECK)
    cross = _sensor_checks(inp, REQUIRED_CROSS, c, now)
    cross += _require(inp, ("tc_air_c", "tc_plate_c", "tc_housing_c", "flame_pixels", "imu_roll_deg",
                            "imu_pitch_deg"))
    if inp.radar_status is None or inp.radar_status == "UNKNOWN":
        cross.append("RADAR_UNKNOWN")
    if inp.flame_status != "FLAME":
        cross.append("FLAME_UNKNOWN" if inp.flame_status in (None, "UNKNOWN") else "FLAME_NOT_CONFIRMED")
    elif inp.radar_status != "FLAME_EFFECT":
        cross.append("FLAME_RADAR_INCONSISTENT")
    elif not (_num(inp.flame_held_s) and inp.flame_held_s >= c.min_flame_evidence_s):
        cross.append("FLAME_EVIDENCE_TOO_SHORT")
    if inp.near_edge_observed is False or (inp.near_edge_observed is not True and _num(inp.near_edge_m)):
        cross.append("NEAR_EDGE_NOT_OBSERVED")
    elif inp.near_edge_observed is not True:
        cross.append("NO_NEAR_EDGE")
    if not (_num(inp.near_edge_m) and _num(inp.far_echo_m) and inp.far_echo_m > inp.near_edge_m):
        cross.append("NO_FAR_ECHO")
    if not (_num(inp.gnss_fix) and inp.gnss_fix >= 1 and _num(inp.lat) and _num(inp.lon)):
        cross.append("GNSS_NO_FIX")
    if not _depth_ok(inp.depth):
        cross.append("DEPTH_INVALID")
    if not _intensity_ok(inp.intensity):
        cross.append("INTENSITY_INVALID")

    out_kw: Dict[str, Any] = {"dose_limit_tdu": veh.dose_limit_tdu}
    if not cross:
        dm = dose_model(inp.depth.lo_m, depth_hi_for_decision(inp.depth), inp.intensity.hi, veh.length_m, c)
        vmax = veh.max_safe_speed_m_s
        d_max = dm.dose(vmax)
        details.update({"depth_hi_combined_m": inp.depth.hi_m,
                        "depth_hi_from": getattr(inp.depth, "hi_decision_from", "") or "hi_m",
                        "estimators_disagree": any(str(f).startswith("ESTIMATORS_DISAGREE")
                                                   for f in (getattr(inp.depth, "flags", None) or []))})
        details.update({"q_in_flame_kw_m2": dm.q_in_kw_m2, "depth_lo_m": dm.depth_lo_m, "depth_hi_m": dm.depth_hi_m,
                        "intensity_hi_kw_m": dm.intensity_hi_kw_m, "dose_at_max_speed_tdu": d_max,
                        "max_safe_speed_m_s": vmax, "q_in_flame_fds_ref_kw_m2": dm.q_in_fds_kw_m2,
                        "fds_label": heat.FDS_LABEL, "depth_calibrated": bool(getattr(inp.depth, "calibrated", False))})
        if not (_num(d_max) and d_max >= 0):
            cross.append("DOSE_INVALID")
        else:
            v = min_speed(dm.dose, veh.dose_limit_tdu, vmax, c.speed_resolution_m_s)
            if v is not None:
                return Verdict(CROSS_FAST, ["DOSE_WITHIN_LIMIT"], now, now + c.verdict_ttl_s, min_speed_m_s=v,
                               time_in_flame_s=dm.time_in_flame(v), dose_tdu=dm.dose(v),
                               dose_limit_tdu=veh.dose_limit_tdu, dose_fds_ref_tdu=dm.dose_fds_ref(v),
                               details=details)
            within_margin = d_max <= veh.dose_limit_tdu * (1.0 + c.spray_margin)
            if within_margin and veh.has_water is True:
                return Verdict(SPRAY, ["DOSE_WITHIN_SPRAY_MARGIN"], now, now + c.verdict_ttl_s,
                               min_speed_m_s=vmax, time_in_flame_s=dm.time_in_flame(vmax), dose_tdu=d_max,
                               dose_limit_tdu=veh.dose_limit_tdu, dose_fds_ref_tdu=dm.dose_fds_ref(vmax),
                               details=details)
            cross.append("DOSE_OVER_LIMIT")
            if within_margin:
                cross.append("NO_WATER_FOR_SPRAY")
            out_kw.update(time_in_flame_s=dm.time_in_flame(vmax), dose_tdu=d_max,
                          dose_fds_ref_tdu=dm.dose_fds_ref(vmax))
    details["crossing_reasons"] = list(cross)

    # ---- reopen path
    if inp.passed is True:
        reo = _sensor_checks(inp, REQUIRED_REOPEN, c, now)
        reo += _require(inp, ("plate_flux_kw_m2", "flame_pixels", "imu_roll_deg", "imu_pitch_deg", "tc_air_c",
                              "tc_plate_c", "tc_housing_c", "speed_m_s"))
        if not (_num(inp.gnss_fix) and inp.gnss_fix >= 1 and _num(inp.lat) and _num(inp.lon)):
            reo.append("GNSS_NO_FIX")
        if inp.flame_status == "FLAME":
            reo.append("FLAME_PRESENT")
        if inp.crossing_in_view is not True:
            reo.append("REOPEN_CROSSING_NOT_IN_VIEW")
            if inp.crossing_view_reason:
                details["reopen_view_reason"] = str(inp.crossing_view_reason)[:200]
        if _num(inp.speed_m_s) and inp.speed_m_s > c.reopen_max_speed_m_s:
            reo.append("REOPEN_VEHICLE_MOVING")
        if _num(inp.plate_flux_kw_m2) and not inp.plate_flux_kw_m2 < c.reopen_flux_kw_m2:
            reo.append("PLATE_FLUX_ABOVE_REOPEN")
        if _num(inp.flame_pixels) and inp.flame_pixels > c.reopen_hot_pixels:
            reo.append("FLAME_PIXELS_PRESENT")
        if not _num(inp.crossing_hot_pixels):
            reo.append("VALUE_MISSING:crossing_hot_pixels")
        elif inp.crossing_hot_pixels > c.reopen_hot_pixels:
            reo.append("CROSSING_HOT_PIXELS_PRESENT")
        if not (_num(inp.reopen_quiet_s) and inp.reopen_quiet_s >= c.reopen_hold_s):
            reo.append("REOPEN_HOLD_NOT_MET")
        details["reopen_reasons"] = list(reo)
        if not reo:
            details["stamp"] = {"lat": inp.lat, "lon": inp.lon, "utc": inp.utc}
            return Verdict(REOPENED, ["REOPEN_CONDITIONS_HELD"], now, now + c.verdict_ttl_s,
                           dose_limit_tdu=veh.dose_limit_tdu, details=details)
        return _closed(cross + reo, now, c, details=details, **out_kw)
    return _closed(cross, now, c, details=details, **out_kw)


def effective(verdict: Optional[Verdict], now: float, ttl_s: Optional[float] = None) -> Verdict:
    """The verdict to show at time ``now``: CLOSED once it is ttl_s (default its own expiry, 5 s) old."""
    if not isinstance(verdict, Verdict) or not _num(now):
        return Verdict(CLOSED, ["NO_VERDICT"], now if _num(now) else 0.0, now if _num(now) else 0.0)
    expires = verdict.expires_mono if ttl_s is None else verdict.issued_mono + ttl_s
    if not (_num(verdict.issued_mono) and _num(expires)) or now >= expires or now < verdict.issued_mono - 1e-6:
        return Verdict(CLOSED, ["VERDICT_EXPIRED"], verdict.issued_mono if _num(verdict.issued_mono) else now,
                       expires if _num(expires) else now, dose_limit_tdu=verdict.dose_limit_tdu,
                       details={"expired_state": verdict.state, "expired_verdict_id": verdict.verdict_id})
    return verdict


# ---------------------------------------------------------------------------------------------- reopen helpers
class HoldTracker:
    """How long a condition has held CONTINUOUSLY (seconds). A false/non-bool condition, a non-finite time, time
    going backwards, or a gap between updates longer than ``max_gap_s`` restarts the hold from zero (fail closed:
    a pipeline that stops ticking cannot carry an old hold forward). Used for the minimum flame evidence (D4)."""

    def __init__(self, max_gap_s: float = 2.0):
        self.max_gap_s = float(max_gap_s)
        self.since: Optional[float] = None
        self.last_mono: Optional[float] = None

    def reset(self) -> None:
        self.since = None
        self.last_mono = None

    def update(self, now: float, condition: bool) -> float:
        if not _num(now):
            self.reset()
            return 0.0
        gap = self.last_mono is None or now < self.last_mono or now - self.last_mono > self.max_gap_s
        self.last_mono = now
        if condition is not True:
            self.since = None
            return 0.0
        if gap or self.since is None:
            self.since = now
        return now - self.since


_SPEED_NOT_GIVEN = object()   # ReopenTracker.update: speed not supplied (direct/legacy callers)


class ReopenTracker:
    """Measures how long the REOPENED quiet conditions have held CONTINUOUSLY.

    Quiet = all sensors fresh (caller supplies ``sensors_ok``), plate flux < reopen_flux_kw_m2, flame pixels <=
    reopen_hot_pixels, the recorded crossing in the camera's view (``in_view``) and flame-temperature pixels in the
    image columns covering the crossing <= reopen_hot_pixels (``crossing_hot_pixels``). ``in_view`` /
    ``crossing_hot_pixels`` left as None count as NOT quiet (fail closed). When ``speed_m_s`` is given (the
    pipeline always gives it), the vehicle must also be at or below reopen_max_speed_m_s, so the hold is time
    spent stopped facing the crossing; a None / non-finite speed counts as moving (fail closed). Any non-quiet
    update, a non-finite value, time going backwards, or a gap between updates longer than stale_s restarts the
    hold from zero.
    """

    def __init__(self, cfg: Any = None):
        self.cfg = coerce_config(cfg)
        self.quiet_since: Optional[float] = None
        self.last_mono: Optional[float] = None

    def reset(self) -> None:
        self.quiet_since = None
        self.last_mono = None

    def update(self, now: float, plate_flux_kw_m2: Optional[float], flame_pixels: Optional[int],
               sensors_ok: bool, *, in_view: Optional[bool] = None,
               crossing_hot_pixels: Optional[int] = None, speed_m_s: Any = _SPEED_NOT_GIVEN) -> float:
        if not _num(now):
            self.reset()
            return 0.0
        gap = self.last_mono is None or now < self.last_mono or now - self.last_mono > self.cfg.stale_s
        self.last_mono = now
        quiet = (sensors_ok is True and _num(plate_flux_kw_m2) and plate_flux_kw_m2 < self.cfg.reopen_flux_kw_m2
                 and _num(flame_pixels) and flame_pixels <= self.cfg.reopen_hot_pixels
                 and in_view is True and _num(crossing_hot_pixels)
                 and crossing_hot_pixels <= self.cfg.reopen_hot_pixels)
        if quiet and speed_m_s is not _SPEED_NOT_GIVEN:
            quiet = _num(speed_m_s) and 0.0 <= speed_m_s <= self.cfg.reopen_max_speed_m_s
        if not quiet:
            self.quiet_since = None
            return 0.0
        if gap or self.quiet_since is None:
            self.quiet_since = now
        return now - self.quiet_since


def has_passed(position_en: Sequence[float], ref_en: Sequence[float], direction_en: Sequence[float],
               beyond_m: float) -> bool:
    """True when the vehicle position (local ENU, m) is more than beyond_m past ref along direction_en.

    ref_en: the far edge recorded at the crossing, or a recorded flame location (then beyond_m = depth_hi +
    vehicle length). direction_en: travel direction at the crossing. Non-finite input gives False.
    """
    try:
        px, py = float(position_en[0]), float(position_en[1])
        rx, ry = float(ref_en[0]), float(ref_en[1])
        ux, uy = float(direction_en[0]), float(direction_en[1])
        b = float(beyond_m)
    except (TypeError, ValueError, IndexError):
        return False
    if not all(math.isfinite(x) for x in (px, py, rx, ry, ux, uy, b)):
        return False
    n = math.hypot(ux, uy)
    if n <= 0:
        return False
    return ((px - rx) * ux + (py - ry) * uy) / n > b
