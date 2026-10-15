"""Latest-forecast -> routing hazard bridge (wfg.final-forecast-bridge/2.0-latest-c651).

Consumes one clock-bound latest export (wfg.latest-forecast-export/2, checkpoint c651f672...) and emits the inherited
packet layout (HAZARD.json wfg.routing.edgegrid/1, REPORT.json, NATIVE_METADATA.json, constructed_arrays.npz) under the
UNCHANGED scalar source law wfg.hazard.construction/1 that the inherited search, bounds and whole-road checkers rebuild.
Derived from the reviewed bridge v1.1 (code/bridge/final_forecast_bridge.py, sha256 1df78f68...): the probability rule,
ignition draws, exact-event breakpoints, radiation model call and edgegrid assembly are unchanged. Changes:
  * Strict raw validation first (contract.validate_raw; B07): masks must be genuine booleans (no coercion), shapes must
    match, valid-marked NaN or contradictory activity/remaining values are refused.
  * Thermal scenario of the latest export: every ignited or present-fire cell burns for the export's scalar coarse-cell
    duration T (latest documented default: point residence 11.52 s + front crossing of the cell at 341 m/h, about
    3970.46 s for 375 m cells) and emits the fixed phase energy w*f*H spread over T: density w*f*H/T (about 4686.6 W/m2 for
    w=10 kg/m2, f=0.1, H=18.608 MJ/kg) with radiative fraction 0.30 through the inherited finite-cell isotropic source sheet
    (emission 5 m, receiver 0 m, transmissivity 1). The 300 s / 60000 W/m2 scenario of v1.1 is NOT used here.
  * Present fire (initial activity) is a SCALAR MAXIMUM-REMAINING ENCLOSURE of the latest per-cell activity: every cell the
    latest heat package marks active at the cutoff (arrival age < T on known burned support) is treated as active on
    [0, R_max) where R_max is the largest per-cell remaining time; a known-burned cell with unknown age is active on [0, T).
    Because emission is uniform and nonnegative and the source model is linear in the active map, flame contact and
    incident flux (hence peak and dose) under the enclosure are >= their per-cell values at every receiver and time.
    The exact per-cell latest trajectory is therefore NOT implemented; per-cell remaining times are preserved in
    constructed_arrays.npz (mask__initial_remaining_s_native) and the enclosure is flagged (initial_remaining_exact=false).
  * Probability rule (owner policy, unchanged): constructed q = native new-burn probability where the native mask is true,
    0 where false (recorded as mask__policy_assigned_zero), 0 on known already-burned cells. This zero assignment is not
    applied to activity, remaining time, timestamps, geometry or thermal quantities.
  * Cells whose cumulative burned state is unknown (no reconstructed arrival) carry no present-fire source because the
    latest heat package defines previous burning only on known already-burned cells; they are counted separately
    (mask__unknown_cumulative_state) and reported as a source-domain limitation.
  * Marginal probabilities do not define a joint law; independent cells and uniform timing are declared research
    assumptions, not a calibrated joint forecast.
"""
from __future__ import annotations

import hashlib, json, math, sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import contract as CT  # noqa: E402

BRIDGE_VERSION = "wfg.final-forecast-bridge/2.0-latest-c651"
SOURCE_LAW_VERSION = "wfg.hazard.construction/1"   # law recognised by the unchanged checkers (scalar T and R)
P = CT.POLICY
BASE_SETTINGS = {
    "bridge_version": BRIDGE_VERSION,
    "source_law_version": SOURCE_LAW_VERSION,
    "scenario_count": 4,
    "seed": 20261008,
    "horizon_s": 3600.0,
    "dependence": "independent",
    "timing": "uniform",
    "missing_new_burn_probability_policy": "zero (owner policy; native mask retained as mask__policy_assigned_zero)",
    "known_burned_first_new_burn_probability": 0.0,
    "present_fire_rule": "latest heat package arrival-age rule (known burned support, same scalar T); represented as a scalar max-remaining enclosure",
    "present_fire_representation": "SCALAR_MAX_REMAINING_ENCLOSURE (upper enclosure of per-cell activity; exact per-cell trajectory not implemented)",
    "unknown_age_burned_cell_policy": "conservative enclosure: active on [0,T)",
    "unknown_cumulative_state_present_fire": "not a source: the latest heat package defines previous burning only on known already-burned cells (no reconstructed arrival); counted separately as a source-domain limitation",
    "current_remaining_representation": "exact when all present-fire cells share one remaining time, else max-remaining enclosure (flagged)",
    "burning_duration_s": None,     # bound per export: the latest scalar coarse-cell duration
    "fuel_load_kg_m2": P["fuel_load_kg_m2"],
    "heat_of_combustion_j_kg": P["heat_of_combustion_j_kg"],
    "consumed_fraction": P["consumed_fraction"],
    "radiative_fraction": P["radiative_fraction"],
    "emission_height_m": P["emission_height_m"],
    "receiver_height_m": P["receiver_height_m"],
    "atmospheric_transmissivity": P["atmospheric_transmissivity"],
    "latest_export_policy": P,
    "spatial_interpretation": "whole 375 m cell treated as flaming (contact) and uniformly emitting on [ignition, ignition+T) with T the latest documented coarse-cell front-crossing duration; fixed phase energy w*f*H spread over T",
    "radiation_operator": "inherited reviewed finite-cell source-sheet implementation (release forecast/wildfire heat module, identity recorded per packet); the checkers recompute the same scalar law",
    "extinction_breakpoint_rounding": "round up to binary64 >= exact ignition+T (router flame interval contains exact interval)",
    "flux_numerical_margin": "per interval with any active source: flux + 1e-8*max(1 W/m2, max over the map of that interval) added to every cell, then nextafter up; <= 1e-8*max_flux per cell",
    "routing_dt_s": 1,
    "clock_offset_policy": "time_origin must equal the clock-bound forecast cutoff; any other offset is rejected",
    "support_channel": "all true under the declared policies (results are policy-conditional; native masks exported for audit)",
}


class BridgeError(ValueError):
    def __init__(self, code, message):
        super().__init__(code + ": " + message)
        self.code = code


def settings_for(cell_duration_s):
    s = json.loads(json.dumps(BASE_SETTINGS))
    T = float(cell_duration_s)
    if not (math.isfinite(T) and T > 0):
        raise BridgeError("DURATION", repr(cell_duration_s))
    s["burning_duration_s"] = T
    return s


def settings_digest(settings):
    return hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _utc(text):
    dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise BridgeError("TIME_METADATA", "timezone-aware timestamp required")
    return dt.astimezone(timezone.utc)


def draw_ignitions(q, scenario_count, seed, horizon_s):
    """Verbatim law of the preserved constructor (independent/uniform branch)."""
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or not np.all(np.isfinite(q)) or np.any((q < 0) | (q > 1)):
        raise BridgeError("PROBABILITY", "complete finite [0,1] probability matrix required")
    rng = np.random.default_rng(seed)
    shape = (scenario_count,) + q.shape
    u = rng.random(shape)
    occurrence = u < q
    times = rng.random(shape) * horizon_s
    return np.where(occurrence, times, np.inf)


def round_up_sum(a, b):
    s = float(a) + float(b)
    if Fraction(s) < Fraction(float(a)) + Fraction(float(b)):
        s = float(np.nextafter(s, np.inf))
    return s


def radiation_model(transform, settings, epsg):
    """Inherited radiation operator (release forecast/wildfire/heat.py on sys.path, identity recorded by the caller)."""
    from wildfire.heat import AffineGrid, CombustionParameters, ExpectedHeatFluxModel, FlameResidenceTime
    residence = FlameResidenceTime(settings["burning_duration_s"], provenance={"source": "bridge settings", "bridge": BRIDGE_VERSION})
    comb = CombustionParameters.from_flame_residence(residence, fuel_load_kg_m2=settings["fuel_load_kg_m2"],
                                                     heat_of_combustion_j_kg=settings["heat_of_combustion_j_kg"],
                                                     consumed_fraction=settings["consumed_fraction"])
    return ExpectedHeatFluxModel(grid=AffineGrid(tuple(float(v) for v in transform)),
                                 heat_release_rate_density_w_m2=comb.heat_release_rate_density_w_m2,
                                 radiative_fraction=settings["radiative_fraction"],
                                 emission_height_m=settings["emission_height_m"],
                                 receiver_height_m=settings["receiver_height_m"],
                                 atmospheric_transmissivity=settings["atmospheric_transmissivity"], epsg=int(epsg))


def radiation_operator_identity():
    import wildfire.heat as H
    return {"module": H.__file__, "sha256": sha256_file(H.__file__)}


def load_forecast(npz_path):
    """Load arrays exactly as stored (no dtype coercion; validation is strict and happens in construct)."""
    with np.load(npz_path, allow_pickle=False) as a:
        return {k: a[k].copy() for k in a.files}


def construct(forecast, *, cutoff_utc, epsg, settings):
    """Return per-member event arrays, masks and exact intervals on native north-up rows (strictly validated input)."""
    st = dict(settings)
    T = float(st["burning_duration_s"]); horizon = float(st["horizon_s"])
    try:
        summary = CT.validate_raw(forecast, T)
    except CT.ContractError as exc:
        raise BridgeError("RAW_INPUT", str(exc)) from exc
    q_native = forecast["new_burn_probability"]; valid = forecast["probability_valid"]
    burned = forecast["source_burned_area"]; bvalid = forecast["source_burned_area_valid"]
    H, W = q_native.shape
    known_burned = bvalid & (burned == 1)
    known_unburned = bvalid & (burned == 0)
    init_p = forecast["heat__initial_active_burning_probability"]
    init_r = forecast["heat__initial_remaining_burning_duration_s"]
    init_valid = forecast["heat__initial_burning_valid"]
    current_exact = init_valid & (init_p == 1) & known_burned
    unknown_age = known_burned & ~init_valid
    current = current_exact | unknown_age
    remaining_cells = {}
    for idx in zip(*np.nonzero(current_exact)):
        remaining_cells[(int(idx[0]), int(idx[1]))] = float(init_r[idx])
    for idx in zip(*np.nonzero(unknown_age)):
        remaining_cells[(int(idx[0]), int(idx[1]))] = T
    distinct = sorted(set(remaining_cells.values()))
    remaining = max(distinct) if distinct else 0.0
    remaining_exact = len(distinct) <= 1 and not unknown_age.any()
    # enclosure statistics over the horizon (cell-seconds of present-fire activity: per-cell exact vs enclosure)
    exact_cs = float(sum(min(r, horizon) for r in remaining_cells.values()))
    encl_cs = float(len(remaining_cells) * min(remaining, horizon))
    cq = np.where(valid, q_native, 0.0)
    cq[known_burned] = 0.0
    cq = np.where(np.isfinite(cq), cq, 0.0)
    events = draw_ignitions(cq, st["scenario_count"], st["seed"], horizon)
    if np.isfinite(events[:, current]).any():
        raise BridgeError("PRESENT_FIRE", "present-fire cell also drew a first-new ignition")
    masks = {
        "probability_valid_native": valid,
        "policy_assigned_zero": ~valid,
        "structural_zero_native": valid & known_unburned & (q_native == 0),
        "positive_native_probability": valid & known_unburned & (q_native > 0),
        "known_burned": known_burned,
        "unknown_cumulative_state": ~bvalid,
        "present_fire_exact": current_exact,
        "present_fire_unknown_age_enclosed": unknown_age,
        "constructed_probability": cq,
        "initial_remaining_s_native": np.where(current_exact, init_r, np.where(unknown_age, np.nan, 0.0)),
    }
    model = radiation_model(forecast["affine_transform"], st, epsg)
    members = []
    for s in range(st["scenario_count"]):
        births = events[s]
        fin = np.isfinite(births)
        ext = np.full(births.shape, np.inf)
        for idx in zip(*np.nonzero(fin)):
            ext[idx] = round_up_sum(births[idx], T)
        knots = {0.0, horizon}
        knots.update(float(v) for v in births[fin] if 0.0 < v < horizon)
        knots.update(float(v) for v in ext[fin] if 0.0 < v < horizon)
        if current.any() and 0.0 < remaining < horizon:
            knots.add(float(remaining))
        bp = sorted(knots)
        flame, flux = [], []
        for left in bp[:-1]:
            active = (fin & (births <= left) & (left < ext))
            if current.any() and left < remaining:
                active = active | current
            f = model.predict_details(active.astype(float)).incident_heat_flux_w_m2.astype(float)
            if active.any():
                f = np.nextafter(f + 1e-8 * max(1.0, float(f.max())), np.inf)
            flame.append(active.copy()); flux.append(f)
        members.append({"breakpoints": bp, "flame": np.array(flame, dtype=bool), "flux_w_m2": np.array(flux, dtype=float),
                        "ignition_time_s": births, "extinction_breakpoint_s": ext})
    enclosure = {"present_fire_cells": int(current.sum()), "present_fire_exact_cells": int(current_exact.sum()),
                 "unknown_age_cells_enclosed": int(unknown_age.sum()), "R_max_s": float(remaining),
                 "distinct_remaining_times": len(distinct), "initial_remaining_exact": bool(remaining_exact),
                 "present_fire_cell_seconds_exact_per_cell": exact_cs, "present_fire_cell_seconds_enclosure": encl_cs,
                 "enclosure_over_exact_ratio": None if exact_cs == 0 else encl_cs / exact_cs}
    return {"events": events, "current": current, "remaining_s": float(remaining), "remaining_exact": bool(remaining_exact),
            "remaining_cells": remaining_cells, "masks": masks, "members": members, "settings": st, "shape": (H, W),
            "crs": "EPSG:%d" % int(epsg), "affine_transform": [float(v) for v in forecast["affine_transform"]],
            "raw_summary": summary, "enclosure": enclosure}


def to_edgegrid(graph, built, *, cutoff_utc, identity, time_origin=None, version=1):
    """Assemble wfg.routing.edgegrid/1 with per-member breakpoints; validated by the unchanged router validator."""
    from routing.validation import validate_graph, validate_hazard
    validate_graph(graph)
    grid = graph["grid"]; H, W = built["shape"]
    if (grid["height"], grid["width"]) != (H, W):
        raise BridgeError("GRID_ALIGNMENT", "graph grid shape differs from forecast grid")
    cutoff = _utc(cutoff_utc)
    origin = cutoff if time_origin is None else _utc(time_origin)
    if origin != cutoff:
        raise BridgeError("CLOCK_OFFSET_UNSUPPORTED", "time_origin must equal the forecast cutoff (offset %s s)" % (cutoff - origin).total_seconds())
    if built["crs"] != graph["crs"] or identity.get("crs") != graph["crs"]:
        raise BridgeError("CRS_ALIGNMENT", "forecast CRS %s / identity CRS %s differ from graph CRS %s" % (built["crs"], identity.get("crs"), graph["crs"]))
    transform = built["affine_transform"]
    if [float(v) for v in identity["affine_transform"]] != transform:
        raise BridgeError("GRID_ALIGNMENT", "identity affine differs from the forecast affine used for radiation")
    res = grid["resolution"]
    expected = (res, 0.0, grid["x0"], 0.0, -res, grid["y0"] + H * res)
    if any(abs(x - y) > 1e-8 for x, y in zip(transform, expected)):
        raise BridgeError("GRID_ALIGNMENT", "native north-up affine must coincide with the graph grid (no resampling)")
    out = []
    for k, m in enumerate(built["members"]):
        flux_kw = (m["flux_w_m2"] / 1000.0)[:, ::-1, :]
        flame = m["flame"][:, ::-1, :]
        n = len(m["breakpoints"]) - 1
        out.append({"id": identity["scenario_ids"][k], "breakpoints": [float(x) for x in m["breakpoints"]],
                    "flux": flux_kw.reshape(n, -1).tolist(), "flame": flame.reshape(n, -1).tolist(),
                    "support": np.ones((n, H * W), dtype=bool).tolist()})
    T = built["settings"]["burning_duration_s"]
    hz = {"schema": "wfg.routing.edgegrid/1", "version": version, "graph_revision": graph["revision"], "crs": graph["crs"],
          "grid": dict(grid), "dt": built["settings"]["routing_dt_s"], "time_origin": origin.isoformat(),
          "issued_at": cutoff.isoformat(), "available_at": cutoff.isoformat(), "valid_from": 0.0,
          "valid_until": float(built["settings"]["horizon_s"]), "units": {"time": "s", "flux": "kW/m2", "dose": "kJ/m2"},
          "channels": ["flame_contact", "incident_heat_flux"],
          "unsupported_channels": ["smoke", "convective_heat", "embers", "secondary_ignition", "omitted_domain_sources", "spotting", "outside_domain_fire"],
          "evidence_class": "RESEARCH_CONSTRUCTION",
          "provenance": {"source": "Latest supplied forecast (wildfire 3 (1).zip, checkpoint c651f672...) through " + BRIDGE_VERSION,
                         "interpretation": ("Exact-event research realizations of a marginal one-hour new-burn forecast under declared independence, uniform timing, "
                                            "the latest documented coarse-cell duration T=%.6f s with fixed phase energy, a scalar max-remaining enclosure of present fire, "
                                            "and the inherited finite-cell radiation source model; cell-centre receivers; not a calibrated joint forecast or physical-safety evidence" % T),
                         "flame_semantics": "piecewise_constant_flame_contact (exact active set on each member interval; present fire enclosed to R_max)",
                         "flux_semantics": "piecewise_constant_incident_radiant_flux at cell centres (+ FFT margin 1e-8*max(1 W/m2, interval map max) per cell)",
                         "row_reversal": True, "identity": identity}, "members": out}
    validate_hazard(graph, hz)
    return hz
