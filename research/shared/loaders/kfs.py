"""Loaders for Korea Forest Service (KFS) datasets.

Owned by A1 (data acquisition). ``load_fire_stats_csv`` (registry entry
``kfs_fire_stats_csv``) and ``load_fire_state_history`` (registry entry
``kfs_fire_state_history_csv``) are implemented. The Open API loader
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
DEFAULT_STATE_HISTORY_CSV = REPO / "research" / "data" / "raw" / \
    "kfs_fire_state_history_csv" / "산불상태별이력_2025.11.10.csv"

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


def load_fire_state_history(path: "Path | None" = None):
    """Load 산불상태별이력 (KFS fire state-history CSV).

    Registry id: ``kfs_fire_state_history_csv``. Source:
    https://www.data.go.kr/data/15121205/fileData.do -- fetched keyless
    round 2 (2026-09-16): the portal serves this file directly
    (원문파일등록, "파일데이터는 로그인 없이 다운로드를 통해 이용하실 수
    있습니다"), no account, no terms click, no captcha.

    Parameters
    ----------
    path:
        Optional override. Defaults to the committed copy under
        ``research/data/raw/kfs_fire_state_history_csv/``.

    Returns
    -------
    pandas.DataFrame
        One row per fire per the state-history record, 2,030 rows as fetched
        2026-09-16 (sha256
        2e94ab963feeb9ad998761537a397e4d5912ac7f90e147487ef43aafc1512c00).
        Temporal coverage of 산불신고일 is 2022-01-01 to 2025-11-10 (measured
        by ``research/data/checks/check_kfs_fire_state_history_csv.py``, not
        assumed).

    Columns, units and time zone
    -----------------------------
    All date and time fields are KST (UTC+9); none carry an explicit zone
    marker.

    ``산불정보아이디``
        int, KFS internal fire identifier. Not the same numbering as
        ``kfs_fire_stats_csv``; do not join on identifier without first
        checking whether the two datasets share a key at all (not verified in
        this round).
    ``산불신고일``
        str "YYYY-MM-DD". Reported date, same reporting caveat as
        ``kfs_fire_stats_csv``'s 발생일시: this is when the fire was reported,
        not necessarily observed ignition.
    ``산불발생주소``
        str, free-text Korean address, not split into administrative-level
        columns the way ``kfs_fire_stats_csv`` is. Address only, no
        coordinates.
    ``진화시작시간`` / ``진화완료시간``
        str "YYYY-MM-DD HH:MM", suppression-start and containment-declared
        timestamps.
        ⚠ 41 rows (measured 2026-09-16, matches the program brief's claim of
        41 exactly) have 진화완료시간 earlier than 진화시작시간, producing a
        negative duration. Same nature as the 12 negative-duration rows in
        ``kfs_fire_stats_csv``: administrative recording errors, not fires
        contained before suppression started. Never silently drop; flag or
        impute explicitly. See
        ``research/data/checks/check_kfs_fire_state_history_csv.py`` for a
        re-run count.
        ⚠ Uiseong 2025 appears as two same-day records in this file (52,707
        ha and 46,575 ha per the registry's known_issues); apply the
        K-SPREAD complex-fire rule rather than summing or averaging them as
        one event, and check whether that rule applies to any other date
        pair before aggregating by date.
    ``관할기관명``
        str, the KFS/local office responsible for suppression.
    ``문자전송여부``
        str "Y"/"N", whether an emergency text alert was sent. Not a measure
        of fire severity; this is a dispatch/notification flag.
    ``일출시간`` / ``일몰시간``
        str "HH:MM:SS". ⚠ Confirmed 2026-09-16 (see the check script): these
        are a single national value per calendar date, identical across every
        row on that date regardless of the fire's address. Never use them as
        the local sunrise/sunset for a specific fire location; compute local
        solar times from coordinates instead, as the registry's known_issues
        already state.

    Known defects (see check_kfs_fire_state_history_csv.py for a re-run count)
    -----------------------------------------------------------------------------
    - 41 negative-duration rows (진화완료시간 earlier than 진화시작시간).
    - Uiseong 2025 double-counted as two same-day records; apply the
      K-SPREAD complex rule.
    - 일출시간/일몰시간 are a national daily value, not local to the address.
    - Portal ships CP949/EUC-KR, not UTF-8.

    This function does no cleaning, no filtering and no derivation (no
    duration column is added). It only decodes and returns the raw table.
    """
    import pandas as pd

    csv_path = Path(path) if path is not None else DEFAULT_STATE_HISTORY_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Registry id kfs_fire_state_history_csv; "
            f"see research/data/REGISTRY.yaml for the source URL and "
            f"checksum."
        )
    df = pd.read_csv(csv_path, encoding=ENCODING)
    df.columns = [c.strip() for c in df.columns]
    return df
