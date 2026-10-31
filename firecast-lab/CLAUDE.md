# firecast-lab/ — Track A: calibrated probabilistic fire-hazard generator (side project, at most ~20% of effort)

Goal (not "beat FARSITE"): *"Produce scenario members whose spread of outcomes is honest, so
that evacuation decisions made on them are rarely falsely safe."* Output: K scenario members
in `hazard_contract` v1 format for Track C.

Host, data availability, worktree paths and blockers: see `program/STATUS.md`. Never proceed
on synthetic data as if it were real; synthetic test fixtures are fine when labeled SYNTHETIC.

## Ground rules (identical in every program folder; they override this repo's older audit conventions)

1. **Allowed folders.** Create and edit files only in `evacplan/`, `firecast-lab/`,
   `hazard_contract/` and `program/`. Never edit, move or delete anything else: the rest of
   the repo is the frozen research release. Import from `integration/` (`wfg_latest`) and
   `forecast/` (`wildfire`) instead of copying them. Adding these tracks to CI needs
   Siyeong's approval.
2. **Light rigor, no bureaucracy.** Every result row records the git commit, seed, config and
   host. That's all. No SHA ledgers, custody receipts, gate JSON files, "HOLD" taxonomies or
   reviews of reviews. If you want a verification document, write a test instead.
3. **One feasibility oracle**, `evacplan.oracle`. It is the only code that may declare a
   vehicle itinerary `checked`, `model_no_route` (model-infeasible, scoped to model and
   horizon) or `unresolved`. Fast relaxed checks are allowed inside search loops, but final
   answers and Track A's decision metric go through the oracle.
4. **Unknown is not unburned.** Missing hazard data flows through as `unsupported`, which
   leads to `unresolved`. It never defaults to safe. `unresolved` never counts as safe or
   delivered.
5. **Splits before methods.** Track C: frozen `dev` and `test` instance sets. Track A:
   `firecast-lab/SPLITS.json`, split by whole fire, never by cell or window. Touch `test`
   sets or held-out fires only at milestones, after Siyeong approves. Track A reports
   uncertainty with whole-fire bootstrap intervals; repeated windows are not independent fires.
6. **Fair timing.** Agents may write code in parallel. Timed benchmark runs must not overlap
   other heavy computation: run them through the shared lock,
   `python program/benchlock.py -- <command>` (lock file `program/.bench.lock` in the main
   checkout, shared by all worktrees). Always compare methods at equal wall-clock budgets.
7. **Data and licenses.** Keep OSM attribution (ODbL). Choi et al. 2026 reconstructions and
   NIROPS perimeters are CC BY 4.0; CMS provider data is public. Label synthetic data as
   SYNTHETIC everywhere, including figures. Ask before any download over 1 GB, any scraping,
   or committing anything over 20 MB. Never commit raw rasters, weights or personal data
   (use the folder's `.gitignore`).
8. **Stack.** Python 3.12. Track C: numpy, networkx, osmnx, OR-Tools, HiGHS (`highspy`),
   pydantic, pytest, matplotlib. Track A: also PyTorch (CPU or Apple MPS), scipy,
   scikit-image, rasterio or xarray. CPU or MPS only. Ask before adding other major
   dependencies.
9. **Time-box.** Each experiment states its budget and ends with one decision: KEEP, KILL or
   ITERATE. Negative results are reported in the same format as positive ones.
10. **Git.** Never commit to or push `Main`. Never force-push. Never create GitHub repos. Push
    only `next/integration`, the track branches `evacplan/phase0` and `firecast-lab/phase0`,
    and short-lived experiment branches (`evacplan/exp-<ID>-<slug>`,
    `firecast-lab/exp-<ID>-<slug>`) to `origin`. Experiments merge into their track branch,
    track branches into `next/integration`; Siyeong merges `next/integration` into `Main`
    through pull requests. Commit small and often, with clear messages.

**Always ask Siyeong before:** changing either problem definition or the `hazard_contract`
interface; touching test sets or held-out fires; downloads over 1 GB; adding a major
dependency; any single run longer than 2 hours; editing anything outside the four folders;
opening a pull request to `Main`.

## SMOKE facts (forecast/, checkpoint c651) — treat these as facts

- Environment-conditioned CNNs generate nonnegative kernels at sizes 3, 5, 7, 9; rates are
  combined and converted to a probability with `q = (1-B)(1-exp(-λΔt))`; recursive Monte
  Carlo simulation gives multi-hour forecasts. Training used the kriged satellite
  time-of-arrival reconstructions of Choi et al. 2026; evaluation uses NIROPS aerial-infrared
  perimeters.
- Known failures: (1) Wapiti alone (25 intervals, model chosen after looking at held-out
  diagnostics) showed +8.2% Brier skill vs persistence; the frozen 6-fire study (273 windows)
  failed its primary criterion — Brier-skill interval vs persistence ≈ [−0.7%, +2.5%] — and
  morphological dilation was better calibrated in the lowest-probability bin. (2) Low
  probabilities are underpredicted: 37% of new burns fall in the <1% bin and 617 positives
  got exactly 0 probability. (3) The binary absorbing state has no burnout, and cutoff weather
  is repeated through the horizon. (4) The FARSITE comparison was one uncalibrated
  deterministic scenario; don't rely on it.

## Phase 0: evaluation harness first

1. **Loader and splits.** Write `SPLITS.json` before any modeling. Default test = this repo's
   held-out seasons (US-2024 and KR-2025), because c651 trained on the other seasons; these
   held-out fires were already looked at by earlier studies, so they are not fresh. Also a
   locked `fresh_holdout`: 2025 US fires with NIROPS coverage, and 2026 Korean fires when
   available. Nothing touches `fresh_holdout` until a final claim.
2. **Data checks** → `firecast-lab/docs/DATA_NOTES.md`: the real timing uncertainty of the
   reconstructed labels, especially Korean (if hours, choose a headline lead time the labels
   can support — likely 24 h — justify it, keep shorter leads secondary); fires too short to
   produce headline-lead windows; whether Choi et al. used NIROPS to build the US
   reconstructions or only to evaluate them (decides whether NIROPS is independent truth);
   whether the weather inputs are analyses or forecasts.
3. **Baselines**, all scored on identical cells, dev scores cross-fitted by leaving out groups
   of whole fires: persistence; morphological dilation tuned on dev fires; calibrated best
   dilation (the bar to beat); logistic regression on distance-to-front, wind alignment and
   slope; c651 SMOKE, labeled in-sample on dev rows (time one fire at 256 trajectories before
   any full run). Every baseline must output spatially coherent members (e.g. threshold one
   shared uniform field per member, or a Gaussian copula) so "every member clear"
   comparisons are fair at matched K.
4. **Metrics** (definitions in `firecast-lab/METRICS.md`): Brier, with Brier skill vs both
   persistence and calibrated best dilation; reliability diagrams and ECE; average precision;
   Fractions Skill Score at several neighborhood sizes (Roberts & Lean 2008); CRPS on arrival
   time; rank histograms and spread-skill. Scoring domain: the headline uses the final
   perimeter plus a buffer fixed before seeing results (~3 km, with a reason); the full
   rectangle is secondary. Never-mapped cells are not certified unburned.
5. **Decision metric (the most important one).** Feed members through `hazard_contract` and
   Track C's oracle on fixed routing requests built only from information available at the
   cutoff; score against truth built from the observed perimeters. Report together: the
   headline false-safe rate P(hit | cleared); the miss rate (cleared-but-hit ÷ routes the fire
   reached); the clearance rate; the false-unsafe rate. Plot false-safe vs clearance rate as K
   varies — a model that never clears anything has 0 false-safe, so always show clearance.
6. **Producer:** write scenario sets in `hazard_contract` v1 format.

## Phase 1 backlog (start with L1 and L8 on real data)

- **L1** Post-hoc calibration per lead time: isotonic, beta calibration, conformal risk
  control (Angelopoulos et al. 2022) targeting a guaranteed bound on false-safe rate.
- **L2** Fat-tailed long-range term + background rate: heavy-tailed dispersal kernel (Clark et
  al. 1999 2Dt, or power law) plus a small background ignition rate. Goal: no exact-zero
  positives; spotting represented beyond 9×9.
- **L3** S-I-R states (SMOKE is a spatial-kernel epidemic model, same form as Keeling et al.
  2001): susceptible → burning → burned-out with a burning-duration distribution;
  likelihood-based fitting on arrival times.
- **L4** Continuous-time survival / point-process likelihood on arrival times with censoring.
- **L5** Learned rate-of-spread field + eikonal (fast-marching) solver; ensemble by perturbing
  rate-of-spread.
- **L6** Data assimilation: particle filter or EnKF reweighting/resampling trajectories as
  detections arrive (VIIRS FIRMS ~12 h; FireSat-like 20 min simulated by subsampling); skill
  and false-safe rate vs cadence.
- **L7** Archived weather forecasts instead of repeated cutoff weather.
- **L8** Ensemble honesty: spread-skill, rank histograms, inflation methods from weather
  ensembles.
- **Free slot:** up to 3 unconventional ideas with mathematical justification. Ask first.

## Claim rule

A new model counts as an improvement only if, on held-out fires, it beats calibrated best
dilation with a whole-fire bootstrap interval that excludes zero, on Brier skill or on the
decision metric. If nothing clears that bar, say so plainly. A model can still be useful as a
scenario generator if its false-safe rate at a useful clearance rate is good.

## Done (this stage)

Harness, baselines and decision metric work on real data; at least 3 experiments concluded;
an honest leaderboard exists; the best-calibrated generator runs inside Track C's Caldor demo
through `hazard_contract`.
