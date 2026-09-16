"""Tests for the shared splitters.

Most of these test a REFUSAL. That is the point of the module: a splitter that
silently returns a leaky fold is worse than no splitter, because the number it
produces looks like a held-out number.
"""

import pytest

from splits import (
    FIRE_COMPLEXES,
    LeakageRefusal,
    PRIMARY_SPLITS,
    Split,
    assert_group_disjoint,
    assert_min_separation,
    assert_time_ordered,
    audit_split,
    canonical_fire_id,
    complex_of,
    forward_chaining_by_year,
    leave_one_complex_out,
    leave_one_fire_out,
    primary_split_spec,
    spatial_block_cv,
    splits_fingerprint,
)

ROADS_FIRES = ["goseong_2019", "uljin_samcheok_2022", "gangneung_2023",
               "uiseong_andong_2025", "sancheong_2025"]


# ------------------------------------------------------------------- ids --

def test_korean_and_romanised_spellings_resolve_to_one_id():
    ids = {canonical_fire_id(s) for s in
           ["Uiseong 2025", "의성 2025", "의성·안동 2025", "uiseong-andong-2025", "안동2025"]}
    assert ids == {"uiseong_andong_2025"}


def test_an_empty_fire_id_is_refused():
    with pytest.raises(LeakageRefusal):
        canonical_fire_id("   ")
    with pytest.raises(LeakageRefusal):
        canonical_fire_id(None)


def test_the_2025_yeongnam_pair_is_one_complex():
    assert complex_of("의성 2025") == complex_of("영덕 2025") == "yeongnam_2025"
    assert FIRE_COMPLEXES["yeongdeok_2025"] == FIRE_COMPLEXES["uiseong_andong_2025"]


def test_an_unregistered_fire_is_refused_rather_than_made_its_own_complex():
    with pytest.raises(LeakageRefusal) as e:
        complex_of("some_new_fire_2026")
    assert "complex registry" in str(e.value)


def test_an_unregistered_fire_can_be_declared_by_the_caller():
    assert complex_of("some_new_fire_2026",
                      {"some_new_fire_2026": "yeongnam_2025"}) == "yeongnam_2025"


def test_non_strict_lookup_falls_back_to_the_normalised_id():
    assert complex_of("some_new_fire_2026", strict=False) == "somenewfire2026"


# ---------------------------------------------------- leave one fire out --

def test_leave_one_fire_out_gives_one_disjoint_fold_per_fire():
    rows = [f for f in ROADS_FIRES for _ in range(3)]
    folds = leave_one_fire_out(rows)
    assert len(folds) == len(ROADS_FIRES)
    assert {f.held_out for f in folds} == set(ROADS_FIRES)
    for f in folds:
        assert_group_disjoint(f, rows, "fire")
        assert len(f.test) == 3
        assert len(f.train) == 12


def test_leave_one_fire_out_refuses_a_fold_that_trains_on_the_same_complex():
    rows = ["uiseong_andong_2025", "yeongdeok_2025", "goseong_2019"]
    with pytest.raises(LeakageRefusal) as e:
        leave_one_fire_out(rows)
    assert "same complex" in str(e.value)
    assert "yeongnam_2025" in str(e.value)


def test_declaring_the_contamination_still_needs_a_written_reason():
    rows = ["uiseong_andong_2025", "yeongdeok_2025", "goseong_2019"]
    with pytest.raises(LeakageRefusal):
        leave_one_fire_out(rows, on_complex_overlap="declare")
    with pytest.raises(LeakageRefusal):
        leave_one_fire_out(rows, on_complex_overlap="declare", reason="   ")


def test_a_declared_contaminated_fold_carries_the_flag_and_the_reason():
    rows = ["uiseong_andong_2025", "yeongdeok_2025", "goseong_2019"]
    folds = leave_one_fire_out(rows, on_complex_overlap="declare",
                               reason="comparison against the canonical fold")
    dirty = [f for f in folds if f.meta.get("complex_contaminated")]
    assert {f.held_out for f in dirty} == {"uiseong_andong_2025", "yeongdeok_2025"}
    for f in dirty:
        assert f.meta["contamination_reason"]
        assert f.meta["complex_siblings_in_train"]


def test_an_unknown_value_for_on_complex_overlap_is_refused():
    with pytest.raises(LeakageRefusal):
        leave_one_fire_out(ROADS_FIRES, on_complex_overlap="ignore")


def test_leave_one_fire_out_needs_at_least_two_fires():
    with pytest.raises(LeakageRefusal):
        leave_one_fire_out(["goseong_2019", "goseong_2019"])


# ------------------------------------------------- leave one complex out --

def test_leave_one_complex_out_holds_the_yeongnam_pair_out_together():
    rows = ["uiseong_andong_2025", "yeongdeok_2025", "goseong_2019", "gangneung_2023"]
    folds = leave_one_complex_out(rows)
    pair = [f for f in folds if f.held_out == "yeongnam_2025"][0]
    assert sorted(pair.test) == [0, 1]
    assert pair.meta["fires_held_out"] == ["uiseong_andong_2025", "yeongdeok_2025"]


def test_leave_one_complex_out_refuses_an_unregistered_fire():
    with pytest.raises(LeakageRefusal):
        leave_one_complex_out(["goseong_2019", "mystery_fire_2026"])


def test_leave_one_complex_out_refuses_a_single_complex():
    with pytest.raises(LeakageRefusal) as e:
        leave_one_complex_out(["uiseong_andong_2025", "yeongdeok_2025"])
    assert "at least two complexes" in str(e.value)


def test_every_complex_fold_survives_its_own_audit_and_covers_each_row_once():
    rows = [f for f in ROADS_FIRES + ["yeongdeok_2025"] for _ in range(2)]
    folds = leave_one_complex_out(rows)
    seen = []
    for f in folds:
        audit_split(f, fire_ids=rows)
        seen.extend(f.test)
    assert sorted(seen) == list(range(len(rows)))


# ------------------------------------------------------- spatial block CV --

def _line(n=100, step=10.0):
    xs = [i * step for i in range(n)]
    ys = [0.0] * n
    return xs, ys


def test_spatial_blocks_never_straddle_a_fold():
    xs, ys = _line()
    folds = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=7)
    blocks = [int(x // 100) for x in xs]
    assert len(folds) == 5
    for f in folds:
        assert_group_disjoint(f, blocks, "spatial block")


def test_degrees_are_refused_because_block_size_is_metres():
    xs = [127.0 + i * 0.01 for i in range(50)]
    ys = [36.0 + i * 0.01 for i in range(50)]
    with pytest.raises(LeakageRefusal) as e:
        spatial_block_cv(xs, ys, block_size_m=5000.0, n_folds=5)
    assert "degrees" in str(e.value)


def test_degrees_are_allowed_only_when_the_caller_says_so():
    xs = [127.0 + i * 0.01 for i in range(50)]
    ys = [36.0 + i * 0.01 for i in range(50)]
    folds = spatial_block_cv(xs, ys, block_size_m=0.02, n_folds=5,
                             allow_degrees=True)
    assert len(folds) == 5


@pytest.mark.parametrize("kwargs", [
    {"block_size_m": 0.0, "n_folds": 5},
    {"block_size_m": -100.0, "n_folds": 5},
    {"block_size_m": 100.0, "n_folds": 1},
    {"block_size_m": 100.0, "n_folds": 5, "buffer_m": -1.0},
])
def test_nonsense_spatial_arguments_are_refused(kwargs):
    xs, ys = _line()
    with pytest.raises(LeakageRefusal):
        spatial_block_cv(xs, ys, **kwargs)


def test_too_few_blocks_for_the_requested_folds_is_refused():
    xs, ys = _line(n=20, step=1.0)          # 20 rows inside two 10 m blocks
    with pytest.raises(LeakageRefusal) as e:
        spatial_block_cv(xs, ys, block_size_m=10.0, n_folds=5)
    assert "cannot fill" in str(e.value)


def test_mismatched_or_missing_coordinates_are_refused():
    with pytest.raises(LeakageRefusal):
        spatial_block_cv([0.0, 1000.0], [0.0], block_size_m=100.0)
    with pytest.raises(LeakageRefusal):
        spatial_block_cv([0.0, float("nan")] + [1000.0] * 8, [0.0] * 10,
                         block_size_m=100.0)


def test_a_block_split_without_a_buffer_still_trains_next_to_the_test_rows():
    xs, ys = _line()
    folds = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=3)
    violated = False
    for f in folds:
        try:
            assert_min_separation(f, xs, ys, 20.0)
        except LeakageRefusal:
            violated = True
    assert violated, ("a block edge is not a barrier to spatial correlation; "
                      "this test exists so the buffer is not treated as optional")


def test_the_buffer_removes_the_training_rows_next_to_the_test_rows():
    xs, ys = _line()
    folds = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=3,
                             buffer_m=20.0)
    for f in folds:
        assert_min_separation(f, xs, ys, 20.0)
        assert f.meta["dropped_to_buffer"] > 0


def test_a_fire_never_straddles_a_fold_when_fire_disjointness_is_required():
    fires = ["goseong_2019", "uljin_samcheok_2022", "gangneung_2023",
             "miryang_2022", "sancheong_2025"]
    xs, ys, fire_ids = [], [], []
    for k, fire in enumerate(fires):
        for j in range(20):                  # each fire spans two 100 m blocks
            xs.append(k * 200.0 + j * 10.0)
            ys.append(0.0)
            fire_ids.append(fire)
    folds = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=11,
                             fire_ids=fire_ids, require_fire_disjoint=True)
    for f in folds:
        assert_group_disjoint(f, fire_ids, "fire")
        assert len({fire_ids[i] for i in f.test}) == 1


def test_requiring_fire_disjointness_without_fire_ids_is_refused():
    xs, ys = _line()
    with pytest.raises(LeakageRefusal):
        spatial_block_cv(xs, ys, block_size_m=100.0, require_fire_disjoint=True)


def test_the_same_seed_gives_the_same_split():
    xs, ys = _line()
    a = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=42)
    b = spatial_block_cv(xs, ys, block_size_m=100.0, n_folds=5, seed=42)
    assert splits_fingerprint(a) == splits_fingerprint(b)


# ------------------------------------------------------- forward chaining --

YEARS = [y for y in range(2010, 2026) for _ in range(4)]


def test_forward_chaining_never_trains_on_the_test_year_or_later():
    folds = forward_chaining_by_year(YEARS, min_train_years=5)
    assert folds
    for f in folds:
        assert_time_ordered(f, YEARS)
        assert max(f.meta["train_years"]) < min(f.meta["test_years"])


def test_forward_chaining_refuses_a_record_that_is_too_short():
    with pytest.raises(LeakageRefusal) as e:
        forward_chaining_by_year([2023, 2024, 2025], min_train_years=5)
    assert "distinct year" in str(e.value)


def test_the_embargo_year_is_left_out_of_training():
    folds = forward_chaining_by_year(YEARS, min_train_years=5, gap_years=1)
    for f in folds:
        assert_time_ordered(f, YEARS, gap_years=1)
        assert min(f.meta["test_years"]) - max(f.meta["train_years"]) >= 2


def test_a_rolling_window_keeps_only_the_recent_years():
    folds = forward_chaining_by_year(YEARS, min_train_years=5, window_years=5)
    for f in folds:
        assert len(f.meta["train_years"]) == 5


@pytest.mark.parametrize("kwargs", [
    {"horizon": 0}, {"gap_years": -1}, {"min_train_years": 0},
    {"window_years": 0},
])
def test_nonsense_forward_chaining_arguments_are_refused(kwargs):
    with pytest.raises(LeakageRefusal):
        forward_chaining_by_year(YEARS, **kwargs)


def test_time_order_is_refused_on_a_hand_made_backwards_split():
    bad = Split("hand_made", 0, "2020", train=(60,), test=(40,))   # 2025 vs 2020
    with pytest.raises(LeakageRefusal) as e:
        assert_time_ordered(bad, YEARS)
    assert "not before the first test year" in str(e.value)


# -------------------------------------------------- the Split object itself --

def test_a_split_with_a_row_on_both_sides_is_refused_at_construction():
    with pytest.raises(LeakageRefusal) as e:
        Split("hand_made", 0, "x", train=(0, 1, 2), test=(2, 3))
    assert "both sides" in str(e.value)


@pytest.mark.parametrize("train,test", [((), (1,)), ((0,), ())])
def test_an_empty_side_is_refused(train, test):
    with pytest.raises(LeakageRefusal):
        Split("hand_made", 0, "x", train=train, test=test)


def test_the_fingerprint_moves_when_the_fold_moves():
    a = Split("s", 0, "x", train=(0, 1), test=(2,))
    b = Split("s", 0, "x", train=(0, 1), test=(3,))
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() == Split("s", 0, "x", train=(1, 0), test=(2,)).fingerprint()


# ------------------------------------------------------------ the audit ----

def test_the_audit_catches_a_hand_made_split_that_leaks_a_complex():
    rows = ["uiseong_andong_2025", "goseong_2019", "yeongdeok_2025"]
    leaky = Split("hand_made", 0, "uiseong_andong_2025", train=(1, 2), test=(0,))
    assert_group_disjoint(leaky, rows, "fire")          # the fire itself is clean
    with pytest.raises(LeakageRefusal) as e:
        audit_split(leaky, fire_ids=rows)
    assert "complex" in str(e.value)


def test_the_audit_can_be_told_the_contamination_is_deliberate():
    rows = ["uiseong_andong_2025", "goseong_2019", "yeongdeok_2025"]
    leaky = Split("hand_made", 0, "uiseong_andong_2025", train=(1, 2), test=(0,))
    audit_split(leaky, fire_ids=rows, allow_complex_contamination=True)


def test_the_audit_refuses_groups_that_do_not_cover_the_indices():
    s = Split("hand_made", 0, "x", train=(0, 5), test=(1,))
    with pytest.raises(LeakageRefusal):
        assert_group_disjoint(s, ["a", "b"], "fire")


# ---------------------------------------------------------- the registry --

def test_each_direction_has_one_registered_primary_split():
    assert set(PRIMARY_SPLITS) == {"roads", "landslides", "suppression"}
    for direction in PRIMARY_SPLITS:
        spec = primary_split_spec(direction)
        assert spec["scheme"] in {"leave_one_complex_out", "spatial_block_cv",
                                  "forward_chaining_by_year"}
        assert spec["why"].strip()


def test_every_registered_split_carries_a_note_about_the_data_it_will_meet():
    for direction in PRIMARY_SPLITS:
        spec = primary_split_spec(direction)
        assert spec["data_note"].strip()
        assert spec["minimum_units"] >= 3


def test_the_registered_suppression_split_refuses_the_committed_four_year_extract():
    """2022 to 2025, 2020 rows, is the verified span of the committed extract.

    The registered scheme refuses it, and that refusal is the finding: the
    direction is conditional on the longer Korean record arriving.
    """
    years = [y for y in (2022, 2023, 2024, 2025) for _ in range(505)]
    assert len(years) == 2020
    spec = primary_split_spec("suppression")
    with pytest.raises(LeakageRefusal) as e:
        forward_chaining_by_year(years, **spec["kwargs"])
    assert "distinct year" in str(e.value)


def test_an_unregistered_direction_does_not_get_to_invent_a_split():
    with pytest.raises(LeakageRefusal) as e:
        primary_split_spec("scenarios")
    assert "no primary split is registered" in str(e.value)
