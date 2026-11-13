# Survey-timing leak bound: plan and "material" threshold (S-D9). NOT RUN

**Status.** This file was written and committed before any run. It is a part-a-only measurement and is descriptive. The orchestrator approved it on 2026-11-12, adopting Iris's item 5.
- Marcus runs it with the part-a refits, on part-a fire folds, and not before them.
- Owen verifies it.
- It reads nothing from parts b, c or d, and no H-test fire.

## Why
Two files on Main carry survey timing for every NIROPS incident, including the sealed parts: `data-fetch/nirops_incidents_v2.csv` and `data-fetch/incident_metadata.csv`. The fields are `first_utc`, `last_utc`, `days` and `discovery_utc`.
- At any cutoff, `last_utc` (and `days`) is **future information**. It tells how much longer the fire was surveyed, which is a proxy for how long and how far it kept growing.
- This measurement bounds how much a model could gain from that information. If even a model handed the information directly gains little, a design choice that leaked it indirectly could have gained no more.

## The forbidden features
They are computed per training interval, from **part-a** metadata only:
- **F1, remaining survey days.** `r = max(0, last_utc − cutoff) / 24 h`, entered as `log1p(r)`.
- **F2, cadence**, for the secondary run only: `surveys / max(1, (last_utc − first_utc)/24 h)`, entered as `log1p`.

## Arms
Each arm fits a model **with and without** the feature on identical folds and entries. The comparison is paired.

| arm | base model | augmented model |
|---|---|---|
| L (primary) | `logistic_rebuilt`: its frozen feature set and fit settings (A1 §3.1) | the same model plus F1 |
| R (primary) | `d4_wind_recal`: one-feature logistic on logit(p) of `d4_wind_rebuilt`, using each fold's held-out-safe refit predictions | logit(p) plus F1 |
| L2 (secondary) | `logistic_rebuilt` | the same model plus F1 and F2 |

**Arm R** is only as available as the `d4_wind_rebuilt` fold predictions. If the refits produce no fold-held-out predictions, arm R is reported as NOT RUN. In that case a recalibration fitted on its own training predictions is **not** substituted.

## Folds and population
- **Folds.** 5 folds grouped by fire over PART_A_ALLOWLIST_FINAL (7db3cc0e…). A fire goes to fold `int(sha256(Incident_C).hexdigest(), 16) mod 5`. It is fixed now.
- **Entries.** The same intervals, cells and band as the part-a training data of the base model (A1 §3.1 rules). The primary population is the 4 km band (A1 §4); the full domain is secondary.
- **Score.** Out-of-fold pooled Brier. ΔBrier is augmented minus base, so a negative value means the leak helps.
- **Interval.** A 95% whole-fire bootstrap of ΔBrier: B = 2,000 fire resamples, seed 20261030 (the A1 seed).

## "Material" (fixed now)
For an arm, the leak is **material** if the 95% interval of the paired ΔBrier lies **entirely below 0** in the 4 km band. This is the same test the §6.1 criteria apply ("the interval lies below 0"), so "material" means: detectable by the protocol's own decision test on part a.

Also reported, without bearing on the label:
- the relative Brier change;
- the per-fire ΔBrier distribution;
- the lowest-bin [0, 0.1) calibration gap with and without the feature;
- the fitted coefficient on F1.

## Consequence (fixed now)
- **Not material in arms L and R:** the limitations paragraph cites the measured bound (the interval and the relative change).
- **Material in either primary arm:** the result is reported in the limitations together with Hannah's audit result.
  - Any A1 design constant whose provenance table entry is not shown to be independent of b/c/d survey timing is flagged.
  - Criteria that depend on a flagged constant become descriptive, per Iris's assessment.
- In either case, part-c results are also reported by tercile of survey span (amendment rule g).

## Outputs
- `derive/LEAK_BOUND.json` and `.md`, with input hashes, code SHA, fold assignment hash and receipts.
- No cell-level data is committed.

## Not decided here
None. Any change to this plan before the run is made by a committed revision of this file, with a reason.

## Revision 1 (2026-11-12, before any implementation or fit): answers to Marcus's five questions
These points were not fixed above. They are fixed here before code is committed.
1. **Source of the times.** F1 and F2 use the **metadata** `first_utc`, `last_utc` and survey count, because that is the leaked field being bounded.
   - They are read for part-a records only, with the allowlist-safe reader (`nirops_access.py`, ab065e85). The filter to PART_A_ALLOWLIST_FINAL is applied by ID before any attribute leaves the driver, and the read is logged in the ACCESS_LOG.
   - **Check, not a substitute:** the same three values are computed from the pinned perimeter states (982eb71c `states.npz` times). The report gives the number of incidents where they differ and the largest difference.
   - *Reason:* if the builder dropped surveys, the state times would understate `last_utc`, and the bound would understate the leak.
2. **Arm R is NOT RUN** unless the orchestrator approves extra fold refits of `d4_wind_rebuilt`. That approval would itself be a further revision.
   - A1 §3.1 refits once, with no folds, so no held-out-safe predictions exist.
   - An in-sample recalibration is not substituted. Arm L is then the only primary arm.
3. **Entries.**
   - **Scoring** uses every cell of the held-out fires' intervals, unsubsampled: the 4 km band is primary and the full domain is secondary. The 0.05 negative subsample and its inverse weights are a training device only.
   - The base and augmented fits use the **identical** subsample (same RNG draws).
   - The A1 §3.1 crop, `crop_box(initial, 10)`, applies to both training and scoring, as in base training. The number of excluded new-burn cells is reported.
4. **Cutoff.** The cutoff is the interval's **start** survey time t0 (the `cutoff` column), exact to the second, not floored.
   - *Reason:* t0 is when the forecast is issued, and t1 is the target time. Using t1 would mix the leak with the horizon.
5. **Timing.** The measurement starts after the part-a weather fetch and the `logistic_rebuilt` refit.
   - The implementation and the fold-assignment hash are committed before any fit.


## Revision 2 (2026-11-13, before any implementation or fit; APPROVED by the orchestrator 11:37Z)
Proposed by the plan author after the refit author's feasibility note. **Nothing has been implemented or fitted.**
1. **Timing (replaces revision 1 item 5).** The measurement may start once the part-a weather fetch is done (pinned: `parta_input_manifest_night1.json` f70e52b0…). It no longer waits for the A1 §3.1 `logistic_rebuilt` refit.
   - *Reason:* arms L and L2 refit the `logistic_rebuilt` **recipe** inside each part-a fold (A1 §3.1 frozen feature set and fit settings). They never read the A1 refit's output. The fit-23 fires are not in the folds, so the fit-23 weather (day 2) is not needed.
   - Arm R is unchanged and stays **NOT RUN** (revision 1 item 2).
2. **Clarification of the base model in arms L and L2.** In each fold, the base is the `logistic_rebuilt` recipe trained on the other four part-a folds only. It is therefore not the A1 `logistic_rebuilt` object, which is trained on fit-23 ∪ part a. The output says so in every row. The bound measures what survey-timing features add to this recipe on part a. That is the quantity §"Material" is about.
3. **Unchanged:**
   - the code-first rule: the implementation, the fold-assignment hash and a smoke test on the committed fixture are committed before any fit;
   - the folds, entries, cutoff (t0), score, bootstrap (B = 2,000, seed 20261030), "material" threshold and consequences.
4. **Where it runs.** In the executor's container, which holds the pinned part-a environment, as a tracked task from the refit author's pinned commit. The custodian's `checked_utc` rule is applied before the pin check. The independent verifier checks the run.

## Revision 3 (2026-11-13, implementation details; before any fit)
Revision 2 is kept as written above. It holds the timing change and the base-model clarification, and the
orchestrator approved it at 11:37 UTC. This revision fixes only the implementation details revisions 1–2 left
implicit. **Nothing has been fitted.**

**Approvals.**
- Approved by the plan author, 2026-11-13.
- Revision 2 approved by the orchestrator, 11:37Z.
- The independent verifier's reading of this revision is recorded below before any fit.

1. **Samples.** Every part-a interval ≤ 48 h comes from unmodified `pipeline.perimeter_samples(event, perimeters,
   env, crop=False)`. It is then cropped by unmodified `pipeline.cropped` (`crop_box(initial, 10)`), the A1 §3.1 crop,
   for training and scoring alike. New-burn cells outside the crop are counted and reported.
2. **Base features.** `pipeline.logistic_features` (21 columns), unchanged. Rows are `score_mask & all-finite
   environment & all-finite features`, as in `pipeline.command_baselines`.
3. **Forbidden features.**
   - F1 = log1p(max(0, last_utc − cutoff) / 24 h), with cutoff = the interval's start survey time, exact to the second.
   - F2 = log1p(surveys / max(1, (last_utc − first_utc) / 24 h)).
   - Source: PARTA_TIMES.csv (metadata via nirops_access ab065e85; check file at 378d4c95, 0 differences against
     states.npz).
   - Appended as extra columns: L adds F1; L2 adds F1 and F2.
4. **Training subsample: STATED DEVIATION.**
   - One uniform per training entry: `keep = (y == 1) | (rng.random(N) < 0.05)`, `rng = np.random.default_rng(0)`.
   - It is drawn ONCE over all part-a entries, concatenated by fire id (string sort), then interval order, then
     row-major cell order. The same keep-vector is reused for every fold and every arm, so base and augmented are
     exactly paired, which rev 1 item 3 requires.
   - Its sha256 is written to the output.
   - `command_baselines` instead draws sequentially over its own training list. This is a deviation, accepted by the
     plan author.
   - Weights are 1 for positives and 20 for kept negatives.
5. **Fit, per fold k (train = the 4 other folds).**
   - `StandardScaler().fit(x, sample_weight=w)`, then `LogisticRegression(max_iter=3000, random_state=0)` (default
     C = 1), with the same weights.
   - `random_state=0` equals `command_baselines`' `--seed` default (0); it is not a new choice.
   - Base, L and L2 differ only in their columns.
   - Every output row is labelled "base = logistic_rebuilt recipe refit on the other 4 part-a folds; NOT the A1
     logistic_rebuilt object" (revision 2 item 2).
6. **Scoring, per held-out fold.**
   - Every masked cell of the held-out fires' cropped intervals is scored, unsubsampled.
   - **4 km band** = Euclidean distance between 375 m cell centres to the nearest initial cell ≤ 4000 m, computed on
     the cropped grid. The full cropped domain is secondary.
   - **STATED DEVIATION: the crop truncates the band.** The crop margin is 10 cells = 3.75 km beyond the initial
     bounding box, so wherever the crop binds, the 3.75–4 km shell is not scored.
   - Reported beside the "material" result, overall and per fire: the share of the UNCROPPED band cells (score_mask,
     distance computed on the uncropped grid ≤ 4000 m) that fall outside the crop.
7. **Statistics.**
   - Pooled out-of-fold Brier, base vs augmented, per arm, in the band (primary) and the full domain.
   - ΔBrier = augmented − base.
   - 95% interval = the 2.5–97.5 percentile of a whole-fire bootstrap. It resamples, with replacement, from the union
     of held-out fires (all 490), with base and augmented paired per fire: B = 2,000, `np.random.default_rng(20261030)`.
     Each resample gives ΔBrier = Σ SSE_aug − Σ SSE_base over Σ n.
   - **Material:** rev 1, unchanged; arm L in the band. L2 is secondary.
   - Also reported, with no bearing on the label:
     - the relative change;
     - per-fire ΔBrier quantiles;
     - the [0, 0.1) calibration gap (mean p − mean y), base vs augmented;
     - the F1 coefficient per fold (standardised and raw).
8. **Smoke test: STATED DEVIATION from revision 2 item 3.**
   - The committed fixture has no perimeters and no baseline terrain, so the extract stage cannot run on it.
   - Before any fit, the following are committed and run:
     (a) synthetic unit tests and a synthetic end-to-end test (fake per-fire caches) of the fit, score, report, resume
         and stop paths;
     (b) an extract-only smoke on 2 real part-a fires (`--limit 2`, no fit) in the executor's container. It reports
         intervals, cells, seconds, cache size and peak RSS. No values from inside the cache are read.
9. **Execution.**
   - The run takes place in the executor's container, from the refit author's pinned commit. The executor runs the
     exact command verbatim and changes no code.
   - Inputs:
     - the pinned refit venv, with `check_refit_env.py` ok;
     - part-a pins f70e52b0, after the checked_utc rule;
     - pool perimeters 982eb71c.
   - **Checkpointed.** Per-fire extraction caches and per-fold models and aggregates are written as they finish. The
     identical command resumes and skips completed work.
   - `--stop-at 2026-11-13T23:30:00Z`: if the run is not finished by then, it stops cleanly (exit 3, STOPPED.json),
     and the partial state is reported as NOT COMPLETE (no result). This keeps the 00:12Z day-2 weather launch clear.
   - Outputs: `derive/LEAK_BOUND.json` and `.md`, with per-fire aggregates only; no cell-level data is committed.

**Records (added 2026-11-13, before any fit).**
- **Plan author:** the item 8 smoke deviation is ACCEPTED (2026-11-13). The plan author spot-checked the runner at
  34a428c0 against items 1–7.
- **Cutoff mapping (item 3):** the runner's cutoff is `sample.t1`. In `pipeline.perimeter_samples`, `t1` is
  `times[i].isoformat()`, the interval's START survey time, i.e. A1's t0. Despite its name, it is not the interval's
  end (the end is `meta["t2"]`).
- **Band truncation (item 6):** the denominator is the uncropped band cells with `score_mask` only. The scored band
  additionally requires finite environment and features, so the reported share outside the crop is slightly
  conservative (it overstates the loss).
- **Independent verifier:** READ rev 3, 2026-11-13. One objection, the interval cap, pending a ruling. Revision 4
  states the cap (0, all intervals) with the evidence from the archived run.

## Revision 4 (2026-11-13, clarification before any fit): interval cap
The independent verifier asked which per-fire interval cap the `logistic_rebuilt` recipe uses: `pipeline.py`'s
`--max-fit-intervals-per-fire` defaults to 3 ("first three eligible consecutive intervals").
- **Evidence.** The archived logistic baseline (`research/forecast-v2/executions/a03_baselines.json`, job
  a03_baselines) ran `pipeline.py baselines` with `--max-fit-intervals-per-fire 3` and then, later in the same argv,
  `--max-fit-intervals-per-fire 0`. argparse keeps the last value, so the frozen logistic trained on **all** eligible
  intervals per fire (cap 0).
- **Fixed now.** Arms L and L2 use every eligible interval ≤ 48 h per fire (cap 0). This equals the archived logistic
  invocation and the A1 §3.1 `final` commands (`--max-fit-intervals-per-fire 0`).
- The refit runbook's `logistic_rebuilt` command is amended to pass `--max-fit-intervals-per-fire 0` explicitly, so
  the A1 object and this fold base use the same cap.
- Not a change to revisions 1–3. It states the cap they left implicit.

**Orchestrator ruling on the cap (2026-11-13 11:48Z): option (a), every eligible interval per fire
(`--max-fit-intervals-per-fire 0`).** This is what the archived logistic run actually used (the last flag wins) and
what the A1 §3.1 refit commands pass. The leak bound's fold base must match the object it bounds.
- *Condition:* before the fit, the independent verifier confirms both facts himself and records them in his row:
  (i) the a03_baselines.json invocation, with argparse's last-value behaviour for that flag; and (ii) the A1 §3.1
  command text.

**Records on revisions 3–4 (2026-11-13, before any fit).**
- **Plan author:** revision 4 APPROVED (cap 0). The revision 3 item 8 smoke deviation was accepted by the plan author
  (recorded under revision 3).
- **Independent verifier:** READ rev 3–4, 2026-11-13; no objection. Implementation b25d963d verified pre-fit (ledger
  row 60). The interval-cap objection is resolved by the archived argv. The run head a55e2366 differs from b25d963d
  only by a code comment (t1 = A1 t0) and the band-truncation note string; the verifier is asked to confirm.
- **HOLD on the fit** (plan author, 11:48Z). A1 §3.1 names `baselines.fit_logistic`, which cannot do the inverse
  weighting A1 also requires; the runbook and this bound use `pipeline.command_baselines`' inline weighted fit. The
  leak-bound fit and the `logistic_rebuilt` refit wait for the orchestrator's ruling on which recipe A1 means. The
  code and the extract-only smoke may proceed.
