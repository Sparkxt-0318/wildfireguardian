#!/usr/bin/env python
"""Re-verify the KFS landslide occurrence history CSV (kfs_landslide_history).

    /home/user/wildfireguardian/.auto/venv/bin/python \
        research/data/checks/check_kfs_landslide_history.py

Fetched keyless from data.go.kr id 15125006 (원문파일등록 -- the file is hosted
on data.go.kr itself, "파일데이터는 로그인 없이 다운로드를 통해 이용하실 수
있습니다" stated on the portal page, confirmed 2026-09-16). No account, no
terms click, no captcha was presented for this download.

This script answers, from the file itself, every time it is run:

1. Is the file on disk still the exact file recorded in the registry (sha256,
   byte count)?
2. Does it still decode as CP949 / EUC-KR?
3. What is the row count and the year range of 연도?
4. What is the null fraction per column?

Address-level only (시도/시군구/읍면/리); no coordinates, confirmed on the
portal page and independently confirmed here by column inspection. Any
coordinate-based use of this dataset needs geocoding via vworld_geocoder.

Exit code is 0 only when the integrity checks (sha256, byte count, encoding)
all pass.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO / "research" / "data" / "raw" / "kfs_landslide_history" / \
    "전국 산사태 발생 이력(21년~25년).csv"

#: Recorded in research/data/REGISTRY.yaml under kfs_landslide_history.
EXPECTED_SHA256 = "b7413e72b18b84c9c379a97111aef1f5794efb6590974679567e7d0c61c8211f"
EXPECTED_BYTES = 399_075

ENCODINGS = ("cp949", "euc-kr")


def digest(path: Path) -> tuple[str, int]:
    b = path.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def load(path: Path):
    import pandas as pd

    last_exc = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df, enc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise SystemExit(f"could not decode with {ENCODINGS}: {last_exc}")


def main() -> int:
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

    year_min = int(df["연도"].min())
    year_max = int(df["연도"].max())
    print(f"temporal coverage (연도): {year_min} to {year_max}")

    print("\naddress-level fields only, confirmed no coordinate columns:")
    coord_like = [c for c in df.columns if any(
        tok in c for tok in ("위도", "경도", "lat", "lon", "x좌표", "y좌표", "X", "Y")
    )]
    print(f"  columns matching a coordinate-like name: {coord_like or 'none'}")

    print("\nnull cells and null fraction by column:")
    for col, n in df.isna().sum().items():
        frac = n / n_rows if n_rows else 0.0
        if n:
            print(f"  {col:<16} {n:>5}  ({frac:.4%})")

    print(f"\n{'OK' if ok else 'FAILED'} -- integrity checks "
          f"{'passed' if ok else 'did not all pass'}.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
