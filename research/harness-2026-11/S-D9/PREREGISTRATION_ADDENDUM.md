# Pre-registration addendum A1: multi-fire, multi-horizon benchmark (S-D9)

**Status: DRAFT, not frozen.** Nothing in this document is in force until Hannah has verified it, Iris has assessed it, and it has been committed together with the hashes in §9. No fire in any cohort defined below has been scored under this addendum.

## 0. Relation to the existing protocol

This addendum **extends** `forecast/documents/preregistration_blind_test.md` (the "base protocol") and does not edit it. The base protocol stays byte-identical, and its 2026 primary rule, model identities and registry are unchanged.
- **2026 prospective cohort.** The base protocol's primary decision governs. Every A1 statistic below is a **pre-declared secondary** analysis of that cohort.
- **Retrospective untouched cohorts (C1, C3 below).** The base protocol does not cover them. For these, A1 defines the primary statistic, reusing the base protocol's conventions wherever one exists: the interval rule, scoring population, baselines, 10 equal-width bins, NLL floor, 10,000 whole-fire draws, seed 20261030, and "fail any criterion means no superiority claim".

## 1. Cohorts and exposure

Exposure is defined by the S-D9 ledger (`ledger/`, checkpoint 3e2eb2d), extended by any later amendment committed **before** the cohort manifest.

| id | cohort | label | role |
|---|---|---|---|
| R | US2024: 6 NIROPS fires, 273 intervals | NIROPS mapped extent | Frozen descriptive regression reference. Already scored and inspected. Never confirmatory. D1/D2 may use it for selection, provided they declare that use. |
| C1 | NIROPS 2020–2024 fires absent from the ledger | NIROPS mapped extent | Retrospective-untouched. **Primary A1 cohort.** |
| C2 | 2026 first-survey NIROPS cohort | NIROPS mapped extent | Base protocol primary; A1 secondary |
| C3 | Korean events absent from the ledger | Kriged arrival reconstruction | Separate stratum, never pooled with NIROPS |
| C4 | GOFER (hourly), FEDS (12-hourly) | Their own perimeter definitions | One separate descriptive stratum per source, excluding any fire in the ledger or matching a ledger fire by incident |

A fire enters C1 or C3 only if all of the following hold:
1. It is absent from the ledger.
2. Its admission is decided from metadata only (incident ID, survey timestamps, grid, input availability), never from outcomes or model output.
3. The cohort manifest listing it is committed, hashed and verified **before** any predictor runs on it.

The person or agent building the manifest attests that they have not viewed the fire's perimeter growth. The ledger's lower-bound caveat applies: exposures on local machines cannot be detected.

## 2. Intervals and lead times

- **Consecutive intervals (as forecast-v2).** These are consecutive distinct survey times t1 < t2 with 0 < t2 − t1 ≤ 48 h, chosen from timestamps only. Cumulative unions are rasterized at cell centres. Weather at floor_hour(t1) is repeated over the interval.
- **Lead-time design (new, secondary).** From each cutoff t1, forecast to every later survey t_j of the same fire with t_j − t1 ≤ 48 h. This gives true multi-horizon lead times from one cutoff state. On NIROPS, consecutive-interval "horizon" is survey cadence: in R, 272 of 273 intervals are longer than 12 h. Lead-time strata are therefore the multi-horizon analysis, and consecutive intervals are the comparison with forecast-v2.

## 3. Predictors

Every predictor is declared by checkpoint or artifact SHA-256 before the cohort manifest is frozen.
- **Models:**
  - `d4_wind_seed0`, the base protocol primary.
  - `c651_mc` with 1,024 trajectories, the integration default.
  - Any D1/D2 variant frozen by SHA before the manifest.
- **Baselines** (computed on identical cells):
  - `persistence`: always zero for new burn.
  - `dilation_8h`: the fixed training-selected rate of one cell per 8 h. It is never reselected.
  - Frozen `logistic`.
  - All 1/2/4/8 h dilations, reported.
- **Later slots** (declared before their first run on C1, otherwise excluded from C1):
  - A FARSITE ensemble with stated weather perturbations.
  - WildfireSpreadTS-trained learned baselines.
  - Missing cases are reported as unavailable and never imputed.

## 4. Scoring population and strata

- **Full population (as forecast-v2).** Initially unmapped cells inside the fixed event rectangle, on the intersection of all predictors' validity masks. Cells outside the endpoint union are mapped-extent negatives. Non-finite or out-of-range probabilities on declared-valid support fail the case.
- **At-risk band (new).** `dist_m` is the Euclidean distance from the cell centre to the nearest cell centre in the cutoff mapped union, on the event's metric 375 m grid.
  - **Primary band rule (revision 1; this rule and threshold were committed before any band share was computed).** The candidate cumulative widths are 1, 2, 4, 8 and 16 km. The primary population is the band of the **smallest candidate width whose pooled share of positives on cohort R (US2024, already exposed) is at least 0.90**. If no candidate reaches 0.90, the primary population is the full domain. The selected width is then fixed for every later cohort. Per-fire and per-horizon shares on R are reported next to the choice, and the out-of-band positive count and share appear in the primary table of every cohort.
  - The band is itself a dilation, so it favours `dilation_8h` (about 1.1 km in 24 h) near its own radius. All widths are shown side by side.
  - Until the rule has been applied, the earlier draft value is superseded. That value was **B2**: dist ≤ 2,000 m.
  - Cumulative bands of ≤ 1, 2, 4 and 8 km, and annuli (0,1], (1,2], (2,4], (4,8] km, are secondary.
  - The band depends on the cutoff state only, never on the outcome.
  - Positives outside 8 km are counted and reported (spotting or long runs).
- **Horizon strata.** (0,12], (12,24], (24,36], (36,48] h, by consecutive-interval duration and, separately, by lead time. Every stratum reports its entry, positive, interval and fire counts. A stratum with fewer than 3 fires is labelled descriptive and gets no interval.

## 5. Metrics

Reported for every predictor, cohort, stratum and fire, computed by `sd9bench` (definitions identical to `forecast/wildfire/baselines.py`):
- Brier.
- BSS against persistence and against `dilation_8h`.
- `base_rate_bss`, an in-sample uncertainty-term diagnostic and not a forecast.
- AP and ROC AUC (unavailable for a single class).
- Ten equal-width reliability bins, plus low-probability bins with edges 0, 1e-5, 1e-4, 1e-3, 1e-2, 0.1. These are reported by horizon stratum and include the count and share of entries in each bin.
- ECE over the ten bins.
- **Exact zero-probability positives**: the count and share of positives.
- Clipped NLL with floor 1e-7, plus an exact-NLL infinity flag.
- **Burned-area CRPS.** The exact ensemble CRPS of the per-interval new-burn cell count, computed only from stored trajectory area samples. There is no independence approximation from marginals. Without samples it is reported as unavailable.
- **Arrival-time score (lead-time design).** For each cell and cutoff, the arrival survey bin is interval-censored to the survey grid (t1, t2], (t2, t3], …, plus "not by 48 h". The score is the **ranked probability score** over those bins, using each predictor's cumulative marginals at each survey time. This is the discrete, censoring-respecting analogue of arrival-time CRPS. NIROPS gives no arrival time within an interval, so no finer target is claimed.

## 6. Primary statistic and decision (C1)

**Primary:** the pooled B2 Brier difference, candidate minus reference, over consecutive intervals. The 95% percentile interval comes from 10,000 whole-fire bootstrap resamples, seed 20261030. The candidate is `d4_wind_seed0`. Any D1/D2 candidate is a separate pre-declared comparison, each with its own family.

Superiority requires **all** of the following. Each criterion is reported separately.
1. The interval against `persistence` lies below 0.
2. The interval against `dilation_8h` lies below 0.
3. The candidate's lowest fixed bin [0, 0.1) on B2 has an absolute calibration gap no larger than either baseline's.
4. **At least 10 C1 fires** have at least one B2 positive. Below 10, every result is **descriptive** and the decision is INCONCLUSIVE, following the base protocol's minimum.

Per-fire and per-horizon BSS (Iris's per-fire, per-horizon emphasis) are reported for every fire and stratum with paired whole-fire intervals. They are not decision criteria. Multiple candidates are reported without multiplicity adjustment and are labelled as such. Only the `d4_wind_seed0` decision is confirmatory.

## 7. Label heterogeneity

NIROPS, kriged reconstruction, GOFER and FEDS each define burned-by-t differently, with different latency. They are **never pooled**, and each is scored and reported as its own stratum. NIROPS has no survey-coverage footprint (unless Daniel or Sofia find one). Outside-union negatives remain "not mapped", not "observed unburned", and this limitation travels with every C1 number.

## 8. Correctness gate

Before any cohort score, the harness must pass `tests/` (24 tests at 29493b1, including exact reproduction of the forecast-v2 held-out block). The harness version (git SHA) used for every score is recorded. A score from an unverified harness version is void.

## 9. Freeze procedure (order matters)

1. Hannah verifies the ledger (3e2eb2d) and the harness (29493b1).
2. Iris assesses this addendum. Revisions are committed, then Hannah verifies.
3. The addendum is frozen: commit its final bytes and record their SHA-256 in `FREEZE.json`, together with the ledger CSV hashes, the harness SHA and the predictor checkpoint SHAs.
4. The C1, C3 and C4 manifests are built from metadata only, committed and hashed in `FREEZE.json` (amended by a new commit, never rewritten), and verified.
5. Only then do predictors run and scores get computed. Every attempted case gets a receipt, and failed or unavailable cases are retained.
6. Hannah replays the scores from the frozen bundle in a fresh container.

## 10. Open questions for review

- **Q1 (Iris).** The B2 band is cutoff-dependent. Could it favour models that spread only locally, such as dilation? Mitigation: secondary 4 and 8 km bands, and reporting positives beyond 8 km.
- **Q2.** The RPS arrival score needs cumulative marginals at every later survey time from one cutoff. Does c651_mc (sampled histories) or d4 (hourly marginals) emit these without code changes? The November note says both can, synthetically, but this is unverified.
- **Q3.** C1's size is unknown until Daniel lists the NIROPS archive members. If it has fewer than 10 fires, A1's C1 result is descriptive by construction, and C2 (2026) remains the only confirmatory route.
