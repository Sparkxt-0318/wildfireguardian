# Forecast v2 execution plan

## Source reading and authority

The maintained transition in `forecast/wildfire/models.py::new_burn_probability`
uses a position-dependent nonnegative offset kernel, the exponential link, a
zero centre contribution, and explicit source/environment validity. Interior
unknown cells are not observed zeros. `EnvironmentConditionedConvolution`
provides `kernel_rates`; the selected mixed model uses that same path.
`TrainedBurnModel` additionally applies saved normalization and categorical
contracts. `BayesianBurnModel` mixes probabilities after component evaluation,
not rates before the exponential. Mean-field propagation must preserve these
facts and reject model families without a burned-independent offset kernel.

`rollout.py::simulate` synchronously updates binary trajectories, supports an
hourly weather sequence, fractional final steps for survey evaluation, repeated
cutoff weather, conservative availability, and prefix-stable trajectory blocks.
This file remains read-only. Multi-step mean field is a closure approximation,
not the expectation of that stochastic recurrence.

`train.py` fits normalization and category emphasis using training rows only.
`data.py` loads explicit masked event sequences; `cohort.py` retains inverse
inclusion weights and chooses contact populations from current inputs, not
future labels. `observed_data.py` records NIROPS archive identity and timestamp
limits. `observed_evaluation.py` rasterizes unions of actual survey polygons at
exact endpoints. `observed_combined.py` authenticates frozen splits and reused
cases. `heat.py::FlameResidenceTime.from_fbfm40` provides point residence, which
must not be confused with whole-cell front-crossing duration.

The maintained evidence handoff reports no established general superiority of
the four-branch model. Its historical held-out partition is not a blind 2026
test. None of its fitted ablation checkpoints will replace c651.

## Mathematical corrections to the supplied prompt

- Endpoint Brier is a proper scoring rule, not a likelihood. Bernoulli endpoint
  NLL is the interval-censored likelihood under the stated hazard model.
- Binary single-step mean-field increments equal the existing MC transition's
  conditional expectation. A multi-step closure generally differs from the
  mean of trajectories because random spatial dependencies are discarded.
- Wind canonicalization by bilinear resampling is approximate on a finite
  grid. D4 transforms can be exact if vector channels and offset kernels are
  transformed consistently.
- Anderson/Finney length-to-breadth uses effective midflame wind. Applying it
  directly to 10 m weather wind without a declared conversion is unsupported.

## Work sequence

1. Freeze a year/fire split before any new fitting. Inventory real data and
   hashes; retain missing records rather than evaluating a catalog as data.
2. Implement mean-field, endpoint survival losses, weighted fitting and a
   manifest-based interval dataset. Add independent analytic/MC tests.
3. Add D4/canonical kernels, ellipse prior, finite flaming-window sources and
   sparse long-range spotting, with controls and opt-in interfaces.
4. Add persistence, dilation and logistic baselines; grouped bootstrap and
   calibration. Fit only eligible development fires.
5. Execute available cohort comparisons and the prespecified ablations. If
   inputs are incomplete, record NOT_RUN per planned study, not toy headline
   replacements. Produce reproducible figures for executed numerical checks.
6. Freeze a blind-test protocol with exact checkpoint identities only after
   fitting and selection are complete. If fitting is blocked, explicitly keep
   registration in a not-ready state.
7. Run new and existing forecast tests in a fresh pinned environment, verify
   additive source changes and manifests, and report all acceptance gates.

## Graph verification

Tier 2, parent graph generation 2026-10-30T02:10:29Z, then dedicated project
`wfg-next-1b-20261030`. All eleven task-relevant forecast files had metadata
matching and no recorded parser gap. This is best-effort coverage. A one-hop
trace of `new_burn_probability` exposed false-positive name resolution in an
unrelated plotting file, so source bodies, not graph edges alone, determine
material mathematics. Exact source reads supplement graph snippets.
