# Is fixed-route admissibility monotone in a uniform ignition advance δ?

Status: **analytical claim, awaiting independent verification (Hannah)**. Numerical checks on the frozen panel are in
`RESULTS.md` once run.

## Model (as implemented by the frozen bridge `wfg.final-forecast-bridge/2.0-latest-c651`)

Per member, a cell with a drawn first-new ignition time `b ∈ [0, H)` (H = horizon = 3600 s) is flaming and emitting
on `[b, b+T)`, with the scalar burning duration `T` (≈ 3970.46 s on all frozen exports, so `T > H`). Present-fire cells
are active on `[0, R_max)`. Contact is the closed road footprint meeting a flaming cell; dose and peak are integrals and
maxima of incident flux, a nonnegative function that is linear in the active-source indicator. (The packet adds a
per-interval margin `1e-8·max(1 W/m², max flux)`, which is also nondecreasing in the active set.) A journey, dwell
included, lies in `[0, t_end] ⊆ [0, H]`.

Perturbation `A_δ`: every finite drawn `b` becomes `b − δ`. Present fire and `T` are unchanged.

## Claim 1 (monotone range)

Let `b_min` be the smallest drawn ignition time in any member. For every fixed route, if the route is admissible
under `A_δ`, it is admissible under `A_δ'` for all `0 ≤ δ' ≤ δ`, provided `δ < T − t_end + b_min`. Since
`b_min ≥ 0` and `t_end ≤ H`, this always covers `δ < T − H` (≈ 370 s on the frozen exports).

*Proof.* A source is active at time t under `A_δ` iff `b − δ ≤ t < b − δ + T`. For `t ≤ t_end` and
`δ < T − t_end + b`, the right-hand inequality always holds, so activity reduces to `t ≥ b − δ`, which is
nondecreasing in δ. Contact (a union over sources), flux (a nonnegative linear combination), dose and peak are therefore
nondecreasing in δ at every route point. Each admissibility condition has the form "contact = ∅, dose ≤ budget,
peak ≤ budget", so if it holds at δ it holds at every δ' ≤ δ. ∎

## Claim 2 (contact alone is monotone on [0, T])

For a route that is contact-clear at δ = 0, contact-clearness is monotone on `δ ∈ [0, T]`.

*Proof.* A route visit `[t0, t1]` to a cell with ignition b is in contact exactly for `δ ∈ [b − t1, b + T − t0)`.
Contact-clear at 0 means `b − t1 > 0` for every visited ignited cell (a visit with `b ≤ t1` would already be in contact,
since `b + T − t0 > T − H > 0`). Each bad interval therefore starts at a positive δ and ends after `T + (b − t0) > T`.
The bad set intersected with `[0, T]` is `[min(b − t1), T]`, an up-set. ∎

So the exact contact margin of a route is `min(b − t1)` over its visits to ignited cells. It has a closed form and
needs no repeated search.

## Counterexample (dose, δ beyond the monotone range)

Admissibility in general is **not** monotone, because advanced sources also burn out earlier. Take a destination
dwell `[3480, 3600]` (t_end = H = 3600) and two sources near the destination, each giving flux k at the dwell point:
S1 with `b = 10` and S2 with `b = 3590`, with T = 3970 and a dose budget `B = 200·k·s`.

| δ (s) | S1 active over dwell | S2 active over dwell | dwell dose | admissible |
|---|---|---|---|---|
| 0 | all 120 s (`[10, 3980)`) | 10 s (`[3590, …)`) | 130 k | yes |
| 100 | all 120 s (`[−90, 3880)`) | 110 s (`[3490, …)`) | 230 k | **no** |
| 500 | none (`[−490, 3480)` ends at the dwell start) | all 120 s | 120 k | **yes** |

The route is admissible at δ = 0, inadmissible at δ = 100 and admissible again at δ = 500. Bisection on δ can
therefore land on a later transition and over-report the margin. The breakdown needs `δ ≥ b + T − t_end`, which is
outside Claim 1's range.

## Consequences for computing a margin

* Define the margin as the **first failure**, `δ* = inf{δ ≥ 0 : route inadmissible under A_δ}`. This is
  well defined without monotonicity.
* Contact part: use the closed form `min(b − t1)` from Claim 2. No search is needed.
* Radiation part: bisection is sound only inside `[0, T − t_end + b_min)`. Beyond that range, dose as a function of δ
  is continuous and piecewise linear: activity switches only when `b − δ` or `b − δ + T` crosses a route breakpoint
  or a flux-interval boundary. An exact first-failure scan therefore needs only the finite set of switching values,
  not bisection.
* The checker certifies with outward enclosures rather than exact values. Even where the exact model is monotone, the
  certified status could in principle fail to be monotone (slab subdivision, the adaptive fallback). The sweep in
  `RESULTS.md` tests this empirically on a δ grid.
