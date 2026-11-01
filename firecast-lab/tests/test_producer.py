"""hazard_contract v1 producer: round trip through ScenarioSet.read on SYNTHETIC members, present fire, support."""
import json

import numpy as np
import pytest
from hazard_contract import CONTRACT_VERSION, ScenarioSet

import synthetic as syn
from firecast_lab import baselines as bl
from firecast_lab import producer as pr

T = pr.PACKET_HEAT.burn_duration_s


def _centre(transform, row, col):
    a, _, x0, _, e, y0 = transform
    return np.array([[x0 + (col + 0.5) * a, y0 + (row + 0.5) * e]])


def test_packet_heat_source_matches_the_repo_packets():
    assert pr.PACKET_HEAT.emission_kw_m2(T) == pytest.approx(1.406, abs=5e-4)   # hazard_contract README value
    assert (pr.PACKET_HEAT.fuel_load_kg_m2, pr.PACKET_HEAT.consumed_fraction, pr.PACKET_HEAT.heat_content_kj_kg,
            pr.PACKET_HEAT.radiative_fraction, pr.PACKET_HEAT.transmissivity, pr.PACKET_HEAT.emission_height_m,
            pr.PACKET_HEAT.receiver_height_m, T) == (10.0, 0.1, 18608.0, 0.3, 1.0, 5.0, 0.0, 3970.4642815249267)


def test_round_trip_of_baseline_members(tmp_path):
    train = syn.windows("SYNTHETIC_0", *syn.fire(seed=0)) + syn.windows("SYNTHETIC_1", *syn.fire(seed=1))
    window = syn.windows("SYNTHETIC_2", *syn.fire(seed=2))[1]
    model = bl.Logistic(rows_per_class=100).fit(train)
    hours = bl.members(model, window, K=6, seed=3)
    config = dict(baseline="logistic", K=6, coupling="shared")
    written = pr.write(tmp_path / "set", pr.from_window(window, hours, model=model, seed=3, config=config))
    s = ScenarioSet.read(written)
    known = ~np.isnan(hours)
    assert np.array_equal(s.supported, known)
    assert np.array_equal(s.ignite_s[known], hours[known] * 3600.0)
    assert np.array_equal(s.extinguish_s[known], hours[known] * 3600.0 + T)
    assert np.isnan(s.ignite_s[~known]).all() and np.isnan(s.extinguish_s[~known]).all()
    meta = s.meta
    assert (meta.source, meta.synthetic, meta.K, meta.horizon_s) == ("model", True, 6, 24 * 3600.0)
    assert meta.issue_time_utc.isoformat().startswith(window.cutoff_utc[:19])
    assert meta.model_version.endswith("logistic") and "wind" in meta.weather_source
    assert meta.heat_source == pr.PACKET_HEAT and meta.crs_epsg == 5179 and meta.transform == window.transform
    assert {"commit", "seed", "config", "host"} <= set(meta.provenance) and meta.provenance["seed"] == 3
    assert meta.provenance["config"] == config and meta.extra["fire"] == "SYNTHETIC_2"
    assert "outside the reconstruction domain" in meta.extra["support_policy"]
    assert json.loads((written / "meta.json").read_text())["contract_version"] == CONTRACT_VERSION


def test_present_fire_unknown_age_and_unknown_cells(tmp_path):
    # SYNTHETIC 1 x 5 grid: burned 0.5 h before the cutoff, burned 10 h before, age unknown, never, unknown.
    hours = np.array([[[-0.5, -10.0, -np.inf, np.inf, np.nan]]])
    transform = (375.0, 0.0, 0.0, 0.0, -375.0, 375.0)
    s = pr.scenario_set(hours, transform=transform, crs_epsg=5179, issue_time_utc="2030-01-01T12:00:00Z",
                        horizon_h=24, model_version="SYNTHETIC", weather_source="none", seed=0, config={},
                        synthetic=True)
    assert np.allclose(s.ignite_s[0, 0, :4], [-1800.0, -36000.0, -T, np.inf])
    assert np.allclose(s.extinguish_s[0, 0, :4], [-1800.0 + T, -36000.0 + T, T, np.inf])
    assert s.supported[0, 0].tolist() == [True, True, True, True, False]
    m0 = s.member(0)
    assert m0.segment(_centre(transform, 0, 0), 0.0, 60.0).contact is True         # still burning at issue
    assert m0.segment(_centre(transform, 0, 1), 0.0, 60.0).contact is False        # burned out before issue
    assert m0.segment(_centre(transform, 0, 2), 0.0, 60.0).contact is True         # unknown age: [-T, T)
    assert m0.segment(_centre(transform, 0, 3), 0.0, 60.0).contact is False
    hz = m0.segment(_centre(transform, 0, 4), 0.0, 60.0)
    assert hz.supported is False and hz.contact is None                            # unknown is never safe
    reread = ScenarioSet.read(pr.write(tmp_path / "s", s))
    assert np.array_equal(reread.ignite_s, s.ignite_s, equal_nan=True) and reread.meta == s.meta
    assert s.meta.extra["unsupported_cells"] == 1 and s.meta.extra["edge_burning_members"] == 1


def test_producer_validates_members():
    kwargs = dict(transform=(375.0, 0.0, 0.0, 0.0, -375.0, 375.0), crs_epsg=5179,
                  issue_time_utc="2030-01-01T12:00:00Z", horizon_h=24, model_version="SYNTHETIC",
                  weather_source="none", seed=0, config={}, synthetic=True)
    with pytest.raises(ValueError, match="beyond the horizon"):
        pr.scenario_set(np.array([[[25.0]]]), **kwargs)
    with pytest.raises(ValueError, match=r"\[K, H, W\]"):
        pr.scenario_set(np.array([[1.0]]), **kwargs)
    s = pr.scenario_set(np.array([[[3.0, 4.0]]]), np.array([[True, False]]), **kwargs)
    assert s.supported.tolist() == [[[True, False]]] and np.isnan(s.ignite_s[0, 0, 1])
