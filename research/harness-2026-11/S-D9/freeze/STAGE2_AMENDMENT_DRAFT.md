# A1 stage-2 amendment: DRAFT text (not frozen)

**Status: draft.** Nothing here is frozen until `make_freeze.py` writes the stage-2 record and Hannah verifies the text and the record. Part c stays closed until then (A1 §6.1, §9).

- Any item marked **PENDING** or **UNVERIFIED** is cited only after the named verifier's ledger row exists.
- Pins are collected in `STAGE2_PINS.md`.

## 1. Survey-timing exposure (declared; gate cleared)
- **Source:** `ledger/ACCESS_CONTROL.md`, PR #147, frozen at 1fc38266. Hannah's audit is ledger row 38 (PASS WITH NOTES) and her text check is row 41 (PASS).
- **Status wording for part c:** "Labels, perimeters and growth are sealed. Survey-timing metadata was exposed before the split, and the membership rules used it." Part c stays confirmatory, with these limitations. H is descriptive. Part d is exposed.
- **§1.2 reconciliation.** The five-field list in §1.2 describes what scorers may read. The membership filters are separate: §1.3, item 8 (timing-dependent), item 9 and item 10. These used discovery, first and last survey times to decide membership only. In total they changed membership for **18 b/c/d and 96 part-a** incidents. §1.1 uses no timing.
- **File list:** survey-timing files F1–F5, with their shas, are listed in the disclosure. This includes `GOFER_MATCH.csv` (451675c1).
- **Standing rule (added to A1).** No design choice, eligibility rule, constant or candidate may use a sealed incident's last survey time, survey days, or any cadence derived from them. Stratum G is defined from part a only.
- **Reporting rule.** Part-c results are also reported by tercile of survey span. This is descriptive and does not change the primary test.
- **Leak bound.** The plan is `derive/LEAK_BOUND_PLAN.md` (e8772880, PR #148), and constant provenance is in `CONSTANT_PROVENANCE.md` (0a89bee2).
  - Marcus runs the leak bound with the refits, and Owen verifies it.
  - A material leak is pre-defined as a 95% interval of ΔBrier lying entirely below 0. **PENDING** result.
- **Clean confirmation.** The clean confirmation is CR1 (`clean_replication/PREREGISTRATION_DRAFT.md`, PR #153), not part c. It is frozen separately.

## 2. d2_bracket_rebuilt protocol
- **Code (claude/s-d2-next):** final `refit/` head **df55cff7** (verified: Owen rows 51, 52, 55, 56, 57) (Elena, 03:50Z 13 Nov). It is 55b268df with `run_d2.py` restored to the frozen stage-1 pin e3c0843c… (orchestrator ruling, option A), so FREEZE.json §3.1 item 21 stays valid with no amendment. `git diff 55b268df df55cff7 -- refit/` touches only run_d2.py (+2/−3, text only). It supersedes 55b268df, 7d4937c7 and e598a840, for `d2_bracket_rebuilt` and `d2_nll_rebuilt`. File sha256 prefixes, checked from the commit: `d2_bracket.py` 80f9fbb6, `run_d2_bracket.py` cc41cc33, `run_d2.py` e3c0843c (= stage-1 pin; 46d299ea at 55b268df reverted), `time_estep.py` 0bebc764, `native_marginals.py` 5fad4734, `demo_native_marginals_R.py` bcad73ed (its receipt carries the three weight conditions: weights.status, a strict weights.load_check, summary.non_degenerate; it reads R states only through `nirops_access.py` ab065e85 with `R_ALLOWLIST` c4d74159, under Hannah's row-78 terms). Earlier pins superseded: `d2_bracket.py` 98d7d6c6, `run_d2.py` e3c0843c, `native_marginals.py` 48825e3d. **Owen's verification (LEDGER-SMOKE-2):**
  - Row 51 (PASS WITH NOTES): the core code.
  - Row 52 (PASS): the centre guard, `d2_bracket.py` 80f9fbb6.
  - Row 55 (PASS WITH NOTES, 7e195b36): `native_marginals.py` and the demo driver at 55b268df.
  - Row 56 (PASS WITH NOTES, 29d55102): the whole `refit/` at 55b268df.
  - df55cff7 differs from 55b268df only by the run_d2.py revert. Victor checked: sha e3c0843c, and the demo driver and `native_marginals.py` do not import run_d2.py (the driver only hashes it into its receipt). Owen confirmed: **PASS, LEDGER-SMOKE-2 row 57**. run_d2.py is byte-identical to 10b02285; every other refit/ file matches the row-56 shas; the demo driver never imports or runs run_d2.py, so the demo outputs are unaffected and no rerun is needed. Tests are 13/13. **Bookkeeping:** both existing demo receipts (Daniel's and Owen's) record run_d2.py 46d299ea and git_head 55b268df. The frozen object is df55cff7.
- **E-step:** discretised Gibbs on a 0.25 h grid.
  - 2 sweeps per epoch, with midpoint initialisation and a warm start.
  - Its own RNG: `SeedSequence([seed, 0x5D2B])`.
  - Order per epoch: kernel pass, then 2 detached sweeps, then the M-step on the same kernels, then the optimiser step.
  - The last epoch is used, with no validation selection.
  - Budget: 3 epochs (A1 budget line).
  - The protocol refuses burnout and spotting inputs.
- **Unscored burned cells.** Cells burned at the endpoint but not initially are latent.
  - Unscored latent cells get no own-event or exposure term; they act as sources only.
  - **Residual, recorded.** Unscored cells that are not endpoint-burned keep τ = ∞. Report their part-a share.
- **Grid step.** Elena's 0.25 h vs 0.05 h synthetic check (8b0fde65) finds differences ≤ 0.0024 in far share and ≤ 0.0010 in rate ratio. Verified: PASS WITH NOTES (Owen, LEDGER-SMOKE-2 @9f0a5162, row 27).
- **Timing.** About 2.6× d4 per pass, as an upper bound. Not a frozen quantity.
- **§5.2.** The native-marginal demo on R must exist before the code sha is frozen. Export built and unit-tested at 2c45d27a; current version in the proposed head e598a840 (`native_marginals.py` 5fad4734…; single lead bit-identical to `sample_forecast`). **Demo on R: ran 2026-11-13 03:14–03:18Z, all checks true** (Daniel executed 55b268df verbatim; summary S-D2 RESULTS §3i at efa53abf; receipt sha256 89288293…, held off-repo pending Hannah). It covered 6 fires and 273 cutoffs, with 0 skipped. CDFs were in [0,1] and non-decreasing, and the single lead was bit-identical at all 273. The development weights `d4_wind_seed0` 33c5b3cf loaded strictly, the outputs were non-degenerate, and no RPS was used. Custody PASS (Hannah, ledger row 79). **Owen: PASS WITH NOTES (LEDGER-SMOKE-2 row 55, 7e195b36).** His independent rerun reproduces Daniel's 6 arrival files bit for bit, plus all 273 cutoff rows and the summary. Conditions (a)–(d) and the weight conditions are met. **Freeze note:** at fractional leads, later columns are not bit-identical to separate single-lead runs; the difference is up to 0.03 on a synthetic probe, from the extra break steps. Only the single-lead column is required to be bit-identical. Original note: R's rebuilt inputs come from the US2024 environment (manifest 286f4c47…, regenerated by Marcus with `rebuild_us2024_pinned.sh` 12fc6e7b). The demo runs from the final code head that is frozen; any later code change re-runs it.
  - **Orchestrator ruling (2026-11-13).** §5.2 is a code-path requirement, so the demo may use a pre-freeze, part-a-trained model, under four conditions:
    - (a) it runs from the exact code sha that is frozen;
    - (b) the weights' provenance is recorded;
    - (c) the receipt shows, per R fire and cutoff, valid cumulative CDFs: in [0,1], non-decreasing across observation times, one column per later survey ≤ 48 h, with the single-lead column bit-identical to `sample_forecast`;
    - (d) no RPS is used at this step; the revision-30 propriety gate governs any scoring for admission.
  - **Execution.** The demo may run in Daniel's container, where the US2024 environment (286f4c47) already exists, from Elena's exact commit. Daniel executes it verbatim and changes no code; Elena owns the command and the receipt. This is the same arrangement as the refits.
  - **Weights (orchestrator ruling, 2026-11-13, 03:06Z).** The demo may use the committed `d4_wind_seed0` checkpoint (33c5b3cf…) as **development weights**, under three conditions in addition to (a)–(d):
    - the receipt names the checkpoint and its archive provenance, and says plainly that these are development weights, not part-a-trained;
    - the weights load unchanged into the model class of the final head (df55cff7; model code unchanged from e598a840), with no shape or key remapping;
    - the outputs are non-degenerate.
  - **R inputs (orchestrator with Hannah as custodian, approved with conditions).** R's survey states, times and cutoffs come only through `nirops_access.py` in Daniel's container, with a committed allowlist of exactly the 6 R IDs. Hannah checks the allowlist and driver shas before the run, and the access log and audit after it.

## 3. far_share (descriptive, carries no weight)
- **Definition.** F is the set of offsets at Chebyshev distance ≥ 2 on the 9×9 stencil.
  - Mass is taken from `kernel_rates` after modulation.
  - It is averaged over part-a training scored cells, with equal weight.
  - The same stencil is used for d4_wind, d2_nll and d2_bracket.
- **Recovery tolerance.** Committed before the output was read, at 946f1e4e (`TOLERANCE_shape_recovery.md`).
- **Result.** Elena's 780cbabe: MCEM and mean-field NLL recover the far share in both kernels, while plug-in inflates it (0.388 vs 0.072). Verified: PASS (Owen, LEDGER-SMOKE-2 @9f0a5162, row 26).
  - **Interpretive note:** the real part-a gap in NLL (about 0.64–0.68 vs MCEM about 0.07) is *not* explained by estimator bias under the synthetic model.

## 4. Crop property (A1 §3.1; item 22 declaration)
- **Finding.** 12,384 of 122,640 new-burn cells (10.1%), in 97 of 3,773 intervals, fall outside `crop_box(initial, 10)`. They are dropped in all arms. This is a property of the recipe, not a change to it.
  - Source: Elena b7cdc48f. Verified: PASS (Owen, LEDGER-SMOKE-2 @9f0a5162, row 40).
- **Note:** spread beyond about 3.75 km is scored as unreachable and never trained.

## 5. Half-step scope
- "Half-step" in A1 §2.1 means Marcus's hourly CA (`half_step=True`) on H only.
- No mean-field half-step is added for d4_wind. Any such comparator needs its own synthetic check and is descriptive.

## 6. Pins (from `STAGE2_PINS.md`)

| item | state |
|---|---|
| refit train-events, final | **PENDING** (pre-weather list bbedca82 = fit-23 + 490, checked against allowlist 7db3cc0e) |
| part-a pool manifest | daniel/data-fetch-3 982eb71c, `parta_pool/`: `PERIMETER_MANIFEST.json` sha256 `08f96b450cfe9c72420b1d38ffe677aa50a5399cff0d82c0333e555edf842e77`, `events.json` sha256 `fef3626051d4a06b80c355b0773a28ce28c5bdc6131f5208ac4a7d89405b3b19`, 490 `states.npz`. These are the files the §3.1 stage-1 report (7b810e66) reads; Victor re-ran that report on them and got byte-identical output. Pinned |
| weather input manifest (refits) | part a: `f70e52b0…` (490 events, 16,664 pins; completeness `09af55fa…`; data-fetch-3 748afe70), event set equal to the part-a allowlist. Fit-23 US: **PENDING** (after night 2, 14 Nov) |
| rebuild environment | **PENDING** |
| refit receipts: d4_wind_rebuilt, logistic_rebuilt, d4_wind_recal, d2_nll_rebuilt, d2_bracket_rebuilt | **PENDING** |
| rate-mixture form | **PENDING** |
| part-c manifests | **PENDING** |
| item 14 weather outcome (AlderCreek T/wind) | **PASS WITH NOTES** (Hannah, ledger row 72, ff7857b2: full sha256 match; not a file copy by inode, mtime and request log; she does not hold the files, and a content copy by another path is not excluded). Daniel, `data-fetch-3/weather/ITEM14_ALDERCREEK.md` at 24d20770: the three model-read channels (2 m temperature, 10 m wind east/north), the node-index raster and the band table (2,139 hours) are byte-identical to the owner's files, so median and p95 abs. difference are 0 (thresholds: median ≤ 1 K or 1 m/s, p95 ≤ 3 K or 3 m/s). Covers only those channels; RH, precipitation and ERA5 are not rebuilt |

**Control-run evidence.** Owen verified Marcus's unmodified-rollout control on R (owen-smoke-2, rows 25 and 33).
- All 273 rebuilt cases are identical.
- d4_wind sits at the 4.17e-7 floor.
- c651_mc is bit-identical on 40 of 273 cases: a post-hoc subset of 34, disclosed, plus 6 chosen by a fixed rule.

## 7. Wording updates to A1
- **Line ~113:** "Open-Meteo, day 2" becomes "Open-Meteo, the 13 Nov 00:12 UTC fetch" for the AlderCreek weather.

- **Erratum (orchestrator, 16:05Z):** A1's status line still reads "DRAFT revision 24 (amendment 1 to the revision-23 freeze candidate), not frozen". It should read: "Frozen at stage 1 (`FREEZE.json`, with amendment 1, A1 item 30); stage 2 by this amendment." This changes no rule, number or membership. The frozen file is not edited in place, so the stage-2 record carries the correction.

## 7a. Named stage-2 items (orchestrator rulings, 2026-11-13)
These are stage-2 change items, made before any refit has run and before part c opens.

**S2-1. Promotion from part d skips incidents near training fires** (A1 §1.2 items 5, 6, 10 and 12). *Found by:* the custodian's ledger row 86, totals only:
- kept b and c are clean against part a (0 hits under item 9);
- part a was never filtered against part d: 12 part-a fires are within 50 km and 30 days of 9 of the 31 kept part-d incidents;
- fit-23 and Wapiti are clean against b, c and d (row 85).

*Gap:* A1 lets a d incident replace a b or c fire (items 5, 6 and 10), but item 9 filters part a against b and c only. A replacement made after the refits are trained (for example an input-build failure under item 5) could bring in a d incident near a training fire. At that point item 9 could not be honoured without retraining.

*Rule:* when the custodian promotes a d incident into b or c, she **skips** any d incident within 50 km and 30 days (point of origin and discovery date, A1 item 11) of any training fire **as trained**, meaning part a, fit-23 and Wapiti. She takes the next eligible incident in `u` order and logs each skip with counts only. The check uses metadata only. The item-12 floor counts all remaining d incidents. At most **1** promotion is possible: kept d is 31 and the floor is 30.

*Not done:* the 12 part-a fires are **not** dropped from training. With at most one promotion possible, the skip rule closes the gap without changing the training list. *Assessor:* the required minimum is met; the alternative (dropping the 12 part-a fires) was offered and not adopted.

*Limitation, stated for any later use of d:* 9 of the 31 kept-d incidents are within item-9 proximity of part-a training fires. Any later test on d must first apply item 9 from the training side.

**S2-2. `logistic_rebuilt` recipe: a clarification of a line that cannot be executed as written** (named item). *Assessor (2026-11-13):* "Named item. The resolution follows the archive object's recorded recipe and is made before any refit."

*The contradiction.* A1 §3.1 reads "Fit: `fit_logistic(C=1.0, seed=0)`, negatives subsampled at 0.05 and inverse-weighted". `baselines.fit_logistic` takes no sample weights: it uses an unweighted `StandardScaler` and `LogisticRegression(C, max_iter=2000)`. So it cannot inverse-weight, and the line contradicts itself.

*Resolution (orchestrator ruling; assessor: a named item, labelled clarification).* The object being rebuilt is the archive `logistic`. Its own record (`logistic.json`) says "negatives subsampled at the stated fraction and weighted by its inverse", and it was produced by `research/forecast-v2/scripts/pipeline.py` `command_baselines` (pipeline.py 88d376d2…, lines 529–560). `logistic_rebuilt` therefore uses `command_baselines`'s recipe. Every point where it differs from `fit_logistic` is pinned literally:
1. **Samples and order.**
   - Samples come from `fit_samples(..., mixed=False)`: `perimeter_samples(event, ..., crop=True, ...)` for each event in the **order of the pinned `TRAIN_EVENTS_final` file**, then in pipeline interval order within each event.
   - The interval cap is `--max-fit-intervals-per-fire 0` (all intervals), per the archive invocation evidence.
   - **Sample order is part of the recipe** (item 3).
2. **Row mask (per sample):** `score_mask & isfinite(environment) on every channel & isfinite(features) on every feature`, with features from `pipeline.logistic_features(sample, names, terrain_gradient)`.
3. **Subsample draw:** a single generator `rng = np.random.default_rng(seed)` with seed 0, advanced **sample by sample in the order of item 1**: `keep = (y == 1) | (rng.random(len(y)) < 0.05)` per sample. Changing the sample order changes the draw.
4. **Weights:** 1 for positives and 1 / 0.05 = 20 for kept negatives.
5. **Scaler: fit WITH `sample_weight`** (`StandardScaler().fit(x, sample_weight=w)`), giving weighted moments. This differs from `fit_logistic` and from the `d4_wind_recal` pin.
6. **Estimator:** `LogisticRegression(max_iter=3000, random_state=0)` with the default C = 1.0, fit with `sample_weight=w`.

*Has any score been seen?* Whether any score of `logistic_rebuilt` under either reading has ever been looked at: **PENDING**, a plain yes or no from the refit author and the independent verifier. If no, the choice was made blind to outcomes. If yes, it is stated here with what was seen.

*Descriptive line, after pinning:* the largest |Δp| on part a between the two readings, so a reader can see how much rides on the choice. The expectation that it is small is a hypothesis, not a claim.

*Verification.*
- **Archive invocation evidence: PASS** (independent verifier, LEDGER-SMOKE-2 row 61, 9c39559b). The archived `a03_baselines` argv, parsed with the pinned pipeline.py parser, gives `max_fit_intervals_per_fire` = 0. A1 §3.1 lines 215 and 222 pass `--max-fit-intervals-per-fire 0`.
- **Reproduction of `logistic_rebuilt` from this pinned text alone**, as for the recalibration: **PENDING**. The `logistic_rebuilt` refit and the leak-bound fit are released on that row.

*Consequence for the `d4_wind_recal` pin.* Its estimator is **not** the same as `logistic_rebuilt`'s. They share only the 0.05 fraction, the 1/0.05 weights and C = 1.0. The recal scaler is unweighted and uses `max_iter` 2000; `logistic_rebuilt` here has a weighted scaler and `max_iter` 3000. The recal recipe itself is unchanged and stays identical to the development recalibration (`derive/logistic_dev.py`). Any wording implying the two estimators are identical is corrected by this item.

## 8. Archive-trained rows promoted to named secondaries on part c (A1 §3.1, conditional on item 14)
**Orchestrator decision, 2026-11-13.** A1 §1.2 item 14 and §3.1 (revision 29) allow the archive-trained rows to be promoted "by amendment to named secondaries on part c" if item 14 passes before part c opens. Item 14 now passes on **every channel it names**: temperature, both wind components, slope, tree cover and biome. **One leg (non-weather rasters) is unverified** (see below). Item 14 is a one-fire check. Each leg, with its scope and verifier:

| leg | fire(s) | result | verified by |
|---|---|---|---|
| non-weather rasters, cell by cell (slope, tree cover, biome and the other shared rasters) | AlderCreek (MT-BDF-006269), one fit fire | all **44** shared rasters have identical masks and identical or float32-close values (daniel/data-fetch-3 4c643033, `cmp_region.py` 9857fe46…) | **reported by the fetcher; not yet independently verified** (A1 says the same). Verification requested before the freeze |
| temperature and wind (u, v), every cell and hour | AlderCreek | byte-identical to the owner's files, so median and p95 abs. difference are 0 | custodian, ledger row 72, PASS WITH NOTES |
| end to end: stored predictions reproduced from rebuilt inputs | the 6 cohort-R fires (US2024), 273 cases | max \|Δp\| 3.6e-7, 0 above the 4.2e-7 floor | independent verifier, LEDGER-SMOKE-2 row 58, independent rerun |

- **44, not 47.** A1 revision 23 said "47". The amendment-1 erratum corrects this as a counting error: the source table has 66 rows, of which 44 are shared rasters, 21 are archive-only weather files and 1 is the archive-only GLAD canopy height.
- **Channels not rebuilt.** RH, precipitation and ERA5 are not item-14 channels and were not rebuilt (row 72 notes). **None of the three promoted models reads them.** `d4_wind_seed0` and `logistic` read exactly the six pipeline source channels (`pipeline.py` SOURCE_CHANNELS: 2 m temperature, 10 m wind east and north, slope, tree cover, biome). `c651_mc`'s checkpoint contract lists the same channels, with biome one-hot (19 inputs). So the unrebuilt channels cannot affect these rows.

This amendment therefore promotes exactly **three** archive-trained models to **named secondaries** on part c, scored on rebuilt inputs:

| name | frozen object | sha256 | note |
|---|---|---|---|
| `d4_wind_seed0` | `forecast/runs/20261030_perimeter_trained/execution_v3/final/d4_wind_seed0/checkpoint.pt` | `33c5b3cfc1332940a905da80b9414d0a5a91aad06d8797b46dc151e893de48a3` | trained on the fit-23 archive inputs |
| `c651_mc` | `forecast/runs/20261010_categorical_balanced_benchmark/candidates/mixed_3_5_7_9_02_lr0.1_warmup_cosine/checkpoint.pt`. Marginals come from 1,024 Monte Carlo trajectories per case, with **seed 0**: `pipeline.c651_monte_carlo(predictor, sample, names, n_samples=1024, seed=0)`, called exactly as in the frozen producer `score_cohorts.predict_case` (`research/forecast-v2/scripts/score_cohorts.py` line 191, last changed a5ba8210, sha256 88bb3839…, verified). The per-case seed is `case_seed(0, event_id, t1)`, with trajectory batch 32. The part-c `c651_mc` run calls that line unmodified | `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843` | **Revision-28 limitation:** trained only on hindsight-restricted interior patches of final kriged footprints, it is uninformative on full-rectangle perimeter labels and is **not a comparator**. Tail reported only against the 1/1024 floor. **Scored on the primary Brier statistic and its paired comparisons only; no arrival RPS** (A1 §5.2, revision 7, declared unavailable for this model and closed to later addition). **The seed must be a number in the frozen text. If the pinned prediction command is not available by the freeze, `c651_mc` is not scored on part c** |
| `logistic` | `forecast/runs/20261030_perimeter_trained/execution_v3/baselines/logistic.pkl` (coefficients in `logistic.json`, sha256 `7640bf6cde5d9ab95371c32828fd325c9618e16a6d4e20ea37e7fa2fd8a1c6df`) | `4acab15a10a9c128741e442f5da7a99dee45986e9dfa64dea35070de51deed49` | trained on the fit-23 archive inputs |

- **Out of sample: a condition of scoring these rows (training fires against part c).**
  - The training events are the fit-23 US fires, for all three, plus KFS_02 and KFS_03 for `c651_mc`.
  - **ID overlap.** Part a–d were drawn from the clean pool of A1 §1.2 item 1, which keeps only incidents with `project_status == "unused_in_repo_events"` and no shared IRWIN with a project fire. So no training event can be a part-c fire by ID. KFS_02 and KFS_03 are Korean, so they are not NIROPS incidents at all.
  - **Proximity** (A1 item 9's 50 km and 30 days, applied here to the training fires).
    - KFS_02 and KFS_03 satisfy it by geography: they are in Korea, and every part-c incident is a US NIROPS fire.
    - Only the fit-23 fires need checking. **Result: no overlap** (custodian, ledger row 85, totals only; rows 83–84 are superseded, because they counted rows already excluded by §1.3):
      - ID overlap is 0 against b and c, also by unit-number key.
      - A1 §1.3 ("Independence from fit fires") already excluded every b/c/d incident within 50 km and 30 days of a fit-23 fire or Wapiti (`cohort/apply_filters.py`, `ref.csv` = the 23 fit fires plus Wapiti). Against **kept** members (COHORT_FINAL d5ae66f4): b 0, c 0, d 0. All 5 incidents flagged in row 83 were §1.3 exclusions.
      - Near-duplicate pairs (< 1 km and < 2 d) between the full training list (part a + fit-23) and kept b, c and d incidents: 0.
    - So the promoted rows are out of sample by A1's own rules. No incident is excluded, and no change is made to training lists or scoring.
- **Secondaries only.** None of the three is, or replaces, a §6.1 criterion object. Those stay `persistence`, `dilation_8h`, `logistic_rebuilt` and `d4_wind_recal`. The rebuilt refits stay the confirmatory comparators.
- **No named secondary's result changes the §6.1 verdict or the wording of the headline claim, whichever way it falls.** Each is reported with its own paired comparisons and intervals, with no multiplicity adjustment and no claim that would need one. Every sentence about them says "secondary, no multiplicity adjustment" (§9, row O12).
- **Count.** This adds three named secondaries. The other part-c secondaries (§9, §13) are unchanged.
- **Disclosed limitation, carried into every sentence.** All three were trained on archive inputs before the split.
- **Assessor's reading (2026-11-13): PASS WITH NOTES.** "The promotion follows A1 §3.1's pre-stated condition and adds no criterion object. Notes 1–7 are addressed in this section; note 1 (training fires against part c) is a condition of scoring these rows." *Follow-up (assessor, 2026-11-13):* the note-6 departure is accepted, because A1 §5.2 governs, and `c651_mc`'s row now states what it is scored on. Note 1 is closed by row 85 (no overlap), and note 6 is closed (seed 0, pinned above). **Open until the freeze commit:** note 4 (a verifier row for the non-weather leg).

## 9. Outcome-to-claim table, parts c and b (written before part c opens; changes no criterion)
Each row fixes the sentence the paper may write for one possible result.
- The rows apply to **part c** (headline candidate) and, word for word, to **part b** (the later named candidate of §11, if one is ever named). For part b, "headline" means that candidate.
- **Neither part c nor part b is the clean confirmation.** Both carry the same exposure label, and the clean confirmation is **CR1 Tier 2** (fires from 2027-01-01). Every b or c sentence ends: "This test set is not the clean confirmation; that is CR1 Tier 2." 
- "Superior" means **all six** §6.1 criteria pass for that candidate, on ≥ 20 analysable fires.
- The headline is `d2_bracket_rebuilt`. If it is not admitted, the headline is `d2_nll_rebuilt`. If neither is admitted, there is none (§6.1, revision 29).
- Every part-b and part-c sentence carries the survey-timing limitation (§1; b's membership changes are among the 18): "labels, perimeters and growth sealed; survey-timing metadata exposed before the split; membership rules used it".
- Any other admitted candidate is **secondary**, with its own verdict and **no multiplicity adjustment**. Any statement about it says so.
- **Part-a evidence before part c opened (dated 2026-11-12; verified: PASS WITH NOTES, Owen, LEDGER-SMOKE-2 @9f0a5162, row 49).** Elena's part-a fire-level cross-validation, **pinned version of record 4278da2d** (earlier runs 96f99bf6 and 7cc21f47 are superseded), used a **covariate-free analogue on 25 fires, not the neural refit** (`d2_bracket_rebuilt` itself was not cross-validated). Out of sample in the 4 km band (paired Brier, whole-fire intervals):
  - MCEM (bracket kernel) − plug-in: **+0.0091 [+0.0057, +0.0124]**. The bracket kernel was worse; it was better on 5 of 25 fires. Source: `S-D2/results/cv_part_a_pinned.json`, seed 20261030.
  - persistence − MCEM: **−0.0014 [−0.0078, +0.0054]**. The bracket kernel showed no skill over no growth. Source: `S-D2/results/cv_baselines_pinned.json`, seed 20261112.
  - `logistic_cf` − plug-in: **−0.0003 [−0.0008, +0.0003]**, `logistic_cf` better on 17 of 25 fires. The best kernel (plug-in) was no better than a 3-feature covariate-free distance logistic (`logistic_cf`). Source: `cv_baselines_pinned.json`. Plug-in is the best kernel: the converged composite is also worse than plug-in, +0.0068 [+0.0044, +0.0091].

  This was recorded before part c opened. **A negative part-c result for the headline is therefore the expected one, and a positive one would run against the training-set evidence.** Any part-c sentence about the headline cites this line once it is verified. The headline and fallback stay exactly as registered.

| # | part-c outcome (headline candidate) | what the paper may write | what it may not write |
|---|---|---|---|
| O1 | Superior: criteria 1–6 all pass | "On 30 reserved NIROPS fires (N analysable), the pre-registered headline candidate improved on persistence, 8 h dilation, the rebuilt logistic reference and the recalibrated rebuilt d4_wind in the 4 km band (paired Brier, 95% whole-fire interval below 0), with low-probability calibration no worse than the references." Plus the limitation. | "Confirmed" or "validated" without the limitation. Any claim outside the 4 km band, outside NIROPS survey horizons, or for other regions. |
| O2 | Beats persistence (1) and dilation (2); **not superior to `logistic_rebuilt`** (3 fails) | "The candidate improved on persistence but did not improve on a rebuilt logistic reference trained on the same fires. The pre-registered decision is NOT SUPERIOR." Also state: "Development power against the logistic reference was about zero at the effect seen on the development cohort (§6.3), so this outcome was the expected one." | That the candidate "matches" or is "equivalent to" logistic, since no equivalence test is registered. That it "beats the baseline", unqualified. |
| O3 | Beats persistence, logistic and dilation; **fails criterion 4** (vs `d4_wind_recal`) | "Improved on persistence and the logistic reference, but not on the recalibrated physical model, so the D1/D2 method change adds no demonstrated gain over recalibration. NOT SUPERIOR." | That the method change caused the gain over logistic. |
| O4 | Criteria 1–4 pass; **fails criterion 5** (low-bin calibration) | "Better on paired Brier, but worse calibrated in the lowest probability bin than a reference. NOT SUPERIOR under the pre-registered rule." | That it is superior. |
| O5 | **Not superior to persistence** (1 fails) | "The candidate did not improve on persistence in the 4 km band (NOT SUPERIOR)." Report the interval and the direction. If the interval includes 0, say "no detectable difference at this sample size", with the half-effect power of §6.3 (0.42 at 30 fires). | "Worse than persistence", unless the interval lies above 0. |
| O6 | **< 20 analysable fires** (criterion 6) | "INCONCLUSIVE: too few analysable fires; results descriptive." | Any verdict. |
| O7 | Headline `d2_bracket_rebuilt` **not admitted**; fallback `d2_nll_rebuilt` scored | The O1–O6 sentence for `d2_nll_rebuilt`, preceded by: "The pre-registered headline candidate was not admitted (reason); the pre-registered fallback is reported as the headline." | That the bracket model was tested on part c. |
| O8 | **No headline** (neither admitted) | "No candidate met the admission rules, so there is no headline part-c decision. Secondary candidates are reported individually, without multiplicity adjustment." | Promoting a secondary result to headline. |
| O10 | Headline **worse than, or not better than, `d4_wind_recal` or `logistic_rebuilt`** (criterion 3 or 4 fails, whatever the direction of the interval) | "Handling the survey gaps correctly in the likelihood did not improve forecasts over [the reference]; P-D2 is not supported." Add the dated part-a cross-validation line above. If the interval lies wholly above 0, also say the candidate was worse. | That the bracket likelihood helps forecasts. That the result is unexpected or anomalous. |
| O11 | The **fallback or a secondary candidate beats the headline** (or passes criteria the headline fails) | "[Candidate] scored better than the pre-registered headline on [criteria]. It is reported as secondary, without multiplicity adjustment; the pre-registered decision rests on the headline." | Promoting the fallback or a secondary to headline, or any superiority claim for it. |
| O12 | Any result of a **named archive-trained secondary** (§8: `d4_wind_seed0`, `c651_mc`, `logistic`), in either direction | "[Model] (archive-trained, named secondary, no multiplicity adjustment): [paired results]." Plus the §8 limitations, and for `c651_mc` the revision-28 statement. | Any claim from these rows. Any change to the §6.1 verdict or the headline wording because of them. Calling `c651_mc` a comparator. |
| O9 | **Material leak bound** (§1; `LEAK_BOUND_PLAN.md`) | Whatever row applies, plus: "A part-a measurement found that survey-timing information could improve the reference model detectably. Criteria that depend on constants not shown independent of sealed survey timing are reported as descriptive." | Omitting the leak-bound result. |

**Preprint wording (Wapiti).** Marcus's reconciliation note (1c3c4270) finds that the sign change is entirely due to the interval set: on the preprint's 25-interval cohort the BSS is +8.17%; on all 52 eligible intervals it is −44.5%; and the 24 common intervals have bit-identical predictions. Verified: PASS WITH NOTES (Owen, LEDGER-SMOKE-2 @9f0a5162, row 42). Any text about the preprint's Wapiti figure says it is **"specific to its 25-interval August cohort"**, and no row of this table cites the preprint figure as evidence for any candidate.

For **secondary candidates and comparator rows** (d4_wind vs logistic on part c, `c651_fullvalid_rebuilt` and others), the same sentences apply with "secondary, no multiplicity adjustment" added. A secondary success never becomes the headline.

## 10. A1 closed to new change items after the stage-2 freeze
- A1 has **30 change items** in its revision log as of this draft. Once stage 2 is frozen and verified, **A1 accepts no new change items**.
- **One stated exception:** the amendment that names the part-b candidate by SHA (§11).
- Also allowed: errata that change no rule, number or membership, each logged as an erratum, and the separately named `c651_fullvalid_rebuilt` amendment (§13), which is part-a development and an admission under existing rules.
- **Later ideas go to CR1** (`clean_replication/`), before its freeze. Part b stays held for a later named candidate (§11); it is opened only by the excepted naming amendment, under §11's conditions.
- A proposal that needs an A1 change after the freeze is recorded as "not adopted: A1 closed" and is redirected to one of these two places.

## 11. Part b: held for a later named candidate; conditions for naming one (revised 2026-11-12)
- **No reservation at this freeze.** An earlier draft reserved part b for one combined candidate (bracket likelihood plus the rate-mixture form). That reservation is **withdrawn**: part-a cross-validation on the covariate-free analogue pointed against the bracket arm out of sample (§9, dated line; Owen row 49).
- **A1's wording stands unchanged.** A1 §1.2 item 4 reads: "a confirmatory test set held for a later named candidate… opened only when a named candidate is declared by SHA in an amendment committed before the opening". §9 step 5 and §6.1 say the same. This section adds conditions for naming a candidate and removes nothing.
- **Conditions for naming a candidate.** All of the following must hold, and each is recorded in the naming amendment (the one exception of §10):
  1. **Beats `logistic_cf` out of sample on part a.** In fire-level cross-validation on part a (whole-fire folds, 4 km band, paired Brier), the candidate beats the covariate-free distance logistic `logistic_cf` (and so the plug-in kernel and `logistic_rebuilt` as well) by at least a margin.
     - **No test-fire future.** For each held-out fire the candidate may use only that fire's earlier intervals, or a mixture whose weights are learned on the training fires. No information from the held-out fire's later intervals may enter.
  2. **The margin is stated beforehand.** The margin, the fold assignment and the scoring command are committed **before** that cross-validation is run for the candidate, and the naming amendment cites that commit.
  3. **Power supports opening b.** The power of the candidate against `logistic_rebuilt` is estimated on **part a only**, using the §6.3 method on part-a folds. If it is below **0.50 at 30 fires**, part b is not opened; it stays held, and this is reported. The threshold is fixed here, before any estimate.
  4. **One object.** The candidate is a single declared model. Recalibration is applied or not applied, decided in the declaration, never two arms on b. It is declared by commit hash before part b opens.
- **Same criteria.** §6.1 criteria 1–6 apply, including the ≥ 20 analysable-fire rule. Outcome sentences follow §9.
- **Same exposure label as c.** b's membership is among the 18 b/c/d changes made by timing-dependent rules. **b is not the clean confirmation**; that is CR1 Tier 2.
- **Timing disclosure.** If the candidate is designed, or any of its choices are made, **after part-c results are seen**, the naming amendment says so explicitly and lists which choices came after.
- The part-c headline (`d2_bracket_rebuilt`; fallback `d2_nll_rebuilt`) is unchanged.

**`d4_wind_recal` recipe (pin, not a criterion change).** The details A1 leaves open (the subsample draw, the fit population, clipping, the estimator, and the frozen coefficient file with a reproduction tolerance) are pinned in `STAGE2_PINS.md`. Iris assessed them. The *recipe* is identical to the development recalibration behind item 13. The *fitting entries* differ: they use the per-model producer rule, not the development set's common support. A descriptive part-a-only companion, `d4_wind_recal_band`, shows how much the full-grid fit matters in the band. It has no role in any criterion and is never run on b or c. Limitation, disclosed: the full-grid fit may calibrate worse in the band, which would make criterion 4 easier to pass.

**Named scorer for every criterion pair (pin, not a criterion change).** Criteria 1–4 are computed by `freeze/score_criteria.py`, a thin wrapper over the frozen `sd9bench.score` with the references fixed to the four §6.1 objects. The frozen CLI cannot write criteria 3 and 4 (Owen, eb4d05f5). The same tool scores part a (development, in-sample) and part c. Owen's numpy-only scorer is the independent second run (see `STAGE2_PINS.md`).

## 12. Minimal custody procedure: a condition of opening part c (Iris; not the full custody design)
Part c is not opened until **all** of the following hold:
1. **Audit verdict delivered.** Done: Hannah's survey-timing audit, ledger row 38, and the disclosure text check, row 41.
2. **The custodian builds the labels.** Label files and perimeter states for part c (and part b) are built **only by the custodian**, from the frozen build script, with the command logged.
3. **Sealed files hashed.** The sha256 of every sealed part-c file (labels, perimeter states, manifests) is recorded in the stage-2 record before any scoring.
4. **One custodian scores.** The scoring run is performed by one custodian, from the stage-2 SHAs, with the exact command logged.
5. **Workers never see labels.** Worker sessions receive scores and receipts, never part-c label files.
6. **Two runs, compared exactly.** Two independent scoring runs from the frozen SHAs, in separate fresh containers, are compared exactly (byte-identical score records) before any number is reported. A mismatch stops reporting until it is resolved and logged.

7. **No-touch declaration at opening.** Every worker session declares that it will not build, read or derive part-b or part-c labels or perimeters until the decision is recorded. A breach moves the affected fires to an **"exposed" stratum**, which is reported separately.
8. **Access audit before opening.** Every worker session runs `verification/access_audit.py` on its own transcript and its subagents' transcripts, and sends the output and the transcript sha256 to the custodian. The script is `verification/access_audit.py` at commit **8156141c** on claude/verification-ledger, sha256 `e18338fb190dbddcb58bd4ae0c9374365ead6d59343d389540ad384230f69bf8`. Nora passed it (her row 52, 8e1e09c6), and it is Hannah's ledger row 59 (f52f2ea9). Earlier heads (4844e7fb, 72a07bf1, a4094fa7) are superseded and are not cited; a4094fa7 had a GOFER pattern regression.
   - **Roster closed.** The pre-opening roll-out covers 16 sessions in Hannah's ledger rows 58–71 (closure noted at row 71, 999aaa57): rows 58, 60, 62, 63, 64, 66, 67, 69, 70 and 71.
   - **Re-run at opening** (adopted by the orchestrator 2026-11-13; `CUSTODY_NOTE_A1.md` §2 item 6, commit 07a4a25a on claude/verification-ledger, file sha256 `37df2b202a9e85db6ef41f4345e1651d9dfa28d7caefcc398a4a13147819123f`). At the opening of part c, the custodian has the access audit re-run, at the same script version, for any session not on the roster and for every session whose transcript (main or subagent) has grown or changed since its recorded hashes. Each session runs it on its own transcripts. Opening proceeds only once those rows are recorded; a session that cannot re-run is recorded, and opening waits for the orchestrator's decision.

The same conditions apply to opening part b. This text matches Hannah's `verification/CUSTODY_NOTE_A1.md`.

## 13. Out of scope
- **c651_fullvalid_rebuilt** goes in a separate, later amendment, developed first on part a and using the 44 events fetched on 14 Nov. It does not block stage 2. If part c opens first, c651_fullvalid is not scored on part c.
- **CR1** has its own preregistration.
