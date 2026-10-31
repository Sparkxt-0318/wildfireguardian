"""Opt-in trajectory construction, preserving physical source law v1.

Construction version 2 changes joint sampling, not the sheet-radiation law.
Unknown trajectory cells are unsupported. Consumers must honor support; no
global certificate follows when support is incomplete. Ordered sub-hour timing
is a distance-rank heuristic, not a fire spread model.
"""
from __future__ import annotations

import heapq
import importlib.util
import json
import hashlib
import sys
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


def ignition_seconds(first_burn_hour, *, seed=0, timing="uniform", trajectory_indices=None):
    a = np.asarray(first_burn_hour)
    if a.ndim != 3 or a.dtype != np.int16 or (a < -2).any():
        raise ValueError("Expected int16 [K,H,W] first-burn hours")
    if timing not in ("uniform", "ordered"):
        raise ValueError("Unknown sub-hour timing")
    ids = list(range(len(a))) if trajectory_indices is None else list(trajectory_indices)
    if len(ids) != len(a):
        raise ValueError("Trajectory identity count mismatch")
    result = np.full(a.shape, np.inf)
    for k, field in enumerate(a):
        rng = np.random.default_rng([int(seed), int(ids[k])])
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
                seconds = np.sort(rng.random(len(indices))) * 3600
                result[k].ravel()[indices[order]] = (hour - 1) * 3600 + seconds
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
    if (not indices or len(set(indices)) != len(indices)
            or any(isinstance(i, bool) or not isinstance(i, (int, np.integer)) or not 0 <= i < len(first) for i in indices)):
        raise ValueError("Unique valid trajectory indices required")
    weights = np.asarray(selection["weights"], dtype=float)
    if weights.shape != (len(indices),) or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError("Normalized retained weights required")
    fields = first[indices]
    if fields.shape[1:] != forecast["new_burn_probability"].shape:
        raise ValueError("Trajectory grid differs from raw export")
    horizon = float(st["horizon_s"])
    if np.any(fields > np.ceil(horizon / 3600)):
        raise ValueError("Trajectory exceeds declared horizon")
    summary = v1.CT.validate_raw(forecast, st["burning_duration_s"])
    impossible = forecast["probability_valid"] & (forecast["new_burn_probability"] == 0)
    if np.any((fields == 1) & impossible):
        raise ValueError("First-hour burn contradicts a valid zero transition probability")
    st.update(construction_version="wfg.hazard.construction/2", dependence="trajectory",
              scenario_count=len(fields), member_selection=selection)
    st.setdefault("acceptance", {"rule": "all", "k": len(fields), "m": len(fields)})
    timing = st.get("timing", "uniform")
    events = ignition_seconds(fields, seed=st["seed"], timing=timing, trajectory_indices=indices)
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
    from wfg_latest.radiation.heat import AffineGrid, CombustionParameters, ExpectedHeatFluxModel, FlameResidenceTime
    residence = FlameResidenceTime(T, provenance={"source": "declared v1 scalar duration"})
    comb = CombustionParameters.from_flame_residence(residence, fuel_load_kg_m2=st["fuel_load_kg_m2"],
        heat_of_combustion_j_kg=st["heat_of_combustion_j_kg"], consumed_fraction=st["consumed_fraction"])
    model = ExpectedHeatFluxModel(grid=AffineGrid(tuple(map(float, forecast["affine_transform"]))),
        heat_release_rate_density_w_m2=comb.heat_release_rate_density_w_m2,
        radiative_fraction=st["radiative_fraction"], emission_height_m=st["emission_height_m"],
        receiver_height_m=st["receiver_height_m"], atmospheric_transmissivity=st["atmospheric_transmissivity"], epsg=epsg)
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
    routing_root = ROOT / "integration/kit/routing_candidate/baseline/routing-package"
    if str(routing_root) not in sys.path:
        sys.path.insert(0, str(routing_root))
    hazard = v1.to_edgegrid(graph, built, **kwargs)
    for m, unknown in zip(hazard["members"], built["masks"]["trajectory_unknown"]):
        # Unknown emitting cells can irradiate known receivers. Without an
        # enclosure for those sources, route-local support is insufficient.
        support = (np.zeros_like(unknown, dtype=bool) if unknown.any() else ~unknown[::-1]).ravel().tolist()
        m["support"] = [support.copy() for _ in m["flame"]]
    hazard["provenance"]["construction_version"] = "wfg.hazard.construction/2"
    hazard["provenance"]["dependence"] = "trajectory"
    hazard["provenance"]["settings"] = built["settings"]
    hazard["provenance"]["interpretation"] = "Coherent simulated trajectory members with declared sub-hour timing, scalar present-fire enclosure and physical sheet law v1. Empirical model-relative construction, not calibrated joint probabilities."
    return hazard


def packet_identity(graph, built, *, cutoff_utc, forecast_identity):
    base = dict(crs=graph["crs"], affine_transform=built["affine_transform"],
                forecast_identity=forecast_identity, cutoff_utc=cutoff_utc,
                graph_canonical_sha256=v1.canonical_sha(graph),
                settings_digest=v1.settings_digest(built["settings"]))
    cid = v1.canonical_sha(base)
    base.update(construction_id=cid, scenario_ids=["trajectory:%s:%s:%d" %
        (v1.CT.tag(cutoff_utc), cid[:16], i) for i in built["settings"]["member_selection"]["selected_indices"]])
    return base


def to_contact_model(built, *, ids=None):
    src = str(Path(__file__).parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from wfg_scenario_members.contact import ContactModel
    model = ContactModel.from_arrays(built["events"], built["current"],
        built["settings"]["burning_duration_s"], built["remaining_s"], ids=ids,
        weights=built["settings"]["member_selection"]["weights"])
    model.supported = not bool(built["masks"]["trajectory_unknown"].any())
    return model


def write_packet(out_dir, graph, built, *, cutoff_utc, template_metadata, request_template,
                 forecast_identity):
    """Write the inherited packet layout, retaining the unknown support mask.

    The template binds geometry and source-domain conventions only. New member
    identities and histories must be supplied explicitly by the caller. This
    refuses to synthesize incurred history for different trajectories.
    """
    import copy
    out = Path(out_dir)
    cutoff = v1.CT.normalize_cutoff(cutoff_utc)[0]
    if (v1.CT.normalize_cutoff(template_metadata["time_origin"])[0] != cutoff
            or v1.CT.normalize_cutoff(template_metadata["construction"]["parent_forecast"]["cutoff_utc"])[0] != cutoff):
        raise ValueError("Template clock differs from the exported cutoff")
    if template_metadata.get("crs", graph["crs"]) != graph["crs"]:
        raise ValueError("Template CRS differs from graph")
    identity = packet_identity(graph, built, cutoff_utc=cutoff_utc, forecast_identity=forecast_identity)
    ids = identity["scenario_ids"]
    if set(request_template["incurred"]) != set(ids) or set(request_template["budgets"]["dose"]) != set(ids):
        raise ValueError("Explicit new-member incurred history and budgets required")
    hazard = to_edgegrid(graph, built, cutoff_utc=cutoff_utc, identity=identity)
    metadata = copy.deepcopy(template_metadata)
    metadata.update(shape=list(built["shape"]), affine_transform=built["affine_transform"],
                    identity=identity, construction_id=identity["construction_id"], settings=built["settings"])
    assumptions = metadata["construction"]["assumptions"]
    assumptions.update(scenario_count=len(ids), dependence="trajectory", timing=built["settings"]["timing"],
                       initial_remaining_s=built["remaining_s"], initial_remaining_exact=built["remaining_exact"])
    metadata["construction"].update(construction_version="wfg.hazard.construction/2", scenario_ids=ids)
    metadata["construction"]["assumptions"]["version"] = "wfg.hazard.construction/1"
    metadata["unknown_policy"] = "Unknown trajectory support retained, no zero-assigned source certainty"
    support = ~built["masks"]["trajectory_unknown"].copy()
    for row, unknown in zip(support, built["masks"]["trajectory_unknown"]):
        if unknown.any():
            row[:] = False
    arrays = dict(ignition_time_s=built["events"], current_active=built["current"],
                  support=support, mask__trajectory_unknown=built["masks"]["trajectory_unknown"])
    for i, member in enumerate(built["members"]):
        arrays["member%d__breakpoints_s" % i] = np.asarray(member["breakpoints"])
        arrays["member%d__extinction_breakpoint_s" % i] = member["extinction_breakpoint_s"]
    out.mkdir(parents=True, exist_ok=False)
    for name, data in (("HAZARD.json", hazard), ("NATIVE_METADATA.json", metadata),
                       ("REPORT.json", {"schema": "wfg.final-forecast-bridge.report/1", "native_metadata": metadata,
                                        "rows": [{"request": request_template}]})):
        (out / name).write_text(json.dumps(data, allow_nan=False) + "\n")
    np.savez_compressed(out / "constructed_arrays.npz", **arrays)
    return {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in
            ("HAZARD.json", "NATIVE_METADATA.json", "REPORT.json", "constructed_arrays.npz")}
