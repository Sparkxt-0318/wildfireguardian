"""Independent data loading, whole timelines, time selection and batch padding."""

import inspect
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import torch

from tests.loader.test_dataset import bundle
from wildfire import WildfireModel, WildfireSequenceDataset, collate_fire_sequences, load_data, select_time


TEMPORAL_FIELDS = (
    "features", "feature_valid", "feature_quality", "burned_area", "newly_burned_area",
    "burned_area_valid", "time_utc", "time_valid", "elapsed_hours",
    "source_interval_start_utc", "source_interval_end_utc",
)
START = "2021-07-15T06:00:00Z"
MIDDLE = "2021-07-15T07:00:00Z"
END = "2021-07-15T08:00:00Z"


def test_data_imports_and_loading_do_not_import_the_model_api(bundle):
    code = """
import importlib.abc
import sys

class BlockModelImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'wildfire.api', 'wildfire.models', 'wildfire.inference', 'wildfire.heat'}:
            raise AssertionError('Data loading imported ' + fullname)

sys.meta_path.insert(0, BlockModelImports())
from wildfire import load_data, select_time
assert load_data.__module__ == 'wildfire.data'
assert select_time.__module__ == 'wildfire.data'
with load_data(sys.argv[1], events=['KR_TEST'], sequence_length=None) as dataset:
    whole = dataset[0]
assert whole['features'].shape[0] == 3
assert select_time(whole, '2021-07-15T07:00:00Z')['features'].shape[0] == 1
assert 'wildfire.api' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code, str(bundle)],
                   cwd=Path(__file__).resolve().parents[1], check=True,
                   capture_output=True, text=True)


def test_model_has_no_loading_or_catalog_methods():
    for name in ("sample", "load_data", "available_events", "available_cutoffs"):
        assert not hasattr(WildfireModel, name)


def test_public_loader_exposes_every_dataset_option_with_identical_defaults():
    public = inspect.signature(load_data).parameters
    dataset = inspect.signature(WildfireSequenceDataset).parameters
    assert public.keys() == dataset.keys()
    for name, parameter in dataset.items():
        assert public[name].kind == parameter.kind
        assert public[name].default == parameter.default
    assert public["sequence_length"].default == 24


def test_default_loading_retains_24_step_windows(bundle):
    with load_data(bundle, events=["KR_TEST"]) as dataset:
        sample = dataset[0]
        assert len(dataset) == 1
        assert sample["features"].shape[0] == 24
        assert sample["time_valid"].tolist() == [True] * 3 + [False] * 21
        assert sample["time_utc"][3:].tolist() == [-1] * 21


def test_full_timeline_option_returns_one_whole_timeline_for_each_event(bundle):
    with load_data(bundle, sequence_length=None) as dataset:
        assert len(dataset) == 2 and dataset.event_ids == ("KR_TEST", "US_TEST")
        for index, event in enumerate(dataset.event_ids):
            sample = dataset[index]
            assert sample["event_id"] == event
            assert sample["features"].shape[0] == 3
            assert sample["time_valid"].tolist() == [True, True, True]
            assert sample["time_utc"].tolist() == [1_626_328_800, 1_626_332_400, 1_626_336_000]
            assert not (sample["feature_quality"] == 5).any()
            location = dataset.sample_location(index)
            assert location["valid_hours"] == 3
            assert location["start_utc"] == "2021-07-15T06:00:00+00:00"
            assert location["end_utc"] == "2021-07-15T08:00:00+00:00"
    assert not dataset._readers


def test_full_timeline_option_matches_all_explicit_hourly_windows(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as whole_dataset, \
            load_data(bundle, events=["KR_TEST"], sequence_length=1) as hourly_dataset:
        whole = whole_dataset[0]
        windows = [hourly_dataset[index] for index in range(len(hourly_dataset))]
        assert len(whole_dataset) == 1 and len(hourly_dataset) == 3
        for name in TEMPORAL_FIELDS:
            expected = torch.cat([window[name] for window in windows], dim=0)
            torch.testing.assert_close(whole[name], expected, rtol=0, atol=0, equal_nan=True)


def test_full_timeline_option_uses_the_whole_selected_range_and_one_sample_per_tile(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None, patch_size=2,
                   time_range=(MIDDLE, END)) as dataset:
        assert len(dataset) == 2
        assert [dataset.sample_location(index)["col"] for index in range(len(dataset))] == [0, 2]
        for index in range(len(dataset)):
            sample = dataset[index]
            assert sample["features"].shape == (2, len(dataset.channel_names), 2, 2)
            assert sample["time_valid"].tolist() == [True, True]
            assert sample["time_utc"].tolist() == [1_626_332_400, 1_626_336_000]
        assert not dataset[1]["pixel_valid"][:, :, 1].any()


def test_explicit_windows_retain_fixed_length_and_final_time_padding(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=2, patch_size=2) as dataset:
        assert len(dataset) == 4
        assert [dataset.sample_location(index)["valid_hours"] for index in range(4)] == [2, 1, 2, 1]
        last = dataset[1]
        assert last["features"].shape[0] == 2
        assert last["time_valid"].tolist() == [True, False]
        assert last["time_utc"].tolist() == [1_626_336_000, -1]
        assert (last["feature_quality"][1] == 5).all()
        assert not last["feature_valid"][1].any()


@pytest.mark.parametrize("stride", [1, 2, True])
def test_stride_requires_an_explicit_window_length(bundle, stride):
    with pytest.raises(ValueError, match="sequence_length|stride|whole"):
        load_data(bundle, sequence_length=None, temporal_stride=stride)


@pytest.mark.parametrize("length", [True, False, 0, -1, 1.5])
def test_window_length_must_be_none_or_a_positive_integer(bundle, length):
    with pytest.raises((TypeError, ValueError)):
        load_data(bundle, sequence_length=length)


def test_independent_loader_retains_nondefault_options_and_schema_controls(bundle):
    options = dict(events=["US_TEST"], sequence_length=2, temporal_stride=1,
                   patch_size=(2, 2), channels=("weather.temperature_2m", "vegetation.landcover_class"),
                   time_range=(MIDDLE, END), daily_policy="containing_day", fill_value=-7.0,
                   max_open_files=1, categorical_encoding="one_hot",
                   categorical_classes={"vegetation.landcover_class": [111, 200]})
    with load_data(bundle, **options) as public, WildfireSequenceDataset(bundle, **options) as direct:
        assert len(public) == len(direct) == 4
        assert public.channel_names == direct.channel_names
        assert public.daily_policy == "containing_day" and public.fill_value == -7
        assert public.categorical_classes["vegetation.landcover_class"] == (111, 200)
        for name in TEMPORAL_FIELDS + ("pixel_valid", "affine_transform", "categorical_channel"):
            torch.testing.assert_close(public[1][name], direct[1][name], rtol=0, atol=0, equal_nan=True)
        assert len(public._readers) <= 1


@pytest.mark.parametrize("backend", ["torch", "numpy"])
def test_select_time_keeps_singleton_time_axis_and_static_metadata(bundle, backend):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    if backend == "numpy":
        sample = {name: value.numpy() if isinstance(value, torch.Tensor) else value
                  for name, value in sample.items()}
    # Time selection must not guess from equal-length static dimensions.
    sample["static_extra"] = np.arange(3)
    selected = select_time(sample, "2021-07-15T16:00:00+09:00")
    assert isinstance(selected, dict)
    assert selected["features"].shape == (1, len(sample["channel_names"]), 2, 3)
    for name in TEMPORAL_FIELDS:
        np.testing.assert_array_equal(selected[name], sample[name][1:2])
    for name in ("arrival_hours", "coordinates", "affine_transform", "pixel_valid",
                 "channel_names", "categorical_channel", "event_id", "static_extra"):
        assert selected[name] is sample[name]
    assert sample["features"].shape[0] == 3


def test_select_time_is_inclusive_and_additional_label_masks_are_sliced(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    sample["newly_burned_area_valid"] = sample["burned_area_valid"].clone()
    selected = select_time(sample, MIDDLE, END)
    assert selected["time_utc"].tolist() == [1_626_332_400, 1_626_336_000]
    for name in (*TEMPORAL_FIELDS, "newly_burned_area_valid"):
        torch.testing.assert_close(selected[name], sample[name][1:3], rtol=0, atol=0, equal_nan=True)
    whole = select_time(sample, START, END)
    torch.testing.assert_close(whole["features"], sample["features"], rtol=0, atol=0, equal_nan=True)


@pytest.mark.parametrize("backend", ["torch", "numpy"])
@pytest.mark.parametrize("index,expected", [
    (0, 0), (1, 1), (-1, 2), (np.int64(1), 1), (torch.tensor(1, dtype=torch.int64), 1),
])
def test_select_loaded_time_index_preserves_inputs_outcomes_and_static_storage(bundle, backend, index, expected):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    sample["newly_burned_area_valid"] = sample["burned_area_valid"].clone()
    if backend == "numpy":
        sample = {name: value.numpy() if isinstance(value, torch.Tensor) else value
                  for name, value in sample.items()}
    sample["static_extra"] = np.arange(3)
    selected = select_time(sample, index=index)

    assert selected["features"].shape == (1, len(sample["channel_names"]), 2, 3)
    assert int(selected["time_utc"][0]) == int(sample["time_utc"][expected])
    for name in (*TEMPORAL_FIELDS, "newly_burned_area_valid"):
        np.testing.assert_array_equal(selected[name], sample[name][expected:expected + 1])
        if backend == "torch":
            assert selected[name].untyped_storage().data_ptr() == sample[name].untyped_storage().data_ptr()
        else:
            assert np.shares_memory(selected[name], sample[name])
    for name in ("arrival_hours", "coordinates", "affine_transform", "pixel_valid",
                 "channel_names", "categorical_channel", "event_id", "static_extra"):
        assert selected[name] is sample[name]
    assert sample["features"].shape[0] == 3
    assert not dataset._readers


@pytest.mark.parametrize("index", [
    True, False, np.bool_(True), torch.tensor(True), torch.tensor(False),
    1.0, 1.5, "1", slice(0, 1), (1,), [1],
])
def test_select_time_index_requires_an_integer_position(bundle, index):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    with pytest.raises(TypeError, match="index"):
        select_time(sample, index=index)


@pytest.mark.parametrize("index", [3, 48, -4])
def test_select_time_index_rejects_positions_outside_the_loaded_timeline(bundle, index):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    with pytest.raises(IndexError, match="index"):
        select_time(sample, index=index)


@pytest.mark.parametrize("options", [
    {"start": START, "index": 1},
    {"start": START, "end": END, "index": 1},
    {"end": END, "index": 1},
])
def test_select_time_rejects_mixing_timestamp_boundaries_with_a_position(bundle, options):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    with pytest.raises(ValueError, match="index|timestamp"):
        select_time(sample, **options)


def test_select_time_index_identifies_stored_positions_and_rejects_invalid_time_slots(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=4) as dataset:
        sample = dataset[0]
    sample["time_valid"][1] = False
    selected = select_time(sample, index=2)
    assert int(selected["time_utc"][0]) == 1_626_336_000
    for index in (1, 3, -1):
        with pytest.raises(ValueError, match="invalid|padding|valid"):
            select_time(sample, index=index)


@pytest.mark.parametrize("start,end", [
    ("2021-07-15T06:00:00", None), ("NaT", None), (None, None),
    ("2021-07-15T06:30:00Z", None), ("2021-07-15T09:00:00Z", None),
    (START, "2021-07-15T07:30:00Z"), (END, START),
    ("2021-07-15T06:00:00.000000001Z", None),
])
def test_select_time_rejects_nonfinite_naive_unavailable_or_reversed_boundaries(bundle, start, end):
    with load_data(bundle, events=["KR_TEST"], sequence_length=None) as dataset:
        sample = dataset[0]
    with pytest.raises((TypeError, ValueError)):
        select_time(sample, start, end)


def test_select_time_excludes_invalid_temporal_slots_and_preserves_real_times(bundle):
    with load_data(bundle, events=["KR_TEST"], sequence_length=4) as dataset:
        sample = dataset[0]
    selected = select_time(sample, START, END)
    assert selected["time_utc"].tolist() == [1_626_328_800, 1_626_332_400, 1_626_336_000]
    assert selected["time_valid"].all()
    with pytest.raises(ValueError):
        select_time(sample, "1969-12-31T23:59:59Z")
    sample["time_valid"][1] = False
    with pytest.raises(ValueError):
        select_time(sample, MIDDLE)


def test_collation_pads_time_and_space_independently_with_explicit_support(bundle):
    with load_data(bundle, sequence_length=None, fill_value=-7.0) as dataset:
        longer = dataset[0]
        shorter = select_time(dataset[1], START, MIDDLE)
    batch = collate_fire_sequences([longer, shorter])
    channels = longer["features"].shape[1]
    assert batch["features"].shape == (2, 3, channels, 3, 3)
    assert batch["time_valid"].tolist() == [[True, True, True], [True, True, False]]
    assert batch["time_utc"][1].tolist() == [1_626_328_800, 1_626_332_400, -1]
    assert torch.isnan(batch["elapsed_hours"][1, -1])
    assert (batch["source_interval_start_utc"][1, -1] == -1).all()
    assert (batch["source_interval_end_utc"][1, -1] == -1).all()
    assert not batch["feature_valid"][1, -1].any()
    assert not batch["burned_area_valid"][1, -1].any()
    assert (batch["burned_area"][1, -1] == 0).all()
    assert (batch["newly_burned_area"][1, -1] == 0).all()
    assert (batch["feature_quality"][1, -1] == 5).all()
    categorical = shorter["categorical_channel"]
    assert (batch["features"][1, -1, categorical] == 0).all()
    assert (batch["features"][1, -1, ~categorical] == -7).all()
    assert (batch["feature_quality"][0, :, :, 2] == 4).all()
    assert (batch["feature_quality"][1, :2, :, :, 2] == 4).all()
    assert batch["coordinates"].shape == (2, 2, 3, 3)
    assert torch.isnan(batch["coordinates"][0, :, 2]).all()
    assert torch.isnan(batch["coordinates"][1, :, :, 2]).all()
    for index, sample in enumerate((longer, shorter)):
        time, _, height, width = sample["features"].shape
        torch.testing.assert_close(batch["features"][index, :time, :, :height, :width],
                                   sample["features"], rtol=0, atol=0, equal_nan=True)
        torch.testing.assert_close(batch["feature_valid"][index, :time, :, :height, :width],
                                   sample["feature_valid"], rtol=0, atol=0)


def test_collation_pads_optional_new_burn_validity_in_time_and_space(bundle):
    with load_data(bundle, sequence_length=None) as dataset:
        longer = dataset[0]
        shorter = select_time(dataset[1], START, MIDDLE)
    for sample in (longer, shorter):
        sample["newly_burned_area_valid"] = sample["burned_area_valid"].clone()
    shorter["newly_burned_area_valid"][0, 0, 0, 0] = False
    batch = collate_fire_sequences([longer, shorter])
    assert batch["newly_burned_area_valid"].shape == (2, 3, 1, 3, 3)
    assert not batch["newly_burned_area_valid"][0, :, :, 2].any()
    assert not batch["newly_burned_area_valid"][1, :, :, :, 2].any()
    assert not batch["newly_burned_area_valid"][1, 2].any()
    assert not batch["newly_burned_area_valid"][1, 0, 0, 0, 0]
    for index, sample in enumerate((longer, shorter)):
        time, _, height, width = sample["features"].shape
        torch.testing.assert_close(batch["newly_burned_area_valid"][index, :time, :, :height, :width],
                                   sample["newly_burned_area_valid"], rtol=0, atol=0)
