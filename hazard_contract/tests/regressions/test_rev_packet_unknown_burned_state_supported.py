# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""from_wfg_packet promises (docstring, program/DECISIONS.md) that cells whose native probability is
missing OR whose burned state is unknown become supported=False. It computes the unknown set as
mask__policy_assigned_zero & ~mask__known_burned only, i.e. it never reads
mask__unknown_cumulative_state and silently assumes unknown burned state => missing probability.

Nothing guarantees that: wfg_latest.contract.validate_raw accepts an export cell with a valid
native probability and an unknown burned state, and wfg_latest.bridge.construct then writes
policy_assigned_zero=False, unknown_cumulative_state=True and even draws ignitions from q there.
Such a cell (which may be burning right now: the bridge says it "is not a source ... counted as a
source-domain limitation") comes out supported=True, and a query on it reports contact=False,
supported=True.

test_hand_built_packet: masks computed with the bridge's own formulas (bridge.py construct).
test_real_bridge_packet: the same through the real wfg_latest bridge (skipped if not importable).
"""
from pathlib import Path
import json
import sys

import numpy as np
import pytest

import hazard_contract as hc

T = 3970.4642815249267
H, W, K = 3, 4, 4


def _write_packet(d, events, ext, masks, current, r_max, r_exact):
    arrays = {"ignition_time_s": events, "current_active": current, "support": np.ones((K, H, W), bool)}
    for k, v in masks.items():
        arrays["mask__" + k] = np.asarray(v)
    for s in range(K):
        arrays[f"member{s}__extinction_breakpoint_s"] = ext[s]
        arrays[f"member{s}__breakpoints_s"] = np.array([0.0, 3600.0])
    np.savez_compressed(d / "constructed_arrays.npz", **arrays)
    A = {"scenario_count": K, "seed": 20261008, "horizon_s": 3600.0, "initial_remaining_s": r_max,
         "initial_remaining_exact": r_exact, "fuel_load_kg_m2": 10.0, "heat_of_combustion_j_kg": 18608000.0,
         "burning_duration_s": T, "consumed_fraction": 0.1, "radiative_fraction": 0.3, "emission_height_m": 5.0,
         "receiver_height_m": 0.0, "atmospheric_transmissivity": 1.0}
    md = {"schema": "wfg.forecast.native-intervals/2", "bridge_version": "wfg.final-forecast-bridge/2.0-latest-c651",
          "crs": "EPSG:5179", "shape": [H, W], "affine_transform": [375.0, 0.0, 1000.0, 0.0, -375.0, 5000.0],
          "time_origin": "2022-03-04T06:00:00+00:00",
          "construction": {"assumptions": A, "scenario_ids": [f"m{k}" for k in range(K)]},
          "identity": {}, "regional": {"window_rows_cols_north_up": None}}
    (d / "NATIVE_METADATA.json").write_text(json.dumps(md))


def _raw_export():
    """An export that passes wfg_latest.contract.validate_raw: cell (0,1) has a valid native
    probability but an UNKNOWN burned state (source_burned_area_valid=False)."""
    fc = {
        "new_burn_probability": np.zeros((H, W)), "probability_valid": np.ones((H, W), bool),
        "rate_per_h": np.zeros((H, W)), "rate_valid": np.ones((H, W), bool),
        "source_burned_area": np.zeros((H, W)), "source_burned_area_valid": np.ones((H, W), bool),
        "heat__initial_active_burning_probability": np.zeros((H, W)),
        "heat__initial_remaining_burning_duration_s": np.zeros((H, W)),
        "heat__initial_burning_valid": np.ones((H, W), bool),
        "affine_transform": np.array([375.0, 0.0, 1000.0, 0.0, -375.0, 5000.0]),
    }
    fc["new_burn_probability"][0, 1] = 0.3
    fc["source_burned_area_valid"][0, 1] = False
    return fc


def _bridge_masks(fc):
    """Mask formulas copied from wfg_latest/bridge.py construct()."""
    valid, q = fc["probability_valid"], fc["new_burn_probability"]
    bvalid, burned = fc["source_burned_area_valid"], fc["source_burned_area"]
    known_burned = bvalid & (burned == 1)
    known_unburned = bvalid & (burned == 0)
    init_p, init_r, init_valid = (fc["heat__initial_active_burning_probability"],
                                  fc["heat__initial_remaining_burning_duration_s"], fc["heat__initial_burning_valid"])
    current_exact = init_valid & (init_p == 1) & known_burned
    unknown_age = known_burned & ~init_valid
    cq = np.where(valid, q, 0.0)
    cq[known_burned] = 0.0
    masks = {
        "probability_valid_native": valid, "policy_assigned_zero": ~valid,
        "structural_zero_native": valid & known_unburned & (q == 0),
        "positive_native_probability": valid & known_unburned & (q > 0),
        "known_burned": known_burned, "unknown_cumulative_state": ~bvalid,
        "present_fire_exact": current_exact, "present_fire_unknown_age_enclosed": unknown_age,
        "constructed_probability": cq,
        "initial_remaining_s_native": np.where(current_exact, init_r, np.where(unknown_age, np.nan, 0.0)),
    }
    return masks, current_exact | unknown_age


def _assert_unknown_state_cell_not_safe(d):
    try:
        s = hc.from_wfg_packet(d)
    except hc.ContractError:
        return                                   # refusing the packet is also honest
    c = s.grid.cell_centers(np.array([0]), np.array([1]))[0]
    for k, hz in enumerate(s.query(c, 0.0, 600.0)):
        assert not (hz.contact is False and hz.supported), (
            f"member {k}: cell with UNKNOWN burned state reads as safe: {hz}")
    assert not s.supported[:, 0, 1].any()


def test_hand_built_packet(tmp_path):
    fc = _raw_export()
    masks, current = _bridge_masks(fc)
    assert masks["unknown_cumulative_state"][0, 1] and not masks["policy_assigned_zero"][0, 1]
    events = np.full((K, H, W), np.inf)          # no member draws an ignition there
    ext = np.full((K, H, W), np.inf)
    _write_packet(tmp_path, events, ext, masks, current, 0.0, True)
    _assert_unknown_state_cell_not_safe(tmp_path)


def test_real_bridge_packet(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "integration" / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "forecast"))
    B = pytest.importorskip("wfg_latest.bridge")
    WH = pytest.importorskip("wildfire.heat")
    WH.validate_metric_crs = lambda c: int(c)    # pyproj is not installed here; only a CRS check
    fc = _raw_export()
    B.CT.validate_raw(fc, T)                     # the export is valid
    built = B.construct(fc, cutoff_utc="2022-03-04T06:00:00Z", epsg=5179, settings=B.settings_for(T))
    m = built["masks"]
    assert m["unknown_cumulative_state"][0, 1] and not m["policy_assigned_zero"][0, 1]
    ext = np.stack([mm["extinction_breakpoint_s"] for mm in built["members"]])
    _write_packet(tmp_path, built["events"], ext, m, built["current"], built["remaining_s"], built["remaining_exact"])
    _assert_unknown_state_cell_not_safe(tmp_path)
