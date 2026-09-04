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
            "caveat": ("Administrative inventory as published; not a survey of what stands today. The 사물주소 "
                       "shapefiles carry no .prj and were assigned EPSG:5179 (see manifest crs_note). This is NOT "
                       "the 도로명주소 건물 layer (NH-005 stays open)."),
            "forbidden_phrasings": [],
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
