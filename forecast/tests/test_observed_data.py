import hashlib
import json
from pathlib import Path
import zipfile

import pytest
import shapefile
from pyproj import CRS

from wildfire.observed_data import _download_archive, _extract_incident, acquire_observed_data


class Response:
    def __init__(self, body, status=200, headers=None, interrupt=False):
        self.body = body
        self.status_code = status
        self.headers = headers or {"Content-Length": str(len(body))}
        self.interrupt = interrupt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body
        if self.interrupt:
            raise KeyboardInterrupt


def digest(body):
    return hashlib.sha256(body).hexdigest()


def test_range_resumes_partial_and_verifies_digest(tmp_path, monkeypatch):
    whole = b"abcdefgh"
    destination = tmp_path / "surveys.zip"
    partial = Path(str(destination) + ".part")
    partial.write_bytes(whole[:3])
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs["headers"])
        return Response(whole[3:], 206, {"Content-Range": "bytes 3-7/8", "Content-Length": "5"})

    monkeypatch.setattr("wildfire.observed_data.requests.get", get)
    result = _download_archive("https://example.test/observed.zip", destination,
                               expected_size=8, expected_sha256=digest(whole))
    assert result.read_bytes() == whole
    assert calls == [{"Accept-Encoding": "identity", "Range": "bytes=3-"}]
    assert not partial.exists()


def test_server_ignoring_range_restarts_instead_of_appending(tmp_path, monkeypatch):
    destination = tmp_path / "surveys.zip"
    Path(str(destination) + ".part").write_bytes(b"abc")
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: Response(b"abcdefgh"))
    _download_archive("https://example.test/observed.zip", destination,
                      expected_size=8, expected_sha256=digest(b"abcdefgh"))
    assert destination.read_bytes() == b"abcdefgh"


def test_bad_range_is_rejected_before_modifying_partial(tmp_path, monkeypatch):
    destination = tmp_path / "surveys.zip"
    partial = Path(str(destination) + ".part")
    partial.write_bytes(b"abc")
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: Response(
        b"defgh", 206, {"Content-Range": "bytes 2-7/8", "Content-Length": "5"}))
    with pytest.raises(RuntimeError, match="Content-Range"):
        _download_archive("https://example.test/observed.zip", destination,
                          expected_size=8, expected_sha256=digest(b"abcdefgh"))
    assert partial.read_bytes() == b"abc"
    assert not destination.exists()


def test_bad_digest_never_promotes_partial_to_verified_archive(tmp_path, monkeypatch):
    destination = tmp_path / "surveys.zip"
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: Response(b"abcdefgh"))
    with pytest.raises(RuntimeError, match="SHA-256"):
        _download_archive("https://example.test/observed.zip", destination,
                          expected_size=8, expected_sha256=digest(b"bad data"))
    assert Path(str(destination) + ".part").read_bytes() == b"abcdefgh"
    assert not destination.exists()


def test_keyboard_interrupt_leaves_resumable_bytes(tmp_path, monkeypatch):
    destination = tmp_path / "surveys.zip"
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: Response(
        b"abc", headers={"Content-Length": "8"}, interrupt=True))
    with pytest.raises(KeyboardInterrupt):
        _download_archive("https://example.test/observed.zip", destination,
                          expected_size=8, expected_sha256=digest(b"abcdefgh"))
    assert Path(str(destination) + ".part").read_bytes() == b"abc"


def test_verified_existing_archive_needs_no_network(tmp_path, monkeypatch):
    destination = tmp_path / "surveys.zip"
    destination.write_bytes(b"abcdefgh")
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: pytest.fail("network call"))
    assert _download_archive("https://example.test/observed.zip", destination,
                             expected_size=8, expected_sha256=digest(b"abcdefgh")) == destination


@pytest.fixture
def perimeter_archive(tmp_path):
    stem = tmp_path / "perimeters"
    with shapefile.Writer(str(stem), shapeType=shapefile.POLYGON) as writer:
        writer.field("Inc Number", "C", 80)
        writer.field("Incident_C", "C", 80)
        writer.field("UTC", "C", 80)
        writer.field("Acres", "N", 18, 6)
        entries = [("OTHER", "2024-08-22 07:00:00", 5),
                   ("WY-BTF-002416", "2024-08-23 02:14:00", 10),
                   ("WY-BTF-002416", "2024-08-22 08:02:00", 8)]
        for incident, utc, acres in entries:
            writer.poly([[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]])
            writer.record(incident, "FishCreek" if incident != "OTHER" else "Other", utc, acres)
    # pyshp's writer substitutes underscores; the authentic published DBF
    # contains a literal space in this field name.
    dbf = stem.with_suffix(".dbf")
    dbf.write_bytes(dbf.read_bytes().replace(b"Inc_Number\x00", b"Inc Number\x00", 1))
    stem.with_suffix(".prj").write_text(CRS.from_epsg(4326).to_wkt(version="WKT1_ESRI"))
    archive = tmp_path / "surveys.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as packed:
        for extension in (".shp", ".shx", ".dbf", ".prj"):
            path = stem.with_suffix(extension)
            packed.write(path, "source/" + path.name)
    return archive


def test_selects_real_records_preserves_fields_and_exact_interval(perimeter_archive, tmp_path):
    output = tmp_path / "FishCreek.geojson"
    provenance = _extract_incident(perimeter_archive, output, "WY-BTF-002416")
    features = json.loads(output.read_text())["features"]
    assert [item["properties"]["source_record_id"] for item in features] == [2, 1]
    assert features[0]["properties"]["UTC"] == "2024-08-22 08:02:00"
    assert features[0]["properties"]["time_utc"] == "2024-08-22T08:02:00+00:00"
    assert features[0]["properties"]["Acres"] == 8
    assert features[0]["geometry"]["type"] == "Polygon"
    assert provenance["survey_intervals"] == [{
        "initial_utc": "2024-08-22T08:02:00+00:00", "endpoint_utc": "2024-08-23T02:14:00+00:00",
        "duration_hours": 18.2,
    }]
    assert provenance["exact_six_hour_consecutive_pairs"] == 0
    assert not list(tmp_path.glob("nirops-extract-*"))


def test_missing_incident_rejects_without_creating_output(perimeter_archive, tmp_path):
    output = tmp_path / "unknown.geojson"
    with pytest.raises(ValueError, match="not found"):
        _extract_incident(perimeter_archive, output, "UNKNOWN")
    assert not output.exists()


def test_cached_archive_exports_complete_provenance_without_network(perimeter_archive, tmp_path, monkeypatch):
    directory = tmp_path / "cache"
    directory.mkdir()
    archive_name = "NIROPS_2020_2024_R1_R6.zip"
    body = perimeter_archive.read_bytes()
    (directory / archive_name).write_bytes(body)
    (directory / "files.json").write_text(json.dumps([{
        "filename": archive_name,
        "content_details": {"sha256_hash": digest(body), "size": len(body),
                            "download_url": "https://data.mendeley.com/public-files/fixture"},
    }]))
    (directory / "publisher_snapshot.json").write_text(json.dumps({
        "licence": {"short_name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
    }))
    monkeypatch.setattr("wildfire.observed_data.ARCHIVE_BYTES", len(body))
    monkeypatch.setattr("wildfire.observed_data.ARCHIVE_SHA256", digest(body))
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: pytest.fail("network call"))
    output = acquire_observed_data(directory)
    provenance = json.loads((directory / "provenance.json").read_text())
    assert output == directory / "FishCreek.geojson"
    assert provenance["archive_sha256"] == digest(body)
    assert provenance["geojson_sha256"] == digest(output.read_bytes())
    assert provenance["license"]["short_name"] == "CC BY 4.0"
    assert "estimated timestamps" in provenance["timestamp_caveat"]
    assert provenance["feature_count"] == 2
    assert provenance["survey_intervals"][0]["duration_hours"] == 18.2


@pytest.mark.parametrize("name", ["../outside.geojson", "a/b.geojson", "labels.csv"])
def test_invalid_output_names_rejected_before_network(tmp_path, name, monkeypatch):
    monkeypatch.setattr("wildfire.observed_data.requests.get", lambda *args, **kwargs: pytest.fail("network call"))
    with pytest.raises(ValueError, match="basename"):
        acquire_observed_data(tmp_path, output_filename=name)
