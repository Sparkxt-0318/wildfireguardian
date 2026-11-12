# Clean-replication cohort (CR1): pre-registration DRAFT

**Status: DRAFT 2, not frozen. Nothing has been fetched, listed or read for this cohort.**
- It is a new document, not an edit to A1.
- Owner decision (relayed by the orchestrator, 2026-11-12): collect a fresh set of fires for a clean replication.
- The current A1 parts b and c proceed, but are described as **"labels, perimeters and growth sealed; survey-timing metadata exposed; membership rules used it"**. H is descriptive. Neither is presented as the clean confirmation.

Draft 1 added Iris's design input (15:06Z). Draft 2 adds her section-by-section assessment (15:09Z), adopted by the orchestrator. Items marked **OWNER DECISION PENDING** are the orchestrator's provisional positions, which go to the owner with Daniel's availability table. Open items are marked **[OPEN]**:
- data availability (Daniel);
- protocol review (Hannah).

## 0. Why a new cohort
The A1 hold-out parts are sealed for labels, perimeters and growth. But per-incident survey timing was readable by every session before the split, and the cohort's own membership rules used discovery date and the survey window (ACCESS_CONTROL, combined amendment). GOFER/H fires had aggregate labels and final sizes inspected. A replication that can be called clean needs fires about which **no session has read anything, not even metadata**, until the predictors and the scorer are frozen.

**The replication differs from A1 part c in one thing only: cleanliness.** It keeps the same label type, the same criteria and the same candidates, so a different result can be interpreted.

## Owner summary: schedule options (OWNER DECISION PENDING)
1. **Option A, N_target = 30** (power 0.94 at the R effect, 0.42 at half of it).
   - Tier 1 (NIROPS 2025 + 2026 to date) could likely reach 30 within weeks of the freeze. The pace is set by building the FTP perimeter series and by Open-Meteo's 5-day lag.
   - Tier 2 (prospective) would complete after the 2027 season, around **Nov 2027**.
2. **Option B, N_target about 90** (power about 0.87 at half the R effect; the rule in §5).
   - Tier 1 may reach 90 from two seasons, if the FTP still holds 2025.
   - Tier 2 needs one strong season, or two, so **about Nov 2027 to Nov 2028**.
3. **Common to both.**
   - Tier 2 is the confirmation, and its first fires are summer 2027.
   - The extension rule adds one season.
   - All dates assume about 100 analysable fires per season, an unverified extrapolation from 2020–24.

## Timing, detail (provisional)
- **Tier 1 (unseen retrospective).** It covers fires between the latest date we hold (NIROPS: 2024 season) and the freeze, that is, the 2025 season and 2026 to date, **if** a NIROPS-type product for those years is published.
  - If it is, Tier 1 could be listed, built and scored about **1–2 weeks after the freeze**. The custodian's covariate and weather fetch is the main cost.
  - Its weakness: these fires are public events, so a session could know of them from other routes. The declaration in §1 narrows this but cannot close it.
- **Tier 2 (prospective, THE confirmation).** It covers only fires that start after the freeze. The main US season is about June–October, so the first realistic Tier-2 fires are **summer 2027**.
  - Scoring follows the product's release lag [OPEN: Daniel].
  - With N_target = 30, Tier 2 plausibly completes in **late 2027 or early 2028**, if one season yields 30 analysable NIROPS-type fires.
  - With N_target = 90, it likely needs **2–3 seasons, to about 2029–2030**.
  - Daniel's per-season counts turn this from plausible into a date.

## 1. Principles
1. **Nothing is read before the freeze except salted ID hashes.** Non-custodian sessions never see a raw incident ID, because IDs can carry names and dates.
2. **One custodian, one second custodian.**
   - Hannah is the only session that reads any CR1 byte beyond the hashed ID list, and only after the freeze.
   - A second verifier, **Nora** (no forecast-side involvement; named by the orchestrator 2026-11-12), independently reruns the frozen scorer on the sealed data. The two hashes of the released statistics must match.
3. **Complete rules, written first.** Every rule that touches a CR1 fire's data, however mechanical, names its fields here. Nothing outside these lists is read for any purpose.
4. **Outside-repository declaration.** Before the ID listing, and again before the decision, every session signs a declaration in `clean_replication/DECLARATIONS.md`. It states that the session has not looked up, searched for or read anything about any fire in the cohort's source and window **outside the repository**: news, agency pages, other datasets or search engines. A positive declaration excludes the named fires, and the count is reported.
5. **Every access is logged** with who, what, when and the hash.
6. **Leak rule.** If a fire is read outside the protocol, by an unlogged read or a positive declaration, it moves to a named **"exposed" stratum**. That stratum is reported separately and never counted toward N. One leak therefore does not void the cohort.

## 2. Source, window and tiers

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
- FEDS may be declared as a descriptive stratum [OPEN: owner].
- **Expected volume.** The Magstadt archive averages about 147 incidents per season (737 over 2020–24). No part-a incident failed the ≥ 1 interval ≤ 48 h rule (Marcus, train-events build). The analysable count per season is therefore plausibly around 100, but it varies by year and is **unverified**. No CR1 count is taken before the freeze, since counting folders would be the listing itself.

- **Primary product: NIROPS-type IR perimeters**, the same label type as R and A1 part c.
  - If NIROPS yields too few fires, the fallback is a **longer window**, never another product.
  - Other perimeter products (FEDS, WFIGS, CWFIS and others) may be declared here as **separate descriptive strata**. They are never pooled.
- **Two tiers, declared now and never pooled:**
  - **Tier 1, unseen retrospective.** Fires discovered after the latest date in any file any session holds (per source, established by Daniel, verified by Hannah) and **before** this document's freeze commit.
    - *Stated weakness:* these are public events, so a session could know of them from other routes.
  - **Tier 2, prospective.** Fires discovered **after** this document's freeze commit. This is the only tier clean against every route, and it is the one called **the confirmation**.
    - It may mean waiting for the next season, and that is stated plainly.
- **Listing runs once per tier.**
  - Tier 1 is listed after the freeze, at its snapshot.
  - Tier 2 fires do not exist at the freeze, so **the freeze comes first** and Tier 2 is listed at its own snapshot.
- **Weather product.** The frozen rebuild script uses the **same weather and covariate products as the A1 training data**. If a product lags a tier's snapshot, that tier waits for it, up to its closing date. Fires still lacking the product then are E3.
- **Snapshot and closing.** A **closing date** and a **"data as of" snapshot date** for each tier are fixed here [OPEN: dates]. The version of a revised product that counts is the one present at the snapshot.

## 3. Access protocol, from the first byte
1. **ID listing.**
   - Daniel **writes** the ID-only reader. Hannah reviews it and **runs** it: whoever runs it has raw identifiers in their process, and identifiers can carry names.
   - It runs once per tier.
   - Before any CR1 run, it is **rehearsed on an already-exposed source list**, to prove that nothing but the hash is written.
   - It returns only the identifier. It discards every other attribute **in memory before any print or write**, and a test proves this.
   - It writes:
     - `CR1_IDS.csv` (`source`, `id_hash = sha256(salt + "|" + source + "|" + fire_id)`);
     - the ID-to-hash mapping, sealed and held by the custodian only.
   - The salt is generated by the custodian and never released until the decision is recorded.
2. **Optional pre-freeze existence flag.** If a pre-freeze filter is ever forced, the only permitted field is a binary "a perimeter product exists for this ID". It is computed by the reader, and only the filtered hash list is released: no counts, dates or sizes. Survey count is **not** permitted, because it tracks duration and therefore outcome.
3. **Split fields, complete:** `source` and `id_hash`. The order is ascending `u = sha256("S-D9-CR1|" + id_hash)`.
4. **Freeze before any further read.** `CR1_FREEZE.json` is verified by Hannah. **Order (OWNER DECISION PENDING): CR1 freezes BEFORE A1 part c is opened.** It holds:
   - the predictors (A1 stage-2 candidates and comparators, by SHA);
   - the scorer (sd9bench SHA);
   - the covariate and weather rebuild script (SHA);
   - the custodian interface (SHA);
   - this document;
   - the salt commitment (its hash).
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
- **New candidates (OWNER DECISION PENDING: allowed).** A separate set of new candidates may be frozen by SHA at the CR1 freeze. Each is scored and reported **apart, labelled "not a replication"**. This keeps the only clean data from being spent solely on candidates already known to fail, without amending the replication set.
- A candidate not frozen at CR1's freeze is not scored.

## 5. Eligibility, independence, analysability, stopping (custodian, post-freeze)
- **Fields the custodian reads for these rules, complete:**
  - perimeter or survey observation times and geometries (for the interval rule and labels);
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
  - *Location (same ground):* a CR1 fire is excluded if its **point of origin lies inside, or within B = 2 km of, any training fire's final perimeter** (fit-23 ∪ part a).
    - This uses the training fire's outcome, never the CR1 fire's. Excluding by the CR1 fire's own final extent would select against large fires.
    - [OPEN: Iris/Hannah to confirm B.]
  - *Space-time proximity:* the A1 50 km / 30 days clause is empty for a cohort later than every training fire. It applies only if a CR1 window ever overlaps a training window.
  - *Duplicates:* fires within 5 km with overlapping record windows are duplicates; the lower `u` is kept.
  - Only flags and counts are released.
- **Stopping rule.**
  - The custodian walks the `u` order and evaluates eligibility fire by fire.
  - It stops at **N_target analysable fires**, or at the closing date, whichever comes first.
    - **N_target is set from §7:** the smallest N giving power ≥ 0.80 at **half** the R effect, with **30 as the minimum**. The power achieved at the chosen N is stated.
    - Stopping early only saves the custodian's cost, so more analysable fires are better when the cost is acceptable.
  - The stopping rule and E6 depend on **labels, never on any model output**. That mirrors A1 for comparability.
  - The **count of fires walked** before stopping is reported.
- **Underpowered outcome, fixed now.** If fewer than 20 analysable fires exist at the closing date, the result is reported as **underpowered and descriptive**. **Extension rule (OWNER DECISION PENDING): extend the closing date once, by one season, for Tier 2 only.** No other extension is decided afterwards.

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

**Consequence for §5.**
- By the §5 rule (power ≥ 0.80 at half the R effect, minimum 30), **N_target ≈ 90**.
- Whether that is one season or several depends on Daniel's per-season counts. If the owner instead accepts a lower target, the power achieved at that N is stated in advance, and a null at half-effect sizes is declared uninformative. [OWNER DECISION PENDING]
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

## Open items
| item | owner | status |
|---|---|---|
| latest date held per source; whether NIROPS 2025+ exists; ID-only listing feasibility; release lag; expected Tier 1/Tier 2 counts; covariate coverage | Daniel | requested 2026-11-12 |
| closing and snapshot dates; N_target; extension rule, new-candidate set and freeze order (provisional positions above) | orchestrator / owner | OWNER DECISION PENDING, with the availability table |
| buffer B for the same-ground rule | Iris / Hannah | proposed 2 km |
| power at the R effect and at half of it | Victor | provisional table in §7; `power_cr1.py` committed before the freeze |
| second custodian | orchestrator | Nora |
| access protocol review, custodian interface, reader rehearsal | Hannah | after draft 2 |
| section-by-section design assessment | Iris | draft 1 assessed (15:09Z); re-assess draft 2 |
