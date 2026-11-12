# Pre-registration addendum A1: multi-fire, multi-horizon benchmark (S-D9)

**Status: DRAFT revision 13, not frozen.** Nothing here is in force until Hannah has verified it, Iris has re-assessed it, and it is committed with the hashes in §9. No fire in any untouched cohort below has been scored. The only scores computed so far are on cohort R, which is already exposed. They were computed to apply rules that are stated in this document before the computation, and each one is labelled.

## Revision log

| # | revision (Iris assessment of 9348abb5, adopted by the orchestrator) | where | status |
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
| 18 | Rebuilt-pipeline refits of d4_wind and logistic on the training pool: the confirmatory comparators for part c (orchestrator decision; Iris option b) | §3.1 | Recipe frozen here **before any refit runs**. Archive-trained models become labelled descriptive rows |
| 17 | Filters applied (`cohort/RUN_FILTERS.md`). The script now enforces §1.1 ledger exclusion by incident ID, including NIROPS incidents matching GOFER fires. Clarification: an incident that is an item-10 duplicate of an opened incident counts as opened | §1.2 items 8–12 | Clarification written after the first filter run showed Caldor and a pilot sibling in test parts. Only metadata was viewed |
| 16 | Pre-declared plan for a non-burnable secondary; provenance of the H tolerance rule; H disclosure note on every H result (Iris) | §4, §2.1 | Added. **The secondary was added after a development finding on R** (`derive/LOGISTIC_DEV.md`, follow-up 2) |
| 15 | H refinements: Chebyshev reach, one-pixel tolerance, resolution labels per lead, H-dev open to D1 and D2, half-step comparator; Marcus's GOFER disclosure (Marcus, Iris) | §2.1 | Added before any H score |
| 14 | Short-horizon stratum H for the D1 continuous-time claim (orchestrator) | §2.1 | Declared before any score on H. Membership is computed after the metadata filters run |
| 13 | Recalibrated d4 is a part-c comparator that D1/D2 must beat (Iris) | §3, §6.1 | Added. Chosen after seeing the development-only R result (`derive/LOGISTIC_DEV.md`) |
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
| K | Korean events absent from the ledger | kriged arrival reconstruction | not yet located | Separate stratum |

**Label strata are never pooled.** The 4 km band and every other rule fixed on R come from NIROPS. Applying them to G, F and K is a stated transfer assumption, not a validated equivalence. Because R is NIROPS, **only N (or C2) can carry a confirmatory A1 result**. G, F and K results are descriptive whatever their size.

Daniel's metadata name-match on Main gives the current untouched GOFER candidates (17 fires): Kincade, Walker, Bobcat, CZU, Dolan, Glass, July, KNP, LNU, McFarland, SCU, Slater & Devil, Tamarack, W-5 Cold Springs, Windy, Zogg and Beckwourth. Dixie, River, Antelope, August, North/PNF, Monument, Creek, SQF, McCash and Red Salmon are FIT fires. Caldor is INSPECTED. Membership becomes final only through the manifest procedure in §9, after §1.3 is applied.

Admission to any untouched cohort requires all of the following:
- The fire is absent from the ledger.
- Admission is decided from metadata only.
- The manifest is committed, hashed and verified before any predictor runs.
- The manifest builder attests that they have not viewed the fire's growth.

### 1.2 NIROPS cohort selection and four-part split (revision 3; committed before any assignment was generated)

The source is Daniel's metadata table `research/harness-2026-11/data-fetch/nirops_incidents.csv` (branch daniel/data-fetch, 3129ad59 or later). It has 737 incidents from the Magstadt et al. NIROPS 2020–24 archive and uses **only** these fields: `Incident_C`, `surveys`, `project_status`, `shares_irwin_with_project_fire` and `year`. `max_acres` (final size) is an outcome and is **not used**.

1. **Clean pool.** Keep `project_status == "unused_in_repo_events"` and `shares_irwin_with_project_fire == False`. That leaves 704 incidents. The input file is pinned: daniel/data-fetch 971f825d, `nirops_incidents.csv` SHA-256 f2aae4b8891bcaa5489631185d19a50991ae059c056384f11d8b8f299922d9ca. Clarification committed before the first run: the status label is the one used in the file.
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
- These are the GOFER v0.2 fires (Zenodo 14642378) with no project use. Daniel's name match lists 17: Kincade, Walker, Bobcat, CZU, Dolan, Glass, July, KNP, LNU, McFarland, SCU, Slater & Devil, Tamarack, W-5 Cold Springs, Windy, Zogg and Beckwourth.
- They are filtered by §1.3, using point of origin and discovery date against every FIT or SELECTED_ON fire. Caldor 2021 (INSPECTED) is also excluded. Exclusions are logged.
- The survivors are ordered by `u = sha256("S-D9-A1|GOFER|" + GOFER fire name)` (same construction as §1.2).
  - The **first ⌊n/2⌋ form H-dev**: open to **both D1 and D2** for development (revision 15). Each use is logged in the ledger.
  - The **rest form H-test**: closed until the D1 candidate is frozen by SHA.
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
- The **part-a training pool** (`cohort/PART_A_ALLOWLIST_FINAL.csv`, sha 801acdd8…). An incident is used only if it has at least 2 surveys and a buildable grid.
- Intervals follow §2's rule (0 < Δ ≤ 48 h, timestamp-only), with all eligible intervals per fire. Build failures are logged, never replaced.
- No US2024, KR2025, part b/c/d or H-test fire is used.

**`d4_wind_rebuilt`** follows the forecast-v2 recipe exactly; only the training fires and the covariate pipeline change.
- Source: `research/forecast-v2/scripts/pipeline.py` (sha256 88d376d2…2d67), invoked as forecast-v2 invoked its final stage (`run_campaign.py` sha256 7d089b86…b74d): `pipeline.py final --variant d4_wind --max-fit-intervals-per-fire 0 --intervals-per-epoch 0`.
- Hyperparameters: the `fitting` block of `research/forecast-v2/RUN_PROTOCOL.json` (sha256 c2dce7f7…8243). That is epochs 3, seed 0, hidden_channels 16, kernel_size 9, learning_rate 0.003, weight_decay 1e-4, samples_per_step 1, training crop = cutoff initial extent + 10 cells with zero exterior, biome emphasis training-only inverse-sqrt, threads 2. Variant d4_wind: prior free, frame wind, d4 true.
- There is **no development-fold selection**: the variant is fixed, so nothing is selected. There is one seed.
- The checkpoint SHA is recorded in FREEZE.json before part c opens.

**`logistic_rebuilt`** uses `forecast/wildfire/baselines.py` (sha256 325abbe7…afbb1f):
- Features: `hand_features` with an elevation-gradient directional slope and the same 14 biome codes (the feature list in `forecast/runs/20261030_perimeter_trained/execution_v3/baselines/logistic.json`).
- Fit: `fit_logistic(C=1.0, seed=0)`, negatives subsampled at 0.05 and inverse-weighted.

**`d4_wind_recal`** (§3) is redefined on top of `d4_wind_rebuilt`: a one-feature logistic recalibration fit on the same training data.

**`dilation_8h`** has no fitted weights, so it is unchanged.

**Rate-mixture candidate** (development first, per Iris; added as a part-c comparator only if it performs in leave-one-fire-out development on R): `d4_wind_rebuilt` run at global rate multipliers m ∈ {1, 2, 4, 8, 16}, with mixture weights fit on the training data. Once weather covariates exist, a development check also tests whether the fast tail intervals are predictable from wind; if they are, one wind-dependent weight parameter is allowed. The final form is frozen by amendment before part c opens.

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
  - The class is defined **from covariates only** (fuel / land-cover code and validity flags), never from the endpoint or from enclosure, because enclosure uses the outcome.
  - The exact code list is fixed in an amendment once Daniel's US2024 fuel layers exist, and **before** any untouched score.
  - **The primary population is unchanged.**
  - This secondary was added after a development finding on R.
- **Horizon strata:** (0,12], (12,24], (24,36], (36,48] h, by interval duration and separately by lead time, with entry, positive, interval and fire counts.
- **Domain stratum (requested by Elena, S-D2):** where an `in_domain` mask is supplied (the kriging domain), the same metrics are reported inside and outside it.

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
| d4_wind − persistence | −0.000200 | 5 of 6 (Lava against) | **0.54** | **0.44** | 0.000165 |
| d4_wind − dilation_8h | −0.353 | 6 of 6 | 1.00 | 1.00 | 0.022 |

**Sizing (orchestrator request).** Power against persistence by cohort size, from the same simulation:

| fires | 10 | 15 | 20 | 25 | 30 | 40 | 60 |
|---|---|---|---|---|---|---|---|
| P(interval < 0) vs persistence | 0.52 | 0.68 | **0.80** | 0.88 | 0.93 | 0.98 | 1.00 |
| P(interval < 0) vs logistic | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

The current POWER.json reruns with logistic added. The persistence row's random stream changed, so its 10-fire value is 0.52 here and 0.54 in the earlier table.

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
