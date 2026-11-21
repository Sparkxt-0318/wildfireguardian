# AIR-EXTRACT fetch plan: one item

**Status:** PLANNED. Nothing has been fetched.

**Scope:** decided by the orchestrator and relayed by Leo at 22:39 UTC on 12 Nov 2026. It is staff/agency-only (DESIGN.md B3, 8f13c1c0).

**Timing:** after the road extract. It does not block anything.

## Item 1: 산림청 산림항공본부_이착륙장 정보 (registered helicopter landing sites)

- **Source:** data.go.kr fileData 15069465. 627 rows. Modified 2026-09-17. Licence: "이용허락범위 제한 없음".
- **Method:** one HTTPS download of the published file. No API.
  - If the download page requires a data.go.kr login, STOP and report BLOCKED. We do not register for accounts.
- **Store:** in the scratchpad, not the repo, until the custodian reviews it.
  - Commit only derived, small files: a manifest and, if approved, a cleaned CSV.
- **Record in the manifest:**
  - sha256 and size;
  - retrieval time (UTC) and the final URL;
  - row count (expect 627; note any difference);
  - detected encoding (expect CP949; record the decode test);
  - header field names;
  - coordinate format (expect DMS). Record the parse rule and its datum if the file states one; if it does not, write "not stated".
- **Processing:** run with Python -I from a separate scripts directory. Read-only parse; no pickles.

## Excluded

- API variant 15134224: needs a service key.
- GLO-30 extra tiles, ESA WorldCover and OSM land-use/POI polygons. These are a later extension, only if the owner asks again.
