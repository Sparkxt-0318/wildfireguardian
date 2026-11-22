# kcf-buildings: sources, dates, hashes

Every file below was fetched or read on 2026-11-20/21 (UTC times as given). Raw files that are large or re-fetchable are in
`raw/` (not committed); their SHA-256 is recorded so a re-fetch can be compared. The Overpass attic option returns the
OpenStreetMap database as it stood at the given date.

| dataset | where | date of the data | fetched (UTC) | file | SHA-256 | status |
|---|---|---|---|---|---|---|
| MOIS 주민등록 인구통계, 월간, 전체 읍면동, 세대수·인구 | https://jumin.mois.go.kr/statMonth.do (downloadCsv.do, all 읍면동) | 2025-02 month-end | 2026-11-20T16:32Z | data/mois_202502_households.csv | fa3647a35f702a2a995d347d2e8bd017d2b2dbd1b687c94bd4277e99827aed88 | MEASURED (읍·면·동) |
| MOIS 주민등록 인구통계, 연령별 (5세 구간), 전체 읍면동 | https://jumin.mois.go.kr/ageStatMonth.do (downloadCsvAge.do, all 읍면동) | 2025-02 month-end | 2026-11-20T16:32Z | data/mois_202502_age5.csv | 2f81ba5c5b9f6f77d72b1ee2199e49fb566644e0037fa920aade410ba2f06dd8 | MEASURED (읍·면·동) |
| 법정동코드 table (live 법정리 per 읍·면) | PublicDataReader 1.1.1.post2 wheel, raw/code_bdong.json (newest entry 2022-09-01) | table of 2022-09 | 2026-11-20 | raw/PublicDataReader.whl (not committed, SHA pinned) | 7802f750bcd538b078e7be54146556968017dd43fb1b4e781fa440a4e770b2b6 | public code table |
| OpenStreetMap building | https://overpass-api.de/api/interpreter with [date:"2025-03-21T23:59:59Z"] (attic); boxes in fetch_osm.py | snapshot 2025-03-21T23:59:59Z | 2026-11-20T17:04:52Z | raw/osm_building_20250321.json (not committed; 17293 elements) | 1bbb21e5e341d89584ff7512633a9c0f9a35386ee2899a3efe02361c7a14d1d2 | MAPPED (lower bound) |
| OpenStreetMap amenity | https://overpass-api.de/api/interpreter with [date:"2025-03-21T23:59:59Z"] (attic); boxes in fetch_osm.py | snapshot 2025-03-21T23:59:59Z | 2026-11-20T16:56:46Z | raw/osm_amenity_20250321.json (not committed; 572 elements) | ffd225ce937cf5cf05d2edde43de58684719292620a9b94369d85bb2ff7b616b | MAPPED (lower bound) |
| OpenStreetMap place | https://overpass-api.de/api/interpreter with [date:"2025-03-21T23:59:59Z"] (attic); boxes in fetch_osm.py | snapshot 2025-03-21T23:59:59Z | 2026-11-20T17:10:59Z | raw/osm_place_20250321.json (not committed; 1686 elements) | 8e3942b11edc43cc57f7d2cdb81291d62802829c1319a2748bdc6c36d0be8943 | MAPPED (lower bound) |
| OpenStreetMap admin | https://overpass-api.de/api/interpreter with [date:"2025-03-21T23:59:59Z"] (attic); boxes in fetch_osm.py | snapshot 2025-03-21T23:59:59Z | 2026-11-20T16:58:42Z | raw/osm_admin_20250321.json (not committed; 68 elements) | eb2105db360bd3e7e578fc76f002419142878ad1f5b61656d89c084723aa0c6b | MAPPED (lower bound) |
| Gyeongbuk registered vehicles 2024-12 (1,552,434) | cited in product/wfg-roadlayer/data/traffic_sources.json (대구MBC citing MOLIT) | end of 2024 | (already in repo) | traffic_sources.json |  | CITED; ratio = ESTIMATE |

## What was tried and did not work (the order of PROTOCOL §2)

* **건축물대장 (data.go.kr) and the road-name address building database, VWorld:** need `DATA_GO_KR_KEY` / a VWorld key.
  The folder "wildfire 3 (1)" holds only `DATA_INDEX.md` (no key, per that file); `DATA_GO_KR_KEY` is not set in the
  environment. No key was looked for elsewhere. Not used.
* **Geofabrik `south-korea-250321.osm.pbf`:** HTTP 404 (the public server no longer holds it). Replaced by the Overpass
  attic query of the same date.
* **Microsoft building footprints:** the dataset index (`dataset-links.csv`, 35 location names) has no Korea row.
  **Google Open Buildings:** does not cover Korea. Neither was fetched.
* **MOLIT `stat.molit.go.kr` (자동차등록현황보고, table 5498 is by 시도):** the district table needs the script-driven portal;
  the plain data endpoint returned no rows. **data.go.kr 국토교통부_자동차 등록 현황 (15024777):** the file download is behind a
  CAPTCHA, which was not bypassed. **KOSIS (DT_MLTM_5498, 시군구 selectable):** the page did not render in the built-in
  browser. A third-party ranking (knsi.kr, citing KOSIS e-지방지표) gives vehicles per person rounded to 0.1 (0.6 for 안동·영덕,
  0.7 for 의성·청송·영양): too coarse to use. Result: the province ratio (`data/vehicle_ratio.json`).
* **MOIS per-리 statistics:** none exist on the site (the download options are 시도, 시군구, 읍면동). Per-village figures are
  therefore estimates inside measured 읍·면·동 totals.
* **Copernicus built-up cover (Zenodo 3939050), window 128.2–129.6 E, 36.05–37.05 N:** read (200 KB) for the sensitivity of
  PROTOCOL amendment 1(e); **not used**: the 법정리 anchors needed to split a 읍·면 by it could not be located.
