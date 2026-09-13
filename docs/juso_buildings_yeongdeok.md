# The 도로명주소 건물 layer for 영덕 (NH-005, closed 2026-09-13)

**What arrived.** On 2026-09-13 the author attached `(도로명주소)건물_경북.zip` — the
행정안전부 도로명주소 전자지도 **건물** layer for 경상북도, data month 2026-08, EPSG:5179,
1,410,840 buildings — the file NH-005 had asked for since 2026-09-04 (portal login and
agency approval; nothing the loop could fetch). It sits under the git-ignored
`data/raw/juso_buildings/`. Registered keys: `jbld_*` (`scripts/register_juso_buildings.py`).

## 1. What was done

`scripts/extract_juso_buildings_yeongdeok.py` cuts `SIG_CD == '47770'` (영덕군; the code
the 2026-09-04 사물주소 cut established, NH-022) and commits **centroids only** as
`data/processed/external/juso_buildings_yeongdeok/buildings_47770.geojson.gz` (0.9 MB,
byte-stable) with the layer's attributes: 건물관리번호, 건물용도코드, 주/부속 구분,
지상·지하 층수, 건물명, 읍면동·리 코드, 산 여부, projected footprint area, and a flag for
「centroid inside the canonical 영덕 box」. `manifest.json` carries the zip digest and counts.

`JusoBuildingSource` (`source="juso"`) now sits behind the existing `BuildingSource` seam
in `src/wildfireguardian/buildings/`, next to `osm`. It returns the inside-box population,
which is the extent the OSM layer was acquired on, so the two sources describe the same
ground. Nothing downstream was switched to it.

## 2. Result

| quantity | value | key |
|---|---:|---|
| buildings in the 경북 file | 1,410,840 | `jbld_province_buildings` |
| 영덕군 (47770) | 33,113 | `jbld_county_buildings` |
| inside the canonical 영덕 box | 28,361 | `jbld_inside_box` |
| of which 주건물 (M) | 19,959 | `jbld_inside_box_main` |
| OSM `building=*` used so far, same box | 124 | `jbld_osm_inside_box` (= `bld_yeongdeok_n_mapped`) |
| OSM share of the 도로명주소 count | 0.44 % | `jbld_osm_share_pct` |

**The coverage question WFG-013 kept open is answered for 영덕: the OSM footprints the
building-origin results stand on are under half a percent of the administrative building
stock in the same box.** `docs/building_sampling.md` §3 had measured that the OSM sample
is spatially biased; this is its size.

## 3. What this does NOT show

- **Not a household count.** A building is not a household and the layer says nothing
  about who lives in it, whether anyone does, or their age. 부속건물 (S) are 8,402 of the
  inside-box buildings; a count must say whether it took M only.
- **No routing number moves.** Every building-origin result (`bld_*`, village-edge,
  WUI) still stands on the 124 OSM footprints and stays labelled provisional. Re-running
  them on this layer is the next row (see `docs/auto/BACKLOG.md`), not this one, because it
  changes an origin population the committed contrasts were built on.
- **One region only.** 의성·안동 needs the same 경북 file cut on its 시군구 codes; 울진·삼척
  straddles 경북 and 강원 and needs both 시도 files. The seam raises until then.
- **건물용도코드 is carried, not decoded.** `bdtyp_cd_top` in the manifest lists the codes;
  01001 dominates (21,081 inside the box). A 요양시설 / 경로당 proxy is possible from these
  codes once the code table is sourced, and is not claimed here.

## 4. Reproduce

    python scripts/extract_juso_buildings_yeongdeok.py     # needs data/raw/juso_buildings/ (laptop only)
    python scripts/register_juso_buildings.py --check
