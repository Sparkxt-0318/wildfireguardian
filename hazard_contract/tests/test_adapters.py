"""Adapters: synthetic, drawn zones, perimeters, wfg packets."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from hazard_contract import ContractError, from_drawn_zones, from_perimeters, from_wfg_packet, synthetic

INF, NAN = np.inf, np.nan
GRID = dict(transform=(100.0, 0.0, 0.0, 0.0, -100.0, 1000.0), height=10, width=10, crs_epsg=3310,
            issue_time_utc="2021-08-18T00:00:00Z")


def test_synthetic_is_labeled_valid_and_coherent():
    s = synthetic(K=4, height=30, width=30, seed=1)
    assert s.meta.synthetic and s.meta.source == "synthetic" and s.meta.weather_source == "SYNTHETIC"
    assert s.K == 4 and not np.array_equal(s.ignite_s[0], s.ignite_s[1])
    mid = s.ignite_s[:, 15, 15]
    assert np.all(mid <= s.ignite_s[:, 15, 25])           # arrival grows away from the ignition
    s2 = synthetic(K=4, height=30, width=30, seed=1)
    np.testing.assert_array_equal(s.ignite_s, s2.ignite_s)  # seeded


def test_drawn_zones_spread_and_burn_at_issue():
    zone = np.array([[400.0, 400.0], [600.0, 400.0], [600.0, 600.0], [400.0, 600.0]])
    s = from_drawn_zones(zone, [1.0, 0.5], horizon_s=3600.0, burn_duration_s=600.0, **GRID)
    assert s.K == 2 and s.meta.source == "drawn"
    assert s.ignite_s[0, 5, 5] == -INF and s.extinguish_s[0, 5, 5] == 600.0
    # cell (5, 8) spans x 800..900; nearest zone point x = 600 -> 200 m
    assert s.ignite_s[0, 5, 8] == pytest.approx(200.0) and s.ignite_s[1, 5, 8] == pytest.approx(400.0)
    assert s.member(0).segment(np.array([500.0, 500.0]), 0.0, 1.0).contact is True


def test_perimeters_bracket_arrival_and_respect_horizon():
    p1 = np.zeros((10, 10), bool); p1[4:6, 4:6] = True
    p2 = np.zeros((10, 10), bool); p2[3:7, 3:7] = True
    series = [(-600.0, p1), (1200.0, p2)]
    s = from_perimeters(series, 900.0, K=4, mode="stratified", **GRID)
    assert s.meta.horizon_s == 1200.0 and s.meta.source == "perimeter"
    assert np.all(s.ignite_s[:, 4, 4] == -INF) and np.all(s.extinguish_s[:, 4, 4] == -600.0 + 900.0)
    ring = s.ignite_s[:, 3, 3]
    assert np.all((ring > -600.0) & (ring <= 1200.0)) and len(set(ring.tolist())) == 4
    assert np.all(s.ignite_s[:, 0, 0] == INF)             # never inside a perimeter
    env = from_perimeters(series, 900.0, K=1, mode="envelope", **GRID)
    assert env.ignite_s[0, 3, 3] == -600.0 and env.extinguish_s[0, 3, 3] == 1200.0 + 900.0
    assert np.all(env.ignite_s[0, 3, 3] <= ring) and np.all(env.extinguish_s[0, 3, 3] >= s.extinguish_s[:, 3, 3])
    with pytest.raises(ContractError):
        from_perimeters(series, 900.0, horizon_s=5000.0, **GRID)
    mapped = np.ones((10, 10), bool); mapped[9, :] = False
    sm = from_perimeters(series, 900.0, mapped_mask=mapped, **GRID)
    assert not sm.supported[:, 9, :].any() and np.isnan(sm.ignite_s[:, 9, 0]).all()


def test_perimeter_polygons_are_rasterized_all_touched():
    ring = np.array([[410.0, 410.0], [590.0, 410.0], [590.0, 590.0], [410.0, 590.0]])
    s = from_perimeters([(0.0, ring), (600.0, ring * 0 + np.array([[300.0, 300.0], [700.0, 300.0], [700.0, 700.0], [300.0, 700.0]]))],
                        300.0, K=2, **GRID)
    assert np.all(s.ignite_s[:, 4:6, 4:6] == -INF)


def write_fake_packet(d: Path) -> None:
    """A 3x4 packet with every cell class of wfg.forecast.native-intervals/2."""
    K, H, W, T = 2, 3, 4, 1000.0
    ig = np.full((K, H, W), INF)
    ig[0, 0, 0], ig[1, 0, 1] = 100.0, 200.0                       # new ignitions
    ex = np.where(np.isfinite(ig), ig + T, INF)
    cur = np.zeros((H, W), bool); cur[1, 1] = cur[1, 2] = True    # present fire
    rem = np.zeros((H, W)); rem[1, 1] = 300.0; rem[1, 2] = NAN      # exact age / unknown age
    known_burned = cur.copy(); known_burned[2, 0] = True          # (2,0) burned out
    pz = np.zeros((H, W), bool); pz[2, 3] = pz[0, 3] = True       # missing probability -> unknown
    arrays = {
        "ignition_time_s": ig, "current_active": cur, "support": np.ones((K, H, W), bool),
        "mask__known_burned": known_burned, "mask__policy_assigned_zero": pz,
        "mask__unknown_cumulative_state": np.zeros((H, W), bool),
        "mask__initial_remaining_s_native": rem,
    }
    for k in range(K):
        arrays[f"member{k}__extinction_breakpoint_s"] = ex[k]
    np.savez_compressed(d / "constructed_arrays.npz", **arrays)
    md = {
        "schema": "wfg.forecast.native-intervals/2", "bridge_version": "test",
        "crs": "EPSG:5179", "shape": [H, W], "affine_transform": [375.0, 0, 1000.0, 0, -375.0, 5000.0],
        "time_origin": "2022-03-04T06:00:00+00:00",
        "construction": {"assumptions": {
            "scenario_count": K, "seed": 1, "horizon_s": 3600.0, "initial_remaining_s": 300.0,
            "fuel_load_kg_m2": 10.0, "heat_of_combustion_j_kg": 18608000.0, "burning_duration_s": T,
            "consumed_fraction": 0.1, "radiative_fraction": 0.3, "emission_height_m": 5.0,
            "receiver_height_m": 0.0, "atmospheric_transmissivity": 1.0},
            "scenario_ids": ["m0", "m1"]},
        "identity": {"checkpoint_sha256": "c651f6724fe6"}, "regional": {"region_id": "test", "event_id": "X"},
    }
    (d / "NATIVE_METADATA.json").write_text(json.dumps(md))


def test_wfg_packet_mapping_applies_rule4(tmp_path):
    write_fake_packet(tmp_path)
    s = from_wfg_packet(tmp_path)
    assert s.meta.source == "packet" and not s.meta.synthetic and s.meta.horizon_s == 3600.0
    assert s.ignite_s[0, 0, 0] == 100.0 and s.extinguish_s[0, 0, 0] == 1100.0 and s.ignite_s[1, 0, 0] == INF
    assert np.all(s.ignite_s[:, 1, 1] == 300.0 - 1000.0) and np.all(s.extinguish_s[:, 1, 1] == 300.0)
    assert np.all(s.ignite_s[:, 1, 2] == -1000.0) and np.all(s.extinguish_s[:, 1, 2] == 1000.0)
    assert np.all(s.ignite_s[:, 2, 0] == -INF) and np.all(s.extinguish_s[:, 2, 0] == 0.0)
    assert not s.supported[:, 2, 3].any() and not s.supported[:, 0, 3].any()
    assert np.isnan(s.ignite_s[:, 2, 3]).all() and s.supported[:, 0, 0].all()
    h = s.meta.heat_source
    assert h.emission_kw_m2(h.burn_duration_s) == pytest.approx(0.3 * 10 * 0.1 * 18608 / 1000.0)
    enc = from_wfg_packet(tmp_path, present_fire="enclosure")
    assert enc.extinguish_s[0, 1, 1] == 300.0 and enc.extinguish_s[0, 1, 2] == 1000.0


REAL = os.environ.get("WFG_ROUTING_INPUTS")


@pytest.mark.skipif(not REAL, reason="set WFG_ROUTING_INPUTS to the fetched routing inputs to run")
def test_real_uljin_packet():
    d = Path(REAL) / "latest_inputs_try02/packets/uljin_2022/20220304T060000Z"
    s = from_wfg_packet(d)
    assert s.shape == (4, 62, 58)
    assert (~s.supported[0]).sum() == 2529           # missing native probability or unknown state
    assert s.meta.extra["n_present_fire_cells"] == 26
    q = s.meta.heat_source.emission_kw_m2(s.meta.heat_source.burn_duration_s)
    assert q == pytest.approx(1.405981669694301, rel=1e-12)


def test_envelope_refuses_interval_policy():
    """Review finding: stretching intervals dilutes C/duration, so an envelope is only conservative
    under the scalar policy."""
    from hazard_contract import HeatSource
    p1 = np.zeros((10, 10), bool); p1[4:6, 4:6] = True
    p2 = np.zeros((10, 10), bool); p2[3:7, 3:7] = True
    heat = HeatSource(fuel_load_kg_m2=10, consumed_fraction=0.1, heat_content_kj_kg=18608, radiative_fraction=0.3,
                      burn_duration_s=600.0, burn_duration_policy="interval")
    with pytest.raises(ValueError):
        from_perimeters([(0.0, p1), (3600.0, p2)], 600.0, K=1, mode="envelope", heat=heat, **GRID)
