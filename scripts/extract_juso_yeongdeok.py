#!/usr/bin/env python
"""Extract the 영덕군 subset of two 주소정보누리집 (행정안전부) datasets the author downloaded on
2026-09-04 and placed under the git-ignored ``data/raw/juso/``:

* ``사물주소도형_전체분_경상북도.zip`` (data date 2025-03-01) — 사물주소 point layers for the whole of
  경상북도: bus stops, fire hydrants, emergency water, earthquake outdoor evacuation sites,
  tsunami evacuation sites, cooling centres, life-saving equipment boxes, ...
* ``민원행정기관전자지도_240124.zip`` (data date 2024-01-24) — nationwide points of public
  service institutions (schools, 읍면동 offices, 보건소, police, fire, post).

Neither is the 도로명주소 건물 (building footprint) layer NH-005 asks for; that stays open.

Output (committed, small, EPSG:4326 GeoJSON): ``data/processed/external/juso_yeongdeok/``
with one file per layer and a ``manifest.json`` carrying the zip digests, dates, agency,
CRS decision and per-layer counts. Deterministic; re-run to regenerate.

    python scripts/extract_juso_yeongdeok.py
"""
from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

import geopandas as gpd

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "juso"
OUT = REPO / "data" / "processed" / "external" / "juso_yeongdeok"
SIGUNGU = "47770"  # 경상북도 영덕군 (47920 is 봉화군: the first cut used it by mistake, NH-022)
SAMUL_BASE = RAW / "samul_gyeongbuk_20250301" / "Total.JUSUAI.20250301.TI_SPOT_"
# layer file stem -> (Korean name, English name)
SAMUL_LAYERS = {
    "EQOUT_POINT": ("지진옥외대피장소", "earthquake outdoor evacuation site"),
    "EQWAV_POINT": ("지진해일긴급대피장소", "tsunami emergency evacuation site"),
    "CoolingCen_POINT": ("무더위쉼터", "cooling centre"),
    "LIFESAV_POINT": ("인명구조함", "life-saving equipment box"),
    "FireHydr_POINT": ("소화전", "fire hydrant"),
    "EMERWAT_POINT": ("비상급수시설", "emergency water supply"),
    "BUSST_POINT": ("버스정류장", "bus stop"),
}
ZIPS = {
    "samul": RAW / "사물주소도형_전체분_경상북도.zip",
    "minwon": RAW / "민원행정기관전자지도_240124.zip",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _inside_share(path: Path, box):
    gj = json.loads(path.read_text(encoding="utf-8"))
    pts = [f["geometry"]["coordinates"][:2] for f in gj["features"]]
    inside = sum(box[0] <= x <= box[2] and box[1] <= y <= box[3] for x, y in pts)
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return inside / len(pts), cx, cy


def main() -> int:
    if not RAW.exists():
        print(f"[juso] raw bundle absent at {RAW}; nothing to do (laptop-only input)")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {}
    minwon = gpd.read_file(RAW / "minwon_agencies_20240124" / "minwon_agencies_202401.shp", encoding="cp949")
    my = minwon[minwon["시군구코드"].astype(str) == SIGUNGU].copy()
    my = my.rename(columns={"유형": "type", "상세분류": "subtype", "시군구코드": "sigungu_cd", "도로명코드": "road_cd",
                            "도로명주소": "road_address", "기관명": "name", "전화번호": "phone"})
    my = my.drop(columns=[c for c in ("위치X", "위치Y") if c in my.columns])
    assert my.crs is not None and my.crs.to_epsg() == 5179, my.crs
    my4326 = my.to_crs(4326)
    my4326.to_file(OUT / "minwon_agencies.geojson", driver="GeoJSON")
    layers["minwon_agencies"] = {"count": int(len(my)), "by_type": {k: int(v) for k, v in my["type"].value_counts().items()},
                                 "source_zip": "minwon", "data_date": "2024-01-24"}
    ref_bounds = [float(v) for v in my.total_bounds]
    for stem, (ko, en) in SAMUL_LAYERS.items():
        g = gpd.read_file(f"{SAMUL_BASE}{stem}.47000.shp", encoding="cp949")
        sel = g[g["OBJ_MNG_NO"].astype(str).str[5:10] == SIGUNGU].copy()
        # the shapefiles carry no .prj; the coordinates match the EPSG:5179 agency points for 영덕
        sel = sel.set_crs(5179, allow_override=True)
        inside = sel.cx[ref_bounds[0] - 20000:ref_bounds[2] + 20000, ref_bounds[1] - 20000:ref_bounds[3] + 20000]
        sel["layer_ko"], sel["layer_en"] = ko, en
        sel.to_crs(4326).to_file(OUT / f"samul_{stem.lower()}.geojson", driver="GeoJSON")
        layers[f"samul_{stem.lower()}"] = {"count": int(len(sel)), "within_20km_of_agency_bbox": int(len(inside)),
                                            "name_ko": ko, "name_en": en, "source_zip": "samul", "data_date": "2025-03-01"}
    manifest = {
        "what": "영덕군 subset of two 행정안전부 주소정보누리집 datasets; NOT the 도로명주소 건물 layer",
        "correction": "first cut (2026-09-04, commit 3fdb888) used 47920, which is 봉화군; re-cut the same day with 47770 after critic #11 (NH-022). Verified: every agency road address contains 영덕군 and every point lies inside the canonical 영덕 box 129.25-129.55 E / 36.30-36.60 N",
        "agency": "행정안전부 주소정보누리집 (business.juso.go.kr)",
        "retrieved_by": "the author, 2026-09-04 (downloaded from business.juso.go.kr; the loop cannot log in)",
        "sigungu_cd": SIGUNGU,
        "crs_note": "민원행정기관 carries EPSG:5179 in its .prj; the 사물주소 shapefiles carry none and were assigned "
                    "EPSG:5179 because their coordinates fall on the same grid as the agency points for 영덕",
        "samul_filter": f"OBJ_MNG_NO[5:10] == '{SIGUNGU}' (OBJ + kind(2) + sigungu(5) + serial(8))",
        "zips": {k: {"file": v.name, "sha256": sha256(v), "bytes": v.stat().st_size} for k, v in ZIPS.items()},
        "layers": layers,
    }
    # 영덕군 is larger than the canonical routing canvas (config/default.yaml), so the check is
    # containment of the set, not of every point: centroid inside the box and most points inside.
    box = (129.25, 36.30, 129.55, 36.60)
    shares = {k: _inside_share(OUT / f"{k}.geojson", box) for k, v in layers.items() if v["count"]}
    for k, (share, cx, cy) in shares.items():
        layers[k]["inside_canonical_box_share"] = round(share, 3)
        layers[k]["centroid_lon_lat"] = [round(cx, 4), round(cy, 4)]
        assert share >= 0.5 and box[0] <= cx <= box[2] and box[1] <= cy <= box[3], (k, share, cx, cy)
    assert my["road_address"].astype(str).str.contains("영덕군").all(), "an agency address is not in 영덕군"
    manifest["bbox_check"] = {"box": list(box), "rule": "centroid inside and >= 50 % of points inside; the county is larger than the canvas",
                              "result": "pass"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in layers.items():
        print(f"[juso] {k:28s} {v['count']:5d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
