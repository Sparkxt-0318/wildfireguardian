"""Final targeted quality/source raster custody checks, synthetic inputs only."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
import numpy as np
import rasterio
from affine import Affine
from rasterio.shutil import copy as raster_copy

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent / "audit-1b"
spec = importlib.util.spec_from_file_location("inventory_d03_test_fixture", CHECKOUT / "forecast/tests/test_blind_inventory.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
inventory = fixture.inventory
run_root = Path(tempfile.mkdtemp(prefix="repair-d031b72b-", dir=HERE))
observations = []


def admitted(release, label):
    report = release.validate()
    assert report["case_count"] == 2 and report["raw_inventory"]["raw_record_count"] == 3
    assert report["exclusions"] == []
    assert report["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    observations.append({"control": label, "result": "ADMITTED_EXPECTED", "cases": 2, "execution_status": report["execution_status"]})


def refused(release, label, relative):
    try:
        release.validate()
    except inventory.InventoryError as error:
        assert "Canonical source must be a GeoTIFF, not VRT" in str(error)
        assert relative in str(error)
        observations.append({"control": label, "result": "REFUSED_EXPECTED", "reason": str(error)})
    else:
        raise AssertionError(f"{label}: expected VRT refusal")


def quality_geotiff(release, variable, value=0):
    path = release.root / f"environment/quality_flags/SYNTHETIC_A/{variable}_quality_flags_375m.tif"
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=3, width=3, count=97, dtype="uint8",
                       crs=release.grid["epsg"], transform=Affine(*release.grid["transform"])) as output:
        output.write(np.full((97, 3, 3), value, dtype=np.uint8))
    return path


for variable in ("temperature_2m", "wind_eastward_10m", "wind_northward_10m"):
    release = fixture.SyntheticRelease(run_root / variable)
    admitted(release, variable+":baseline")
    quality = quality_geotiff(release, variable)
    release.pin()
    admitted(release, variable+":regular_pinned_quality")
    borrowed = release.root / "borrowed-quality.tif"
    shutil.move(str(quality), str(borrowed))
    raster_copy(borrowed, quality, driver="VRT")
    release.pin()
    manifest_sha = inventory.sha256(release.manifest_path)
    refused(release, variable+":external_quality_vrt_before_mutation", str(quality.relative_to(release.root)))
    with rasterio.open(borrowed, "r+") as output:
        output.write(np.ones((97, 3, 3), dtype=np.uint8))
    assert inventory.sha256(release.manifest_path) == manifest_sha
    refused(release, variable+":external_quality_vrt_after_unpinned_mutation", str(quality.relative_to(release.root)))

for kind in ("quality", "canonical_source"):
    release = fixture.SyntheticRelease(run_root / (kind+"-mask"))
    admitted(release, kind+":baseline_before_mask")
    source = quality_geotiff(release, "temperature_2m", value=1) if kind == "quality" else release.raster_path("terrain.slope_degrees")
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=False):
        with rasterio.open(source, "r+") as output:
            output.write_mask(np.full((3, 3), 255, dtype=np.uint8))
    sidecar = Path(str(source)+".msk")
    assert sidecar.is_file()
    release.pin()
    assert str(sidecar.relative_to(release.root)) in release.manifest["environment_sha256"]
    admitted(release, kind+":regular_pinned_mask_sidecar")
    borrowed = release.root / "borrowed-mask.tif"
    shutil.move(str(sidecar), str(borrowed))
    raster_copy(borrowed, sidecar, driver="VRT")
    release.pin()
    manifest_sha = inventory.sha256(release.manifest_path)
    refused(release, kind+":vrt_mask_sidecar_external_source", str(sidecar.relative_to(release.root)))
    with rasterio.open(borrowed, "r+") as output:
        output.write(np.zeros((1, 3, 3), dtype=np.uint8))
    assert inventory.sha256(release.manifest_path) == manifest_sha
    refused(release, kind+":vrt_mask_sidecar_after_unpinned_mutation", str(sidecar.relative_to(release.root)))

result = {"source_commit":"d031b72b86d4f9089c87ab3e8d706ca74423c31f", "adapter_sha256":inventory.sha256(fixture.SCRIPT), "scope":"Targeted synthetic software controls only; no study/future/heldout data or heavy jobs.", "fixture_root":str(run_root), "status":"PASS_TARGETED_REPAIR_CONTROLS", "observations":observations}
(HERE / "repaired_controls_d031b72b.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result))
