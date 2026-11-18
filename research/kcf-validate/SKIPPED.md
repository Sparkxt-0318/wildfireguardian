# SKIPPED

Rule applied: a source that cannot be obtained, or does not cover the dates, gets one line and nothing is compared for it. No mirror,
copy, key or login was used or sought; no network setting was changed. Probes are plain requests to each source's own host.

1. **Korea Expressway Corporation 15-minute section traffic volume, 22-27 March 2025: NOT OBTAINED.** `data.ex.co.kr` is refused by the
   build container's network policy (HTTPS CONNECT answered 403 by the proxy at 2026-11-18 ~15:25 UTC; the separate fetch tool failed with
   "getaddrinfo ENOTFOUND"); whether the portal would also require an account or API key, or hold 15-minute data for these dates, was not
   reachable and is not claimed.
2. **Official emergency texts (재난문자) with send times, 22-27 March 2025: NOT OBTAINED.** `www.safekorea.go.kr`, `www.data.go.kr`,
   `apis.data.go.kr` and `www.mois.go.kr` are refused by the same policy (CONNECT 403; fetch tool: ENOTFOUND); nothing read from them. The
   existing text times in `research/kcf-replay/SOURCES.md` remain REPORTED (county log via news), not official records.
3. **Independent satellite record: OBTAINED IN PART (not skipped).** Sentinel-2 L2A (open bucket) 24 March 2025 02:17 UTC, i.e. fire
   extent on day 3, covers neither the 25 March replay window nor any scene after the fire's main run (27 March is 99.99 % cloud; the 22
   March scene is partial). GK-2A (`nmsc.kma.go.kr`) refused by the network policy (CONNECT 403): **GK-2A NOT OBTAINED**. Landsat 8/9 was **not used**
   (its AWS bucket is requester-pays, as I know it, not tested here; no payer account was given). So the record is real but is a different day from the road closures.
4. **NIST Camp Fire case study (TN 2135 progression, TN 2252 evacuation), road-layer run on Paradise: NOT OBTAINED.** `nvlpubs.nist.gov`,
   `www.nist.gov`, `tsapps.nist.gov` and `data.nist.gov` are refused by the network policy (CONNECT 403; fetch tool: ENOTFOUND on
   `nvlpubs.nist.gov`). Whether the progression and closures are tables or only figures, and whether a companion dataset exists, could not
   be read and is **not** claimed either way; no Paradise run was made (it also needs a Paradise road graph, which this repository does not
   have).
5. **Twin experiment: RUN** (see RESULTS.md). Its limits are in RESULTS.md, not here: the simulator is mine, not FARSITE.
6. **Prospective log: STARTED, no first entry.** No active Korean fire was identified (web search only; FIRMS and KFS unreachable, so
   absence is unverified). See `PROSPECTIVE_LOG.md`.
