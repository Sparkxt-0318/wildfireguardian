# Clean-replication cohort (CR1): pre-registration DRAFT

**Status: DRAFT 4, not frozen. Nothing has been fetched, listed or read for this cohort.**
- It is a new document, not an edit to A1.
- Owner decision (relayed by the orchestrator, 2026-11-12): collect a fresh set of fires for a clean replication.
- The current A1 parts b and c proceed, but are described as **"labels, perimeters and growth sealed; survey-timing metadata exposed; membership rules used it"**. H is descriptive. Neither is presented as the clean confirmation.

Draft 1 added Iris's design input (15:06Z). Draft 2 adds her section-by-section assessment (15:09Z), adopted by the orchestrator. Draft 3 records the owner's decision on N_target (12 Nov). Draft 4 resolves Hannah's custodian protocol review (15:23Z): blocking items B1–B5 and her smaller fixes. Draft 5 answers her re-review of draft 4 (15:30Z): a canonical_id rule that survives archive moves, and the Tier-1 scope conflict with two earlier registrations, recorded as **[OPEN] owner decision**. Items marked **orchestrator position, presented to the owner 12 Nov, no objection** are not owner decisions until the owner confirms them. Open items are marked **[OPEN]**:
- data availability (Daniel);
- protocol review (Hannah).

## 0. Why a new cohort
The A1 hold-out parts are sealed for labels, perimeters and growth. But per-incident survey timing was readable by every session before the split, and the cohort's own membership rules used discovery date and the survey window (ACCESS_CONTROL, combined amendment). GOFER/H fires had aggregate labels and final sizes inspected. A replication that can be called clean needs fires about which **no session has read anything, not even metadata**, until the predictors and the scorer are frozen.

**The replication differs from A1 part c in one thing only: cleanliness.** It keeps the same label type, the same criteria and the same candidates, so a different result can be interpreted.

## Decisions and proposed dates
- **N_target = 90 analysable fires: OWNER DECISION, 12 Nov 2026.** This is the §5 rule (power ≥ 0.80 at half the R effect).
  - Achieved power at N = 90: about **0.87 at half the R effect**, and about 1.0 at the R effect.
  - These figures are rough, because only 6 R fires are resampled (§7).
- **Orchestrator positions, presented to the owner 12 Nov, no objection (not yet confirmed):**
  - extension once, by one season, Tier 2 only;
  - a separately frozen new-candidate set, reported apart as "not a replication";
  - CR1 freezes before A1 part c is opened;
  - FEDS as a descriptive, non-pooled stratum.
- **Proposed dates (for confirmation).** Tier 1 dates are relative to the freeze date F, which is set by A1 stage 2 and is before part c opens.

| tier | discovery window | snapshot ("data as of") | closing |
|---|---|---|---|
| Tier 1, unseen retrospective (**scope [OPEN]**, see §2) | 2024-12-18 to F, before the scope decision | F + 14 days | F + 60 days |
| Tier 2, prospective (THE confirmation) | F + 1 day to 2027-12-31 | 2028-01-31 | 2028-03-31 |
| Tier 2 extension (once, if < 90 analysable at closing) | to 2028-12-31 | 2029-01-31 | 2029-03-31 |

- **Why these dates.** NIFC IR lags about a day and Open-Meteo about 5 days. The 31 Jan snapshot leaves a month for late uploads and revisions. The closing date leaves the custodian two months to build inputs and score.
- **The NIROPS-type series builder.** Daniel may write and rehearse it now, on **exposed 2020–24 fires only**. There is no CR1 listing or fetch before the freeze.

## Timing, detail (provisional)
- **Tier 1 (unseen retrospective).** Its scope is an **[OPEN] owner decision** (§2, "Tier-1 scope"). Before that decision it was drafted as the 2025 season plus 2026 up to the freeze, **if** the NIFC FTP still holds 2025 (unverified).
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

## 2. Source, window and tiers

**Tier-1 scope: conflicts with two earlier registrations ([OPEN] owner decision; Hannah's B5 result, ledger row 43).**
- **US 2026** is reserved by `forecast/documents/preregistration_blind_test.md` (owner, 2026-10-30). Any access before the owner's OSF registration of that test would block the test.
- **US 2025** is earmarked by `firecast-lab/SPLITS.json` `fresh_holdout` (`us_2025_membership_rule`, pending).
- The owner chooses one of the following:
  - **(a)** Tier 1 = 2025 only, superseding or merging `fresh_holdout` explicitly, with 2026 excluded from Tier 1;
  - **(b)** no Tier 1, so CR1 is Tier 2 only;
  - **(c)** the blind test declared superseded, so Tier 1 stays 2025 plus 2026 to the freeze.
- The decision, and which document it supersedes or merges with, is written here before the freeze. Until then, every Tier-1 count and date in this draft is conditional on it.
- Tier 2 starts the day after the freeze. Under (a) or (b), Tier 2 would also take in late-2026 fires, which the blind test reserves; this is **[OPEN]** for the same decision.

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
  - **Tier 1** (2025 plus 2026 to the freeze, as first drafted): about 200–300 incidents with IR. Under option (a) this drops to the 2025 share; under (b) it is zero.
  - **Tier 2** (prospective): the rest of 2026 is about 0 after mid-November in the western US. The 2027 season is about 100–170.
  - CR1 has no survey-count threshold, and no part-a incident failed the ≥ 1 interval ≤ 48 h rule (Marcus). So **N_target = 90 is plausibly reachable from Tier 1, and from Tier 2 in the single 2027 season**, after QA losses and E6.
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
- **FTP retention of 2025 is unverified.** If 2025 is gone: under (a) Tier 1 is empty; under (c) Tier 1 shrinks to 2026. Tier 2 is unaffected either way.

- **Primary product: NIROPS-type IR perimeters**, the same label type as R and A1 part c.
  - If NIROPS yields too few fires, the fallback is a **longer window**, never another product.
  - Other perimeter products (FEDS, WFIGS, CWFIS and others) may be declared here as **separate descriptive strata**. They are never pooled.
- **Two tiers, declared now and never pooled:**
  - **Tier 1, unseen retrospective.** Fires discovered after the latest date in any file any session holds, and **before** this document's freeze commit.
    - **"Latest date held" is a pre-freeze task with a recorded result (B5).** The custodian checks every committed and scratch file the sessions hold for any 2025+ US fire, and logs the result. The sources include NIROPS, the FEDS archive listing, the WFIGS/ICS-209 joins, FIRMS US2024, WSTS 2018–21 and GOFER 2019–21.
    - The Tier-1 window start (provisionally 2024-12-18) is set from that result.
    - *Stated weakness:* these are public events, so a session could know of them from other routes.
  - **Tier 2, prospective.** Fires discovered **after** this document's freeze commit. This is the only tier clean against every route, and it is the one called **the confirmation**.
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
       - **Rehearsal requirement:** the reader's rehearsal on exposed fires must include at least one exposed fire listed under both a current and an archived path, and must show that both give one hash. If no such fire exists among the exposed fires, a synthetic fixture with both path forms is used instead, and that is disclosed.
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
- Tier 2 carries the confirmatory §6.1 decision. Tier 1 is reported alongside, labelled "unseen retrospective", and is never pooled with Tier 2.
- Also reported: results by tercile of survey span, computed by the custodian after the decision.
- **All-eligible secondary.** The Brier comparison over all eligible fires, **including E6 fires with no positives**. Excluding quiet fires removes the cases where persistence is exactly right.
- **Errata rule.**
  - A scorer defect found **before** the CR1 freeze is fixed, and both versions are reported on A1.
  - **After** the freeze nothing changes.
  - The decision is recorded whatever its direction.

## 7. Power (provisional: computed from A1's committed `derive/POWER.json` per-fire R differences)
- **Method.** As in A1 §6.3, R's 6 fires are resampled as the fire population, with entry-weighted pooled ΔBrier and a whole-fire percentile bootstrap. Power is the share of simulated cohorts whose 95% interval lies below 0.
- **Comparison used.** The available proxy is `d4_wind_seed0` vs `persistence`; the eventual candidate's effect is unknown.
- **Scenarios.** "Half" shifts every per-fire difference by half the R pooled effect toward 0. The code is in the scratch run, to be committed as `clean_replication/power_cr1.py` before the freeze.

| effect | N = 20 | N = 30 | N = 45 | N = 60 | N = 90 |
|---|---|---|---|---|---|
| R effect (−2.0e-4) | 0.81 | 0.94 | – | – | – |
| half of the R effect | 0.30 | 0.42 | 0.60 | 0.67 | 0.87 |

- vs `dilation_8h`: power 1.0 in every case.
- vs `logistic`: power 0, since the R effect has the wrong sign. A1's own finding stands.

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

## Open items
| item | owner | status |
|---|---|---|
| latest date held per source; whether NIROPS 2025+ exists; ID-only listing feasibility; release lag; expected Tier 1/Tier 2 counts; covariate coverage | Daniel | requested 2026-11-12 |
| N_target | owner | **decided: 90** (12 Nov) |
| extension, new-candidate set, freeze order, FEDS stratum | owner | orchestrator positions, no objection; awaiting confirmation |
| snapshot and closing dates | owner | proposed in draft 3 |
| Magstadt-equivalent series builder | Daniel | may start the rehearsal on exposed 2020–24 fires only |
| buffer B for the same-ground rule | Iris / Hannah | B = 4 km in the text (draft 4); Iris to confirm |
| power at the R effect and at half of it | Victor | provisional table in §7; `power_cr1.py` committed before the freeze |
| second custodian | orchestrator | Nora |
| access protocol review | Hannah | draft 4 re-reviewed (15:30Z): B1–B5 resolved. Two items remained: the Tier-1 scope (owner) and canonical_id stability (fixed in draft 5). She would pass it for freeze once the scope is decided |
| **Tier-1 scope vs the blind test (US 2026) and `fresh_holdout` (US 2025)** | owner | **[OPEN]**: option (a), (b) or (c) in §2 |
| latest date held per source: 2025+ US fire check across committed and scratch files (B5) | Hannah | done for committed data (ledger row 43); per-session scratch declarations pending |
| owner-held salt and key storage; dedicated custodian environment | owner / orchestrator | to set up before the freeze |
| the custodian named by amendment (the role definition in §1.2) | orchestrator | Hannah and Nora as first holders |
| section-by-section design assessment | Iris | draft 1 assessed (15:09Z); re-assess draft 2 |
