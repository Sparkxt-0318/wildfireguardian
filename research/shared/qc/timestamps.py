"""Timestamp quality control for KFS fire-record tables (T1.5b).

WHY THIS MODULE EXISTS
-----------------------
Both known KFS fire-record files carry dirty timestamps: the statistics file
(``kfs_fire_stats_csv``) is known to contain impossible end years (2055 and
2223) and reports 12 negative durations (the brief's own figure, confirmed by
``research/shared/loaders/kfs.py``); the state-history file
(``kfs_fire_state_history_csv``) is reported to carry 41 negative durations.
This module FLAGS these defects with added boolean columns. **It never drops
a row.** Every caller decides for itself, with the flags in hand, whether a
flagged row is excluded, imputed or kept with a caveat; that decision is not
made here.

COLUMN CONTRACT
----------------
This module works in two layers, deliberately, so it does not depend on
whichever loader eventually reads the state-history file (not on disk yet,
and not this agent's file to write):

1. :func:`parse_kfs_ymdhm` parses ONE raw KFS timestamp quadruple into a
   ``pandas.Series`` of ``datetime64[ns]`` values. Both known KFS CSVs report
   a timestamp as four columns sharing one prefix:
   ``<prefix>_년`` (year, int), ``<prefix>_월`` (month, int),
   ``<prefix>_일`` (day, int), ``<prefix>_시간`` (str, ``"HH:MM"``, minute
   resolution only; no seconds are reported anywhere in either file). This
   is the exact quadruple ``research/shared/loaders/kfs.py`` documents for
   ``발생일시`` and ``진화종료시간`` in the statistics file. The state-history
   file's own column names are not yet confirmed (the file is not on disk);
   if it uses a different quadruple naming, call :func:`parse_kfs_ymdhm` with
   that file's own prefix rather than assuming ``발생일시``/``진화종료시간``.
   A value that fails to parse (e.g. a malformed ``_시간`` string) becomes
   ``NaT``, per ``pandas.to_datetime(..., errors="coerce")``; it is not
   silently coerced to a guessed value.

2. :func:`flag_dirty_timestamps` takes two ALREADY-PARSED
   ``datetime64[ns]`` columns (a start column and an end column, produced by
   step 1 or by any other loader) and adds the QC flag columns. This layer
   never touches raw KFS column names, so it is reusable for any fire-record
   table with a start and an end timestamp, KFS or otherwise.

:func:`flag_kfs_ymdhm_timestamps` composes both layers for the common case of
a KFS-style quadruple pair.

TIME ZONE
---------
Every timestamp handled by this module is KST (UTC+9, fixed; Korea has not
observed daylight saving time since 1988). Neither the raw KFS columns nor
the ``datetime64[ns]`` values this module produces carry a timezone; KST is
assumed throughout and is never converted. See
``research/shared/geo/solar.py`` for the same convention applied to solar
geometry.

WHAT "NEGATIVE DURATION" AND "END BEFORE START" MEAN HERE
------------------------------------------------------------
The task brief names four defect categories: impossible end years, negative
durations, end before start, and missing containment. In this module,
duration is defined as ``end - start``, so "negative duration" and "end
before start" are the SAME boolean condition on non-missing timestamps; this
module still emits both as separately named flag columns
(``flag_negative_duration`` and ``flag_end_before_start``) because the brief
and the registry name them as separate categories and a caller may filter by
either name without knowing they coincide here. This equivalence is a
documented design decision, not an oversight: if a future loader ever
supplies an independently reported duration field (as opposed to one derived
from the two timestamps), that field would need its own comparison and is
out of scope for this module, which only ever sees start and end timestamps.

WHAT "IMPOSSIBLE END YEAR" MEANS HERE
----------------------------------------
An end year outside ``[min_reasonable_year, max_reasonable_year]``
(defaults: 1990 to 2035; both bounds keyword-configurable). ``pandas``
``datetime64[ns]`` supports years up to about 2262, so a value like 2223
parses successfully as a real ``Timestamp`` rather than becoming ``NaT``;
this is exactly why an explicit range check is needed here rather than
relying on a parse failure to catch it.
"""

from __future__ import annotations

import pandas as pd

#: Default plausible range for a KFS containment year. KFS's Korea-wide
#: digital fire-statistics record begins well after 1990; 2035 is a
#: generous forward margin past this program's 2026-10-24 finals date.
#: Callers with a different plausible range (e.g. a longer historical KFS
#: series) should pass their own bounds explicitly.
DEFAULT_MIN_REASONABLE_YEAR = 1990
DEFAULT_MAX_REASONABLE_YEAR = 2035


def parse_kfs_ymdhm(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Parse one KFS ``<prefix>_년/_월/_일/_시간`` quadruple into a datetime.

    Parameters
    ----------
    df:
        The already-loaded table. Must carry ``f"{prefix}_년"``,
        ``f"{prefix}_월"``, ``f"{prefix}_일"`` (numeric-like) and
        ``f"{prefix}_시간"`` (string ``"HH:MM"``).
    prefix:
        The shared column-name prefix, e.g. ``"발생일시"`` or
        ``"진화종료시간"`` for the statistics file. Documented contract only
        (see module docstring); this function does not hardcode either
        prefix so it works unchanged once the state-history file's own
        prefixes are confirmed.

    Returns
    -------
    pandas.Series
        ``datetime64[ns]``, minute resolution (KST, see module docstring).
        A row whose quadruple does not form a valid calendar timestamp (bad
        month, bad ``HH:MM``, or a missing component) becomes ``NaT``.
        Row order and index are preserved from ``df``.
    """
    # Numeric columns that carry any missing value (e.g. a row with no
    # containment year at all) come back from pandas as float64 (2024.0,
    # not 2024), because a plain int64 column cannot hold NaN. Route through
    # a nullable Int64 first so "2024.0" never reaches the string builder
    # below and corrupts every row's format match, not just the missing one.
    def _numeric_component(col: str, width: int) -> pd.Series:
        as_int = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        return as_int.astype("string").str.zfill(width)

    year = _numeric_component(f"{prefix}_년", 4)
    month = _numeric_component(f"{prefix}_월", 2)
    day = _numeric_component(f"{prefix}_일", 2)
    hm = df[f"{prefix}_시간"].astype("string").str.strip()
    stamp = year + "-" + month + "-" + day + " " + hm
    return pd.to_datetime(stamp, format="%Y-%m-%d %H:%M", errors="coerce")


def flag_dirty_timestamps(
    df: pd.DataFrame,
    start_col: str,
    end_col: str,
    *,
    min_reasonable_year: int = DEFAULT_MIN_REASONABLE_YEAR,
    max_reasonable_year: int = DEFAULT_MAX_REASONABLE_YEAR,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Flag dirty timestamps. Never drops a row. See module docstring.

    Parameters
    ----------
    df:
        Any table with two ``datetime64[ns]`` columns already parsed (e.g.
        by :func:`parse_kfs_ymdhm`, or by any other loader).
    start_col, end_col:
        Column names in ``df`` holding the reported start (report/ignition)
        and end (containment) timestamps. Must already be
        ``datetime64[ns]``; this function does not parse strings.
    min_reasonable_year, max_reasonable_year:
        Inclusive bounds an end year must fall within to NOT be flagged as
        impossible. Defaults documented above.

    Returns
    -------
    (df_out, counts)
        ``df_out`` is a copy of ``df`` with four added boolean columns
        (``qc_flag_missing_containment``, ``qc_flag_impossible_end_year``,
        ``qc_flag_negative_duration``, ``qc_flag_end_before_start``) and one
        added float column ``qc_duration_minutes`` (``NaN`` where either
        timestamp is missing or the end year is impossible; an impossible
        year makes the duration meaningless even though it is numerically
        computable). ``counts`` is a plain ``dict[str, int]`` with the
        number of ``True`` values per flag plus ``"n_rows"``, meant to be
        logged by every caller (per the task's "so every caller can log the
        counts").  ``len(df_out) == len(df)`` always: no row is ever
        dropped.
    """
    out = df.copy()

    start = out[start_col]
    end = out[end_col]

    missing_containment = end.isna()

    end_year = end.dt.year
    impossible_end_year = end.notna() & (
        (end_year < min_reasonable_year) | (end_year > max_reasonable_year)
    )

    both_present = start.notna() & end.notna()
    duration_minutes = pd.Series(pd.NA, index=out.index, dtype="Float64")
    duration_minutes.loc[both_present] = (
        (end[both_present] - start[both_present]).dt.total_seconds() / 60.0
    )
    # An impossible end year makes the computed duration meaningless (e.g. a
    # multi-century gap from a mistyped year field); it is set back to NaN
    # rather than reported as a giant-but-technically-computable number.
    duration_minutes.loc[impossible_end_year] = pd.NA

    negative_duration = both_present & (duration_minutes.fillna(0) < 0) & duration_minutes.notna()
    end_before_start = both_present & (end < start)

    out["qc_duration_minutes"] = duration_minutes.astype("float64")
    out["qc_flag_missing_containment"] = missing_containment.astype("bool")
    out["qc_flag_impossible_end_year"] = impossible_end_year.astype("bool")
    out["qc_flag_negative_duration"] = negative_duration.astype("bool")
    out["qc_flag_end_before_start"] = end_before_start.astype("bool")

    counts = {
        "n_rows": int(len(out)),
        "missing_containment": int(missing_containment.sum()),
        "impossible_end_year": int(impossible_end_year.sum()),
        "negative_duration": int(negative_duration.sum()),
        "end_before_start": int(end_before_start.sum()),
    }
    return out, counts


def flag_kfs_ymdhm_timestamps(
    df: pd.DataFrame,
    start_prefix: str,
    end_prefix: str,
    *,
    min_reasonable_year: int = DEFAULT_MIN_REASONABLE_YEAR,
    max_reasonable_year: int = DEFAULT_MAX_REASONABLE_YEAR,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Parse a KFS-style start/end quadruple pair and flag it in one call.

    Convenience composition of :func:`parse_kfs_ymdhm` (twice) and
    :func:`flag_dirty_timestamps`. See both docstrings for the column
    contract. Adds ``qc_start_dt`` and ``qc_end_dt`` (the parsed timestamps)
    to the returned frame alongside the QC flag columns, so the parse step
    is inspectable rather than thrown away.
    """
    out = df.copy()
    out["qc_start_dt"] = parse_kfs_ymdhm(out, start_prefix)
    out["qc_end_dt"] = parse_kfs_ymdhm(out, end_prefix)
    return flag_dirty_timestamps(
        out,
        "qc_start_dt",
        "qc_end_dt",
        min_reasonable_year=min_reasonable_year,
        max_reasonable_year=max_reasonable_year,
    )
