# Blind retrospective mapped-extent test on 2026 fires

Status: NOT_READY. Current controlled fitting, exact final checkpoint registry,
source closure and external registration are not complete. This document is a
draft protocol, not a completed pre-registration or evidence of a blind test.
The selection rule below is frozen before inspection of current heldout scores.

## Question, target and primary comparison

Does the development-selected perimeter-trained model reduce endpoint Brier
error relative to the best training-selected dilation baseline on unseen 2026
US fires? The target is cumulative mapped extent at actual published survey
endpoints, within a fixed event rectangle. It is not observed flame contact,
vehicle tenability, evacuation effectiveness or a joint fire probability law.
Korean 2026 reconstruction endpoints are a separate secondary assessment.

The primary statistic is the pooled cell-interval Brier difference, candidate
minus dilation, with a percentile interval from 10,000 whole-fire bootstrap
resamples (seed 20261030). Report every fire separately. A positive headline
requires its interval to lie below zero, the corresponding comparison with
persistence to lie below zero, and the candidate's lowest fixed calibration
bin to have no larger absolute calibration gap than either baseline. Report
all criteria separately. Failure of any criterion forbids a superiority claim.
No calibration or decision threshold is fitted on 2026 outcomes.

## Frozen model identities

Checkpoint identities will be written by the producing run into
`research/forecast-v2/MODEL_SELECTION.json` and an immutable blind registry
before any blind evaluation is permitted. Until those files identify exact
bytes, this draft is not ready for registration.

- The primary candidate is selected by lowest equal-fire development Brier
  across leave-one-year-out folds of 2020, 2021 and 2022 US fit fires. The
  catalog contains no 2023 US fit fire. Fixed tie order is base, D4,
  D4 plus local wind frame, ellipse, burnout, burnout plus spotting, mixed.
- All final variants use all eligible 2020 to 2023 fit intervals and the same
  fixed three-epoch policy. The mixed variant additionally uses eligible
  reconstruction windows of fit fires with kriging-SD weights. No 2024 or
  Korean 2025 fire contributes to fitting or model selection.
- c651 remains a frozen comparator, SHA-256
  `c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`.
- Baselines are no-new-burn persistence, dilation at one cell per 1, 2, 4 or
  8 hours, the single best dilation rate selected using fit fires only, and
  training-fitted logistic hand features. The registry pins the chosen rate,
  logistic parameters, normalization and every candidate checkpoint.
- Existing FARSITE deterministic scenario results may be a separate secondary
  comparator when exact 2026 inputs and an authenticated native scenario
  exist. Their absence cannot remove a case from the primary comparison.

Inspecting 2024 results never permits a checkpoint, hyperparameter or primary
candidate change for this protocol. Any such change makes a new prospective
registration necessary and invalidates this version's blind claim.

## Dataset freeze and exclusions

Use every 2026 US fire in the first public NIROPS release containing 2026
acquisitions that is available by 2027-12-31 23:59 UTC. Include only incidents
with at least two distinct published UTC survey times, an aligned metric
375 m event grid and the six source channels in the frozen model contract.
If that release is already accessible or inspected before external registration,
this proposed assessment must be described as retrospective, not blind.

Before running models, freeze a cohort manifest from incident metadata,
timestamps, grids, source hashes and input availability. No model output or
endpoint growth amount can select a fire or interval. Include every consecutive
survey pair with duration in (0,48] hours whose cutoff weather is available.
Use cumulative unions up to each exact endpoint, rasterized at cell centres.
No interpolation of survey polygons or times is permitted. Published normalized
times can include estimated acquisition timestamps; retain that limitation.

Within each full rectangle, score initially unmapped cells on the intersection
of all registered model validity masks. Record excluded cells, intervals and
fires with their reasons. An empty supported population is unavailable, never
a zero Brier score. Absence outside a mapped union is a negative mapped-extent
reference under this policy, not evidence of physically unburned terrain. No
complete survey coverage footprint is available under the present data model.

All qualifying fires are retained until the fixed data deadline. If fewer than
ten US fires qualify, report all results and intervals as exploratory and mark
the primary test INCONCLUSIVE. There is no early stopping on a favourable score.
Korean 2026 arrival reconstructions follow their source mask and SD policies
and are never pooled with NIROPS observations as if they were the same truth.

## Forecast and scoring rules

Use cutoff information only. Repeat the latest available whole-hour cutoff
weather over each interval; no subsequently observed weather enters a forecast.
Use hourly synchronous transitions and one final fractional step. Recursive
Monte Carlo uses 1,024 trajectories, blocks of 32 and the frozen case-seed
function. Record seeds, checkpoint and input hashes, boundary policy, support
masks, finite-window source assumptions and physical scenario parameters.

Report Brier, Brier skill relative to persistence and best dilation, average
precision, ROC AUC, ten equal-width calibration bins, expected calibration error,
clipped NLL with floor 1e-7, exact zero-probability positives, per-fire values,
whole-fire paired intervals, runtime and parameter counts. Single-class AUC or
AP is unavailable as appropriate. Do not treat cells, intervals or repetitions
as independent fires. Do not conceal infinite exact log loss behind clipping.

All seven final variants are secondary comparisons. Report their full table
regardless of sign. The primary decision uses only the previously selected
candidate, with no post-hoc replacement by the best 2026 model. Reliability
figures show all bins and the low-probability region with the same bin edges.

## Execution and custody

The pinned registry and cohort are mandatory inputs. The blind execution tool
must verify model/source/data identities before producing predictions, write one
case receipt and retain every failed or unavailable case. Scoring recomputes
all figures and metrics from stored common-cohort predictions. A clean relocated
replay must reproduce those scores before the assessment is called complete.

The producing commands and registry schema will be frozen with exact source
hashes when the current controlled fit finishes. Until that executable closure
exists, this document retains NOT_READY. The owner registers the final frozen
protocol on OSF; this task sends nothing to OSF and claims no registration.

## Scope and limits

This is a blind retrospective test of mapped-extent forecasts within predefined
archive rectangles. Those rectangles can use hindsight and do not establish
prospective landscape detection. A positive result would remain conditional on
one archive, repeated cutoff weather, masks, lattice, fuel scenarios and the
fixed model family. It would not establish physical flame accuracy, calibrated
joint trajectories, continuous thermal truth or operational evacuation safety.
