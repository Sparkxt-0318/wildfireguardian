# SKIPPED

Rule applied: a source that cannot be obtained, or does not cover the dates, gets one line and nothing is compared for it. No mirror,
copy, account, key or login was used or invented. First pass (to 22:40 UTC): hosts blocked by the network policy, nothing changed. Second
pass (from 22:41 UTC): the user allowed the hosts (new environment `wildfireguardian-kcf-validate`); probes are plain requests to each
source's own host or its own public pages.

1. **Korea Expressway Corporation 15-minute section traffic volume, 22-27 March 2025: PARTLY OBTAINED, 15-minute NOT.** The user supplied six **daily** files (dataset 512, TCS section volumes, all routes); the monthly ZIP arrived empty. The 15-minute API (0305) needs a key (`인증키값이 없습니다`) and the 15-minute file dataset (148) a portal login with five declarations, neither of which I hold or invented. So **no closure time (volume to zero) and no outbound surge** can be derived; only day totals (RESULTS.md row 1).
2. **Official emergency texts (재난문자) with send times, 22-27 March 2025: OBTAINED** (user-supplied export, 312 messages for the five counties and 경상북도 전체; RESULTS.md rows 2-2c). Six REPORTED rows stay REPORTED (RD5, RD6, RD12, RD13, VA1, VA2) for lack of a matching official message. Authenticity of the export is not independently verified.
3. **Independent satellite record: OBTAINED IN PART (not skipped).** Sentinel-2 L2A (open bucket) 24 March 2025 02:17 UTC, i.e. fire
   extent on day 3, covers neither the 25 March replay window nor any scene after the fire's main run (27 March is 99.99 % cloud; the 22
   March scene is partial). GK-2A: **NOT OBTAINED**; `nmsc.kma.go.kr` is reachable now, but its download link goes to `data.kma.go.kr` (not allowed, login needed). Landsat 8/9 was **not used**
   (its AWS bucket is requester-pays, as I know it, not tested here; no payer account was given). So the record is real but is a different day from the road closures.
4. **NIST Camp Fire: PARTLY OBTAINED.** Both reports were read; burnovers, fire-progression and closure rows were extracted as data (tables, never figures) and compared by road (RESULTS.md 4a-4b). **Not obtained:** a fire-arrival field (no polygon dataset found; the tables are point times at named places), and therefore **the roadlayer run on Paradise was not made**; it would also need a Paradise road graph, places and shelters that this repository does not have.
5. **Twin experiment: RUN** (see RESULTS.md). Its limits are in RESULTS.md, not here: the simulator is mine, not FARSITE.
6. **Prospective log: STARTED, no first entry.** No active Korean fire was identified (web search only; FIRMS and KFS unreachable, so
   absence is unverified). See `PROSPECTIVE_LOG.md`.
