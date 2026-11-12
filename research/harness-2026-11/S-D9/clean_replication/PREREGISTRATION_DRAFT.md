# Clean-replication cohort (CR1): pre-registration DRAFT

**Status: DRAFT 1, not frozen. Nothing has been fetched, listed or read for this cohort.**
- It is a new document, not an edit to A1.
- Owner decision (relayed by the orchestrator, 2026-11-12): collect a fresh set of fires for a clean replication.
- The current A1 parts b and c proceed, but are described as **"labels, perimeters and growth sealed; survey-timing metadata exposed; membership rules used it"**. H is descriptive. Neither is presented as the clean confirmation.

Draft 1 adds Iris's design input of 2026-11-12, 15:06Z. Open items are marked **[OPEN]**:
- data availability (Daniel);
- protocol review (Hannah).

## 0. Why a new cohort
The A1 hold-out parts are sealed for labels, perimeters and growth. But per-incident survey timing was readable by every session before the split, and the cohort's own membership rules used discovery date and the survey window (ACCESS_CONTROL, combined amendment). GOFER/H fires had aggregate labels and final sizes inspected. A replication that can be called clean needs fires about which **no session has read anything, not even metadata**, until the predictors and the scorer are frozen.

**The replication differs from A1 part c in one thing only: cleanliness.** It keeps the same label type, the same criteria and the same candidates, so a different result can be interpreted.

## Timing, for the owner (provisional until Daniel's availability report)
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
5. **Every access is logged** with who, what, when and the hash. An unlogged read removes the "clean" label from the affected fires.

## 2. Source, window and tiers [OPEN: Daniel's availability report]
- **Primary product: NIROPS-type IR perimeters**, the same label type as R and A1 part c.
  - If NIROPS yields too few fires, the fallback is a **longer window**, never another product.
  - Other perimeter products (FEDS, WFIGS, CWFIS and others) may be declared here as **separate descriptive strata**. They are never pooled.
- **Two tiers, declared now and never pooled:**
  - **Tier 1, unseen retrospective.** Fires discovered after the latest date in any file any session holds (per source, established by Daniel, verified by Hannah) and **before** this document's freeze commit.
    - *Stated weakness:* these are public events, so a session could know of them from other routes.
  - **Tier 2, prospective.** Fires discovered **after** this document's freeze commit. This is the only tier clean against every route, and it is the one called **the confirmation**.
    - It may mean waiting for the next season, and that is stated plainly.
- **Snapshot and closing.** A **closing date** and a **"data as of" snapshot date** for each tier are fixed here [OPEN: dates]. The version of a revised product that counts is the one present at the snapshot.

## 3. Access protocol, from the first byte
1. **ID listing.**
   - Daniel writes an **ID-only reader**. It must be committed and reviewed by Hannah before it runs, and it runs once.
   - It returns only the identifier. It discards every other attribute **in memory before any print or write**, and a test proves this.
   - It writes:
     - `CR1_IDS.csv` (`source`, `id_hash = sha256(salt + "|" + source + "|" + fire_id)`);
     - the ID-to-hash mapping, sealed and held by the custodian only.
   - The salt is generated by the custodian and never released until the decision is recorded.
2. **Optional pre-freeze existence flag.** If a pre-freeze filter is ever forced, the only permitted field is a binary "a perimeter product exists for this ID". It is computed by the reader, and only the filtered hash list is released: no counts, dates or sizes. Survey count is **not** permitted, because it tracks duration and therefore outcome.
3. **Split fields, complete:** `source` and `id_hash`. The order is ascending `u = sha256("S-D9-CR1|" + id_hash)`.
4. **Freeze before any further read.** `CR1_FREEZE.json` is verified by Hannah. It holds:
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
- These are unchanged from A1 stage 2. There is no refit, no retuning and no new candidate.
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
  - *Location:* a fire is excluded if its point of origin lies within 50 km and 30 days of any A1 training-pool fire (fit-23 ∪ part a), **or** if its final perimeter overlaps any training-fire perimeter (the same ground reburning, or a complex sharing a perimeter).
  - *Duplicates:* fires within 5 km with overlapping record windows are duplicates; the lower `u` is kept.
  - Only flags and counts are released.
- **Stopping rule.**
  - The custodian walks the `u` order and evaluates eligibility fire by fire.
  - It stops at **N_target = 30 analysable fires** (20 plus a margin of 10), or at the closing date, whichever comes first.
  - The stopping rule depends only on eligibility, never on a score.
- **Underpowered outcome, fixed now.** If fewer than 20 analysable fires exist at the closing date, the result is reported as **underpowered and descriptive**. The extension rule [OPEN: choose one now] is either "none", or "extend the closing date once, by one season, for Tier 2 only". No extension is decided afterwards.

## 6. Scoring and decision
- A1 §4–§6 apply unchanged: population, 4 km band, criteria 1–6, the whole-fire bootstrap (seed 20261030) and the secondaries.
- Tier 2 carries the confirmatory §6.1 decision. Tier 1 is reported alongside, labelled "unseen retrospective", and is never pooled with Tier 2.
- Also reported: results by tercile of survey span, computed by the custodian after the decision.

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

**Consequence for §5 [OPEN: decide before the freeze].**
- N_target = 30 is adequate only if the true effect is close to R's.
- At half of R's effect, about 90 analysable fires are needed for 0.8 power.
- **Option A:** keep N_target = 30 and state in advance that a null at half-effect sizes is uninformative.
- **Option B:** set N_target = 90. That is likely several seasons of NIROPS-type data for Tier 2.
- The resampling of only 6 fires makes all of these figures rough.

## 8. Reporting
- **What gets reported:**
  - the access log;
  - the hash of the ID-reader code and its output;
  - the freeze hash;
  - the rehearsal receipts;
  - both custodians' statistic hashes;
  - attrition by category E1–E6;
  - the §6 statistics.
- **What does not:** CR1 per-fire metadata and raw IDs are never committed before the decision. Afterwards, only hashes, the salt and derived statistics are committed.

## Open items
| item | owner | status |
|---|---|---|
| latest date held per source; whether NIROPS 2025+ exists; ID-only listing feasibility; release lag; expected Tier 1/Tier 2 counts; covariate coverage | Daniel | requested 2026-11-12 |
| closing and snapshot dates; the extension rule (choose now) | orchestrator / owner | after availability |
| power at the R effect and at half of it | Victor | provisional table in §7; N_target choice (A or B) [OPEN] |
| naming the second custodian | orchestrator | — |
| access protocol review, custodian interface | Hannah | after draft 1 |
| section-by-section design assessment | Iris | after draft 1 |
