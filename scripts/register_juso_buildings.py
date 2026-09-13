#!/usr/bin/env python
"""Register the 영덕 도로명주소 건물 layer counts in docs/NUMBERS.json (additive, `jbld_` keys).

Source artifact: data/processed/external/juso_buildings_yeongdeok/manifest.json, written by
scripts/extract_juso_buildings_yeongdeok.py from the zip the author downloaded on 2026-09-13
(NH-005). ADDITIVE: loads the registry, replaces only `jbld_` keys.

    python scripts/register_juso_buildings.py          # upsert
    python scripts/register_juso_buildings.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/external/juso_buildings_yeongdeok/manifest.json"
PREFIX = "jbld_"

BAND = (
    "AN ADMINISTRATIVE BUILDING INVENTORY, NOT A HOUSEHOLD COUNT, AND NOT YET AN INPUT TO ANY "
    "ROUTING RESULT. Four facts travel together or none may be quoted. (1) THE LAYER is the "
    "행정안전부 도로명주소 전자지도 건물 layer for 경상북도, data month 2026-08, cut on SIG_CD 47770 "
    "(영덕군) by scripts/extract_juso_buildings_yeongdeok.py; the committed artifact holds footprint "
    "CENTROIDS and the layer's attributes, the polygons stay in the laptop-only raw bundle. (2) A "
    "BUILDING IS NOT A HOUSEHOLD: the layer says nothing about who lives where; bul_dpn_se separates "
    "주건물 (M) from 부속건물 (S) and a count must say which it took. (3) THE OSM SHARE is 124 OSM "
    "building=* polygons over the 도로명주소 buildings whose centroid lies inside the canonical 영덕 box; "
    "it measures OSM coverage on this box only and transfers to no other region (docs/building_sampling.md "
    "§3 already showed the OSM sample is biased; this is its size). (4) NO COMMITTED ROUTING NUMBER "
    "MOVES: every building-origin result in this repository (bld_*, village-edge, WUI) still stands on "
    "the 124 OSM footprints and is labelled provisional; re-running them on this layer is the next row, "
    "not this one. docs/juso_buildings_yeongdeok.md states the method, the result and what it does NOT show."
)
FORBIDDEN = ["가구 수", "households", "28,361 households", "28361 가구", "coverage is complete", "모든 건물"]

FIGURES = [
    ("province_buildings", "counts.province_47_buildings", "buildings", "buildings in the 경상북도 layer file (every 시군구)"),
    ("county_buildings", "counts.county_47770_buildings", "buildings", "buildings with SIG_CD 47770 (영덕군)"),
    ("inside_box", "counts.inside_canonical_box", "buildings", "영덕군 buildings whose footprint centroid lies inside the canonical 영덕 box (regions.lookup('yeongdeok_2025').bbox_epsg5179)"),
    ("inside_box_main", "counts.inside_canonical_box_main_buildings", "buildings", "of those, 주건물 (bul_dpn_se == 'M')"),
    ("osm_inside_box", "counts.osm_buildings_inside_walk_bbox", "buildings", "the OSM building count the repository has used so far (= bld_yeongdeok_n_mapped, read from data/processed/building_origin_routing.json)"),
    ("osm_share_pct", "counts.osm_share_of_juso_inside_box_pct", "%", "100 × OSM buildings / 도로명주소 buildings inside the box"),
]


def build_entries(man: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in FIGURES:
        cur = man
        for part in path.split("."):
            cur = cur[part]
        out[PREFIX + suffix] = {
            "value": cur, "unit": unit, "source_file": ARTIFACT, "json_path": path,
            "derivation": derivation + ". Regenerate: python scripts/extract_juso_buildings_yeongdeok.py (needs the laptop-only zip)",
            "config_hash": doc_hash, "config_hash_at_production": None, "git_commit": head,
            "sample": "영덕군 · 도로명주소 전자지도 건물 · 2026-08 · SIG_CD 47770",
            "caveat": BAND, "forbidden_phrasings": FORBIDDEN,
            "reproducible": False,
            "reproducibility": {"status": "external",
                                "evidence": "re-run scripts/extract_juso_buildings_yeongdeok.py on the zip (sha256 in the manifest); the artifact is byte-stable",
                                "blocked_by": "data/raw/juso_buildings/ is a laptop-only bundle (portal login + agency approval)"},
            "provenance": "external", "arm": "juso_buildings", "figure_status": "final",
            "agency": man["agency"], "as_of": man["data_month"], "scope": "영덕군 (47770)",
            "source_url": "https://business.juso.go.kr",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": path}}},
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
    stale = [k for k, e in new.items() if k not in cur or cur[k]["value"] != e["value"] or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE juso-buildings registry entries: " + ", ".join(stale)); return 1
        print(f"OK — {len(new)} juso-buildings entries match the manifest"); return 0
    for k, e in new.items():
        if k in cur:
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"upserted {len(new)} juso-buildings entries ({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
