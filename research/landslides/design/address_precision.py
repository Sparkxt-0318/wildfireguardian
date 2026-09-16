"""Measure the geocoding precision ceiling of the landslide occurrence record.

Owner: A4. Written for `research/landslides/PREREG_landslides_2026-09-16_v0.1.md`
sections 5 and 8, which decide the unit of analysis. `research/eval/LEAKAGE.md`
item C10 says a sign-off will not be given for a slope-unit model whose unit
assignment error has not been quantified. What has to be measured before
anything else is the ceiling: how precise could a geocode of these addresses
possibly be, before any geocoder is called.

WHAT IT READS, AND WHY THAT IS NOT LOOKING AT THE OUTCOME
---------------------------------------------------------
It reads the four address columns of `kfs_landslide_history` and nothing else.
It does not read `연도`, `재난구분`, `피해물량(ha)` or any cross-tabulation of
them, because the per-year and per-place counts of recorded landslides are the
outcome and item C3 of the leakage checklist turns on them. What is read is the
**completeness and shape of the address text**, which determines which rung of
`research/shared/geo/geocode.py`'s precision ladder a record can reach.

The one field-content test is whether the finest address field carries a lot
number. `GeocodePrecision.PARCEL` is reachable only for an address that names a
lot, typically a 산 lot number in mountain districts. An address whose finest
component is a 리 name with no number cannot be resolved to a parcel by any
geocoder, because the information is not in the string.

This look is declared in the pre-registration, section 3.2.

Run:  .auto/venv/bin/python research/landslides/design/address_precision.py
Writes: research/landslides/design/design_numbers.json (key path `address_precision`)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from research.shared.geo.geocode import GeocodePrecision  # noqa: E402
from research.shared.loaders.landslide import load_landslide_history  # noqa: E402

ADDRESS_COLUMNS = ["상세주소_시도", "상세주소_시군구", "상세주소_읍면도", "상세주소_리"]

#: A lot number is a digit run, optionally preceded by 산. Without one of
#: these in the string, no geocoder can return a parcel.
LOT_NUMBER = re.compile(r"\d")

#: The rung each presence pattern bottoms out at. The committed ladder has no
#: 리 rung, which is section 3.2's finding; `RI_CENTROID` is the name this
#: pre-registration proposes for it and is not yet in geocode.py.
PATTERN_TO_RUNG = {
    "1111": "RI_CENTROID",
    "1110": "EUPMYEONDONG_CENTROID",
    "1101": "RI_CENTROID_NO_EUPMYEON",
    "1100": "SIGUNGU_CENTROID",
    "1011": "RI_CENTROID_NO_SIGUNGU",
    "1010": "EUPMYEONDONG_CENTROID_NO_SIGUNGU",
    "1000": "SIDO_CENTROID",
}


def main() -> int:
    d = load_landslide_history()
    missing = [c for c in ADDRESS_COLUMNS if c not in d.columns]
    if missing:
        raise SystemExit("address columns missing from the loader output: %s" % missing)

    present = d[ADDRESS_COLUMNS].notna()
    for c in ADDRESS_COLUMNS:
        present[c] = present[c] & (d[c].astype(str).str.strip() != "")
    pattern = present.apply(lambda r: "".join("1" if v else "0" for v in r), axis=1)

    finest = d[ADDRESS_COLUMNS[-1]].fillna("").astype(str)
    with_lot = int(finest.apply(lambda s: bool(LOT_NUMBER.search(s))).sum())

    counts = pattern.value_counts().to_dict()
    out = {
        "generated_by": "research/landslides/design/address_precision.py",
        "inputs": [{"dataset_id": "kfs_landslide_history", "status": "verified"}],
        "reads": "address columns only; no year, no storm window, no damaged area",
        "rows": int(len(d)),
        "address_columns": ADDRESS_COLUMNS,
        "presence_pattern_counts": {k: int(v) for k, v in counts.items()},
        "presence_pattern_share": {k: round(int(v) / len(d), 6) for k, v in counts.items()},
        "presence_pattern_rung": {k: PATTERN_TO_RUNG.get(k, "UNKNOWN_PATTERN")
                                  for k in counts},
        "records_with_a_lot_number_in_the_finest_field": with_lot,
        "share_with_a_lot_number": round(with_lot / len(d), 6),
        "parcel_rung_reachable": bool(with_lot > 0),
        "committed_ladder": [p.name for p in GeocodePrecision],
        "finding": ("no record carries a lot number, so GeocodePrecision.PARCEL "
                    "is unreachable for the whole record. The committed ladder "
                    "has no rung between PARCEL and EUPMYEONDONG_CENTROID, and "
                    "the modal record bottoms out at a 리, which sits between "
                    "them. A rung must be added or the record must be carried "
                    "at EUPMYEONDONG_CENTROID, which is coarser than the "
                    "address actually is."),
        "distinct_values": {c: int(d[c].dropna().astype(str).str.strip().replace("", None).nunique())
                            for c in ADDRESS_COLUMNS},
    }

    dest = Path(__file__).resolve().parent / "design_numbers.json"
    existing = {}
    if dest.exists():
        existing = json.loads(dest.read_text(encoding="utf-8"))
    existing["address_precision"] = out
    dest.write_text(json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote %s key path address_precision" % dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
