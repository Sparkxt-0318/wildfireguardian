import hashlib
import json
import numpy as np
import pytest
from wfg_synthetic_truth.adapters import GridSpec, utc_seconds, reconstructed_arrival, observed_perimeters, external_simulator


@pytest.fixture
def grid():
    return GridSpec((2, 2), (100., 0., 0., 0., -100., 200.), 3857)


def test_clock_grid_and_identity_guards(grid):
    assert utc_seconds("2025-01-01T01:00:00+01:00") == utc_seconds("2025-01-01T00:00:00Z")
    for bad in ("2025-01-01T00:00:00", "2025-01-01T00:00:00.1Z", True, 1.5):
        with pytest.raises(ValueError): utc_seconds(bad)
    with pytest.raises(ValueError): GridSpec((2, 2), (100, 0, 0, 0, 100, 0), 3857)
    with pytest.raises(ValueError): GridSpec((2, 2), (1, 0, 0, 0, -1, 0), 4326)
    with pytest.raises(ValueError): grid.require_alignment((2, 2), (100, 0, 1, 0, -100, 200), 3857)


def write_farsite(tmp_path, grid, *, coverage=None, raw=None, units="minutes"):
    p = tmp_path/"prediction.npz"; r = tmp_path/"reference.npz"
    np.savez(r, burned_area=np.zeros((2, 1, 2, 2)), affine_transform=grid.affine, epsg=grid.epsg,
             time_utc=np.array(["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"]))
    np.savez(p, arrival_minutes=np.array([[0., 2.], [-9999., 7.]]) if raw is None else raw,
             valid=np.ones((1, 1, 2, 2), bool) if coverage is None else coverage,
             affine_transform=grid.affine, epsg=grid.epsg,
             metadata_json=json.dumps(dict(model_family="FARSITE", method="farsite_deterministic", exact_duration_minutes=10, arrival_units=units, arrival_origin_time_utc="2025-01-01T00:00:00Z", no_burn_value=-9999., grid_alignment="caller_verified_no_resampling_in_importer")))
    return p, r


def test_external_units_never_missingness_alignment_and_holdout(tmp_path, grid):
    p, r = write_farsite(tmp_path, grid)
    kwargs = dict(reference_path=r, cutoff_utc="2025-01-01T00:00:00Z", source_id="heldout-fire")
    t = external_simulator(p, **kwargs)
    assert t.lower_s[0, 1] == 120 and t.lower_s[1, 0] == 600 and np.isinf(t.upper_s[1, 0])
    assert t.censored[1, 0] and not t.never.any()
    assert t.exact_ignition()["status"] == "UNSCORABLE"
    bounded = t.exact_ignition(horizon_s=600)
    assert bounded["status"] == "MODEL_RELATIVE_BOUNDED_ARRIVAL_ONLY"
    assert bounded["valid_until_s"] == 600 and np.isinf(bounded["ignition_time_s"][1, 0])
    assert t.exact_ignition(horizon_s=601)["status"] == "UNSCORABLE"
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    for extra in (dict(planning_ids=["heldout-fire"]), dict(planning_hashes=[digest]), dict(expected_sha256="0"*64)):
        with pytest.raises(ValueError): external_simulator(p, **kwargs, **extra)
    cover = np.array([[[[True, True], [False, False]]]])
    write_farsite(tmp_path, grid, coverage=cover)
    t = external_simulator(p, **kwargs)
    assert np.isnan(t.lower_s[1]).all() and not t.never.any()
    assert t.exact_ignition()["status"] == "UNSCORABLE"
    write_farsite(tmp_path, grid, coverage=cover.astype(int))
    with pytest.raises(ValueError): external_simulator(p, **kwargs)
    write_farsite(tmp_path, grid, units="hours")
    with pytest.raises(ValueError): external_simulator(p, **kwargs)
    write_farsite(tmp_path, grid, raw=np.array([[0., -5.], [-9999., 7.]]))
    with pytest.raises(ValueError): external_simulator(p, **kwargs)


def tif(path, grid, values):
    rio = pytest.importorskip("rasterio")
    from rasterio.transform import Affine
    with rio.open(path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float64", crs="EPSG:3857", transform=Affine(*grid.affine), nodata=-9999) as ds:
        ds.write(np.array(values, dtype=float), 1)


def test_reconstructed_units_native_orientation_nodata_and_sd(tmp_path, grid):
    p = tmp_path/"arrival.tif"; s = tmp_path/"sd.tif"
    tif(p, grid, [[0, 1], [2, -9999]]); tif(s, grid, [[.1, .2], [.3, .4]])
    args = dict(grid=grid, origin_utc="2025-01-01T00:00:00Z", cutoff_utc="2025-01-01T01:00:00Z", units="hours", source_id="reconstruction")
    t = reconstructed_arrival(p, **args)
    assert t.lower_s[0, 0] == -3600 and t.lower_s[1, 0] == 3600
    assert not t.known[1, 1] and not t.never.any()
    interval = reconstructed_arrival(p, **args, std_path=s)
    assert interval.lower_s[0, 1] == -1440 and interval.upper_s[0, 1] == 1440
    assert interval.exact_ignition()["status"] == "UNSCORABLE"
    wrong = GridSpec((2, 2), (100, 0, 1, 0, -100, 200), 3857)
    with pytest.raises(ValueError): reconstructed_arrival(p, **dict(args, grid=wrong))


def test_perimeters_retain_clock_interval_coverage_and_cause(tmp_path, grid):
    pytest.importorskip("rasterio"); pytest.importorskip("shapely")
    from pyproj import Transformer
    from shapely.geometry import box, mapping
    from shapely.ops import transform
    tr = Transformer.from_crs(3857, 4326, always_xy=True)
    # One cell centre is mapped. Unmapped is unknown, not surveyed unburned.
    f = {"type": "Feature", "geometry": mapping(transform(tr.transform, box(1, 101, 99, 199))),
         "properties": {"time_utc": "2025-01-01T00:30:00Z", "source_record_id": 5}}
    p = tmp_path/"extent.geojson"; p.write_text(json.dumps(dict(type="FeatureCollection", features=[f])))
    t = observed_perimeters(p, grid=grid, cutoff_utc="2025-01-01T00:00:00Z", source_id="nirops-holdout")
    assert t.known.sum() == 1 and t.known[0, 0] and t.upper_s[0, 0] == 1800 and np.isneginf(t.lower_s[0, 0])
    assert not t.never.any() and t.exact_ignition()["status"] == "UNSCORABLE"
    assert "not_ignition" in t.source["records"][0]["cause"]
    f["properties"]["time_utc"] = "2025-01-01T00:30:00"
    p.write_text(json.dumps(dict(type="FeatureCollection", features=[f])))
    with pytest.raises(ValueError): observed_perimeters(p, grid=grid, cutoff_utc="2025-01-01T00:00:00Z", source_id="nirops")


def test_invalid_observed_geometry_is_retained_as_unsupported(tmp_path, grid):
    pytest.importorskip("rasterio"); pytest.importorskip("shapely")
    # Self-crossing bowtie, never auto-repaired into a different observation.
    f = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [.001, .001], [0, .001], [.001, 0], [0, 0]]]},
         "properties": {"time_utc": "2025-01-01T00:30:00Z", "source_record_id": 8, "Incident_C": "fire"}}
    p = tmp_path/"invalid.geojson"; p.write_text(json.dumps(dict(type="FeatureCollection", features=[f])))
    t = observed_perimeters(p, grid=grid, cutoff_utc="2025-01-01T00:00:00Z", source_id="holdout", expected_event="fire")
    assert not t.known.any() and t.source["unusable_records"][0]["source_record_id"] == 8
    with pytest.raises(ValueError, match="event identity"):
        observed_perimeters(p, grid=grid, cutoff_utc="2025-01-01T00:00:00Z", source_id="holdout", expected_event="other-fire")


def test_simulator_coordinates_are_checked_against_reference_grid(tmp_path, grid):
    p, r = write_farsite(tmp_path, grid)
    with np.load(p) as a: contents = {k: a[k] for k in a.files}
    contents["coordinates"] = np.zeros((2, 2, 2))
    np.savez(p, **contents)
    with pytest.raises(ValueError, match="coordinate/grid alignment"):
        external_simulator(p, reference_path=r, cutoff_utc="2025-01-01T00:00:00Z", source_id="stored-output")


def test_fractional_utc_offset_is_rejected_without_rounding():
    # The local clock has no microseconds, but UTC would be 198.5 seconds.
    with pytest.raises(ValueError, match="Whole UTC seconds"):
        utc_seconds("1970-01-01T00:03:20+00:00:01.5")
    assert utc_seconds("1970-01-01T00:03:20+00:00:02") == 198


def rewrite_npz(path, *, metadata_update=None, drop=(), **arrays):
    with np.load(path) as z: fields = {k: z[k] for k in z.files if k not in drop}
    if metadata_update:
        meta = json.loads(str(fields["metadata_json"].item())); meta.update(metadata_update)
        fields["metadata_json"] = json.dumps(meta)
    fields.update(arrays); np.savez(path, **fields)


def test_finite_run_and_family_admissions(tmp_path, grid):
    p, r = write_farsite(tmp_path, grid)
    args = dict(reference_path=r, cutoff_utc="2025-01-01T00:00:00Z", source_id="sim")
    rewrite_npz(p, arrival_minutes=np.array([[0, 2], [-9999, 1000]]))
    with pytest.raises(ValueError, match="exceeds.*run end"): external_simulator(p, **args)
    for bad in (dict(model_family="LearnedProbability", method="probability_predictor"),
                dict(model_family=None), dict(exact_duration_minutes=0), dict(exact_duration_minutes=float("inf")),
                dict(exact_duration_minutes=True), dict(exact_duration_minutes=.001)):
        p, r = write_farsite(tmp_path, grid); rewrite_npz(p, metadata_update=bad)
        with pytest.raises(ValueError): external_simulator(p, **args)
    p, r = write_farsite(tmp_path, grid)
    rewrite_npz(p, arrival_minutes=np.array([[0, 2], [-9999, 10]]))
    t = external_simulator(p, **args)
    assert t.lower_s[1, 1] == 600  # Inclusive endpoint.
    assert t.exact_ignition(horizon_s=600)["status"] == "MODEL_RELATIVE_BOUNDED_ARRIVAL_ONLY"
    for horizon, dep in ((601, 0), (float("nan"), 0), (float("inf"), 0), (600, -1), (100, 101), (True, 0)):
        assert t.exact_ignition(horizon_s=horizon, departure_s=dep)["status"] == "UNSCORABLE"


def test_grid_binding_is_independent_of_reference_shape(tmp_path, grid):
    p, r = write_farsite(tmp_path, grid)
    args = dict(reference_path=r, cutoff_utc="2025-01-01T00:00:00Z", source_id="sim")
    rewrite_npz(p, drop=("affine_transform", "epsg"))
    with pytest.raises(ValueError, match="no verifiable grid/CRS binding"): external_simulator(p, **args)
    p, r = write_farsite(tmp_path, grid)
    shifted = list(grid.affine); shifted[2] += 1000
    rewrite_npz(r, affine_transform=shifted)
    with pytest.raises(ValueError, match="alignment mismatch"): external_simulator(p, **args)


def test_cutoff_run_clock_shift_is_explicit_and_bounded(tmp_path, grid):
    p, r = write_farsite(tmp_path, grid)
    rewrite_npz(r, time_utc=np.array(["2025-01-01T00:01:00Z"]))
    t = external_simulator(p, reference_path=r, cutoff_utc="2025-01-01T00:01:00Z", source_id="sim")
    assert t.valid_from_s == -60 and t.valid_until_s == 540 and t.lower_s[0, 0] == -60
    assert t.lower_s[0, 1] == 60 and t.lower_s[1, 0] == 540 and not t.never.any()
    assert t.exact_ignition(horizon_s=540)["status"] == "MODEL_RELATIVE_BOUNDED_ARRIVAL_ONLY"
    assert t.exact_ignition(horizon_s=541)["status"] == "UNSCORABLE"
    rewrite_npz(r, time_utc=np.array(["2025-01-01T00:10:00Z"]))
    with pytest.raises(ValueError, match="Cutoff outside"):
        external_simulator(p, reference_path=r, cutoff_utc="2025-01-01T00:10:00Z", source_id="sim")
