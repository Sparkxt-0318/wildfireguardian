# 산림청 helipad register: addendum 1 to KFS_HELIPAD_MANIFEST.md (@ca7133d8)

This note adds detail to the manifest; the manifest itself is not edited. It answers the independent verifier's
notes on verification ledger row 88 (PASS WITH NOTES: independent re-fetch, same sha256 55f66625…, counts reproduce).

## Row breakdown (re-derived from the fetched CSV with `helipad_breakdown` logic below; matches the verifier's)

- Blank coordinates, 24 rows: 22 rows with all six DMS fields blank, 2 rows with some fields blank.
- Invalid coordinates, 65 rows:
  - seconds ≥ 60 only: 38
  - minutes ≥ 60 and seconds ≥ 60: 11
  - minutes ≥ 60 only: 4
  - inside the DMS limits but outside the 33–39°N, 124–132°E box: 10
  - minutes ≥ 60, seconds ≥ 60 and outside the box: 2
- Valid coordinates, 538 rows, of which 500 are distinct points (38 rows repeat an earlier valid coordinate).

Rule used: a row is blank if any of the six DMS fields is empty; otherwise lat = deg + min/60 + sec/3600 (same for lon),
and the row is valid only if minutes < 60, seconds < 60 and the point is inside the box. Invalid rows are still not
repaired.

## Portal metadata (from the dataset page saved at retrieval, 2026-11-13T00:30Z)

- 기준일자 (`stdrDe` in the step-1 response): 2025-10-22.
- 데이터 한계: "군(軍) 이착륙장 정보는 제공되지 않습니다. 해당 이착륙장을 이용하기 위해서는 사전에 담당 기관과 협의가 필요합니다."
  Military landing sites are not included, and using a listed site needs prior coordination with the managing agency.
- Datum: not stated in the file or on the page.

## About KFS_HELIPAD_INSPECT.txt

It is the combined output of both committed scripts (`inspect_kfs_helipad.py` and `coords_kfs_helipad.py`), abridged:
the invalid-row sample shows the first 5 rows only.
