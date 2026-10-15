"""Latest regional packet writer (wfg.latest-regional-packet/2). Derived from the reviewed regional adapter
wfg.regional-packet-adapter/1 (phaseA/adapter/regional_packets.py): event id plumbing, lattice-window restriction of ONE
full-event construction (draws on the full event grid, shared by every window of that event), packet layout and the
omitted-outside-source diagnostics are unchanged in substance. Changes: the bridge is the latest bridge (bridge.py) with
settings bound to the clock-bound export (contract.verify_binding) instead of module constants; the export record,
its embedded clock and policy, the exporter source and the radiation-operator identity are bound into NATIVE_METADATA;
present-fire enclosure statistics are recorded. Omitted-source values are reported diagnostics (LA06), not a proof.
Revision 2.1 (narrow repair of review findings MC01/MC02 on packet writer f1f3b421): the requested EPSG is verified against
the hashed export and its record (contract 1.1) and the graph CRS is compared BEFORE thermal construction; identity
clock_binding publishes only the verified derived clock object, never the unchecked record copy."""
from __future__ import annotations

import hashlib, json, math, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import bridge as B      # noqa: E402
import contract as CT   # noqa: E402

ADAPTER_VERSION = "wfg.latest-regional-packet/2.1"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crop_forecast(fc, win):
    r0, r1, c0, c1 = win["r0"], win["r1"], win["c0"], win["c1"]
    a, b, c, d, e, f = [float(x) for x in fc["affine_transform"]]
    out = {}
    for k, v in fc.items():
        if k.startswith("contract__"):
            out[k] = v
        elif k == "affine_transform":
            out[k] = np.array([a, b, c + c0 * a, d, e, f + r0 * e], dtype=np.float64)
        elif np.ndim(v) == 2:
            out[k] = np.ascontiguousarray(v[r0:r1 + 1, c0:c1 + 1])
        else:
            raise ValueError("UNEXPECTED_FORECAST_ARRAY:" + k)
    return out


def construct_regional(fc_full, cutoff, epsg, win, settings):
    full = B.construct(fc_full, cutoff_utc=cutoff, epsg=epsg, settings=settings)
    if win is None:
        return full, full
    r0, r1, c0, c1 = win["r0"], win["r1"], win["c0"], win["c1"]
    fc_w = crop_forecast(fc_full, win)
    draws = full["events"][:, r0:r1 + 1, c0:c1 + 1].copy()
    want_q = full["masks"]["constructed_probability"][r0:r1 + 1, c0:c1 + 1]
    original = B.draw_ignitions; calls = []

    def full_event_draws(q, scenario_count, seed, horizon_s):
        if not np.array_equal(np.asarray(q, dtype=float), want_q):
            raise ValueError("WINDOW_Q_DIFFERS_FROM_FULL_EVENT_Q")
        if (scenario_count, seed, horizon_s) != (settings["scenario_count"], settings["seed"], settings["horizon_s"]):
            raise ValueError("DRAW_SETTINGS_DIFFER")
        calls.append(1)
        return draws.copy()
    B.draw_ignitions = full_event_draws
    try:
        built = B.construct(fc_w, cutoff_utc=cutoff, epsg=epsg, settings=settings)
    finally:
        B.draw_ignitions = original
    if len(calls) != 1:
        raise ValueError("DRAW_INJECTION_NOT_USED_EXACTLY_ONCE")
    return full, built


def omitted_source_analysis(full, built, win, settings, epsg):
    if win is None:
        return {"window": None, "outside_sources_possible": False}
    r0, r1, c0, c1 = win["r0"], win["r1"], win["c0"], win["c1"]
    S, H, W = full["events"].shape
    inside = np.zeros((H, W), bool); inside[r0:r1 + 1, c0:c1 + 1] = True
    a, _, cx, _, e, fy = [float(v) for v in full["affine_transform"]]
    res = abs(a); h = settings["emission_height_m"] - settings["receiver_height_m"]
    density = settings["fuel_load_kg_m2"] * settings["heat_of_combustion_j_kg"] * settings["consumed_fraction"] / settings["burning_duration_s"]
    E = density * settings["radiative_fraction"] * settings["atmospheric_transmissivity"]; cap = E / 2.0
    wx0, wx1 = cx + c0 * a, cx + (c1 + 1) * a
    wy_n, wy_s = fy + r0 * e, fy + (r1 + 1) * e
    rows, cols = np.mgrid[0:H, 0:W]
    sx0 = cx + cols * a; sx1 = sx0 + a; sy_n = fy + rows * e; sy_s = sy_n + e
    dx = np.maximum(0.0, np.maximum(wx0 - sx1, sx0 - wx1)); dy = np.maximum(0.0, np.maximum(wy_s - sy_n, sy_s - wy_n))
    per_cell = np.minimum(cap, E * res * res * h / (4 * math.pi * (dx * dx + dy * dy + h * h) ** 1.5))
    model = B.radiation_model(full["affine_transform"], settings, epsg)
    cur_out = full["current"] & ~inside
    R = float(full["remaining_s"])
    out = {"window": dict(win), "emitted_radiative_W_m2": E, "cap_W_m2": cap, "members": []}
    for s, m in enumerate(full["members"]):
        ev = full["events"][s]; ext = m["extinction_breakpoint_s"]
        fin_out = np.isfinite(ev) & ~inside
        bp = m["breakpoints"]; pk = dose = cpk = cdose = 0.0; n_int = 0
        for k, left in enumerate(bp[:-1]):
            length = bp[k + 1] - left
            act = fin_out & (ev <= left) & (left < ext)
            if cur_out.any() and left < R:
                act = act | cur_out
            if not act.any():
                continue
            n_int += 1
            ub = min(cap, float(per_cell[act].sum()))
            pk = max(pk, ub); dose += ub * length
            f = model.predict_details(act.astype(float)).incident_heat_flux_w_m2[r0:r1 + 1, c0:c1 + 1]
            mx = float(np.max(f)); cpk = max(cpk, mx); cdose += mx * length
        out["members"].append({"member_index": s, "outside_ignitions": int(fin_out.sum()), "outside_present_fire": int(cur_out.sum()),
            "intervals_with_outside_sources": n_int, "reported_peak_bound_kW_m2": pk / 1000.0, "reported_dose_bound_kJ_m2": dose / 1000.0,
            "centre_model_max_omitted_flux_kW_m2": cpk / 1000.0, "centre_model_omitted_dose_envelope_kJ_m2": cdose / 1000.0})
    out["max_reported_dose_bound_kJ_m2"] = max(x["reported_dose_bound_kJ_m2"] for x in out["members"])
    out["max_reported_peak_bound_kW_m2"] = max(x["reported_peak_bound_kW_m2"] for x in out["members"])
    out["max_centre_model_omitted_flux_kW_m2"] = max(x["centre_model_max_omitted_flux_kW_m2"] for x in out["members"])
    out["interpretation"] = ("Window packets omit event sources outside the window (declared source domain). The analytic outside-source "
        "values are evaluated in ordinary floating point and are reported conditional diagnostics, not an independently verified enclosure; "
        "centre-model values use the inherited FFT model at window cell centres.")
    return out


def write_regional_packet(graph, graph_path, forecast_npz, record, record_sha256, cutoff, epsg, out_dir, *,
                          event_id, region_id, window=None, version=1):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=False)
    graph_sha = _sha(graph_path); graph_canon = B.canonical_sha(graph)
    bridge_src_sha = _sha(B.__file__)
    forecast_npz_sha256 = B.sha256_file(forecast_npz)
    if forecast_npz_sha256 != record["npz_sha256"]:
        raise ValueError("FORECAST_EXPORT_HASH_MISMATCH")
    fc_full = B.load_forecast(forecast_npz)
    bound = CT.verify_binding(fc_full, record, cutoff, event_id, epsg)    # clock / event / policy / duration / CRS authority
    cutoff = bound["cutoff_utc"]; epsg = bound["epsg"]
    if graph.get("crs") != "EPSG:%d" % epsg:                             # graph CRS bound before any thermal construction
        raise ValueError("CRS_GRAPH_MISMATCH: graph %r export/request EPSG:%d" % (graph.get("crs"), epsg))
    settings = B.settings_for(bound["cell_duration_s"])
    if settings["latest_export_policy"] != record["policy"]:
        raise ValueError("POLICY_MISMATCH")
    full, built = construct_regional(fc_full, cutoff, epsg, window, settings)
    omitted = omitted_source_analysis(full, built, window, settings, epsg)
    sdig = B.settings_digest(settings)
    rad = B.radiation_operator_identity()
    cid = hashlib.sha256((sdig + forecast_npz_sha256 + cutoff + bridge_src_sha + graph_canon).encode()).hexdigest()
    S = settings["scenario_count"]; H, W = built["shape"]
    ids = ["ffb1:%s:%s:%d" % (CT.tag(cutoff), cid[:16], k) for k in range(S)]
    identity = {"bridge_version": B.BRIDGE_VERSION, "bridge_source_sha256": bridge_src_sha, "settings_digest": sdig,
                "construction_id": cid, "scenario_ids": ids, "forecast_export_sha256": forecast_npz_sha256,
                "forecast_record_sha256": record_sha256, "checkpoint_sha256": CT.CHECKPOINT_SHA256,
                "exporter_sha256": record.get("exporter_sha256"), "contract_sha256": _sha(HERE / "contract.py"),
                "packet_writer_sha256": _sha(__file__), "radiation_operator": rad,
                "graph_revision": graph["revision"], "graph_file_sha256": graph_sha, "graph_canonical_sha256": graph_canon,
                "crs": "EPSG:%d" % epsg, "affine_transform": [float(v) for v in built["affine_transform"]],
                "native_shape": list(built["shape"]), "units": {"time": "s", "flux": "kW/m2", "dose": "kJ/m2", "native_flux": "W/m2"},
                "issued_at": B._utc(cutoff).isoformat(), "time_origin": B._utc(cutoff).isoformat(), "clock_offset_s": 0,
                "clock_binding": bound["clock"], "horizon_s": settings["horizon_s"],
                "scenario_identity_scope": "fresh cutoff-conditioned research realizations; no identity across cutoffs"}
    hz = B.to_edgegrid(graph, built, cutoff_utc=cutoff, identity=identity, version=version)
    with (out_dir / "HAZARD.json").open("x") as f:
        json.dump(hz, f, allow_nan=False, separators=(",", ":")); f.write("\n")
    arrays = {"ignition_time_s": built["events"], "current_active": built["current"], "support": np.ones((S, H, W), bool)}
    for k, v in built["masks"].items():
        arrays["mask__" + k] = np.asarray(v)
    for s, m in enumerate(built["members"]):
        arrays["member%d__breakpoints_s" % s] = np.asarray(m["breakpoints"], dtype=float)
        arrays["member%d__extinction_breakpoint_s" % s] = m["extinction_breakpoint_s"]
    np.savez_compressed(out_dir / "constructed_arrays.npz", **arrays)
    assumptions = {"version": B.SOURCE_LAW_VERSION, "bridge_version": B.BRIDGE_VERSION, "variant": "latest_forecast_exact_event",
                   "scenario_count": S, "seed": settings["seed"], "horizon_s": settings["horizon_s"],
                   "dependence": "independent", "timing": "uniform", "unknown_probability": 0.0,
                   "current_state": "latest_package_arrival_age_rule_scalar_max_remaining_enclosure",
                   "unknown_current_state": "no present-fire source outside known burned support (latest heat package rule)",
                   "initial_remaining_s": built["remaining_s"], "initial_remaining_exact": built["remaining_exact"],
                   **{k: settings[k] for k in ("fuel_load_kg_m2", "heat_of_combustion_j_kg", "burning_duration_s", "consumed_fraction",
                                                "radiative_fraction", "emission_height_m", "receiver_height_m", "atmospheric_transmissivity")}}
    template = {"position": {"node": graph["nodes"][0]["id"]}, "incoming_edge": None, "departure": 0, "horizon": 3600.0,
                "destinations": [{"node": graph["nodes"][1]["id"], "dwell": 0, "open_intervals": [[0, 3600]]}],
                "incurred": {i: 0 for i in ids}, "hazard_version": 1, "as_of": B._utc(cutoff).isoformat(),
                "objective": "earliest_arrival", "exposure_scope": "including_dwell",
                "budgets": {"peak": 10, "dose": {i: 100 for i in ids}}, "limits": {"wall_s": 30}, "solver": "baseline"}
    md = {"schema": "wfg.forecast.native-intervals/2", "mode": "research", "bridge_version": B.BRIDGE_VERSION,
          "construction_id": cid, "construction": {"assumptions": assumptions, "scenario_ids": ids, "construction_version": B.SOURCE_LAW_VERSION,
              "parent_forecast": {"cutoff_utc": cutoff, "event_id": event_id, "export_sha256": forecast_npz_sha256}},
          "graph_revision": graph["revision"], "crs": identity["crs"], "shape": list(built["shape"]), "affine_transform": identity["affine_transform"],
          "time_origin": identity["time_origin"], "issued_at": identity["issued_at"], "available_at": identity["issued_at"],
          "breakpoints_s": [0.0, settings["horizon_s"]], "member_breakpoint_counts": [len(m["breakpoints"]) for m in built["members"]],
          "identity": identity, "settings": settings, "present_fire_cells": {"%d,%d" % k: v for k, v in built["remaining_cells"].items()},
          "present_fire_enclosure": built["enclosure"], "raw_input_summary": built["raw_summary"],
          "mask_definitions": {"probability_valid_native": "native model probability validity (export mask, unmodified)",
                               "policy_assigned_zero": "native probability missing; constructed q=0 by owner policy (probabilities only)",
                               "structural_zero_native": "native valid, known unburned, q exactly 0",
                               "positive_native_probability": "native valid, known unburned, q>0",
                               "known_burned": "known already-burned (first-new q=0 by definition)",
                               "unknown_cumulative_state": "burned state unknown (no reconstructed arrival); not a present-fire source under the latest heat package rule; counted as a source-domain limitation",
                               "present_fire_exact": "latest heat package arrival-age rule active at cutoff",
                               "present_fire_unknown_age_enclosed": "known burned with unknown age; enclosed active [0,T)",
                               "initial_remaining_s_native": "per-cell latest remaining time (enclosed to R_max in the source law)"},
          "evidence_class": "RESEARCH_CONSTRUCTION", "physical_scope": "research construction; not physical-safety evidence"}
    if window is not None:
        md["regional"] = {"adapter_version": ADAPTER_VERSION, "region_id": region_id, "event_id": event_id,
            "full_event_shape": list(full["shape"]), "full_event_affine_transform": [float(v) for v in full["affine_transform"]],
            "window_rows_cols_north_up": dict(window),
            "draw_provenance": "ignition draws are the bridge draws on the FULL event grid [S,H,W] (seed %d) restricted to the window; present fire, q rule, radiation and breakpoints recomputed on the window" % settings["seed"],
            "full_event_present_fire_enclosure": full["enclosure"],
            "source_domain": "window only; outside-window event sources omitted from router flux/flame and checker source arrays alike",
            "omitted_outside_sources": omitted}
    else:
        md["regional"] = {"adapter_version": ADAPTER_VERSION, "region_id": region_id, "event_id": event_id,
            "window_rows_cols_north_up": None, "source_domain": "whole event grid"}
    for name, obj in (("REPORT.json", {"schema": "wfg.final-forecast-bridge.report/1", "mode": "research", "native_metadata": md, "rows": [{"request": template}]}),
                      ("NATIVE_METADATA.json", md)):
        with (out_dir / name).open("x") as f:
            json.dump(obj, f, allow_nan=False, indent=1); f.write("\n")
    summary = {"out_dir": str(out_dir), "construction_id": cid, "scenario_ids": ids, "shape": list(built["shape"]),
               "ignitions_per_member": [int(np.isfinite(built["events"][s]).sum()) for s in range(S)],
               "breakpoints_per_member": md["member_breakpoint_counts"], "present_fire_cells": len(built["remaining_cells"]),
               "initial_remaining_s": built["remaining_s"], "initial_remaining_exact": built["remaining_exact"],
               "enclosure": built["enclosure"], "raw_input_summary": built["raw_summary"],
               "max_flux_kW_m2": max(float(m["flux_w_m2"].max()) for m in built["members"]) / 1000.0,
               "files_sha256": {n: _sha(out_dir / n) for n in ("HAZARD.json", "REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")},
               "hazard_bytes": (out_dir / "HAZARD.json").stat().st_size, "settings_digest": sdig, "radiation_operator": rad, "omitted": omitted}
    return out_dir, hz, summary
