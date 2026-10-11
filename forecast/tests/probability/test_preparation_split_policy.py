"""Fresh preparation and cache adapters preserve explicit row-split semantics."""

import hashlib
import json
import shutil
import sys

from tests.probability.test_weighted_resplit import prepared
import wildfire.prepare as prepare_training
from wildfire.cache import load_split
from wildfire.cache import validate_partition_disjointness
from wildfire.prepare import filter_contact
from wildfire.prepare import resplit_existing_cache
from wildfire.prepare import subset_country


def test_fresh_preparation_defaults_to_weighted_rows_and_keeps_valid_lineage(prepared, tmp_path, monkeypatch):
    source, _, metadata = prepared
    output = tmp_path / "fresh"
    seen = []

    def extracted(args):
        seen.append((args.seed, args.split_seed, args.output_dir))
        for name in ("metadata.json", "train.npz", "validation.npz", "test.npz"):
            shutil.copyfile(source / name, args.output_dir / name)

    monkeypatch.setattr(prepare_training, "prepare_season_cache", extracted)
    monkeypatch.setattr(sys, "argv", ["prepare", "--output-dir", str(output),
                                     "--data-root", metadata["data_root"], "--seed", "19", "--split-seed", "11"])
    prepare_training.prepare_main()
    actual = json.loads((output / "metadata.json").read_text())
    record = json.loads((output / "resplit.json").read_text())
    assert seen[0][:2] == (19, 11)
    assert actual["split_unit"] == "cell_hour"
    assert actual["categorical_coverage"]["training_present"] == ["biome=4", "biome=8"]
    assert (output / "test.npz").read_bytes() == (source / "test.npz").read_bytes()
    assert actual["fresh_preparation"]["negative_sampling_seed"] == 19
    assert actual["fresh_preparation"]["split_seed"] == 11
    assert record["source_directory_retained"] is False
    assert not seen[0][2].exists()
    retained = output / actual["fresh_preparation"]["parent_metadata_file"]
    assert json.loads(retained.read_text()) == metadata
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == actual["parent_metadata_sha256"]
    for name, expected in record["output_cache_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected


def test_explicit_season_policy_still_uses_original_preparation(prepared, tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(prepare_training, "prepare_season_cache", lambda args: seen.append(args))
    monkeypatch.setattr(sys, "argv", ["prepare", "--output-dir", str(tmp_path / "legacy"),
                                     "--split-policy", "season"])
    prepare_training.prepare_main()
    assert len(seen) == 1 and seen[0].split_policy == "season"


def test_contact_and_country_adapters_keep_row_memberships_and_test_separation(prepared, tmp_path):
    source, _, _ = prepared
    balanced = tmp_path / "balanced"
    resplit_existing_cache(source, balanced)
    contact = tmp_path / "contact"
    metadata = filter_contact(balanced, contact)
    # Every fixture patch already has contact. Per-event accepted counts must
    # add train and validation rows, rather than overwrite with the last split.
    records = {entry["id"]: entry for entry in metadata["per_event"]}
    assert records["trainfire"]["accepted_samples"] == 16
    assert records["valfire"]["accepted_samples"] == 16
    assert metadata["split_summary"]["train"]["events"] == 2
    assert metadata["split_summary"]["validation"]["events"] == 2
    # Drop an empty event from the country selection, checking that the
    # original whole-fire map is also restricted to the remapped event list.
    records["emptyfire"]["country"] = "US"
    (contact / "metadata.json").write_text(json.dumps(metadata))
    country = tmp_path / "country"
    selected = subset_country(contact, country, "KR")
    assert selected["event_ids"] == ["trainfire", "valfire", "testfire"]
    assert set(selected["original_splits"]) == set(selected["event_ids"])
    data = {name: load_split(country, name, selected) for name in ("train", "validation", "test")}
    check = validate_partition_disjointness(data, selected)
    assert check["disjoint_cell_hour_identities"]
    assert check["test_fires_disjoint_from_training_validation"]
    assert not check["disjoint_contributing_fire_sets"]
    assert sum(len(data[name]) for name in ("train", "validation")) == 32
