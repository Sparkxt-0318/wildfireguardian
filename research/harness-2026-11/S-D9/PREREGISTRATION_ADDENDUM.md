# Pre-registration addendum A1: multi-fire, multi-horizon benchmark (S-D9)

**Status: DRAFT revision 3, not frozen.** Nothing here is in force until Hannah has verified it, Iris has re-assessed it, and it is committed with the hashes in §9. No fire in any untouched cohort below has been scored. The only scores computed so far are on cohort R, which is already exposed. They were computed to apply rules that are stated in this document before the computation, and each one is labelled.

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
   - **b**, ranks 1–30: the **d4_wind_seed0 / c651 confirmatory test set**.
   - **c**, ranks 31–60: the **reserved D1/D2 methods confirmatory test set**. It stays closed until every D1/D2 candidate is frozen by SHA.
   - **a**, ranks 61–120, plus every clean incident with `surveys < 20`: the **training and development pool** for D1/D2 refits.
   - **d**, ranks 121 onward: held back for later work. It stays closed.
5. **Sizing.** 30 per confirmatory set comes from §6.3. At R's effect against persistence, power reaches 0.80 at about 20 fires. 30 gives a buffer for attrition, at 0.93 if all 30 are analysable. **At least 20 analysable fires** are required in b (analysable means inputs built and at least one positive in the 4 km band); otherwise the decision is INCONCLUSIVE. Attrition is decided before any prediction runs on the fire:
   - **Input-build failure** (no covariates, or a grid that cannot be aligned): the fire is replaced by the next d incident in `u` order. The replacement is logged.
   - **No positive in the band:** this is known only after labels are built. It never triggers a replacement; it only reduces the analysable count.
6. **Independence (§1.3)** is applied after assignment. An excluded b or c fire is replaced by the next d fire in `u` order, before any prediction runs.
7. **Pilot.** The pipeline pilot uses only the **first 3 eligible (surveys >= 20) part-a fires in `u` order**. Clarification committed before the first run. Pilot fires are training-pool fires; no b, c or d fire is ever a pilot.
8. **Access control.** Whoever assigns the parts publishes the part list as a CSV. **No one opens the perimeters of b, c or d until the addendum is frozen and the manifest for that part is verified.** Training users filter the shapefile by the part-a allowlist. This is recorded in the ledger.

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

## 3. Predictors

Every predictor is declared by SHA-256 before the manifest.
- **Models:** `d4_wind_seed0` (the primary), `c651_mc` (1,024 trajectories), and D1/D2 variants frozen by SHA (part b only).
- **Baselines on identical cells:**
  - `persistence`.
  - `dilation_8h`, fixed and never reselected.
  - Frozen `logistic`.
  - All of the 1/2/4/8 h dilations.
- **Later slots** must be declared before their first run. They include a perturbed-input physics ensemble (FARSITE, or ELMFIRE with its published inputs) and WildfireSpreadTS-trained learned baselines. **Any WildfireSpreadTS-trained baseline must list its training fires. A G, F or N fire that is in that training set is excluded from that baseline's comparison, and the exclusion is recorded in the ledger.**

**Running predictors on G, F or N currently blocked.** Running any predictor on a new fire requires building its covariates. Daniel measured the hosts the covariate builders depend on (`forecast/wildfire/environment.py`):
- **Refused:** archive-api.open-meteo.com, tds-proxy.nkn.uidaho.edu, lfps.usgs.gov, glad.geog.umd.edu and www.landfire.gov.
- **Reachable:** copernicus-dem-30m.s3.amazonaws.com and zenodo.org.

Until the user opens the refused hosts or supplies the covariates, **no untouched cohort can be scored**.

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

**Revision 7 outcome:** the multi-observation cumulative-marginal export could not be run on R. The model inputs are owner-only (confirmed by Daniel and Marcus) and the covariate hosts are blocked. The arrival RPS is therefore **declared UNAVAILABLE for `d4_wind_seed0` and `c651_mc`** in this addendum. It cannot be added for them after freeze. A D1/D2 predictor may carry it if its export is demonstrated on R before its own SHA freeze. An interval-censored variant that does not penalize mass inside a true bracket is a secondary, used only where brackets exist.

## 6. Primary statistic and decision

### 6.1 Primary (cohort N part a, or C2 under the base protocol)

The primary statistic is the **pooled paired Brier difference** in the 4 km band, `d4_wind_seed0` minus reference, over consecutive intervals. The interval is the 95% percentile interval from 10,000 whole-fire bootstrap draws, seed 20261030.

Superiority requires **all** of the following:
1. The interval against `persistence` lies below 0.
2. The interval against `dilation_8h` lies below 0.
3. The lowest fixed bin [0, 0.1) in the band has an absolute calibration gap no larger than either baseline's.
4. **At least 20 analysable fires** in part b (§1.2), meaning fires with inputs built and at least one positive in the band. Below 20, the result is descriptive and the decision is INCONCLUSIVE. This replaces the base protocol's 10, following the power calculation in §6.3.

### 6.2 Named secondaries

- The **equal-fire mean** of per-fire Brier differences, with its own whole-fire interval (revision 4).
- Paired Brier differences against `logistic`.
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
| P(interval < 0) | 0.54 | 0.68 | **0.80** | 0.88 | 0.93 | 0.98 | 1.00 |

The target power is 0.80, reached at 20 fires. Each confirmatory set has 30 fires, which buffers attrition, and requires at least 20 analysable fires.

**Plain reading:**
- At R's effect size, a 10-fire cohort detects an improvement over persistence only about half the time.
- The dilation criterion is almost uninformative: dilation_8h over-predicts heavily inside the band.

The decision rule is kept as the base protocol's. Logistic is added as a named secondary because it is the informative learned reference (in R it beats d4_wind on full-domain pooled Brier: 0.004859 against 0.004927).

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

- **Q4.** Does the user want the refused covariate hosts or data.mendeley.com opened? Without them, A1 can be frozen but not executed on any untouched fire (§3).
- **Q5.** What is the GOFER label definition (GOES fire-detection-derived perimeters at hourly cadence) relative to NIROPS? This needs Sofia's reading of the GOFER paper before the G cadence rule in §2 is frozen.
