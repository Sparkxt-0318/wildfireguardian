"""Synthetic-only tests of the proposed future raw-release inventory adapter."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest
import rasterio
import shapefile
from affine import Affine
from pyproj import CRS, Transformer
from shapely.geometry import Polygon, box, mapping
from shapely.geometry.polygon import orient
from shapely.ops import transform

SCRIPT = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/blind_inventory.py"
SPEC = importlib.util.spec_from_file_location("future_blind_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


class SyntheticRelease:
    """Build a complete synthetic ZIP, source snapshot, catalog and full states."""

    def __init__(self, root, records=None, extra_layers=None):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.grid = dict(id="SYNTHETIC_A", name="Synthetic incident A", incident_number="SYN-A", country="US", year=2026,
                         height=3, width=3, epsg=32610, transform=[375, 0, 500000, 0, -375, 5000000],
                         t0_utc="2026-07-01T00:00:00+00:00", start_utc="2026-07-01T00:00:00+00:00",
                         end_utc="2026-07-05T00:00:00+00:00")
        self.to_lonlat = Transformer.from_crs(32610, 4326, always_xy=True).transform
        self.records = records if records is not None else [
            ("SYNTHETIC_A", "SYN-A", "2026-07-01 00:00:00", self.geometry(0)),
            ("SYNTHETIC_A", "SYN-A", "2026-07-01 12:00:00", self.geometry(1)),
            ("SYNTHETIC_A", "SYN-A", "2026-07-02 00:00:00", self.geometry(2)),
        ]
        self.layers = {"nested/source": self.records, **(extra_layers or {})}
        self.archive = root / "publisher.zip"
        self.zip_members = {}
        for name, records_for_layer in self.layers.items():
            base = root / "construction" / name
            base.parent.mkdir(parents=True, exist_ok=True)
            with shapefile.Writer(str(base), shapeType=shapefile.POLYGON, encoding="utf-8") as writer:
                writer.field("Incident_C", "C", size=80)
                writer.field("Inc Number", "C", size=80)
                writer.field("UTC", "C", size=60)
                for event, number, timestamp, geometry in records_for_layer:
                    writer.poly([list(geometry.exterior.coords)] + [list(r.coords) for r in geometry.interiors])
                    writer.record(event, number, timestamp)
            base.with_suffix(".prj").write_text(CRS.from_epsg(4326).to_wkt())
            base.with_suffix(".cpg").write_text("UTF-8")
            for suffix in (".shp", ".dbf", ".shx", ".prj", ".cpg"):
                self.zip_members[name + suffix] = base.with_suffix(suffix).read_bytes()
            # pyshp Writer normalizes spaces to underscores. The real NIROPS v1
            # field is literally "Inc Number", so restore that DBF descriptor.
            dbf = bytearray(self.zip_members[name + ".dbf"])
            dbf[64:75] = b"Inc Number\x00"
            self.zip_members[name + ".dbf"] = bytes(dbf)
        self.write_zip()
        dump(root / "environment/events.json", [self.grid])
        dump(root / "environment/biome_classes.json", {"classes": [{"code": k, "name": str(k)} for k in range(1, 15)]})
        variables = [n.split(".")[1] for n in inventory.CHANNELS[:3]]
        weather = root / "environment/regions/SYNTHETIC_A/weather"
        dump(weather / "era5_complete.json", {"variables": variables})
        self.hours = pd.date_range(self.grid["start_utc"], self.grid["end_utc"], freq="h")
        pd.DataFrame({"band": range(1, len(self.hours) + 1), "time_utc": [t.isoformat() for t in self.hours]}).to_csv(
            weather / "era5_bands.csv", index=False)
        for channel in inventory.CHANNELS:
            self.raster(channel, np.ones((len(self.hours) if channel.startswith("weather.") else 1, 3, 3), dtype=np.float32))
        self.write_states()
        self.manifest_path = root / "inventory-input.json"
        self.manifest = dict(schema=inventory.SCHEMA, eligibility_policy=inventory.POLICY,
                             source_contract=inventory.SOURCE_CONTRACT,
                             release=dict(path="publisher.zip", publisher_url="https://example.invalid/synthetic-release",
                                          version="synthetic-2026-v1", public_release_utc="2027-01-10T00:00:00Z",
                                          first_public_release_attestation=dict(path="attestation.json")),
                             states_sha256={"SYNTHETIC_A": inventory.sha256(root / "perimeters/SYNTHETIC_A/states.npz")})
        self.pin()

    def geometry(self, column):
        rectangle = box(500000 + column * 375 + 20, 5000000 - 355, 500000 + (column + 1) * 375 - 20, 4999980)
        return orient(transform(self.to_lonlat, rectangle), sign=-1)

    def raster_path(self, channel):
        category, variable = channel.split(".")
        return self.root / f"environment/regions/SYNTHETIC_A/{category}/{variable}_375m.tif"

    def raster(self, channel, values, grid=None):
        grid = self.grid if grid is None else grid
        path = self.raster_path(channel)
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", driver="GTiff", height=3, width=3, count=len(values),
                           dtype="float32", crs=grid["epsg"], transform=Affine(*grid["transform"]), nodata=np.nan) as output:
            output.write(values.astype(np.float32))

    def write_zip(self):
        with zipfile.ZipFile(self.archive, "w") as output:
            for name, data in sorted(self.zip_members.items()):
                output.writestr(name, data)

    def write_states(self):
        from wildfire.survival import survey_states
        features = []
        for records in self.layers.values():
            for event, _, timestamp, geometry in records:
                if event == "SYNTHETIC_A" and geometry.is_valid:
                    features.append(dict(type="Feature", geometry=mapping(geometry),
                                         properties=dict(time_utc=inventory._utc(timestamp, publisher_naive=True).isoformat())))
        if features:
            times, states = survey_states(features, self.grid)
        else:
            times, states = [], np.zeros((0, 3, 3), dtype=np.uint8)
        path = self.root / "perimeters/SYNTHETIC_A/states.npz"
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, times=np.array([t.isoformat() for t in times]), states=states)

    def pin(self):
        release = self.manifest["release"]
        release["sha256"] = inventory.sha256(self.archive)
        release["member_sha256"] = {k: inventory._digest(v) for k, v in sorted(self.zip_members.items())}
        dump(self.root / "attestation.json", dict(archive_sha256=release["sha256"], claim=inventory.CLAIM,
                                                  public_release_utc=release["public_release_utc"], verified=True))
        release["first_public_release_attestation"]["sha256"] = inventory.sha256(self.root / "attestation.json")
        self.manifest["environment_sha256"] = {str(p.relative_to(self.root)): inventory.sha256(p)
                                               for p in (self.root / "environment").rglob("*") if p.is_file()}
        dump(self.manifest_path, self.manifest)
        self.pinned_manifest_sha = inventory.sha256(self.manifest_path)

    def validate(self):
        return inventory.validate_inventory(self.root, self.manifest_path, self.pinned_manifest_sha)


@pytest.fixture
def release(tmp_path):
    return SyntheticRelease(tmp_path / "synthetic")


def test_complete_raw_inventory_and_exact_full_states(release):
    report = release.validate()
    assert report["admitted_event_count"] == 1 and report["case_count"] == 2
    assert report["raw_inventory"]["incidents"][0]["record_count"] == 3
    assert report["admitted_events"][0]["source_record_ids"] == [f"nested/source.shp:{i}" for i in range(3)]
    assert report["admitted_events"][0]["full_rectangle"] is True
    assert report["release_identity"]["attestation_status"] == "CALLER_ATTESTATION_NOT_EXTERNALLY_VERIFIED"
    assert report["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    assert "READY" not in report["status"]


def test_all_layers_and_unsorted_same_time_records_are_inventoried(tmp_path):
    seed = SyntheticRelease(tmp_path / "seed")
    old = [("OLDER_FIRE", "OLD", "2025-12-31 00:00:00", seed.geometry(0)),
           ("OLDER_FIRE", "OLD", "2026-01-01 00:00:00", seed.geometry(1))]
    records = [seed.records[2], seed.records[0], seed.records[1],
               ("SYNTHETIC_A", "SYN-A", seed.records[1][2], seed.geometry(2))]
    candidate = SyntheticRelease(tmp_path / "candidate", records, {"second/source": old})
    report = candidate.validate()
    assert [e["event"] for e in report["raw_inventory"]["incidents"]] == ["OLDER_FIRE", "SYNTHETIC_A"]
    assert report["raw_inventory"]["incidents"][1]["record_count"] == 4
    assert report["case_count"] == 2
    assert report["exclusions"] == [dict(event="OLDER_FIRE", reason="FIRST_SURVEY_YEAR_NOT_2026")]


def test_detached_forged_extraction_cannot_replace_authenticated_archive(release):
    detached = release.root / "nested/source.shp"
    detached.parent.mkdir(parents=True, exist_ok=True)
    detached.write_bytes(b"forged selected shapes")
    assert release.validate()["case_count"] == 2
    release.zip_members["nested/source.shp"] += b"tamper"
    release.write_zip()
    with pytest.raises(inventory.InventoryError, match="Pinned bytes"):
        release.validate()


def test_archive_member_pin_is_checked_even_after_archive_hash_is_changed(release):
    release.zip_members["publisher-readme.txt"] = b"another pinned member"
    release.write_zip()
    release.manifest["release"]["sha256"] = inventory.sha256(release.archive)
    # Rebind the attestation and manifest, but deliberately omit the new member pin.
    original = dict(release.manifest["release"]["member_sha256"])
    release.pin()
    release.manifest["release"]["member_sha256"] = original
    dump(release.manifest_path, release.manifest)
    release.pinned_manifest_sha = inventory.sha256(release.manifest_path)
    with pytest.raises(inventory.InventoryError, match="Complete archive member"):
        release.validate()


@pytest.mark.parametrize("suffix", [".shx", ".dbf", ".prj", ".cpg"])
def test_all_shapefile_components_required(release, suffix):
    del release.zip_members["nested/source" + suffix]
    release.write_zip()
    release.pin()
    with pytest.raises(inventory.InventoryError, match="Incomplete SHP"):
        release.validate()


def test_second_source_layer_cannot_be_omitted_from_catalog(tmp_path):
    seed = SyntheticRelease(tmp_path / "seed")
    second = [("SYNTHETIC_B", "SYN-B", r[2], r[3]) for r in seed.records]
    candidate = SyntheticRelease(tmp_path / "candidate", extra_layers={"another/source": second})
    with pytest.raises(inventory.InventoryError, match="omitted from full event catalog"):
        candidate.validate()


def test_unpinned_or_omitted_prepared_eligible_fire_fails(release):
    release.manifest["states_sha256"] = {}
    release.pin()
    with pytest.raises(inventory.InventoryError, match="omitted from full prepared"):
        release.validate()


@pytest.mark.parametrize("modification", ["cell", "time_order", "drop_survey", "mask"])
def test_prepared_subset_state_or_mask_cannot_choose_reference_population(release, modification):
    path = release.root / "perimeters/SYNTHETIC_A/states.npz"
    with np.load(path) as source:
        times, states = source["times"].copy(), source["states"].copy()
    kwargs = {}
    if modification in ("cell", "mask"):
        states[-1, 2, 2] = 1
        kwargs["mask"] = np.zeros((3, 3), dtype=bool)
    elif modification == "time_order":
        times = times[::-1]
    else:
        times, states = times[:-1], states[:-1]
    np.savez_compressed(path, times=times, states=states, **kwargs)
    release.manifest["states_sha256"]["SYNTHETIC_A"] = inventory.sha256(path)
    release.pin()
    with pytest.raises(inventory.InventoryError, match="all raw records/full ordered"):
        release.validate()


def test_an_unused_mask_does_not_change_full_reference_state_admission(release):
    path = release.root / "perimeters/SYNTHETIC_A/states.npz"
    with np.load(path) as source:
        times, states = source["times"].copy(), source["states"].copy()
    np.savez_compressed(path, times=times, states=states, mask=np.zeros((3, 3), dtype=bool))
    release.manifest["states_sha256"]["SYNTHETIC_A"] = inventory.sha256(path)
    release.pin()
    assert release.validate()["case_count"] == 2


def test_invalid_geometry_fails_closed_with_original_record_hashes(tmp_path):
    seed = SyntheticRelease(tmp_path / "seed")
    valid = seed.geometry(0)
    x, y = np.asarray(valid.exterior.coords)[:4].T
    bowtie = Polygon([(x[0], y[0]), (x[2], y[2]), (x[1], y[1]), (x[3], y[3]), (x[0], y[0])])
    records = [*seed.records, ("SYNTHETIC_A", "SYN-A", "2026-07-02 12:00:00", bowtie)]
    candidate = SyntheticRelease(tmp_path / "candidate", records)
    with pytest.raises(inventory.InventoryError, match="Raw record admission failures") as caught:
        candidate.validate()
    failures = caught.value.report["raw_inventory"]["record_failures"]
    assert len(failures) == 1 and failures[0]["source_record_id"] == "nested/source.shp:3"
    assert len(failures[0]["shp_record_sha256"]) == len(failures[0]["dbf_record_sha256"]) == 64
    assert caught.value.report["admitted_events"] == []


def test_deleted_dbf_record_is_not_silently_skipped(release):
    blob = bytearray(release.zip_members["nested/source.dbf"])
    header = struct.unpack_from("<H", blob, 8)[0]
    blob[header] = ord("*")
    release.zip_members["nested/source.dbf"] = bytes(blob)
    release.write_zip()
    release.pin()
    with pytest.raises(inventory.InventoryError) as caught:
        release.validate()
    failures = caught.value.report["raw_inventory"]["record_failures"]
    assert "Deleted/unhandled DBF" in failures[0]["error"]
    assert failures[0]["source_record_id"] == "nested/source.shp:0"


def test_catalog_incident_number_must_match_raw_contract(release):
    altered = dict(release.grid, incident_number="another incident")
    dump(release.root / "environment/events.json", [altered])
    release.pin()
    with pytest.raises(inventory.InventoryError, match="membership mismatch"):
        release.validate()


def test_conflicting_raw_membership_fails_closed(tmp_path):
    seed = SyntheticRelease(tmp_path / "seed")
    records = [*seed.records, ("SYNTHETIC_A", "WRONG", "2026-07-02 12:00:00", seed.geometry(0))]
    candidate = SyntheticRelease(tmp_path / "candidate", records)
    with pytest.raises(inventory.InventoryError) as caught:
        candidate.validate()
    assert "conflicting incident numbers" in caught.value.report["raw_inventory"]["record_failures"][0]["error"]


def test_missing_canonical_file_is_objective_and_fully_ledgered(release):
    missing = release.raster_path(inventory.CHANNELS[0])
    missing.unlink()
    release.manifest["states_sha256"] = {}
    release.pin()
    report = release.validate()
    assert report["case_count"] == 0 and len(report["exclusions"]) == 2
    assert all(e["evidence"] == [dict(code="MISSING_SOURCE_FILE", path=str(missing.relative_to(release.root)))]
               for e in report["exclusions"])
    assert report["raw_inventory"]["incidents"][0]["record_count"] == 3


@pytest.mark.parametrize("all_unknown", [False, True])
def test_partial_and_entirely_unknown_values_do_not_exclude_cases(release, all_unknown):
    for channel in inventory.CHANNELS:
        values = np.ones((len(release.hours) if channel.startswith("weather.") else 1, 3, 3), dtype=np.float32)
        values[:, :, :] = np.nan if all_unknown else 1
        values[:, 0, 0] = np.nan
        release.raster(channel, values)
    release.pin()
    report = release.validate()
    assert report["case_count"] == 2 and report["exclusions"] == []


def test_misaligned_source_is_an_objective_input_exclusion(release):
    release.raster(inventory.CHANNELS[-1], np.ones((1, 3, 3)), dict(release.grid, transform=[375, 0, 500001, 0, -375, 5000000]))
    release.manifest["states_sha256"] = {}
    release.pin()
    report = release.validate()
    assert report["case_count"] == 0
    assert all(e["evidence"][0]["code"] == "SOURCE_GRID_UNAVAILABLE" for e in report["exclusions"])


def test_missing_cutoff_time_excludes_only_that_interval_and_validates_all_surveys(release):
    altered = dict(release.grid, start_utc="2026-07-01T01:00:00Z")
    dump(release.root / "environment/events.json", [altered])
    times = pd.date_range(altered["start_utc"], altered["end_utc"], freq="h")
    weather = release.root / "environment/regions/SYNTHETIC_A/weather"
    pd.DataFrame({"band": range(1, len(times) + 1), "time_utc": [t.isoformat() for t in times]}).to_csv(weather / "era5_bands.csv", index=False)
    release.pin()
    report = release.validate()
    assert report["case_count"] == 1 and report["admitted_events"][0]["survey_count"] == 3
    assert len(report["exclusions"]) == 1 and report["exclusions"][0]["evidence"][0]["code"] == "MISSING_CUTOFF_TIME"


def test_no_growth_filter_and_exact_48h_limit(tmp_path):
    seed = SyntheticRelease(tmp_path / "seed")
    records = [("SYNTHETIC_A", "SYN-A", timestamp, seed.geometry(0)) for timestamp in
               ("2026-07-01 00:00:00", "2026-07-03 00:00:00", "2026-07-05 00:00:00.000000001")]
    candidate = SyntheticRelease(tmp_path / "candidate", records)
    report = candidate.validate()
    assert report["case_count"] == 1
    assert report["cases"][0]["endpoint"] == "2026-07-03T00:00:00+00:00"
    assert report["admitted_events"][0]["survey_count"] == 3


def test_non_wgs84_raw_crs_fails_without_silent_reprojection_contract_change(release):
    release.zip_members["nested/source.prj"] = CRS.from_epsg(3857).to_wkt().encode()
    release.write_zip()
    release.pin()
    with pytest.raises(inventory.InventoryError, match="WGS84"):
        release.validate()


def test_snapshot_cannot_omit_quality_or_other_source_file(release):
    path = release.root / "environment/quality_flags/SYNTHETIC_A/extra.txt"
    path.parent.mkdir(parents=True)
    path.write_text("complete snapshot means every file")
    with pytest.raises(inventory.InventoryError, match="snapshot file set"):
        release.validate()


def test_previously_pinned_manifest_hash_cannot_be_replaced(release):
    original = release.pinned_manifest_sha
    release.manifest["release"]["version"] = "changed"
    dump(release.manifest_path, release.manifest)
    with pytest.raises(inventory.InventoryError, match="previously pinned hash"):
        inventory.validate_inventory(release.root, release.manifest_path, original)


def test_cli_is_executable_and_never_reports_ready(release):
    output = release.root / "report.json"
    process = subprocess.run([sys.executable, str(SCRIPT), "--input-root", str(release.root),
                              "--manifest", str(release.manifest_path), "--manifest-sha256", release.pinned_manifest_sha,
                              "--out", str(output)], check=True, text=True, capture_output=True)
    assert json.loads(process.stdout)["ready"] is False
    assert json.loads(output.read_text())["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"


def test_missing_weather_band_is_an_objective_per_cutoff_exclusion(release):
    for channel in inventory.CHANNELS[:3]:
        release.raster(channel, np.ones((1, 3, 3), dtype=np.float32))
    release.pin()
    report = release.validate()
    assert report["case_count"] == 1 and len(report["exclusions"]) == 1
    assert report["exclusions"][0]["evidence"][0]["code"] == "MISSING_SOURCE_BAND"
    assert report["admitted_events"][0]["survey_count"] == 3


def test_no_arrival_or_uncertainty_labels_are_opened(release):
    region = release.root / "environment/regions/SYNTHETIC_A"
    for label in ("arrival_time_hours.tif", "kriging_std_hours.tif"):
        (region / label).write_bytes(b"invalid synthetic label: opening this must fail")
    release.pin()
    assert release.validate()["case_count"] == 2


def test_operational_first_survey_year_does_not_assert_physical_ignition_year(release):
    dump(release.root / "environment/events.json", [dict(release.grid, t0_utc="2025-12-31T00:00:00Z")])
    release.pin()
    assert release.validate()["case_count"] == 2


@pytest.mark.parametrize("member", ["../escape.txt", "other/archive.zip"])
def test_unsafe_or_unhandled_archive_members_fail_closed(release, member):
    release.zip_members[member] = b"unsupported source"
    release.write_zip()
    release.pin()
    with pytest.raises(inventory.InventoryError, match="Unsafe|unhandled"):
        release.validate()


def test_source_survey_cannot_postdate_declared_public_release(release):
    release.manifest["release"]["public_release_utc"] = "2026-07-01T00:00:00Z"
    release.pin()
    with pytest.raises(inventory.InventoryError, match="after declared public release"):
        release.validate()


def test_exact_state_array_dtype_is_required(release):
    path = release.root / "perimeters/SYNTHETIC_A/states.npz"
    with np.load(path) as source:
        times, states = source["times"].copy(), source["states"].astype(np.float32)
    np.savez_compressed(path, times=times, states=states)
    release.manifest["states_sha256"]["SYNTHETIC_A"] = inventory.sha256(path)
    release.pin()
    with pytest.raises(inventory.InventoryError, match="all raw records/full ordered"):
        release.validate()


def test_orphaned_source_bundle_cannot_be_silently_ignored(release):
    release.zip_members["another/omitted.dbf"] = release.zip_members["nested/source.dbf"]
    release.write_zip()
    release.pin()
    with pytest.raises(inventory.InventoryError, match="Orphaned source bundle"):
        release.validate()
