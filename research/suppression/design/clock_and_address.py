#!/usr/bin/env python
"""Outcome-free design measurements for the suppression direction (A5).

    /home/user/wildfireguardian/.auto/venv/bin/python \
        research/suppression/design/clock_and_address.py

Writes research/suppression/design/design_numbers.json.

WHAT THIS MEASURES, AND WHY IT IS NOT A RESULT
-----------------------------------------------
`research/eval/SIGNOFF.md` section 0 permits, on an unsigned direction,
"looking at covariate distributions listed in the pre-registration". Every
quantity below is a property of a covariate column or of the record's
address and clock structure. None of them touches 피해면적_합계, which is
this direction's outcome, and none of them touches any duration derived
from 발생일시 and 진화종료시간, which is the containment model's outcome.

WHAT THIS DELIBERATELY DOES NOT MEASURE
----------------------------------------
1. The burned-area distribution, at any threshold.
2. The report-to-containment duration, its mean, its distribution, or its
   relationship to anything.
3. Any cross-tabulation of a covariate against either of those.

(1) and (2) are the two outcome variables of this direction. Section 4 of
`research/eval/SIGNOFF.md` makes any look at them an amendment event, and
the pre-registration's "what has been seen" section would then have to
carry them. The exceedance counts this direction has ALREADY been told
(26 / 32 / 1 / 19 at the 10 ha floor and so on, computed by A4 for the
landslides cohort geometry) are declared in that section rather than
recomputed here, because recomputing them would add nothing and would make
this script a thing that touches the outcome.

THE FOUR MEASUREMENTS
---------------------
M-C1  Report-clock granularity. Is 발생일시_시간 minute-resolved or rounded?
      A clock rounded to the hour cannot carry an hourly discrete-time
      hazard, and a pile-up on :00 would say so.

M-C2  Report-hour exposure. The hour-of-day histogram of report times. This
      bounds the night arm's exposure from above at the fire level. It is
      NOT the night arm's exposure in the hazard model, which is counted in
      fire-hours and therefore depends on durations, which are the outcome.
      That distinction is the point of the measurement.

M-A1  Address completeness and the finest reachable geocoding rung. The
      access-distance covariate, every terrain covariate, the nearest-station
      weather match and the local solar phase all need coordinates, and the
      record carries none. This measures how precisely an address can be
      resolved at best.

M-A2  Cause-field informativeness and its investigation status. The brief
      names cause as a first-hours covariate. This measures whether the
      record's own cause field is a dispatch-time observation.

Provenance: dataset id `kfs_fire_stats_csv`, status `verified` in
`research/data/REGISTRY.yaml`, CP949, 2,020 rows, report years 2022 to 2025.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CSV = REPO / "data/raw/kfs_fire_statistics/산림청_산불통계데이터_20250911.csv"
OUT = Path(__file__).resolve().parent / "design_numbers.json"

ADDRESS_COLS = ("발생장소_시도", "발생장소_시군구", "발생장소_읍면", "발생장소_동리")

#: A 지번 (lot number) in the finest address field. Korean lot numbers appear
#: as "123-4", "123번지" or "산 12". If none of these ever appears, the
#: PARCEL rung of research/shared/geo/geocode.py is unreachable for the whole
#: file, exactly as A4 measured for the landslide occurrence record.
LOT_PATTERN = r"\d+\s*-\s*\d+|\d+번지|산\s*\d+"

#: Words that mark a cause as not yet established. 조사중 = under
#: investigation, 추정 = presumed, 미상 = unknown.
INVESTIGATION_PATTERN = "조사중|추정|미상"


def _stripped(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].astype("string").str.strip().replace({"": pd.NA})


def measure(df: pd.DataFrame) -> dict:
    n = len(df)
    out: dict = {"rows": int(n), "source": {
        "dataset_id": "kfs_fire_stats_csv",
        "path": "data/raw/kfs_fire_statistics/산림청_산불통계데이터_20250911.csv",
        "encoding": "cp949",
        "outcome_columns_not_touched": ["피해면적_합계",
                                        "any duration from 발생일시 and 진화종료시간"],
    }}

    # ---- M-C1 and M-C2, the report clock ----------------------------------
    t = df["발생일시_시간"].astype("string").str.strip()
    minute = t.str.split(":").str[1]
    hour = pd.to_numeric(t.str.split(":").str[0], errors="coerce")
    hist = {str(h): int((hour == h).sum()) for h in range(24)}
    out["report_clock"] = {
        "non_null": int(t.notna().sum()),
        "minute_resolved": {
            "share_on_the_hour_pct": round(100.0 * float((minute == "00").mean()), 2),
            "share_on_hour_or_half_pct": round(
                100.0 * float(minute.isin(["00", "30"]).mean()), 2),
            "reading": ("minute-resolved; there is no hour-rounding artefact, "
                        "so an hourly discrete-time hazard has a clock that "
                        "can carry it"),
        },
        "hour_histogram_kst": hist,
        "counts": {
            "h00_to_h05": int(hour.between(0, 5).sum()),
            "h20_to_h23": int(hour.between(20, 23).sum()),
            "h10_to_h17": int(hour.between(10, 17).sum()),
        },
        "night_by_clock_hour": {
            "definition": "report hour in 20:00-05:59 KST, a clock-hour proxy only",
            "count": int(hour.between(0, 5).sum() + hour.between(20, 23).sum()),
            "share_pct": round(100.0 * float(
                (hour.between(0, 5) | hour.between(20, 23)).mean()), 2),
            "what_this_is_not": ("the night arm's exposure in the containment "
                                 "hazard, which is counted in fire-hours and "
                                 "therefore depends on durations, which are the "
                                 "outcome and are not measured here"),
        },
    }

    # ---- M-A1, the address ceiling ----------------------------------------
    s = {c: _stripped(df, c) for c in ADDRESS_COLS}
    pattern = pd.Series(
        ["".join("1" if pd.notna(s[c].iloc[i]) else "0" for c in ADDRESS_COLS)
         for i in range(n)], index=df.index)
    finest = s["발생장소_동리"]
    full = pattern == "1111"
    parents = pd.DataFrame({c: s[c] for c in ADDRESS_COLS[:3]})[full.values]
    parents["ri"] = finest[full.values]
    per_name = parents.groupby("ri").apply(
        lambda g: g[list(ADDRESS_COLS[:3])].drop_duplicates().shape[0],
        include_groups=False)
    province_raw = df["발생장소_시도"].astype("string")
    out["address"] = {
        "presence_pattern_시도_시군구_읍면_동리": {
            k: {"rows": int(v), "share_pct": round(100.0 * v / n, 2)}
            for k, v in pattern.value_counts().items()},
        "rows_with_a_lot_number_in_the_finest_field": int(
            finest.str.contains(LOT_PATTERN, na=False, regex=True).sum()),
        "finest_reachable_rung": "RI_CENTROID (the 리 or 동 polygon)",
        "parcel_rung_reachable": False,
        "distinct_full_four_tuples": int(
            parents[list(ADDRESS_COLS[:3]) + ["ri"]].drop_duplicates().shape[0]),
        "distinct_finest_names": int(per_name.shape[0]),
        "finest_names_under_more_than_one_parent_path": int((per_name > 1).sum()),
        "rows_with_finest_but_no_읍면": int(
            (s["발생장소_동리"].notna() & s["발생장소_읍면"].isna()).sum()),
        "rows_with_no_시군구": int(s["발생장소_시군구"].isna().sum()),
        "province_values_raw": int(province_raw.nunique()),
        "province_values_after_strip": int(s["발생장소_시도"].nunique()),
        "rows_carrying_a_whitespace_variant_province": int(
            (province_raw != province_raw.str.strip()).sum()),
    }

    # ---- M-A2, the cause field --------------------------------------------
    detail = _stripped(df, "발생원인_세부원인")
    free = _stripped(df, "발생원인_기타")
    other = detail == "기타(직접입력)"
    flagged = free.str.contains(INVESTIGATION_PATTERN, na=False, regex=True)
    out["cause"] = {
        "coarse_column_distinct_values": sorted(
            _stripped(df, "발생원인_구분").dropna().unique().tolist()),
        "coarse_column_nulls": int(_stripped(df, "발생원인_구분").isna().sum()),
        "detail_column_nulls": int(detail.isna().sum()),
        "detail_value_counts": {str(k): int(v)
                                for k, v in detail.value_counts().items()},
        "rows_whose_detail_is_free_text_other": int(other.sum()),
        "rows_whose_detail_is_free_text_other_pct": round(
            100.0 * float(other.mean()), 2),
        "distinct_free_text_values": int(free.nunique()),
        "rows_marked_under_investigation_presumed_or_unknown": int(flagged.sum()),
        "rows_marked_under_investigation_presumed_or_unknown_pct": round(
            100.0 * float(flagged.mean()), 2),
        "by_marker": {p: int(free.str.contains(p, na=False).sum())
                      for p in ("조사중", "추정", "미상")},
        "reading": ("the cause field carries its own investigation status, so "
                    "it is an outcome of an enquiry and not an observation "
                    "available at the prediction horizon"),
    }
    return out


def main() -> int:
    if not CSV.exists():
        print("STOP: %s is not on disk" % CSV)
        return 2
    df = pd.read_csv(CSV, encoding="cp949")
    payload = {
        "schema_version": 1,
        "owner": "A5",
        "direction": "suppression",
        "produced": "2026-09-16",
        "script": "research/suppression/design/clock_and_address.py",
        "outcome_free": True,
        "note": ("Design-side measurements only. No burned area and no "
                 "duration is read. See the module docstring for what is "
                 "deliberately not measured and why."),
        "measurements": measure(df),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("wrote %s" % OUT)
    print(json.dumps(payload["measurements"]["report_clock"]["counts"],
                     ensure_ascii=False))
    print(json.dumps({k: v for k, v in payload["measurements"]["address"].items()
                      if k != "presence_pattern_시도_시군구_읍면_동리"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
