"""Tiny synthetic-only controls for inventory custody and trailing DBF bytes."""
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tarfile

sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent / "audit-1b"
for fixture_name in ("synthetic-symlink", "synthetic-trailing-dbf", "synthetic-nested-seed", "synthetic-nested-builder", "synthetic-nested-tgz"):
    fixture_path = HERE / fixture_name
    if fixture_path.exists():
        shutil.rmtree(fixture_path)
spec = importlib.util.spec_from_file_location("inventory_test_fixture", CHECKOUT / "forecast/tests/test_blind_inventory.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
inventory = fixture.inventory
result = {"source_commit": "a6d1551926ad9d830836e4b0d77ee9a7b8e9cd0d", "source_sha256": inventory.sha256(fixture.SCRIPT), "scope": "Generated synthetic 3x3 fixtures only. No real archive, 2026 study, heldout data, forecasting, or heavy jobs."}

release = fixture.SyntheticRelease(HERE / "synthetic-symlink")
region = release.root / "environment/regions/SYNTHETIC_A"
target = release.root / "borrowed-region"
shutil.move(str(region), str(target))
region.symlink_to(target, target_is_directory=True)
release.pin()
pin_before = release.pinned_manifest_sha
source_path = release.raster_path("terrain.slope_degrees")
source_hash_before = inventory.sha256(source_path)
first = release.validate()
release.raster("terrain.slope_degrees", np.full((1, 3, 3), 99, dtype=np.float32))
source_hash_after = inventory.sha256(source_path)
second = release.validate()
assert source_hash_before != source_hash_after
assert inventory.sha256(release.manifest_path) == pin_before
assert first["case_count"] == second["case_count"] == 2
result["unpinned_symlink_source"] = {"status_before": first["status"], "status_after_unpinned_source_mutation": second["status"], "case_count":second["case_count"], "environment_pins":sorted(release.manifest["environment_sha256"]), "manifest_sha_unchanged":True,"slope_source_sha_before":source_hash_before,"slope_source_sha_after":source_hash_after,"execution_status":second["execution_status"]}

release = fixture.SyntheticRelease(HERE / "synthetic-trailing-dbf")
blob = release.zip_members["nested/source.dbf"]
count = struct.unpack_from("<I",blob,4)[0]
header, record_size = struct.unpack_from("<HH",blob,8)
extra_record = blob[header:header+record_size]
release.zip_members["nested/source.dbf"] = blob + extra_record
release.write_zip()
release.pin()
report = release.validate()
assert report["raw_inventory"]["raw_record_count"] == count == 3
result["unindexed_dbf_record"] = {"status":report["status"],"case_count":report["case_count"],"declared_dbf_count":count,"dbf_record_size":record_size,"appended_unindexed_bytes":len(extra_record),"reported_raw_record_count":report["raw_inventory"]["raw_record_count"],"record_failures":report["raw_inventory"]["record_failures"],"execution_status":report["execution_status"]}

seed = fixture.SyntheticRelease(HERE / "synthetic-nested-seed")
second_records = [("SYNTHETIC_B", "SYN-B", timestamp, geometry) for _, _, timestamp, geometry in seed.records]
second = fixture.SyntheticRelease(HERE / "synthetic-nested-builder", extra_layers={"second/source": second_records})
nested_bytes = io.BytesIO()
with tarfile.open(fileobj=nested_bytes, mode="w:gz") as nested:
    for name, data in sorted(second.zip_members.items()):
        if name.startswith("second/"):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            nested.addfile(info, io.BytesIO(data))
release = fixture.SyntheticRelease(HERE / "synthetic-nested-tgz")
release.zip_members["other/archive.tgz"] = nested_bytes.getvalue()
release.write_zip()
release.pin()
report = release.validate()
assert [entry["event"] for entry in report["raw_inventory"]["incidents"]] == ["SYNTHETIC_A"]
result["unhandled_tgz_bundle"] = {"status":report["status"],"case_count":report["case_count"],"outer_member_pinned":"other/archive.tgz" in report["raw_inventory"]["member_sha256"],"omitted_nested_incident":"SYNTHETIC_B","omitted_nested_records":3,"reported_raw_record_count":report["raw_inventory"]["raw_record_count"],"execution_status":report["execution_status"]}
(HERE / "reproductions.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result))
