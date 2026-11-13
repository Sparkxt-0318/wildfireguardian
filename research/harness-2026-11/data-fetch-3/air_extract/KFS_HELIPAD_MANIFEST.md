# 산림청 산림항공본부_이착륙장 정보: fetch manifest (FETCH_PLAN item 1)

## Retrieval

- **Retrieved:** 2026-11-13T00:30:41Z (UTC). One file download, no login, no key.
- **Route:** the site's own public download flow, as the page's buttons do it:
  1. `POST /tcs/dss/selectFileDataDownload.do` (publicDataPk 15069465, detail uddi:11220fc8-6fe3-47c3-bed3-fe3972f9a736). This returned atchFileId FILE_000000003705212, fileDetailSn 1.
  2. `POST /cmm/cmm/check-limit.json`. This returned `{"needCaptcha":false}`. If a captcha had been required, the plan was to stop as BLOCKED.
  3. `GET /cmm/cmm/fileDownload.do`. This returned HTTP 200.
- **Final URL:** `https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003705212&fileDetailSn=1&dataNm=…`
- **Served filename:** `산림청 산림항공본부_이착륙장 정보_20251022.csv`. The portal shows it as modified 2026-09-17 10:03:33, licence "이용허락범위 제한 없음".

## File

- **sha256:** 55f666251b5e803ad2fd92eaaf1a8518200045038dc03838b0d76f73b6137931
- **Size:** 116,211 bytes.
- **Encoding:** CP949 (decode test: UTF-8 fails at byte 0; EUC-KR fails at byte 14,080 on an extended character; CP949 OK). CRLF line endings, no BOM.
- **Rows:** 627 data rows, as expected, plus the header. 32 columns, none ragged.
- **Header:** 이착륙장주소, 이착륙장명, 북쪽위도, 북위분, 북위초, 동경도, 동경분, 동경초, 관리소거리값, 관할기관명, 변경1이착륙장명, 변경1이착륙장방위각, 안전지역상세내용, 착륙상승구역내용, 이착륙방향내용, 표면상세내용, 장애물1–3 (형태내용, 높이, 방위각, 거리값), 장애1내용, 장애2내용, 유조차대기장소, 점검일.

## Coordinates

- **Format:** DMS split over six integer columns: lat 도/분/초 (북쪽위도, 북위분, 북위초) and lon 도/분/초 (동경도, 동경분, 동경초).
- **Parse rule:** deg + min/60 + sec/3600. A row is valid only if minutes and seconds are both below 60 and the point falls inside 33–39°N, 124–132°E.
- **Results:**
  - 538 rows are valid. Their range is 33.29–38.11°N, 126.29–129.67°E.
  - 24 rows have blank coordinates.
  - **65 rows are INVALID**: minutes or seconds of 60 or more, for example 북위분 95 and 북위초 82, or a seconds value of 4966. These look like decimal fragments mis-entered into the DMS columns.
  - The invalid rows are NOT repaired or guessed. They are reported as unusable until the data owner corrects them.
- **Datum:** not stated (there is no datum column or note in the file).
- **Other facts:** 경북 rows: 48. 점검일 range 2014-07-07 to 2025-10-22.

## Storage

- The CSV is kept in the scratchpad, outside the repository, pending custodian review. This manifest, the inspect scripts and their output are committed.
