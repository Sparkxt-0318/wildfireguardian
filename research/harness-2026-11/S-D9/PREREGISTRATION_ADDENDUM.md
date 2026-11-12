# Pre-registration addendum A1: multi-fire, multi-horizon benchmark (S-D9)

**Status: DRAFT revision 18, not frozen.** Nothing here is in force until Hannah has verified it, Iris has re-assessed it, and it is committed with the hashes in §9. No fire in any untouched cohort below has been scored. The only scores computed so far are on cohort R, which is already exposed. They were computed to apply rules that are stated in this document before the computation, and each one is labelled.

## Revision log

*How to read this log:* "#" numbers **change items**, in the order they were adopted, and the "(revision N)" tags in the text refer to these item numbers. The status line's "DRAFT revision N" counts **document versions**. The two numberings are independent. **Row order:** items 1–8 are listed oldest-first, and items after 8 are listed newest-first, directly below item 8. Item 12 is the hash-match clarification in §1.2 item 14.

| # | change item (items 1–7: Iris assessment of 9348abb5, adopted by the orchestrator) | where | status |
|---|---|---|---|
| 1 | Choose the primary band by a stated rule on R | §4 | Rule committed at 3eb31a38 before any share was computed. Applied: **4 km** (`derive/BAND_RULE.json`) |
| 2 | Reserve untouched data for D1/D2 | §1.2 | Hash split, fixed now |
| 3 | Independence from fit fires | §1.3 | Metadata exclusion rule, fixed now |
| 4 | Equal-fire weighting as a named secondary | §6 | Added |
| 5 | Power from R | §6.3 | Computed (`derive/POWER.json`): **limited** |
| 6 | A common zero-probability floor | §5 | Added: count of positives with p < 1/1024 |
| 7 | Run the RPS export on R before freezing | §5.2 | **Not runnable here**, so RPS is declared unavailable for the current models |
| — | Network reality: NIROPS 2020–24 is unreachable (data.mendeley.com blocked) | §1 | **Superseded**: the user approved network access, and Daniel fetched the full archive (737 incidents) |
| 8 | Four-part NIROPS split (orchestrator), sized from power | §1.2, §6.3 | Rule committed before any assignment was generated |
| 25 | GOFER fires matched to a kept part-a incident are assigned to **H-dev, never H-test** (forced H-dev set F: 12 GOFER fires, 10 of them H survivors, since Creek and River Complex are FIT fires); H-test is drawn only from the other survivors. Elena's real-bracket comparison must state its 42 → 25 filter before results | §2.1 | **Correction made after Owen's finding** (5 GOFER fires among Elena's 42 part-a fits). Decided by a rule on committed metadata (GOFER_MATCH.csv, COHORT_FINAL.csv), not by results. H membership was not yet computed, and nothing was scored on H |
| 24 | §4.1 rule 5 resolved for US kriged rasters: the arrival-valid set equals the final NIROPS union cell for cell on all 29 exposed US fires (Daniel); Korea stays an assumption | §4.1 rule 5 | Result received after the rule was written; no threshold was set. No b/c/d or H-test fire was opened |
| 23 | Two development-first candidates (Iris), declared before any refit: `c651_fullvalid_rebuilt` (the c651 recipe with full-rectangle label validity, the one change) and `rate_composite` (composite-likelihood kernel shape plus a bracket-likelihood rate), which is compared with the full latent-time method on Elena's synthetic harness first. Owen's synthetic findings recorded beside P-D2 as development evidence; Iris's ranking of SMOKE experiments | §3.2, §3.1 | Orchestrator decision. **Declared before any refit.** Admission to part c only by amendment before part c opens |
| 22 | Scored-population flag. Kriged-label populations are **hindsight-restricted**: a cell has a valid burned state only if the final reconstruction gives it an arrival time, so every scored cell burns eventually. Stratum K and the forecast-v2 KR2025 results are flagged and never pooled or paired with perimeter populations; NIROPS parts, cohort R and H use full-grid perimeter populations; training and scoring paths may not take label validity from an arrival raster | §4.1, §1.1 K, harness `population` | Iris's side finding, checked from code and committed files (orchestrator request). **No part-c score exists**; nothing previously reported for R changes |
| 21 | D2 loss or likelihood-procedure candidates admitted under the §3.1 recipe: `d2_nll_rebuilt` (mean-field Brier loss replaced by Bernoulli NLL) and `d2_bracket_rebuilt` (latent arrival-time augmentation within survey brackets). Elena's hypothesis and prediction P-D2 (tail, lowest-bin gap, Brier non-inferiority, plus the bracket-vs-NLL ordering) are recorded before any refit. The soft-risk-set arm is development-only. Also corrects §3.1's stale allowlist sha (801acdd8… → 7db3cc0e…, per item 20) | §3.1 | Orchestrator decision on Elena's (S-D2) request. **Declared before either D2 refit runs**; the wrapper shas are recorded in FREEZE.json before any run |
| 20 | Correction after Hannah's FAIL. CA-KNF-007084_Devil (GOFER "Slater and Devil") had been kept in part c and is now excluded. GOFER↔NIROPS matching is redone systematically by location and dates (`cohort/gofer_match.py`). Pinned inputs are by commit and file hash and are never edited in place | §1.1, §1.2 | **Made after Hannah's finding.** COHORT_FINAL went from 13078990… to d5ae66f4…, the part-a allowlist from 801acdd8… to 7db3cc0e…, and part c swapped Devil for ID-SCF-022091_WolfFang. The systematic matching found no further b/c/d exposure. Nothing had been scored on part c |
| 19 | Refit deviations required to run on rebuilt inputs (Marcus): verbatim command line, input-manifest and train-events patches, part-a grid and window rules | §3.1 | Frozen before any refit. The patch is pinned by sha once Marcus sends it |
| 18 | Rebuilt-pipeline refits of d4_wind and logistic on the training pool: the confirmatory comparators for part c (orchestrator decision; Iris option b) | §3.1 | Recipe frozen here **before any refit runs**. Archive-trained models become labelled descriptive rows |
| 17 | Filters applied (`cohort/RUN_FILTERS.md`). The script now enforces §1.1 ledger exclusion by incident ID, including NIROPS incidents matching GOFER fires. Clarification: an incident that is an item-10 duplicate of an opened incident counts as opened | §1.2 items 8–12 | Clarification written after the first filter run showed Caldor and a pilot sibling in test parts. Only metadata was viewed |
| 16 | Pre-declared plan for a non-burnable secondary; provenance of the H tolerance rule; H disclosure note on every H result (Iris) | §4, §2.1 | Added. **The secondary was added after a development finding on R** (`derive/LOGISTIC_DEV.md`, follow-up 2) |
| 15 | H refinements: Chebyshev reach, one-pixel tolerance, resolution labels per lead, H-dev open to D1 and D2, half-step comparator; Marcus's GOFER disclosure (Marcus, Iris) | §2.1 | Added before any H score |
| 14 | Short-horizon stratum H for the D1 continuous-time claim (orchestrator) | §2.1 | Declared before any score on H. Membership is computed after the metadata filters run |
| 13 | Recalibrated d4 is a part-c comparator that D1/D2 must beat (Iris) | §3, §6.1 | Added. Chosen after seeing the development-only R result (`derive/LOGISTIC_DEV.md`) |
| 12 | How a covariate channel passes the archive check: a byte-identical hash counts as a pass. Written after Daniel's first hash report; no threshold changed | §1.2 item 14 | Added and disclosed |
| 11 | Part b NOT run now, kept for a later named candidate; covariate check gains tail bounds, and failure makes results descriptive (orchestrator and Iris) | §1.2 items 4 and 14, §6.1 | Added |
| 10 | Iris fast pass on §1.2: a-vs-c leakage filter, cross-part duplicates, d floor, half-effect power, per-part comparability, check tolerance | §1.2 items 9–13, §6.3 | Added; the split itself is unchanged |
| 9 | Frozen logistic becomes an A1 decision criterion; power labelled rough; D1/D2 must emit native cumulative marginals (Iris re-assessment, orchestrator) | §5.2, §6 | Added. **This choice was made after seeing R results**, which is allowed because R is exposed |

## 0. Relation to the existing protocol

This addendum **extends** `forecast/documents/preregistration_blind_test.md` (the "base protocol") without editing it.
- For the 2026 cohort, the base protocol's primary decision governs, and everything in A1 is a pre-declared secondary.
- For retrospective untouched cohorts, which the base protocol does not cover, A1 defines the primary. It reuses the base conventions: interval rule, scoring population, baselines, 10 equal-width bins, NLL floor, whole-fire bootstrap with seed 20261030, and "fail any criterion means no superiority claim".

## 1. Cohorts, exposure, reservation and independence

### 1.1 Cohorts

Exposure is defined by the S-D9 ledger (checkpoint 3e2eb2d), plus any amendment committed before a cohort manifest.

| id | cohort | label definition | reachable now | role |
|---|---|---|---|---|
| R | US2024: 6 NIROPS fires, 273 intervals | NIROPS IR mapped extent | yes (in git) | Descriptive regression reference; already exposed. Rules may be fixed on R. |
| N | NIROPS 2020–24 fires absent from the ledger | NIROPS IR mapped extent | **yes** (Daniel, daniel/data-fetch) | **Primary untouched cohort**, split per §1.2 |
| C2 | 2026 first-survey NIROPS | NIROPS | no (future release) | Base protocol primary; A1 secondary |
| G | GOFER v0.2 fires absent from the ledger (Zenodo 14642378) | GOES-derived hourly perimeters | yes | Separate stratum |
| F | FEDS CONUS fires absent from the ledger | VIIRS-derived 12-hourly perimeters | 2021 yes; 2019/20 scripted | Separate stratum |
| K | Korean events absent from the ledger | kriged arrival reconstruction | not yet located | Separate stratum; **hindsight-restricted population** (§4.1) |

**Label strata are never pooled.** The 4 km band and every other rule fixed on R come from NIROPS. Applying them to G, F and K is a stated transfer assumption, not a validated equivalence. Because R is NIROPS, **only N (or C2) can carry a confirmatory A1 result**. G, F and K results are descriptive whatever their size.

**Correction (Hannah, A1 note; same root cause as the Devil miss).** None of the GOFER fires is untouched. All 28 had their aggregate label statistics inspected by S-D1 before stratum H was declared (ledger, ACCESS_CONTROL.md). The G stratum and stratum H are therefore **INSPECTED (aggregate label)** and descriptive only, and every NIROPS incident matching a GOFER fire (`cohort/GOFER_MATCH.csv`) is excluded from parts b, c and d. The list below, kept for the record, is GOFER fires with **no forecast fit or score** in the project. It is not a list of untouched fires. Daniel's metadata name match gave 17: Kincade, Walker, Bobcat, CZU, Dolan, Glass, July, KNP, LNU, McFarland, SCU, Slater & Devil, Tamarack, W-5 Cold Springs, Windy, Zogg and Beckwourth. Dixie, River, Antelope, August, North/PNF, Monument, Creek, SQF, McCash and Red Salmon are FIT fires. Caldor is INSPECTED. Membership becomes final only through the manifest procedure in §9, after §1.3 is applied.

Admission to any untouched cohort requires all of the following:
- The fire is absent from the ledger.
- Admission is decided from metadata only.
- The manifest is committed, hashed and verified before any predictor runs.
- The manifest builder attests that they have not viewed the fire's growth.

### 1.2 NIROPS cohort selection and four-part split (revision 3; committed before any assignment was generated)

The source is Daniel's metadata table `research/harness-2026-11/data-fetch/nirops_incidents.csv` (branch daniel/data-fetch, 3129ad59 or later). It has 737 incidents from the Magstadt et al. NIROPS 2020–24 archive and uses **only** these fields: `Incident_C`, `surveys`, `project_status`, `shares_irwin_with_project_fire` and `year`. `max_acres` (final size) is an outcome and is **not used**.

1. **Clean pool.** Keep `project_status == "unused_in_repo_events"` and `shares_irwin_with_project_fire == False`. That leaves 704 incidents. The input file is pinned: daniel/data-fetch 3129ad59, `nirops_incidents.csv` SHA-256 f2aae4b8891bcaa5489631185d19a50991ae059c056384f11d8b8f299922d9ca. (The pin previously cited 971f825d, a later head where the file had changed; corrected after Hannah found it. Pinned inputs are referenced by commit and hash and are never edited in place.) Clarification committed before the first run: the status label is the one used in the file.
2. **Eligible.** A clean incident is eligible if `surveys >= 20`, which keeps well-surveyed fires so that a fire contributes several intervals.
3. **Order.** For each eligible incident, set `u = int(sha256("S-D9-A1|NIROPS|" + Incident_C).hexdigest()[:12], 16) / 16**12`, then sort ascending by `u`. This order is the fixed "seed".
4. **Parts, by rank in that order:**
   - **b**, ranks 1–30: a **confirmatory test set held for a later named candidate** (revision 11). It is **not run now**. With power 0.00 against logistic, scoring the current d4_wind on b would spend 30 untouched fires for almost no information. b is opened only when a named candidate is declared by SHA in an amendment committed before the opening. d4_wind, c651 and logistic are instead scored as **comparators on part c** when the D1/D2 candidate runs. That records d4_wind versus logistic on untouched fires as a named secondary at no extra cost in data.
   - **c**, ranks 31–60: the **reserved D1/D2 methods confirmatory test set**. It stays closed until every D1/D2 candidate is frozen by SHA.
   - **a**, ranks 61–120, plus every clean incident with `surveys < 20`: the **training and development pool** for D1/D2 refits.
   - **d**, ranks 121 onward: held back for later work. It stays closed.
5. **Sizing.** 30 per confirmatory set comes from §6.3. At R's effect against persistence, power reaches 0.80 at about 20 fires. 30 gives a buffer for attrition, at 0.93 if all 30 are analysable. **At least 20 analysable fires** are required in b, and likewise in c (analysable means inputs built and at least one positive in the 4 km band); otherwise the decision is INCONCLUSIVE. Attrition is decided before any prediction runs on the fire:
   - **Input-build failure** (no covariates, or a grid that cannot be aligned): the fire is replaced by the next d incident in `u` order. The replacement is logged.
   - **No positive in the band:** this is known only after labels are built. It never triggers a replacement; it only reduces the analysable count.
6. **Independence (§1.3)** is applied after assignment. An excluded b or c fire is replaced by the next d fire in `u` order, before any prediction runs.
7. **Pilot.** The pipeline pilot uses only the **first 3 eligible (surveys >= 20) part-a fires in `u` order**. Clarification committed before the first run. Pilot fires are training-pool fires; no b, c or d fire is ever a pilot.
8. **Access control.** (Clarification, revision 17: an incident that is an item-10 duplicate of an opened incident, for example a component of the same complex, counts as opened.) Whoever assigns the parts publishes the part list as a CSV. **No one opens the perimeters of b, c or d until the addendum is frozen and the manifest for that part is verified.** Training users filter the shapefile by the part-a allowlist. This is recorded in the ledger.

9. **Leakage filter, part a vs part c** (and vs part b). D1/D2 are refit on part a, so a part-a incident is **dropped from a** if its point of origin lies within 50 km of a part-b or part-c incident's point of origin **and** its discovery date is within 30 days of that incident's. Fires are never dropped from b or c by this filter. Drops are logged.
10. **Duplicates across parts.** Pairs whose points of origin lie within 5 km of each other and whose survey windows overlap are treated as the same fire under two names (for example, a complex and its member). On a hit, the copy in a or d is removed. If both copies are in b or c, the lower-ranked one is removed and replaced from d.
11. **Point of origin and dates** for items 9 and 10 and for §1.3 come from incident metadata (an ICS-209-PLUS join by IRWIN ID or incident number, from Daniel), never from perimeters. If an incident has no point of origin, it is kept, and that is logged.
12. **Floor on d.** Replacements are taken from d in `u` order, but never below **30 remaining d incidents**. If b or c would need more, that part proceeds short. If it falls below 20 analysable fires, the decision is INCONCLUSIVE (point 5).
13. **Comparability and scope.** b and c differ by year by chance: b has 11 fires from 2024, and c has 13 from 2021. **Parts are not compared with each other**; each candidate is compared with baselines inside its own part. Every result states its scope as "NIROPS incidents with 20 or more surveys". Reports give the number of b and c fires removed by §1.3 and by items 9–10.
14. **Rebuilt-vs-archive covariate check** (fixed before any run), on one already-exposed fire where archive values are recoverable from committed files. It compares the rebuilt covariates with the archive covariates cell by cell inside the rectangle:
   - Pass requires a median absolute difference of ≤ 1.0 K for temperature, ≤ 1.0 m/s for each wind component, ≤ 1.0° for slope and ≤ 5 percentage points for tree cover, and at least 95% agreement on biome class.
   - Pass **also** requires tail bounds (revision 11): the 95th percentile of |difference| must be ≤ 3.0 K, ≤ 3.0 m/s per wind component, ≤ 3.0° and ≤ 15 percentage points respectively.
   - **How a channel passes (clarification, revision 12).** A channel whose rebuilt file is **byte-identical** to the archive file hash pinned in committed evidence (for example, FIT_COVERAGE.json) has a difference of 0 and passes. A channel whose hashes differ and whose archive values are not recoverable is **UNAVAILABLE**, and the fallback applies to it. *Disclosure:* this clarification was written after Daniel reported that 16 of 35 AlderCreek covariate files hash-match and that slope and tree cover differ. It adds no tolerance and changes no threshold. It only states how a hash match counts.
   - **Hash-check outcome** (Daniel, daniel/data-fetch 78cbe58b `covariate_hash_table.csv`, fit fires AlderCreek, TrailCreek and GreenRidge):
     - biome_class, arrival_time_hours and kriging_std_hours **PASS** (byte-identical; biome on all 34 events with an archive hash).
     - slope_degrees and tree_cover_percent: bytes differ on all 3, and no archive values are committed, so **UNAVAILABLE**.
     - temperature and wind: not yet built (Open-Meteo limit).
     - The only archive-derived values are the frozen logistic's pooled feature scaler statistics. They are not per-channel values, so they do not satisfy the cell-wise check.
     - **Consequence under the fallback below: decisions for archive-trained models on rebuilt inputs are descriptive**, unless the owner supplies archive values for one fit fire.
   - **Labels.** The rebuilt label pipeline reproduced all 52 committed Wapiti held-out cases exactly (grid, reference_cells, positives, y). This was reported by Daniel at 60a94974 and is not yet verified by Hannah.
   - **Fallback.** Untouched fires have no archive values, so the rebuilt source is used whatever the outcome. On a failure, or if no archive values are recoverable (check UNAVAILABLE), every decision on rebuilt inputs for a model trained on archive covariates is **descriptive, not confirmatory**, until the check passes (revision 11). The failing channels are reported.

The covariates for these fires are **rebuilt** with `forecast/wildfire/environment.py` and will not reproduce the owner archive's hashes. Where the archive values are recoverable from committed files for an already-exposed fire, a rebuilt-vs-archive consistency check on that fire is reported before any b score.

### 1.3 Independence from fit fires (revision 3)

A candidate fire is excluded if, by metadata alone (the publisher's ignition or first-perimeter centroid and start date, never growth), **both** of the following hold for any FIT or SELECTED_ON ledger fire:
- Its centroid lies within **50 km** of that fire's catalog-rectangle centre.
- Its start date falls within **30 days** of that fire's catalog active window.

Exclusions are listed in the manifest with distance and dates. Daniel's FEDS↔ledger spatial matches (for example, FEDS 57413 Jack plus Devils Knob merged) are applied first as identity exclusions.

## 2. Intervals and lead times

- **Consecutive intervals (as forecast-v2):** consecutive distinct observation times t1 < t2 with 0 < t2 − t1 ≤ 48 h, chosen from timestamps only. Weather at floor_hour(t1) is repeated over the interval.
- **GOFER (hourly) and FEDS (12-hourly):** observation times are sampled to a fixed cadence before any scoring, fixed now at 12 h from each fire's first observation. This keeps the cadence comparable to NIROPS rather than chosen per fire.
- **Lead-time design:** from each cutoff, forecast to every later observation time within 48 h.

The 51 US2024 intervals longer than 48 h are excluded by the same frozen timestamp rule, so they are not scored. Their timestamps are not in git (they come from NIROPS). Recovering them is blocked by the same network refusal and is recorded as such.

### 2.1 Short-horizon stratum H (revision 14; declared before anything is scored on it)

**Why.** D1's claim is that a continuous-time formulation removes the hourly 4-cell reach cap. On NIROPS survey intervals of 12 h or more the cap never binds: in R, 0 of 1,310 tail positives were beyond reach (`derive/REACH.json`). Marcus's sizing, descriptive and unverified, says the cap binds for about 1–9% of new cells on hourly GOFER perimeters. D1's accuracy case therefore cannot show on NIROPS. H is where it can.

**Fires.**
- **Disclosure (revision 15).** Before this rule existed, at the orchestrator's request, Marcus (S-D1) ran a perimeter-only descriptive analysis on all 28 GOFER fires (s-d1 branch a902678, `gofer_cap.py`, `RESULTS_gofer_cap.json`). It computed per-fire shares of new cells beyond 4 cells/h and distance quantiles. No model, forecast, score or covariate was used. Every H fire, including future H-test members, therefore has its **label displacement statistics inspected (aggregate, label-only)**. This is recorded in the ledger. It does not change membership, because H is descriptive. Per-fire beyond-cap shares for H-test fires must not be used to tune a D1 candidate.
- These are the GOFER v0.2 fires (Zenodo 14642378) with no forecast fit or score in the project. They are **not untouched**: all 28 GOFER fires had aggregate label statistics inspected by S-D1 (see the disclosure above). Daniel's name match lists 17: Kincade, Walker, Bobcat, CZU, Dolan, Glass, July, KNP, LNU, McFarland, SCU, Slater & Devil, Tamarack, W-5 Cold Springs, Windy, Zogg and Beckwourth.
- They are filtered by §1.3, using point of origin and discovery date against every FIT or SELECTED_ON fire. Caldor 2021 (INSPECTED) is also excluded. Exclusions are logged.
- The survivors are ordered by `u = sha256("S-D9-A1|GOFER|" + GOFER fire name)` (same construction as §1.2).
  - The **first ⌊n/2⌋ form H-dev**: open to **both D1 and D2** for development (revision 15). Each use is logged in the ledger.
  - The **rest form H-test**: closed until the D1 candidate is frozen by SHA.
  - **Part-a overlap rule (revision 25; correction made after Owen's finding).**
    - *The problem.* Part a is the D1/D2 training pool, and some part-a NIROPS incidents are the same fires as GOFER fires. Fitting on their NIROPS brackets would let H-test fires tune a candidate. Owen found 5 such fires among the 42 part-a incidents Elena fits (≥ 20 surveys): Bobcat, CZU Lightning, KNP Complex, LNU Lightning (Meyers) and Slater ("Slater and Devil").
    - *The rule.* Let **F** be the GOFER fires that `cohort/GOFER_MATCH.csv` (sha256 451675c1…) lists with status MATCH or UNDETERMINED against an incident **kept in part a** in `cohort/COHORT_FINAL.csv` (sha256 d5ae66f4…). The rule covers every part-a use, not only Elena's 42.
    - *The set F.* Bobcat; CZU Lightning Complex; Creek (via Bullfrog); Glass; July Complex (Allen, Caldwell); KNP Complex; LNU Lightning Complex (Meyers); Slater and Devil; Tamarack; Zogg; Beckwourth Complex (UNDETERMINED, treated as matched); River Complex (UNDETERMINED, name-only via Kootenai). Creek and River Complex are FIT fires and are removed from H by §1.3 in any case.
    - *Assignment.* Every survivor in F goes to **H-dev**. The remaining survivors are ordered by u. With **n = the number of GOFER survivors after §1.3**, H-dev also takes the first max(0, ⌊n/2⌋ − |F ∩ survivors|) of them, and **H-test is the rest**. H-test therefore contains no fire in F by construction.
    - *Status.* Membership has not yet been computed. It is computed from metadata only, after this rule is committed, and logged in the ledger.
    - *Consequence, stated now.* With about 17 survivors and F holding 10 of them, H-test will hold about 7 fires. It remains descriptive (see "Status" below).
- Korean 2025 overpass detections (including the 25 March KFS_01 run) are **exposed** (KR2025 was scored by forecast-v2) and are reported **descriptively only**, never as H-test.

**Horizons.** Lead times of 1, 2, 3, 6 and 12 h from each cutoff, where the cutoff is a GOFER hourly perimeter time at least 12 h after the fire's first perimeter. Weather is held at the cutoff hour, as in §2.

**Strata (the D1-specific question).** Cells are split by the kernel's own geometry: **r = d_cheb / (4 × lead hours)**, where d_cheb is the chessboard distance in 375 m cells to the cutoff union (revision 15, per Marcus).
- **r ≥ 1** (beyond the hourly cap on every path) is the stratum where D1 should help.
- **r < 1** is the rest.
- **One-pixel tolerance (revision 15, per Iris and Marcus).** *Provenance:* this rule came from Marcus's label-only inspection of all 28 GOFER fires (see the disclosure above). It is a fixed rule and is not tuned per fire or per lead. Every r ≥ 1 result is reported twice: raw, and tolerant (d_cheb > 4 × lead + 6, one GOES pixel ≈ 2 km). **A D1 gain counts only if it is present under the tolerant definition.** Marcus's perimeter-only sizing: 8.9% of new cells raw vs 1.25% tolerant.
- **Label resolution per lead.** The ratio of pixel to reach is 2 km / (1.5 km/h × lead): 1.33 at 1 h, 0.67 at 2 h, 0.44 at 3 h, 0.22 at 6 h, 0.11 at 12 h. **The 1 h lead exceeds 1, so it is labelled "below label resolution" and not interpreted.**
- Note: the R reach diagnostic (`derive/REACH.json`) used Euclidean distance ÷ 1.5 km/h. Euclidean distance is never smaller than chessboard distance, so its r is never smaller than the Chebyshev r, and its "0 tail positives beyond reach" holds a fortiori.
These are reported by lead time, with entry, positive and fire counts. The primary H population is the r ≥ 1 cells within the horizon-scaled band (§4) plus the full domain. The 4 km NIROPS band is not used at hourly leads.

**Predictors.** The D1 candidate (SHA-frozen) and `d4_wind_seed0`, both on **rebuilt covariates** for every H fire. Also the **half-step-corrected hourly scheme** (Marcus's, SHA-frozen), which shows whether a simple correction matches first-passage at short leads. Also `d4_wind_recal`, `persistence` and `dilation_8h`; `logistic` too if its covariates can be built.

**Metrics.**
- Brier and paired Brier difference (D1 minus d4_wind, and D1 minus d4_wind_recal), with whole-fire bootstrap intervals (10,000 draws, seed 20261030).
- AP.
- Low-probability bins.
- The share of positives with r ≥ 1.
- Arrival RPS over the hourly leads, if D1 emits native cumulative marginals.

**Disclosure on every H result.** Each H result carries this line: "All GOFER fires, including H-test, had aggregate label displacement statistics inspected by S-D1 before H was declared (s-d1 a902678); no model output was inspected." D1's design may not be set from per-fire or per-lead statistics of H-test fires. Per-fire displacement numbers used for tuning come from H-dev only.

**Status: descriptive, not confirmatory.** The GOFER label definition (GOES-derived hourly perimeters) differs from NIROPS, and H-test will hold at most about 8 fires, below the §6.1 minimum of 20. A result on H can support or contradict D1's mechanism. It cannot carry a confirmatory accuracy claim.

## 3. Predictors

Every predictor is declared by SHA-256 before the manifest.
- **Models:** `d4_wind_seed0`, `c651_mc` (1,024 trajectories), and D1/D2 variants frozen by SHA. D1/D2 run on part c only.
- **`d4_wind_recal`** (revision 13): d4_wind_seed0 followed by a one-feature logistic recalibration on logit(p), **fit on part a only** and frozen by SHA before part c opens. It is a part-c comparator, so that a D1/D2 candidate cannot win merely by being better calibrated. Its marginals are for scoring only and are never used for the routing member draws.
- **Baselines on identical cells:**
  - `persistence`.
  - `dilation_8h`, fixed and never reselected.
  - Frozen `logistic`.
  - All of the 1/2/4/8 h dilations.
- **Later slots** must be declared before their first run. They include a perturbed-input physics ensemble (FARSITE, or ELMFIRE with its published inputs) and WildfireSpreadTS-trained learned baselines. **Any WildfireSpreadTS-trained baseline must list its training fires. A G, F or N fire that is in that training set is excluded from that baseline's comparison, and the exclusion is recorded in the ledger.**

**Covariate rebuild (resolved).** Running any predictor on a new fire requires building its covariates. Daniel measured the hosts the covariate builders depend on (`forecast/wildfire/environment.py`):
- **Refused:** archive-api.open-meteo.com, tds-proxy.nkn.uidaho.edu, lfps.usgs.gov, glad.geog.umd.edu and www.landfire.gov.
- **Reachable:** copernicus-dem-30m.s3.amazonaws.com and zenodo.org.

**Update:** the user has since approved unrestricted network access for this environment, and Daniel is rebuilding the covariates (a pilot on part-a fires, §1.2). The covariates are rebuilt rather than taken from the owner archive; see the consistency check required in §1.2.

### 3.1 Rebuilt-pipeline refits (revision 18; recipe frozen before any refit runs)

**Why.** Slope and tree cover cannot be checked against the archive (§1.2 item 14), so any model trained on archive covariates and scored on rebuilt inputs is descriptive. To give part c a confirmatory comparison, **every model scored on part c is trained and scored on one input pipeline**: rebuilt covariates from `rebuild_env.sh` (daniel/data-fetch; its exact commit is pinned in FREEZE.json).
- The archive-trained `d4_wind_seed0`, `c651_mc` and `logistic` stay as **labelled descriptive rows**.
- If the owner supplies archive values and item 14 passes, they can be promoted by amendment before part c opens.

**Training data, identical for every refit and for every D1/D2 candidate.** It is the union of:
- The 23 forecast-v2 US fit fires, rebuilt. They are already exposed as FIT.
- The **part-a training pool** (`cohort/PART_A_ALLOWLIST_FINAL.csv`, sha 7db3cc0e…; corrected from the superseded 801acdd8… by item 21, following item 20). An incident is used only if it has at least 2 surveys and a buildable grid.
- Intervals follow §2's rule (0 < Δ ≤ 48 h, timestamp-only), with all eligible intervals per fire. Build failures are logged, never replaced.
- No US2024, KR2025, part b/c/d or H-test fire is used.

**`d4_wind_rebuilt`** follows the forecast-v2 recipe exactly; only the training fires and the covariate pipeline change.
- Source: `research/forecast-v2/scripts/pipeline.py` (sha256 88d376d2…2d67), invoked as forecast-v2 invoked its final stage (`run_campaign.py` sha256 7d089b86…b74d): `pipeline.py final --variant d4_wind --max-fit-intervals-per-fire 0 --intervals-per-epoch 0`.
- Hyperparameters: the `fitting` block of `research/forecast-v2/RUN_PROTOCOL.json` (sha256 c2dce7f7…8243). That is epochs 3, seed 0, hidden_channels 16, kernel_size 9, learning_rate 0.003, weight_decay 1e-4, samples_per_step 1, training crop = cutoff initial extent + 10 cells with zero exterior, biome emphasis training-only inverse-sqrt, threads 2. Variant d4_wind: prior free, frame wind, d4 true.
- There is **no development-fold selection**: the variant is fixed, so nothing is selected. There is one seed.
- The checkpoint SHA is recorded in FREEZE.json before part c opens.

**Required deviations, frozen before any refit (revision 19, from Marcus's reading of `pipeline.py`).**
1. **Command line, verbatim** as `run_campaign.py` built it. CLI defaults differ (samples-per-step defaults to 4, and `--balance` is off by default):
   `pipeline.py final --variant d4_wind --seed 0 --epochs 3 --hidden 16 --lr 0.003 --samples-per-step 1 --threads 2 --n-samples 1024 --balance --max-fit-intervals-per-fire 0 --intervals-per-epoch 0`
   weight_decay 1e-4 and kernel 9 are internal. Marcus confirms they cannot be overridden from the CLI.
2. **Input pins.** A reviewed copy of `pipeline.py` adds `--input-manifest PATH`: a JSON map of path → sha256 for every rebuilt file, written by `rebuild_env.sh`, including `baseline-terrain/<event>/elevation_m_375m.tif`. The map is passed to `Environment(input_sha256=…)`. The frozen original is untouched. The copy lives at `research/harness-2026-11/s-d1/refit/` and **its sha256 is recorded in FREEZE.json before any refit runs**.
   - **Implemented as a wrapper, not a diff** (Marcus). `research/harness-2026-11/s-d1/refit/run_pipeline_rebuilt.py`, sha256 264deaeae7dc532bbfa27e55d35d3def7c01eb0c7f85cdf358ee529b866e1d1d, commit 6dcf3f9 on harness/s-d1-first-passage.
     - It refuses to run unless pipeline.py hashes 88d376d2… and RUN_PROTOCOL.json hashes c2dce7f7….
     - It loads pipeline.py unchanged and injects, in memory only, (a) an `Environment` subclass that passes `input_sha256` from `--input-manifest`, so every read still goes through the unmodified `_verify_path`, and (b) the `--train-events` list in place of `SPLIT["fit"]["us_perimeter_and_kriged"]`. SPLIT.json is untouched.
     - It writes `REFIT_RECEIPT_<command>.json`.
     - It passed a smoke test end to end on the forecast-v2 synthetic fixture.
   - Marcus confirmed these are not CLI-overridable: kernel 9 and dropout 0.0 are literals (pipeline.py:336), and weight_decay is `fit_mean_field`'s default of 1e-4 (survival.py:327).
   - The initial rate comes from the training-set prevalence, so it legitimately depends on the pool.
3. **Training events.** The same copy adds `--train-events FILE` (the fit-23 fires ∪ eligible part-a incidents) in place of the hard-coded SPLIT fit list. The list is recorded in each result.json. **No other code change is allowed**, except the loss and fitting-procedure replacements of the two named D2 candidates below (revision 21).
4. **Part-a grid rule:**
   - EPSG:5070, 375 m cells, aligned to multiples of 375 m (the Choi reference-grid convention).
   - Extent = bounds of the union of all of the incident's NIROPS survey perimeters, plus 2 km.
   - This is the rule in Daniel's builder, which reproduces the archived Moose, GreenRidge, Dixie and CameronPeak grids exactly.
   - *Disclosure:* the extent uses the final union of perimeters (hindsight), as forecast-v2's archive rectangles did. It does not establish prospective landscape detection.
5. **Part-a time window.** start_utc = floor_hour(first survey UTC) and end_utc = ceil_hour(last survey UTC), written to `events.json` entries by the builder. Intervals that `Environment.available_at()` skips, for example missing cutoff weather, are **logged with their reason** and never replaced.
6. **Determinism.** One run with seed 0. The torch version differs from the archive host (2.5.1 there), so bitwise equality with the archive pipeline is not expected or claimed.

**`logistic_rebuilt`** uses `forecast/wildfire/baselines.py` (sha256 325abbe7…afbb1f):
- Features: `hand_features` with an elevation-gradient directional slope and the same 14 biome codes (the feature list in `forecast/runs/20261030_perimeter_trained/execution_v3/baselines/logistic.json`).
- Fit: `fit_logistic(C=1.0, seed=0)`, negatives subsampled at 0.05 and inverse-weighted.

**`d4_wind_recal`** (§3) is redefined on top of `d4_wind_rebuilt`: a one-feature logistic recalibration fit on the same training data.

**`dilation_8h`** has no fitted weights, so it is unchanged.

**Rate-mixture candidate** (development first, per Iris; added as a part-c comparator only if it performs in leave-one-fire-out development on R): `d4_wind_rebuilt` run at global rate multipliers m ∈ {1, 2, 4, 8, 16}, with mixture weights fit on the training data. Once weather covariates exist, a development check also tests whether the fast tail intervals are predictable from wind; if they are, one wind-dependent weight parameter is allowed. The final form is frozen by amendment before part c opens.

**D2 candidates: loss or likelihood-procedure deviations (revision 21; declared before either refit runs).** Two named D2 candidates use **the identical recipe** above: the same training data, rebuilt inputs and input pins, Marcus's wrapper (264deaea…) and its hash guards, the same command line and hyperparameters, seed 0, and receipts. `d2_nll_rebuilt` **replaces only the training loss**. `d2_bracket_rebuilt` replaces the loss **and** the fitting procedure (an EM over latent arrival times), and nothing else. The replacement is injected in memory the same way as Marcus's wrapper, and `pipeline.py` and `survival.py` stay unchanged.
- **`d2_nll_rebuilt`.** The mean-field model is trained with **Bernoulli negative log-likelihood** on the mean-field p(t2) in place of the Brier loss of `survival.fit_mean_field` (survival.py:334). It keeps the same weights and the same prevalence scaling. This is the same-regime NLL baseline Iris asked for.
- **`d2_bracket_rebuilt`.** The same recipe plus **latent arrival-time augmentation within each survey bracket**. The E-step imputes each cell's arrival time inside (t_k, t_{k+1}] given the current model. The M-step maximizes the complete-data likelihood. It is fit under the same 3-epoch budget. **If it cannot finish within that budget, it is reported as not admitted, and the budget is not changed.**
- **Code and freeze.** The code lives in `research/harness-2026-11/S-D2/refit/`. Each wrapper's sha256 is published for review and recorded in FREEZE.json **before it runs**. Neither candidate may change the training data, covariates, hyperparameters, architecture or seed.
- **Admission to part c.** Both remain subject to §5.2: each must emit multi-observation cumulative marginals natively, demonstrated on R before its SHA freeze. Both are judged by §6.1, criteria 1–4 included.
- **Soft-risk-set arm: development only.** It needs kriged arrival inputs, which exist only for the 23 fit fires, so it is **not a part-c candidate**.
- **Hypothesis, recorded before any D2 refit (Elena, S-D2).** Ignoring within-bracket timing cuts the fitted spread rate by about 3–4×. **`d2_bracket_rebuilt`, not `d2_nll_rebuilt`, is therefore the arm predicted to shrink d4's near-zero tail without recalibration.** The prediction is fixed in the following wording, which Elena confirmed before any refit.
  - **Prediction P-D2.** It applies in the 4 km band, relative to `d4_wind_rebuilt`, on the same cohort and the same intervals, with no recalibration of any arm. All three parts must hold:
    - (a) **The tail shrinks:** fewer positives at p < 1e-5 **and** fewer at p < 1/1024 (§5).
    - (b) **The band is not inflated to get there:** the lowest-bin calibration gap, |mean p − observed frequency| over p in [0, 1e-3), is smaller than `d4_wind_rebuilt`'s.
    - (c) **Brier is not worse:** the whole-fire bootstrap 95% interval of the pooled band Brier difference (D2 − `d4_wind_rebuilt`; 10,000 draws, seed 20261030) does not lie entirely above zero.
  - **Ordering (also a hypothesis, recorded now).** `d2_bracket_rebuilt` moves (a) and (b) more than `d2_nll_rebuilt` does. **If `d2_nll_rebuilt` matches `d2_bracket_rebuilt` on (a), that falsifies "within-bracket timing is the cause"** and points to the loss change alone.
  - P-D2 is a stated scientific prediction. It does not change §6.1: admission and the decision criteria are unchanged.
  - *Motivating evidence (development, part a, Elena's stream; **not verified by Hannah**).* It comes from covariate-free spatial fits on NIROPS part-a brackets: 42 fires with ≥ 20 surveys, from allowlist 7db3cc0e at 2d40d170, first 240 h. On one fire (CooksPeak), the fitted total spread rate was 0.018/h plug-in (first observation time), 0.026/h mean-field NLL, 0.065/h composite likelihood and 0.069/h MCEM. A 24-fire run is pending, and its result is evidence for the hypothesis, not a change to it.
  - If P-D2 or the ordering fails, the failure is reported as stated, whatever the §6.1 outcome.
  - *Development evidence on synthetic data (Owen, S-D2 verification; recorded beside the hypothesis, **not a revision of it**; not verified by Hannah).* The full latent-time method recovers the total rate with a small upward bias (ratio 1.025–1.040) and wins on held-out likelihood when given perimeter brackets. It is **worse than the composite likelihood on kernel shape** at 12–24 h brackets, and worse than simple arms on kriged inputs. (Elena confirmed this description.)
  - *Real-data part-a estimator agreement (Elena with Owen; 25 fires; **unverified**).* Fitted rates relative to MCEM: plug-in 0.454, mean-field NLL 0.587, composite 0.967. **This is agreement between estimators, not accuracy against truth** (Iris): real fires have no known rate.

### 3.2 Development-first candidates (revision 23; declared before any refit runs)

These two candidates are developed **first on the training pool (fit-23 ∪ part a) and on exposed data (cohort R, H-dev)**. Each enters part c **only by an amendment committed before part c opens**, with its SHA, its receipts and the §5.2 native marginals demonstrated on R. Until then each is development-only and never part of a §6 decision.

**(1) Full-rectangle validity arm, `c651_fullvalid_rebuilt`.** It isolates the "never saw a cell that stays unburned" defect (§4.1 provenance table).
- *Which models it changes.*
  - c651 is the only scored model trained on hindsight-restricted labels. The arm is therefore defined as a **refit of the c651 recipe** with exactly one change.
  - `d4_wind`, `d4_wind_rebuilt`, `logistic` and `logistic_rebuilt` already train on perimeter states over the full crop. **For them the arm changes nothing**, and no new d4 or logistic model is created.
- *Recipe.* c651's recorded candidate configuration is kept: `forecast/runs/20261010_categorical_balanced_benchmark/candidate_selection.json`, candidate `mixed_3_5_7_9_02_lr0.1_warmup_cosine`, which is kernel sizes 3/5/7/9 mixed with nonnegative mixing, CNN branches, hidden 64, depth 1, dropout 0.15, learning rate 0.1, weight decay 0.01, warmup-cosine with a 4,096 horizon, 32 warm-up epochs, minimum factor 0.01 and restart period 512, and 512 epochs. Its training events and splits, its sampling limits and its validation-based best-epoch rule are also kept. It is run on the §3.1 rebuilt covariates plus the Choi kriged arrival rasters, and the seed is recorded.
  - *What committed files pin (Marcus, from the c651 checkpoint's own contract).* There are 44 events.
    - Training and validation (a cell-hour split within the same fires) use **25 events**: KFS_02, KFS_03 and the 23 forecast-v2 US fit fires.
    - The test set is KFS_01/04/06/13 plus the six US2024 fires. KFS_05/07/09/11/12/14/15/16/17 are unused.
    - The population condition is "complete K = 9 context, ≥ 1 burned neighbour". The categorical balance is inverse-sqrt with min_freq 0.001, max_factor 10 and chunk 512. The cache metadata sha256 is 6cd4ae58…. The training seed, 7, is **not** stored in the checkpoint. It comes from `forecast/runs/20261010_categorical_balanced_benchmark/protocol.json` (`"seed": 7`) (Hannah).
    - The arm keeps all of these.
  - *Not committed: the cache's `metadata.json`.* The negative-sampling limits, the split seed and fraction, and the chunking are pinned only by that hash.
  - **Gate before the recipe is frozen.** Row sampling depends only on the arrival rasters, the seed and the limits. Marcus re-runs it on the Choi rasters with the candidate limits, and it must reproduce the committed sampling totals. If it does, the limits are recovered and recorded here by amendment before any training. If not, the owner's `metadata.json` is required, and the arm waits.
    - *Correction, disclosed.* As first written, the gate quoted an inconsistent set of targets: 158,561 is the native-9×9 train row count, while 34,481,268.6405 and 64,420 are the **base** train weights. Train-only totals also depend on the split RNG of the cell-hour train/validation re-split. The gate is therefore applied to the **pooled train + validation totals before the environment filter** (`forecast/documents/weighted_stratified_split_20261009.json`): base 249,085 rows, 80,519 positives and weight 43,104,713.278; native 9×9 198,337 rows, 77,993 positives and weight 7,406,169. Victor re-summed these from the committed file. This correction was made after Marcus's run, and it changes the reference file and pooling, not any tolerance.
    - **Result: PASS for recoverability** (Marcus; `research/harness-2026-11/s-d1/refit/c651_sampling_gate.py` sha256 153bf393…7cf63, `RESULTS_c651_sampling_gate.json`, harness/s-d1-first-passage 03b55002d9c488adfdd6eb350e2f2b631b2ad7a0; the script hash was re-checked by Victor).
      - With kernel 9, contact limit 5,000 and no-contact limit 2,000, the pre-filter totals are base 249,093 / 80,523 / 43,104,756 and native 198,341 / 77,997 / 7,406,173. That is exactly 8 rows more than committed, namely 4 contact positives and 4 cold negatives that the environment-validity filter dropped with no refill (prepare.py:958–962).
      - The **test-split totals match exactly** (base 61,965 / 11,924 / 3,505,209; native 45,391 / 10,113 / 287,415).
      - The alternatives are excluded. (4,000, 2,000) and (5,000, 1,000) miss the base rows by about 24,000. (6,000, 1,000) and (4,000, 3,000) miss the native rows by about 24,000. Kernel 7 misses the base rows by 13,508 and the native rows by 11,752 (Hannah's re-run).
      - Recovered and fixed for the arm: **kernel 9, contact limit 5,000, no-contact limit 2,000**. The Choi rasters agree with the archive arrival rasters for these events.
      - **Assumption, not identified:** the sampling seed. The totals do not depend on it. Seed 7, the CLI default and the recorded protocol seed, is used.
      - With rebuilt covariates, the environment-filter rejections will differ from the archive's 8. They are reported per event in the refit receipt.
  - *Dependencies (Daniel: feasible).*
    - **Weather.** The repo's weather stage already fetches every hour of each event's window, so sampling the full window adds no requests. The cost depends on the number of O1280 nodes times days. For the 25 events it is about 5,860 weighted Open-Meteo calls with the slim rebuild, or about 7,980 with the full one. The free-tier limits are 10,000 calls a day and 5,000 an hour, so this takes **one daily quota** spread over at least 2 h, or 1–2 days if the earlier limit was shared by IP. (events.json gives KFS_02 a 194 h window.)
    - **Korea.** KFS_02 and KFS_03 on EPSG:5179 need no new code. `environment.py` branches on country, and the global DEM, land cover, biome and weather sources apply, while the US-only stages skip. This has not yet been run on KR; Daniel runs a non-weather smoke test first.
      - *Smoke test passed (non-weather), Daniel.* For KFS_02 and KFS_03 on EPSG:5179, the terrain, land-cover and biome stages ran with rc 0, and every output is on the exact events.json grid. Pin: `research/harness-2026-11/data-fetch-3/kr_smoke/` at daniel/data-fetch-3 3b2c2fbb920a255052fa5c08eeb2d0bdc7a6bb16, with `kr_check.py` sha256 d3683886…8760. Victor re-checked the script and two raster hashes.
      - 10 of the 1,937 arrival-valid cells on KFS_02 have no biome value, because they fall on coastal sea, and are masked. KFS_03 has 0 such cells. In the refit these become environment-filter rejections, reported per event.
      - The KFS_02 window is 194 h, from events.json, which prepare.py uses. Marcus's earlier 360 h came from catalog.csv.
  - **Trainer (decision, revision 23).** c651 was not trained by `forecast/wildfire/train.py`. It came out of the categorical-balanced kernel **search** (`runs/20261010_categorical_balanced_benchmark/protocol.json`), whose current equivalent is `wildfire.search` `MixedSearch`, and that trains every candidate before selecting. **Both arms restrict the search, by an in-memory injection, to the single candidate `mixed_3_5_7_9_02_lr0.1_warmup_cosine`, keeping its validation best-epoch rule** (Marcus's option b).
    - *Why.* The arm exists to isolate label validity. Re-running the whole search would add a second change, a possibly different selected configuration, and would cost many candidates × 512 epochs per arm.
    - *Limitation, stated now.* Under full-rectangle validity a different configuration might be selected. That is not tested.
  - **Code version.** "The c651 recipe" means **the recipe as implemented by the current refactored code**: prepare.py e2c70433…, train.py 9c8a6215… and data.py 8fb447ab…, plus the `wildfire.search` path, all sha-checked by the wrapper. The archived trainer files differ. For example, the pre-refactor `wildfire_burned_area_hourly/probability_model/train.py` had sha256 23d8a25e…, recorded in c651's `protocol.json` (`training_source_sha256`) and in `refactor_20261010.json` (`before_maintained_source_sha256`). No file with that hash is in the working tree.
    - The committed refactor record (`forecast/documents/refactor_20261010.json`) documents the module moves, 1,437 passing tests and exact loading of 560 checkpoints. By its own scope, it does **not** establish retraining equivalence ("no full model retraining or new scientific/operational validation").
    - Therefore the reference for the arm is the **unchanged-recipe refit on the same current code and inputs**, not the archived c651 checkpoint. Any comparison with the archived c651 is labelled descriptive.
  - *Runner and cost.* Marcus runs it with a pinned in-memory wrapper. The unchanged-recipe comparator is the same wrapper with the injection switched off, so the two arms share every other byte. Each arm takes hours on CPU.
- *The one change.* `forecast/wildfire/prepare.py` admits a target only if its whole k × k neighbourhood has a finite arrival time (lines 862–883), and label validity comes from the arrival raster (`data.py:477-492`). In the arm, **cells with no arrival value inside the event rectangle are known unburned for the whole event**, and the neighbourhood rule requires only that the window lie inside the rectangle.
  - The basis is §4.1 rule 5, which is verified cell for cell on 29 exposed US fires.
  - For Korean kriged-only training fires it is an **assumption** (no perimeters exist), and that is disclosed.
  - The change is injected in memory, with prepare.py and train.py unchanged and their shas pinned. The wrapper sha goes in FREEZE.json before the run.
- *Comparison (development).* `c651_fullvalid_rebuilt` against a refit of the unchanged c651 recipe on the same rebuilt inputs, scored on cohort R (full rectangle) with the `C651_DEV` decomposition: full domain, 4 km band, off and on the final footprint, and tail against the 1/1024 floor.
- *Hypothesis, recorded now (Iris).* The off-footprint Brier excess largely disappears, and the on-footprint score is not materially worse.

**(2) Cheap rate candidate, `rate_composite`.**
- *Definition.* The kernel shape is fit by the **composite (independent-bracket) likelihood**. Then **one scalar rate, or a small grid of rates** (at most the §3.1 rate-mixture grid m ∈ {1, 2, 4, 8, 16}), is fit by the bracket likelihood with the shape held fixed.
- *Step 1, synthetic, before any refit.* On Elena's synthetic harness, it is compared with the full latent-time method (`d2_bracket_rebuilt`'s estimator) on rate recovery (ratio to truth), held-out likelihood, kernel-shape error, wall time and peak memory, with brackets of 12–24 h and perimeter-type inputs.
- *Scale fit, clarified (Elena).* The scale is fit by the **bracket likelihood** with the shape held fixed. That means a one-parameter latent-time EM, or the grid m ∈ {1, 2, 4, 8, 16}. Its E-step costs as much as the full method's, and only the M-step is cheaper, so **the expected cost advantage is modest**.
- *Regimes, fixed before step 1 (Elena).* Seeds 0–4 are used in both regimes.
  - **Slow:** the verified Markov setting (crossing time ≈ 6.6 h), with 12 h and 24 h brackets.
  - **Fast:** the same kernel × 4 (crossing time ≈ 1.7 h), with 12 h and 24 h brackets.
- *Disclosure of a pre-threshold run (Elena, S-D2 commit d68d790f, `results/composite_scale.md`).* Before this rule existed, a **different** estimator was run at Iris's request: composite shape plus a **moment-matched** scalar scale, with m chosen so that exact forward simulation matches the observed new-burn count. That is not the bracket likelihood.
  - Over 8 replicates, its rate ratios were 1.086, 1.177 and 1.367 at 6, 12 and 24 h, and 1.293 with spotting, against 1.03–1.10 for MCEM. Its held-out NLL beat MCEM in 0–1 of 8 replicates.
  - That estimator is **excluded**. It is labelled exploratory and pre-threshold, and it does not inform the thresholds below.
- *Matching rule.* Marcus's amendments were adopted, and Elena agreed before step 1 runs. The design uses ≥ 5 seeds per regime, paired by seed, in **at least a slow-run and a fast-run synthetic regime**. The fast-run regime is where the tail lives. **All three conditions must hold in both regimes:**
  - **Rate:** the error is |log(r̂ / r)|. The full method's mean advantage over seeds, as a difference of these errors, is ≤ 0.05.
  - **Likelihood:** the mean paired held-out log-likelihood difference (full − composite) is < 2 × SD(paired differences) / √seeds.
  - **Shape:** the composite's kernel-shape error is no worse than the full method's, within the same paired 2-SE tolerance.

  If all three hold in both regimes, **`rate_composite` is the rate candidate refit on the training pool**, under the §3.1 recipe and the §4.1 rule 3 label rule. Otherwise the full method stays the rate candidate.
- `rate_composite` does not replace `d2_bracket_rebuilt` as a D2 candidate. P-D2 and its ordering stand as recorded.

**Iris's ranking of SMOKE experiments (planning order, not a decision rule).**
1. The full-rectangle validity arm.
2. The rate fit, cheap version first.
3. The rate-mixture and recalibration comparators.
4. The half-step correction on real data.
5. The first-passage sampler, on the hourly stratum H only.

**Who runs it.** Marcus (S-D1) runs the baseline refits, and Elena's D2 refit uses the identical training data and pipeline. Every refit writes a receipt with input hashes, code SHA, seed and wall time.

## 4. Scoring population and strata

- **Full domain (as forecast-v2):** initially unmapped cells inside the fixed rectangle, on the intersection of the validity masks. Reported as a fixed secondary.
- **Primary band (revision 1, applied):** `dist_m` ≤ **4,000 m**, where `dist_m` is the Euclidean distance between cell centres on the 375 m grid to the nearest cell of the cutoff mapped union. This was chosen by the rule committed at 3eb31a38: the smallest of 1/2/4/8/16 km holding at least 90% of R's positives.

  R's pooled positive share within each width, measured:

  | width | 1 km | 2 km | 4 km | 8 km | 16 km |
  |---|---|---|---|---|---|
  | share | 0.663 | 0.847 | **0.960** | 0.995 | 1.000 |

  Per fire at 4 km, the share ranges from Wapiti 0.932 to Goat, Red Rock and Pioneer 1.000. Per horizon at 4 km, (12,24] h is 0.933. The R distances were derived from committed files with checks that passed (`derive/derive_dist.py`).
- **Every primary table** carries the out-of-band positive count and share, per fire and per horizon.
- **Secondary bands:**
  - Cumulative widths of 1, 2, 8 and 16 km.
  - Annuli (0,1], (1,2], (2,4], (4,8] km.
  - **A horizon-scaled width** of max(1 km, 4 km × h / 24 h), anchored to the primary width at 24 h.

  The band is itself a dilation and favours dilation baselines near its radius. All widths are shown side by side.
- **Non-burnable secondary (revision 16).** The band score is also reported **excluding cells classed non-burnable or covariate-missing**, with the count and share of positives removed, per fire.
  - The class is defined **from covariates only** (fuel / land-cover code and validity flags), never from the endpoint or from enclosure, because enclosure uses the outcome. **Proposed and accepted by Iris: FBFM40 codes 91–99.**
  - **Vintage:** LANDFIRE 2016 FBFM40, as used by the archive and the rebuilt builder. It predates every 2020–2024 NIROPS fire, so "non-burnable" describes the pre-fire landscape and not post-fire reclassification. A later LANDFIRE version would need an amendment.
  - The exact code list is fixed in an amendment once Daniel's US2024 fuel layers exist, and **before** any untouched score.
  - **The primary population is unchanged.**
  - This secondary was added after a development finding on R.
- **Horizon strata:** (0,12], (12,24], (24,36], (36,48] h, by interval duration and separately by lead time, with entry, positive, interval and fire counts.
- **Domain stratum (requested by Elena, S-D2):** where an `in_domain` mask is supplied (the kriging domain), the same metrics are reported inside and outside it.

### 4.1 Scored population: full grid vs hindsight-restricted (revision 22)

**Finding, checked from code and committed files.**
- *Loader.* `forecast/wildfire/data.py:477-492` takes the label-validity mask, `burned_area_valid`, from the valid mask of `arrival_time_hours.tif`. A cell has a known burned state only if it has a reconstructed arrival time.
- *forecast-v2 KR2025.* `korean_samples` (`research/forecast-v2/scripts/score_cohorts.py:58-80`) scores `finite(arrival) & ~initial`. **Every scored Korean cell has a finite reconstructed arrival time, so every one burns eventually.** Prevalence in the committed files: KR2025 404 / 1,792 = **22.5%**; US2024 (cohort R) 8,520 / 1,705,079 = **0.50%**.
- *forecast-v2 kriged training.* `kriged_samples` (`pipeline.py:253-288`) applies the same restriction, but it feeds only the `mixed_base` variant (`mixed=True`). `d4_wind` and `logistic` are fit on perimeter samples only (`pipeline.py:347-358, 533`).
- *Raster extent.* For FishCreek, the archive arrival raster has 2,642 valid cells out of 7,519 (`forecast/demonstration/burn_state_coverage/summary.json`, source sha f69a283c…). That **equals** the number of cells in FishCreek's final NIROPS union on the same 103 × 73 rectangle (derived from R as in `derive/enclosure.py`).
  - This is a count match, not a per-cell comparison. The raster is not in the repository.
  - The Korean arrival rasters could not be inspected here.
  - Daniel's rebuilt part-a `arrival_time_hours.tif` is defined as the stepwise first-mapped survey time (data-fetch README), so by definition it is empty outside the final mapped union. This was not opened here.
- *Cohort R is not affected.* `perimeter_samples` (`pipeline.py:224-250`) scores `~initial` over the whole fixed rectangle, with labels from the NIROPS perimeter states. Arrival validity plays no part. The rectangle's extent is itself hindsight, which is already disclosed (§3.1 item 4). No number reported for R changes.

**Rules.**
1. A population is **hindsight-restricted** when the validity of its labels, or the set of cells it scores, comes from the final reconstruction: a finite arrival time, `arrival_valid` or `burned_area_valid` from an arrival raster. Otherwise it is **full-rectangle**: every cell of the grid that is unburned at cutoff is scored. NIROPS parts a–d, cohort R and stratum H (GOFER perimeters) are full-rectangle. Stratum K and the forecast-v2 KR2025 results are hindsight-restricted.
2. The harness records the population (`sd9bench` `population`: `full_rectangle` | `hindsight_restricted`). Every hindsight-restricted result carries a note saying that its Brier, calibration, AP and prevalence are **not comparable** with full-rectangle results. **The two are never pooled, paired or used in one decision.** §6 decisions use full-rectangle populations only.
3. **Training and part-c scoring paths for every A1 model** (the rebuilt refits, `d2_nll_rebuilt`, `d2_bracket_rebuilt`, D1 candidates) must take label validity from perimeter states over the full grid, as `perimeter_samples` does. They may not take it from an arrival raster. The receipt of any path that reads an arrival raster must state how that raster's validity is used. The D2 bracket E-step may impute arrival times **within survey brackets** for cells that are burned in the perimeter states. Cells never mapped as burned remain negatives over the full grid.
4. Any forecast-v2 KR2025 number quoted in S-D9 reports is labelled hindsight-restricted and descriptive.
5. **Definition (Iris), checked cell by cell for the US (revision 24).** *Rule as written:* "arrival no-data" means "outside the final footprint" once the arrival raster's valid mask equals the final perimeter union cell for cell on every **exposed** fire that has both.
   - *Result (Daniel).* On all **29 exposed US project fires**, which include the six cohort-R fires, the kriged arrival-valid set **equals** the final NIROPS union cell for cell: |valid ∖ union| = |union ∖ valid| = 0, over 159,522 cells in total.
     - Grid shape, transform and EPSG equal `events.json` and the archive raster on all 29.
     - NIROPS was read per incident with an attribute filter, and no part b, c or d fire or H-test fire was opened.
     - Pins: `research/harness-2026-11/data-fetch-3/arrival_vs_union/arrival_vs_union.py` (sha256 c847e3df…de40) and `arrival_vs_union.csv` (sha256 32dd3982…ab31) at daniel/data-fetch-3 f5342c29d44a1ca1faf5e4448502f91300694c40. The hashes and the 29 identical rows were re-checked by Victor.
     - *Disclosure:* for RedRock, the union derived from R (the last scored interval) is 2,283 cells against 2,285 for the final survey union, because R's last scored interval precedes the final survey. It shifts the `C651_DEV` off-footprint split by at most 2 cells per interval on one fire.
   - **The definition therefore holds for the US kriged rasters.** For **Korean** rasters it cannot be checked, because there are no perimeters. It remains an **assumption**. Daniel reports valid shares from 28% to 59% of each rectangle on the 15 KR2025 rasters, as counts only.
6. **Repaired Korean stratum K-full (Iris; declared now, descriptive).** If rule 5 holds, a second Korean stratum is scored on the **full event rectangle**. Cells with no arrival value count as never burned, so the population no longer conditions on eventual burning. K-full is labelled `full_rectangle` but stays **descriptive**: its timing is kriged and the fires are exposed. It is never part of a §6 decision. *Availability:* the committed forecast-v2 KR2025 files hold predictions only on finite-arrival cells. K-full therefore needs the predictors re-run over the full rectangle, which needs the owner-only inputs. It is **UNAVAILABLE** for the current models until those inputs exist.
   - *Timing evidence on Korean kriged labels (Leo, F-DYN, commit 68b0b23, `research/harness-2026-11/F-DYN/ahi_results/README.md`; geostationary rule fixed before computing; **Nora's verification pending, not verified by Hannah**).*
     - **Finding.** On KFS_01, 25 Mar 2025, pixel-level AHI first fire clusters at 06:24–09:24 UTC, about 7–10 h before the kriged arrival burst at 16:24–17:24 UTC. For the 323 cells MODIS first detects at 12:25 UTC, the kriged arrival is a median 4.8 h **later** than that detection.
     - **Caveats (Leo's).** The pixels are 2 km. The daytime false-alarm rate is 3.75%, and PSF bleed and left-censoring are present.
     - **Bearing on A1.** In such runs, kriged "truth" can lag real arrival by hours. Every K and K-full result therefore carries this as a stated label limitation, in addition to the hindsight restriction. This is a further reason that K and K-full stay descriptive and never enter a §6 decision. Nothing about NIROPS-perimeter populations changes.

**Training-label provenance of the predictors (revision 22; development fact, checked from code).** The same validity mask also governs **training** (Iris). A model trained on hindsight-restricted labels never saw a cell that stays unburned.

| predictor | training label source | evidence |
|---|---|---|
| `c651_mc` (checkpoint c651f672…, run 20261010_categorical_balanced_benchmark) | **Hindsight-restricted kriged, interior only.** Targets are cells whose whole k × k neighbourhood has a finite reconstructed arrival time, so every training target, positive or negative, lies inside the final footprint at least k/2 cells from its edge | `forecast/wildfire/prepare.py:862-883` (`neighborhood_known = minimum_filter(finite, k) > 0`); label validity from `data.py:477-492`; training contract "boundary: unknown; complete interior patches only" (`train.py:371`) |
| `d4_wind_seed0`, `d4_seed0`, `base`, `ellipse`, `burnout`, `burnout_spotting` (forecast-v2 final) | **Perimeter states, full crop**: score_mask = ~initial over the initial-extent crop + 10 cells | `pipeline.py:347-353` with `mixed=False` |
| `mixed_base_seed0` | **Mixed**: perimeter states plus kriged windows (`finite & ~initial`, including Korean kriged-only fires) | `pipeline.py:354-358` (`mixed=True`), `kriged_samples` 253-288 |
| frozen `logistic`, `dilation_best` / `dilation_8h` | **Perimeter states** (fit fires) | `pipeline.py:532-550` (`mixed=False`) |
| `persistence` | none | — |
| `d4_wind_rebuilt`, `logistic_rebuilt`, `d4_wind_recal`, `d2_nll_rebuilt`, `d2_bracket_rebuilt`, D1 candidates | **Perimeter states, full grid (required by rule 3)** | §3.1, §4.1 rule 3 |

*Hypothesis only (Iris), not tested here.* A model trained without true far-field negatives has no reason to be calibrated on cells far from the front. This may bear on c651's tail behaviour. It does not explain d4_wind's tail, because d4_wind was trained on perimeter states (§4.1 table; `derive/LOGISTIC_DEV.md`).

## 5. Metrics

Computed by `sd9bench`, with definitions identical to `forecast/wildfire/baselines.py` where one exists:
- Brier, BSS against persistence and against `dilation_8h`, and `base_rate_bss` (a diagnostic).
- AP and ROC AUC.
- Ten equal-width reliability bins, plus low-probability bins with edges 0, 1e-5, 1e-4, 1e-3, 1e-2 and 0.1, by stratum.
- ECE.
- Clipped NLL (floor 1e-7) and the exact-NLL flag.
- **Zero-probability positives:** the exact count and share, plus **positives with p < 1/1024** (revision 6). 1/1024 is the resolution floor of a 1,024-trajectory MC model, which makes MC and mean-field models comparable.
- **Burned-area CRPS** from stored trajectory area samples only. There is no independence approximation.

### 5.2 Arrival score (revision 7)

The score is the RPS over observation-censored arrival bins, on **all** cells of the band (not only burned cells). It is the sum over observation times of the Brier score of the cumulative marginal, which is Iris's discrete right-censored CRPS. Implemented: `sd9bench/arrival.py`.

**Revision 7 outcome:** the multi-observation cumulative-marginal export could not be run on R. The model inputs are owner-only (confirmed by Daniel and Marcus), and the covariate hosts were blocked at that time. The arrival RPS is therefore **declared UNAVAILABLE for `d4_wind_seed0` and `c651_mc`** in this addendum. It cannot be added for them after freeze. **Every new D1/D2 candidate must emit multi-observation cumulative marginals natively** (revision 9), so the arrival score exists for the models it was designed for. The export must be demonstrated on R before the candidate's SHA freeze. A candidate without it is not admitted to part c. An interval-censored variant that does not penalize mass inside a true bracket is a secondary, used only where brackets exist.

## 6. Primary statistic and decision

### 6.1 Primary (cohort N: part c for each SHA-frozen D1/D2 candidate; part b for a later named candidate; C2 under the base protocol)

The primary statistic is the **pooled paired Brier difference** in the 4 km band, candidate minus reference, over consecutive intervals. The candidate is the SHA-frozen model declared for that part. On part c, `d4_wind_seed0` and `c651_mc` are scored as comparators and named secondaries, not as the decision candidate. Earlier drafts named `d4_wind_seed0` as the candidate on part b, and that is superseded by revision 11. The interval is the 95% percentile interval from 10,000 whole-fire bootstrap draws, seed 20261030.

Superiority requires **all** of the following:
1. The interval against `persistence` lies below 0.
2. The interval against `dilation_8h` lies below 0. Reported, but near-automatic inside the band (§6.3).
3. **The interval against the frozen `logistic` lies below 0** (revision 9; applies to the A1 cohort decision only, not to the base protocol's 2026 rule).
4. **For a D1/D2 candidate on part c:** the interval against `d4_wind_recal` lies below 0 (revision 13).
5. The lowest fixed bin [0, 0.1) in the band has an absolute calibration gap no larger than that of persistence, `dilation_8h` or `logistic`.
6. **At least 20 analysable fires** in the part being scored (b or c; §1.2), meaning fires with inputs built and at least one positive in the band. Below 20, the result is descriptive and the decision is INCONCLUSIVE. This replaces the base protocol's 10, following the power calculation in §6.3.

### 6.2 Named secondaries

- The **equal-fire mean** of per-fire Brier differences, with its own whole-fire interval (revision 4).
- Per-fire and per-horizon paired Brier differences. These are tested, meaning an interval is reported, only in fire × horizon cells with **at least 10 positives**. Below that they are reported without an interval.
- Skill ratios (BSS) are **descriptors, never test statistics**.

### 6.3 Power (revision 5; measured on R, `derive/POWER.json`)

Method: 2,000 simulated 10-fire cohorts, resampling R's 6 fires, each analysed with the primary method.

| comparison in 4 km band | R pooled difference | R fires favouring d4_wind | P(interval < 0), pooled | P(interval < 0), equal-fire | median half-width |
|---|---|---|---|---|---|
| d4_wind − persistence | −0.000200 | 5 of 6 (Lava against) | **0.54** (10-fire comparison run: 0.5355) | **0.44** | 0.000165 |
| d4_wind − dilation_8h | −0.353 | 6 of 6 | 1.00 | 1.00 | 0.022 |

**Sizing (orchestrator request).** Power against persistence by cohort size, from the same simulation:

| fires | 10 | 15 | 20 | 25 | 30 | 40 | 60 |
|---|---|---|---|---|---|---|---|
| P(interval < 0) vs persistence | 0.52 | 0.68 | **0.80** | 0.88 | 0.93 | 0.98 | 1.00 |
| P(interval < 0) vs logistic | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

The current POWER.json reruns with logistic added. Two 10-fire figures exist: **0.54** (0.5355) is the 10-fire comparison run in the table above, and **0.52** (0.5195) is the sizing run here, whose random stream differs. Both are rough Monte Carlo figures. The sizing row is the one used for cohort size (0.80 at 20 fires).

**At half R's effect** (the same between-fire spread, with each fire shifted toward zero), power against persistence is 0.23 at 10 fires, 0.33 at 20, **0.42 at 30**, 0.53 at 40 and 0.69 at 60. **Plainly: if the true effect is half what R shows, 30 fires will more likely than not be inconclusive against persistence.**

**Rough figure.** These powers come from resampling only 6 fires and are labelled rough. What they say is that a 10-fire cohort would probably be inconclusive for d4_wind against persistence at R's effect size.

The target power is 0.80, reached at 20 fires. Each confirmatory set has 30 fires, which buffers attrition, and requires at least 20 analysable fires.

**Plain reading:**
- At R's effect size, a 10-fire cohort detects an improvement over persistence only about half the time.
- The dilation criterion is almost uninformative: dilation_8h over-predicts heavily inside the band.

**Against logistic, the binding criterion (revision 9; measured on R in the 4 km band):**
- d4_wind − logistic = **+0.000194** pooled and +0.000156 equal-fire. Only 2 of 6 fires favour d4_wind (Goat, Pioneer).
- Simulated power for an interval below 0 is **0.00** at every cohort size from 10 to 60.

**Expectation, stated before any run.** If the untouched cohort resembles R, the A1 d4_wind decision will **fail its logistic criterion**, and probably also its persistence criterion at small n. A failure is the expected, informative outcome. It is not a reason to change the rule.

This power estimate treats 6 fires as the fire population, which is a strong assumption, so it is a scale estimate only.

## 7. Label heterogeneity and observation limits

- No label source is ever pooled with another.
- **NIROPS has no survey-coverage footprint.** Sofia checked 32 public 2026 nightly deliveries: none carried "Area Covered by IR Flight". Acquisition times are estimated for some records, with no per-record flag. Consequences:
  - Outside-union cells are "not mapped", never "observed unburned".
  - Every NIROPS interval carries a timestamp-uncertainty note.
  - A ±2 h timing sensitivity, which shifts each observation time by ±2 h and re-applies the 48 h rule, is a secondary.
- GOFER and FEDS sensitivity to observation gaps is reported per fire as a count of missing observations.

## 8. Correctness gate

Before any cohort score, the `tests/` suite in the harness version recorded in `FREEZE.json` must pass, including the exact reproduction of the forecast-v2 held-out block. A score from an unverified harness version is void.

## 9. Freeze procedure (order matters)

1. Hannah verifies the ledger (3e2eb2d), the harness, the R derivations (`derive/`: dist_m checks, band rule, power) and this revision.
2. Iris re-assesses this revision.
3. Freeze: the final bytes, ledger CSV hashes, harness SHA and predictor SHAs go into `FREEZE.json`.
4. Manifests for N, G, F and K are built from metadata only, with §1.2 and §1.3 applied, then committed and hashed into `FREEZE.json` (amended, never rewritten), and verified.
5. Predictors run on part a only. Every case gets a receipt, and failed and unavailable cases are kept. Part b stays closed until D1/D2 are frozen.
6. Hannah replays the scores from the frozen bundle in a fresh container.

## 10. Open questions

- **Q4 (resolved).** The user approved network access, and NIROPS and the covariate hosts are reachable.
- **Q5.** What is the GOFER label definition (GOES fire-detection-derived perimeters at hourly cadence) relative to NIROPS? This needs Sofia's reading of the GOFER paper before the G cadence rule in §2 is frozen.
