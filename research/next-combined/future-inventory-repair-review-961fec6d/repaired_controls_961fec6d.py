"""Separate repair checks; preserves the original review and reproductions."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
import numpy as np
import rasterio
from affine import Affine
from rasterio.shutil import copy as raster_copy

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent / "audit-1b"
spec = importlib.util.spec_from_file_location("inventory_repaired_test_fixture", CHECKOUT / "forecast/tests/test_blind_inventory.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
inventory = fixture.inventory
run_root = Path(tempfile.mkdtemp(prefix="repair-961fec6d-", dir=HERE))
results = []


def valid(release, name):
    report = release.validate()
    assert report["case_count"] == 2 and report["raw_inventory"]["raw_record_count"] == 3
    assert report["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    results.append({"control": name, "result": "ADMITTED_EXPECTED", "cases": 2})


def refused(release, name, message):
    try:
        release.validate()
    except inventory.InventoryError as error:
        assert message in str(error), (name, str(error))
        results.append({"control": name, "result": "REFUSED_EXPECTED", "reason": str(error)})
    else:
        raise AssertionError(f"{name}: refusal expected")


release = fixture.SyntheticRelease(run_root / "symlink")
valid(release, "baseline_before_symlink")
region = release.root / "environment/regions/SYNTHETIC_A"
target = release.root / "borrowed-region"
shutil.move(str(region), str(target))
region.symlink_to(target, target_is_directory=True)
release.pin()
refused(release, "original_internal_directory_symlink", "Filesystem symlinks")
release.raster("terrain.slope_degrees", np.full((1, 3, 3), 99, dtype=np.float32))
refused(release, "mutated_unpinned_symlink_target", "Filesystem symlinks")

release = fixture.SyntheticRelease(run_root / "dbf")
valid(release, "baseline_before_dbf_changes")
blob = release.zip_members["nested/source.dbf"]
count = struct.unpack_from("<I", blob, 4)[0]
header, size = struct.unpack_from("<HH", blob, 8)
payload = blob[:header + count*size]
for suffix, name in ((b"", "exact_dbf_without_eof"), (b"\x1a", "exact_dbf_single_eof")):
    release.zip_members["nested/source.dbf"] = payload + suffix
    release.write_zip()
    release.pin()
    valid(release, name)
for suffix, name in ((payload[header:header+size], "original_appended_full_dbf_record"), (b"\x1a\x1a", "double_dbf_eof")):
    release.zip_members["nested/source.dbf"] = payload + suffix
    release.write_zip()
    release.pin()
    refused(release, name, "DBF payload must contain exactly")

release = fixture.SyntheticRelease(run_root / "archive")
valid(release, "baseline_before_archive_changes")
release.zip_members["README.txt"] = b"Synthetic metadata\n"
release.zip_members["docs/contract.md"] = b"# Synthetic contract\n"
release.zip_members["nested/source.shp.xml"] = b"<metadata>synthetic</metadata>"
release.write_zip()
release.pin()
valid(release, "allowlisted_text_metadata")
second_records = [("SYNTHETIC_B", "SYN-B", timestamp, geometry) for _, _, timestamp, geometry in release.records]
second = fixture.SyntheticRelease(run_root / "nested-builder", extra_layers={"second/source": second_records})
buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode="w:gz") as nested:
    for name, data in sorted(second.zip_members.items()):
        if name.startswith("second/"):
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            nested.addfile(entry, io.BytesIO(data))
archive_bytes = buffer.getvalue()
release.zip_members["other/archive.tgz"] = archive_bytes
release.write_zip()
release.pin()
refused(release, "original_tgz_with_second_incident", "unhandled member format")
del release.zip_members["other/archive.tgz"]
release.zip_members["other/disguised.txt"] = archive_bytes
release.write_zip()
release.pin()
refused(release, "binary_tgz_disguised_as_text", "Allowed metadata")

release = fixture.SyntheticRelease(run_root / "canonical-vrt")
valid(release, "baseline_before_canonical_vrt")
source = release.raster_path("terrain.slope_degrees")
borrowed = release.root / "borrowed-slope.tif"
shutil.move(str(source), str(borrowed))
raster_copy(borrowed, source, driver="VRT")
release.pin()
refused(release, "canonical_vrt_external_source", "Canonical source must be a GeoTIFF")

release = fixture.SyntheticRelease(run_root / "quality-vrt")
valid(release, "baseline_before_quality_raster")
quality = release.root / "environment/quality_flags/SYNTHETIC_A/temperature_2m_quality_flags_375m.tif"
quality.parent.mkdir(parents=True)
with rasterio.open(quality, "w", driver="GTiff", height=3, width=3, count=97, dtype="uint8", crs=release.grid["epsg"], transform=Affine(*release.grid["transform"])) as output:
    output.write(np.zeros((97, 3, 3), dtype=np.uint8))
release.pin()
valid(release, "regular_pinned_quality_geotiff")
borrowed = release.root / "borrowed-quality.tif"
shutil.move(str(quality), str(borrowed))
raster_copy(borrowed, quality, driver="VRT")
release.pin()
before_manifest = inventory.sha256(release.manifest_path)
before_quality = inventory.sha256(borrowed)
before = release.validate()
from wildfire.data import load_data
def valid_feature_count():
    with load_data(release.root / "environment", events=["SYNTHETIC_A"], sequence_length=1, patch_size=None,
                   channels=inventory.CHANNELS, categorical_encoding="raw", include_fire_labels=False,
                   time_range=(release.grid["start_utc"], release.grid["start_utc"])) as dataset:
        return int(dataset[0]["feature_valid"].sum())
before_valid_features = valid_feature_count()
with rasterio.open(borrowed, "r+") as output:
    output.write(np.ones((97, 3, 3), dtype=np.uint8))
after = release.validate()
after_valid_features = valid_feature_count()
assert before["case_count"] == after["case_count"] == 2
assert before_manifest == inventory.sha256(release.manifest_path)
assert before_quality != inventory.sha256(borrowed)
assert str(borrowed.relative_to(release.root)) not in release.manifest["environment_sha256"]
assert before_valid_features == 54 and after_valid_features == 45
results.append({"control": "quality_vrt_unpinned_external_dependency", "result": "ACCEPTED_CUSTODY_GAP", "before_status": before["status"], "after_status": after["status"], "cases": 2, "manifest_unchanged": True, "valid_feature_count_before": before_valid_features, "valid_feature_count_after": after_valid_features, "execution_status": after["execution_status"]})

result = {"source_commit": "961fec6d43bd8f89433c183f973805de3a228444", "adapter_sha256": inventory.sha256(fixture.SCRIPT), "scope": "Tiny generated synthetic controls only; no real raw/future/heldout study data or heavy jobs.", "fixture_root": str(run_root), "controls": results}
(HERE / "repaired_controls_961fec6d.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result))
