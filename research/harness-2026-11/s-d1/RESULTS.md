# S-D1: continuous-time first-passage formulation of the SMOKE forecast

Owner: Marcus. Status: **checkpoint 1**, covering steps 1 and 2: the mapping, an independent toy check, and convergence tests. Step 3, the real Wapiti comparison, is blocked on input data (see Blockers). Nothing here changes `forecast/` or any frozen artifact.

## 1. Mapping from the hourly recursion to continuous-time rates

**What the fitted model is.** This is read from the code, not taken from the direction document.

- c651 is `MixedNonnegativeKernel`: 19 channels, branches of size 3, 5, 7 and 9 (`forecast/wildfire/models.py:559-720`).
- At each target `i` it generates nonnegative offset coefficients `K[i, δ]` from the environment only. They are a softplus of each branch, mixed with nonnegative global weights. Units are 1/h; the centre coefficient is 0.
- The hazard is linear in the sources: `λ_i = Σ_δ K[i,δ] · B[i+δ]`.
- The link is `P(new burn in dt) = 1 − exp(−dt · λ_i)` (`new_burn_probability`, `models.py:104-190`).
- Offsets follow the PyTorch cross-correlation convention: coefficient (dy, dx) at target (y, x) multiplies the source at (y+dy, x+dx).
- The recursion (`wildfire/rollout.py`) is synchronous with dt = 1 h. Burning is absorbing, and every cumulatively burned cell keeps emitting: there is no burnout in this model.

**Mapping.** The pair rate for source `s = i+δ` → target `i` is **`K[i,δ]` itself**, with no transformation.

- The hourly link already factorises over sources: `1 − exp(−Σ_δ K_δ) = 1 − Π_δ (1 − p_δ)`, where `p_δ = 1 − exp(−K_δ)`. So the "per-step probability p vs rate −log(1−p)" question resolves to `−log(1−p_δ) = K_δ` exactly. Using the coefficient as the rate *is* the −log(1−p) choice.
- The only incorrect option is to treat `p_δ` itself as a rate. That would bias every pair rate down by the factor `p/K` (0.63 at K = 1/h; about 1 − K/2 for small K).
- The hourly CA is exactly the continuous-time Markov jump process with the burned set **frozen for each hour**. Its dt → 0 limit is that process. Because sources never stop emitting and hazards are additive, the process equals first-passage percolation with independent `Exp(rate)` clocks per (source, target) pair. Time-dependent Dijkstra is exact for hourly-varying weather, since edge delays are FIFO.

**The decision that actually matters (labelled; needs Iris).** c651 was fitted **one step ahead with teacher forcing**:

- target = "currently unburned cell is burned at the exact next-hour snapshot";
- loss = weighted Brier;
- `dt_hours = 1.0` is enforced (`wildfire/train.py:323-367`).

Any multi-hop spread inside one hour in the training labels was therefore explained by the fitted kernels, mostly the long-range 7×7 and 9×9 branches. Plugging the same `K` into the continuous-time sampler adds within-hour multi-hop spread *on top*. My hypothesis is that it double-counts and over-spreads in fast regimes. So the "plug-in" continuous-time forecast is a **different model** from c651, not a better solver for the same model. The clean comparison needs coefficients refitted under a continuous-time likelihood (Elena, S-D2).

The plug-in result is still informative. It bounds how much of the hourly scheme's speed deficit is discretisation rather than fit.

## 2. Independent toy check

Code: `fpp.py` contains:

- `first_passage`: numba time-dependent Dijkstra, one pass per trajectory, with no step and no reach cap;
- `cellular_automaton`: an independent re-implementation of the hourly recursion with any dt.

### Tests

`python -m pytest research/harness-2026-11/s-d1/tests -q` → **9 passed** (8.5 s). The tests cover:

- single edge, constant and piecewise-constant rate vs `1 − exp(−∫k)` (exact for both samplers);
- competing sources superposing;
- a two-hop chain vs the analytic hypoexponential CDF: the sampler is exact; the hourly CA equals its own analytic value `(1−e^{−a})(1−e^{−b})` and is biased low; the dt-CA converges;
- the sampler vs CA at dt = 1/32 with **hourly-varying** random 3×3 kernels, per cell;
- arrival-field consistency: every burned cell has an earlier-burned in-neighbour;
- seed reproducibility;
- **offset convention and rate equal to `wildfire.models.new_burn_probability`** for K = 3, 5, 9 (rtol 1e-12);
- source → target direction checked against the forecast code.

### Toy, my own specification

The direction document's exact toy specification was not in the repository, so I chose one:

- 40×40 grid;
- 5×5 uniform off-centre kernel, with the stated coefficient sums;
- 3×3 centre ignition;
- zero boundary;
- 12 h;
- 2,000 trajectories.

Expected number of new cells (± MC SE) and wall time. Command: `python research/harness-2026-11/s-d1/toy_check.py --out …/RESULTS_toy.json`; the output is in `RESULTS_toy.json`.

| method | slow (Σ = 0.043/h) | fast (Σ = 1.0/h) | wall time, fast |
|---|---:|---:|---:|
| hourly CA (dt = 1) | 3.48 ± 0.05 | **349.8 ± 1.0** | 2.4 s |
| CA dt = 1/4 | 3.59 ± 0.05 | 610.2 ± 1.9 | 10.0 s |
| CA dt = 1/16 | 3.60 ± 0.05 | 728.0 ± 2.3 | 39.0 s |
| CA dt = 1/32 | 3.69 ± 0.05 | 743.9 ± 2.4 | 78.6 s |
| Richardson extrapolation (1/16, 1/32) | 3.79 | 759.8 | — |
| **first-passage** | 3.63 ± 0.05 | **771.0 ± 2.4** | **1.2 s** |

- **Slow regime:** all methods agree within about 4%. The hourly CA is 0.15 lower, about 2 combined SE.
- **Fast regime:** the hourly CA gives **55% fewer** expected new cells than the first-passage sampler. The direction document reported 38% on its own, unknown specification; the qualitative claim reproduces but the size depends on the specification.
- **Wall time:** the first-passage sampler is about 2× faster than the *hourly* CA here and 60× faster than CA at dt = 1/32. In the slow regime it takes 0.04 s against 2.6 s, because its cost scales with the burned cells, not with grid × steps.

### Convergence order

`convergence_check.py` → `RESULTS_convergence.json`. Setup: 20×20 grid, Σ = 1/h, single ignition, 4 h, n = 8,000.

- First-passage: 25.49 ± 0.20.
- The CA gap shrinks with dt: 14.13, 9.45, 5.79, 3.13, 2.06, 0.82, 0.34 for dt = 1 down to 1/64.
- The gap × m stays in 14–33, i.e. **first-order convergence**.
- At dt = 1/64 the gap is 0.34, about 1.2 combined SE.

## Blockers

- **Step 3 needs data.** Re-running c651 on the 52 Wapiti held-out cases needs each case's initial burned raster, its 19-channel environmental snapshot and its reference mask. The receipts in `forecast/runs/20261030_perimeter_trained/execution_v3/heldout/cases/` give only SHA-256 hashes. The inputs came from the owner's local archive (`research/forecast-v2/DATA_PROVENANCE.md`). I have asked Daniel whether any of it can be fetched.
- The saved hourly-recursion predictions (`p_c651_mc`) and labels are in the repository, so the baseline side of the comparison is available.

## Ideas and gaps

1. **Teacher-forced one-step fit + plug-in continuous-time = double counting.** See section 1. Flagged to Iris. Elena's continuous-time likelihood is the remedy. Under teacher forcing, the CT one-step likelihood for a target is not `1 − exp(−λ)` with the hour-start sources: it must integrate over within-hour ignitions of neighbours, so it is no longer a closed form per cell. One option is a survival likelihood on reconstructed arrival times, which the Choi kriging reconstructions provide (`forecast/wildfire/survival.py` exists; to check).
2. **Zero-probability positives are structural in the hourly CA.** A cell more than 4 × h cells from every burned source has P = 0 at horizon h. The first-passage sampler gives positive probability wherever a path exists. To be measured on Wapiti.
3. **Tail probabilities from arrival times (hypothesis).** A conditional Monte Carlo estimator, `P(T_i ≤ t | T^{−i}) = 1 − exp(−Σ_s Λ_si(T_s^{−i}, t))`, is exact if `T^{−i}` is computed with `i` removed. With the full-graph `T_s` it is biased for sources reached through `i`. A cheap correction, or a proof that the bias vanishes for the min, is open. It would give nonzero, low-variance tail estimates where trajectory counts give 0.
4. **The coverage/unknown-cell envelope is not ported.** The sampler implements only the zero boundary. The forecast's conservative coverage, where unknown sources invalidate dependants, must be reproduced before any scored comparison.
5. **Burnout.** The present c651 has no burnout, so the Kenah–Robins finite emitting window is not needed to match it. It is needed for the burnout variants (`burnout_seed0`, etc.).
