"""Audit actual survey-reference availability for every locally cached fire.

This is an availability inventory, not a model evaluation. NIROPS polygons are
manually interpreted aerial infrared extents. A polygon exterior is not a
survey-footprint-certified physically unburned cell. Korean events are outside
the released Western United States collection and remain explicitly excluded.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile

from affine import Affine
import numpy as np
import rasterio
import shapefile

from .farsite_inputs import LANDSCAPE_FILES, WEATHER_FILES, _encode_landscape, _read_aligned
from .observed_data import ARCHIVE_BYTES, ARCHIVE_NAME, ARCHIVE_SHA256, DEFAULT_DIRECTORY, DOI, TIMESTAMP_CAVEAT
from .paths import DATA_ROOT


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREPARED = ROOT / "runs" / "20261009_weighted_stratified_split" / "prepared_all"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _timestamp(value) -> datetime:
    timestamp = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    if timestamp.second or timestamp.microsecond:
        raise ValueError(f"Survey timestamps must be whole minutes: {value!r}")
    return timestamp


def _partition_counts(prepared_directory: Path, event_ids: list[str]) -> tuple[dict, dict]:
    """Count actual saved benchmark rows, rather than infer exposure from names."""
    metadata_path = prepared_directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    saved_ids = metadata["event_ids"]
    if len(saved_ids) != len(set(saved_ids)):
        raise ValueError("Prepared benchmark event identifiers must be unique")
    output = {event_id: {split: 0 for split in ("train", "validation", "test")}
              for event_id in event_ids}
    hashes = {"metadata.json": _sha256(metadata_path)}
    for split in ("train", "validation", "test"):
        path = prepared_directory / f"{split}.npz"
        with np.load(path, allow_pickle=False) as payload:
            indices = payload["event_index"]
        if (indices.ndim != 1 or indices.dtype.kind not in "iu"
                or np.any(indices < 0) or np.any(indices >= len(saved_ids))):
            raise ValueError(f"Invalid saved event indices in {path}")
        counts = np.bincount(indices.astype(np.int64), minlength=len(saved_ids))
        for index, event_id in enumerate(saved_ids):
            if event_id in output:
                output[event_id][split] = int(counts[index])
        # Full checkpoints and NPZ arrays are large. The source metadata hash,
        # file sizes, and directly counted event indices specify this audit.
        hashes[f"{split}.npz"] = {"bytes": path.stat().st_size,
                                   "event_index_sha256": hashlib.sha256(indices.tobytes()).hexdigest()}
    return output, {"prepared_directory": str(prepared_directory.resolve()),
                    "source_files": hashes,
                    "split_policy": metadata.get("split_policy"),
                    "generalization_scope": metadata.get("generalization_scope")}


def _physical_availability(event: dict, data_root: Path) -> dict:
    region = data_root / "regions" / event["id"]
    relative = list(LANDSCAPE_FILES) + [f"weather/{name}_375m.tif" for name in WEATHER_FILES]
    missing = [name for name in relative if not (region / name).is_file()]
    result = {"farsite_inputs_available": event["country"] == "US" and not missing,
              "missing_farsite_inputs": missing,
              "physical_landscape_valid_cells": None,
              "physical_landscape_complete_rectangle": False,
              "physical_input_audit_error": None}
    if not result["farsite_inputs_available"]:
        return result
    geometry = Affine(*event["transform"])
    dimensions = (int(event["height"]), int(event["width"]))
    try:
        landscape = [_read_aligned(region / name, transform=geometry,
                     shape=dimensions, epsg=int(event["epsg"]))[0] for name in LANDSCAPE_FILES]
        _, valid, _ = _encode_landscape(landscape)
        result["physical_landscape_valid_cells"] = int(valid.sum())
        result["physical_landscape_complete_rectangle"] = bool(valid.all())
        # Validate geometry and band count for every physical weather variable.
        # Individual cutoff bands and their finite masks are checked by the
        # evaluation preflight; file presence alone does not imply full coverage.
        for name in WEATHER_FILES:
            with rasterio.open(region / "weather" / f"{name}_375m.tif") as dataset:
                if (dataset.transform != geometry or (dataset.height, dataset.width) != dimensions
                        or dataset.crs.to_epsg() != int(event["epsg"]) or dataset.count < 1):
                    raise ValueError(f"Physical weather geometry does not match: {name}")
    except (ValueError, OSError, rasterio.errors.RasterioError) as error:
        result["farsite_inputs_available"] = False
        result["physical_input_audit_error"] = str(error)
    return result


def _event_rows(events: list[dict], records: list[dict], partitions: dict,
                physical: dict, *, geometry_records: set[int], archive_verified: bool) -> list[dict]:
    """Match published component IDs exactly; never union sibling complexes."""
    by_component = defaultdict(list)
    by_number = defaultdict(list)
    for record in records:
        by_component[str(record["Incident_C"]).strip()].append(record)
        by_number[str(record["Inc Number"]).strip()].append(record)
    output = []
    for event in events:
        event_id = event["id"]
        country = event["country"]
        matching = by_component.get(event_id, []) if country == "US" else []
        basis = "exact published Incident_C == local event_id" if matching else None
        # Full component IDs usually match. An exact incident-number fallback
        # is safe only if it identifies one published component, never a mix.
        if not matching and country == "US":
            candidates = by_number.get(event_id.split("_", 1)[0], [])
            components = {str(record["Incident_C"]).strip() for record in candidates}
            if len(components) == 1:
                matching = candidates
                basis = "exact local incident number with exactly one published component"
        numbers = sorted({str(record["Inc Number"]).strip() for record in matching})
        components = sorted({str(record["Incident_C"]).strip() for record in matching})
        if len(numbers) > 1 or len(components) > 1:
            raise ValueError(f"Ambiguous incident/component identity for {event_id}")
        grouped = defaultdict(list)
        invalid_times = []
        for record in matching:
            try:
                timestamp = _timestamp(record["UTC"])
            except (TypeError, ValueError):
                invalid_times.append(int(record["source_record_id"]))
                continue
            grouped[timestamp].append(int(record["source_record_id"]))
        all_times = sorted(grouped)
        start, end = _timestamp(event["start_utc"]), _timestamp(event["end_utc"])
        times = [timestamp for timestamp in all_times if start <= timestamp <= end]
        intervals = []
        for cutoff, endpoint in zip(times, times[1:]):
            minutes = int((endpoint - cutoff).total_seconds()) // 60
            intervals.append({"cutoff_utc": cutoff.isoformat(), "endpoint_utc": endpoint.isoformat(),
                              "duration_minutes": minutes, "hours": minutes / 60,
                              "cutoff_source_record_ids": sorted(grouped[cutoff]),
                              "endpoint_source_record_ids": sorted(grouped[endpoint])})
        source_ids = sorted(int(record["source_record_id"]) for record in matching)
        geometry = bool(matching) and archive_verified and set(source_ids) <= geometry_records
        counts = partitions.get(event_id, {split: 0 for split in ("train", "validation", "test")})
        exposure = ("training_or_validation_event" if counts["train"] or counts["validation"] else
                    "held_out_event" if counts["test"] else "unrepresented_event")
        reasons = []
        if country != "US":
            reasons.append("Outside the NIROPS Western United States 2020-2024 collection; no paired observed perimeter reference acquired for this Korean event")
        elif not matching:
            reasons.append("No unambiguous exact incident/component match in the verified source")
        if matching and not geometry:
            reasons.append("Selected perimeter geometry is not available in a verified archive")
        if matching and invalid_times:
            reasons.append("Some matched survey timestamps are missing or not exact minutes")
        if not intervals:
            reasons.append("No two valid published survey times inside the cached environment window")
        if not physical[event_id]["farsite_inputs_available"]:
            reasons.append("Cached physical FARSITE inputs are unavailable or geometrically incompatible")
        row = {"event_id": event_id, "country": country, "name": event["name"], "year": event["year"],
               "observed_incident_number": numbers[0] if numbers else None,
               "observed_incident_component": components[0] if components else None,
               "matching_basis": basis,
               "matching_evidence": [{"source_record_id": int(record["source_record_id"]),
                                     "Incident_C": str(record["Incident_C"]).strip(),
                                     "Inc Number": str(record["Inc Number"]).strip(),
                                     "Inc Name": str(record.get("Inc Name", "")).strip(),
                                     "IRWINID": str(record.get("IRWINID", "")).strip()}
                                    for record in matching[:1]],
               "source_record_ids": source_ids, "survey_record_count": len(matching),
               "distinct_survey_times": len(all_times), "survey_times_utc": [t.isoformat() for t in all_times],
               "survey_times_in_cached_window": [t.isoformat() for t in times],
               "invalid_timestamp_record_ids": invalid_times,
               "consecutive_intervals": intervals, "consecutive_interval_count": len(intervals),
               "exact_six_hour_interval_count": sum(p["duration_minutes"] == 360 for p in intervals),
               "cached_start_utc": start.isoformat(), "cached_end_utc": end.isoformat(),
               "rectangle_height": int(event["height"]), "rectangle_width": int(event["width"]),
               "epsg": int(event["epsg"]), "geometry_available_in_verified_archive": geometry,
               "m548_partition": counts, "m548_exposure": exposure,
               **physical[event_id], "eligible": not reasons, "exclusion_reasons": reasons}
        output.append(row)
    return output


def build_inventory(data_root: Path | str = DATA_ROOT, *, archive: Path | str | None = None,
                    prepared_directory: Path | str = DEFAULT_PREPARED,
                    verify_archive: bool = True) -> dict:
    """Audit all events; optional unverified fixture mode never marks rows eligible.

    The pinned archive hash authenticates every compressed polygon byte. This
    operation CRC-checks the small companion members and checks SHX geometry
    records. It does not decompress all 2.1 GB of polygons or assert geometric
    validity; acquisition and per-case preflight do those checks separately.
    """
    if not isinstance(verify_archive, bool):
        raise ValueError("verify_archive must be a boolean")
    data_root = Path(data_root).resolve()
    archive = Path(archive or DEFAULT_DIRECTORY / ARCHIVE_NAME).resolve()
    events_path = data_root / "events.json"
    events = json.loads(events_path.read_text())
    ids = [event["id"] for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("Local event identifiers must be unique")
    if verify_archive and (archive.stat().st_size != ARCHIVE_BYTES or _sha256(archive) != ARCHIVE_SHA256):
        raise ValueError("NIROPS archive differs from its pinned published size or SHA-256")
    hashes = {}
    with zipfile.ZipFile(archive) as packed:
        members = {Path(entry.filename).suffix.lower(): entry for entry in packed.infolist()
                   if not entry.is_dir()}
        if not {".shp", ".shx", ".dbf", ".prj"} <= members.keys():
            raise ValueError("NIROPS archive lacks required shapefile components")
        companion = {}
        for extension in (".shx", ".dbf", ".prj"):
            entry = members[extension]
            payload = packed.read(entry)  # zipfile verifies the uncompressed member CRC.
            hashes[entry.filename] = hashlib.sha256(payload).hexdigest()
            companion[extension] = payload
        if (len(companion[".shx"]) < 100 or (len(companion[".shx"]) - 100) % 8):
            raise ValueError("Published SHX index has an invalid record table")
        geometry_records = set()
        for index, (offset, words) in enumerate(struct.iter_unpack(">ii", companion[".shx"][100:])):
            if offset >= 50 and words >= 2 and 2 * (offset + words) + 8 <= members[".shp"].file_size:
                geometry_records.add(index)
        with shapefile.Reader(dbf=io.BytesIO(companion[".dbf"]), encoding="utf-8") as reader:
            required = {"Incident_C", "Inc Number", "UTC"}
            if not required <= {field[0] for field in reader.fields[1:]}:
                raise ValueError("NIROPS DBF lacks exact incident and acquisition-time fields")
            records = [{**record.as_dict(), "source_record_id": record.oid}
                       for record in reader.iterRecords()]
    partitions, split_source = _partition_counts(Path(prepared_directory), ids)
    physical = {event["id"]: _physical_availability(event, data_root) for event in events}
    rows = _event_rows(events, records, partitions, physical,
                       geometry_records=geometry_records, archive_verified=verify_archive)
    return {"status": "availability_audit_complete", "dataset_doi": DOI,
            "archive": str(archive), "archive_bytes": archive.stat().st_size,
            "archive_verified": verify_archive, "archive_sha256": ARCHIVE_SHA256 if verify_archive else None,
            "companion_member_sha256": hashes,
            "geometry_audit": "Pinned whole-archive hash and SHX record existence; polygon validity is checked on extraction and per-case preflight",
            "local_events_sha256": _sha256(events_path), "m548_split_source": split_source,
            "timestamp_caveat": TIMESTAMP_CAVEAT,
            "reference_semantics": "Cumulative manually mapped NIROPS fire extent; outside a mapped union is not mapped, not physically certified unburned",
            "negative_reference_assumption": "The cumulative perimeters are treated as complete mapped incident extents within the cached rectangle; the source provides no survey-footprint validity mask",
            "korean_exclusion_scope": "No paired observed-perimeter data acquired for these Korean events; source exclusion does not establish that no other observation source exists",
            "event_count": len(rows), "matched_us_event_count": sum(bool(row["source_record_ids"]) for row in rows),
            "eligible_event_count": sum(row["eligible"] for row in rows),
            "eligible_interval_count": sum(row["consecutive_interval_count"] for row in rows if row["eligible"]),
            "events": rows}


def write_inventory(inventory: dict, output_directory: Path | str) -> tuple[Path, Path]:
    """Write a full JSON audit plus a flat, readable per-event CSV."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = output / "observation_availability.json", output / "observation_availability.csv"
    json_path.write_text(json.dumps(inventory, indent=2, allow_nan=False) + "\n")
    keys = ("event_id", "country", "name", "year", "observed_incident_number",
            "observed_incident_component", "matching_basis", "survey_record_count",
            "distinct_survey_times", "consecutive_interval_count", "exact_six_hour_interval_count",
            "geometry_available_in_verified_archive", "farsite_inputs_available",
            "physical_landscape_valid_cells", "physical_landscape_complete_rectangle",
            "m548_exposure", "eligible", "exclusion_reasons")
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*keys, "m548_train_samples", "m548_validation_samples", "m548_test_samples"])
        writer.writeheader()
        for event in inventory["events"]:
            row = {key: event[key] for key in keys}
            row["exclusion_reasons"] = "; ".join(row["exclusion_reasons"])
            row.update({f"m548_{split}_samples": event["m548_partition"][split]
                        for split in ("train", "validation", "test")})
            writer.writerow(row)
    return json_path, csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--archive", type=Path, default=DEFAULT_DIRECTORY / ARCHIVE_NAME)
    parser.add_argument("--prepared-directory", type=Path, default=DEFAULT_PREPARED)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    inventory = build_inventory(arguments.data_root, archive=arguments.archive,
                                prepared_directory=arguments.prepared_directory)
    paths = write_inventory(inventory, arguments.output_dir)
    print(f"Audited {inventory['event_count']} events: {inventory['eligible_event_count']} eligible events, "
          f"{inventory['eligible_interval_count']} actual survey intervals. Written to {paths[0]} and {paths[1]}")


if __name__ == "__main__":
    main()
