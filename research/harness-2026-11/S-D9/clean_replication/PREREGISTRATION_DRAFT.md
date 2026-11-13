# Clean-replication cohort (CR1): pre-registration DRAFT

**Status: DRAFT 13, not frozen. Nothing has been fetched, listed or read for this cohort.**
- It is a new document, not an edit to A1.
- Owner decision (relayed by the orchestrator, 2026-11-12): collect a fresh set of fires for a clean replication.
- The current A1 parts b and c proceed, but are described as **"labels, perimeters and growth sealed; survey-timing metadata exposed; membership rules used it"**. H is descriptive. Neither is presented as the clean confirmation.

Draft 1 added Iris's design input (15:06Z). Draft 2 adds her section-by-section assessment (15:09Z), adopted by the orchestrator. Draft 3 records the owner's decision on N_target (12 Nov). Draft 4 resolves Hannah's custodian protocol review (15:23Z): blocking items B1–B5 and her smaller fixes. Draft 5 answers her re-review of draft 4 (15:30Z): a canonical_id rule that survives archive moves, and the Tier-1 scope conflict with two earlier registrations. Draft 6 records the owner's scope decision (relayed 12 Nov): no 2026 fire in any tier, and Tier 2 starts 2027-01-01. It also adds the 2026+ no-access rule and Hannah's conditions on the rehearsal fallback (15:40Z). Draft 7 records the orchestrator's Tier-1 position and the freeze precondition on access (15:47Z). Draft 8 adds Hannah's fixed access attempt and outcome rule (16:01Z) and records the disagreement over the access gate as open. Draft 9 adds §9, a Korean prospective descriptive stratum (KR-P), at the orchestrator's request. Draft 10 records the owner's ftp.wildfire.gov finding and lays out the access-route options. Draft 11 drafts the in-season harvest route (d'), after Sofia's path correction, and the recommended route. In 11c, after Daniel's documentation answer, the harvest is primary and a compiled release is a cross-check. The §0 "cleanliness only" claim is qualified. 11d adds Hannah's no-look conditions a–g and her finding that the Maps tree serves only the current season. Draft 12 records the owner's decision approving the in-season harvest, and rewords §0. Draft 13 adds Iris's assessment of the harvest route, adopted by the orchestrator (18:19Z): a content-free canary, incident metadata under the harvest route, a fixed flight-time rule, builder acceptance before the freeze, two independent harvest jobs, and a totals-only weekly log. Items marked **orchestrator position, presented to the owner 12 Nov, no objection** are not owner decisions until the owner confirms them. Open items are marked **[OPEN]**. The live list is the "Open items" table at the end.

## 0. Why a new cohort
The A1 hold-out parts are sealed for labels, perimeters and growth. But per-incident survey timing was readable by every session before the split, and the cohort's own membership rules used discovery date and the survey window (ACCESS_CONTROL, combined amendment). GOFER/H fires had aggregate labels and final sizes inspected. A replication that can be called clean needs fires about which **no session has read anything, not even metadata**, until the predictors and the scorer are frozen.

**The replication differs from A1 part c in two things: cleanliness and the label pipeline.** It keeps the same criteria and the same candidates, and the same IR interpretation as the labels.
- **The difference in labels:** part c's labels went through the Magstadt compilation, with its time conversion, estimated times and ≥ 3-collection-day selection. CR1's labels come from the in-season harvest of the IR deliveries, built by the custodian's frozen builder, with free-text flight times flagged as estimated or missing and no compilation-stage selection. Harvested deliveries may also be **dissolved products that drop unburned interior islands** (Dixie August 2021 KMZ), which part c's labels keep (§2, harvest-route item 4).
- **What this means:** a different result could come from either difference. The compiled-release cross-check (§2), where it exists, is the only within-study measure of the pipeline effect. Otherwise the pipeline difference is reported as a limitation.

## Decisions and proposed dates
- **N_target = 90 analysable fires: OWNER DECISION, 12 Nov 2026.** This is the §5 rule (power ≥ 0.80 at half the R effect).
  - Achieved power at N = 90: about **0.87 at half the R effect**, and about 1.0 at the R effect.
  - These figures are rough, because only 6 R fires are resampled (§7).
- **Orchestrator positions, presented to the owner 12 Nov, no objection (not yet confirmed):**
  - extension once, by one season, Tier 2 only;
  - a separately frozen new-candidate set, reported apart as "not a replication";
  - CR1 freezes before A1 part c is opened;
  - FEDS as a descriptive, non-pooled stratum.
- **Scope: OWNER DECISION, 12 Nov 2026 (relayed by the orchestrator; ledger row 48).**
  - **No 2026 fire is in any CR1 tier.** US 2026 stays reserved for `forecast/documents/preregistration_blind_test.md`.
  - **Tier 2 (THE confirmation) starts 2027-01-01**, not at the freeze. This removes any overlap with late-2026 fires.
  - **Tier 2, from 2027-01-01, is the only confirmation.**
- **Tier 1: orchestrator position, owner informed, no objection (12 Nov).**
  - Tier 1 is **optional**, covers **2025 only**, and is **descriptive**. It is **never called a replication**.
  - Every 2025 fire that is named in any session's transcript or committed text (research-scout included), or fetched by any session, goes to the **"exposed" stratum**.
  - **No session can declare ignorance of 2025 fires.** They are public events that a model may know from general training knowledge, and no declaration or audit can rule that out. This is why Tier 1 cannot confirm.
  - If Tier 1 runs, `firecast-lab/SPLITS.json` `fresh_holdout` is merged or superseded by name here before the freeze.
- **Dates.** Tier 1 dates are relative to the freeze date F, which is set by A1 stage 2 and is before part c opens.

| tier | discovery window | snapshot ("data as of") | closing |
|---|---|---|---|
| Tier 1, 2025 only, optional and descriptive | 2024-12-18 to 2025-12-31 | F + 14 days | F + 60 days |
| Tier 2, prospective (THE confirmation) | **2027-01-01** to 2027-12-31 | 2028-01-31 | 2028-03-31 |
| Tier 2 extension (once, if < 90 analysable at closing) | 2028-01-01 to 2028-12-31 | 2029-01-31 | 2029-03-31 |

The snapshot and closing dates were recomputed for the 2027-01-01 start. They are unchanged, because the 2027 window still ends 2027-12-31 and the extension is still the 2028 season.

- **Why these dates.** NIFC IR lags about a day and Open-Meteo about 5 days. The 31 Jan snapshot leaves a month for late uploads and revisions. The closing date leaves the custodian two months to build inputs and score.
- **The NIROPS-type series builder.** Daniel may write and rehearse it now, on **exposed 2020–24 fires only**. There is no CR1 listing or fetch before the freeze.

## Timing, detail (provisional)
- **Tier 1 (optional; 2025 only; descriptive).** It runs **only if** the NIFC FTP still holds 2025 (unverified).
  - Expect about 200–300 incidents (Daniel). Listing, building and scoring take about 1–2 weeks after the freeze, and the custodian's covariate and weather fetch is the main cost.
  - Its weakness: these fires are public events. The declaration in §1 narrows this but cannot close it.
- **Tier 2 (prospective, THE confirmation).** Its first fires are in summer 2027.
  - The 2027 season is about 100–170 incidents, so N = 90 is plausibly reached in that one season.
  - The decision comes at closing, 2028-03-31. The extension season is a fallback.

## 1. Principles
1. **Nothing is read before the freeze except salted ID hashes.** Non-custodian sessions never see a raw incident ID, because IDs can carry names and dates.
2. **Custody by role, not by session (B1, B4).** Cloud sessions are ephemeral, and Tier 2 runs into 2028–29, so custody is defined by role:
   - **Custodian:** a session **started by the owner**, which has read no CR1 byte and had no forecast-side role, and which is **named in an amendment before it acts**. It reads CR1 bytes after the freeze, under rules 4–7. First holder: Hannah.
   - **Second custodian:** another session under the same conditions and bound by the same rules 4–7. It receives the **encrypted sealed-input bundle** and independently reruns the frozen scorer. The two hashes of the released statistics must match. First holder: Nora.
   - **No other session** reads any CR1 byte beyond the hashed ID list.
   - **Hand-over.** The departing custodian commits a log line (time, last state-file hash, bundle hash). The incoming custodian signs the §1.4 declaration and is named by amendment before acting. The same procedure applies after a restart that loses the session.
   - **Transfer between custodians** happens only via the encrypted bundle plus its sha256, logged by both. It never goes through git or messages.
3. **Complete rules, written first.** Every rule that touches a CR1 fire's data, however mechanical, names its fields here. Nothing outside these lists is read for any purpose.
4. **Outside-repository declaration.** Before the ID listing, and again before the decision, every session signs a declaration in `clean_replication/DECLARATIONS.md`. It states that the session has not looked up, searched for or read anything about any fire in the cohort's source and window **outside the repository**: news, agency pages, other datasets or search engines. A positive declaration excludes the named fires, and the count is reported.
5. **Every access is logged** with who, when, sha and count, and **no raw IDs**. The required log lines:
   - salt generation (commitment hash, storage location);
   - reader rehearsal (input-list hash, output hash, test result);
   - each FTP listing request (URL template, time, response sha);
   - each per-fire raw download (id_hash, bytes sha);
   - the builder's QA decision per fire (id_hash, E-code, reason code);
   - the covariate and weather fetch per fire (call count, quota day);
   - custodian environment host changes;
   - every custodian session start, restart and hand-over;
   - the transfer to the second custodian (bundle sha);
   - the stopping point (walked count, time);
   - the release of statistics (both hashes);
   - the decision record.
6. **Leak rule.**
   - If a fire is read outside the protocol, by an unlogged read or a positive declaration, it moves to a named **"exposed" stratum**. That stratum is reported separately and never counted toward N.
   - **A custodian leak** (printing a raw name, or posting a per-fire value) does the same: the fire moves to "exposed", and the incident is logged.
   - One leak therefore does not void the cohort.
7. **Raw names never enter a transcript.**
   - The reader writes the map to a file, and the custodian never displays it.
   - Tracebacks are redacted: exceptions never carry a raw name (KeyError, path errors), and a test covers this.
8. **No 2026+ US fire access before the Tier-2 listing.**
   - From this draft on, no session fetches, lists or reads any source of 2026-or-later US fires before the CR1 Tier-2 listing. The only exception is the custodian, under this protocol.
   - The sources covered include NIFC/NIROPS FTP folders and nightly deliveries, FEDS NRT, WFIGS, ICS-209, FIRMS US and news.
   - **Prior 2026 exposure, recorded.** Sofia opened 32 public 2026 NIROPS nightly deliveries before this rule. Her 2026 material is **frozen in place**: kept as it is, not extended, and not copied further (ledger row 46: the exposed set by hash, and receipts). Two 2026 incident names and one flight comment from it reached one other session's transcript (Victor, Q7; rows 43 and 45), and nothing was repeated or committed. A1 addendum §7 uses only the aggregate finding (no coverage field; estimated times). This is one reason 2026 is excluded from CR1.

## 2. Source, window and tiers

**Tier-1 scope: conflicts with two earlier registrations (Hannah's B5 result, ledger row 43). The owner's decision is recorded under "Decisions" above.**
- **US 2026** is reserved by `forecast/documents/preregistration_blind_test.md` (owner, 2026-10-30). Any access before the owner's OSF registration of that test would block the test.
- **US 2025** is earmarked by `firecast-lab/SPLITS.json` `fresh_holdout` (`us_2025_membership_rule`, pending).
- **Decided (owner, 12 Nov):**
  - The blind test keeps US 2026, and no CR1 tier contains a 2026 fire.
  - Tier 2 starts 2027-01-01.
  - Tier 1 is optional, 2025 only and descriptive (see "Decisions"). If it runs, `fresh_holdout` is merged or superseded by name here before the freeze.

**Availability (Daniel, 2026-11-12 15:11Z; from documentation and his own manifests, nothing fetched; items marked (u) are unverified).**

| source | latest held by any session | 2025+ available? | ID-only listing | covariates (US pipeline) |
|---|---|---|---|---|
| **NIROPS / NIFC IR** (primary) | 2024-12-17 (Magstadt archive) | **yes**: nightly IR perimeters on the public NIFC FTP (`incident_specific_data/<GACC>/<year>_<fire>/IR`), lag about 1 day; FTP retention of past years (u) | a directory listing of fire folders, **names only** | yes: CONUS, Open-Meteo lag about 5 d, about 12.5 calls per fire |
| FEDS | 2024 held; the archive lists 2012–2025 | yes: NRT OGC API (12-hourly), Zenodo 2025; 2026 (u) | fireID property only (u; `t` must be excluded) | yes (CONUS) |
| WFIGS | not held as a cohort | yes, but one final or current perimeter, no progression | outFields=IrwinID,IncidentName, no geometry | yes |
| CWFIS / NBAC, EFFIS, Australia | not held | yes (final polygons or daily hotspot perimeters) | an attribute table by ID | **no**: new grid and fuel sources needed |
| Korea | **2025 already exposed** (FIRMS KR2025, Choi rasters, AHI, KFS to 2025-11-10) | FIRMS NRT only | – | own EPSG:5179 path |

**Consequences fixed here.**
- **The primary is NIROPS/NIFC IR, 2025 and later.** It is the same product family as the Magstadt archive that A1 uses.
- Folder names are fire names, so the listing is run by the custodian and only salted hashes leave it (§3).
- Building a Magstadt-equivalent perimeter series from the raw FTP files is **new engineering**. It is written by Daniel, rehearsed on exposed 2020–24 fires (the output must match the Magstadt archive), frozen by SHA, and run by the custodian.
- Korea is excluded: 2025 is exposed.
- Canada, the EU and Australia are not feasible without new fuel sources; they are not declared.
- **FEDS is a descriptive, non-pooled stratum** (orchestrator position, presented to the owner 12 Nov, no objection). It follows the same protocol, with its own ID-only reader.
- **Expected volume (Daniel, 15:20Z, from the Magstadt base rate; no 2025+ data seen).**
  - Non-project incidents per year ran from 101 to 171 in 2020–24.
  - **Tier 1, if run** (2025 only): the 2025 share of Daniel's 200–300 estimate for 2025 plus 2026 (not split by year). It is descriptive and never counts toward N.
  - **Tier 2** (prospective, from 2027-01-01): the 2027 season is about 100–170.
  - CR1 has no survey-count threshold, and no part-a incident failed the ≥ 1 interval ≤ 48 h rule (Marcus). So **N_target = 90 is plausibly reachable from Tier 2 in the single 2027 season**, after QA losses and E6.
  - These are ranges. Real counts exist only after the custodian's run.
  - No CR1 count is taken before the freeze.
- **Reader details (agreed with Daniel).**
  - The reader emits `id_hash` as defined in §3.1. The salt comes only from an environment variable the custodian sets.
  - It emits **no GACC or year column**, because the split fields are `source` and `id_hash` only. The tier comes from Hannah's post-freeze reading.
  - The raw-to-hash map is written only to a path Hannah names. Tests assert that no raw name appears in stdout, stderr or any output.
- **Builder gaps (Daniel).**
  - The Magstadt-equivalent builder must emit the NIROPS schema (`Incident_C`, `UTC`, geometry), so that the frozen `rebuild_env.sh` runs unchanged on an allowlist. That pipeline ran 490 incidents unattended with 0 failures.
  - Raw FTP folders are messier: inconsistent names, and HeatPerimeter, IntenseHeat and ScatteredHeat layers. The builder's QA rules are frozen with it.
  - Weather is limited by the 10k/day quota, so a tier spans days and needs a resumable re-run.
  - `rebuild_env.sh` gets a `--quiet-ids` mode that logs only salted hashes.
- **Custodian environment.** It is a dedicated environment, and the hash of its allowed-host list is in the freeze, so a host change after the freeze is visible. It needs these hosts: Copernicus DEM S3, zenodo.org, the LANDFIRE host, the Open-Meteo archive, PyPI and the NIFC FTP. They are set up before the freeze and appear in the access log.
- **FTP retention of 2025 is unverified.** If 2025 is gone, Tier 1 is empty. Tier 2 is unaffected.

- **Primary product: NIROPS-type IR perimeters**, the same label type as R and A1 part c.
  - If NIROPS yields too few fires, the fallback is a **longer window**, never another product.
  - **Access status (ledger row 49).** The documented NIFC FTP layouts for 2020–24 are **not served today**: all 504 constructed URLs, and a documented GACC-year folder, returned 404. Documentation records a 2022 purge notice and an unconfirmed move from /public to /protected.
    - **Both documented roots and all documented layouts were tried.** Finder v3 (ledger row 49) covered both roots, including `incident_specific_data/<region>/{y}_Incidents_<State>/` and `Z_{y}_HISTORIC/…`: 504 URLs, 0 found. Finder v3.1 in years mode (row 51) tried 980 year-folder URLs for 2015–2024 under both roots, and none answered. **Past seasons are not served.** The builder's rehearsal on exposed fires therefore uses IR files **already held**, for example Zenodo 15492982 (Dixie 2021, KMZ-derived, no flight times). Its acceptance criteria are stated for what those files can test.
    - **2027 retrieval paths are unverified** until the custodian's Tier-2 listing.
    - **Fixed at the freeze, so no choice is left for afterwards (Hannah, 16:01Z):**
      - **Product:** NIROPS-type NIFC IR perimeters.
      - **Access attempt:** at the Tier-2 snapshot (2028-01-31), the custodian first tries the frozen root and template list. It then tries any NIFC-announced successor location for the same product, identified from NIFC documentation. Every attempt is logged.
      - **Outcome rule:** if no 2027 IR deliveries are retrievable by the closing date (2028-03-31), Tier 2 is reported as **"source unavailable; no confirmation"**. The frozen extension is taken only if the product reappears for 2028. **There is never a product switch.** FEDS and other products stay separate descriptive strata, as already declared.
    - **Freeze gate on access (orchestrator ruling, 16:02Z): a DOCUMENTED route identified.**
      - CR1 does not freeze until a route to 2027 NIROPS-type IR deliveries is identified **from documentation only**, with no fire data read, and recorded here. The method, any credential holder and the permitted users are written down.
      - Acceptable sources: the owner's browser check of the ftp.wildfire.gov notices and the terms for /protected; or Daniel's answer, from documentation and the ACCESS_LOG only, on the publisher of the compiled release that supplied A1's 2020–24 NIROPS data.
      - Retrieval itself is not verified before the freeze, because that would break §1 item 8. The outcome rule above covers failure.
      - **Documentation finding (owner's browser check, relayed by the orchestrator 16:07Z):**
        - The ftp.wildfire.gov front page says: "As of May 4 all folders under the Authenticated Access area require authentication via FAMAuth… `https://ftp.wildfire.gov/public/incident_specific_data` changed to `https://ftp.wildfire.gov/protected/incident_specific_data`… The path for the Incident Specific Maps folder has not changed."
        - The Authenticated Access area lists Incident Specific Data, Base Information, NIROPS Information, Predictive Services Information and National BAER Information.
        - Access needs a FAMAuth account plus approval by a GACC representative or Authorizing Official, for interagency users.
        - The site calls itself "short-term interagency sharing, not a file archive", with "not much data that carries over from season to season".
        - This explains finder rows 49 and 51; it was not a client-identity problem.
      - **Consequence:** the raw NIFC FTP is **not a public route** for 2027 IR. **No session attempts /protected or requests an account.**
      - **Recorded route: decided by the owner on 12 Nov, the in-season harvest (d'), see OWNER DECISION below.** For the record, the candidates that were considered and what each means for "the same label type as R and part c":

| option | route | label type vs R and part c | implications |
|---|---|---|---|
| **(a)** | A **public compiled release** of NIROPS-type perimeters: the compilation behind A1's 2020–24 data (Magstadt et al., Mendeley 10.17632/95rj5d379g), **if** it has yearly editions | **Same.** It is the source of R's and part c's labels, with the same interpreters' IR perimeters and the same compilation steps | Depends on the publisher issuing a 2027 edition, and on its release lag against the 2028-03-31 closing (the extension covers one season of lag at most). To be checked **from documentation only** (Daniel): who publishes it, whether yearly editions exist, the licence, and the release cadence. If an edition comes after closing, the outcome rule gives "source unavailable; no confirmation" |
| **(b)** | A **formal data request** by the owner to NIFC/NIROPS or to the compilation's authors, for 2027 IR perimeters with flight times | **Same**, if the delivered files are the interpreters' IR products | The request terms (who receives, the custodian, no worker access) must fit §3 custody. It is a human, owner-level step and its outcome is uncertain. The request and any agreement are recorded before the freeze, and the data are received by the custodian only |
| **(c)** | A **different public product** (for example FEDS, or WFIGS interagency perimeters) | **Different.** Not NIROPS-type IR | This is a **product switch** and needs the owner's decision **before** the freeze. "Same label type as R and part c" would then not hold, so CR1 would replicate across a label change. The §2 rule "never another product" would be rewritten before the freeze, never after |
| **(d)** (now the recommended primary route; see (d') and RECOMMENDED below) | The **public Incident Specific Maps** folder, whose path the site says has not changed. It holds nightly IR map deliveries | **Partly the same.** The geometry derives from the same IR interpretation (the Dixie KMZ rehearsal had median IoU 0.9993 against the archive), but flight times appear only in free text and coverage footprints are absent (A1 §7) | The site is "not a file archive", so the data would have to be harvested **during the 2027 season** by the custodian, ID-only and sealed, not at the 2028 snapshot. That changes the access protocol. Any check of the folder's current contents would touch 2026 and is forbidden (§1 item 8); only documentation and Sofia's recorded aggregate (row 46, under verification) may be used |

      - **Update (orchestrator, 16:09Z, from Sofia's raw-transcript extraction):**
        - Nothing under `/public/incident_specific_data/` returned 200 for Sofia either. Her 32 delivery zips (ShapeFileOutputs with Heat_Perimeter layers) all came from the **still-public** `https://ftp.wildfire.gov/public/incident_specific_maps/<region>/<year or YYYY_Incidents_<State>>/<INC>/IR/<date>/`.
        - So a **public, documented path carrying NIROPS-type IR shapefile deliveries exists for the current season**. Option (d) is therefore the leading candidate. It is drafted below as the **proposed route**, pending Hannah's judgement on the no-look rule and the owner's confirmation.
        - **Stated (Hannah, 16:12Z):** finder v3 (row 49) and v3.1 (row 51) both used the roots `incident_specific_data` **and** `incident_specific_maps`, with the layouts Sofia found for 2026 (`<region>/{y}/` and `<region>/{y}_Incidents_<State>/`) plus the Z_ and historic variants, for all 7 GACCs. Every 2015–2024 year folder under both roots returned 404. **The public Maps tree serves only the current season.** A 2027 delivery must therefore be harvested while 2027 is the current season.
      - **Proposed route (d'): custodian in-season HARVEST of the public Incident Specific Maps IR deliveries.** This is not frozen. It is the change the orchestrator asked to have drafted.
        1. **Why in-season.** The site is "short-term interagency sharing, not a file archive". A single listing at the 2028-01-31 snapshot could find nothing, so deliveries are copied while they are posted.
        2. **Who.** The custodian (§1.2) only, in the dedicated custodian environment (§3). No worker session lists, fetches or reads the folder from this draft on (§1 item 8 covers it).
        3. **What runs.** A frozen harvester. Its code sha is in the freeze, and it is rehearsed before the freeze on a **synthetic fixture only**, because the real path's 2026 content must not be touched. On each run it:
           - lists `incident_specific_maps/<region>/<2027 or 2027_Incidents_<State>>/<INC>/IR/<date>/` for every region on a frozen region list;
           - downloads every file in any **new** `IR/<date>/` folder, together with the ShapeFileOutputs zips and their companions;
           - writes each file straight into the encrypted sealed store;
           - logs only the run time, HTTP status counts, file counts, the sha256 of each file, and `id_hash` = HMAC(salt, "NIFC_MAPS|" + canonical_id).
           - It never prints or logs names, paths, attributes or file contents, and tracebacks are redacted (§1 item 7).
        4. **Schedule (frozen).** Once a day at a fixed UTC time, from 2027-01-01 to 2027-12-31, then weekly until 2028-01-31 to catch late deliveries for 2027 fires.
           - A missed run is logged and never back-filled from another source. Deliveries removed before a run caught them are lost.
           - The harvest log (hashes only) is committed weekly, so its completeness can be audited without content.
        5. **Scope filter.** Only `2027` / `2027_Incidents_*` year folders are listed. The 2026 folders are never opened, and a test checks this.
        6. **After closing.** The custodian builds labels from the sealed harvest exactly as in §5 and §6. The discovery-window and eligibility rules are applied then, and scoring is unchanged.
           - Flight times are parsed from the delivery comments by the frozen builder rule, which carries its own estimated/missing flag (A1 §7).
           - `canonical_id` = `<region>/<year>_<INC>`, taken from the leaf incident folder (§3).
        7. **New attrition category E7: delivery not harvested.** This applies to a 2027 incident whose deliveries were removed before any harvest run, or were only partly harvested, leaving no scorable interval. It is counted and reported, and never replaced.
        8. **Failure outcome unchanged.** If the harvest yields no 2027 IR deliveries by closing (2028-03-31), Tier 2 is reported as "source unavailable; no confirmation".
        9. **Infrastructure (owner/orchestrator).** A scheduled custodian job that survives session ends for a year, the sealed store, and alerting on missed runs. These must exist **before 2027-01-01**. Otherwise the harvest starts late, the late start is logged, and fires discovered before it are E7.
      - **No-look conditions for (d') (Hannah, 16:12Z). With these, (d') is acceptable to her as the documented route:**
        - **a. Unattended.** Only the custodian role runs the harvest, under §1, as an **unattended scheduled job**, not interactive tool calls, so folder names never enter any session transcript. The harvester writes only hashes, counts and status codes to stdout and logs. A test asserts that no name appears in its output, including on exceptions.
        - **b. Listing in memory, 2027 only.** Listing pages are parsed **in memory only**, as hrefs, with no text, sizes or mtimes, as in the finder. Only `<region>/2027…/` paths are touched, plus `2028…` for the extension. A test checks that 2026, or any other year, is refused **before** any request.
        - **c. No unpacking in season.** Downloads go straight into the encrypted sealed store. Nothing is unzipped or parsed during the season, and building waits for the snapshot.
        - **d. Hashes at harvest.** `canonical_id` and the HMAC are computed at harvest. The **detailed** log (HMACs, file sha256s, byte counts, HTTP status counts) stays in the sealed store. The **weekly committed log holds totals only**, plus the sha256 of the sealed detailed log at that moment (adopted 18:19Z; this replaces the earlier per-file weekly log). It has no folder names and no dates finer than the week.
        - **e. 13 months of custody continuity.**
          - The scheduled job runs under an owner-held identity and environment, with the salt and key as owner secrets.
          - Every session start or hand-over of the custodian role is logged (§1.5).
          - A missed day is logged as a gap and never back-filled from other sources.
        - **f. Failure handling.**
          - A delivery that 404s before it is harvested is E7, never replaced.
          - A site layout change mid-season is logged and **fails closed**.
          - Any fix to the harvester after the freeze is a logged amendment that cannot change which deliveries count.
        - **g. Fixture-only rehearsal.** The harvester is rehearsed on the synthetic fixture only. It is **never run against the live site before 2027-01-01**, and its first live request is a 2027 path.
      - **Harvest-route requirements (Iris's assessment, adopted by the orchestrator 18:19Z).** Items 1 to 4 are **MUST before the freeze**, and items 5 and 6 are adopted.
        1. **Content-free canary.**
           - On every run and for each region, the harvester records **two counts only**: the number of year-level entries listed, and the number of those matching the frozen 2027 (or 2028) year patterns.
           - **Alert A (layout drift):** a region has year-level entries but none match. **Alert B (silent failure):** nothing at all has been harvested by **2027-06-30**, the start of the western fire season.
           - Alerts carry **counts only**.
           - **Rule when a canary fires:** the custodian may look at **year-level folder names only** (for example a new `2027_…` spelling), **never incident names**.
           - The layout or pattern list is changed **only by a logged amendment** that states the old and new patterns. Deliveries already lost before the fix are E7.
        2. **Incident metadata under the harvest route (origin, discovery date, IRWIN ID).**
           - **Source and fields (Daniel, 18:22Z, from documentation and the existing `data-fetch/incident_metadata_join.py`; no records fetched):** the NIFC feature service `WFIGS_Incident_Locations/FeatureServer/0`.
             - **IRWIN ID:** `IrwinID`, a braced GUID.
             - **Discovery date-time:** `FireDiscoveryDateTime`, epoch milliseconds in UTC.
             - **Point of origin:** the feature's point geometry, with outSR = 4326 (x = lon, y = lat). This is not `InitialLatitude`/`InitialLongitude`, which is the initially reported location.
             - **Also used for the key match:** `UniqueFireIdentifier`.
           - **Who and when:** the custodian fetches them **once, at the snapshot (2028-01-31)**. It is filtered in memory to the IRWIN IDs found in the harvested deliveries, and lands in the sealed store. No worker sees it.
           - **IR deliveries carry no IRWIN ID** (Daniel: the delivery attribute tables and the Dixie KMZ have none; the Magstadt compilation added it by joining an IROC export). The match is therefore made in this fixed order, applied by the custodian at the snapshot:
             1. **Key match (proposed, for Hannah and Iris):** the incident number in the leaf delivery folder, normalised by a frozen rule, is matched to `UniqueFireIdentifier`. It is accepted only if exactly one record matches.
             2. **Space-time match:** a unique WFIGS record whose point of origin lies within B = 4 km of the first harvested perimeter, and whose `FireDiscoveryDateTime` is within 3 days before that perimeter's flight time.
             3. Otherwise the incident is **E8: no incident metadata**. It is counted, reported and never replaced.
             - **Fixed note:** this matching is a rule, not a choice, and it is applied before any score exists.
        3. **Flight-time rule (fixed now).**
           - **Source:** the time is parsed from the delivery's free-text comment by the frozen builder rule, converted to UTC with the frozen per-region time-zone table.
           - **Midnight rule:** a parsed local time of 12:00 or later is assigned to the day **before** the delivery folder date. An earlier time is assigned to the folder date itself. This follows the night-flight, morning-delivery pattern in A1 §7.
           - **Missing or unparseable text:** t = the delivery folder date at 00:00 local, flagged **ESTIMATED**.
           - **Δ rule:** an interval with an estimated endpoint **counts** under 0 < Δ ≤ 48 h using those times. This is the primary rule.
           - **Pre-stated secondary:** the same analysis with every interval having an ESTIMATED endpoint dropped. It is reported beside the primary, with no decision role.
           - **Caveat:** this rule is untested on real free text until after the closing date (see the synthetic-fixture limits).
        4. **Builder acceptance (Daniel, 18:22Z; daniel/data-fetch-3 76ec1daf, `ir_builder/README.md`). Done; recorded as PARTIAL.**
           - **Criteria:**
             - geometry: IoU ≥ 0.99 and |area error| ≤ 0.5% per survey, against interpreter-shapefile references;
             - time, where testable: equal to the minute under the fixed rule in item 3. ESTIMATED surveys are reported separately and are excluded from the time criterion.
           - **The 13 of 37 failing Dixie nights (31 Jul to 30 Aug 2021) are EXPLAINED, not fitted.** The diagnosis (`diag_dixie_holes.py`, `DIAG_DIXIE_HOLES.txt`) was done after the run.
             - The built perimeter is **larger**: 3.6–70.9 km² built-only, against ≤ 1.5 km² archive-only. This corrects an earlier "smaller".
             - The extra area is exactly the archive's **interior holes** (unburned islands). The August KMZ "HeatPerimeterDissolved" layers keep 1–5 interior rings, while the archive has 5–14.
             - With interior rings removed on both sides, IoU is ≥ 0.9994 on all 37 nights.
             - So the cause is the input product's dissolve, not the builder. Acceptance test 2 stays **PARTIAL (24/37)**, with no criterion or rule changed after the run.
             - Expected to pass on interpreter shapefiles, which carry the islands, but **untested**: none are reachable.
           - **Consequence for CR1 labels (added to the §0 pipeline difference).** If the 2027 harvested deliveries are dissolved products like the August KMZ, unburned islands inside the perimeter would be labelled burned. Part c's compiled labels keep them. This is a concrete label-pipeline difference, mostly affecting interior cells.
             - Whether 2027 deliveries keep the islands cannot be known before harvest. The builder reports the interior-ring count per survey, and the result states the share of dissolved-type surveys.
        5. **Two independent harvest jobs (adopted).**
           - One job is run by the custodian and one by the second custodian (Nora), in **different environments**, at **different fixed UTC times** (for example about 06 and about 18 UTC).
           - The sealed store keeps the **union of files by sha256**.
           - Each job's detailed log is kept separately, so a delivery caught by only one job is visible in the counts.
        6. **Weekly log and smaller items (adopted).**
           - The weekly committed log holds totals only, plus the sha256 of the sealed detailed log (see d).
           - It also carries the weekly **distribution of E7 counts and gap days**.
           - All alerts carry counts only.
           - Stale header and open-items rows are refreshed in this draft.
        7. **OWNER DECISION PENDING (morning):** may the custodian **alone** use Sofia's 32 frozen 2026 deliveries **offline** to rehearse time parsing, given they are already exposed (row 46)?
           - If yes, the rehearsal result is committed as counts only, and those deliveries stay excluded from every tier.
           - If no, time parsing stays untested until after the closing date.
        8. **OWNER DECISION PENDING (morning):** the owner checks the site's terms of use for a daily automated listing and download, two jobs a day.
           - If the terms forbid it, the harvest route is reconsidered **before** the freeze.

      - **OWNER DECISION, 12 Nov 2026 (relayed by the orchestrator 16:31Z): in-season collection of 2027 fire data is APPROVED** ("feel free to collect fire data in season"). **Recorded route:** the primary source is the custodian in-season harvest (d') of the public Incident Specific Maps IR deliveries during 2027. A compiled release, if one exists, is a same-fire cross-check only. Nothing is fetched now, 2026 stays untouched, and the first harvest run is not before 2027-01-01.
      - **Design of the route (orchestrator position 16:10Z, now adopted by the owner's decision). Not frozen:**
        - **Why (a) cannot be primary (Daniel, 16:09Z; documentation only, nothing fetched):**
          - Mendeley Data 10.17632/95rj5d379g is **v1 only**, published 2026-06-02 and covering 2020–2024, under CC BY 4.0.
          - No editions, cadence or maintainer are documented. The only update route is the authors' FTP harvest script, whose paths are now behind FAMAuth.
          - v1 came about 18 months after the 2024 season.
          - Some acquisition times were estimated without a flag. Scope: USFS Regions 1–6, ≥ 3 collection days.
          - So a 2027 edition by 2028-03-31 is unlikely.
        - **PRIMARY: (d'), the custodian in-season harvest** of the public Incident Specific Maps IR deliveries during 2027, as specified above: a frozen script, hash-logged, written to the sealed store and left unopened.
          - After closing, the deliveries are built into perimeter series with **Daniel's frozen builder**.
          - **The builder's status, stated plainly:** so far it has been rehearsed **geometry-only**, on one exposed fire (Dixie 2021: 24 of 37 nights pass both shape criteria, all failures in August 2021, and the survey-time criterion untested). Flight times come from free text in the deliveries, and there are no coverage footprints.
        - **SECONDARY: a compiled release**, if one covering 2027 appears by the closing date. It is scored **as a cross-check on the same fires**, by a rule fixed now:
          - the same frozen candidates;
          - only fires present in both sources;
          - reported as "compiled-label cross-check";
          - it never replaces the primary result and is never pooled with it.
        - **In parallel: (b) the owner's formal data request.** Any files it delivers are handled exactly like a compiled release: secondary cross-check only, unless the owner changes the primary **before** the freeze.
        - **Last: (c), a product switch**, by the owner's decision before the freeze.
        - **What this does to the label type, and to §0's claim.**
          - The primary label becomes **"NIROPS-type deliveries, harvested"**: the same IR interpretation as R and part c, but not identical to their **compiled** labels. Part c's labels went through the Magstadt compilation (time conversion, estimated times, ≥ 3-day selection). CR1's go through the custodian's builder (free-text times with an estimated/missing flag, no compilation-stage selection).
          - §0's sentence "differs from A1 part c in one thing only: cleanliness" therefore **no longer holds exactly**. CR1 differs in cleanliness **and in the label pipeline** (compiled vs harvested and built).
          - A different result could come from either. The secondary cross-check, where it exists, is the only within-study measure of the pipeline effect. Otherwise the pipeline difference is reported as a limitation.
          - §0 has been reworded accordingly (owner decision 12 Nov).
        - **What the synthetic fixture can and cannot establish** (no real dual-path fire is retrievable: rows 49 and 51).
          - *Can:*
            - that `canonical_id` stripping maps the current-path and archive-path forms of the frozen layouts (`Z_<y>_HISTORIC`, `Historic_archived NIROPS/<y>_fires/`, `GACC_Incidents/<y>/`, and the Maps `<region>/<year or YYYY_Incidents_<State>>/<INC>/IR/<date>/`) to one hash;
            - that the reader and harvester write nothing but hashes, and redact tracebacks;
            - that the 2026 folders are never opened;
            - that the builder's code paths run end to end on files with the documented structure.
          - *Cannot:*
            - whether real 2027 folders use these layouts;
            - whether real archive moves preserve leaf names;
            - whether the builder's time parsing is correct on real free-text comments;
            - whether harvested perimeters match the interpreters' intent (the full acceptance test).
          - These remain **untested until after closing**, and the result states this.
        - **What the owner must provide:**
          - a custodian session and environment that exist **through the 2027 season**, with a scheduled daily harvest job and missed-run alerting, running before 2027-01-01;
          - the owner-held secrets: the salt and the sealed-store encryption key;
          - the custodian's network allowlist, including `ftp.wildfire.gov`, whose hash goes in the freeze.
      - **Open for this route:**
        - Hannah's no-look judgement: **given**, with conditions a–g above (16:12Z).
        - The owner's confirmation.
        - Who operates the year-long scheduled job.
      - Options (a) to (c) stay recorded as alternatives. (a) and (b) remain useful as cross-checks on harvest completeness, but are never pooled. The chosen route is recorded here by commit and sha before the freeze.
  - Other perimeter products (FEDS, WFIGS, CWFIS and others) may be declared here as **separate descriptive strata**. They are never pooled.
- **Two tiers, declared now and never pooled:**
  - **Tier 1 (only if kept), 2025 only, descriptive: "not a confirmation".** Fires discovered from the latest date held through 2025-12-31. 2026 is excluded by the owner's decision.
    - **"Latest date held" is a pre-freeze task with a recorded result (B5).** The custodian checks every committed and scratch file the sessions hold for any 2025+ US fire, and logs the result. The sources include NIROPS, the FEDS archive listing, the WFIGS/ICS-209 joins, FIRMS US2024, WSTS 2018–21 and GOFER 2019–21.
    - The Tier-1 window start (2024-12-18) is set from that result (B5 done: ledger rows 43 and 45).
    - *Stated weakness, and why Tier 1 is descriptive:* these are public events. A session could know of them from transcripts, committed text (for example the 2025 US names in research-scout) or general model knowledge. Every fire named in any transcript or committed text goes to "exposed". The general-knowledge route cannot be audited.
  - **Tier 2, prospective.** Fires discovered on or after **2027-01-01**, after this document's freeze commit and after the 2026 season the blind test reserves. This is the only tier clean against every route, and it is the one called **the confirmation**.
    - It may mean waiting for the next season, and that is stated plainly.
- **Listing runs once per tier.**
  - Tier 1 is listed after the freeze, at its snapshot.
  - Tier 2 fires do not exist at the freeze, so **the freeze comes first** and Tier 2 is listed at its own snapshot.
- **Weather product.** The frozen rebuild script uses the **same weather and covariate products as the A1 training data**. If a product lags a tier's snapshot, that tier waits for it, up to its closing date. Fires still lacking the product then are E3.
- **Snapshot and closing.** A **closing date** and a **"data as of" snapshot date** for each tier are fixed here (see the table at the top). The version of a revised product that counts is the one present at the snapshot.

## 3. Access protocol, from the first byte
1. **ID listing.**
   - Daniel **writes** the ID-only reader. The custodian reviews it and **runs** it: whoever runs it has raw identifiers in their process.
   - It runs once per tier, rehearsed first on an already-exposed source list to prove that nothing but the hash is written.
   - It discards every other attribute **in memory before any print or write**, and tests cover this, including redacted tracebacks.
   - **Hash, one definition (B3):** `id_hash = HMAC-SHA256(salt, source + "|" + canonical_id)`.
     - The salt is **256-bit random**.
     - For the NIFC FTP, `canonical_id` is `<GACC code>/<year>_<fire>`, taken from the **leaf incident folder**, not the full path. This matters because GACCs move old seasons into archive folders (`firecast-lab/docs/FRESH_HOLDOUT.md` §2.1, from web summaries), for example pacific_nw `Z_<year>_HISTORIC`, n_rockies `Historic_archived NIROPS/<year>_fires/` and great_basin `pre2015-...`. A full path would change between the Tier-1 snapshot and a later re-read or hand-over, and the same fire would hash twice.
       - **Frozen stripping rule:** keep the GACC code (the first path segment, mapped to a frozen list of GACC codes) and the leaf incident folder name. Drop every intermediate segment: archive, historic, season and year folders. If the leaf name carries no year, take the year from the nearest stripped year or season segment.
       - **Normalisation:** lower case; spaces, hyphens and underscores collapsed to `_`; trailing qualifiers kept.
       - **Rehearsal requirement:** the reader's rehearsal on exposed fires must include at least one exposed fire listed under both a current and an archived path, and must show that both give one hash.
       - **Fallback (accepted by Hannah, 15:40Z):** a synthetic fixture is used **only if** no exposed 2020–24 fire appears under both path forms in the custodian's constructed-URL run.
         - The fixture mirrors the real archive layouts: `Z_<y>_HISTORIC`, `Historic_archived NIROPS/<y>_fires/` and `GACC_Incidents/<y>/`.
         - The disclosure says which was used.
         - **Result: the synthetic fixture is used.** No dual-path fire is retrievable: rows 49 (504 URLs, 0 found) and 51 (980 year folders for 2015–2024, 0 answered), covering both roots and all documented layouts. Condition (i) is met. The disclosure records this.
     - **Renamed, merged or complex folders:** the frozen rule maps every folder that resolves to the same incident (by the IRWIN ID in its IR files, read by the custodian after the freeze) to the canonical folder with the **lowest `u`**. The others are logged as aliases.
     - Two incidents that collide on `canonical_id` are both listed and resolved by IRWIN ID after the freeze.
   - **Outputs:**
     - `CR1_IDS.csv` (`source`, `id_hash`);
     - the raw-ID→hash map, written only to the custodian's sealed store (below).
   - **Salt and map custody (B2).**
     - The salt is generated by the custodian and stored **only as a secret the owner holds**: a secret on a dedicated custodian environment, or owner-held encrypted storage.
     - Only `sha256(salt)` is committed, in `CR1_FREEZE.json`.
     - The raw-ID→hash map and **all sealed per-fire inputs and outputs** are encrypted with an owner-held key before they leave the custodian's container. They are stored outside git, in owner-controlled storage.
     - **Between Tier-1 scoring and the decision**, the sealed builds live only in that encrypted store, with the bundle sha logged.
     - Nothing sealed is in git or in messages.
   - The salt is released, and the map decrypted for the record, only after the decision is recorded.
2. **Optional pre-freeze existence flag.** If a pre-freeze filter is ever forced, the only permitted field is a binary "a perimeter product exists for this ID". It is computed by the reader, and only the filtered hash list is released: no counts, dates or sizes. Survey count is **not** permitted, because it tracks duration and therefore outcome. The listing's **folder modification times and file counts are also forbidden**, because they track duration.
3. **Split fields, complete:** `source` and `id_hash`. The order is ascending `u = sha256("S-D9-CR1|" + id_hash)`.
4. **Freeze before any further read.** `CR1_FREEZE.json` is verified by Hannah. **Order (orchestrator position, presented to the owner 12 Nov, no objection): CR1 freezes BEFORE A1 part c is opened.** It holds:
   - the predictors (A1 stage-2 candidates and comparators, by SHA);
   - the scorer (sd9bench SHA);
   - the covariate and weather rebuild script (SHA);
   - the custodian interface (SHA);
   - this document;
   - the salt commitment (`sha256(salt)`);
   - the custodian environment (the hash of its allowed-host list);
   - the builder with its frozen QA rules (HeatPerimeter, IntenseHeat and ScatteredHeat handling; SHA) and Daniel's rehearsal match statistics against Magstadt;
   - the custodian interface: **one resumable command**, with a state file of walked hashes and E-codes, so that a restarted custodian session continues exactly where it stopped.
5. **Rehearsal before the freeze.** Every candidate runs once end to end through the custodian interface on **part-a** fires, with receipts, and failed or unavailable cases are kept. A crash on CR1 is then a result, not a reason to touch code.
6. **After the freeze, the custodian only:**
   - reads metadata, perimeters and labels;
   - fetches covariates and weather with the frozen rebuild script, outputs sealed, because fetching reveals place and date;
   - applies §5;
   - runs the frozen predictors and scorer;
   - releases only the §6 statistics and attrition counts.

   The second custodian reruns the scorer, and the hashes are compared. Per-fire outputs are released only after the decision is recorded.
7. **No other session** fetches, opens or derives anything from CR1 sources until the decision is recorded.

## 4. Training data and predictors
- **Replication set.** The A1 stage-2 candidates and comparators, unchanged: no refit, no retuning. **The headline stays A1's headline.**
- **New candidates (orchestrator position, presented to the owner 12 Nov, no objection: allowed).** A separate set of new candidates may be frozen by SHA at the CR1 freeze. Each is scored and reported **apart, labelled "not a replication"**. This keeps the only clean data from being spent solely on candidates already known to fail, without amending the replication set.
- A candidate not frozen at CR1's freeze is not scored.

## 5. Eligibility, independence, analysability, stopping (custodian, post-freeze)
- **Fields the custodian reads for these rules, complete:**
   - perimeter or survey observation times and geometries (for the interval rule and labels; survey times are also used for the post-decision tercile report);
  - the IRWIN ID inside the IR files (for canonical-ID resolution, §3.1);
  - **the training fires' final perimeters** (fit-23 ∪ part a; for the same-ground rule);
  - point of origin and discovery date (for independence and the tier);
  - the covariate and weather inputs built by the frozen script.
- **Eligibility categories, fixed now:**
  - E1: no perimeter product;
  - E2: no valid interval under the A1 §2 rule (0 < Δ ≤ 48 h);
  - E3: input-build failure;
  - E4: tier mismatch (discovery date outside the tier window);
  - E5: not independent (below);
  - E6: no positive in the 4 km band (counts against analysability, not a replacement).
- **Independence.**
  - *Date:* follows from the window.
  - *Location (same ground):* a CR1 fire is excluded if its **point of origin lies inside, or within B = 4 km of, any training fire's final perimeter** (fit-23 ∪ part a).
    - B equals the A1 primary band (Hannah). It is a rule already in A1, not a new number: no scored band cell around a CR1 origin lies on ground a training fire burned.
    - This uses the training fire's outcome, never the CR1 fire's. Excluding by the CR1 fire's own final extent would select against large fires.
    - If Iris prefers another B, the reason is recorded. B is fixed before the freeze either way.
  - *Space-time proximity:* the A1 50 km / 30 days clause is empty for a cohort later than every training fire. It applies only if a CR1 window ever overlaps a training window.
  - *Duplicates:* fires within 5 km with overlapping record windows are duplicates; the lower `u` is kept.
  - Only flags and counts are released.
- **Stopping rule.**
  - The custodian walks the `u` order and evaluates eligibility fire by fire.
  - It stops at **N_target analysable fires**, or at the closing date, whichever comes first.
    - **N_target = 90** (owner decision, 12 Nov 2026). This is the smallest tabulated N giving power ≥ 0.80 at **half** the R effect (achieved about 0.87).
    - Stopping early only saves the custodian's cost, so more analysable fires are better when the cost is acceptable.
  - The stopping rule and E6 depend on **labels, never on any model output**. That mirrors A1 for comparability.
  - The **count of fires walked** before stopping is reported.
- **Underpowered outcome, fixed now.** If fewer than 20 analysable fires exist at the closing date, the result is reported as **underpowered and descriptive**. **Extension rule (orchestrator position, presented to the owner 12 Nov, no objection): extend the closing date once, by one season, for Tier 2 only** (dates in the table above). No other extension is decided afterwards.

## 6. Scoring and decision
- A1 §4–§6 apply unchanged: population, 4 km band, criteria 1–6, the whole-fire bootstrap (seed 20261030) and the secondaries.
- Tier 2 carries the confirmatory §6.1 decision. If Tier 1 runs, it is reported alongside, labelled "2025 unseen retrospective: descriptive, not a replication", and is never pooled with Tier 2.
- Also reported: results by tercile of survey span, computed by the custodian after the decision.
- **All-eligible secondary.** The Brier comparison over all eligible fires, **including E6 fires with no positives**. Excluding quiet fires removes the cases where persistence is exactly right.
- **Errata rule.**
  - A scorer defect found **before** the CR1 freeze is fixed, and both versions are reported on A1.
  - **After** the freeze nothing changes.
  - The decision is recorded whatever its direction.

## 7. Power (computed from A1's committed `derive/POWER.json` per-fire R differences)
- **Method.** As in A1 §6.3, R's 6 fires are resampled as the fire population, with entry-weighted pooled ΔBrier and a whole-fire percentile bootstrap (2,000 cohorts × 2,000 draws). Power is the share of simulated cohorts whose 95% interval lies below 0.
- **Comparison used.** The available proxy is `d4_wind_seed0` vs `persistence`; the eventual candidate's effect is unknown.
- **Scenarios.** "Half" shifts every per-fire difference by half the R pooled effect toward 0, keeping the between-fire spread (the rule in A1's `derive/power.py`).
- **Code and output (committed).** `clean_replication/power_cr1.py`, seed 20261113. It reads only `derive/POWER.json`, whose sha256 it records, and writes `clean_replication/POWER_CR1.json`. No fire data is read.

| effect | N = 20 | N = 30 | N = 45 | N = 60 | N = 90 |
|---|---|---|---|---|---|
| R effect (−2.0e-4) | 0.81 | 0.92 | 0.99 | 1.00 | 1.00 |
| half of the R effect | 0.33 | 0.43 | 0.59 | 0.72 | 0.87 |

- vs `dilation_8h`: power 1.0 in every case.
- vs `logistic`: power 0, since the R effect has the wrong sign (+1.9e-4). A1's own finding stands.
- The committed figures replace the provisional scratch-run table (previously 0.81 and 0.94 at the R effect; 0.30, 0.42, 0.60, 0.67 and 0.87 at half). Differences are Monte Carlo noise of about ±0.02–0.05 and change no conclusion.

**Consequence for §5.** N_target = 90, decided by the owner on 12 Nov 2026. Achieved power is about 0.87 at half the R effect.
- The resampling of only 6 fires makes all of these figures rough.

## 8. Reporting
- **What gets reported:**
  - the access log;
  - the hash of the ID-reader code and its output;
  - the freeze hash;
  - the rehearsal receipts;
  - both custodians' statistic hashes;
  - attrition by category E1–E6, and the exposed-stratum count;
  - the count of fires walked before stopping;
  - the all-eligible secondary;
  - the §6 statistics.
- **What does not:** CR1 per-fire metadata and raw IDs are never committed before the decision. Afterwards, only hashes, the salt and derived statistics are committed.
- **Committed at the freeze:** the builder's frozen QA rules, and Daniel's rehearsal match statistics against the Magstadt archive.

## 9. Korean prospective stratum (KR-P; descriptive)
Added at the orchestrator's request (16:02Z, from an external review passed on by the owner). The orchestrator has asked for no other new CR1 design work until the 2027 access route is settled.

- **What it is.** A separate, prospective **descriptive** stratum: Korean fires discovered on or after **2027-01-01**.
  - It is **never pooled** with Tier 2 and **never counts toward N**.
  - It **carries no §6.1 decision**. Its label is "descriptive, not a replication".
- **When it is declared.** This section, and the frozen KR-P rules below, are committed **before 2027-01-01**: before the window opens and ahead of the Korean spring fire season. At minimum the frozen rules fix the **label source** and the **minimum event count**.
  - Rules not frozen by then do not apply to the 2027 season, and KR-P starts with the 2028 season instead.
- **KR-P's freeze is a separate commitment.** Its rules are frozen by their own commit, which may come after the CR1 freeze, and Hannah verifies that commit before any 2027 Korean listing. If the two dates disagree, the earlier one applies (before 2027-01-01, per the orchestrator).
- **No claim follows from KR-P.** It supports no confirmatory, superiority or generalisation claim. It is reported for description only.
- **Labels.** These are **satellite active-fire detections**, not IR perimeters, so the label type differs from R and from Tier 2. This is why the stratum is descriptive.
  - Before the declaration date, the frozen rules fix:
    - the detection product (for example, the VIIRS 375 m sensors used for A1 cohort K);
    - the arrival-time reconstruction, which is A1 cohort K's kriged arrival method or a pinned successor;
    - the hindsight-restricted scoring population (A1 §4.1).
- **Event eligibility and minimum count.** Fixed before the declaration date from Korea Forest Service (KFS) incident records: a minimum burned area, a minimum number of detection-days so that the event yields at least one scorable interval, and the **minimum number of eligible events** below which KR-P is reported only as a count.
- **No-look rule.** This is the same rule as §1 item 8, applied to Korea.
  - From the declaration on, no session fetches, lists or reads any 2027-or-later Korean fire source before the KR-P listing. The sources include FIRMS KR, KFS reports and news.
  - The only exception is the custodian, under the §3 protocol: ID-only listing, the salted hash, the sealed store, and the leak rule into "exposed".
- **Snapshot and closing.** These are the same as Tier 2: 2028-01-31 and 2028-03-31. The extension year is the same.
- **Reporting.** KR-P results are reported with the Tier-2 report, in a separate table. They are never in the abstract's confirmatory sentence.
- **Label source (orchestrator decision, 2026-11-13): option (a), pending its preconditions.** We run the deposit's published reconstruction code ourselves, pinned, on VIIRS and Himawari detections. MODIS MCD64A1 is a descriptive cross-check (option b). Before any rule is drafted, the following must be confirmed and recorded:
  - (i) the licence permits reuse;
  - (ii) the code runs end to end from public inputs in a pinned environment;
  - (iii) it reproduces cohort K's published labels on at least one 2025 event. This is the acceptance test, and its rule is committed before it runs.
  - **Findings so far (Victor, 2026-11-13; no fire data fetched):**
    - (i) **Licence: CC-BY-4.0** (Zenodo record 10.5281/zenodo.21788344, metadata only). Reuse is permitted with attribution.
    - (ii) **Not yet shown, and blocked.** The committed copy of the deposit's code (`routing-review/.../sources/zenodo_21788344/extracted/code/`, 5 files, 406 lines) holds library functions only, with no end-to-end driver. Its Korean product (`produce_rasters.kr_product`) interpolates **only inside the event's final perimeter** (EPSG:5179) and selects detections inside that perimeter (`preprocess.select`). The deposit does not include Korean final perimeters (`forecast/documents/korean_observation_availability_20261012.md`). So option (a) needs a public source of KFS final damage perimeters, plus a pinned Himawari active-fire product, as well as VIIRS. Neither has been identified yet.
    - (iii) Not run. It depends on (ii).
  - Per the orchestrator's instruction, this goes back to the orchestrator before (b) or (c) is chosen.
  - **Orchestrator (11:37Z):** (a1) first, as a time-boxed documentation check by the web-research session: are KFS final damage perimeters and a Himawari active-fire product publicly obtainable for 2025 events, and on what terms? If the perimeters are not obtainable, fall back to (b). The (b) rule set is drafted below in parallel. **It is NOT ADOPTED.**

  - **Documentation check result (web-research session, 2026-11-13; documentation only, no data downloaded; detail in that session's LOG.md batch 12, PR #175):**
    - **KFS final damage perimeters: not publicly available**, as far as found. data.go.kr offers statistics and points only. The law provides only for sharing between agencies. The yearly statistics book is statistics only. 2025 drone, IR and VIIRS mapping went to agencies only. A few portals could not be checked from here. **So option (a) as specified is not feasible from public inputs.**
    - **Himawari:** JAXA P-Tree L2WLF version 1.00 (0.02°, 10 min). Its terms forbid redistribution to third parties and require contacting the Secretariat before results are released, which conflicts with JAXA's general credit-based policy. Written clearance would be needed. The archive start and latency are not stated.
    - **The deposit** (CC-BY-4.0) names neither the Himawari product nor the Korean perimeter source.
    - **Burned area for 2027 is not assured.** NASA says Terra and Aqua (MODIS) begin shutting down in late 2026 or early 2027. VNP64A1, the named successor, depends on Suomi NPP, whose data delivery **ended 2026-11-02**. No NOAA-20 burned-area product exists yet. **So option (b) as drafted below may have no 2027 data.**
    - **Wider consequence:** any 2027 VIIRS pipeline in this project must use NOAA-20/21, not S-NPP.
  - **Back to the orchestrator for a decision** (2026-11-13), with options (c) VIIRS first detection and (a′) a perimeter-free reconstruction. See the message of that date.

### 9.1 KR-P label: option (c), descriptive only (orchestrator ruling, 2026-11-13; for the assessor's reading and the custodian's verification)
**Neither option (a) nor option (b) is adopted.** Option (a) cannot run from public inputs. Option (b) has no confirmed 2027 product. KR-P is built around what will exist in 2027, and it is **conditional**: if no qualifying product exists for the season, KR-P is reported as **"count only; not run (no qualifying product)"**. No label is forced.
- **No confirmatory claim.** KR-P supports no confirmatory, superiority or generalisation claim. It is reported **"not run"** if fewer than the minimum number of events qualify, or if no qualifying product exists.
- **Label: first VIIRS detection (option c), NOAA-20/21 only.**
  - Product: VIIRS 375 m active-fire detections from **NOAA-20 and NOAA-21 only** (FIRMS class VJ114/VJ214, I-band). Product names, versions and terms are **PENDING** the web-research session's documentation check. Each is pinned by version, and each downloaded file by sha256, before the season.
  - **Suomi NPP is excluded.** Its data delivery ended on 2026-11-02.
  - **Arrival** = the earliest detection time among the detections whose 375 m footprint centre falls in a cell of the 375 m EPSG:5179 analysis grid. Detections flagged low confidence are excluded.
  - **Footprint and population:**
    - The scored area is the event's detection cells dilated by one cell (375 m), within the KFS incident's reported location area.
    - Cells inside it never detected count as not burned. Cells outside it are not scored.
    - **The footprint is defined from the detections themselves**, including later ones. That is hindsight: the population is **hindsight-restricted** (A1 §4.1) and is labelled so.
  - **Endpoints and leads.** Endpoints are the NOAA-20/21 overpass times over the event. A forecast issued at one overpass is scored at each later overpass within 48 h (A1 §2), on the cells first detected by that overpass.
  - **Known biases, stated in every result:**
    - **First detection is an upper bound on arrival time.** Fire arrives at or before the first overpass that sees it. The bound is limited by overpass cadence (about 12 h between NOAA-20/21 passes) and by cloud and smoke.
    - Cloud and smoke obscuration delays or misses detections.
    - Small or low-intensity burning goes undetected, so the burned area is underestimated.
    - Detection geolocation is uncertain to about one pixel.
    - Labels are not perimeters, so results are not comparable with NIROPS, cohort R, or cohort K's kriged labels.
- **(b′) Burned-area cross-check, conditional.** Used only if a NOAA-20/21-based burned-area product, or another public 2027 burned-area product, is confirmed before the season. MCD64A1 and VNP64A1 are **not** relied on (MODIS is ending; VNP64A1 depends on S-NPP).
- **Official KFS perimeters: obtainable only through an agency contact. OWNER ITEM.** If the owner obtains 2027 KFS final damage perimeters under terms that allow use, the deposit's kriging (CC-BY-4.0) could be applied inside them as a later descriptive variant, declared before use. It is not part of KR-P as registered. **(a′)**, the kriging of NOAA-20/21 detections inside a detection- or Sentinel-2-derived footprint, is **not adopted**.
- **Himawari: not used.** The P-Tree terms forbid redistribution and require contact before results are released.
- **Eligibility (proposal).**
  - KFS-reported burned area ≥ 100 ha.
  - Detections on at least 2 distinct overpasses at least 12 h apart, so the event yields at least one scorable interval.
  - At least 10 detection cells.
- **Minimum event count (proposal).** If fewer than **5** events are eligible, KR-P is reported as a count only.
- **Status:** for the assessor's reading and the custodian's verification, to be frozen before 2027-01-01. The earlier option-(b) draft is withdrawn.
- **Product pins:** taken from the web-research session's documentation batch on NOAA-20/21 active-fire products and terms. **PENDING**; each product is pinned by name, version and terms before the season.
- **US side checked for S-NPP dependence.**
  - Tier 2's primary label, NIROPS-type IR deliveries, does not use VIIRS.
  - The **FEDS** descriptive stratum is VIIRS-derived and 12-hourly. Whether FEDS NRT continues on NOAA-20/21 after the S-NPP cut-off is **PENDING** the documentation check. If its cadence or inputs change, the FEDS stratum states that.

- **Training.** KR-P is scored with the Tier-2 frozen candidates exactly as frozen, plus the A1 Korean comparators (persistence, `dilation_8h`, and the KR logistic reference, if one is frozen by then). There is no Korean refit after the declaration.

## Open items
| item | owner | status |
|---|---|---|
| latest date held per source; whether NIROPS 2025+ exists; ID-only listing feasibility; release lag; expected Tier 1/Tier 2 counts; covariate coverage | Daniel / Hannah | **done** (Daniel 15:11Z; B5 rows 43 and 45) |
| N_target | owner | **decided: 90** (12 Nov) |
| extension, new-candidate set, freeze order, FEDS stratum | owner | orchestrator positions, no objection; awaiting confirmation |
| snapshot and closing dates | owner | **recomputed in draft 6** for the 2027-01-01 start |
| Magstadt-equivalent series builder | Daniel | rehearsal on exposed 2020–24 fires, using IR files already held (FTP paths 404, row 49) |
| buffer B for the same-ground rule | Iris / Hannah | **B = 4 km, confirmed by Iris** (18:19Z) |
| power at the R effect and at half of it | Victor | **done**: `power_cr1.py` and `POWER_CR1.json` committed; §7 table updated from the committed run |
| second custodian | orchestrator | Nora |
| access protocol review | Hannah | draft 9 checked: **PASS WITH NOTES** (ledger row 53), subject to the gate finding |
| Tier-1 scope vs the blind test (US 2026) and `fresh_holdout` (US 2025) | owner | **decided** (12 Nov): no 2026 in any tier; Tier 2 from 2027-01-01 |
| Tier 1 | orchestrator (owner informed) | **decided**: optional, 2025 only, descriptive, never a replication; exposed stratum; no ignorance declaration possible |
| canonical_id rehearsal | Daniel / custodian | **synthetic fixture** (no dual-path fire retrievable, rows 49 and 51) |
| KR-P frozen rules (label source and minimum event count; also detection product, arrival method, eligibility) | Victor drafts; Hannah verifies | due **before 2027-01-01** |
| access route for 2027 NIROPS-type IR | owner | **decided 12 Nov: in-season harvest (d') primary; compiled release a cross-check only.** Before the freeze: Hannah's and Iris's assessments of the harvest design (Hannah's a–g given); the frozen harvest script plus its synthetic-fixture rehearsal; and the owner-side setup (custodian environment through 2027, a daily job with missed-run alerting, and the two owner-held secrets), which the orchestrator walks the owner through |
| frozen harvest script and synthetic-fixture rehearsal (including the canary, two-job union and totals-only log) | **Daniel** writes (acknowledged 16:32Z; after tonight's weather run and the road probe); Hannah reviews and verifies; Nora reads it as second custodian and runs the second job | MUST before the freeze; never run live before 2027-01-01 Review so far: v1 `6e37bd80` FAIL (Hannah, ledger row 68); v2 `14157891` FAIL, narrow (row 73): read-time errors are still logged ALL DONE, and a missing Content-Length is treated as 404. The rule file HARVEST_RULE.md `42906d99` is unchanged. |
| WFIGS/IRWIN field names, and the no-IRWIN space-time match rule (E8) | Daniel (documentation only) | **done** (18:22Z, 76ec1daf): deliveries carry no IRWIN ID; key match on `UniqueFireIdentifier` proposed first, then the space-time match, else E8. Hannah and Iris to confirm the key-match step |
| flight-time rule (midnight rule, ESTIMATED flag, Δ rule, secondary) | Victor (text); Daniel (builder code) | rule fixed in draft 13; code pending |
| builder acceptance: criteria stated, and the 13/37 failing Dixie nights met or explained | Daniel | **done**: criteria stated; the 13 nights are explained (dissolved interior holes in the input product; ≥ 0.9994 IoU without holes); test stays PARTIAL 24/37 |
| second harvest job (Nora, separate environment and time) | owner / orchestrator | to set up before 2027-01-01 |
| custodian offline use of Sofia's 32 frozen 2026 deliveries to rehearse time parsing | owner | **PENDING (morning)** |
| site terms for a daily automated listing and download | owner | **PENDING (morning)** |
| Daniel: the source of A1's 2020–24 NIROPS data, and whether yearly editions exist | Daniel | **done** (16:09Z): Mendeley v1 only, no editions documented |
| latest date held per source: 2025+ US fire check across committed and scratch files (B5) | Hannah | **done** (ledger rows 43 and 45); per-session declarations (Q7) collected |
| owner-held salt and key storage; dedicated custodian environment | owner / orchestrator | to set up before the freeze |
| the custodian named by amendment (the role definition in §1.2) | orchestrator | Hannah and Nora as first holders |
| section-by-section design assessment | Iris | harvest-route assessment adopted (18:19Z, items 1–8 above) |
