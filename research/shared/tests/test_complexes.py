"""Tests for research/shared/qc/complexes.py (T1.5c)."""

from __future__ import annotations

import pandas as pd

from research.shared.qc.complexes import (
    COMPLEX_MEMBERSHIP,
    assign_complex_id,
)


def _synthetic_records() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "record_id": [
                "uiseong_a",
                "uiseong_b",
                "yeongdeok",
                "andong",
                "uljin_2022",
                "gangneung_2023",
                "uiseong_2019",  # same county name, different (non-complex) year
            ],
            "year": [2025, 2025, 2025, 2025, 2022, 2023, 2019],
            "sigungu": [
                "경상북도 의성군",
                "경상북도 의성군",
                "경상북도 영덕군",
                "경상북도 안동시",
                "경상북도 울진군",
                "강원특별자치도 강릉시",
                "경상북도 의성군",
            ],
            "area_ha": [52707.3, 46575.0, 1200.0, 300.0, 20913.0, 379.0, 5.0],
        }
    )


def test_uiseong_pair_grouped_with_yeongdeok_and_andong():
    df = _synthetic_records()
    ids = assign_complex_id(df, year_col="year", region_col="sigungu")

    complex_id = COMPLEX_MEMBERSHIP[0]["id"]

    by_record = dict(zip(df["record_id"], ids))
    assert by_record["uiseong_a"] == complex_id
    assert by_record["uiseong_b"] == complex_id
    assert by_record["yeongdeok"] == complex_id
    assert by_record["andong"] == complex_id
    # the two Uiseong rows share the complex id exactly, per the task's
    # "Uiseong 2025 appears as two same-day records" example
    assert by_record["uiseong_a"] == by_record["uiseong_b"]


def test_unrelated_fires_not_swept_into_the_complex():
    df = _synthetic_records()
    ids = assign_complex_id(df, year_col="year", region_col="sigungu")
    complex_id = COMPLEX_MEMBERSHIP[0]["id"]

    by_record = dict(zip(df["record_id"], ids))
    assert by_record["uljin_2022"] != complex_id
    assert by_record["gangneung_2023"] != complex_id
    # same county name (의성) but wrong year -> not part of the 2025 complex
    assert by_record["uiseong_2019"] != complex_id


def test_standalone_ids_are_unique_per_row():
    df = _synthetic_records()
    ids = assign_complex_id(df, year_col="year", region_col="sigungu")
    by_record = dict(zip(df["record_id"], ids))
    standalone = [
        by_record["uljin_2022"],
        by_record["gangneung_2023"],
        by_record["uiseong_2019"],
    ]
    assert len(set(standalone)) == 3  # all distinct, no accidental collision


def test_every_row_gets_a_non_null_id():
    df = _synthetic_records()
    ids = assign_complex_id(df, year_col="year", region_col="sigungu")
    assert ids.notna().all()
    assert len(ids) == len(df)


def test_deterministic_across_repeated_calls():
    """The whole point of a shared function is that roads, landslides and
    suppression get IDENTICAL groupings; simulate that by calling it three
    times (as three directions would) and checking byte-identical output.
    """
    df = _synthetic_records()
    ids_roads = assign_complex_id(df, year_col="year", region_col="sigungu")
    ids_landslides = assign_complex_id(df, year_col="year", region_col="sigungu")
    ids_suppression = assign_complex_id(df, year_col="year", region_col="sigungu")
    assert ids_roads.equals(ids_landslides)
    assert ids_roads.equals(ids_suppression)


def test_missing_region_falls_back_to_standalone():
    df = pd.DataFrame(
        {"year": [2025], "sigungu": [pd.NA]},
    )
    ids = assign_complex_id(df, year_col="year", region_col="sigungu")
    complex_id = COMPLEX_MEMBERSHIP[0]["id"]
    assert ids.iloc[0] != complex_id


def test_does_not_mutate_input_frame():
    df = _synthetic_records()
    before = df.copy(deep=True)
    assign_complex_id(df, year_col="year", region_col="sigungu")
    pd.testing.assert_frame_equal(df, before)
