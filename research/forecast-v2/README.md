# Forecast v2, current execution

Eighteen intended development fits and six intended full final fits are
complete. The three corrected spotting folds and corrected full spotting fit
remain pending. Three earlier spotting folds and one full fit remain historical
smouldering-inclusive variants; they do not satisfy intended completeness or
selection. No heldout forecast-quality result or superiority claim is available.
The mixed final fit attempted all 4,391 inputs in each of three epochs, with
4,376 optimizer updates and 15 logged source-unsupported windows per epoch.
Complete attempted input coverage is distinct from optimizer coverage.

The selected integration checkpoint c651 remains unchanged. This branch adds
opt-in mean-field propagation, interval-endpoint losses, structural kernels,
baselines and a draft blind protocol. It reuses prior implementation source
with independent repairs and tests; `REUSE_MANIFEST.json` identifies those bytes.

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
python research/forecast-v2/scripts/run_campaign.py baselines --attempt 3
python research/forecast-v2/scripts/run_campaign.py compare --attempt 4
# After all fits, run audit_caches.py to CACHE_AUDIT_FINAL.json, then
# audit_fit_coverage.py to FIT_COVERAGE.json, preserving the original audit.
python research/forecast-v2/scripts/run_campaign.py freeze --attempt 3
# Only after MODEL_SELECTION.json freezes exact checkpoint identities:
python research/forecast-v2/scripts/run_campaign.py heldout --attempt 3
python research/forecast-v2/scripts/status.py
```

The commands use the fresh pinned forecasting environment, task-local verified
inputs and per-job `/tmp/wfg/HEAVY.lock` leases. `executions/` records commands,
exit codes, source/input/output hashes, seeds, host and elapsed time. Earlier
failed commands remain separate. Data are real aligned covariates and NIROPS
survey perimeters recovered from the source-supplied archive, with fresh
archive/member verification documented in `DATA_PROVENANCE.md`.

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
fallbacks are coarse model choices. No field validation, physical flame accuracy,
calibrated joint forecast, evacuation-safety or universal speed claim is made.
Current 2024 testing will remain retrospective; it is not the blind 2026 test.
The proposed blind protocol retains NOT_READY until exact registry and execution
closure are complete and the owner performs external registration.

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
