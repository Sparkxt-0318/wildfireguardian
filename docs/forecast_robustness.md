# Forecast-error sensitivity of the evacuation routes — risk reduction with a characterized failure mode

**The claim this analysis supports.** On this one real route pair the future-aware
method delivers **risk reduction with a characterized failure mode**, *not*
blanket robustness. Its exposure advantage over the forecast-unaware route
largely survives perturbation, while its hazard-free guarantee has a specific,
quantified breaking condition (spatial displacement). We state it that way
deliberately: a method that measurably reduces risk *and* names the error that
would defeat it is a stronger result than an untested claim of robustness.

**Headline.**

- **PRIMARY — 미래 인지 경로의 노출이 화재 예측 미사용 경로보다 낮은 경우가 86%였습니다.**
  (The future-aware route's exposure is lower than the forecast-unaware route in
  86 % of perturbed worlds.)
- **SECONDARY — 공간 오차에 취약하며, 방향에 따라 125–530 m 변위에서 임계값에 도달합니다.**
  (It is vulnerable to spatial error, reaching the cutoff at displacements of
  125–530 m depending on direction.)

**Question.** The router chooses routes *once*, on the forecast hazard field. This
analysis asks the separate question: **if the forecast were wrong, would the
already-chosen routes still be safe?** We take the two fixed routes frozen into
`data/processed/routing_demo.npz` — a naive route (28 nodes) and a future-aware
route (23 nodes) — hold their geometry and arrival clock fixed, and re-score
their on-route hazard against deliberately perturbed hazard fields. **We never
re-route.**

## Scope and caveats

This is a forecast-error *sensitivity* analysis of the **method** on **one real
route pair** — characterizing where it reduces risk and where it breaks, not
asserting robustness. The
npz route pair has a *different origin* from the committed `routing_demo.json`
headline (origin_node 3316, 23/23 nodes). It is **not** a restatement of that
headline. The perturbation magnitudes below are **exploratory ranges, not a
calibrated forecast-error model** — they probe how much error the route can
absorb, not how much error the forecast actually has.

The re-scorer is a standalone reimplementation of
`wildfireguardian.routing.hazard.HazardSequence` (bilinear in space, linear in
time, clamped outside the horizon) and the route scoring in
`routing.evacuation._evaluate_path` (exposure = Σ hazard·edge-time, max-hazard =
worst node, enters-hazard = any node ≥ `p_cut`). At zero perturbation it
reproduces the stored `fa_node_haz` / `naive_node_haz` arrays to < 1×10⁻⁶,
so the analysis runs entirely from the npz with no raw bundle. Cutoff
`p_cut = 0.5`.

Unperturbed, the future-aware route peaks at **0.2597** on-route hazard — a
**0.2403 margin** below the `p_cut = 0.5` impassability cutoff — while the naive
route peaks at 0.755 and enters hazard.

## Three perturbation axes

- **(a) Temporal shift** — the front arrives `Δt` minutes *early*; a node at
  clock time *t* then sees the hazard the forecast placed at *t + Δt*. Grid
  Δt ∈ {0, 15, 30, 60, 90, 120} min.
- **(b) Spatial translation** — the whole reach envelope is displaced by
  *(dx, dy)*; hazard at *(x, y)* becomes the forecast hazard at *(x−dx, y−dy)*.
  Grid magnitude ∈ {0, 250, 500, 1000, 2000} m across 8 compass directions.
- **(c) Probability scaling** — every cell multiplied by *k* and clipped to
  [0, 1]. Grid k ∈ {1.0, 1.2, 1.5, 2.0}.

The exact scaling formula matters (see the note below): *k* is applied to each
grid **cell** and clipped **before** the bilinear spatial and linear temporal
interpolation that produce a route node's hazard —

```
node_haz(k) = clip( (1-f)·B[ clip(k·S_i0, 0, 1) ] + f·B[ clip(k·S_i1, 0, 1) ], 0, 1 )
```

where `S_i0`, `S_i1` are the two bracketing forecast surfaces, `B[·]` is the
bilinear sample at the node, and `f` is the time fraction. This is **not**
`clip(k · node_haz)`.

## Deterministic breaking-point sweep

For each axis independently, the smallest perturbation at which the future-aware
route's maximum on-route hazard first reaches `p_cut = 0.5`:

| Axis | Breaking point | Interpretation |
|------|----------------|----------------|
| Temporal (early arrival) | **Never** within 720 min (12 h); max 0.352 | genuine but shallow response — does not break in range |
| Probability scaling | **Never** within k ≤ 2.0 (max 0.270); still 0.481 even at k = 20 | **null result — a low-information test, NOT robustness** (see below) |
| **Spatial translation** | **125–530 m** by direction (E worst, NW most forgiving) | **non-monotone — the breaking axis** |

The temporal axis moves the future-aware route only modestly — arriving up to 12
hours early lifts its peak from 0.260 to 0.352, never reaching the cutoff in
range. This is a real, shallow response, not a robustness proof.

**Probability scaling is a NULL RESULT WITH A KNOWN CAUSE — do not read it as
robustness.**

> 확률 스케일링 축에서는 임계값에 도달하지 않았으나, 이는 강건성의 근거로 해석되어서는 안
> 됩니다. 해당 경로의 최대 노출 지점은 확률 1.0으로 포화된 셀에 인접해 있으며, 곱셈적
> 스케일링은 포화된 셀의 값을 높일 수 없습니다. 따라서 본 축은 이 경로쌍에 대하여 정보량이
> 낮은 검정이며, 예측 화재 규모의 과소추정을 검정하려면 임계 영역의 형태학적 팽창이 더
> 적합합니다. 이는 향후 과제입니다.

(*The probability-scaling axis did not reach the cutoff, but this must not be read
as evidence of robustness. The route's maximum-exposure point is adjacent to a
cell already saturated at probability 1.0, and multiplicative scaling cannot
raise the value of a saturated cell. This axis is therefore a low-information
test for this route pair; to probe underestimation of forecast fire size,
morphological dilation of the hazard region is the appropriate instrument. That
is left as future work.*)

The mechanism, verified numerically: *k* multiplies and clips each grid **cell
before** the bilinear+time interpolation, not the sampled node value. The
future-aware route's peak node sits at bilinear weights (dc = 0.75, dr = 0.25)
with ~25 % of its weight on a cell already saturated at 1.0 and ~75 % on cells
near zero. Scaling leaves the saturated cell at 1.0 (clipped — no gain) and lifts
the near-zero neighbours only modestly, so even ×20 reaches just 0.481. A naive
`clip(k · 0.2597)` would read 1.0 at k ≥ 3.86, but that scales the sampled
scalar, which the field never does. Because the axis literally cannot exercise
the saturated cell that dominates this node, its "no break" says nothing about
the route's tolerance to a genuinely larger fire — hence a low-information test,
and hence morphological dilation as the correct future instrument.

**Spatial displacement is the axis that breaks it.** Because the fixed route
threads close to the hazard boundary, translating the front by only a few
hundred metres slides a route node into a high-hazard cell. The response is
**non-monotone** in magnitude (displace far enough and the route can emerge on
the far side of the front), so the breaking point is the *first* radial crossing,
scanned at 5 m steps and minimised over the 8 directions. The smallest breaking
displacement is **125 m to the east** (a quarter of the 500 m hazard cell). The
full per-direction first-crossing thresholds span **125 m (worst) to 530 m
(most-forgiving)**:

| Direction | E | SE | SW | NE | N | S | W | NW |
|-----------|----|----|----|----|----|----|----|----|
| First crossing to p_cut (m) | 125 | 175 | 175 | 175 | 205 | 205 | 205 | 530 |

So the failure mode is directional: the route tolerates as little as **125 m** of
front displacement toward the east but up to **530 m** toward the northwest
before a node enters hazard — a **125–530 m** breaking band, not a single number.
Quoting the 125 m minimum alone overstates the fragility; the route's actual
tolerance depends on the direction of the forecast error. By the 250 m grid point
the worst direction already sits at 0.75.

Breaking-point summary: **the future-aware route does not break under forecast
timing error (arriving 12 h early) and cannot be exercised by the
probability-scaling axis (a low-information test here), while spatial forecast
error is the real failure mode — reaching the cutoff at a direction-dependent
125–530 m of front displacement.**

## Joint Monte Carlo

2000 draws (seed 20260723), sampling the three axes jointly and independently
from the documented ranges: Δt ~ U(0, 120) min, translation magnitude
~ U(0, 2000) m with a uniform continuous direction, k ~ U(1.0, 2.0). Both routes
are re-scored in the *same* perturbed world each draw.

**Read the two fractions differently — one reflects the method, one reflects the
chosen range.**

- **Exposure advantage (the PRIMARY result): 0.86.** In 86 % of perturbed worlds
  the future-aware route's exposure stays *below* the naive route's — even when
  perturbation has pushed it into hazard. This is the risk-reduction signal, and
  it is a property of the method.
- **Stays below `p_cut`: 0.21 — but this number largely reflects the sampling
  range, not the method.** The Monte Carlo samples spatial displacement uniformly
  out to **2000 m — 16× the 125 m minimum break point (and ~4× the 530 m
  maximum)** — so the majority of draws sit *past* the breaking band by
  construction, and the future-aware route is displaced into hazard in most of
  them. The 0.21 figure must never be quoted without this caveat: it is an
  artifact of a deliberately punishing exploratory range, not a measured failure
  rate under realistic forecast error. (95th-percentile perturbed on-route peak:
  0.92.)

Both fractions are stable and seeded-reproducible: the exposure advantage holds
at 0.856–0.860 across seeds and converges 0.844 → 0.859 from 500 to 4000 draws;
the below-`p_cut` fraction sits at 0.18 → 0.21 over the same range — and carries
the same 2000 m sampling caveat wherever it appears.

## Reproduce

```
python scripts/run_routing_monte_carlo.py            # refuses to overwrite existing JSON
python scripts/run_routing_monte_carlo.py --force    # regenerate
python scripts/mc_perturb.py                         # re-scorer self-check
```

Full results, perturbation ranges, seed, npz SHA-256 and git HEAD are recorded in
`data/processed/forecast_robustness.json`. That path matches the
`data/processed/**` ignore rule, so — like `routing_demo.json` — it must be
force-added (`git add -f`) to be tracked.
