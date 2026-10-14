"""Exact component selection, single-pass extraction, and bound resumability."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

from pyproj import CRS
import pytest
import shapefile

from wildfire import observed_catalog_data as module


@pytest.fixture
def archive(tmp_path, monkeypatch):
    stem = tmp_path / "perimeters"
    records = [("OTHER", "Other", "2024-08-21 08:00:00", 1),
        ("SHARED", "Left", "2024-08-23 02:14:00", 10),
        ("SHARED", "Left", "2024-08-22 08:02:00", 8),
        ("SHARED", "Right", "2024-08-22 09:00:00", 20),
        ("SHARED", "Right", "2024-08-22 15:00:00", 30)]
    with shapefile.Writer(str(stem), shapeType=shapefile.POLYGON) as writer:
        writer.field("Inc Number", "C", 80)
        writer.field("Incident_C", "C", 80)
        writer.field("UTC", "C", 80)
        writer.field("Acres", "N", 18, 6)
        for i, record in enumerate(records):
            writer.poly([[(i, 0), (i, 1), (i+1, 1), (i+1, 0), (i, 0)]])
            writer.record(*record)
    dbf = stem.with_suffix(".dbf")
    dbf.write_bytes(dbf.read_bytes().replace(b"Inc_Number\x00", b"Inc Number\x00", 1))
    stem.with_suffix(".prj").write_text(CRS.from_epsg(4326).to_wkt(version="WKT1_ESRI"))
    packed_path = tmp_path / "perimeters.zip"
    with zipfile.ZipFile(packed_path, "w", compression=zipfile.ZIP_DEFLATED) as packed:
        for extension in (".shp", ".shx", ".dbf", ".prj"):
            path = stem.with_suffix(extension)
            packed.write(path, "source/" + path.name)
    monkeypatch.setattr(module.source, "ARCHIVE_BYTES", packed_path.stat().st_size)
    monkeypatch.setattr(module.source, "ARCHIVE_SHA256", module.source._sha256(packed_path))
    return packed_path


def rows():
    return [dict(event_id="Left", observed_incident_number="SHARED",
                 observed_incident_component="Left", source_record_ids=[1, 2]),
            dict(event_id="Right", observed_incident_number="SHARED",
                 observed_incident_component="Right", source_record_ids=[3, 4])]


def test_all_components_use_one_decompression_and_preserve_original_sources(archive, tmp_path, monkeypatch):
    output = tmp_path / "exports"
    output.mkdir()
    (output / "FishCreek.geojson").write_bytes(b"original Fish Creek export")
    (output / "provenance.json").write_bytes(b"original provenance")
    old_archive = archive.read_bytes()
    original = module._unpack
    calls = []
    def tracked(*args):
        calls.append(args[0])
        return original(*args)
    monkeypatch.setattr(module, "_unpack", tracked)
    result = module.extract_catalog(archive, rows(), output)
    assert set(result) == {"Left", "Right"}
    assert len(calls) == 1
    left = json.loads(result["Left"].read_text())
    assert [feature["id"] for feature in left["features"]] == [2, 1]
    assert left["features"][0]["properties"]["time_utc"] == "2024-08-22T08:02:00+00:00"
    assert left["features"][0]["properties"]["Acres"] == 8
    assert left["features"][0]["properties"]["Incident_C"] == "Left"
    provenance = json.loads((result["Left"].parent / "provenance.json").read_text())
    assert provenance["source_record_ids"] == [1, 2]
    assert provenance["incident_component"] == "Left"
    assert provenance["archive_sha256"] == module.source.ARCHIVE_SHA256
    assert provenance["geojson_sha256"] == module.source._sha256(result["Left"])
    assert provenance["survey_intervals"][0]["duration_hours"] == 18.2
    assert provenance["source_shapefile_record_count"] == 5
    assert provenance["invalid_geometry_source_records"] == []
    with zipfile.ZipFile(archive) as packed:
        assert provenance["source_member_sha256"] == {
            name: hashlib.sha256(packed.read(name)).hexdigest() for name in packed.namelist()}
    assert (output / "FishCreek.geojson").read_bytes() == b"original Fish Creek export"
    assert (output / "provenance.json").read_bytes() == b"original provenance"
    assert archive.read_bytes() == old_archive
    assert not list(output.glob("nirops-catalog-extract-*"))


def test_valid_exports_resume_without_unpack_or_network(archive, tmp_path, monkeypatch):
    output = tmp_path / "exports"
    first = module.extract_catalog(archive, rows(), output)
    old_times = {event: path.stat().st_mtime_ns for event, path in first.items()}
    monkeypatch.setattr(module, "_unpack", lambda *args: pytest.fail("unnecessary decompression"))
    monkeypatch.setattr(module.source.requests, "get", lambda *args, **kwargs: pytest.fail("network"))
    assert module.extract_catalog(archive, rows(), output) == first
    assert {event: path.stat().st_mtime_ns for event, path in first.items()} == old_times


@pytest.mark.parametrize("alteration", ["geometry_bytes", "record_selection", "archive_provenance", "component_provenance"])
def test_resume_rejects_any_unbound_existing_export(archive, tmp_path, monkeypatch, alteration):
    output = tmp_path / "exports"
    result = module.extract_catalog(archive, rows(), output)
    selection = rows()
    provenance_path = result["Left"].parent / "provenance.json"
    if alteration == "geometry_bytes":
        result["Left"].write_text(result["Left"].read_text() + " ")
    elif alteration == "record_selection":
        selection[0]["source_record_ids"] = [2]
    else:
        provenance = json.loads(provenance_path.read_text())
        provenance["archive_sha256" if alteration == "archive_provenance" else "incident_component"] = "wrong"
        provenance_path.write_text(json.dumps(provenance))
    frozen = result["Left"].read_bytes()
    monkeypatch.setattr(module, "_unpack", lambda *args: pytest.fail("resume mismatch must precede extraction"))
    with pytest.raises(RuntimeError, match="exact selection"):
        module.extract_catalog(archive, selection, output)
    assert result["Left"].read_bytes() == frozen


def test_identical_incident_number_does_not_allow_component_cross_contamination(archive, tmp_path):
    selection = rows()
    selection[0]["source_record_ids"] = [1, 3]
    selection[1]["source_record_ids"] = [4]
    output = tmp_path / "exports"
    with pytest.raises(ValueError, match="exact incident/component"):
        module.extract_catalog(archive, selection, output)
    assert not list(output.rglob("*.geojson"))
    assert not list(output.glob("nirops-catalog-extract-*"))


def test_missing_record_rejects_before_any_event_is_published(archive, tmp_path):
    selection = rows()
    selection[1]["source_record_ids"] = [3, 999]
    output = tmp_path / "exports"
    with pytest.raises(ValueError, match="outside"):
        module.extract_catalog(archive, selection, output)
    assert not list(output.rglob("*.geojson"))


def test_incomplete_existing_export_is_preserved(archive, tmp_path):
    output = tmp_path / "exports"
    incomplete = output / "Left"
    incomplete.mkdir(parents=True)
    (incomplete / "Left.geojson").write_bytes(b"incomplete")
    with pytest.raises(FileExistsError, match="Both GeoJSON"):
        module.extract_catalog(archive, rows(), output)
    assert (incomplete / "Left.geojson").read_bytes() == b"incomplete"


def test_archive_digest_is_verified_even_when_export_is_cached(archive, tmp_path):
    output = tmp_path / "exports"
    module.extract_catalog(archive, rows(), output)
    original = archive.read_bytes()
    archive.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(RuntimeError, match="SHA-256"):
        module.extract_catalog(archive, rows(), output)


def test_insufficient_disk_space_prevents_partial_exports(archive, tmp_path, monkeypatch):
    monkeypatch.setattr(module.shutil, "disk_usage", lambda *args: SimpleNamespace(free=0))
    output = tmp_path / "exports"
    with pytest.raises(RuntimeError, match="additional free bytes"):
        module.extract_catalog(archive, rows(), output)
    assert not list(output.rglob("*.geojson"))
    assert not list(output.glob("nirops-catalog-extract-*"))


def test_member_crc_is_checked_and_corrupt_temporary_files_are_removed(archive, tmp_path, monkeypatch):
    stored = tmp_path / "stored.zip"
    with zipfile.ZipFile(archive) as incoming, zipfile.ZipFile(stored, "w", zipfile.ZIP_STORED) as outgoing:
        for name in incoming.namelist():
            outgoing.writestr(name, incoming.read(name))
    with zipfile.ZipFile(stored) as packed:
        member = next(item for item in packed.infolist() if item.filename.endswith(".dbf"))
        offset = member.header_offset + 30 + len(member.filename.encode()) + len(member.extra)
    damaged = bytearray(stored.read_bytes())
    damaged[offset+50] ^= 1
    stored.write_bytes(damaged)
    # Accept this deliberately damaged archive digest in the fixture so the
    # separate member CRC check, rather than the outer hash, is exercised.
    monkeypatch.setattr(module.source, "ARCHIVE_BYTES", stored.stat().st_size)
    monkeypatch.setattr(module.source, "ARCHIVE_SHA256", module.source._sha256(stored))
    output = tmp_path / "exports"
    with pytest.raises(zipfile.BadZipFile, match="CRC"):
        module.extract_catalog(stored, rows(), output)
    assert not list(output.rglob("*.geojson"))
    assert not list(output.glob("nirops-catalog-extract-*"))


@pytest.mark.parametrize("change,match", [
    ({"event_id": "../escape"}, "basename"),
    ({"observed_incident_component": "Wrong"}, "equal event_id"),
    ({"source_record_ids": [True]}, "nonnegative integers"),
    ({"source_record_ids": [1., 2.]}, "nonnegative integers"),
    ({"source_record_ids": [1, 1]}, "Duplicate source"),
    ({"source_record_ids": []}, "nonnegative integers"),
])
def test_invalid_selection_rejects_before_archive_io(tmp_path, change, match):
    row = dict(rows()[0], **change)
    with pytest.raises(ValueError, match=match):
        module.extract_catalog(tmp_path / "missing.zip", [row], tmp_path / "exports")
    assert not (tmp_path / "exports").exists()


def test_empty_catalog_requires_no_archive_or_output(tmp_path):
    assert module.extract_catalog(tmp_path / "missing.zip", [], tmp_path / "exports") == {}
    assert not (tmp_path / "exports").exists()
