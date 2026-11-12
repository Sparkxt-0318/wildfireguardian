# Clean-replication cohort (CR1): pre-registration DRAFT

**Status: DRAFT 0, not frozen. Nothing has been fetched, listed or read for this cohort.**
- It is a new document, not an edit to A1.
- Owner decision (relayed by the orchestrator, 2026-11-12): collect a fresh set of fires for a clean replication.
- The current A1 parts b and c proceed, but are described as **"labels, perimeters and growth sealed; survey-timing metadata exposed; membership rules used it"**. H is descriptive. Neither is presented as the clean confirmation.

Open items, marked **[OPEN]**:
- data availability (Daniel);
- design review (Iris);
- protocol review (Hannah).

## 0. Why a new cohort
The A1 hold-out parts are sealed for labels, perimeters and growth. But per-incident survey timing was readable by every session before the split, and the cohort's own membership rules used discovery date and the survey window (ACCESS_CONTROL, combined amendment). GOFER/H fires had aggregate labels and final sizes inspected. A replication that can be called clean needs fires about which **no session has read anything, not even metadata**, until the predictors and the scorer are frozen.

## 1. Principles
1. **Nothing is read before it is needed, and nothing is needed before the freeze.** Before the freeze, the only things anyone sees are the fire ID and the source name.
2. **One custodian.** Hannah (verifier) is the only session that reads any CR1 byte beyond the ID list, and she reads it only after the freeze. She builds labels and inputs, runs the frozen scorer, and releases only the pre-declared statistics.
3. **Everything is decided by rules written here first.** That covers which fires, which parts, eligibility, analysability, independence, scoring and the decision. Every rule is complete as written: if a rule needs a field, the field is named here.
4. **Every access is logged.** Each read is logged with who, what, when and the hash. An unlogged read voids the cohort's "clean" label for the affected fires.

## 2. Source and window [OPEN: Daniel's data availability]
- **Window:** fires whose **source record is first published after 2026-11-12**, or whose season lies wholly after the latest date in any file any session holds, whichever the availability report supports.
  - The "latest date held" is established per source by Daniel and verified by Hannah from the repository and scratch logs.
  - Candidates: the NIROPS/NIFC IR 2025 season and later, FEDS 2025+, WFIGS 2025+ operational perimeters, CWFIS/NBAC 2025+, and others.
- **Label strata are not pooled.** A NIROPS-type IR source is primary, because it matches R's label type and so the A1 band and other R-fixed rules transfer. Other perimeter products are separate descriptive strata, as in A1 §1.1.
- Any source that cannot list IDs **without** returning other attributes is either excluded, or listed by the custodian, who then releases the ID column only (§3).

## 3. Access protocol, from the first byte
1. **ID listing.**
   - Daniel writes an **ID-only reader** for the chosen source: an API field selection, a directory listing, or a manifest parse that returns the fire identifier and nothing else.
   - The code is committed and reviewed by Hannah **before** it runs. It runs once.
   - Its output, `CR1_IDS.csv` (columns: `source`, `fire_id`), is committed with its sha256.
   - If the source returns other attributes in the same response, the reader discards them **in memory, before any print or write**, and a test proves it. This is the parta_price lesson.
2. **Split fields, complete:** `source` and `fire_id`. No other field is read by anyone for any purpose before the freeze.
3. **Order and parts.**
   - `u = sha256("S-D9-CR1|" + source + "|" + fire_id)`, ascending.
   - Part **T** (test): every listed fire, subject to post-freeze eligibility (§5).
   - Part **H0** (held back): none by default. A held-back part may be declared here before listing, as a fixed fraction by `u`.
4. **Freeze, before any further read.** The following are frozen in `CR1_FREEZE.json` and verified by Hannah:
   - the predictors (D1/D2 candidates and comparators, by SHA, with their training data unchanged from A1 stage 2);
   - the scorer (sd9bench SHA);
   - the input-build pipeline (rebuild_env.sh SHA);
   - this document.
5. **After the freeze, the custodian only:**
   - reads the CR1 metadata, perimeters and labels;
   - builds inputs and labels;
   - applies eligibility, independence and analysability (§5);
   - runs the frozen predictors and scorer;
   - releases the §6 statistics and attrition counts.

   Per-fire outputs are released only after the decision is recorded.
6. **No other session** fetches, opens or derives anything from CR1 sources until the decision is recorded. Daniel's ID-only reader is the only exception.

## 4. Training data and predictors
- These are unchanged from A1 stage 2. CR1 adds no refit, no retuning and no new candidate.
- A candidate admitted to A1 part c is scored on CR1 as frozen. A candidate not frozen at CR1's freeze is not scored.

## 5. Eligibility, independence, analysability (post-freeze, custodian only)
- **Eligibility.** At least one valid interval under the A1 §2 interval rule (0 < Δ ≤ 48 h). There is **no survey-count threshold** [OPEN: Iris, whether a minimum is needed for cost or power].
- **Independence.** A CR1 fire is excluded if it lies within 50 km and 30 days (point of origin, discovery date) of any A1 training-pool fire (fit-23 ∪ part a), or if it duplicates another CR1 fire (5 km plus overlapping record window; the lower `u` is kept).
  - The custodian applies this and releases only the exclusion flags and counts.
- **Analysable.** Inputs are built and there is at least one positive in the 4 km band.
  - At least 20 analysable fires are needed; otherwise the result is INCONCLUSIVE and descriptive, as in A1 §6.1 item 6.
  - Build failures are logged and never replaced by inspection.

## 6. Scoring and decision
- A1 §4–§6 apply unchanged: population, band, criteria 1–6, the whole-fire bootstrap (seed 20261030) and the secondaries.
- A1 §6.1 is the confirmatory decision for each candidate frozen at CR1's freeze, with no multiplicity adjustment beyond A1's.
- Also reported: results by tercile of survey span (A1 amendment rule g), computed by the custodian after the decision.

## 7. Power and timing [OPEN]
- Power uses A1 §6.3 (computed on R) at the expected analysable count, which is supplied by the availability report.
- If fewer than 20 analysable fires can be expected from the chosen source and window, CR1 either waits for the next release or is labelled descriptive in advance. That choice is made here, before listing.

## 8. Reporting
- **What gets reported:**
  - the access log, with the ID-listing code and output hash;
  - the freeze hash and the custodian's receipts;
  - attrition counts;
  - the §6 statistics.
- **What does not:** CR1 per-fire metadata is never committed. Only hashes and derived statistics are committed, as for WSTS.

## Open items
| item | owner | status |
|---|---|---|
| sources, latest date held per source, ID-only listing feasibility, release lag, expected count, covariate coverage | Daniel | requested 2026-11-12 |
| eligibility without metadata; label-type strata; timing | Iris | requested 2026-11-12 |
| access protocol review, custodian role | Hannah | after the draft |
| decision to proceed and fetch | orchestrator / owner | after all of the above |
