"""Loaders for Korea Forest Service (KFS) datasets.

Owned by A1 (data acquisition). Only ``load_fire_stats_csv`` is implemented
so far, for the registry entry ``kfs_fire_stats_csv``. The Open API loader
(``load_fire_stats``, registry entry ``kfs_fire_stats_api``) is blocked on
WJ-001 (DATA_GO_KR_KEY unset) and is not implemented here; see
``research/data/checks/probe_kfs_api.py``, which is the one command to run the
moment the key lands.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO / "data" / "raw" / "kfs_fire_statistics" / \
    "산림청_산불통계데이터_20250911.csv"

#: CP949 / EUC-KR only. The portal does not ship UTF-8 for this file.
ENCODING = "cp949"


def load_fire_stats_csv(path: "Path | None" = None):
    """Load 산림청_산불통계데이터 (KFS wildfire occurrence statistics, CSV).

    Registry id: ``kfs_fire_stats_csv``. Source:
    https://www.data.go.kr/data/15121380/fileData.do

    Parameters
    ----------
    path:
        Optional override. Defaults to the committed copy under
        ``data/raw/kfs_fire_statistics/``.

    Returns
    -------
    pandas.DataFrame
        One row per recorded wildfire occurrence, 2,020 rows as of the file
        checked in on 2025-09-11 (sha256
        ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153).
        Temporal coverage of 발생일시 in this file is 2022 to 2025 (measured by
        ``research/data/checks/check_kfs_fire_stats_csv.py``, not assumed).

    Columns, units and time zone
    -----------------------------
    All date and time fields are in KST (UTC+9, Korea does not observe
    daylight saving time). None of the raw columns carry a time zone marker;
    KST is the only zone KFS reports in and is assumed throughout.

    ``발생일시_년`` / ``_월`` / ``_일`` / ``_시간``
        int / int / int / str "HH:MM". The reported fire START time. This is
        a REPORTED time (when the fire was called in or noticed), not
        observed ignition. Every duration computed from it is
        report-to-containment, never ignition-to-containment, and that
        caveat travels with any statistic derived from these columns.
    ``발생일시_요일``
        str, one of 월 화 수 목 금 토 일 (day of week of the start date, Korean
        single character).
    ``진화종료시간_년`` / ``_월`` / ``_일`` / ``_시간``
        int / int / int / str "HH:MM". Reported containment (mop-up
        declared complete) time. Same reporting caveat as the start time:
        this is when containment was DECLARED, not a physically observed
        instant.
        ⚠ Two rows carry impossible end years (2055 and 2223) that cannot be
        the true containment year; treat any duration computed from those two
        rows as invalid, do not clip or reinterpret the year, and exclude
        them explicitly. See ``research/data/checks/check_kfs_fire_stats_csv.py``
        for the current count and which rows.
        ⚠ A further 12 rows (measured, matches the program brief's claim of
        12) have an end timestamp strictly earlier than the start timestamp,
        producing a negative duration. These are administrative recording
        errors (e.g. containment time defaulted to 00:00), not fires that
        were contained before they started. Never silently drop them without
        flagging; a duration-based model must exclude or explicitly impute
        these rows and say so.
    ``발생장소_관서`` / ``_시도`` / ``_시군구`` / ``_읍면`` / ``_동리``
        str. Administrative address hierarchy of the responsible forest fire
        management office and the fire location, coarsest (관서, the
        responsible KFS/local office) to finest (동리, village/neighbourhood).
        No coordinates are present in this file; addresses only.
        ``_시군구`` (13 nulls), ``_읍면`` (307 nulls) and ``_동리`` (1 null) in
        the committed copy are missing for some rows, most often when the
        fire location could not be pinned down to that level; do not treat a
        null here as "not applicable".
    ``발생원인_구분``
        str, single-character cause code (기, 입, 담, 쓰, or null). This is NOT
        the full cause label; it is a code. 294 rows (measured) are null.
        See the code-to-label mapping and its evidence in
        ``scripts/ingest_kfs_statistics.py`` (CAUSE_CODES), which this loader
        does not duplicate or re-derive; read that script rather than
        hand-mapping the codes again.
    ``발생원인_세부원인``
        str, detailed cause label, or the literal placeholder string
        "기타(직접입력)" when no specific label applies. When the placeholder
        appears, the real cause (if known) is usually in 발생원인_기타 instead;
        see scripts/ingest_kfs_statistics.py for the reconciliation logic
        (do not just read 발생원인_세부원인 alone and call ~540 rows
        "specific").
    ``발생원인_기타``
        str, free-text cause detail, populated on all 2,020 rows (454 distinct
        strings in the committed copy). Carries the real cause when
        발생원인_세부원인 is the placeholder, and sometimes carries an
        "unknown" marker (미상 / 조사중 / 불명 / 확인중 / 불상) instead.
    ``피해면적_합계``
        float, hectares (ha). Total damaged/burned area for the record. Range
        observed: 0.01 to 52,707.3 ha (min/max as measured, not assumed); the
        maximum corresponds to the largest event in the file and should be
        checked against the Uiseong 2025 complex-fire caveat recorded for the
        related ``kfs_fire_state_history_csv`` registry entry before being
        used as a single fire's size without adjustment.

    Known defects (see check_kfs_fire_stats_csv.py for a re-run count)
    --------------------------------------------------------------------
    - 12 negative-duration rows (진화종료시간 earlier than 발생일시).
    - 2 impossible end years (2055, 2223).
    - Portal ships CP949/EUC-KR, not UTF-8.
    - 발생일시 is a reported start time, not observed ignition (see above).

    This function does no cleaning, no filtering and no derivation (no
    duration column is added). It only decodes and returns the raw table, so
    that every downstream user makes their own explicit, documented choice
    about the negative durations, the impossible end years and the cause-code
    reconciliation, instead of inheriting a silent default.
    """
    import pandas as pd

    csv_path = Path(path) if path is not None else DEFAULT_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Registry id kfs_fire_stats_csv; see "
            f"research/data/REGISTRY.yaml for the source URL and checksum."
        )
    return pd.read_csv(csv_path, encoding=ENCODING)
