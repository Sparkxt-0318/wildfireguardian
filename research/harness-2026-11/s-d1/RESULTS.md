# S-D1: continuous-time first-passage formulation of the SMOKE forecast

Owner: Marcus. Status: **checkpoint 2**.

Plan changes adopted on the orchestrator's decision, following Iris:
- Running the first-passage sampler on c651 kernels without a refit gives a different, faster model. Any result from it is a labelled diagnostic, never an accuracy claim.
- Gate 1 is the convergence of the sub-stepped CA to the sampler.
- The accuracy comparison waits for a refit (with Elena) and for Victor's frozen protocol.

Nothing here changes `forecast/` or any frozen artifact. Every numerical result is synthetic or descriptive unless stated otherwise.

Reproduce: Python ≥ 3.12, `pip install numpy scipy numba pytest torch pandas geopandas pyogrio rasterio pyproj`. Run commands from the repository root.

## 1. Mapping from the hourly recursion to continuous-time rates

**What the fitted model is.** This is read from the code, not taken from the direction document.

- c651 is `MixedNonnegativeKernel`: 19 channels, branches of size 3, 5, 7 and 9 (`forecast/wildfire/models.py:559-720`).
- At each target `i` it generates nonnegative offset coefficients `K[i, δ]` (1/h) from the environment only.
- The hazard is `λ_i = Σ_δ K[i,δ] · B[i+δ]`.
- The link is `P = 1 − exp(−dt · λ_i)` (`models.py:104-190`).
- The rollout (`wildfire/rollout.py`) is synchronous with dt = 1 h, absorbing, with no burnout: burned cells emit forever.

**Mapping: the pair rate is `K[i,δ]` itself.**

- With `p_δ = 1 − exp(−K_δ)`, the hourly link is `1 − Π(1 − p_δ)`, and `−log(1 − p_δ) = K_δ` exactly. So "use the coefficient as the rate" is the −log(1−p) choice. Only "rate = p" would be wrong.
- The hourly CA is the continuous-time jump process with the burned set frozen for each hour.
- Its dt → 0 limit is first-passage percolation with independent `Exp(K)` clocks per (source, target) pair. Additive hazards plus never-ending emission make this exact.
- Time-varying weather is handled exactly by time-dependent Dijkstra on integrated hazard, because edge delays are FIFO.

**Fit caveat (agreed with Iris).** c651 was fitted one hour ahead with teacher forcing:

- target = "burned at the next-hour snapshot";
- Brier loss;
- `dt_hours = 1` enforced (`wildfire/train.py:323-367`).

Within-hour relay is therefore already inside the kernels. Rolling the model out hour by hour is self-consistent with its labels; a continuous-time reading of the same kernels spreads faster. So the plug-in result is a different model.

## 2. Sampler and tests

`fpp.py` contains:

- `first_passage`: numba time-dependent Dijkstra, with no step and no reach cap; records arrival times and the shortest-path tree;
- `cellular_automaton`: an independent re-implementation of the recursion for any dt, with options `half_step` and `return_cmc`;
- `first_passage_cmc`: the conditional estimator (§6).

`python -m pytest research/harness-2026-11/s-d1/tests -q` → **14 passed** in about 5 min, most of it the rollout-parity test. They cover:

- analytic single-edge, competing-source, two-hop hypoexponential and piecewise-constant time-varying cases;
- an arrival-field consistency check;
- per-cell agreement with the dt = 1/32 CA under hourly-varying kernels;
- rate and offset parity with `wildfire.models.new_burn_probability` (K = 3, 5, 9; rtol 1e-12);
- **per-cell marginals of the reference CA equal to the real `wildfire.rollout.simulate`** (stub predictor with fixed kernels, 5σ);
- the conditional estimators: exact on an analytic chain including a ~1e-4 tail cell; equal to plain counting on a random grid; the hourly conditional estimator exact on the hourly chain;
- the half-step arm lying above the hourly CA.

## 3. Gate 1: the sub-stepped CA converges to first-passage

Command: `python research/harness-2026-11/s-d1/gate1.py` (≈25 min) → `RESULTS_gate1.json`. R5 was run separately with `--regimes R5_c651_magnitude_heterogeneous9 --out …/RESULTS_gate1_R5.json`.

Setup: 40×40 grid, 3×3 centre ignition, n = 2,000 per arm. Distances are measured to first-passage at every whole hour:

- L1 = mean |ΔF| over cells and hours, where F = P(burned by t);
- W1rel = Wasserstein-1 distance of burned area at T, divided by first-passage's mean burned area.

The noise floor is the same distance between two independent first-passage runs.

| regime | first-passage area | floor L1 / W1rel | hourly L1 / W1rel | dt = 1/32 L1 / W1rel |
|---|---:|---|---|---|
| R1 slow uniform 5×5, Σ = 0.043/h, 12 h | 3.6 | 0.0002 / 0.031 | 0.0001 / 0.028 | 0.0002 / 0.019 |
| R2 fast uniform 5×5, Σ = 1/h, 8 h | 323.7 | 0.0024 / 0.005 | 0.0398 / 0.528 | 0.0033 / 0.031 |
| R3 heterogeneous 9×9 (wind, fuel), Σ ≈ 0.6/h, 8 h | 121.5 | 0.0014 / 0.011 | 0.0102 / 0.326 | 0.0015 / 0.008 |
| R4 as R3 with wind rotating 45°/h (8 hourly kernels) | 82.5 | 0.0013 / 0.031 | 0.0097 / 0.556 | 0.0012 / 0.021 |
| R5 heterogeneous 9×9 at c651 magnitude, 12 h | 31.0 | 0.0006 / 0.016 | 0.0018 / 0.234 | 0.0006 / 0.018 |

- **R1, R3, R4, R5:** dt = 1/32 is at the noise floor.
- **R2 (fastest):** still converging at about first order; W1rel 0.108 → 0.055 → 0.031 for dt = 1/8 → 1/16 → 1/32.
- **R1:** the slow regime reproduces the hourly marginals within MC error (Iris's acceptance criterion 2).
- **Small analytic case** (`convergence_check.py`): the gap shrinks 14.1 → 0.34 for dt = 1 → 1/64, i.e. first order.
- **Original toy** (`toy_check.py`, 3×3 ignition, 12 h): hourly CA 349.8 ± 1.0 vs first-passage 771.0 ± 2.4 expected new cells at Σ = 1/h (55% fewer); 3.48 vs 3.63 at Σ = 0.043/h.

## 4. Is the gap just synchronous-update lag? (Iris's arm)

Command: `python research/harness-2026-11/s-d1/lag_check.py` (≈4 min) → `RESULTS_lag.json`. Setup: n = 2,000, same kernels and ignition as Gate 1.

The half-step arm treats cells ignited in a step as sources for half a step, with no further cascade within the step.

Mean new cells at T (± SE), and the share of the hourly → first-passage gap closed:

| regime | first-passage | hourly | **hourly + half-step** | m = 2 | m = 4 | m = 8 |
|---|---:|---:|---:|---:|---:|---:|
| R5 (c651 magnitude, 12 h) | 31.02 ± 0.42 | 24.12 | **30.92 (98.6%)** | 50.7% | 78.5% | 84.2% |
| R3 (Σ ≈ 0.6/h, 8 h) | 121.50 ± 0.62 | 82.15 | **114.28 (81.6%)** | 42.8% | 68.7% | 84.9% |
| R2 (Σ = 1/h, 8 h) | 323.67 ± 1.42 | 152.90 | **269.71 (68.4%)** | 33.9% | 61.7% | 78.6% |

**What it shows.** At c651-like rates the hourly vs continuous gap is almost entirely synchronous-update lag. A one-line correction removes it at 2× stencil cost.

**Over-correction caveat.** The 98.6% partly reflects a lucky over-correction relative to m = 8. Per-cell L1 to first-passage is 0.0006 for half-step against 0.0007 for m = 8, i.e. similar, not better. In fast regimes 18–32% of the gap remains, so the sampler's role is fast regimes and tails.

**What it does not show (Iris).** Half-step makes the fitted model faster. Whether that is *more accurate* on real fires is untested. The no-refit test is the existing rollout ± half-step on US2024 through S-D9. It is blocked here because no US2024 inputs are available to me; I have asked Victor.

## 5. Sizing: where does the hourly cap bind, and where does c651 sit?

### Cap binding on observed perimeters (descriptive)

| data | pairs | new 375 m cells | share beyond 4 cells per gap-hour | notes |
|---|---:|---:|---:|---|
| GOFER v0.2 hourly perimeters, 28 CA fires (`gofer_cap.py`) | 4,071 hourly | 185,278 | **8.9%** (1.25% with one GOES-pixel tolerance, d > 4g + 6) | per-fire median 7.5%, range 0.7–22%; 804 intervals with any |
| NIROPS survey pairs, S-D9 part-a allowlist + 23 fit fires (`nirops_cap.py`) | 3,725 (median gap 24 h) | 254,658 | 0.22% (part-a 0%; fit-23 0.47%) | the one binding pair: August Complex 2020-08-20, 14.5 h, max 98 cells (a complex merging units) |
| VIIRS overpasses, Korea 2025 Gyeongbuk (`firms_korea_cap.py`) | 28 | 2,889 | 12.0% | 326 of 642 cells on 25 Mar 16:09 UTC beyond the 11-step reach, max 45 km in 10.7 h |

- **GOFER:** all 28 fires were read before S-D9 set its GOFER membership rule. This is recorded in the S-D9 ledger as aggregate label-only inspection, and per-fire stats of H-test fires must not tune a candidate. GOFER boundaries come from ~2 km GOES pixels, hence the tolerance column.
- **NIROPS:** parts b–d and held-out fires were never read.
- **Korea VIIRS:** KFS_01 is held out in forecast-v2, so this is descriptive only. The jump envelope (`RESULTS_firms_korea_cap.json`) is an **upper** envelope, inflated by omission. For gaps of 0.5–3 h, 21% of new cells are > 0.5 km from earlier detections, 7.4% > 1 km and 1.2% > 2 km.

**Reading (agreed with Iris and Victor).** The cap binds for roughly 1–9% of new cells per hourly interval on GOFER. It essentially never binds over ~24 h survey brackets, and it binds strongly in the 25 March Korean run. Victor's US2024 diagnostic: all 1,651 tail positives where d4 gives p < 1e-5 are within hourly reach. So the continuous-time step alone does not fix that tail. **D1's case is short horizons and fast events** (S-D9 A1 §2.1 stratum r = d_cheb / (4·lead) ≥ 1, counted only under the one-pixel tolerance) **plus tail estimation**.

### c651 rate magnitude (`c651_rates.py` → `RESULTS_c651_rates.json`)

- **Real, one snapshot** (c651 Fish Creek demo): rate −log(1−q) at cells adjacent to the burned set has median 0.011/h and max 0.024/h. At cells 2–4 away the median is 0.0008/h. This is the slow regime.
- **Proxy** (c651 kernel generator on spatially uniform synthetic patches over a covariate grid; not real environments): total coefficient sum has median 0.075, q90 0.45, q99 1.19, max 5.4 /h. In 75% of patches it is above 0.043, in 1.8% above 1.

## 6. Conditional Monte Carlo tail estimator

- **Estimator.** `P(T_i ≤ t | T^{−i}) = 1 − exp(−Σ_s [Λ_si(t) − Λ_si(T_s^{−i})]⁺)`.
  - This is exact: a first passage to `i` never passes through `i`, and its in-edges form a cut (Sofia: L'Ecuyer et al., conditioning on a uniformly directed cut).
  - From one Dijkstra, `T_s^{−i} = T_s` for every in-neighbour that is not a shortest-path-tree descendant of `i`. Dropping the descendants gives the lower value `lo`; using their full-graph times gives the upper value `hi` (Iris's bounds).
- **Exactness on unburned cells.** If `T_i ≥ t`, every descendant has `T_s > t` and contributes nothing. So **lo = hi exactly on every cell not burned by t** in that trajectory.
- **40×40 at equal wall time** (`cmc_check.py` → `RESULTS_cmc.json`, n = 4,000; CMC costs 4–6× per trajectory). Median efficiency gain over plain counting, by probability bin:

  | p bin | median gain |
  |---|---:|
  | p ≥ 0.1 | 1.4–20× |
  | 1e-2 – 1e-1 | 1.9–3.6× |
  | 1e-3 – 1e-2 | 3.7–6.3× |
  | 1e-4 – 1e-3 | 6.0–12× |
  | 1e-6 – 1e-4 | 20–35× |

  In the 1e-6 – 1e-4 bin most cells get zero plain hits.
- **Caveat.** (hi − lo)/p reaches 0.4–2.1 on a few tail cells, so the local repair is needed there. The repair re-runs the subtree with `i` deleted, reusing the per-edge clocks; the threshold must be fixed in advance.
- **Real-size grid with peak memory and the fair hourly-conditioning baseline** (`cmc_real.py` → `RESULTS_cmc_real.json`): see §8, filled in when the run completes.

## 7. Performance against the real hourly rollout (`perf.py` → `RESULTS_perf_*.json`)

R3 kernels, 40×40, n = 2,000, one thread, each arm in its own process:

- **first-passage:** 0.27 ms/trajectory, peak RSS 941 MiB;
- **`wildfire.rollout.simulate`** (torch, with its coverage probes): 29.5 ms/trajectory, 1,735 MiB;
- **imports only:** 848 MiB.

On top of imports, that is about 93 MiB for first-passage against 887 MiB for the rollout. They are different models (mean new cells 121.5 vs 82.5).

R5 kernels (c651 magnitude, 12 h):

- **first-passage:** 0.086 ms/trajectory, 941 MiB;
- **rollout:** 43.2 ms/trajectory, 1,732 MiB;
- mean new cells 31.0 vs 24.0.

First-passage cost scales with the burned cells, not with grid × steps. The rollout's batch size (500) and its coverage-probe pass are part of its measured cost.

## 8. Real-size conditional estimator

Pending: `RESULTS_cmc_real.json`.

## Blockers and dependencies

- **Refit / step-size ablation (Iris's main experiment)** needs full-grid per-event inputs (`forecast/data/environment/regions/*`, `biome_classes.json`). These are owner-only. The c651 patch cache is insufficient for m > 1, because the receptive field grows to 4m cells. The orchestrator has asked the user.
- **Wapiti / US2024 runs** need the case rasters, which are owner-only. Daniel's covariate rebuild is partial and not byte-identical.
- **S-D9:** the scoring interface is agreed. Candidates emit native cumulative marginals at survey times, so they are eligible for the arrival RPS. The D1 training pool is part-a + fit-23 (not frozen yet). H-dev and H-test GOFER membership is pending.

## Ideas and gaps

1. The half-step correction is the cheapest candidate improvement. It has to be tested on real labels before it is credited (§4).
2. For a fair continuous-time vs hourly comparison: a CT-likelihood refit (Elena) or Iris's step-size ablation refit (m = 1, 2, 4, 8 plus the sampler) on identical labels.
3. Victor's tail (p ≈ 1e-6 cells burning at 0.3–0.6%) is a magnitude/calibration failure, not reach. The conditional estimator gives low-variance tail values once a model is calibrated there. It does not fix calibration.
4. Not done:
   - the conservative coverage/unknown-cell envelope (the sampler implements the zero boundary only);
   - Kenah–Robins burnout windows, needed for burnout variants. Per Sofia, a shared per-cell window correlates out-edges and changes the variance of burned area.
5. FPP shape diagnostics (Sofia): limit shape vs observed length-to-breadth; arrival SD growing like distance^{1/3}. Untested.
