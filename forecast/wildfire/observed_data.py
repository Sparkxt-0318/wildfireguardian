"""Acquire authentic NIROPS survey perimeters for observation-based evaluation.

The public Mendeley archive contains manually interpreted aerial-infrared
perimeters, rather than interpolated arrival-time labels. Its UTC timestamps
are publisher-normalized acquisition times; the publisher notes that some
timestamps were estimated from filenames, metadata, or supplementary maps.
The shapefile does not flag which timestamps were estimated.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any
from urllib.parse import urlparse
import zipfile

import requests
import shapefile
from pyproj import CRS
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "95rj5d379g"
VERSION = 1
DOI = "10.17632/95rj5d379g.1"
PUBLISHER_URL = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
FILES_URL = (f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/files"
             f"?folder_id=root&version={VERSION}&$start=0&$limit=1000")
SNAPSHOT_URL = f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}/snapshot/{VERSION}"
ARCHIVE_NAME = "NIROPS_2020_2024_R1_R6.zip"
ARCHIVE_SHA256 = "b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615"
ARCHIVE_BYTES = 1_387_524_228
DEFAULT_INCIDENT = "WY-BTF-002416"
DEFAULT_DIRECTORY = ROOT / "data" / "sources" / "nirops_95rj5d379g_v1"
TIMESTAMP_CAVEAT = (
    "UTC is the publisher-normalized acquisition timestamp. When acquisition "
    "times were missing or inconsistent, the publisher estimated timestamps "
    "using filenames, metadata, and supplementary maps. The released shapefile "
    "does not identify those records separately. Exact intervals refer to the "
    "published timestamps and do not establish exact physical arrival times."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    """Replace generated metadata only after its complete write succeeds."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def _download_archive(url: str, destination: Path, *, expected_size: int,
                      expected_sha256: str, retries: int = 3) -> Path:
    """Resume a partial download and require exact byte count and SHA-256.

    A server ignoring Range causes a fresh download into the partial file,
    never an append of a complete response. Interruptions preserve ``.part``.
    A completed existing archive with the wrong digest is left untouched.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if destination.exists():
        size = destination.stat().st_size
        if size == expected_size:
            if _sha256(destination) != expected_sha256:
                raise RuntimeError(f"Existing archive failed SHA-256 verification: {destination}")
            return destination
        if size < expected_size and not partial.exists():
            destination.rename(partial)
        else:
            raise RuntimeError(f"Existing archive has an unexpected size: {destination}")
    if partial.exists() and partial.stat().st_size > expected_size:
        raise RuntimeError(f"Partial archive exceeds the published size: {partial}")
    _write_json(partial.with_name(partial.name + ".json"), {
        "url": url, "expected_size": expected_size,
        "expected_sha256": expected_sha256, "resume_file": str(partial),
    })
    failures = 0
    while not partial.exists() or partial.stat().st_size < expected_size:
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with requests.get(url, headers=headers, stream=True,
                              timeout=(30, 120)) as response:
                response.raise_for_status()
                if response.status_code == 206:
                    content_range = response.headers.get("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if (match is None or int(match[1]) != offset
                            or int(match[3]) != expected_size
                            or int(match[2]) != expected_size - 1):
                        raise RuntimeError(f"Invalid archive Content-Range: {content_range!r}")
                    mode = "ab" if offset else "wb"
                    response_bytes = expected_size - offset
                elif response.status_code == 200:
                    if offset:
                        print("Server ignored Range; restarting the partial archive.", flush=True)
                    mode = "wb"
                    response_bytes = expected_size
                else:
                    raise RuntimeError(f"Unexpected archive HTTP status {response.status_code}")
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) != response_bytes:
                    raise RuntimeError("Archive Content-Length differs from the published size")
                written = 0
                last_progress = time.monotonic()
                with partial.open(mode) as stream:
                    for block in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if not block:
                            continue
                        if written + len(block) > response_bytes:
                            raise RuntimeError("Archive response exceeds its expected byte count")
                        stream.write(block)
                        written += len(block)
                        if time.monotonic() - last_progress >= 20:
                            print(f"NIROPS archive: {stream.tell():,}/{expected_size:,} bytes",
                                  flush=True)
                            last_progress = time.monotonic()
                if written != response_bytes:
                    raise requests.ConnectionError("Archive response ended before its expected size")
        except requests.RequestException:
            if failures >= retries:
                raise
            failures += 1
            print(f"Download interrupted; retaining partial file and retrying ({failures}/{retries}).",
                  flush=True)
            time.sleep(min(2 ** failures, 8))
    if partial.stat().st_size != expected_size or _sha256(partial) != expected_sha256:
        raise RuntimeError(f"Downloaded archive failed size or SHA-256 verification: {partial}")
    partial.replace(destination)
    return destination


def _json_property(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _extract_incident(archive: Path, output: Path, incident_number: str) -> dict[str, Any]:
    """Extract only the requested incident; temporary full shapefile is removed.

    Zip extraction verifies member CRCs. The SHA-256 of each decompressed
    member is recorded while streaming, without loading the whole dataset.
    """
    hashes: dict[str, str] = {}
    with zipfile.ZipFile(archive) as packed:
        members = [entry for entry in packed.infolist()
                   if not entry.is_dir() and Path(entry.filename).suffix.lower()
                   in {".shp", ".shx", ".dbf", ".prj", ".cpg"}]
        by_extension = {Path(entry.filename).suffix.lower(): entry for entry in members}
        if len(by_extension) != len(members) or not {".shp", ".shx", ".dbf", ".prj"} <= by_extension.keys():
            raise RuntimeError("NIROPS archive must contain one shapefile and its required companion files")
        needed = sum(entry.file_size for entry in members)
        if shutil.disk_usage(output.parent).free < needed + 100 * 1024 * 1024:
            raise RuntimeError(f"NIROPS extraction needs at least {needed:,} additional free bytes")
        with tempfile.TemporaryDirectory(prefix="nirops-extract-", dir=output.parent) as temporary:
            root = Path(temporary)
            paths: dict[str, Path] = {}
            for extension, member in by_extension.items():
                target = root / ("perimeters" + extension)
                digest = hashlib.sha256()
                with packed.open(member) as source, target.open("wb") as destination:
                    for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
                        destination.write(block)
                        digest.update(block)
                hashes[member.filename] = digest.hexdigest()
                paths[extension] = target
            source_crs = CRS.from_wkt(paths[".prj"].read_text())
            if not source_crs.equals(CRS.from_epsg(4326), ignore_axis_order=True):
                raise RuntimeError(f"Expected the published EPSG:4326 NIROPS shapefile, received {source_crs}")
            features = []
            invalid_geometry_records = []
            with shapefile.Reader(str(paths[".shp"]), encoding="utf-8") as reader:
                field_names = [field[0] for field in reader.fields[1:]]
                if "Inc Number" not in field_names or "UTC" not in field_names:
                    raise RuntimeError("NIROPS shapefile is missing its Inc Number or UTC field")
                source_count = reader.numRecords
                for record in reader.iterRecords():
                    properties = record.as_dict()
                    if str(properties["Inc Number"]).strip() != incident_number:
                        continue
                    timestamp = datetime.fromisoformat(str(properties["UTC"]).strip())
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    timestamp = timestamp.astimezone(timezone.utc)
                    geometry = reader.shape(record.oid).__geo_interface__
                    if not geometry or geometry["type"] not in {"Polygon", "MultiPolygon"}:
                        raise RuntimeError(f"Survey record {record.oid} does not contain a perimeter polygon")
                    if not shape(geometry).is_valid:
                        invalid_geometry_records.append(record.oid)
                    properties = {key: _json_property(value) for key, value in properties.items()}
                    properties.update(time_utc=timestamp.isoformat(), source_record_id=record.oid)
                    features.append({"type": "Feature", "id": record.oid,
                                     "properties": properties, "geometry": geometry})
    if not features:
        raise ValueError(f"Incident {incident_number!r} was not found in the NIROPS dataset")
    features.sort(key=lambda feature: (feature["properties"]["time_utc"], feature["id"]))
    collection = {"type": "FeatureCollection", "name": incident_number,
                  "features": features}
    _write_json(output, collection)
    times = sorted({feature["properties"]["time_utc"] for feature in features})
    intervals = [{"initial_utc": first, "endpoint_utc": second,
                  "duration_hours": (datetime.fromisoformat(second)
                                     - datetime.fromisoformat(first)).total_seconds() / 3600}
                 for first, second in zip(times, times[1:])]
    return {"feature_count": len(features), "distinct_survey_times": len(times),
            "source_shapefile_record_count": source_count, "crs": "EPSG:4326",
            "source_fields": field_names, "source_member_sha256": hashes,
            "invalid_geometry_source_records": invalid_geometry_records,
            "survey_intervals": intervals,
            "exact_six_hour_consecutive_pairs": sum(pair["duration_hours"] == 6 for pair in intervals),
            "record_id_meaning": "Zero-based record index in the published shapefile; geometry and original attributes preserved."}


def acquire_observed_data(output_dir: Path | str | None = None, *,
                          incident_number: str = DEFAULT_INCIDENT,
                          output_filename: str = "FishCreek.geojson") -> Path:
    """Download, verify, and export actual survey perimeters and provenance."""
    if not isinstance(incident_number, str) or not incident_number.strip():
        raise ValueError("incident_number must be a nonempty incident identifier")
    incident_number = incident_number.strip()
    if Path(output_filename).name != output_filename or not output_filename.endswith(".geojson"):
        raise ValueError("output_filename must be a .geojson basename without directories")
    directory = Path(output_dir or DEFAULT_DIRECTORY).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    listing_path = directory / "files.json"
    snapshot_path = directory / "publisher_snapshot.json"
    if listing_path.exists():
        listing = json.loads(listing_path.read_text())
    else:
        response = requests.get(FILES_URL, headers={"Accept": "application/vnd.mendeley-public-dataset.1+json"}, timeout=60)
        response.raise_for_status()
        listing = response.json()
        _write_json(listing_path, listing)
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text())
    else:
        response = requests.get(SNAPSHOT_URL, timeout=60)
        response.raise_for_status()
        snapshot = response.json()
        _write_json(snapshot_path, snapshot)
    matches = [entry for entry in listing if entry.get("filename") == ARCHIVE_NAME]
    if len(matches) != 1:
        raise RuntimeError("Publisher file listing does not contain exactly one expected NIROPS archive")
    entry = matches[0]
    details = entry["content_details"]
    if details["sha256_hash"] != ARCHIVE_SHA256 or int(details["size"]) != ARCHIVE_BYTES:
        raise RuntimeError("Published NIROPS v1 archive differs from the pinned size or SHA-256")
    url = details["download_url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "data.mendeley.com":
        raise RuntimeError("Publisher archive URL must use HTTPS on data.mendeley.com")
    archive = directory / ARCHIVE_NAME
    print(f"Acquiring authentic NIROPS v1 perimeters ({ARCHIVE_BYTES:,} compressed bytes). "
          "Extraction temporarily requires about 2.1 GB more disk space.", flush=True)
    _download_archive(url, archive, expected_size=ARCHIVE_BYTES, expected_sha256=ARCHIVE_SHA256)
    output = directory / output_filename
    extracted = _extract_incident(archive, output, incident_number)
    provenance = {
        "dataset_doi": DOI, "dataset_version": VERSION, "publisher_url": PUBLISHER_URL,
        "files_metadata_url": FILES_URL, "snapshot_metadata_url": SNAPSHOT_URL,
        "license": snapshot.get("licence", {"short_name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}),
        "citation": "Magstadt et al. (2026), A high spatial resolution daily fire perimeter progression dataset for wildfires in the Western United States: 2020-2024, Mendeley Data, v1, DOI 10.17632/95rj5d379g.1.",
        "acquired_utc": datetime.now(timezone.utc).isoformat(),
        "archive": str(archive), "archive_download_url": url,
        "archive_bytes": archive.stat().st_size, "archive_sha256": ARCHIVE_SHA256,
        "geojson": str(output), "geojson_sha256": _sha256(output),
        "incident_number": incident_number,
        "observation_kind": "Manually interpreted aerial-infrared fire survey perimeters; no arrival-time interpolation.",
        "timestamp_field": "UTC", "normalized_timestamp_field": "time_utc",
        "timestamp_caveat": TIMESTAMP_CAVEAT,
        "transformations": ["Select incident by exact Inc Number", "Normalize published UTC to an explicit +00:00 offset", "Export the original polygons and attributes as RFC 7946 GeoJSON"],
        **extracted,
    }
    _write_json(directory / "provenance.json", provenance)
    print(f"Exported {extracted['feature_count']} survey polygons to {output}", flush=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--incident-number", default=DEFAULT_INCIDENT)
    parser.add_argument("--output-name", default="FishCreek.geojson")
    arguments = parser.parse_args()
    acquire_observed_data(arguments.output_dir, incident_number=arguments.incident_number,
                          output_filename=arguments.output_name)


if __name__ == "__main__":
    main()
