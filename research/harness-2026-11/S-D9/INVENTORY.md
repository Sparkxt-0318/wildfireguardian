# S-D9 step 1: inventory of existing forecast evaluation assets

Stream S-D9 is a pre-registered probabilistic benchmark for the forecast across several fires and horizons. This file is the step 1 inventory: what already exists in the repository at `Main` 5fa19a2. It is read-only and nothing below was changed. Measured values carry the command that produced them, and anything labelled hypothesis or unverified is exactly that.

## 1. The direction document's premise is partly out of date

The direction document describes the "preprint" evaluation as one fire (Wapiti), 25 of 324 planned intervals, with Brier skill 8.17%. That is the **October 12–13 M548/c651 observed evaluation** (`forecast/documents/observed_combined_evaluation.md`, `forecast/documents/observed_runtime_*_20261013.json`).

- I reproduced its headline figures arithmetically from the stored validation record (`observed_runtime_stored_validation_20261013.json`). The M548 new-burn record has 275,961 entries, 2,525 positives and Brier 0.0084025. The always-zero ("persistence") forecast scores Brier = base rate = 0.0091498, so BSS = 1 − 0.0084025/0.0091498 = **0.08168 (8.17%)**. That matches the document.
- The 324 planned intervals are the six NIROPS 2024 test events. Only the 25 Wapiti intervals completed. The run was interrupted (`run_status: interrupted`, KeyboardInterrupt).

**A later study already went well beyond this.** `research/forecast-v2/` (Oct 30–31) is a multi-fire, fire-level-split, pre-specified evaluation:
- The split is whole-fire and was frozen before any fit (`research/forecast-v2/SPLIT.json`). There are 23 US fit fires from 2020–2022 with leave-one-year-out development folds. The held-out sets are US2024 (6 NIROPS fires) and Korea2025 (KFS_01, 04, 06, 13).
- All **273 eligible US2024 intervals** (0 < duration ≤ 48 h, chosen from timestamps only) were scored on 1,705,079 common cell-interval entries with 8,520 positives. The scoring covered 16 models, a whole-fire bootstrap (10,000 resamples, seed 20261030), reliability bins, AP and BSS against persistence and against the best dilation. The primary candidate (`d4_wind_seed0`) **failed** its pre-registered superiority rule.
- A prospective blind-test protocol for the 2026 NIROPS cohort already exists (`forecast/documents/preregistration_blind_test.md`). Its status is READY_FOR_OWNER_REGISTRATION and it has not been executed.

**Consequence for S-D9.** The US2024 and Korea2025 held-out sets have now been scored and inspected, so they are **no longer untouched** for any new model selection. c651 was selected after inspecting Wapiti (SPLIT.json `c651_training_overlap`). Any S-D9 claim of untouched evaluation therefore needs fires outside these 10 held-out events and outside the 23+7 fit/validation events, or the 2026 prospective cohort.

## 2. Stored predictions available for scoring now (no fetch needed)

`forecast/runs/20261030_perimeter_trained/execution_v3/heldout/` holds 123 MB of `.npz` files committed in git:
- There is one file per event with all scored entries: `interval`, `row`, `col`, `y` (int8) and `p_<model>` for 16 predictors. The predictors are `c651_mc`, `c651_meanfield`, seven final variants (`base`, `d4`, `d4_wind`, `ellipse`, `burnout`, `burnout_spotting`, `mixed_base`), `persistence`, `dilation_{1,2,4,8}h`, `dilation_best` and `logistic`. Each event file also carries `t1` and `hours` per interval.
- `cases/` holds 273 per-interval `.npz` files plus `.json` receipts. The receipts record the event, cutoff, endpoint, hours, scored/excluded cells, positives, input hashes and per-model seconds.
- `../korean2025/` holds the same layout for 4 Korean events (33 windows, 26 scored).

**Correctness check, measured.** I pooled all 6 US event files (command below) and got n = 1,705,079 and 8,520 positives. The pooled Brier scores match `research/forecast-v2/README.md` to every published digit:

| predictor | recomputed Brier | published |
|---|---|---|
| persistence | 0.004996835923731 | 0.004996836 |
| d4_wind_seed0 | 0.004926886222563 | 0.004926886 |
| c651_mc | 0.009852196942660 | 0.009852197 |
| dilation_best | 0.128456804640723 | 0.128456805 |
| logistic | 0.004858686125164 | 0.004858686 |

```sh
cd forecast/runs/20261030_perimeter_trained/execution_v3/heldout && python3 -c "
import numpy as np,glob
ys=[];P={}
for f in sorted(glob.glob('*.npz')):
    z=np.load(f); ys.append(z['y'].astype(float))
    for m in ['p_persistence','p_d4_wind_seed0','p_c651_mc','p_dilation_best','p_logistic']: P.setdefault(m,[]).append(z[m].astype(float))
y=np.concatenate(ys);print('n',y.size,'pos',int(y.sum()))
for m,v in P.items():
    p=np.concatenate(v);print(m, ((p-y)**2).mean())"
```

**Not in the repository:** the 25 Wapiti M548 case exports (`m548_prediction.npz`, `reference.npz`, `farsite_prediction.npz`) behind the 8.17% figure. They lived in `runs/20261012_observed_test_combined_progress` on the owner's Mac. Reproducing the preprint numbers at cell level therefore needs either those files (request to Daniel) or a rerun. The runtime audit records 25 cases at roughly 1,000 s of M548 time each, about 7 h plus FARSITE, and requires the environmental inputs below. The aggregate record (n, positives, Brier, MAE, confusion) is in the repo and was checked above.

## 3. Existing evaluation code

- `forecast/wildfire/metrics.py`, `evaluate.py`, `cumulative_evaluation.py` and `observed_combined.py` contain the maintained package metrics and the observed-survey evaluation CLI (`python -m wildfire evaluate-observed-combined`, with `--plan-only`, `--reuse-results` and `--report-only`).
- `research/forecast-v2/scripts/` holds about 7,500 lines: `score_cohorts.py` (US2024 and Korea2025 scoring), `report.py` (canonical RESULTS.json, bootstrap and reliability), `blind_test.py` and `blind_inventory.py` (the 2026 prospective tool), `make_split.py`, `prepare_perimeters.py` and `public_baselines.py` (persistence, dilation, logistic).
- Missing from all of these and needed by S-D9: **burned-area CRPS**, **per-horizon stratification** (the data exist in `hours` but are not reported by horizon), **an explicit count of zero-probability positives per predictor** in a standard table, and **a small reusable scoring interface** for D1 and D2 variants. The current scripts are tightly coupled to the forecast-v2 campaign and its frozen registry.

## 4. Fires and intervals, by data availability

| set | events | in-repo state |
|---|---|---|
| catalog (`forecast/data/environment/events.json`) | 44 (15 KR, 29 US) | Metadata only. The rasters, environment and arrival grids are **not** in git (`data/environment` is 48 KB). |
| US fit 2020–22 | 23 | Fit only. No predictions stored. |
| validation (cell-hour benchmark era) | 7 | n/a |
| US2024 held-out (NIROPS) | 6 | **273 intervals scored, predictions in git** |
| KR2025 held-out (kriged reconstruction) | 4 | 33 windows, 26 scored, predictions in git |
| NIROPS source | 6 catalog events | Only provenance and file hashes in git. The 1.39 GB archive is external (Mendeley DOI 10.17632/95rj5d379g.1, CC BY 4.0). |

The forecast-v2 inputs were recovered from an owner-local archive (`wildfire 3 (1).zip`, SHA-256 b9e000e8…). Environmental covariates were **not** re-downloaded. Running any model on a new fire needs the covariates rebuilt. `forecast/wildfire/environment.py` has public-source acquirers for Open-Meteo/ERA5, gridMET THREDDS, Copernicus DEM, LANDFIRE, the Potapov forest height and PROBA-V LC100. Whether they still work from this container is unverified (a question for Daniel).

**Candidate untouched fires (hypothesis, not checked against data):**
- NIROPS 2020–2024 fires in the archive that are not among the 29 catalog US events.
- GOFER hourly perimeters (28 California fires). These overlap the fit set (Dixie, August Complex, Creek, Monument and others likely appear), so overlapping fires must be excluded.
- FEDS 12-hourly perimeters.
- Korean events after 2025.
- The 2026 NIROPS cohort under the existing prospective protocol.

## 5. The two items the direction document's author did not verify

1. **Do the held-out 2025 Korean events include the Uiseong–Andong complex?** The evidence says yes, but this is unconfirmed. Catalog event `KFS_01` is named "Uiseong" with t0 2025-03-22 02:24 UTC and WGS84 bounds of 128.45–129.45°E, 36.32–36.60°N, which reaches the east coast. It has 10,955 valid arrival pixels, the largest event in the catalog. The routing kit's matching case is named `uiseong_andong_2025` (`integration/kit/INPUT_BINDING.json`). **Caveat: 7 of the 33 Korean windows have no common supported cells, and all 7 are KFS_01.** The largest Korean event is therefore only partly scored, and the Korea2025 cohort is on HOLD (`research/forecast-v2/README.md`). I asked Sofia to confirm the extent against the official KFS record.
2. **Do NIROPS flight-coverage metadata exist?** Not in the repo. The forecast-v2 protocol states "No complete survey coverage footprint is available under the present data model". Outside-union cells are treated as negatives, with no coverage mask. The Mendeley release contains `NIROPS_2020_2024_R1_R6.zip`, `Area_Progression_TimeSeries.zip`, `Supplementary_Maps.zip` and `NIROPS_Code.zip`. Whether any of them holds flight footprints or coverage polygons is **unverified** and sent to Daniel and Sofia. This matters: without coverage, the "617 of 2,525 positives with zero probability" and the large lowest-bin miscalibration could partly come from label artefacts such as unflown areas and timestamp estimation.

## 6. Ideas and gaps

- **G1. Untouched-fire scarcity is the binding constraint.** Only 6 US held-out fires have been scored and they are now inspected. A whole-fire bootstrap over 6 fires gives wide intervals; for example, the primary-vs-persistence interval straddles zero. The pre-registration should fix a minimum fire count, the way the existing 2026 protocol uses ≥ 10 US fires or else INCONCLUSIVE, and treat smaller cohorts as exploratory.
- **G2. Reuse rather than rebuild.** forecast-v2 already settles the split, the bootstrap seed, the persistence and dilation baselines and the 0–48 h interval rule. S-D9 should extend that protocol (CRPS, per-horizon reporting, zero-probability positives, a pluggable interface) instead of starting a parallel one with different conventions.
- **G3. Horizon is confounded with survey timing.** Interval duration is set by when the flights happened, not by design. Per-horizon bins will have very uneven fire composition, so per-horizon results should be reported with fire counts per bin.
- **G4. Burned-area CRPS needs an ensemble or a predictive distribution of area.** Only MC models (`c651_mc`) have trajectories. The stored files hold per-cell marginals, not trajectories, so area CRPS cannot be computed from them. A Poisson-binomial approximation from marginals assumes independence, which is wrong for spread. This has to be declared in the pre-registration: either store trajectory-level area samples or use a stated approximation.
- **G5. Persistence is degenerate for new-burn targets.** It predicts 0, so its BSS reference is the base rate, and its "AP" equals the base rate. A climatological or base-rate-by-horizon baseline is a fairer skill reference and costs nothing.

## Next steps (proposed, pending orchestrator OK)

1. Ask Daniel for the 25 Wapiti M548 exports if they can be recovered, plus the NIROPS archive member list and coverage metadata check.
2. Draft PREREGISTRATION.md building on SPLIT.json and the forecast-v2 conventions.
3. Agree the scoring interface with Marcus (D1) and Elena (D2). The proposal is `score(entries: {event, interval, hours, y, p}) -> report`, fed by an npz with the same layout as the existing heldout files.
4. Build the harness with tests. Correctness checks: (a) exact reproduction of the forecast-v2 canonical numbers above, and (b) the preprint aggregate numbers once the Wapiti exports are available.
