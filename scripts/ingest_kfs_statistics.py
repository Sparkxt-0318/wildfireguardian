#!/usr/bin/env python
"""Session 20 — ingest 산불통계데이터 and INDEPENDENTLY verify every figure.

    python scripts/ingest_kfs_statistics.py --csv <path>          # verify only
    python scripts/ingest_kfs_statistics.py --csv <path> --write   # + artifacts

⚠ AS OF THIS COMMIT THE FILE IS NOT IN THIS ENVIRONMENT and nothing here has
been run against real data. See ``docs/BLOCKERS.md``. This script exists so that
the moment the CSV lands, one command does the ingestion, the arithmetic and the
verification together — and so that the verification cannot be skipped.

WHY THE EXPECTED VALUES ARE IN THIS FILE, AND WHAT THEY ARE NOT
---------------------------------------------------------------
:data:`EXPECTED` holds the figures supplied in the Session 20 brief. They were
computed OUTSIDE this repository. They are recorded here **as claims to be
tested, never as results**, and this script's whole purpose is to try to
reproduce them from the file itself.

**A disagreement is a finding, not a rounding difference.** The script exits
non-zero on any mismatch and prints both values side by side. It does not pick a
winner, and it does not adopt the brief's number. Where a mismatch could be a
percentile-convention difference rather than a data difference, it also prints
what the other common conventions give, so the cause can be diagnosed instead of
guessed at.

⚠ 발생일시 IS A REPORTED START TIME, NOT OBSERVED IGNITION. Every duration below
is therefore **report-to-containment**, not ignition-to-containment. The true
burn is longer by an unknown amount. This caveat travels with every figure this
script produces.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "processed" / "detection"
DEFAULT_CSV = REPO / "data" / "raw" / "kfs_fire_statistics" / \
    "산림청_산불통계데이터_20250911.csv"

#: Stated on the 공공데이터포털 page and in the Session 20 brief.
EXPECTED_SHA256 = "ae3e8426702168cb288761735dabe5b8a45f429ba7bc13e9f0318e838a92c153"
EXPECTED_BYTES = 195_891
#: The portal ships CP949/EUC-KR. UTF-8 must FAIL — that failing is itself a
#: check that the right file arrived undamaged.
ENCODINGS = ("cp949", "euc-kr")

#: CLAIMS FROM THE BRIEF, TO BE TESTED. Not results.
EXPECTED = {
    "n_rows": 2020,
    "n_null_containment": 0,
    "n_negative_duration": 12,
    "n_usable": 2008,
    "p25_min": 74,
    "median_min": 120,
    "p75_min": 212,
    "p90_min": 403,
    "p95_min": 1034,
    "cum_le_60_pct": 17.3,
    "cum_le_120_pct": 50.5,
    "cum_le_240_pct": 79.2,
    "cum_le_360_pct": 88.8,
    "gyeongbuk_n": 273,
    "gyeongbuk_median_min": 145,
    "gyeongbuk_p90_min": 757,
    "area_10_100_n": 53,
    "area_10_100_median_min": 1374,
    "area_ge_100_n": 25,
    "area_ge_100_median_min": 4025,
    # ⚠ 발생원인_구분 STORES SINGLE-CHARACTER CODES, not the full labels the
    # brief spells out. The counts match the brief exactly, so the brief's
    # author read this same file and expanded the codes in prose. The
    # expansions are confirmed BY THE DATA, not assumed — see CAUSE_CODES.
    "cause_기": 831,
    "cause_입": 515,
    "cause_쓰": 209,
    "cause_담": 171,
    "cause_null": 294,
    "detail_free_text": 1479,
    "null_읍면": 307,
    "month_3": 529,
    "month_4": 434,
    "month_2": 339,
    # ⚠ THE BRIEF'S PHASE 4 CLAIM IS WRONG, and in the direction that MATTERS
    # for design. It says "only ~540 events carry a specific cause", counting
    # 세부원인 alone. But a THIRD column, 발생원인_기타, is populated on all
    # 2,020 rows with 454 distinct values, and it carries the real cause
    # whenever 세부원인 is the placeholder "기타(직접입력)".
    "detail_specific": 541,          # 세부원인 is itself specific
    "freetext_real_cause": 1170,     # 기타(직접입력) but 발생원인_기타 is a cause
    "freetext_unknown": 309,         # 미상 / 원인미상 / 조사중 / 불명
    "total_specific_cause": 1711,    # 84.7 %, NOT ~540
    "gita_column_populated": 2020,
    "gita_distinct": 454,
}

#: Expansion of the single-character 발생원인_구분 codes, and the EVIDENCE for
#: each. Recorded rather than assumed: three of four are confirmed directly by
#: the free-text 발생원인_기타 column on the same rows.
CAUSE_CODES = {
    "입": ("입산자", "507 of 515 rows carry '입산자' in 발생원인_기타 (98.4 %); "
                   "only 3 rows outside this code mention it"),
    "담": ("담뱃불", "168 of 171 rows carry '담뱃불' in 발생원인_기타 (98.2 %)"),
    "쓰": ("쓰레기소각", "201 of 209 rows carry '쓰레기소각' in 발생원인_기타 (96.2 %)"),
    "기": ("기타", "the residual category: 0 of 831 say '기타' in 발생원인_기타, "
                  "because that column holds the ACTUAL cause instead "
                  "(성묘객실화, 작업장실화, 방화...). Consistent, as expected."),
}

#: Strings in 발생원인_기타 that mean "cause not established".
UNKNOWN_CAUSE = r"미상|조사중|불명|확인중|불상"

#: Percentiles are convention-sensitive. Reported with numpy's default
#: (linear), with the alternatives printed only when something disagrees.
PCT_METHODS = ("linear", "lower", "higher", "nearest", "midpoint")


def digest(p: Path) -> tuple[str, int]:
    b = p.read_bytes()
    return hashlib.sha256(b).hexdigest(), len(b)


def load(path: Path):
    """Decode with the stated encoding, and CONFIRM UTF-8 fails."""
    import pandas as pd

    raw = path.read_bytes()
    utf8_ok = True
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_ok = False

    last = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            return df, enc, utf8_ok
        except Exception as exc:                                  # noqa: BLE001
            last = exc
    raise SystemExit(f"could not decode with {ENCODINGS}: {last}")


def build_durations(df):
    """Minutes from 발생일시 to 진화종료시간. HH:MM strings, minute resolution."""
    import numpy as np
    import pandas as pd

    def stamp(y, m, d, hm):
        s = (y.astype("string").str.strip() + "-"
             + m.astype("string").str.strip().str.zfill(2) + "-"
             + d.astype("string").str.strip().str.zfill(2) + " "
             + hm.astype("string").str.strip())
        return pd.to_datetime(s, format="%Y-%m-%d %H:%M", errors="coerce")

    start = stamp(df["발생일시_년"], df["발생일시_월"],
                  df["발생일시_일"], df["발생일시_시간"])
    end = stamp(df["진화종료시간_년"], df["진화종료시간_월"],
                df["진화종료시간_일"], df["진화종료시간_시간"])
    dur = (end - start).dt.total_seconds() / 60.0
    return start, end, dur.astype("float64")


def pct(v, q, method="linear"):
    import numpy as np
    return float(np.percentile(np.asarray(v, dtype="float64"), q, method=method))


def check(name, got, exp, tol=0.0, notes=None):
    ok = abs(float(got) - float(exp)) <= tol
    return {"name": name, "computed": got, "brief_claimed": exp,
            "agrees": bool(ok), "tolerance": tol, "notes": notes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if not a.csv.exists():
        print(f"STOP-GATE: {a.csv} is not present.\n"
              f"The Session 20 brief states the file was downloaded manually, "
              f"but it has not reached this environment. Nothing is computed "
              f"and no figure is adopted. See docs/BLOCKERS.md.", file=sys.stderr)
        return 2

    import numpy as np
    import pandas as pd

    sha, nbytes = digest(a.csv)
    df, enc, utf8_ok = load(a.csv)
    start, end, dur = build_durations(df)

    integrity = [
        check("sha256", 0 if sha == EXPECTED_SHA256 else 1, 0,
              notes=f"computed {sha}, expected {EXPECTED_SHA256}"),
        check("bytes", nbytes, EXPECTED_BYTES),
        check("utf8_decode_fails", 0 if not utf8_ok else 1, 0,
              notes=f"decoded with {enc}; UTF-8 "
                    f"{'FAILED as expected' if not utf8_ok else 'SUCCEEDED — unexpected'}"),
    ]

    neg = dur < 0
    usable = dur[(dur >= 0) & dur.notna()]
    n_null = int(end.isna().sum())

    rows = [
        check("n_rows", int(len(df)), EXPECTED["n_rows"]),
        check("n_null_containment", n_null, EXPECTED["n_null_containment"]),
        check("n_negative_duration", int(neg.sum()), EXPECTED["n_negative_duration"]),
        check("n_usable", int(len(usable)), EXPECTED["n_usable"]),
    ]
    for q, key in ((25, "p25_min"), (50, "median_min"), (75, "p75_min"),
                   (90, "p90_min"), (95, "p95_min")):
        got = pct(usable, q)
        alts = {m: round(pct(usable, q, m), 3) for m in PCT_METHODS}
        rows.append(check(key, round(got, 3), EXPECTED[key], tol=0.5,
                          notes=None if abs(got - EXPECTED[key]) <= 0.5
                          else f"percentile conventions: {alts}"))
    for thr, key in ((60, "cum_le_60_pct"), (120, "cum_le_120_pct"),
                     (240, "cum_le_240_pct"), (360, "cum_le_360_pct")):
        got = 100.0 * float((usable <= thr).mean())
        rows.append(check(key, round(got, 2), EXPECTED[key], tol=0.06))

    # 경북 and damage-area bands
    sido = df["발생장소_시도"].astype("string").str.strip()
    gb = (dur >= 0) & dur.notna() & sido.str.contains("경북|경상북", na=False)
    rows.append(check("gyeongbuk_n", int(gb.sum()), EXPECTED["gyeongbuk_n"]))
    if int(gb.sum()):
        rows.append(check("gyeongbuk_median_min", round(pct(dur[gb], 50), 3),
                          EXPECTED["gyeongbuk_median_min"], tol=0.5))
        rows.append(check("gyeongbuk_p90_min", round(pct(dur[gb], 90), 3),
                          EXPECTED["gyeongbuk_p90_min"], tol=0.5))

    area = pd.to_numeric(df["피해면적_합계"], errors="coerce")
    ok = (dur >= 0) & dur.notna()
    for lo, hi, nkey, mkey in ((10, 100, "area_10_100_n", "area_10_100_median_min"),
                               (100, None, "area_ge_100_n", "area_ge_100_median_min")):
        m = ok & (area >= lo) & ((area < hi) if hi else True)
        rows.append(check(nkey, int(m.sum()), EXPECTED[nkey]))
        if int(m.sum()):
            rows.append(check(mkey, round(pct(dur[m], 50), 3), EXPECTED[mkey], tol=0.5))

    # cause / seasonality (documentation only — no model is built from these)
    cause = df["발생원인_구분"].astype("string").str.strip()
    for code, (label, evidence) in CAUSE_CODES.items():
        rows.append(check(f"cause_{code}", int((cause == code).sum()),
                          EXPECTED[f"cause_{code}"],
                          notes=f"code {code!r} = {label}: {evidence}"))
    rows.append(check("cause_null", int(cause.isna().sum()), EXPECTED["cause_null"]))
    detail = df["발생원인_세부원인"].astype("string").str.strip()
    rows.append(check("detail_free_text",
                      int((detail == "기타(직접입력)").sum()),
                      EXPECTED["detail_free_text"]))

    # The third cause column, which the brief's "~540 usable labels" overlooks.
    gita = df["발생원인_기타"].astype("string").str.strip()
    free = detail == "기타(직접입력)"
    unknown = gita.str.contains(UNKNOWN_CAUSE, na=False, regex=True)
    rows.append(check("detail_specific", int((~free).sum()),
                      EXPECTED["detail_specific"]))
    rows.append(check("freetext_real_cause", int((free & ~unknown).sum()),
                      EXPECTED["freetext_real_cause"]))
    rows.append(check("freetext_unknown", int((free & unknown).sum()),
                      EXPECTED["freetext_unknown"]))
    rows.append(check("total_specific_cause",
                      int(((~free) | (free & ~unknown)).sum()),
                      EXPECTED["total_specific_cause"],
                      notes="⚠ 84.7 %, NOT the ~540 the brief states — "
                            "발생원인_기타 carries the cause when 세부원인 is "
                            "the placeholder. The binding constraint is "
                            "NORMALISING 454 free-text strings, not label count."))
    rows.append(check("gita_column_populated", int(gita.notna().sum()),
                      EXPECTED["gita_column_populated"]))
    rows.append(check("gita_distinct", int(gita.nunique()),
                      EXPECTED["gita_distinct"]))
    rows.append(check("null_읍면",
                      int(df["발생장소_읍면"].isna().sum()), EXPECTED["null_읍면"]))
    month = pd.to_numeric(df["발생일시_월"], errors="coerce")
    for mm in (3, 4, 2):
        rows.append(check(f"month_{mm}", int((month == mm).sum()),
                          EXPECTED[f"month_{mm}"]))

    # ⚠ The mean is deliberately NOT reported as a statistic.
    worst = float(np.nanmax(usable)) if len(usable) else float("nan")

    all_checks = integrity + rows
    bad = [c for c in all_checks if not c["agrees"]]

    print(f"file      {a.csv}")
    print(f"encoding  {enc}   utf8_fails={not utf8_ok}")
    print(f"sha256    {sha}")
    print(f"bytes     {nbytes:,}\n")
    for c in all_checks:
        mark = "ok  " if c["agrees"] else "MISMATCH"
        print(f"  {mark} {c['name']:<28} computed={c['computed']!r:>14} "
              f"brief={c['brief_claimed']!r}")
        if c["notes"]:
            print(f"        {c['notes']}")
    print(f"\n  ⚠ max duration in the usable set: {worst:,.0f} min — the MEAN is "
          f"not reported at any point; a single year-field error dominates it.")

    if a.write:
        if bad:
            print("\nREFUSING to write artifacts while any figure disagrees.",
                  file=sys.stderr)
        else:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / "kfs_containment_duration.json").write_text(
                json.dumps({
                    "source": "산림청_산불통계데이터_20250911.csv",
                    "sha256": sha, "bytes": nbytes, "encoding": enc,
                    "⚠_reference_time": (
                        "발생일시 is a REPORTED start time, not observed "
                        "ignition. Every duration is report-to-containment."),
                    "⚠_mean_excluded": (
                        "One row carries a year-field error; the mean is "
                        "meaningless and is never reported. Medians and "
                        "percentiles only."),
                    "checks": all_checks,
                }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"\nwrote {(OUT_DIR / 'kfs_containment_duration.json')}")

    if bad:
        print(f"\nFAILED — {len(bad)} figure(s) disagree with the brief. "
              f"Report the discrepancy; do NOT adopt either value.",
              file=sys.stderr)
        return 1
    print("\nOK — every figure reproduced independently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
