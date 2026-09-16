"""Tests for research/shared/qc/timestamps.py (T1.5b).

All frames are synthetic, built in this file, per the task's instruction to
test QC transforms independently of any loader (A1's kfs.py loader may not
exist while this file is authored) and independently of the real CSV.
"""

from __future__ import annotations

import pandas as pd

from research.shared.qc.timestamps import (
    flag_dirty_timestamps,
    flag_kfs_ymdhm_timestamps,
    parse_kfs_ymdhm,
)


def _synthetic_ymdhm_frame() -> pd.DataFrame:
    """Six synthetic KFS-style records covering every defect this module
    flags, plus one clean record, in the exact `<prefix>_년/_월/_일/_시간`
    quadruple contract documented in timestamps.py.
    """
    rows = [
        # 0: clean record, positive duration
        dict(sy=2024, sm=3, sd=15, sh="14:00", ey=2024, em=3, ed=15, eh="18:30"),
        # 1: negative duration / end before start (end clock time before start,
        #    same day) - the administrative-error pattern the brief describes
        dict(sy=2024, sm=4, sd=2, sh="10:00", ey=2024, em=4, ed=2, eh="09:00"),
        # 2: impossible end year, matches the brief's 2055 example
        dict(sy=2023, sm=5, sd=1, sh="09:00", ey=2055, em=5, ed=1, eh="12:00"),
        # 3: impossible end year, matches the brief's 2223 example
        dict(sy=2022, sm=6, sd=10, sh="08:00", ey=2223, em=6, ed=10, eh="10:00"),
        # 4: missing containment (end fields blank / unparsable)
        dict(sy=2024, sm=7, sd=4, sh="11:00", ey=None, em=None, ed=None, eh=None),
        # 5: clean record, different day
        dict(sy=2025, sm=1, sd=20, sh="06:00", ey=2025, em=1, ed=21, eh="02:00"),
    ]
    df = pd.DataFrame(
        {
            "발생일시_년": [r["sy"] for r in rows],
            "발생일시_월": [r["sm"] for r in rows],
            "발생일시_일": [r["sd"] for r in rows],
            "발생일시_시간": [r["sh"] for r in rows],
            "진화종료시간_년": [r["ey"] for r in rows],
            "진화종료시간_월": [r["em"] for r in rows],
            "진화종료시간_일": [r["ed"] for r in rows],
            "진화종료시간_시간": [r["eh"] for r in rows],
        }
    )
    return df


def test_parse_kfs_ymdhm_basic():
    df = _synthetic_ymdhm_frame()
    start = parse_kfs_ymdhm(df, "발생일시")
    assert pd.api.types.is_datetime64_any_dtype(start)
    assert start.iloc[0] == pd.Timestamp("2024-03-15 14:00")
    # row 4 has no end fields at all -> NaT, not dropped, not guessed
    end = parse_kfs_ymdhm(df, "진화종료시간")
    assert pd.isna(end.iloc[4])
    assert len(end) == len(df)


def test_flag_kfs_ymdhm_timestamps_never_drops_rows():
    df = _synthetic_ymdhm_frame()
    out, counts = flag_kfs_ymdhm_timestamps(df, "발생일시", "진화종료시간")
    assert len(out) == len(df)
    assert counts["n_rows"] == len(df)


def test_flag_counts_match_synthetic_design():
    df = _synthetic_ymdhm_frame()
    out, counts = flag_kfs_ymdhm_timestamps(df, "발생일시", "진화종료시간")

    assert counts["missing_containment"] == 1  # row 4
    assert counts["impossible_end_year"] == 2  # rows 2, 3
    assert counts["negative_duration"] == 1  # row 1
    assert counts["end_before_start"] == 1  # row 1 (identical by construction)

    assert bool(out.loc[0, "qc_flag_negative_duration"]) is False
    assert bool(out.loc[1, "qc_flag_negative_duration"]) is True
    assert bool(out.loc[2, "qc_flag_impossible_end_year"]) is True
    assert bool(out.loc[3, "qc_flag_impossible_end_year"]) is True
    assert bool(out.loc[4, "qc_flag_missing_containment"]) is True
    assert bool(out.loc[5, "qc_flag_negative_duration"]) is False


def test_negative_duration_and_end_before_start_always_agree():
    """Documented design decision in timestamps.py: with only two parsed
    timestamps as input, these two flags are the same boolean condition.
    """
    df = _synthetic_ymdhm_frame()
    out, _ = flag_kfs_ymdhm_timestamps(df, "발생일시", "진화종료시간")
    assert (
        out["qc_flag_negative_duration"] == out["qc_flag_end_before_start"]
    ).all()


def test_impossible_end_year_makes_duration_nan_not_a_giant_number():
    df = _synthetic_ymdhm_frame()
    out, _ = flag_kfs_ymdhm_timestamps(df, "발생일시", "진화종료시간")
    assert pd.isna(out.loc[2, "qc_duration_minutes"])
    assert pd.isna(out.loc[3, "qc_duration_minutes"])
    # a clean row still gets a real, positive duration
    assert out.loc[0, "qc_duration_minutes"] == 270.0  # 14:00 -> 18:30


def test_custom_year_bounds():
    """A caller with a different plausible range gets different flags,
    exercising the min/max_reasonable_year keywords directly.
    """
    df = pd.DataFrame(
        {
            "start_dt": pd.to_datetime(["2010-01-01 00:00"]),
            "end_dt": pd.to_datetime(["2010-01-01 01:00"]),
        }
    )
    _, counts_default = flag_dirty_timestamps(df, "start_dt", "end_dt")
    assert counts_default["impossible_end_year"] == 0  # 2010 is within [1990, 2035]

    # tighten the lower bound above 2010 to force a flag
    _, counts_tight = flag_dirty_timestamps(
        df, "start_dt", "end_dt", min_reasonable_year=2011, max_reasonable_year=2035
    )
    assert counts_tight["impossible_end_year"] == 1


def test_generic_flag_dirty_timestamps_on_prebuilt_columns():
    """The lower-layer function works on any two datetime64 columns,
    independent of the KFS quadruple contract (documents the two-layer
    design in timestamps.py).
    """
    df = pd.DataFrame(
        {
            "a": pd.to_datetime(["2024-01-01 08:00", "2024-01-02 08:00", None]),
            "b": pd.to_datetime(["2024-01-01 09:00", "2024-01-02 07:00", None]),
        }
    )
    out, counts = flag_dirty_timestamps(df, "a", "b")
    assert len(out) == 3
    assert counts["negative_duration"] == 1  # row 1: b before a
    assert counts["missing_containment"] == 1  # row 2: b is NaT
    assert counts["n_rows"] == 3
