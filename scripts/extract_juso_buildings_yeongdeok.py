#!/usr/bin/env python
"""NH-005 (closed 2026-09-13): the 도로명주소 건물 (building footprint) layer for 영덕군.

The author downloaded ``(도로명주소)건물_경북.zip`` from 주소기반산업지원서비스
(business.juso.go.kr, 도로명주소 전자지도 → 건물, 경상북도, data month 2026-08) and placed
it under the git-ignored ``data/raw/juso_buildings/``. This script cuts the 영덕군 subset
(``SIG_CD == '47770'``) and writes a small committed artifact:

* ``data/processed/external/juso_buildings_yeongdeok/buildings_47770.geojson.gz`` — one POINT
  per building (the footprint centroid; the polygons stay in the raw bundle) in EPSG:4326,
  with the centroid in EPSG:5179, the projected footprint area and the layer's own
  attributes (건물관리번호, 건물용도코드, 지상/지하 층수, 건물명, 읍면동·리 코드, 주/부속 구분,
  산 여부);
* ``manifest.json`` — zip digest, data month, agency, CRS, counts, and the count inside the
  canonical 영덕 box beside the OSM count the repository has used so far.

Deterministic; re-run to regenerate.

    python scripts/extract_juso_buildings_yeongdeok.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "juso_buildings"
ZIP = RAW / "(도로명주소)건물_경북.zip"
SHP = RAW / "TL_SPBD_BULD_47_202608.shp"
OUT = REPO / "data" / "processed" / "external" / "juso_buildings_yeongdeok"
SIGUNGU = "47770"          # 경상북도 영덕군 (the 2026-09-04 사물주소 cut established this code; NH-022)
OSM_ARTIFACT = REPO / "data/processed/building_origin_routing.json"   # bld_yeongdeok_n_mapped = 124

KEEP = {  # layer field -> (property name, meaning)
    "BD_MGT_SN": ("bd_mgt_sn", "건물관리번호 (unique per building)"),
    "BDTYP_CD": ("bdtyp_cd", "건물용도코드 (as published; not decoded here)"),
    "BUL_DPN_SE": ("bul_dpn_se", "M = 주건물, S = 부속건물"),
    "GRO_FLO_CO": ("gro_flo_co", "지상층수"),
    "UND_FLO_CO": ("und_flo_co", "지하층수"),
    "BULD_NM": ("buld_nm", "건물명 (mostly empty)"),
    "EMD_CD": ("emd_cd", "읍면동코드 (3 digits within the 시군구)"),
    "LI_CD": ("li_cd", "리코드"),
    "MNTN_YN": ("mntn_yn", "산 여부"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    import geopandas as gpd
    from pyproj import Transformer

    from wildfireguardian.utils import regions

    if not SHP.exists():
        raise SystemExit(f"missing {SHP}: unzip {ZIP.name} into {RAW} first (laptop-only bundle)")
    # record count of the whole 시도 file, read off the .shx index (100-byte header, 8 bytes per record)
    n_province = (SHP.with_suffix(".shx").stat().st_size - 100) // 8
    df = gpd.read_file(SHP, encoding="EUC-KR", where=f"SIG_CD = '{SIGUNGU}'")
    crs_layer = str(df.crs)
    assert str(df.crs).upper().endswith("5179"), df.crs
    n_county = int(len(df))
    assert df["BD_MGT_SN"].nunique() == n_county, "건물관리번호 is not unique"

    region = regions.lookup("yeongdeok_2025")
    minx, miny, maxx, maxy = region.bbox_epsg5179
    cen = df.geometry.centroid
    cx, cy = cen.x.to_numpy(), cen.y.to_numpy()
    area = df.geometry.area.to_numpy()
    inside = (cx >= minx) & (cx <= maxx) & (cy >= miny) & (cy <= maxy)
    to_wgs = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    lon, lat = to_wgs.transform(cx, cy)

    feats = []
    for i in range(n_county):
        props = {"centroid_x_5179": round(float(cx[i]), 2), "centroid_y_5179": round(float(cy[i]), 2),
                 "footprint_area_m2": round(float(area[i]), 1),
                 "inside_canonical_box": bool(inside[i])}
        for col, (name, _) in KEEP.items():
            v = df[col].iloc[i]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                v = None
            elif col in ("GRO_FLO_CO", "UND_FLO_CO"):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = None
            else:
                v = str(v)
            if v is not None and v != "":
                props[name] = v
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [round(float(lon[i]), 6), round(float(lat[i]), 6)]}})
    feats.sort(key=lambda f: f["properties"]["bd_mgt_sn"])
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"type": "FeatureCollection", "name": "juso_buildings_yeongdeok_47770",
                       "crs_note": "coordinates EPSG:4326; centroid_x/y_5179 are the layer's own EPSG:5179 metres",
                       "features": feats}, ensure_ascii=False, separators=(",", ":")) + "\n"
    with gzip.GzipFile(OUT / "buildings_47770.geojson.gz", "wb", mtime=0) as fh:   # mtime=0: byte-stable
        fh.write(body.encode("utf-8"))

    osm = json.loads(OSM_ARTIFACT.read_text(encoding="utf-8"))
    osm_n = int(osm["regions"][0]["n_buildings"])
    n_inside = int(inside.sum())
    main_inside = int(((df["BUL_DPN_SE"] == "M").to_numpy() & inside).sum())
    manifest = {
        "what": "영덕군 (SIG_CD 47770) subset of the 도로명주소 전자지도 건물 layer, 경상북도 file, data month 2026-08 — the layer NH-005 asked for",
        "agency": "행정안전부 주소기반산업지원서비스 (business.juso.go.kr), 도로명주소 전자지도 → 건물",
        "retrieved_by": "the author, 2026-09-13 (portal login + agency approval; the loop cannot log in)",
        "zip": {"file": ZIP.name, "sha256": sha256(ZIP), "bytes": ZIP.stat().st_size},
        "artifact": "buildings_47770.geojson.gz (gzip; absent properties were empty in the layer)",
        "layer_file": SHP.name, "layer_crs": crs_layer, "layer_encoding": "EUC-KR (.cpg)",
        "data_month": "2026-08", "sigungu_cd": SIGUNGU,
        "counts": {
            "province_47_buildings": n_province,
            "county_47770_buildings": n_county,
            "inside_canonical_box": n_inside,
            "inside_canonical_box_main_buildings": main_inside,
            "outside_canonical_box": n_county - n_inside,
            "osm_buildings_inside_walk_bbox": osm_n,
            "osm_share_of_juso_inside_box_pct": round(100.0 * osm_n / n_inside, 2),
        },
        "canonical_box": {"wgs84": list(region.bbox_wgs84), "epsg5179": [round(v, 1) for v in region.bbox_epsg5179],
                          "rule": "footprint centroid inside the box"},
        "properties": {name: meaning for _, (name, meaning) in KEEP.items()},
        "footprint_area_m2": {"median": round(float(np.median(area)), 1), "note": "projected area of the source polygon; only the centroid is committed"},
        "bdtyp_cd_top": {k: int(v) for k, v in df["BDTYP_CD"].value_counts().head(10).items()},
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Administrative inventory as published (건축물대장-linked 도로명주소 건물); not a survey of what stands today and not a household count: a building is not a household, and the layer does not say who lives in it.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=1))
    print("wrote", OUT.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
