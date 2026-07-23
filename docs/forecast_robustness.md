# Forecast-error robustness of the evacuation routes

**Question.** The router chooses routes *once*, on the forecast hazard field. This
analysis asks the separate question: **if the forecast were wrong, would the
already-chosen routes still be safe?** We take the two fixed routes frozen into
`data/processed/routing_demo.npz` — a naive route (28 nodes) and a future-aware
route (23 nodes) — hold their geometry and arrival clock fixed, and re-score
their on-route hazard against deliberately perturbed hazard fields. **We never
re-route.**

## Scope and caveats

This is a robustness analysis of the **method** on **one real route pair**. The
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

## Primary result — deterministic breaking-point sweep

For each axis independently, the smallest perturbation at which the future-aware
route's maximum on-route hazard first reaches `p_cut = 0.5`:

| Axis | Breaking point | Behaviour |
|------|----------------|-----------|
| Temporal (early arrival) | **Never** within 720 min (12 h); max 0.352 | monotone, shallow |
| Probability scaling | **Never** within documented k ≤ 2.0 (max 0.270); still below 0.5 even at k = 20 (max 0.481) | monotone, shallow |
| **Spatial translation** | **125 m** (eastward); grid first crosses at 250 m | **non-monotone — the breaking axis** |

The temporal and probability axes barely move the future-aware route: arriving up
to 12 hours early lifts its peak only from 0.260 to 0.352, and multiplying every
hazard probability by 2 lifts it only to 0.270. Neither reaches the cutoff
anywhere in — or well beyond — the explored range.

**Why probability scaling is so weak — and why ×20 gives 0.481, not 1.0.**
Because *k* multiplies and clips each **cell before interpolation**, not the
sampled node value, a route node only gains as much as its *surrounding cells*
gain. The future-aware route's peak node sits at bilinear weights (dc = 0.75,
dr = 0.25) where ~75 % of its weight falls on cells that are essentially zero and
only ~25 % on a cell already saturated at 1.0. Scaling leaves the saturated cell
at 1.0 (clipped — no gain) and lifts the near-zero neighbours only modestly, so
even ×20 raises the route-max to just 0.481. A naive `clip(k · 0.2597)` would
read 1.0 at k ≥ 3.86, but that scales the sampled scalar, which the field never
does. The route runs where the underlying *cells* are low, so scaling the field
cannot manufacture a high on-route sample.

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

So the route tolerates at most ~125 m of front displacement toward the east and
at most ~530 m toward the northwest before a node enters hazard. By the 250 m
grid point the worst direction already sits at 0.75.

Headline: **the future-aware route stays hazard-free against forecast timing
error (arriving 12 h early) and probability error (2× and beyond), but a spatial
forecast error of ~125 m in the worst direction is enough to put it into hazard.**

## Secondary result — joint Monte Carlo

2000 draws (seed 20260723), sampling the three axes jointly and independently
from the documented ranges: Δt ~ U(0, 120) min, translation magnitude
~ U(0, 2000) m with a uniform continuous direction, k ~ U(1.0, 2.0). Both routes
are re-scored in the *same* perturbed world each draw.

- **Fraction where the future-aware route stays below `p_cut`: 0.21.** Because
  the spatial range extends to 2000 m — four cells, far past the 125 m breaking
  point — most random draws displace the route into hazard. The 95th-percentile
  perturbed on-route peak is 0.92.
- **Fraction where the future-aware route's exposure stays below the naive
  route's: 0.86.** Even when perturbation pushes the future-aware route into
  hazard, it usually still accrues *less* cumulative exposure than the naive
  route in the same perturbed world.

The result is stable: across seeds 0.21 vs 0.856–0.860, and converged from 500 to
4000 draws (0.18→0.21 and 0.844→0.859). The two fractions carry different
messages — the *hazard-free guarantee* is sensitive to large spatial error,
while the *relative advantage over the naive route* is robust.

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
