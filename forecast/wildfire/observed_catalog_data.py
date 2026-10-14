"""Export selected NIROPS incident components from one verified archive pass.

The catalog supplies exact zero-based shapefile record IDs. A shared incident
number may describe several separately cached incident components, so both
``Inc Number`` and ``Incident_C`` must match before any polygon is exported.
Existing Fish Creek exports and the authentic source archive are preserved.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
from numbers import Integral
from pathlib import Path
import shutil
import tempfile
import time
import zipfile

from pyproj import CRS
import shapefile
from shapely.geometry import shape

from . import observed_data as source


def _selection(event_rows):
    selected = {}
    record_owners = {}
    for row in event_rows:
        if not isinstance(row, Mapping):
            raise TypeError("Each observed event selection must be a mapping")
        event = row.get("event_id")
        incident = row.get("observed_incident_number")
        component = row.get("observed_incident_component")
        if (not isinstance(event, str) or not event or event in {".", ".."}
                or Path(event).name != event or "/" in event or "\\" in event):
            raise ValueError("event_id must be a nonempty directory basename")
        if event in selected:
            raise ValueError(f"Duplicate observed event selection: {event}")
        if not isinstance(incident, str) or not incident.strip():
            raise ValueError(f"observed_incident_number is required for {event}")
        if component != event:
            raise ValueError(f"observed_incident_component must equal event_id for {event}")
        raw_ids = row.get("source_record_ids")
        if isinstance(raw_ids, (str, bytes)) or raw_ids is None:
            raise ValueError(f"A nonempty source_record_ids sequence is required for {event}")
        try:
            ids = tuple(raw_ids)
        except TypeError as error:
            raise ValueError(f"source_record_ids must be an iterable for {event}") from error
        if (not ids or any(isinstance(value, bool) or not isinstance(value, Integral)
                           or value < 0 for value in ids)):
            raise ValueError(f"source_record_ids must contain nonnegative integers for {event}")
        ids = tuple(int(value) for value in ids)
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate source record IDs for {event}")
        for record_id in ids:
            if record_id in record_owners:
                raise ValueError(f"Source record {record_id} belongs to multiple selected components")
            record_owners[record_id] = event
        selected[event] = dict(incident=incident.strip(), component=component,
                               ids=tuple(sorted(ids)))
    return selected


def _resume(path, selection):
    provenance_path = path.parent / "provenance.json"
    if not path.exists() and not provenance_path.exists():
        if path.parent.exists() and any(path.parent.iterdir()):
            raise FileExistsError(f"Preserve incomplete or unrelated catalog export: {path.parent}")
        return False
    if not path.is_file() or not provenance_path.is_file():
        raise FileExistsError(f"Both GeoJSON and provenance are required to resume: {path.parent}")
    try:
        provenance = json.loads(provenance_path.read_text())
        collection = json.loads(path.read_text())
        actual_ids = sorted(feature["properties"]["source_record_id"]
                            for feature in collection["features"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"Unreadable existing observed catalog export: {path.parent}") from error
    expected = dict(dataset_doi=source.DOI, archive_sha256=source.ARCHIVE_SHA256,
        event_id=path.parent.name, incident_number=selection["incident"],
        incident_component=selection["component"], source_record_ids=list(selection["ids"]))
    if (any(provenance.get(key) != value for key, value in expected.items())
            or actual_ids != expected["source_record_ids"]
            or provenance.get("geojson_sha256") != source._sha256(path)):
        raise RuntimeError(f"Existing catalog provenance does not bind this exact selection: {path.parent}")
    for feature in collection["features"]:
        properties = feature["properties"]
        if (str(properties.get("Inc Number", "")).strip() != selection["incident"]
                or str(properties.get("Incident_C", "")).strip() != selection["component"]):
            raise RuntimeError(f"Existing export has a mismatched incident component: {path.parent}")
    return True


def _unpack(archive, temporary, output_dir):
    """Stream every companion file once; ZipFile verifies member CRCs."""
    paths, hashes = {}, {}
    with zipfile.ZipFile(archive) as packed:
        members = [entry for entry in packed.infolist() if not entry.is_dir()
            and Path(entry.filename).suffix.lower() in {".shp", ".shx", ".dbf", ".prj", ".cpg"}]
        by_extension = {Path(entry.filename).suffix.lower(): entry for entry in members}
        if (len(by_extension) != len(members)
                or not {".shp", ".shx", ".dbf", ".prj"} <= by_extension.keys()):
            raise RuntimeError("NIROPS archive must contain one shapefile and required companions")
        needed = sum(entry.file_size for entry in members)
        if shutil.disk_usage(output_dir).free < needed + 100 * 1024 * 1024:
            raise RuntimeError(f"NIROPS catalog extraction needs at least {needed:,} additional free bytes")
        progress_time = time.monotonic()
        copied = 0
        for extension, member in by_extension.items():
            target = temporary / ("perimeters" + extension)
            digest = hashlib.sha256()
            with packed.open(member) as incoming, target.open("wb") as outgoing:
                for block in iter(lambda: incoming.read(4 * 1024 * 1024), b""):
                    outgoing.write(block)
                    digest.update(block)
                    copied += len(block)
                    if time.monotonic() - progress_time >= 20:
                        print(f"NIROPS catalog extraction: {copied:,}/{needed:,} bytes", flush=True)
                        progress_time = time.monotonic()
            paths[extension] = target
            hashes[member.filename] = digest.hexdigest()
    crs = CRS.from_wkt(paths[".prj"].read_text())
    if not crs.equals(CRS.from_epsg(4326), ignore_axis_order=True):
        raise RuntimeError(f"Expected original EPSG:4326 NIROPS polygons, received {crs}")
    return paths, hashes


def extract_catalog(archive, event_rows, output_dir):
    """Return ``event_id -> GeoJSON Path`` for exactly selected components.

    The archive size and pinned SHA-256 are verified before resuming exports.
    A full temporary shapefile is decompressed only once for all new events.
    Interrupted complete event exports can be resumed; mismatched or partial
    exports are never overwritten. No network request or model inference is
    performed by this function.
    """
    selections = _selection(event_rows)
    if not selections:
        return {}
    archive = Path(archive).resolve()
    output_dir = Path(output_dir).resolve()
    if (not archive.is_file() or archive.stat().st_size != source.ARCHIVE_BYTES
            or source._sha256(archive) != source.ARCHIVE_SHA256):
        raise RuntimeError(f"NIROPS catalog archive failed pinned size/SHA-256 verification: {archive}")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {event: output_dir / event / (event + ".geojson") for event in selections}
    pending = {event: selection for event, selection in selections.items()
               if not _resume(result[event], selection)}
    if not pending:
        return result
    metadata_sources = {path.name: source._sha256(path) for path in (
        archive.parent / "files.json", archive.parent / "publisher_snapshot.json") if path.is_file()}
    print(f"Extracting {len(pending)} exact NIROPS incident components in one archive pass.", flush=True)
    with tempfile.TemporaryDirectory(prefix="nirops-catalog-extract-", dir=output_dir) as directory:
        temporary = Path(directory)
        paths, member_hashes = _unpack(archive, temporary, output_dir)
        parsed = {}
        with shapefile.Reader(str(paths[".shp"]), encoding="utf-8") as reader:
            fields = [field[0] for field in reader.fields[1:]]
            if not {"Inc Number", "Incident_C", "UTC"} <= set(fields):
                raise RuntimeError("NIROPS archive is missing Inc Number, Incident_C, or UTC")
            count = reader.numRecords
            for event, selection in pending.items():
                features, invalid = [], []
                for record_id in selection["ids"]:
                    if record_id >= count:
                        raise ValueError(f"Source record {record_id} is outside the published shapefile")
                    properties = reader.record(record_id).as_dict()
                    if (str(properties["Inc Number"]).strip() != selection["incident"]
                            or str(properties["Incident_C"]).strip() != selection["component"]):
                        raise ValueError(f"Source record {record_id} does not match {event}'s exact incident/component")
                    timestamp = datetime.fromisoformat(str(properties["UTC"]).strip())
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    timestamp = timestamp.astimezone(timezone.utc)
                    geometry = reader.shape(record_id).__geo_interface__
                    if not geometry or geometry["type"] not in {"Polygon", "MultiPolygon"}:
                        raise ValueError(f"Source record {record_id} does not contain a perimeter polygon")
                    polygon = shape(geometry)
                    if polygon.is_empty:
                        raise ValueError(f"Source record {record_id} has an empty perimeter")
                    if not polygon.is_valid:
                        invalid.append(record_id)
                    properties = {key: source._json_property(value) for key, value in properties.items()}
                    properties.update(time_utc=timestamp.isoformat(), source_record_id=record_id)
                    features.append(dict(type="Feature", id=record_id, properties=properties, geometry=geometry))
                features.sort(key=lambda feature: (feature["properties"]["time_utc"], feature["id"]))
                parsed[event] = (features, invalid)
        # Parse and verify every requested component before publishing any new
        # export, so an incorrect selection cannot leave a partly selected set.
        for event, selection in pending.items():
            staging = temporary / event
            staging.mkdir()
            staged_geojson = staging / (event + ".geojson")
            features, invalid = parsed[event]
            source._write_json(staged_geojson, dict(type="FeatureCollection", name=event, features=features))
            times = sorted({feature["properties"]["time_utc"] for feature in features})
            intervals = [dict(initial_utc=first, endpoint_utc=second,
                duration_hours=(datetime.fromisoformat(second)-datetime.fromisoformat(first)).total_seconds()/3600)
                for first, second in zip(times, times[1:])]
            provenance = dict(dataset_doi=source.DOI, dataset_version=source.VERSION,
                publisher_url=source.PUBLISHER_URL, files_metadata_url=source.FILES_URL,
                snapshot_metadata_url=source.SNAPSHOT_URL,
                license=dict(short_name="CC BY 4.0", url="https://creativecommons.org/licenses/by/4.0/"),
                citation="Magstadt et al. (2026), NIROPS Western United States 2020-2024 fire perimeter progression dataset, Mendeley Data v1, DOI 10.17632/95rj5d379g.1.",
                acquired_utc=datetime.now(timezone.utc).isoformat(), archive=str(archive),
                archive_bytes=archive.stat().st_size, archive_sha256=source.ARCHIVE_SHA256,
                geojson=str(result[event]), geojson_sha256=source._sha256(staged_geojson),
                event_id=event, incident_number=selection["incident"], incident_component=selection["component"],
                source_record_ids=list(selection["ids"]), feature_count=len(features),
                source_shapefile_record_count=count, source_fields=fields,
                source_member_sha256=member_hashes, cached_publisher_metadata_sha256=metadata_sources,
                invalid_geometry_source_records=invalid, crs="EPSG:4326",
                distinct_survey_times=len(times), survey_intervals=intervals,
                exact_six_hour_consecutive_pairs=sum(pair["duration_hours"] == 6 for pair in intervals),
                observation_kind="Manually interpreted aerial-infrared fire survey perimeters; no arrival-time interpolation.",
                timestamp_field="UTC", normalized_timestamp_field="time_utc", timestamp_caveat=source.TIMESTAMP_CAVEAT,
                record_id_meaning="Zero-based record index in the published shapefile; original geometry and attributes preserved.",
                transformations=["Select exact source record IDs", "Verify exact Inc Number and Incident_C component",
                    "Normalize publisher UTC timestamps to +00:00", "Preserve original polygons and attributes"])
            source._write_json(staging / "provenance.json", provenance)
        for event in pending:
            destination = result[event].parent
            if destination.exists():
                if any(destination.iterdir()):
                    raise FileExistsError(f"Catalog export appeared during extraction: {destination}")
                destination.rmdir()
            (temporary / event).rename(destination)
            print(f"Exported {len(parsed[event][0])} survey polygons for {event}.", flush=True)
    return result
