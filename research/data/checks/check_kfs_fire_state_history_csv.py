#!/usr/bin/env python
"""Re-verify the KFS fire state-history CSV (kfs_fire_state_history_csv).

    /home/user/wildfireguardian/.auto/venv/bin/python \
        research/data/checks/check_kfs_fire_state_history_csv.py

Fetched keyless from data.go.kr id 15121205 (원문파일등록 -- the file is
hosted on data.go.kr itself, "파일데이터는 로그인 없이 다운로드를 통해 이용하실
수 있습니다" stated on the portal page, confirmed 2026-09-16). No account, no
terms click, no captcha was presented for this download.

This is the file agent A2 has a transform waiting on: the program brief
claims 41 negative durations (진화완료시간 earlier than 진화시작시간) in this
file. This script computes its own count independently and prints it next to
the brief's number, so agreement or disagreement is visible rather than
assumed.

Also verifies the known per-brief caveat that 일출시간/일몰시간 (sunrise and
sunset) are a single national value per day, not local to the fire's address:
every row for a given calendar date must carry the same 일출시간 and 일몰시간
across all rows on that date, or the "single national value" claim in the
registry's known_issues is wrong and must be corrected, not silently kept.

Exit code is 0 only when the integrity checks (sha256, byte count, encoding)
all pass. The negative-duration count and the sunrise/sunset check are always
printed, never gate the exit code by themselves.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO / "research" / "data" / "raw" / "kfs_fire_state_history_csv" / \
    "산불상태별이력_2025.11.10.csv"

#: Recorded in research/data/REGISTRY.yaml under kfs_fire_state_history_csv.
EXPECTED_SHA256 = "2e94ab963feeb9ad998761537a397e4d5912ac7f90e147487ef43aafc1512c00"
EXPECTED_BYTES = 274_225

ENCODINGS = ("cp949", "euc-kr")

#: The brief's claim, printed for comparison only, never adopted as a result.
BRIEF_NEGATIVE_DURATIONS = 41


def digest(path: Path) -> tuple[str, int]:
    b = path.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def load(path: Path):
    import pandas as pd

    last_exc = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            df.columns = [c.strip() for c in df.columns]
            return df, enc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise SystemExit(f"could not decode with {ENCODINGS}: {last_exc}")


def main() -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"STOP-GATE: {args.csv} is not present on disk.", file=sys.stderr)
        return 2

    sha, nbytes = digest(args.csv)
    df, enc = load(args.csv)

    ok = True

    print(f"file      {args.csv}")
    print(f"sha256    computed={sha}")
    print(f"          expected={EXPECTED_SHA256}")
    if sha != EXPECTED_SHA256:
        print("          MISMATCH")
        ok = False
    print(f"bytes     computed={nbytes:,}  expected={EXPECTED_BYTES:,}"
          f"{'' if nbytes == EXPECTED_BYTES else '  MISMATCH'}")
    if nbytes != EXPECTED_BYTES:
        ok = False

    print(f"encoding  decoded with {enc!r}")

    n_rows = int(len(df))
    print(f"\nrows      {n_rows}")
    print(f"columns   {df.columns.tolist()}")

    report_date = pd.to_datetime(df["산불신고일"], errors="coerce")
    print(f"temporal coverage (산불신고일): {report_date.min().date()} to "
          f"{report_date.max().date()}")

    start = pd.to_datetime(df["진화시작시간"], errors="coerce")
    end = pd.to_datetime(df["진화완료시간"], errors="coerce")
    n_null_start = int(start.isna().sum())
    n_null_end = int(end.isna().sum())
    print(f"\nunparseable 진화시작시간: {n_null_start}")
    print(f"unparseable 진화완료시간: {n_null_end}")

    dur_min = (end - start).dt.total_seconds() / 60.0
    neg = dur_min < 0
    n_negative = int(neg.sum())
    agree = n_negative == BRIEF_NEGATIVE_DURATIONS
    print(f"\nnegative-duration rows (진화완료시간 - 진화시작시간 < 0), "
          f"independent count: {n_negative}")
    print(f"negative-duration rows, brief claims:                    "
          f"{BRIEF_NEGATIVE_DURATIONS}")
    print(f"  {'agrees' if agree else 'DISAGREES -- this is a finding, not rounded away'}")

    # Sunrise/sunset single-national-value check: same calendar date must
    # carry the same 일출시간/일몰시간 across every row, regardless of address.
    by_date = df.groupby(report_date.dt.date)[["일출시간", "일몰시간"]].nunique()
    multi_value_dates = by_date[(by_date["일출시간"] > 1) | (by_date["일몰시간"] > 1)]
    print(f"\nsunrise/sunset single-national-value check: "
          f"{len(multi_value_dates)} date(s) with more than one distinct "
          f"일출시간 or 일몰시간 value")
    if len(multi_value_dates):
        print("  NOTE: this contradicts the 'single national value per day' "
              "known_issue; do not silently keep that wording, report it.")
    else:
        print("  confirms: 일출시간 and 일몰시간 are constant within each "
              "calendar date across all rows, consistent with a single "
              "national value per day, not a per-address local time.")

    print("\nnull cells by column:")
    for col, n in df.isna().sum().items():
        if n:
            print(f"  {col:<16} {n}")

    print(f"\n{'OK' if ok else 'FAILED'} -- integrity checks "
          f"{'passed' if ok else 'did not all pass'}.")
    if not agree:
        print("NOTE: negative-duration count differs from the program brief; "
              "report this, do not silently adopt either number.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
