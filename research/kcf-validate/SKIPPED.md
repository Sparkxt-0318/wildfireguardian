# SKIPPED

Rule applied: a source that cannot be obtained, or does not cover the dates, gets one line and nothing is compared for it. No mirror,
copy, account, key or login was used or invented. First pass (to 22:40 UTC): hosts blocked by the network policy, nothing changed. Second
pass (from 22:41 UTC): the user allowed the hosts (new environment `wildfireguardian-kcf-validate`); probes are plain requests to each
source's own host or its own public pages.

1. **Korea Expressway Corporation 15-min section traffic volume, 22-27 March 2025: NOT OBTAINED, needs a key or login.** The host was blocked until you allowed it (22:41 UTC); `data.ex.co.kr` is reachable and has the data (API 0305; file dataset 148), but the API answers a keyless request with `인증키값이 없습니다` and the file download needs a portal login plus five declarations (소속, 지역, 성별, 나이, 활용목적), which I did not create or invent.
2. **Official emergency texts (재난문자) with send times, 22-27 March 2025: NOT OBTAINED, needs a key or your decision.** 국민안전24 (`safekorea.go.kr`) lists messages publicly but its date picker offers only the last 7 days, and I did not send other dates without your say-so; the history route is the `data.go.kr` OpenAPI (service key, usage application). No county publishes a file.
3. **Independent satellite record: OBTAINED IN PART (not skipped).** Sentinel-2 L2A (open bucket) 24 March 2025 02:17 UTC, i.e. fire
   extent on day 3, covers neither the 25 March replay window nor any scene after the fire's main run (27 March is 99.99 % cloud; the 22
   March scene is partial). GK-2A: **NOT OBTAINED**; `nmsc.kma.go.kr` is reachable now, but its download link goes to `data.kma.go.kr` (not allowed, login needed). Landsat 8/9 was **not used**
   (its AWS bucket is requester-pays, as I know it, not tested here; no payer account was given). So the record is real but is a different day from the road closures.
4. **NIST Camp Fire: PARTLY OBTAINED.** Both reports were read; burnovers, fire-progression and closure rows were extracted as data (tables, never figures) and compared by road (RESULTS.md 4a-4b). **Not obtained:** a fire-arrival field (no polygon dataset found; the tables are point times at named places), and therefore **the roadlayer run on Paradise was not made**; it would also need a Paradise road graph, places and shelters that this repository does not have.
5. **Twin experiment: RUN** (see RESULTS.md). Its limits are in RESULTS.md, not here: the simulator is mine, not FARSITE.
6. **Prospective log: STARTED, no first entry.** No active Korean fire was identified (web search only; FIRMS and KFS unreachable, so
   absence is unverified). See `PROSPECTIVE_LOG.md`.
