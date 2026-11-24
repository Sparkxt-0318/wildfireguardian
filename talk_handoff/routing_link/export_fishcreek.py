"""Run the exposure pipeline for Fish Creek, hours 0-5, and export what run_all.py reads (PROTOCOL.md Amendment 1).

Run with the pipeline workspace on the path (its root as the working directory):

    cd WORKSPACE && PYTHONPATH=WORKSPACE python export_fishcreek.py --out EXPORT_DIR [--hours 6]

Settings are those of demonstration/flame_danger/physical_exposure_example.py, unchanged; the later hours use the
pipeline's own retained-path orchestrator. Writes:

* hour_00.npz ... hour_05.npz  (keys of blocking.HourFields)
* fire_arrival_earliest.tif, fire_arrival_half.tif  (road-layer format, minutes from the cutoff)
* checks.json  (hour 0 against the saved example; binwise integrals against the pipeline's hourly totals)
* pipeline_fields.npz  (the pipeline's own hourly output fields, all hours, as returned)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SEED = 20261122
SAMPLES = 1024
EDGES = np.arange(0.0, 3601.0, 60.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    from wildfire import (CellBurningDuration, FlameResidenceTime, EnvironmentalCellDuration, LiveFuelMoisture,
                          HeatSmokeHazards, load_data, load_model)
    from wildfire.environmental_duration import DURATION_SOURCE_CHANNELS
    from wildfire.schema import TRAINING_SOURCE_CHANNELS, HAZARD_SOURCE_CHANNELS
    from wildfire.hazards import HazardTimeline
    from wildfire import monte_carlo_hazards as mch
    from demonstration.flame_danger.reference_inputs import load_reference_inputs
    from demonstration.flame_danger.physical_exposure_example import OUTPUT as SAVED

    # --- exactly the saved example's inputs (physical_exposure_example.generate) ---
    reference = load_reference_inputs()
    parameters, archive, previous = reference.parameters, reference.archive, reference.selection
    model = load_model(device="cpu")
    channels = tuple(dict.fromkeys(TRAINING_SOURCE_CHANNELS + HAZARD_SOURCE_CHANNELS + DURATION_SOURCE_CHANNELS))
    with load_data(events=[previous["event"]], channels=channels, sequence_length=1, patch_size=None,
                   time_range=(previous["cutoff_utc"], previous["cutoff_utc"]), daily_policy="completed_day") as ds:
        assert len(ds) == 1
        sample = ds[0]
    for key in ("future_labels", "newly_burned_area", "future_burned_area", "next_burned_area"):
        sample.pop(key, None)  # future outcomes never enter the forecast
    est = EnvironmentalCellDuration.from_sample(
        sample, live_moisture=LiveFuelMoisture.from_scott_burgan(previous["live_moisture_reference"]))
    environment = est.environment
    residence, cell_duration = est.resolve(
        fallback_residence_time=FlameResidenceTime(archive["residence_duration_s"],
            {"source": "previously user-selected archived Fish Creek point-duration fallback for this example only"}),
        fallback_cell_burning_duration=CellBurningDuration(archive["cell_burning_duration_s"],
                                                           reference.cell_duration_provenance))
    front = np.where(est.resolved, (est.fields["spread_direction_deg_ccw_from_x"] + 90.) % 360.,
                     parameters.parameters_dict()["source_front_direction_deg_ccw_from_projected_x"])
    activity_options = dict(residence_time=residence, cell_burning_duration=cell_duration,
                            initial_arrival_uncertainty=previous["initial_arrival_uncertainty"],
                            boundary="zero", missing_burned_area="unburned")

    def factory(support, *, interval_start_s, interval_end_s):
        # the example's factory; weather held at the cutoff (no environmental forecast)
        return HeatSmokeHazards(support, environment=environment, parameters=parameters,
                                fuel_load_kg_m2=reference.fuel_load_kg_m2, flame_height_m=reference.flame_height_m,
                                source_front_direction_deg_ccw_from_projected_x=front, unresolved_heat_policy="bounds")

    # --- later-hour path: retained joint paths, then [h, h+1] windows ---
    print("activity at the cutoff", flush=True)
    initial = model.predict_fire_activity_sample(sample, **activity_options)
    print("spread, %d retained paths, hours 1..%d" % (SAMPLES, a.hours), flush=True)
    spread = model.predict_cumulative(sample, hours=list(range(1, a.hours + 1)), n_samples=SAMPLES, seed=SEED,
                                      retain_trajectories=True, boundary="zero", missing_burned_area="unburned")

    captured = []
    original = mch.weighted_exposure_integrals

    def capture(physical, probabilities, edges):
        result = original(physical, probabilities, edges)
        timeline = HazardTimeline(physical.receiver_grid, physical.receiver_shape, edges, [1.],
                                  {"source": "direct probability-weighted active-fire maps"})
        f = physical.fields_from_activity(probabilities[None], timeline, quantities=("radiant", "co"))
        captured.append({"edges": np.asarray(edges, float), "radiant_w_m2": np.asarray(f.lower_bounds["radiant"][0]),
                         "co_mg_m3": np.asarray(f.lower_bounds["co"][0]), "integral": result[0], "unresolved": result[1]})
        return result

    mch.weighted_exposure_integrals = capture
    try:
        multi = spread.calculate_hazards(hours_later=list(range(a.hours)), initial_activity=initial,
                                         physical_factory=factory, ignition_timing="uniform_within_step",
                                         timing_seed=SEED, time_step_s=60., batch_size=8,
                                         activity_mode="probability_map",
                                         progress=lambda h, d, t: print("  hour %d: %d/%d" % (h, d, t), flush=True)
                                         if d == t else None)
    finally:
        mch.weighted_exposure_integrals = original
    assert len(captured) == a.hours, len(captured)
    np.savez_compressed(out / "pipeline_fields.npz", **multi.numpy())

    checks = {"hours": a.hours, "samples": SAMPLES, "seed": SEED, "ignition_timing": "uniform_within_step",
              "weather": "cutoff weather held for later hours (no environmental_forecast)"}
    vis_fallback = 0
    for h in range(a.hours):
        r, c = multi.at(hours_later=h), captured[h]
        F = r.fields
        unres_rad, unres_co = c["unresolved"]["radiant"], c["unresolved"]["co"]
        dt = np.diff(c["edges"])[:, None, None]
        e_bins = np.sum(c["radiant_w_m2"] * dt, axis=0)
        co_bins = np.sum(c["co_mg_m3"] * dt, axis=0) / 3600.
        ok_r = ~unres_rad
        checks["hour_%d" % h] = {
            "radiant_integral_max_abs_diff_j_m2": float(np.max(np.abs(e_bins[ok_r] - F["radiant_energy_j_m2"][ok_r]))) if ok_r.any() else None,
            "co_mean_max_abs_diff_mg_m3": float(np.nanmax(np.abs(co_bins - F["co_known_contribution_mg_m3"]))),
            "max_binwise_radiant_kw_m2": float(np.max(c["radiant_w_m2"]) / 1000.),
            "max_binwise_co_ppm": float(np.max(c["co_mg_m3"]) / 1.145),
            "max_visibility_probability": float(np.nanmax(F["visibility_probability_upper"])),
            "radiant_unresolved_cells": int(unres_rad.sum()), "co_unresolved_cells": int(unres_co.sum())}
        pv = np.asarray(F["visibility_danger_probability"], float)
        miss = np.isnan(pv)
        vis_fallback += int(miss.sum())
        pv = np.where(miss, F["visibility_probability_lower"], pv)
        co = np.where(unres_co[None], np.nan, c["co_mg_m3"])
        np.savez_compressed(out / ("hour_%02d.npz" % h), bin_edges_s=c["edges"], p_vis=pv,
                            pm25_ug_m3=np.asarray(F["pm25_known_contribution_ug_m3"]),
                            q_rad_kw_m2=c["radiant_w_m2"] / 1000., thermal_resolved=~unres_rad, co_mg_m3=co)
    checks["visibility_lower_bound_cell_hours"] = vis_fallback

    # hour 0 against the saved one-hour example (exact q there, 1024 sampled paths here)
    with np.load(SAVED / "mapping.npz") as z:
        F0 = multi.at(hours_later=0).fields
        cmp = {}
        for k in ("pm25_hour_mean_ug_m3", "co_hour_mean_mg_m3", "thermal_known_contribution_j_m2",
                  "visibility_danger_probability"):
            x, y = np.asarray(F0[k], float), np.asarray(z[k], float)
            m = np.isfinite(x) & np.isfinite(y)
            cmp[k] = {"saved_max": float(y[m].max()), "this_max": float(x[m].max()),
                      "max_abs_diff": float(np.max(np.abs(x[m] - y[m]))),
                      "corr": float(np.corrcoef(x[m], y[m])[0, 1]) if x[m].std() > 0 and y[m].std() > 0 else None}
        checks["hour0_vs_saved_example"] = cmp

    # fire arrival (Amendment 1, item 6), minutes from the cutoff, road-layer format
    first, valid, transform, epsg = spread.trajectories.select()
    first = np.asarray(first)
    H = a.hours
    burned0 = first[0] == 0
    reached = (first > 0) & (first <= H)
    kmin = np.where(reached.any(axis=0), np.where(reached, first, 10 ** 6).min(axis=0), 0)
    earliest = np.where(burned0, 0.0, np.where(reached.any(axis=0), 60.0 * (kmin - 1), np.inf))
    half = np.full(first.shape[1:], np.inf)
    for k in range(H, 0, -1):
        frac = ((first > 0) & (first <= k)).mean(axis=0)
        half = np.where(frac >= 0.5, 60.0 * (k - 1), half)
    half = np.where(burned0, 0.0, half)
    vcov = np.asarray(valid)[: H + 1].all(axis=0)
    checks["fire_arrival"] = {"valid_cells": int(vcov.sum()), "n_cells": int(vcov.size),
                              "burned_at_cutoff": int(burned0.sum()),
                              "reached_earliest_member": int((np.isfinite(earliest) & ~burned0).sum()),
                              "reached_half_of_paths": int((np.isfinite(half) & ~burned0).sum())}
    earliest = np.where(vcov, earliest, np.nan)
    half = np.where(vcov, half, np.nan)

    sys.path.insert(0, str(HERE))
    import route  # noqa: F401  (puts the road layer on the path)
    from wfg_roadlayer import geotiff
    md = {"WFG_ISSUE_TIME": "2024-08-23T00:00:00Z", "WFG_HORIZON_MIN": 60 * H, "WFG_UNITS": "minutes"}
    for name, arr, rule in (("fire_arrival_earliest.tif", earliest, "earliest of %d retained paths" % SAMPLES),
                            ("fire_arrival_half.tif", half, "first hour by which half of %d paths burned" % SAMPLES)):
        geotiff.write(out / name, arr, tuple(float(v) for v in transform), int(epsg), nodata=float("nan"),
                      dtype="float32", metadata=dict(md, WFG_SOURCE="wildfire M548 recursive Monte Carlo, " + rule))
    checks["elapsed_s"] = time.monotonic() - t0
    (out / "checks.json").write_text(json.dumps(checks, indent=1))
    print(json.dumps(checks, indent=1))


if __name__ == "__main__":
    main()
