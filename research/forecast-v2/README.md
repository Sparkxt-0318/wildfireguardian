# Forecast v2, current execution

Twenty-one intended development fits and all seven intended full final fits are
complete. The corrected full spotting fit used all 1,303 inputs in every epoch,
with 1,303 optimizer updates and no unsupported skips in each of three epochs.
Three earlier spotting
folds and one full fit remain historical
smouldering-inclusive variants; they do not satisfy intended completeness or
selection. No heldout forecast-quality result or superiority claim is available.
The complete source-derived membership audit is on HOLD: its exact recipe
guard refused historical producer functions that predate added input-custody
checks. The failed receipt/log are preserved; compatibility is being checked
against each consumed immutable path. This does not yet establish complete
fit admission, even though all seven fitting commands completed.
The mixed final fit attempted all 4,391 inputs in each of three epochs, with
4,376 optimizer updates and 15 logged source-unsupported windows per epoch.
Complete attempted input coverage is distinct from optimizer coverage.

The selected integration checkpoint c651 remains unchanged. This branch adds
opt-in mean-field propagation, interval-endpoint losses, structural kernels,
baselines and a draft blind protocol. It reuses prior implementation source
with independent repairs and tests; `REUSE_MANIFEST.json` identifies those bytes.

The frozen equal-fire development rule selects D4 with local wind
canonicalization. These are absolute scores on each variant's own support,
from 23 validation fires across three year folds and seed 0. Aggregate receipts
do not retain exact scored coordinates, so paired common-cell development
effects and confidence intervals are unavailable, even when weights match.
`DEVELOPMENT_SCORES.json` retains all per-fire values and producer identities.

| Variant | Mean fire Brier, selection criterion | Pooled Brier | Parameters |
| --- | ---: | ---: | ---: |
| Base | 0.040321559 | 0.043309534 | 26,018 |
| D4 | 0.038817948 | 0.046971023 | 26,018 |
| D4 with local wind | 0.037495116 | 0.040814821 | 26,018 |
| Ellipse prior | 0.041327574 | 0.045037051 | 26,018 |
| Burnout | 0.038401654 | 0.042176448 | 26,019 |
| Burnout with flaming-only spotting | 0.038446229 | 0.042240116 | 26,023 |
| Mixed training | 0.046886875 | 0.046095678 | 26,018 |

Each pooled development score uses total validation weight 198,193. Equal-fire
and pooled statistics use different weighting; their differences are distinct
estimands. These development values establish neither heldout superiority nor
a physical improvement. All seven final identities and the exact fit-coverage
audit must be frozen before current heldout assessment.

## Frozen design and commands

`RUN_PROTOCOL.json` fixes the split, model variants, fitting policy, primary
selection rule and the exact twelve comparison cutoffs before any fit or
heldout score. `RUN_PROTOCOL_EXTENSION_1.json` requires final variants to use
all eligible fit intervals at a fixed three-epoch budget. The first three
eligible intervals per fire are only the bounded development comparison.
`RUN_PROTOCOL_EXTENSION_2.json` retains earlier failures and defines the clean
controlled rerun after repairing missing-support batches. No future endpoint
chooses the training crop. No heldout outcome chooses a model or checkpoint.

```sh
python research/forecast-v2/scripts/run_campaign.py fits --attempt 3
python research/forecast-v2/scripts/run_campaign.py spotting-repair --attempt 5
python research/forecast-v2/scripts/run_campaign.py baselines --attempt 3
python research/forecast-v2/scripts/run_campaign.py compare --attempt 6
# After all fits, run audit_caches.py to CACHE_AUDIT_FINAL.json, then
# audit_fit_coverage.py to FIT_COVERAGE.json, preserving the original audit.
python research/forecast-v2/scripts/run_campaign.py freeze --attempt 3
# Only after MODEL_SELECTION.json freezes exact checkpoint identities:
# freeze_registry.py then binds the final protocol and exact executable closure.
# Run both guarded cohort commands, retaining each exit independently:
python research/forecast-v2/scripts/score_cohorts.py --cohort us2024 --data "$DATA" --work "$DATA/campaign-work" --run "$RUN" --registry research/forecast-v2/BLIND_REGISTRY.json
python research/forecast-v2/scripts/score_cohorts.py --cohort korea2025 --data "$DATA" --work "$DATA/campaign-work" --run "$RUN" --registry research/forecast-v2/BLIND_REGISTRY.json
python research/forecast-v2/scripts/status.py
```

The commands use the fresh pinned forecasting environment, task-local verified
inputs and per-job `/tmp/wfg/HEAVY.lock` leases. `executions/` records commands,
exit codes, source/input/output hashes, seeds, host and elapsed time. Earlier
failed commands remain separate. Data are real aligned covariates and NIROPS
survey perimeters recovered from the source-supplied archive, with fresh
archive/member verification documented in `DATA_PROVENANCE.md`.
`DATA` denotes the task-local verified `work/data/forecast-v2` root and `RUN`
denotes `forecast/runs/20261030_perimeter_trained/execution_v3`; `python` is the
fresh pinned interpreter. A cohort scorer's HOLD exit is preserved and does not
cancel the other mandatory cohort. The original a04 comparison case and source
remain historical; all twelve a06 cutoffs form one current source phase.

The latest integrated forecast regression passed 3,373 tests, and the release
verifier passed all 367 frozen file identities. Its source capture remained
unchanged throughout the gate. Earlier 3,259-test and targeted reviews retain
separate receipts; their counts are not pooled. These software checks are
distinct from scientific and external-release gates.

A separately reviewed source-recipe compatibility candidate passed a
provisional audit of the actual artifacts: all 21 intended development phases,
six pure final sets of 1,303 samples, and the mixed final set of 4,391 samples.
The exact candidate and all 61 active comparison sources remained unchanged.
The exposed record is `PROVISIONAL_NOT_FOR_REGISTRY`; its compressed raw result
is diagnostic evidence, with the actual executed candidate identity recorded
separately from the checked live auditor. Old-main refusal was tested only on
the exposed wrapper, not the raw diagnostic. The original live audit HOLD
remains authoritative until the twelve-cutoff source phase closes, the reviewed
candidate becomes the live auditor, and a new full software gate and live
coverage audit pass. No model selection, blind registry or heldout inference
has run. `review/provisional_coverage_F65/` preserves the exact receipt and
qualification.

## Mathematical and validation boundaries

Brier is a proper score, not a likelihood. Clipped Bernoulli NLL is a diagnostic
for interval endpoints under the stated hazard approximation. Binary single-step
mean field equals the maintained transition expectation; multi-step mean field
is a closure approximation. Wind canonicalization uses each target's local
frame and bilinear finite-support resampling, which is approximate. The repaired
Anderson coefficients use midflame wind in metres per second. Missing SD does
not become full label confidence. A batch with no supported positive-weight
cells is logged as unsupported, never reported as zero error.

## Scope and limits

Targets are mapped survey extent or arrival reconstruction, not flames. There
is no full survey coverage mask. Weather is repeated from the cutoff unless a
sample explicitly records otherwise. Training crops use a declared zero-exterior
scenario, while heldout scoring uses full fixed rectangles and common support.
Point residence on an hourly lattice, midpoint ignition and unsupported-fuel
fallbacks are coarse model choices. Residence below a half-step can alias the
midpoint source schedule, and initial ages use survey-interval proxies. The
domain-mean spotting wind is a coarse global scenario assumption. No field validation, physical flame accuracy,
calibrated joint forecast, evacuation-safety or universal speed claim is made.
Current 2024 testing will remain retrospective; it is not the blind 2026 test.
The prospective protocol is pending current model/source freeze. Completion
will make it ready for owner registration; future 2026 execution separately
remains NOT_READY until independently reviewed documentary release, chronology
and registration prerequisites are satisfied. No external OSF registration is
claimed by this task.

## Global spotting input custody

`RUN_PROTOCOL_EXTENSION_9.json` records the global-wind availability repair.
The original missing-wind failure and the audit serializer failure remain in
`review/`. Source-authenticated produced tensors contain no missing wind for
any of the four completed spotting phases. `GLOBAL_WIND_PHASE_BINDINGS.json`
distinguishes 1,372 role-specific records (69 development plus 1,303 full fit),
1,303 distinct source cases and tensor contents, and 1,510 phase visits across
23 fires. The 69 development cases recur in the full fit and across folds.
These are not 1,510 independent examples.

Known-wind forward values and every parameter gradient match the prior callback
bit for bit in functional controls. Existing spotting fits are retained with
their original producers. Missing domain wind now makes unobserved spotting
targets unsupported; it cannot silently become known zero. The separate c651
comparison has no spotting callback. Its failed prior report is preserved;
the full twelve-cutoff comparison resumes with explicit empty-support states.

The final mixed fit records its actual prefit sample identities and every
epoch attempt and skip. Controls verify that logging consumes no RNG and
leaves fitted parameters unchanged. The six historical pure fits retain
source-derived schedule evidence, not retrospectively claimed runtime IDs.

## Flaming-only emitter correction

`RUN_PROTOCOL_EXTENSION_10.json` preserves the concrete emitter failure and
requires fresh corrected spotting phases. The original branch received local
flaming plus old-cell smouldering occupancy. The corrected extra branch uses
only occupancy still in its residence window; local spread retains learned
smouldering. The historical four spotting phases remain versioned. The earlier
global-wind retention proof addresses only missing-wind availability and does
not waive this independent emitter-law correction. No heldout outcome selected
the repair.

`scripts/check_nonspotting_compatibility.py` reproduces the bounded source and
fixture comparison with the exact pre-repair mean field. Its six controls retain
outputs, masks and every parameter gradient bit for bit without spotting. The
local burnout source method is unchanged. This supports retaining the other
six variants and the unchanged c651 comparison, without asserting equivalence
of the old spotting model.
