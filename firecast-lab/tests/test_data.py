"""Real-data entry points: fail loudly without the data root. Everything read here is a SYNTHETIC data root."""
import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from firecast_lab import data as fd
from firecast_lab import domain as dm
from firecast_lab import splits as sp

CELL = 375.0


def _splits(**split_of):
    """A SYNTHETIC splits document holding only what the data module reads."""
    return dict(fires=[dict(id=i, split=s) for i, s in split_of.items()])


def _write_root(tmp_path, arrival, *, event_id="SYNTHETIC_A", nodata=-1.0, t0="2030-01-01T00:30:00+00:00",
                start="2030-01-01T00:00:00+00:00", end="2030-01-03T12:00:00+00:00"):
    """A SYNTHETIC data root: events.json plus regions/<id>/arrival_time_hours.tif (EPSG:5179, 375 m)."""
    h, w = arrival.shape
    transform = (CELL, 0.0, 1_000_000.0, 0.0, -CELL, 2_000_000.0)
    event = dict(id=event_id, name="SYNTHETIC", country="KR", year=2030, t0_utc=t0, start_utc=start, end_utc=end,
                 arrival_path=f"regions/{event_id}/arrival_time_hours.tif", width=w, height=h, epsg=5179,
                 transform=list(transform))
    region = tmp_path / "regions" / event_id
    region.mkdir(parents=True)
    with rasterio.open(region / "arrival_time_hours.tif", "w", driver="GTiff", height=h, width=w, count=1,
                       dtype="float32", crs="EPSG:5179", transform=Affine(*transform), nodata=nodata) as dst:
        dst.write(np.where(np.isfinite(arrival), arrival, nodata).astype("float32"), 1)
    (tmp_path / "events.json").write_text(json.dumps([event]))
    return tmp_path, event


def test_missing_data_root_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.delenv(fd.ENV_VAR, raising=False)
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        fd.data_root()
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        fd.data_root(tmp_path / "absent")
    with pytest.raises(fd.DataRootNotFound, match="metadata only"):
        fd.data_root(sp.CATALOG_PATH.parent)            # the repo copy has events.json but no regions/
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        fd.main([])                                     # the data check has no fallback either


def test_data_root_from_the_environment(monkeypatch, tmp_path):
    root, _ = _write_root(tmp_path, np.ones((3, 3)))
    monkeypatch.setenv(fd.ENV_VAR, str(root))
    assert fd.data_root() == root


def test_read_arrival_uses_the_nodata_tag_not_the_sign(tmp_path):
    arrival = np.array([[-0.5, 3.0], [np.nan, 10.0]])  # US-style: valid negative value, NoData stored as -1.0
    root, _ = _write_root(tmp_path, arrival)
    got, event = fd.read_arrival("SYNTHETIC_A", root, splits=_splits(SYNTHETIC_A="dev"))
    assert np.array_equal(got, arrival, equal_nan=True) and event["name"] == "SYNTHETIC"
    (root / "regions/SYNTHETIC_A/arrival_time_hours.tif").unlink()
    with pytest.raises(fd.DataRootNotFound, match="data root not found"):
        fd.read_arrival("SYNTHETIC_A", root, splits=_splits(SYNTHETIC_A="dev"))


def test_read_arrival_rejects_a_raster_off_the_event_grid(tmp_path):
    root, event = _write_root(tmp_path, np.ones((3, 4)))
    event["width"] = 5
    (root / "events.json").write_text(json.dumps([event]))
    with pytest.raises(ValueError, match="event grid"):
        fd.read_arrival("SYNTHETIC_A", root, splits=_splits(SYNTHETIC_A="dev"))


def test_test_and_holdout_fires_are_gated(tmp_path):
    root, _ = _write_root(tmp_path, np.ones((2, 2)))
    with pytest.raises(PermissionError, match="test fire"):
        fd.read_arrival("SYNTHETIC_A", root, splits=_splits(SYNTHETIC_A="test"))
    assert fd.read_arrival("SYNTHETIC_A", root, allow_test=True, splits=_splits(SYNTHETIC_A="test"))[0].shape == (2, 2)
    with pytest.raises(PermissionError, match="fresh_holdout"):
        fd.read_arrival("SYNTHETIC_A", root, allow_test=True, splits=_splits(SYNTHETIC_A="fresh_holdout"))
    with pytest.raises(ValueError, match="not in SPLITS"):
        fd.read_arrival("SYNTHETIC_A", root, splits=_splits(OTHER="dev"))
    with pytest.raises(PermissionError):                # the committed splits gate the real test fires too
        fd.check_access("KFS_01")


def test_window_cutoffs_follow_the_splits_rule():
    # t0 = 00:30, start = 00:00 (-0.5 h), end = start + 60 h (59.5 h). Cutoffs -0.5 + 12 k with cutoff + lead < 59.5.
    event = dict(t0_utc="2030-01-01T00:30:00+00:00", start_utc="2030-01-01T00:00:00+00:00",
                 end_utc="2030-01-03T12:00:00+00:00")
    early = np.array([[5.0, 20.0], [40.0, np.nan]])
    assert fd.window_cutoffs(early, event, 24) == [11.5, 23.5]
    assert fd.window_cutoffs(early, event, 12) == [11.5, 23.5, 35.5]
    late = np.array([[15.0, np.nan]])                   # nothing burned at 11.5 h: that cutoff is dropped
    assert fd.window_cutoffs(late, event, 24) == [23.5]
    assert sp.approx_windows(event["start_utc"], event["end_utc"], 24) == 2   # catalog-only approximation


def test_window_labels_keep_outside_cells_as_mapped_extent_negatives():
    arrival = np.array([2.0, 11.5, 12.0, 30.0, np.nan])
    s = fd.window_labels(arrival, cutoff_h=11.5, lead_h=12.0)
    assert s["final_perimeter"].tolist() == [True, True, True, True, False]
    assert s["burned_at_cutoff"].tolist() == [True, True, False, False, False]
    assert s["burned_at_end"].tolist() == [True, True, True, False, False]


def test_check_event_and_cli_record_provenance(tmp_path):
    arrival = np.full((30, 30), np.nan)
    arrival[:4, :4] = 5.0                               # SYNTHETIC fire in the grid's corner
    root, _ = _write_root(tmp_path, arrival)
    splits = _splits(SYNTHETIC_A="dev")
    row = fd.check_event(root, "SYNTHETIC_A", splits=splits)
    final = np.isfinite(arrival)
    domain = dm.headline_domain(final, CELL)
    assert row["final_perimeter_cells"] == 16 and row["headline_cells"] == domain.sum()
    assert row["ring_cells"] == domain.sum() - 16 and row["ring_cells_off_grid"] > 0
    assert (row["windows_24h"], row["windows_12h"]) == (2, 3)
    out = tmp_path / "check.json"
    assert fd.main(["--data-root", str(root), "--out", str(out)], splits=splits) == 0
    record = json.loads(out.read_text())
    assert record["rows"] == [row] and record["config"]["buffer_m"] == 3000.0
    assert record["host"] and {"commit", "dirty", "seed", "config"} <= set(record)
    assert record["commit"] is None or len(record["commit"]) == 40      # None outside a git checkout
