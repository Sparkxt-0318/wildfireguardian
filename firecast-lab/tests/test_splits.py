"""SPLITS.json: disjoint, an exact cover of events.json, by whole fire (repo metadata only, no rasters)."""
import copy
import json
import pickle
import zipfile
from datetime import datetime, timedelta

import pytest

from firecast_lab import splits as sp

C651_DIR = sp.REPO / "forecast/runs/20261010_categorical_balanced_benchmark"
C651_CHECKPOINT = C651_DIR / "candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt"


@pytest.fixture(scope="module")
def committed():
    catalog, sha = sp.load_catalog()
    return sp.load_splits(), catalog, sha


def test_committed_splits_pass_every_check(committed):
    sp.check(*committed)


def test_disjoint_exact_cover_and_locked_holdout(committed):
    splits, catalog, _ = committed
    dev, test = set(sp.fires("dev", splits=splits)), set(sp.fires("test", splits=splits))
    holdout = set(sp.fires("fresh_holdout", splits=splits))
    assert not dev & test and not holdout & (dev | test)
    assert dev | test | holdout == {e["id"] for e in catalog}
    assert len(splits["fires"]) == len(catalog) == 44
    assert (len(dev), len(test), len(holdout)) == (34, 10, 0)
    assert splits["splits"]["fresh_holdout"]["locked"] is True


def test_test_split_is_the_held_out_seasons_and_c651_test(committed):
    splits, catalog, _ = committed
    seasons = {(e["country"], e["year"]) for e in catalog if e["id"] in sp.fires("test", splits=splits)}
    assert seasons == {("US", 2024), ("KR", 2025)}
    protocol = json.loads((C651_DIR / "protocol.json").read_text())
    c651_test = {k for k, v in protocol["original_splits"].items() if v == "test"}
    assert set(sp.fires("test", splits=splits)) == c651_test


def test_folds_partition_dev_by_whole_fire(committed):
    splits, catalog, _ = committed
    folds = {name: set(sp.fires("dev", fold=name, splits=splits)) for name in splits["folds"]}
    assert sorted(len(v) for v in folds.values()) == [7, 13, 14]
    assert set().union(*folds.values()) == set(sp.fires("dev", splits=splits))
    assert sum(len(v) for v in folds.values()) == 34                      # pairwise disjoint
    kr_dev = {e["id"] for e in catalog if e["country"] == "KR" and e["year"] in (2022, 2023)}
    assert kr_dev <= folds["Y2022_2023"]


def test_short_fire_flags_match_hand_count(committed):
    # Hand count from events.json durations (h): KFS_07 27, KFS_09 12, KFS_14 15, KFS_15 21, KFS_16 1, KFS_17 32.
    splits, _, _ = committed
    short = {f["id"] for f in splits["fires"] if "too_short_24h" in f["flags"]}
    assert short == {"KFS_07", "KFS_09", "KFS_14", "KFS_15", "KFS_16", "KFS_17"}
    assert sp.approx_windows("2023-04-02T02:00:00+00:00", "2023-04-03T18:00:00+00:00", 24) == 1   # 40 h
    assert sp.approx_windows("2000-01-01T00:00:00+00:00", "2000-01-02T12:00:00+00:00", 24) == 0   # 36 h
    assert sp.approx_windows("2000-01-01T00:00:00+00:00", "2000-01-02T12:00:00+00:00", 12) == 1   # 36 h


class _Stub:
    def __init__(self, *args, **kwargs):
        pass

    def __setstate__(self, state):
        pass


class _ContractOnly(pickle.Unpickler):
    """Reads the checkpoint's plain-Python contract without torch: every class becomes an inert stub."""

    def find_class(self, module, name):
        if (module, name) == ("collections", "OrderedDict"):
            import collections
            return collections.OrderedDict
        return _Stub

    def persistent_load(self, pid):
        return None


def test_c651_roles_match_the_checkpoint_contract(committed):
    splits, _, _ = committed
    with zipfile.ZipFile(C651_CHECKPOINT) as archive:
        name = next(n for n in archive.namelist() if n.endswith("data.pkl"))
        contract = _ContractOnly(archive.open(name)).load()["contract"]
    roles = {f["id"]: f["c651_role"] for f in splits["fires"]}
    for fire, used in contract["splits"].items():
        expected = {(): "none", ("train", "validation"): "train+validation",
                    ("test",): ("test", "test_declared_no_rows")}[tuple(used)]
        assert roles[fire] in (expected if isinstance(expected, tuple) else (expected,)), fire
    # Row counts: 25 train/validation fires and 8 test fires with rows
    # (forecast/documents/weighted_stratified_split_20261009.md:27-35); KFS_06, KFS_13 have none (:293-294).
    assert sum(r == "train+validation" for r in roles.values()) == 25
    assert sum(r == "test" for r in roles.values()) == 8
    assert {k for k, r in roles.items() if r == "test_declared_no_rows"} == {"KFS_06", "KFS_13"}


def _problems(splits, catalog, sha):
    with pytest.raises(ValueError) as err:
        sp.check(splits, catalog, sha)
    return err.value.args[0].split("\n  ")[1:]


def test_check_rejects_a_fire_in_two_splits(committed):
    splits, catalog, sha = copy.deepcopy(committed)
    twin = copy.deepcopy(splits["fires"][0])
    twin["split"], twin["fold"] = "dev", "Y2020"
    splits["fires"].append(twin)
    assert any("more than once" in p for p in _problems(splits, catalog, sha))


def test_check_rejects_a_missing_fire_and_a_changed_catalog(committed):
    splits, catalog, sha = copy.deepcopy(committed)
    splits["fires"].pop()
    problems = _problems(splits, catalog, "0" * 64)
    assert any("exact cover" in p for p in problems) and any("sha256" in p for p in problems)


def test_check_rejects_window_level_membership(committed):
    splits, catalog, sha = copy.deepcopy(committed)
    splits["fires"][0]["cutoffs"] = ["2025-03-23T02:00:00+00:00"]
    assert any("whole-fire records only" in p for p in _problems(splits, catalog, sha))


def test_check_rejects_a_dev_fire_moved_to_test(committed):
    splits, catalog, sha = copy.deepcopy(committed)
    record = next(f for f in splits["fires"] if f["id"] == "KFS_02")
    record["split"], record["fold"] = "test", None
    assert any("season rule" in p for p in _problems(splits, catalog, sha))


def test_check_keeps_space_time_overlapping_fires_together(committed):
    # Move PNFNorthComplex (Y2020) one year later, into the window of Dixie (Y2021), which overlaps it in
    # space. Everything else stays consistent, so the overlap rule is the only problem.
    splits, catalog, sha = copy.deepcopy(committed)
    fire = "CA-PNF-001308_PNFNorthComplex"
    for record in [next(e for e in catalog if e["id"] == fire), next(f for f in splits["fires"] if f["id"] == fire)]:
        for key in ("start_utc", "end_utc"):
            record[key] = (datetime.fromisoformat(record[key]) + timedelta(days=365)).isoformat()
    problems = _problems(splits, catalog, sha)
    assert len(problems) == 1 and "overlap in space and time" in problems[0]


def test_unknown_split_name_is_an_error(committed):
    with pytest.raises(ValueError):
        sp.fires("validation", splits=committed[0])
