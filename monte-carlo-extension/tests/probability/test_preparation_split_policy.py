"""Fresh preparation and cache adapters preserve explicit row-split semantics."""

import hashlib
import json
import shutil
import sys

import pytest

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
        seen.append((args.seed, args.split_seed, args.output_dir, args.chunk_hours))
        for name in ("metadata.json", "train.npz", "validation.npz", "test.npz"):
            shutil.copyfile(source / name, args.output_dir / name)

    monkeypatch.setattr(prepare_training, "prepare_season_cache", extracted)
    monkeypatch.setattr(sys, "argv", ["prepare", "--output-dir", str(output),
                                     "--data-root", metadata["data_root"], "--seed", "19", "--split-seed", "11"])
    prepare_training.prepare_main()
    actual = json.loads((output / "metadata.json").read_text())
    record = json.loads((output / "resplit.json").read_text())
    assert seen[0][:2] == (19, 11)
    assert seen[0][3] is None
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


@pytest.mark.parametrize("chunk_hours", [None, 2])
def test_explicit_season_policy_still_uses_original_preparation(prepared, tmp_path, monkeypatch, chunk_hours):
    seen = []
    monkeypatch.setattr(prepare_training, "prepare_season_cache", lambda args: seen.append(args))
    arguments = ["prepare", "--output-dir", str(tmp_path / "legacy"), "--split-policy", "season"]
    if chunk_hours is not None:
        arguments.extend(["--chunk-hours", str(chunk_hours)])
    monkeypatch.setattr(sys, "argv", arguments)
    prepare_training.prepare_main()
    assert len(seen) == 1 and seen[0].split_policy == "season"
    assert seen[0].chunk_hours == chunk_hours


@pytest.mark.parametrize("chunk_hours", [None, 2])
def test_public_preparation_factory_forwards_all_options_without_a_model(tmp_path, monkeypatch, chunk_hours):
    from wildfire import prepare_training_data

    seen = []
    monkeypatch.setattr(prepare_training, "prepare_season_cache", lambda args: seen.append(args))
    output = tmp_path / "public"
    root = tmp_path / "rasters"
    returned = prepare_training_data(
        output, data_root=root, channels=("weather.temperature_2m",), kernel_size=5,
        contact_negatives_per_event=17, no_contact_negatives_per_event=9,
        seed=19, split_policy="season", validation_fraction=.3, split_seed=11,
        chunk_hours=chunk_hours,
    )
    assert returned == output.resolve()
    assert len(seen) == 1
    actual = seen[0]
    assert actual.output_dir == output.resolve() and actual.data_root == root
    assert tuple(actual.channels) == ("weather.temperature_2m",)
    assert actual.kernel_size == 5
    assert actual.contact_negatives_per_event == 17 and actual.no_contact_negatives_per_event == 9
    assert actual.seed == 19 and actual.split_seed == 11
    assert actual.split_policy == "season" and actual.validation_fraction == .3
    assert actual.chunk_hours == chunk_hours


def test_public_weighted_preparation_runs_the_same_lineage_workflow(prepared, tmp_path, monkeypatch):
    from wildfire import prepare_training_data

    source, _, metadata = prepared
    output = tmp_path / "public_weighted"
    seen = []

    def extracted(args):
        seen.append(args)
        for name in ("metadata.json", "train.npz", "validation.npz", "test.npz"):
            shutil.copyfile(source / name, args.output_dir / name)

    monkeypatch.setattr(prepare_training, "prepare_season_cache", extracted)
    returned = prepare_training_data(output, data_root=metadata["data_root"], seed=19, split_seed=11)
    assert returned == output.resolve()
    assert seen[0].chunk_hours is None
    actual = json.loads((returned / "metadata.json").read_text())
    assert actual["split_unit"] == "cell_hour"
    assert actual["fresh_preparation"]["negative_sampling_seed"] == 19
    assert actual["fresh_preparation"]["split_seed"] == 11
    assert (returned / "test.npz").read_bytes() == (source / "test.npz").read_bytes()


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
