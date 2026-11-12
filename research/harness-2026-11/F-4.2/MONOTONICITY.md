# Is fixed-route admissibility monotone in a uniform ignition advance δ?

Status: **verified PASS WITH NOTES by Mira (12 Nov, @ b6c94bb)**. She confirmed the counterexample transitions by hand
and found the Claim 1 and Claim 2 proofs correct.

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
needs no repeated search. **Range:** it is meaningful only when `min(b − t1) ≤ T`. Beyond T a visited cell may already
have burned out, so contact-clearness can return. Report a larger value as "> T (no contact-driven failure within
[0, T])".

## Counterexample (dose, δ beyond the monotone range)

Admissibility in general is **not** monotone, because advanced sources also burn out earlier. Take a destination
dwell `[3480, 3600]` (t_end = H = 3600) and two sources near the destination, each giving flux k at the dwell point:
S1 with `b = 10` and S2 with `b = 3590`, T = 3970.464… s (the frozen exports' cell duration) and a dose budget
`B = 200·k·s`. `counterexample.py` evaluates this in exact rational arithmetic:

| δ (s) | S1 over dwell (`[10−δ, 3980.46−δ)`) | S2 over dwell (`[3590−δ, …)`) | dwell dose | admissible |
|---|---|---|---|---|
| 0 | 120 s | 10 s | 130 k | yes |
| 100 | 120 s | 110 s | 230 k | **no** |
| 450 | 50.46 s | 120 s | 170.46 k | **yes** |
| 500 | 0.46 s | 120 s | 120.46 k | yes |

The route is admissible exactly on `δ ∈ [0, 70]` and on `δ ≥ 420.464…`, and inadmissible in between. Bisection on δ
can therefore land on the later transition and over-report the margin. Re-admission needs `δ ≥ b + T − t_end` for
some source, which lies outside Claim 1's range (here `δ < 380.46`).

**Under the shipped limits on the frozen panel this cannot flip a verdict.** Across the 15 published routes the
certified dose upper bound is at most 0.33 of the dose budget, and 0.30 of that is recorded incurred history on three
missions. The certified peak upper bound is at most 0.0005 of the peak budget. Radiation never binds, so every verdict
is decided by contact, which is monotone on `[0, T]` (Claim 2). The counterexample needs a dose limit that binds
during the dwell.

**Status (12 Nov):** following this counterexample and the finding that ignition timing rarely constrains these
routes, the ignition-advance margin is dropped as the headline. The closed-form contact time margin
`min(b − t_exit)` is kept as a diagnostic column. The primary margin is the spatial clearance in `clearance.py`
(nested dilations, so it is monotone by construction).

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
