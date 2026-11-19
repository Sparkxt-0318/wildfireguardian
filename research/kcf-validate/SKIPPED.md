# SKIPPED

Rule applied: a source that cannot be obtained, or does not cover the dates, gets one line and nothing is compared for it. No mirror,
copy, account, key or login was used or invented. First pass (to 22:40 UTC): hosts blocked by the network policy, nothing changed. Second
pass (from 22:41 UTC): the user allowed the hosts (new environment `wildfireguardian-kcf-validate`); probes are plain requests to each
source's own host or its own public pages.

1. **Korea Expressway Corporation 15-minute section traffic volume, 22-27 March 2025: OBTAINED** (user-supplied dataset 148, March 2025, with dataset 157 "콘존" for the section names), routes 0300 (서산영덕선) and 0550 (중앙선); results in RESULTS.md rows 1a-1d. Limits: 14 % of readings are missing; night slots are not testable (baseline < 15 vehicles per 15 min); only 2-6 conzone-directions per event show a derived time; the baseline is not weekday-matched. My first section mapping (TCS correlation) was wrong and is withdrawn (outputs kept in `out/vds/superseded_tcs_mapping/`). Earlier: the daily dataset 512 files arrived and the monthly ZIP was empty.
2. **Official emergency texts (재난문자) with send times, 22-27 March 2025: OBTAINED** (user-supplied export, 312 messages for the five counties and 경상북도 전체; RESULTS.md rows 2-2c). Six REPORTED rows stay REPORTED (RD5, RD6, RD12, RD13, VA1, VA2) for lack of a matching official message. Authenticity of the export is not independently verified.
3. **Independent satellite record: OBTAINED IN PART (not skipped).** Sentinel-2 L2A (open bucket) 24 March 2025 02:17 UTC, i.e. fire
   extent on day 3, covers neither the 25 March replay window nor any scene after the fire's main run (27 March is 99.99 % cloud; the 22
   March scene is partial). GK-2A: **NOT OBTAINED**; `nmsc.kma.go.kr` is reachable now, but its download link goes to `data.kma.go.kr` (not allowed, login needed). Landsat 8/9 was **not used**
   (its AWS bucket is requester-pays, as I know it, not tested here; no payer account was given). So the record is real but is a different day from the road closures.
4. **NIST Camp Fire: OBTAINED AS TABLES; Paradise run MADE on a reconstructed field.** Both reports were read; burnovers, fire-progression and closure rows were extracted as data and compared by road (RESULTS.md 4a-4b). No arrival field exists as data, so the Paradise run (4c-4e) uses a field reconstructed by me from the geocoded progression rows (255 of 392; leave-one-out median error 101 min); the record comparison covers 13 located records (14 of 19 burnovers and 7 of 15 closure rows could not be placed) and cannot separate the closure rule from the interpolation. The roadlayer CLI could not be used (EPSG:5179 is hard-coded in its raster reader); its engine was called directly.
5. **Twin experiment: RUN** (see RESULTS.md). Its limits are in RESULTS.md, not here: the simulator is mine, not FARSITE.
6. **Prospective log: STARTED, no first entry.** No active Korean fire was identified (web search only; FIRMS and KFS unreachable, so
   absence is unverified). See `PROSPECTIVE_LOG.md`.
