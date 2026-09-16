"""Loader for the KFS landslide occurrence history dataset.

Owned by A1 (data acquisition). Only ``load_landslide_history`` is
implemented, for the registry entry ``kfs_landslide_history``.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO / "research" / "data" / "raw" / "kfs_landslide_history" / \
    "전국 산사태 발생 이력(21년~25년).csv"

#: CP949 / EUC-KR only. The portal does not ship UTF-8 for this file.
ENCODING = "cp949"


def load_landslide_history(path: "Path | None" = None):
    """Load 산림청_최근 5년간 전국 산사태 발생 이력 (KFS landslide history CSV).

    Registry id: ``kfs_landslide_history``. Source:
    https://www.data.go.kr/data/15125006/fileData.do -- fetched keyless
    round 2 (2026-09-16): the portal serves this file directly
    (원문파일등록, "파일데이터는 로그인 없이 다운로드를 통해 이용하실 수
    있습니다"), no account, no terms click, no captcha. Licence: KOGL Type 1
    (공공저작물 : 출처표시), attribution required.

    Parameters
    ----------
    path:
        Optional override. Defaults to the committed copy under
        ``research/data/raw/kfs_landslide_history/``.

    Returns
    -------
    pandas.DataFrame
        One row per recorded landslide event, 5,118 rows as fetched
        2026-09-16 (sha256
        b7413e72b18b84c9c379a97111aef1f5794efb6590974679567e7d0c61c8211f).
        Temporal coverage of 연도 is 2021 to 2025 (measured by
        ``research/data/checks/check_kfs_landslide_history.py``, not
        assumed), a rolling 5-year window per the dataset title; the portal
        states annual update, next registration scheduled 2026-11-27.

    Columns and meaning
    --------------------
    ``연도``
        int, the year of the event (or of the reporting window; the exact
        reporting convention for 재난구분's date range versus this column
        was not independently reconciled this round).
    ``순번``
        int, a sequence number within the file. Not confirmed to be a stable
        identifier across future re-downloads; do not treat it as a durable
        key.
    ``재난구분``
        str, a date range for the triggering disaster event, e.g.
        "2021-07-05~07-08" (a multi-day storm window), not a single date.
    ``시설구분_등급``
        str, facility/land classification and grade, e.g. "산사태_사유림"
        (landslide, privately-owned forest). Values not enumerated this
        round; read distinct values before treating this as a clean
        category.
    ``상세주소_시도`` / ``_시군구`` / ``_읍면도`` / ``_리``
        str, administrative address hierarchy, province to
        village/neighbourhood. ⚠ Address-level only. No coordinate columns
        are present in this file (confirmed 2026-09-16 by column
        inspection); any spatial join needs geocoding via
        ``vworld_geocoder``, and its precision-level caveat travels with the
        result. ``_읍면도`` (4 nulls) and ``_리`` (220 nulls, about 4.3%) are
        missing for some rows in the committed copy; do not treat a null as
        "not applicable" without checking the row.
    ``피해물량(ha)``
        float, damaged area in hectares for the event.

    Known defects (see check_kfs_landslide_history.py for a re-run count)
    --------------------------------------------------------------------------
    - Address-level only; no coordinates. Geocode via vworld_geocoder
      (VWORLD_KEY, blocked on WJ-001) before any spatial join.
    - ``_읍면도`` and ``_리`` carry nulls; do not silently drop or impute.
    - Portal ships CP949/EUC-KR, not UTF-8.
    - This is a rolling 5-year window (title says "최근 5년간"); a future
      re-download will not cover the same years as this committed copy, so
      any longitudinal use must re-verify temporal_coverage rather than
      assume 2021-2025 holds forever.

    This function does no cleaning, no filtering and no geocoding. It only
    decodes and returns the raw table.
    """
    import pandas as pd

    csv_path = Path(path) if path is not None else DEFAULT_CSV
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{csv_path} not found. Registry id kfs_landslide_history; see "
            f"research/data/REGISTRY.yaml for the source URL and checksum."
        )
    return pd.read_csv(csv_path, encoding=ENCODING)
