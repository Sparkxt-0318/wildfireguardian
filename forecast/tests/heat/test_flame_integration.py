"""Model-bound flaming estimates keep checkpoint, labels and heat contracts."""

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

torch = pytest.importorskip("torch")

from wildfire.heat import AffineGrid
from wildfire.heat import CombustionParameters
from wildfire.heat import WildfireHeatModel
from wildfire.heat import active_flames_from_arrival
from wildfire.heat import FlameResidenceTime
from tests.test_api import checkpoint
from wildfire import load_model


@pytest.fixture
def snapshot():
    rng = np.random.default_rng(71)
    burned = np.zeros((1, 1, 7, 9), dtype=np.float32)
    burned[0, 0, 3, 4] = 1.0
    environment = rng.normal(size=(1, 2, 7, 9)).astype(np.float32)
    feature_valid = np.ones(environment.shape, dtype=bool)
    feature_valid[0, :, 2, 2] = False
    return burned, environment, feature_valid


def test_model_bound_flames_reuse_probability_masks_and_saved_preprocessing(checkpoint, snapshot):
    model = load_model(checkpoint)
    burned, environment, feature_valid = snapshot
    grid = AffineGrid((375.0, 0.0, 1000.0, 0.0, -375.0, 2000.0))
    duration = FlameResidenceTime(90.0, {"source": "test residence scenario"})
    original = model.predict_details(
        burned, environment, channel_names=model.channel_names, feature_valid=feature_valid,
    )
    # The probability adapter intentionally promotes the checkpoint's float32
    # values to float64 before evaluating seconds-based occupancy factors.
    q = original.probability.cpu().numpy().reshape(7, 9).astype(np.float64)
    valid = original.valid.cpu().numpy().reshape(7, 9).copy()
    old_burned = burned.reshape(7, 9) == 1
    q[old_burned] = 0.0
    valid[old_burned] = True
    result = model.predict_active_flames(
        burned, environment, channel_names=model.channel_names,
        residence_time=duration, grid=grid, feature_valid=feature_valid,
    )
    assert_array_equal(result.valid, valid)
    assert_allclose(result.new_burn_probability, q, rtol=0, atol=0, equal_nan=True)
    assert_allclose(result.endpoint.probability[valid], q[valid] * 90.0 / 3600.0, rtol=1e-14)
    assert_allclose(result.mean_active_probability[valid], q[valid] * (90.0 / 3600.0 - 0.5 * (90.0 / 3600.0) ** 2), rtol=1e-14)
    assert np.isnan(result.endpoint.probability[~valid]).all()
    assert result.endpoint.probability[3, 4] == 0.0
    assert result.interval_s == 3600.0
    assert result.endpoint.grid.transform == grid.transform
    assert result.metadata["predictor"]["checkpoint_sha256"] == model.checkpoint_sha256


def test_flame_forecast_uses_probability_instead_of_hourly_rate(checkpoint, snapshot):
    model = load_model(checkpoint)
    # Set the hourly rate above one. The occupancy bridge must consume the
    # exponential probability instead of interpreting a rate as a probability.
    with torch.no_grad():
        model.predictor.model.kernel_network[-1].weight.zero_()
        model.predictor.model.kernel_network[-1].bias.fill_(100.0)
    burned, environment, _ = snapshot
    original = model.predict_details(burned, environment, channel_names=model.channel_names)
    assert original.rate[0, 0, 3, 5].item() == 100.0
    assert original.probability[0, 0, 3, 5].item() == 1.0
    result = model.predict_active_flames(
        burned, environment, channel_names=model.channel_names,
        residence_time=FlameResidenceTime(60.0, {"source": "test scenario"}),
        grid=AffineGrid.from_cell_size(10.0),
    )
    assert result.endpoint.probability[3, 5] == pytest.approx(1.0 / 60.0)
    assert result.new_burn_probability[3, 5] == 1.0


def test_sample_flame_forecast_reads_current_inputs_and_absolute_time_metadata_only(checkpoint, snapshot):
    model = load_model(checkpoint)
    burned, environment, feature_valid = snapshot
    duration = FlameResidenceTime(60.0, {"source": "test scenario"})

    class CurrentInputs(dict):
        forbidden = {"arrival_hours", "arrival_valid", "arrival_std_hours", "newly_burned_area", "future_burned_area", "future_labels"}

        def __getitem__(self, name):
            assert name not in self.forbidden, f"forecast read retrospective field {name}"
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in self.forbidden, f"forecast read retrospective field {name}"
            return super().get(name, default)

    sample = CurrentInputs(
        burned_area=burned, features=environment, feature_valid=feature_valid,
        channel_names=model.channel_names, affine_transform=np.array([10.0, 1.0, 100.0, 0.0, -10.0, 200.0]),
        epsg=5070, time_utc=np.array([1_700_000_000], dtype=np.int64),
        arrival_hours=object(), arrival_valid=object(), arrival_std_hours=object(),
        newly_burned_area=object(), future_labels=object(),
    )
    result = model.predict_active_flames_sample(sample, residence_time=duration)
    assert result.metadata["epsg"] == 5070
    assert result.metadata["cutoff_unix_s"] == 1_700_000_000
    assert result.endpoint.metadata["endpoint_unix_s"] == 1_700_003_600
    assert result.endpoint.grid.transform == tuple(sample["affine_transform"])
    assert result.endpoint.time_s == 3600.0


def test_model_bound_flames_reject_multiple_spatial_snapshots(checkpoint, snapshot):
    model = load_model(checkpoint)
    burned, environment, _ = snapshot
    with pytest.raises(ValueError):
        model.predict_active_flames(
            np.repeat(burned, 2, axis=0), np.repeat(environment, 2, axis=0),
            channel_names=model.channel_names,
            residence_time=FlameResidenceTime(60.0, {"source": "test scenario"}),
            grid=AffineGrid.from_cell_size(10.0),
        )


def test_model_bound_flames_keep_original_channel_order_guard(checkpoint, snapshot):
    model = load_model(checkpoint)
    burned, environment, _ = snapshot
    with pytest.raises(ValueError, match="channel"):
        model.predict_active_flames(
            burned, environment, channel_names=model.channel_names[::-1],
            residence_time=FlameResidenceTime(60.0, {"source": "test scenario"}),
            grid=AffineGrid.from_cell_size(10.0),
        )


def test_literature_residence_duration_is_shared_by_heat_activity_and_source_strength():
    duration = FlameResidenceTime(np.array([[60.0, 120.0]]), {"source": "test scenario"})
    combustion = CombustionParameters.from_flame_residence(
        duration, fuel_load_kg_m2=1.0, heat_of_combustion_j_kg=18e6,
        consumed_fraction=0.5,
    )
    assert_array_equal(combustion.burning_duration_s, [[60.0, 120.0]])
    assert_array_equal(combustion.heat_release_rate_density_w_m2, [[150_000.0, 75_000.0]])
    model = WildfireHeatModel(
        None, grid=AffineGrid.from_cell_size(10.0), combustion=combustion,
        radiative_fraction=0.3, emission_height_m=5.0, residence_time=duration,
    )
    result = model.predict_from_new_burn_probability_details([[0.5, 0.6]])
    active = result.endpoint_flame_map()
    assert_allclose(active.probability, [[0.5 * 60 / 3600, 0.6 * 120 / 3600]], rtol=1e-14)
    assert_array_equal(active.valid, [[True, True]])
    assert active.metadata["residence_time"]["source"] == "test scenario"
    assert_array_equal(active.positions(min_probability=0.015).cells_rc, [[0, 1]])


def test_heat_model_rejects_inconsistent_flame_and_combustion_residence_durations():
    with pytest.raises(ValueError, match="duration"):
        WildfireHeatModel(
            None, grid=AffineGrid.from_cell_size(10.0),
            combustion=CombustionParameters(1.0, 18e6, 300.0, 0.5),
            radiative_fraction=0.3, emission_height_m=5.0,
            residence_time=FlameResidenceTime(60.0, {"source": "test scenario"}),
        )


def test_explicit_arrival_scenario_can_supply_present_flames_without_new_ignition_overlap():
    grid = AffineGrid.from_cell_size(10.0)
    duration = FlameResidenceTime(7200.0, {"source": "long-duration test scenario"})
    current = active_flames_from_arrival([[-60.0, 60.0]], duration, 0.0, grid=grid)
    combustion = CombustionParameters.from_flame_residence(
        duration, fuel_load_kg_m2=1.0, heat_of_combustion_j_kg=18e6, consumed_fraction=0.5,
    )
    model = WildfireHeatModel(
        None, grid=grid, combustion=combustion, residence_time=duration,
        radiative_fraction=0.3, emission_height_m=5.0,
    )
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, 0.2]], already_burned_mask=np.array([[True, False]]),
        initial_active_burning_probability=current.probability,
        initial_remaining_burning_duration_s=current.remaining_duration_s,
    )
    assert_array_equal(result.new_burn_probability, [[0.0, 0.2]])
    assert_allclose(result.endpoint_flame_map().probability, [[1.0, 0.2]], rtol=0, atol=0)
    assert_array_equal(result.endpoint_flame_map().positions(min_probability=0.9).cells_rc, [[0, 0]])
    assert result.complete


def test_padded_time_snapshot_is_rejected_before_predicting(checkpoint):
    model = load_model(checkpoint)
    sample = {
        "affine_transform": np.array([375.0, 0.0, 0.0, 0.0, -375.0, 0.0]),
        "time_valid": np.array([False]),
    }
    with pytest.raises(ValueError, match="unpadded"):
        model.predict_active_flames_sample(
            sample, residence_time=FlameResidenceTime(10.0, {"source": "test scenario"}),
        )


@pytest.mark.parametrize("epsg", [4326, 2227])
def test_sample_coordinate_crs_must_be_projected_in_metres(checkpoint, epsg):
    model = load_model(checkpoint)
    sample = {
        "affine_transform": np.array([375.0, 0.0, 0.0, 0.0, -375.0, 0.0]),
        "epsg": np.array(epsg),
    }
    with pytest.raises(ValueError, match="projected CRS in metres"):
        model.predict_active_flames_sample(
            sample, residence_time=FlameResidenceTime(10.0, {"source": "test scenario"}),
        )
