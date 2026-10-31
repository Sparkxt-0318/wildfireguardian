# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""from_wfg_packet encodes a present-fire cell (current_active = burning AT the cutoff) as burning on
[R_cell - T, ...) in BOTH present_fire modes. wfg_latest.contract.validate_raw accepts remaining
times up to T * (1 + 1e-12) (rel_tol), and wfg_latest.bridge.construct passes them through (R_max
included). For such a cell R_cell - T > 0: the adapter says it ignites AFTER issue, so a query at
t = 0 on a cell the packet marks as burning at t = 0 (the router's flame set includes it on
[0, R_max)) reports contact=False, supported=True, flux_upper=0 -- even in the "enclosure" mode
documented as what the router used.

test_hand_built_packet: R_cell = T * (1 + 5e-13).
test_real_bridge_packet: the same export through the real wfg_latest bridge (skipped if not importable).
"""
from pathlib import Path
import json
import sys

import numpy as np
import pytest

import hazard_contract as hc

T = 3970.4642815249267
H, W, K = 3, 4, 4
R = T * (1 + 5e-13)                     # within validate_raw's tolerance (ir <= T * (1 + 1e-12))


def _write_packet(d, events, ext, masks, current, r_max):
    arrays = {"ignition_time_s": events, "current_active": current, "support": np.ones((K, H, W), bool)}
    for k, v in masks.items():
        arrays["mask__" + k] = np.asarray(v)
    for s in range(K):
        arrays[f"member{s}__extinction_breakpoint_s"] = ext[s]
    np.savez_compressed(d / "constructed_arrays.npz", **arrays)
    A = {"scenario_count": K, "seed": 20261008, "horizon_s": 3600.0, "initial_remaining_s": r_max,
         "initial_remaining_exact": True, "fuel_load_kg_m2": 10.0, "heat_of_combustion_j_kg": 18608000.0,
         "burning_duration_s": T, "consumed_fraction": 0.1, "radiative_fraction": 0.3, "emission_height_m": 5.0,
         "receiver_height_m": 0.0, "atmospheric_transmissivity": 1.0}
    md = {"schema": "wfg.forecast.native-intervals/2", "bridge_version": "wfg.final-forecast-bridge/2.0-latest-c651",
          "crs": "EPSG:5179", "shape": [H, W], "affine_transform": [375.0, 0.0, 1000.0, 0.0, -375.0, 5000.0],
          "time_origin": "2022-03-04T06:00:00+00:00",
          "construction": {"assumptions": A, "scenario_ids": [f"m{k}" for k in range(K)]},
          "identity": {}, "regional": {"window_rows_cols_north_up": None}}
    (d / "NATIVE_METADATA.json").write_text(json.dumps(md))


def _check(d):
    for mode in ("exact", "enclosure"):
        s = hc.from_wfg_packet(d, present_fire=mode)
        c = s.grid.cell_centers(np.array([1]), np.array([1]))[0]
        hz = s.member(0).segment(c, 0.0, 0.0)        # stationary at the issue instant
        assert hz.contact is True, (
            f"{mode}: present-fire cell (burning at the cutoff) reads {hz}; "
            f"ignite_s={s.ignite_s[0, 1, 1]!r} > 0")


def test_hand_built_packet(tmp_path):
    cur = np.zeros((H, W), bool)
    cur[1, 1] = True
    masks = {"policy_assigned_zero": np.zeros((H, W), bool), "known_burned": cur.copy(),
             "unknown_cumulative_state": np.zeros((H, W), bool), "present_fire_exact": cur.copy(),
             "present_fire_unknown_age_enclosed": np.zeros((H, W), bool),
             "initial_remaining_s_native": np.where(cur, R, 0.0)}
    inf = np.full((K, H, W), np.inf)
    _write_packet(tmp_path, inf, inf.copy(), masks, cur, R)
    _check(tmp_path)


def test_real_bridge_packet(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "integration" / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "forecast"))
    B = pytest.importorskip("wfg_latest.bridge")
    WH = pytest.importorskip("wildfire.heat")
    WH.validate_metric_crs = lambda c: int(c)    # pyproj is not installed here; only a CRS check
    fc = {
        "new_burn_probability": np.zeros((H, W)), "probability_valid": np.ones((H, W), bool),
        "rate_per_h": np.zeros((H, W)), "rate_valid": np.ones((H, W), bool),
        "source_burned_area": np.zeros((H, W)), "source_burned_area_valid": np.ones((H, W), bool),
        "heat__initial_active_burning_probability": np.zeros((H, W)),
        "heat__initial_remaining_burning_duration_s": np.zeros((H, W)),
        "heat__initial_burning_valid": np.ones((H, W), bool),
        "affine_transform": np.array([375.0, 0.0, 1000.0, 0.0, -375.0, 5000.0]),
    }
    fc["source_burned_area"][1, 1] = 1.0
    fc["heat__initial_active_burning_probability"][1, 1] = 1.0
    fc["heat__initial_remaining_burning_duration_s"][1, 1] = R
    B.CT.validate_raw(fc, T)                     # accepted
    built = B.construct(fc, cutoff_utc="2022-03-04T06:00:00Z", epsg=5179, settings=B.settings_for(T))
    assert all(bool(m["flame"][0][1, 1]) for m in built["members"])   # router: burning on [0, R_max)
    ext = np.stack([m["extinction_breakpoint_s"] for m in built["members"]])
    _write_packet(tmp_path, built["events"], ext, built["masks"], built["current"], built["remaining_s"])
    _check(tmp_path)
