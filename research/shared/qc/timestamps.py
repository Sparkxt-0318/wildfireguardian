"""Timestamp quality control for KFS fire-record tables (T1.5b, T1.5f).

WHY THIS MODULE EXISTS
-----------------------
Both known KFS fire-record files carry dirty timestamps: the statistics file
(``kfs_fire_stats_csv``) is known to contain impossible end years (2055 and
2223) and 12 negative durations (confirmed by
``research/shared/loaders/kfs.py`` and by this module, see T1.5b's own
measured counts below); the state-history file
(``kfs_fire_state_history_csv``, on disk since round 2, 2026-09-16) carries
41 negative durations, confirmed T1.5f by THREE independent counts: A1's
check script, the orchestrator, and this module's own
:func:`flag_kfs_state_history_timestamps` (see this agent's round-2 report
for the measured run). This module FLAGS these defects with added boolean
columns. **It never drops a row.** Every caller decides for itself, with the
flags in hand, whether a flagged row is excluded, imputed or kept with a
caveat; that decision is not made here.

COLUMN CONTRACT
----------------
⚠ **The two known KFS files do NOT share one timestamp format.** Round 1 of
this module assumed the state-history file would reuse the statistics
file's ``<prefix>_년/_월/_일/_시간`` quadruple, because the file was not yet
on disk and that was the only documented KFS shape available to design
against. Now that the file is on disk (round 2), that assumption is
confirmed WRONG for it: ``진화시작시간``/``진화완료시간`` are already
combined ``"YYYY-MM-DD HH:MM"`` strings, one column each, not four columns
per timestamp. This module therefore offers two layer-1 parsers, one per
confirmed real contract, both feeding the SAME layer-2 flagging function:

1. :func:`parse_kfs_ymdhm` parses ONE raw KFS timestamp quadruple into a
   ``pandas.Series`` of ``datetime64[ns]`` values, for a table that reports a
   timestamp as four columns sharing one prefix: ``<prefix>_년`` (year, int),
   ``<prefix>_월`` (month, int), ``<prefix>_일`` (day, int), ``<prefix>_시간``
   (str, ``"HH:MM"``, minute resolution only; no seconds). This is the exact
   quadruple ``research/shared/loaders/kfs.py`` documents for ``발생일시`` and
   ``진화종료시간`` in the STATISTICS file only. A value that fails to parse
   (e.g. a malformed ``_시간`` string) becomes ``NaT``, per
   ``pandas.to_datetime(..., errors="coerce")``; it is not silently coerced
   to a guessed value.

1b. :func:`parse_kfs_datetime_column` parses ONE column that is already a
   combined ``"YYYY-MM-DD HH:MM"`` (or a bare ``"YYYY-MM-DD"``) string into
   ``datetime64[ns]``. This is the confirmed real contract for the
   STATE-HISTORY file's ``진화시작시간``/``진화완료시간`` (and would also
   cover its date-only ``산불신고일``, though that column is not part of the
   duration calculation). Same ``NaT``-on-failure behaviour as above.

2. :func:`flag_dirty_timestamps` takes two ALREADY-PARSED
   ``datetime64[ns]`` columns (a start column and an end column, produced by
   either layer-1 parser above, or by any other loader) and adds the QC flag
   columns. This layer never touches raw KFS column names, so it is reusable
   for any fire-record table with a start and an end timestamp, KFS or
   otherwise.

:func:`flag_kfs_ymdhm_timestamps` composes layer 1 (quadruple) + layer 2 for
the statistics file's shape. :func:`flag_kfs_state_history_timestamps`
composes layer 1b (combined string) + layer 2 for the state-history file's
shape. **These are two different functions for two different real column
shapes, not one function with an assumed shape**, which is precisely the
mistake round 1 could not yet detect (the file was not on disk to check
against).

COLUMN-NAME WHITESPACE
------------------------
The state-history file's real header row carries trailing whitespace on
EVERY column name (e.g. ``"산불신고일     "``, five trailing spaces;
confirmed against the committed CSV, round 2). A caller who looks up a
column by its clean name (``"산불신고일"``) against an unstripped frame gets
a ``KeyError``, not a wrong answer, which is at least loud, but avoidable:
every public function in this module that looks up a column by name
(:func:`parse_kfs_ymdhm`, :func:`parse_kfs_datetime_column`) strips
``df.columns`` defensively FIRST (see :func:`_strip_column_names`), so a
caller may pass either a raw, unstripped frame or an already-stripped one
(e.g. from ``research.shared.loaders.kfs.load_fire_state_history``, which
also strips) and get the same result either way.

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


def _strip_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Return a shallow copy of ``df`` with whitespace stripped from column
    names. Defensive: the state-history file's real header row carries
    trailing whitespace on every column (confirmed round 2, see module
    docstring), so a column looked up by its clean name would otherwise
    raise ``KeyError`` on a frame that was not already stripped by the
    caller's own load path. A frame that is already clean is returned with
    no observable change beyond the copy.
    """
    out = df.copy()
    out.columns = [c.strip() if isinstance(c, str) else c for c in out.columns]
    return out


def parse_kfs_ymdhm(df: pd.DataFrame, prefix: str) -> pd.Series:
    """Parse one KFS ``<prefix>_년/_월/_일/_시간`` quadruple into a datetime.

    Parameters
    ----------
    df:
        The already-loaded table. Must carry ``f"{prefix}_년"``,
        ``f"{prefix}_월"``, ``f"{prefix}_일"`` (numeric-like) and
        ``f"{prefix}_시간"`` (string ``"HH:MM"``). Column names are stripped
        defensively first (see :func:`_strip_column_names`), so ``df`` may
        be raw or already-clean.
    prefix:
        The shared column-name prefix. Confirmed (round 2) to describe only
        the STATISTICS file's ``발생일시``/``진화종료시간`` columns; the
        state-history file does NOT use this quadruple shape at all (see
        module docstring and :func:`parse_kfs_datetime_column`), so this
        function's ``prefix`` is not a generic hook for "whatever the
        state-history file turns out to use" -- that assumption from round 1
        is now known to be wrong for that file.

    Returns
    -------
    pandas.Series
        ``datetime64[ns]``, minute resolution (KST, see module docstring).
        A row whose quadruple does not form a valid calendar timestamp (bad
        month, bad ``HH:MM``, or a missing component) becomes ``NaT``.
        Row order and index are preserved from ``df``.
    """
    df = _strip_column_names(df)

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


def parse_kfs_datetime_column(df: pd.DataFrame, col: str) -> pd.Series:
    """Parse a KFS column that is already a combined datetime STRING.

    Confirmed (round 2, 2026-09-16) contract for the state-history file's
    ``진화시작시간``/``진화완료시간`` columns: each is one column holding
    ``"YYYY-MM-DD HH:MM"`` (minute resolution, no seconds), not a
    ``_년/_월/_일/_시간`` quadruple. Its ``산불신고일`` column is the same
    idea at date-only resolution (``"YYYY-MM-DD"``) and also parses cleanly
    through this function, though it is not part of this module's duration
    calculation (see :func:`flag_kfs_state_history_timestamps`).

    Parameters
    ----------
    df:
        The already-loaded table. Column names are stripped defensively
        first (see :func:`_strip_column_names`), so ``df`` may be raw or
        already-clean and ``col`` should be passed clean either way (e.g.
        ``"진화시작시간"``, not ``"진화시작시간          "``).
    col:
        The column name to parse, after stripping.

    Returns
    -------
    pandas.Series
        ``datetime64[ns]`` (KST, see module docstring). A value that fails
        to parse becomes ``NaT`` (``errors="coerce"``), never a guessed
        value. Row order and index are preserved from ``df``.
    """
    df = _strip_column_names(df)
    return pd.to_datetime(df[col].astype("string").str.strip(), errors="coerce")


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


def flag_kfs_state_history_timestamps(
    df: pd.DataFrame,
    start_col: str = "진화시작시간",
    end_col: str = "진화완료시간",
    *,
    min_reasonable_year: int = DEFAULT_MIN_REASONABLE_YEAR,
    max_reasonable_year: int = DEFAULT_MAX_REASONABLE_YEAR,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Parse and flag ``kfs_fire_state_history_csv``'s own start/end columns.

    **This is the transform this program's directions actually run against
    the state-history file (T1.5f)** -- :func:`flag_kfs_ymdhm_timestamps` is
    for the STATISTICS file's quadruple shape and does not apply here (see
    module docstring). Composes :func:`parse_kfs_datetime_column` (twice,
    defaulting to the file's real, confirmed column names
    ``진화시작시간``/``진화완료시간``) and :func:`flag_dirty_timestamps`.
    Column names are stripped defensively (both parser calls go through
    :func:`_strip_column_names`), so ``df`` may come from a raw
    ``pandas.read_csv`` of the committed file or from
    ``research.shared.loaders.kfs.load_fire_state_history`` (which also
    strips); either way the result is identical.

    Adds ``qc_start_dt`` and ``qc_end_dt`` (the parsed timestamps) to the
    returned frame alongside the QC flag columns, same convention as
    :func:`flag_kfs_ymdhm_timestamps`.
    """
    out = _strip_column_names(df)
    out["qc_start_dt"] = parse_kfs_datetime_column(out, start_col)
    out["qc_end_dt"] = parse_kfs_datetime_column(out, end_col)
    return flag_dirty_timestamps(
        out,
        "qc_start_dt",
        "qc_end_dt",
        min_reasonable_year=min_reasonable_year,
        max_reasonable_year=max_reasonable_year,
    )
