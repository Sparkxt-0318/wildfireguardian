"""Opt-in trajectory construction, preserving physical source law v1.

Construction version 2 changes joint sampling, not the sheet-radiation law.
Unknown trajectory cells are unsupported. Consumers must honor support; no
global certificate follows when support is incomplete. Ordered sub-hour timing
is a distance-rank heuristic, not a fire spread model.
"""
from __future__ import annotations

import heapq
import importlib.util
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_wfg_bridge_v1", ROOT / "integration/src/wfg_latest/bridge.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)


def _distance_to(previous):
    h, w = previous.shape
    d = np.full((h, w), np.inf)
    queue = []
    for r, c in zip(*np.nonzero(previous)):
        d[r, c] = 0; heapq.heappush(queue, (0, int(r), int(c)))
    while queue:
        value, r, c = heapq.heappop(queue)
        if value != d[r, c]:
            continue
        for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= rr < h and 0 <= cc < w and value + 1 < d[rr, cc]:
                d[rr, cc] = value + 1
                heapq.heappush(queue, (value + 1, rr, cc))
    return d


def ignition_seconds(first_burn_hour, *, seed=0, timing="uniform"):
    a = np.asarray(first_burn_hour)
    if a.ndim != 3 or a.dtype != np.int16 or (a < -2).any():
        raise ValueError("Expected int16 [K,H,W] first-burn hours")
    if timing not in ("uniform", "ordered"):
        raise ValueError("Unknown sub-hour timing")
    rng = np.random.default_rng(seed)
    result = np.full(a.shape, np.inf)
    for k, field in enumerate(a):
        if timing == "uniform":
            u = rng.random(field.shape)
            result[k] = np.where(field > 0, (field - 1) * 3600.0 + u * 3600.0, np.inf)
        else:
            for hour in sorted(set(field[field > 0].tolist())):
                mask = field == hour
                distance = _distance_to((field >= 0) & (field < hour))
                indices = np.flatnonzero(mask)
                # Lexicographic row index breaks distance ties reproducibly.
                order = np.lexsort((indices, distance.ravel()[indices]))
                result[k].ravel()[indices[order]] = (hour - 1) * 3600 + (np.arange(len(indices)) + 0.5) * 3600 / len(indices)
    return result


def construct(forecast, *, cutoff_utc, epsg, settings, selection=None):
    """Build coherent member arrays with exact event knots and native masks.

    v1 validation and radiation function are imported unchanged. This function
    does not monkey-patch any v1 global and is safe for concurrent constructors.
    """
    st = dict(settings)
    first = np.asarray(forecast["trajectory_first_burn_hour"])
    if selection is None:
        indices = list(range(len(first)))
        selection = {"method": "first_k", "selected_indices": indices,
                     "weights": [1 / len(first)] * len(first), "reduction_cost": 0.0}
    indices = selection["selected_indices"]
    fields = first[indices]
    if fields.shape[1:] != forecast["new_burn_probability"].shape:
        raise ValueError("Trajectory grid differs from raw export")
    horizon = float(st["horizon_s"])
    if np.any(fields > np.ceil(horizon / 3600)):
        raise ValueError("Trajectory exceeds declared horizon")
    summary = v1.CT.validate_raw(forecast, st["burning_duration_s"])
    st.update(construction_version="wfg.hazard.construction/2", dependence="trajectory",
              scenario_count=len(fields), member_selection=selection)
    st.setdefault("acceptance", {"rule": "all", "k": len(fields), "m": len(fields)})
    timing = st.get("timing", "uniform")
    events = ignition_seconds(fields, seed=st["seed"], timing=timing)
    T = float(st["burning_duration_s"])
    known_burned = forecast["source_burned_area_valid"] & (forecast["source_burned_area"] == 1)
    if not np.all(fields[:, known_burned] == 0):
        raise ValueError("Trajectory cutoff state contradicts raw export")
    active = forecast["heat__initial_burning_valid"] & (forecast["heat__initial_active_burning_probability"] == 1) & known_burned
    unknown_age = known_burned & ~forecast["heat__initial_burning_valid"]
    current = active | unknown_age
    remaining_cells = {tuple(map(int, p)): float(forecast["heat__initial_remaining_burning_duration_s"][tuple(p)]) for p in np.argwhere(active)}
    remaining_cells.update({tuple(map(int, p)): T for p in np.argwhere(unknown_age)})
    remaining = max(remaining_cells.values(), default=0.0)
    model = v1.radiation_model(forecast["affine_transform"], st, epsg)
    members = []
    for births in events:
        finite = np.isfinite(births)
        ext = np.full(births.shape, np.inf)
        for rc in np.argwhere(finite):
            rc = tuple(rc); ext[rc] = v1.round_up_sum(births[rc], T)
        knots = {0.0, horizon}
        knots.update(float(x) for x in births[finite] if 0 < x < horizon)
        knots.update(float(x) for x in ext[finite] if 0 < x < horizon)
        if 0 < remaining < horizon:
            knots.add(remaining)
        bp = sorted(knots)
        flames, fluxes = [], []
        for t in bp[:-1]:
            burning = (finite & (births <= t) & (t < ext)) | (current & (t < remaining))
            flux = model.predict_details(burning.astype(float)).incident_heat_flux_w_m2.astype(float)
            if burning.any():
                flux = np.nextafter(flux + 1e-8 * max(1.0, float(flux.max())), np.inf)
            flames.append(burning); fluxes.append(flux)
        members.append(dict(breakpoints=bp, flame=np.asarray(flames, dtype=bool),
                            flux_w_m2=np.asarray(fluxes), ignition_time_s=births,
                            extinction_breakpoint_s=ext))
    return dict(members=members, events=events, current=current, remaining_s=remaining,
                remaining_exact=len(set(remaining_cells.values())) <= 1 and not unknown_age.any(),
                remaining_cells=remaining_cells, settings=st, shape=fields.shape[1:],
                crs="EPSG:%d" % epsg, affine_transform=list(map(float, forecast["affine_transform"])),
                masks={"trajectory_unknown": fields == -2}, raw_summary=summary,
                enclosure={"initial_remaining_exact": len(set(remaining_cells.values())) <= 1 and not unknown_age.any()})


def to_edgegrid(graph, built, **kwargs):
    hazard = v1.to_edgegrid(graph, built, **kwargs)
    for m, unknown in zip(hazard["members"], built["masks"]["trajectory_unknown"]):
        support = (~unknown[::-1]).ravel().tolist()
        m["support"] = [support.copy() for _ in m["flame"]]
    hazard["provenance"]["construction_version"] = "wfg.hazard.construction/2"
    hazard["provenance"]["dependence"] = "trajectory"
    hazard["provenance"]["settings"] = built["settings"]
    hazard["provenance"]["interpretation"] = "Coherent simulated trajectory members with declared sub-hour timing, scalar present-fire enclosure and physical sheet law v1. Empirical model-relative construction, not calibrated joint probabilities."
    return hazard
