# 영덕 designated sites and public offices from 주소정보누리집 (2026-09-04)

**What this is.** On 2026-09-04 the author downloaded two datasets from 행정안전부's
주소정보누리집 (business.juso.go.kr), a portal the loop cannot log into, and placed the zips
under the git-ignored `data/raw/juso/`. `scripts/extract_juso_yeongdeok.py` cuts the 영덕군
subset into `data/processed/external/juso_yeongdeok/` (GeoJSON, EPSG:4326, about 100 KB) with
a manifest carrying both zips' sha256, the data dates and the filter; the layer counts are
registered as `juso_yeongdeok_*_count` by `scripts/register_juso_yeongdeok.py`.

| dataset | data date | what it holds for 영덕 | registry keys |
|---|---|---|---|
| 사물주소도형 (경상북도 전체분) | 2025-03-01 | 지진옥외대피장소, 무더위쉼터, 인명구조함, 소화전, 비상급수시설, 버스정류장 points (지진해일대피장소 and 비상급수 have no 영덕 rows) | `juso_yeongdeok_samul_*_count` |
| 민원행정기관 전자지도 | 2024-01-24 | schools, 읍면동 offices, 보건소·보건지소·진료소, 파출소, 119안전센터, post offices | `juso_yeongdeok_minwon_agencies_count` |

**What this is not.** Neither file is the 도로명주소 **건물** (building footprint) layer that
NH-005 asks for; household counts stay provisional on the OSM buildings and NH-005 stays open.

**Why it matters.** The router's refuges and depots have so far come from OSM tags, the
공공데이터포털 shelter standard data when configured, and a documented synthetic fallback
(`docs/data_sources.md`, "Rescue-aware routing inputs"). These two files give, for the first
time in the repository, an *agency-designated* list for 영덕: outdoor evacuation sites and
cooling centres as refuge candidates, and the 119 centres, 파출소 and 읍면동 offices as
responder depots or notification targets, each with a road address and a phone number.

**Method notes.** 사물주소 object ids encode the 시군구 code in positions 5–10
(`OBJ` + kind + `47920` + serial); the shapefiles ship without a `.prj` and were assigned
EPSG:5179 because they fall on the same grid as the agency points, which do carry it.
Re-running the extractor is deterministic; the raw zips are laptop-only.

**What it does not show.** Whether a listed 무더위쉼터 is open during a spring wildfire, its
capacity, or whether any site is a designated *wildfire* 대피소 — the 사물주소 categories are
earthquake, tsunami and heat. That question (NH-012 b) is narrowed, not answered.

**Next (backlog).** WFG-073 compares the router's current refuges with the designated sites;
WFG-074 wires the 119 centres, 파출소 and 읍면동 offices in as depots and notification targets.
