#!/usr/bin/env python
"""Re-verify the KFS wildfire statistics CSV (kfs_fire_stats_csv, registry id).

    /home/user/wildfireguardian/.auto/venv/bin/python \
        research/data/checks/check_kfs_fire_stats_csv.py

This is an A1 (data acquisition) check, independent of
scripts/ingest_kfs_statistics.py at the repository root, which this script
does not edit and does not import. It exists to answer four questions from the
file itself, every time it is run:

1. Is the file on disk still the exact file recorded in the registry (sha256,
   byte count)?
2. Does it still decode as CP949 / EUC-KR, and still fail UTF-8 as expected?
3. What is the actual row count and temporal coverage (min and max year of
   발생일시, the reported start time)?
4. How many negative-duration rows and impossible-end-year rows does an
   independent computation find?

The program brief states 12 negative-duration rows. This script does not
adopt that number. It computes its own count and prints both, side by side,
so a disagreement is visible as a finding rather than rounded away.

Exit code is 0 only when the integrity checks (sha256, byte count, encoding)
all pass. The defect counts (negative durations, impossible end years) are
always printed, never gate the exit code by themselves, because finding a
different number from the brief is the point of the script, not a failure of
it.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO / "data" / "raw" / "kfs_fire_statistics" / \
    "산림청_산불통계데이터_20250911.csv"

#: Recorded in research/data/REGISTRY.yaml under kfs_fire_stats_csv. This is
#: what was measured off the file already on disk before this program started,
#: not a value taken from the portal blurb.
EXPECTED_SHA256 = "ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153"
EXPECTED_BYTES = 195_891

#: Portal ships CP949/EUC-KR. UTF-8 must fail; that failure is itself part of
#: the check that the right, undamaged file arrived.
ENCODINGS = ("cp949", "euc-kr")

#: The brief's claim, printed for comparison only, never adopted as a result.
BRIEF_NEGATIVE_DURATIONS = 12


def digest(path: Path) -> tuple[str, int]:
    b = path.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def load(path: Path):
    import pandas as pd

    raw = path.read_bytes()
    utf8_ok = True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_ok = False

    last_exc = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df, enc, utf8_ok
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise SystemExit(f"could not decode with {ENCODINGS}: {last_exc}")


def build_timestamps(df):
    """발생일시 (report time, not observed ignition) and 진화종료시간 (containment)."""
    import pandas as pd

    def stamp(y, m, d, hm):
        s = (
            y.astype("string").str.strip()
            + "-" + m.astype("string").str.strip().str.zfill(2)
            + "-" + d.astype("string").str.strip().str.zfill(2)
            + " " + hm.astype("string").str.strip()
        )
        return pd.to_datetime(s, format="%Y-%m-%d %H:%M", errors="coerce")

    start = stamp(df["발생일시_년"], df["발생일시_월"], df["발생일시_일"], df["발생일시_시간"])
    end = stamp(df["진화종료시간_년"], df["진화종료시간_월"], df["진화종료시간_일"], df["진화종료시간_시간"])
    return start, end


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"STOP-GATE: {args.csv} is not present on disk.", file=sys.stderr)
        return 2

    sha, nbytes = digest(args.csv)
    df, enc, utf8_ok = load(args.csv)
    start, end = build_timestamps(df)
    duration_min = (end - start).dt.total_seconds() / 60.0

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

    print(f"encoding  decoded with {enc!r}; utf-8 "
          f"{'failed as expected' if not utf8_ok else 'SUCCEEDED (unexpected, check the file)'}")
    if utf8_ok:
        ok = False

    n_rows = int(len(df))
    print(f"\nrows      {n_rows}")

    year_min = int(df["발생일시_년"].min())
    year_max = int(df["발생일시_년"].max())
    print(f"temporal coverage (발생일시, report time, KST): {year_min} to {year_max}")
    print("  ⚠ 발생일시 is a reported start time, not observed ignition; every "
          "duration derived from it is report-to-containment, not "
          "ignition-to-containment.")

    n_null_start = int(start.isna().sum())
    n_null_end = int(end.isna().sum())
    print(f"\nunparseable start timestamps: {n_null_start}")
    print(f"unparseable end timestamps:   {n_null_end}")

    neg = duration_min < 0
    n_negative = int(neg.sum())
    agree = n_negative == BRIEF_NEGATIVE_DURATIONS
    print(f"\nnegative-duration rows (독립 계산 / independent count): {n_negative}")
    print(f"negative-duration rows (brief claims):                  {BRIEF_NEGATIVE_DURATIONS}")
    print(f"  {'agrees' if agree else 'DISAGREES -- this is a finding, not rounded away'}")

    start_years = set(df["발생일시_년"].unique().tolist())
    end_years_present = df["진화종료시간_년"]
    impossible_mask = ~end_years_present.isin(start_years)
    n_impossible = int(impossible_mask.sum())
    impossible_years = sorted(set(end_years_present[impossible_mask].unique().tolist()))
    print(f"\nimpossible end-year rows (진화종료시간_년 outside the set of years "
          f"발생일시_년 ever takes, {sorted(start_years)}): {n_impossible}")
    print(f"  offending years: {impossible_years}")

    print(f"\nnull cells by column:")
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
