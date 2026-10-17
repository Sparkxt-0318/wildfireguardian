"""Build a routing request (the kit's request JSON) from an API body. Field layout and constants are exactly those of
the recorded final-panel requests (data/routing/latest_inputs_try02/requests/*), so a body that restates a recorded
mission reproduces that mission's request object exactly (tests/api/test_golden.py checks this equality)."""
from __future__ import annotations

import math

from .config import DEFAULT_DOSE_KJ_M2, DEFAULT_DWELL_S, DEFAULT_PEAK_KW_M2, REQUEST_CONSTANTS, REQUEST_LIMITS
from .errors import unprocessable


def num(v):
    """JSON number as recorded: integral values as int, others as float."""
    f = float(v)
    if not math.isfinite(f):
        raise unprocessable("VALIDATION_ERROR", "non-finite number %r" % (v,))
    return int(f) if f.is_integer() else f


def lattice_int(v, name, dt=1):
    f = float(v)
    if not math.isfinite(f) or f < 0 or not f.is_integer() or int(f) % dt:
        raise unprocessable("NOT_ON_TIME_LATTICE", "%s must be a non-negative whole number of seconds on the %d s lattice" % (name, dt),
                            {"field": name, "value": v})
    return int(f)


def effective_limits(body: dict) -> dict:
    lim = body.get("limits") or {}
    return {"peak_kw_m2": num(lim.get("peak_kw_m2", DEFAULT_PEAK_KW_M2)),
            "dose_kj_m2": num(lim.get("dose_kj_m2", DEFAULT_DOSE_KJ_M2)),
            "incurred_dose_kj_m2": num(body.get("incurred_dose_kj_m2", 0))}


def is_default_limits(limits: dict) -> bool:
    return (limits["peak_kw_m2"] == DEFAULT_PEAK_KW_M2 and limits["dose_kj_m2"] == DEFAULT_DOSE_KJ_M2
            and limits["incurred_dose_kj_m2"] == 0)


def build_request(*, start_node: str, dest_node: str, depart_offset_s, dwell_s, window, limits: dict,
                  scenario_ids, horizon_s: float, valid_from: float, hazard_version: int, as_of_iso: str, dt: int = 1) -> dict:
    depart = lattice_int(depart_offset_s, "depart_offset_s", dt)
    dwell = lattice_int(dwell_s if dwell_s is not None else DEFAULT_DWELL_S, "dwell_s", dt)
    horizon = float(horizon_s)
    if window is None:
        open_s, close_s = num(valid_from), num(horizon)
    else:
        if len(window) != 2:
            raise unprocessable("INVALID_WINDOW", "destination_window must be [open_s, close_s]", {"destination_window": window})
        open_s, close_s = lattice_int(window[0], "destination_window[0]", dt), lattice_int(window[1], "destination_window[1]", dt)
    if not (valid_from <= depart <= horizon):
        raise unprocessable("DEPARTURE_OUTSIDE_HORIZON", "depart_offset_s must lie within the hazard horizon [%g, %g] s" % (valid_from, horizon),
                            {"depart_offset_s": depart, "horizon_s": horizon})
    if not (0 <= open_s < close_s <= horizon):
        raise unprocessable("INVALID_WINDOW", "destination_window must satisfy 0 <= open_s < close_s <= %g" % horizon,
                            {"destination_window": [open_s, close_s], "horizon_s": horizon})
    peak, dose, incurred = limits["peak_kw_m2"], limits["dose_kj_m2"], limits["incurred_dose_kj_m2"]
    if not (peak > 0 and dose > 0 and incurred >= 0):
        raise unprocessable("INVALID_LIMITS", "limits must be positive and incurred dose non-negative", limits)
    return {
        "position": {"node": start_node},
        "incoming_edge": None,
        "departure": depart,
        "horizon": horizon,
        "destinations": [{"node": dest_node, "dwell": dwell, "open_intervals": [[open_s, close_s]]}],
        "incurred": {sid: incurred for sid in scenario_ids},
        "hazard_version": hazard_version,
        "as_of": as_of_iso,
        "objective": REQUEST_CONSTANTS["objective"],
        "exposure_scope": REQUEST_CONSTANTS["exposure_scope"],
        "budgets": {"peak": peak, "dose": {sid: dose for sid in scenario_ids}},
        "limits": dict(REQUEST_LIMITS),
        "solver": REQUEST_CONSTANTS["solver"],
    }
