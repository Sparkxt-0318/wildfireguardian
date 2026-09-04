#!/usr/bin/env python
"""Register the 영덕 주소정보누리집 layer counts in docs/NUMBERS.json (additive).

Source artifact: ``data/processed/external/juso_yeongdeok/manifest.json`` written by
``scripts/extract_juso_yeongdeok.py`` from the two zips the author downloaded on 2026-09-04.
One key per layer, ``juso_yeongdeok_<layer>_count``, arm ``external``, so prose can cite a
count and ``scripts/verify_numbers.py`` re-derives it from the manifest.

ADDITIVE: loads the registry, replaces only ``juso_yeongdeok_`` keys, writes it back.

    python scripts/register_juso_yeongdeok.py          # upsert
    python scripts/register_juso_yeongdeok.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/external/juso_yeongdeok/manifest.json"
PREFIX = "juso_yeongdeok_"


# WFG-075 (2026-09-04). The subset was cut on 시군구 code 47920, labelled 영덕군, and the
# geometry says otherwise: all 239 committed points sit at 128.65-129.15 E / 36.78-37.06 N and
# `regions.lookup('yeongdeok_2025').bbox_wgs84` is (129.25, 36.30, 129.55, 36.60) -- the two do
# not overlap on either axis. NO DISTANCE IN KILOMETRES IS WRITTEN HERE: the containment claim
# does not need one, and the figure in circulation ("about 45 km", critic #11) reproduces from
# no construction over these files -- measured, the nearest point is 30.5 km from the box, the
# farthest 65.6 km. An unregistered number is not written down (CHARTER 3.3).
# The COUNTS are what they say they are (the filter really
# selected that many rows); the COUNTY LABEL on them is not established. The wrong label is
# deliberately left in `scope`, `sample` and `derivation` as the record of what was claimed --
# CHARTER 3.2/3.3 annotate, never edit -- and every entry now carries the correction below.
# The correct code must be read off 행정표준코드 by whoever re-cuts (NH-022, WFG-066); this
# script does not guess it.
SCOPE_CORRECTION = (
    "SCOPE WRONG, DO NOT USE AS 영덕 DATA (2026-09-04, WFG-075 / NH-022). The 시군구 filter "
    "47920 is labelled 영덕군 and the extracted geometry lies wholly outside this repository's "
    "영덕 box (129.25-129.55 E / 36.30-36.60): all 239 points are at 128.65-129.15 E / "
    "36.78-37.06 N, overlapping it on neither axis, and the 지진해일긴급대피장소 layer came back "
    "empty, which a coastal county's would not. The count itself is the number of rows the "
    "filter matched; "
    "which county those rows belong to is UNVERIFIED and is not guessed here. Re-cut is "
    "laptop-only (NH-022)."
)
SCOPE_FORBIDDEN = [
    "영덕의 지정 대피장소", "영덕군 무더위쉼터", "영덕의 119안전센터",
    "designated evacuation sites in Yeongdeok", "Yeongdeok cooling centres",
    "영덕 대피장소 27곳", "영덕 무더위쉼터 99곳",
]


def build_entries(man: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for layer, info in man["layers"].items():
        name = info.get("name_ko", "민원행정기관") if layer != "minwon_agencies" else "민원행정기관"
        out[f"{PREFIX}{layer}_count"] = {
            "value": info["count"], "unit": "features", "source_file": ARTIFACT,
            "json_path": f"layers.{layer}.count",
            "derivation": (f"count of {name} features with sigungu code {man['sigungu_cd']} (영덕군) in the "
                           f"{man['agency']} dataset dated {info['data_date']}; filter: "
                           + (man["samul_filter"] if layer.startswith("samul_") else "시군구코드 == 47920")),
            "config_hash": doc_hash, "config_hash_at_production": None, "git_commit": head,
            "sample": "영덕군", 
            "caveat": (SCOPE_CORRECTION + " -- Administrative inventory as published; not a survey of what "
                       "stands today. The 사물주소 shapefiles carry no .prj and were assigned EPSG:5179 (see "
                       "manifest crs_note). This is NOT the 도로명주소 건물 layer (NH-005 stays open)."),
            "scope_status": "wrong (WFG-075, 2026-09-04; county identity unverified, NH-022)",
            "forbidden_phrasings": list(SCOPE_FORBIDDEN),
            "reproducible": False,
            "reproducibility": {"status": "external",
                                "evidence": "re-run scripts/extract_juso_yeongdeok.py on the two zips (sha256 in the manifest)",
                                "blocked_by": "data/raw/juso/ is a laptop-only bundle"},
            "provenance": "external", "arm": "external", "figure_status": "final",
            "agency": man["agency"], "as_of": info["data_date"], "scope": f"영덕군 · {name}",
            "source_url": "https://business.juso.go.kr",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": f"layers.{layer}.count"}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    man = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    new = build_entries(man, head, doc["config_hash"])
    cur = doc["numbers"]
    # `git_commit` records the commit the artifact was produced at, not the commit that
    # last re-ran this script. Re-stamping it while the value is unchanged would assert a
    # production commit at which these GeoJSONs did not exist, so carry the old one
    # forward (independent review, 2026-09-04, WFG-075).
    for k, e in new.items():
        if k in cur and cur[k]["value"] == e["value"] and cur[k].get("git_commit"):
            e["git_commit"] = cur[k]["git_commit"]
    stale = [k for k, e in new.items() if k not in cur or cur[k]["value"] != e["value"]]
    if args.check:
        print(f"[juso] {len(new)} keys, {len(stale)} stale")
        return 1 if stale else 0
    for k in [k for k in cur if k.startswith(PREFIX)]:
        del cur[k]
    cur.update(new)
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[juso] upserted {len(new)} keys; stale before: {len(stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
