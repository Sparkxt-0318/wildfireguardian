import csv
import hashlib
import json
import zipfile

import numpy as np
import pytest
import shapefile

from wildfire import observed_inventory as module


def event(identifier="OR-UMP-000373_RoughPatchCpx", country="US"):
    return {"id": identifier, "name": "RoughPatchCpx", "country": country, "year": 2021,
            "start_utc": "2021-08-02T00:00:00+00:00", "end_utc": "2021-08-05T00:00:00+00:00",
            "height": 2, "width": 3, "epsg": 5070, "transform": [375, 0, 0, 0, -375, 750]}


def record(index, timestamp, component="OR-UMP-000373_RoughPatchCpx", number="OR-UPF-000373"):
    return {"source_record_id": index, "UTC": timestamp, "Incident_C": component,
            "Inc Number": number, "Inc Name": "Rough Patch Complex", "IRWINID": "exact-irwin"}


def physical(available=True):
    return {"farsite_inputs_available": available, "missing_farsite_inputs": [] if available else ["fuel"],
            "physical_landscape_valid_cells": 6 if available else None,
            "physical_landscape_complete_rectangle": available, "physical_input_audit_error": None}


def rows(events, records, *, verified=True, geometry=None, partitions=None):
    return module._event_rows(events, records,
                             partitions or {e["id"]: {"train": 0, "validation": 0, "test": 3} for e in events},
                             {e["id"]: physical(e["country"] == "US") for e in events},
                             geometry_records=set(range(20)) if geometry is None else geometry,
                             archive_verified=verified)


def test_exact_component_proves_roughpatch_alias_and_excludes_siblings():
    input_records = [record(0, "2021-08-03 04:06:00"), record(1, "2021-08-04 04:11:00"),
                     record(2, "2021-08-03 05:00:00", component="different-sibling")]
    output = rows([event()], input_records)[0]
    assert output["source_record_ids"] == [0, 1]
    assert output["observed_incident_number"] == "OR-UPF-000373"
    assert output["observed_incident_component"] == "OR-UMP-000373_RoughPatchCpx"
    assert output["matching_basis"] == "exact published Incident_C == local event_id"
    assert output["matching_evidence"][0]["IRWINID"] == "exact-irwin"
    assert output["consecutive_interval_count"] == 1
    assert output["consecutive_intervals"][0]["duration_minutes"] == 1445
    assert output["eligible"]


def test_duplicate_times_union_record_ids_and_preserve_actual_minutes():
    input_records = [record(0, "2021-08-03 04:06:00"), record(1, "2021-08-03 04:06:00"),
                     record(2, "2021-08-03 05:11:00")]
    output = rows([event()], input_records)[0]
    assert output["survey_record_count"] == 3
    assert output["distinct_survey_times"] == 2
    pair = output["consecutive_intervals"][0]
    assert pair["cutoff_source_record_ids"] == [0, 1]
    assert pair["endpoint_source_record_ids"] == [2]
    assert pair["duration_minutes"] == 65
    assert pair["hours"] == 65 / 60


def test_pairs_are_consecutive_and_both_endpoints_inside_cache():
    input_records = [record(0, "2021-08-01 12:00:00"), record(1, "2021-08-02 01:00:00"),
                     record(2, "2021-08-02 07:00:00"), record(3, "2021-08-06 12:00:00")]
    output = rows([event()], input_records)[0]
    assert output["distinct_survey_times"] == 4
    assert len(output["survey_times_in_cached_window"]) == 2
    assert output["consecutive_interval_count"] == 1
    assert output["exact_six_hour_interval_count"] == 1


def test_unknown_time_is_explicit_exclusion_not_interpolated():
    output = rows([event()], [record(0, "unknown"), record(1, "2021-08-03 04:06:00"),
                             record(2, "2021-08-04 04:06:00")])[0]
    assert not output["eligible"]
    assert output["invalid_timestamp_record_ids"] == [0]
    assert output["consecutive_interval_count"] == 1


def test_korean_events_are_audited_without_claiming_global_nonexistence():
    output = rows([event("KFS_06", "KR")], [record(0, "2021-08-03 04:06:00")])[0]
    assert not output["eligible"]
    assert output["source_record_ids"] == []
    assert "no paired observed perimeter reference acquired" in output["exclusion_reasons"][0]
    assert not output["farsite_inputs_available"]


def test_missing_or_unverified_geometry_prevents_eligibility():
    records = [record(0, "2021-08-03 04:06:00"), record(1, "2021-08-04 04:06:00")]
    assert not rows([event()], records, geometry={0})[0]["eligible"]
    assert not rows([event()], records, verified=False)[0]["eligible"]


def test_exact_number_fallback_requires_single_component():
    e = event("OR-UPF-000373_local")
    records = [record(0, "2021-08-03 04:06:00"), record(1, "2021-08-04 04:06:00")]
    output = rows([e], records)[0]
    assert output["eligible"]
    assert "exactly one" in output["matching_basis"]
    records.append(record(2, "2021-08-04 04:06:00", component="different-sibling"))
    assert not rows([e], records)[0]["eligible"]


@pytest.mark.parametrize("counts,expected", [({"train": 3, "validation": 2, "test": 0}, "training_or_validation_event"),
                                           ({"train": 0, "validation": 0, "test": 3}, "held_out_event"),
                                           ({"train": 0, "validation": 0, "test": 0}, "unrepresented_event")])
def test_exposure_labels_actual_saved_counts(counts, expected):
    e = event()
    output = rows([e], [record(0, "2021-08-03 04:06:00")], partitions={e["id"]: counts})[0]
    assert output["m548_exposure"] == expected


def fixture_archive(tmp_path):
    base = tmp_path / "surveys"
    with shapefile.Writer(str(base), shapeType=shapefile.POLYGON) as writer:
        for name in ("Incident_C", "Inc Number", "UTC", "Inc Name", "IRWINID"):
            writer.field(name, "C", size=80)
        for timestamp in ("2021-08-03 04:06:00", "2021-08-04 04:11:00"):
            writer.poly([[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]])
            writer.record(event()["id"], "OR-UPF-000373", timestamp, "Rough Patch Complex", "exact-irwin")
    # pyshp normalizes field spaces while writing. The authentic NIROPS DBF
    # preserves these spaces; reproduce its actual field-name contract.
    dbf = base.with_suffix(".dbf")
    dbf.write_bytes(dbf.read_bytes().replace(b"Inc_Number\x00", b"Inc Number\x00")
                    .replace(b"Inc_Name\x00", b"Inc Name\x00"))
    base.with_suffix(".prj").write_text("EPSG:4326")
    archive = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as packed:
        for extension in (".shp", ".shx", ".dbf", ".prj"):
            packed.write(base.with_suffix(extension), "surveys" + extension)
    data = tmp_path / "environment"
    data.mkdir()
    (data / "events.json").write_text(json.dumps([event(), event("KFS_06", "KR")]))
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "metadata.json").write_text(json.dumps({"event_ids": [event()["id"], "KFS_06"],
                                                       "split_policy": "test fixture"}))
    for split, indices in (("train", []), ("validation", []), ("test", [0, 0, 1])):
        np.savez(prepared / f"{split}.npz", event_index=np.array(indices, dtype=np.int64))
    return archive, data, prepared


def test_full_inventory_verifies_source_counts_and_csv_exports(tmp_path, monkeypatch):
    archive, data, prepared = fixture_archive(tmp_path)
    monkeypatch.setattr(module, "ARCHIVE_BYTES", archive.stat().st_size)
    monkeypatch.setattr(module, "ARCHIVE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(module, "_physical_availability", lambda e, d: physical(e["country"] == "US"))
    audit = module.build_inventory(data, archive=archive, prepared_directory=prepared)
    assert audit["archive_verified"]
    assert audit["event_count"] == 2
    assert audit["matched_us_event_count"] == 1
    assert audit["eligible_event_count"] == 1
    assert audit["eligible_interval_count"] == 1
    assert audit["events"][0]["m548_partition"] == {"train": 0, "validation": 0, "test": 2}
    assert audit["events"][1]["m548_partition"]["test"] == 1
    json_path, csv_path = module.write_inventory(audit, tmp_path / "output")
    assert json.loads(json_path.read_text())["events"][0]["matching_evidence"][0]["Inc Number"] == "OR-UPF-000373"
    flat = list(csv.DictReader(csv_path.open()))
    assert len(flat) == 2
    assert flat[0]["m548_test_samples"] == "2"
    assert flat[1]["eligible"] == "False"


def test_pinned_archive_mismatch_is_rejected(tmp_path):
    archive, data, prepared = fixture_archive(tmp_path)
    with pytest.raises(ValueError, match="pinned"):
        module.build_inventory(data, archive=archive, prepared_directory=prepared)


def test_fixture_unverified_archive_cannot_claim_eligibility(tmp_path, monkeypatch):
    archive, data, prepared = fixture_archive(tmp_path)
    monkeypatch.setattr(module, "_physical_availability", lambda e, d: physical(e["country"] == "US"))
    audit = module.build_inventory(data, archive=archive, prepared_directory=prepared, verify_archive=False)
    assert audit["eligible_event_count"] == 0
    assert audit["archive_sha256"] is None


def test_partition_indices_outside_saved_event_list_rejected(tmp_path):
    _, _, prepared = fixture_archive(tmp_path)
    np.savez(prepared / "train.npz", event_index=np.array([10]))
    with pytest.raises(ValueError, match="Invalid saved event indices"):
        module._partition_counts(prepared, [event()["id"]])


def test_timestamp_timezone_and_minute_contract():
    assert module._timestamp("2021-08-03T13:06:00+09:00").isoformat() == "2021-08-03T04:06:00+00:00"
    with pytest.raises(ValueError, match="whole minutes"):
        module._timestamp("2021-08-03T04:06:01Z")
