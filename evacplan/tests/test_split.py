"""The frozen dev/test split (instances/SPLIT.json): frozen, disjoint, regenerable, test untouched."""
import csv
import hashlib
import json

import numpy as np
import pytest

from evacplan.generators import GENERATOR, GENERATOR_VERSION
from evacplan.instances import (
    CACHE_DIR, EVACPLAN_ROOT, SPLIT_PATH, GeneratorDrift, canonical_sets, default_split_configs, fingerprint,
    generate_entry, load_entry, load_split, materialize,
)

# sha256 of the canonical JSON of SPLIT.json's sets, pinned when the split was frozen (2026-10-31,
# before any method ran). Changing the split needs Siyeong's approval (program rule 5).
FROZEN_SETS_SHA256 = "dfa65235f799748d90c9d79cb65993ad3217ee22af5f67e80c98ad1fa4c95c06"


@pytest.fixture(scope="module")
def split():
    return load_split(SPLIT_PATH)


@pytest.fixture(scope="module")
def regenerated(split):
    """Every split instance regenerated in memory (generation is not a method run)."""
    return {e.id: generate_entry(e) for name in ("dev", "test") for e in split.entries(name)}


def test_split_is_frozen(split):
    assert split.schema_version == "evacplan.split/1" and split.frozen == "2026-10-31"
    got = hashlib.sha256(canonical_sets(split).encode()).hexdigest()
    assert got == FROZEN_SETS_SHA256, "SPLIT.json changed: the split is frozen (changing it needs Siyeong's approval)"


def test_dev_and_test_are_disjoint_with_the_same_mix(split):
    assert set(split.sets) == {"dev", "test"}
    dev, test = split.entries("dev"), split.entries("test")
    ids = [e.id for e in dev + test]
    assert len(ids) == len(set(ids)) and not set(split.ids("dev")) & set(split.ids("test"))
    assert not {e.config["seed"] for e in dev} & {e.config["seed"] for e in test}

    def mix(entries):
        return sorted((e.config["size"], e.config["graph"], e.config["tightness"]) for e in entries)
    assert mix(dev) == mix(test)
    for entries in (dev, test):
        sizes = [e.config["size"] for e in entries]
        assert (sizes.count("S"), sizes.count("M"), sizes.count("L")) == (4, 4, 2)
    for e in dev + test:
        assert e.synthetic and e.id.startswith("SYNTHETIC-") and e.label == "SYNTHETIC"
        assert e.generator == GENERATOR and e.generator_version == GENERATOR_VERSION
    want = default_split_configs()
    for name in ("dev", "test"):
        assert [e.config for e in split.entries(name)] == [c.model_dump() for c in want[name]]


def test_every_instance_regenerates_to_its_fingerprint(split, regenerated):
    for name in ("dev", "test"):
        for e in split.entries(name):
            g = regenerated[e.id]
            assert g.instance_id == e.id and g.fingerprint() == e.fingerprint, f"generator drift: {e.id}"
            assert e.stats["residents"] == g.instance.residents_total
            assert e.stats["vehicles"] == len(g.instance.vehicles)


def test_split_instances_are_threatened_and_shelters_safe(split, regenerated):
    for e in split.entries("dev") + split.entries("test"):
        d = regenerated[e.id].diagnostics
        assert d["facilities_reached_within_horizon"] >= 1 and d["lead_realized_s"] > 0
        assert all(v is None for v in d["shelter_access_fire_arrival_s"].values()), e.id
        assert all(v is None for v in d["depot_access_fire_arrival_s"].values()), e.id


def test_cache_regenerates_and_refuses_drift(tmp_path, split):
    e = split.entries("dev")[0]
    p = materialize(e, tmp_path)
    assert p == tmp_path / e.id / "instance.json" and (tmp_path / e.id / "hazard" / "members.npz").is_file()
    inst, ss = load_entry(e, tmp_path)
    assert fingerprint(inst, ss) == e.fingerprint and inst.name == e.id and inst.synthetic
    p.write_text(p.read_text().replace('"release_s":', '"release_s": 1.0, "x":', 1))   # corrupt the cache
    materialize(e, tmp_path)
    assert fingerprint(*load_entry(e, tmp_path)) == e.fingerprint
    tampered = e.model_copy(update={"fingerprint": "sha256:" + "0" * 64})
    with pytest.raises(GeneratorDrift):
        materialize(tampered, tmp_path / "other")
    with pytest.raises(GeneratorDrift):
        generate_entry(e.model_copy(update={"generator_version": "evacplan.synthetic/0"}))


def test_test_set_is_untouched(split):
    """No result row and no cached instance of the test set exists (rule 5: test only at milestones,
    after Siyeong approves; then update this test in the same change)."""
    test_ids = set(split.ids("test"))
    for f in sorted((EVACPLAN_ROOT / "results").glob("*.csv")):
        with f.open(newline="") as fh:
            assert not {row["instance"] for row in csv.DictReader(fh)} & test_ids, f"test instance in {f}"
    if CACHE_DIR.is_dir():
        assert not {p.name for p in CACHE_DIR.iterdir()} & test_ids
    lb = EVACPLAN_ROOT / "LEADERBOARD.md"
    if lb.is_file():
        text = lb.read_text()
        assert not any(i in text for i in test_ids)


def test_split_json_is_plain_and_small():
    raw = SPLIT_PATH.read_text()
    assert len(raw.encode()) < 100_000 and json.loads(raw)["schema"] == "evacplan.split/1"
    assert np.isfinite([e["stats"]["horizon_s"] for s in json.loads(raw)["sets"].values() for e in s]).all()
