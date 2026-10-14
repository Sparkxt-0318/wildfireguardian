"""Catalog discovery must select exact, complete hourly input sequences."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from wildfire import available_cutoffs, available_events


def write_catalog(root, events):
    root.mkdir(parents=True, exist_ok=True)
    (root / "events.json").write_text(json.dumps(events))
    return root


@pytest.fixture
def catalog(tmp_path):
    # Deliberately unsorted IDs, non-hour-aligned boundaries, and a fractional
    # endpoint distinguish the catalog grid from rounded UTC clock hours.
    return write_catalog(tmp_path, [
        {"id": "Z_LATE", "start_utc": "2024-08-23T02:00:00Z",
         "end_utc": "2024-08-23T06:45:00Z"},
        {"id": "A_EARLY", "start_utc": "2024-08-23T00:00:00Z",
         "end_utc": "2024-08-23T02:00:00Z"},
        {"id": "HALF", "start_utc": "2024-08-23T00:30:00Z",
         "end_utc": "2024-08-23T02:45:00Z"},
        {"id": "NANO", "start_utc": "2024-08-23T00:00:00.000000123Z",
         "end_utc": "2024-08-23T01:00:00.000000124Z"},
    ])


def test_events_preserve_catalog_order_and_require_a_complete_sequence(catalog):
    assert available_events(data_root=catalog) == ["Z_LATE", "A_EARLY", "HALF", "NANO"]
    assert available_events(data_root=catalog, sequence_length=3) == ["Z_LATE", "A_EARLY", "HALF"]
    assert available_events(data_root=catalog, sequence_length=6) == []
    assert available_events("2024-08-23T02:00:00Z", data_root=catalog) == ["Z_LATE", "A_EARLY"]
    assert available_events("2024-08-23T02:00:00Z", data_root=catalog, sequence_length=2) == ["Z_LATE"]
    assert available_events("2024-08-23T01:30:00Z", data_root=catalog, sequence_length=2) == ["HALF"]
    assert available_events("2024-08-23T00:01:00Z", data_root=catalog) == []
    assert available_events("2024-08-24T00:00:00Z", data_root=catalog) == []


def test_cutoffs_are_exact_hourly_starts_with_inclusive_endpoints(catalog):
    assert available_cutoffs("A_EARLY", data_root=catalog) == [
        "2024-08-23T00:00:00Z", "2024-08-23T01:00:00Z", "2024-08-23T02:00:00Z",
    ]
    assert available_cutoffs("A_EARLY", data_root=catalog, sequence_length=2) == [
        "2024-08-23T00:00:00Z", "2024-08-23T01:00:00Z",
    ]
    assert available_cutoffs("HALF", data_root=catalog, sequence_length=2) == [
        "2024-08-23T00:30:00Z", "2024-08-23T01:30:00Z",
    ]
    assert available_cutoffs("Z_LATE", data_root=catalog)[-1] == "2024-08-23T06:00:00Z"
    assert available_cutoffs("A_EARLY", data_root=catalog, sequence_length=4) == []


def test_nanosecond_grid_does_not_admit_nearly_equal_cutoffs(catalog):
    assert available_cutoffs("NANO", data_root=catalog) == [
        "2024-08-23T00:00:00.000000123Z", "2024-08-23T01:00:00.000000123Z",
    ]
    assert available_events("2024-08-23T00:00:00.000000123Z", data_root=catalog) == ["NANO"]
    assert available_events("2024-08-23T00:00:00.000000124Z", data_root=catalog) == []
    assert available_events("2024-08-23T01:00:00.000000123Z", data_root=catalog, sequence_length=2) == []


def test_timezones_and_naive_cutoffs_use_the_same_utc_instant(catalog):
    expected = ["Z_LATE", "A_EARLY"]
    assert available_events("2024-08-23T11:00:00+09:00", data_root=catalog) == expected
    assert available_events("2024-08-23T02:00:00", data_root=catalog) == expected
    assert available_cutoffs("HALF", data_root=catalog, time_range=(
        "2024-08-23T09:30:00+09:00", "2024-08-23T10:30:00+09:00",
    )) == ["2024-08-23T00:30:00Z", "2024-08-23T01:30:00Z"]


def test_range_limits_sequence_starts_and_keeps_supported_following_times(catalog):
    assert available_cutoffs("HALF", data_root=catalog, sequence_length=2, time_range=(
        "2024-08-23T01:30:00Z", "2024-08-23T01:30:00Z",
    )) == ["2024-08-23T01:30:00Z"]
    assert available_cutoffs("A_EARLY", data_root=catalog, time_range=(
        "2024-08-23T00:30:00", "2024-08-23T01:30:00",
    )) == ["2024-08-23T01:00:00Z"]
    assert available_cutoffs("A_EARLY", data_root=catalog, time_range=(
        "2024-08-24T00:00:00Z", "2024-08-24T01:00:00Z",
    )) == []


@pytest.mark.parametrize("sequence_length", [True, 1.5, 0, -1])
def test_invalid_sequence_length_is_rejected_by_both_helpers(catalog, sequence_length):
    with pytest.raises((TypeError, ValueError)):
        available_events(data_root=catalog, sequence_length=sequence_length)
    with pytest.raises((TypeError, ValueError)):
        available_cutoffs("A_EARLY", data_root=catalog, sequence_length=sequence_length)


@pytest.mark.parametrize("cutoff", ["", "not a timestamp", "NaT", 1724371200])
def test_invalid_cutoff_is_rejected(catalog, cutoff):
    with pytest.raises((TypeError, ValueError)):
        available_events(cutoff, data_root=catalog)


@pytest.mark.parametrize("time_range", [
    "2024-08-23T00:00:00Z",
    ("2024-08-23T00:00:00Z",),
    ("not a timestamp", "2024-08-23T01:00:00Z"),
    ("2024-08-23T02:00:00Z", "2024-08-23T01:00:00Z"),
    (None, "2024-08-23T01:00:00Z"),
])
def test_invalid_time_range_is_rejected(catalog, time_range):
    with pytest.raises((TypeError, ValueError)):
        available_cutoffs("A_EARLY", data_root=catalog, time_range=time_range)


def test_unknown_event_and_missing_catalog_have_clear_failures(catalog, tmp_path):
    with pytest.raises(ValueError, match="[Uu]nknown"):
        available_cutoffs("MISSING", data_root=catalog)
    with pytest.raises(FileNotFoundError):
        available_events(data_root=tmp_path / "missing")
    with pytest.raises(FileNotFoundError):
        available_cutoffs("A_EARLY", data_root=tmp_path / "missing")


@pytest.mark.parametrize("events", [
    {},
    ["bad entry"],
    [{"id": "", "start_utc": "2024-08-23T00:00:00Z", "end_utc": "2024-08-23T01:00:00Z"}],
    [{"id": "A", "start_utc": "2024-08-23T01:00:00Z", "end_utc": "2024-08-23T00:00:00Z"}],
    [{"id": "A", "start_utc": "bad", "end_utc": "2024-08-23T00:00:00Z"}],
    [{"id": "A", "start_utc": "2024-08-23T00:00:00Z"}],
    [{"id": "A", "start_utc": "2024-08-23T00:00:00Z", "end_utc": "2024-08-23T00:00:00Z"}] * 2,
])
def test_malformed_catalogs_are_rejected(tmp_path, events):
    root = write_catalog(tmp_path, events)
    with pytest.raises((TypeError, ValueError)):
        available_events(data_root=root)
    with pytest.raises((TypeError, ValueError)):
        available_cutoffs("A", data_root=root)


def test_empty_catalog_returns_no_events(tmp_path):
    root = write_catalog(tmp_path, [])
    assert available_events(data_root=root) == []
    with pytest.raises(ValueError, match="[Uu]nknown"):
        available_cutoffs("A", data_root=root)


def test_top_level_discovery_needs_no_rasters_models_or_plotting(catalog):
    code = """
import importlib.abc
import sys

class BlockHeavyImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'rasterio', 'matplotlib'}:
            raise AssertionError('Discovery imported ' + fullname)

sys.meta_path.insert(0, BlockHeavyImports())
from wildfire import available_events, available_cutoffs
assert available_events(data_root=sys.argv[1]) == ['Z_LATE', 'A_EARLY', 'HALF', 'NANO']
assert available_cutoffs('A_EARLY', data_root=sys.argv[1])[-1] == '2024-08-23T02:00:00Z'
assert not any(name in sys.modules for name in ('torch', 'rasterio', 'matplotlib'))
"""
    subprocess.run([sys.executable, "-c", code, str(catalog)],
                   cwd=Path(__file__).resolve().parents[1], check=True,
                   capture_output=True, text=True)


def test_public_discovery_is_independent_of_model_state(catalog):
    from wildfire.api import WildfireModel
    from wildfire.api import available_cutoffs as api_cutoffs
    from wildfire.api import available_events as api_events

    assert api_events is available_events
    assert api_cutoffs is available_cutoffs
    # Discovery belongs to the data catalog, independently of model state.
    model = WildfireModel.__new__(WildfireModel)
    assert not hasattr(model, "available_events") and not hasattr(model, "available_cutoffs")
    assert api_events("2024-08-23T02:00:00Z", data_root=catalog,
                      sequence_length=2) == ["Z_LATE"]
    assert api_cutoffs("HALF", data_root=catalog, sequence_length=2,
                       time_range=("2024-08-23T01:00:00Z", "2024-08-23T02:00:00Z")) == [
        "2024-08-23T01:30:00Z",
    ]


def test_discovered_cutoffs_load_complete_sequences_at_the_same_timestamps(tmp_path):
    import pandas as pd
    from tests.loader.test_dataset import bundle
    from wildfire import load_data

    root = bundle.__wrapped__(tmp_path / "data")
    assert available_events(data_root=root) == ["KR_TEST", "US_TEST"]
    cutoffs = available_cutoffs("KR_TEST", data_root=root, sequence_length=2)
    assert cutoffs == ["2021-07-15T06:00:00Z", "2021-07-15T07:00:00Z"]
    for cutoff in cutoffs:
        start = pd.Timestamp(cutoff)
        end = start + pd.Timedelta(hours=1)
        with load_data(root, events=["KR_TEST"], sequence_length=2,
                       time_range=(start.isoformat(), end.isoformat())) as dataset:
            assert len(dataset) == 1
            sample = dataset[0]
        assert sample["time_valid"].tolist() == [True, True]
        assert sample["time_utc"].tolist() == [int(start.timestamp()), int(end.timestamp())]

