# Hybrid radiation enclosure version 1

Accepted API candidate: `hybrid_radiation.HybridRadiationBounds`, compatible with `RadiationBounds.from_case(path, settings=...)` and `trajectory_bound(legs, peak_budget_kw_m2=..., dose_budget_kj_m2=scalar_or_member_map, incurred=member_map, deadline=absolute_shared_deadline)`. `DEFAULT_SETTINGS` exports the separately versioned numerical policy. Radiation results remain `CERTIFIED_RADIATION`, `DEFINITE_REJECT` or `UNRESOLVED`. The pipeline must separately establish complete supported contact clearance, graph/turn legality, issue/travel/wait/arrival/dwell continuity and resource compliance.

## Unchanged physical contract

This module uses the same immutable source realizations, scalar resolved intensity, source geometry, event phases, receiver interpretation and budgets as the prior practical checker. Baseline density is 18,000 W/m², height separation 5 m, burning duration 300 s and initial remaining phase 300 s. Unknown future probability, initial active fire, unknown current-state rules and finite ensemble dependence are not changed. Radiation is the original finite-cell kernel `h/[4π(r²+h²)^(3/2)]`; this is not a replacement combustion model, Lambertian law or physical calibration.

Every source history is interpreted as exact represented numbers, with right-continuous half-open activity `[birth,birth+duration)`, and complete current phase `[0,remaining)`. The declared source grid has disjoint cell interiors. The complete source law, support and axis-aligned affine requirements remain inherited. Unsupported values and masks cannot authorize acceptance. Model-relative proof is not real-fire safety validation.

## Deterministic hybrid policy

For each exact receiver AABB:

1. Form the original outward coarse radial enclosure for every represented source cell.
2. Derive the immutable set of sources that can ever be active under the represented complete history: current cells only when `remaining>0`, plus every explicitly finite future event in any member. An explicitly absent source contributes exactly zero. This does not infer absence from missing probabilities or incomplete support.
3. Select analytic source bounds if the lower Chebyshev source/receiver-box gap is at most `16 × h` (80 m under baseline), or if the complete realization has at most eight ever-active source cells. The sparse branch treats every potentially active source analytically, irrespective of distance.
4. Other potentially active sources within the inherited near partition distance 600 m use the existing exact 8×8 source tiles with outward radial bounds. Distant potentially active sources retain whole-cell radial bounds. No source contribution is dropped.
5. Intersect each selected source's valid analytic and coarse radial enclosures, then perform the inherited source-phase dose/peak calculation over receiver slabs.

The policy is geometric and source-content deterministic. It does not inspect route feasibility, lower hazards, pick favourable member budgets or use confirmation outcomes. These defaults were selected once on known prior failures and controls. The frozen coarse completed-straddle development override is retained; its source-tile/receiver settings are not erased to recover an outcome.

Analytically selected cells do not also perform 8×8 radial subdivision: coarse radial and analytic enclosures are intersected. This saves redundant near geometry work but means the hybrid enclosure need not be uniformly tighter than the practical tiled enclosure for every source or member. All unselected near cells retain tiled bounds. Any unresolved regression must remain visible.

## Analytic source enclosure argument

For source rectangle `R=[sx0,sx1]×[sy0,sy1]` and receiver box `X=[rx0,rx1]×[ry0,ry1]`, every translated footprint `R−x` contains the rectangle

`I=[sx0−rx0,sx1−rx1]×[sy0−ry0,sy1−ry1]`

when its side lengths are positive, and is contained in

`O=[sx0−rx1,sx1−rx0]×[sy0−ry1,sy1−ry0]`.

The kernel is nonnegative, so `integral_I K <= integral_(R−x) K <= integral_O K` for every receiver in X. Empty I gives the valid lower bound zero. The inherited `RationalKernel.source_receiver_box` computes the lower rectangle enclosure on I and upper rectangle enclosure on O, multiplied by the exact resolved source intensity. Its exact source/receiver Fraction geometry does not assume extrema occur at sampled road points.

Rectangle integration uses the signed four-corner solid-angle expression

`atan(xy/[h sqrt(x²+y²+h²)])/(4π)`.

Rational Machin pi, integer sqrt brackets, reduced alternating atan series and outward dyadic arguments enclose each corner; signed corner addition/subtraction uses rational interval endpoints. Multiplication by the exact represented resolved intensity is exact rational arithmetic; conversion to binary64 is directed outward. The radial enclosure is separately justified by distance extrema over complete source/receiver boxes and verified outward elementary arithmetic. Both are enclosures of the **same** represented physical integral, so `[max(lower1,lower2), min(upper1,upper2)]` remains valid. Reversed intersections produce UNRESOLVED numerical failure, never a guessed certificate.

The full-plane kernel integral is 1/2. Because actual active source cells are disjoint, per-cell and total upper flux retain the same valid density/2 cap. Expanded analytic outer rectangles may overlap; that broadens their sum, but does not change the disjoint actual-source plane bound. No claim is made that either enclosure is physically validated.

## Entire mission, events and budgets

Receiver slabs retain the existing 16 m maximum axis displacement, with a second 8 m pass only if needed; waits and dwell use their actual fixed positions. Source events are not rounded into 300-second unions. Each source's exact active overlap length with a receiver slab is converted outward, and lower/upper flux×overlap products bound its integral. Explicit incurred exposure for every member is accumulated before all motion, waits and dwell. J/m²/kJ/m² conversions are outward. Each member uses its own exact represented dose budget, with scalar shorthand only for genuinely equal limits.

Peak upper bounds include all sources potentially active anywhere in a closed receiver slab and enclose endpoint ignition, one-sided burnout limits and interior spatial maxima. Peak lower bounds retain the inherited valid left-endpoint active-source lower enclosure, which can be weak for a source first igniting inside a slab. This may leave unusual lower peak thresholds unresolved; it cannot certify a false acceptance. Baseline peak upper is 9 kW/m² against unchanged 10, so observed thermal failures are dose constraints.

Analytic source refinement changes precision, not time semantics. Original source energy, occurrence probabilities and phases are unchanged. Contact-first clipping remains separately owned and unmodified. Fixed-path rejection is neither global infeasibility nor a statement about alternatives, and a complete radiation certificate is not optimality.

## Cache ownership and numerical dependencies

The inherited source snapshot copies caller inputs into private immutable tuples/read-only arrays. Cache identity includes represented geometry/events/current phases, complete support status, scenario IDs, all source configuration values, resolved density/height, evidence class and all hybrid/radial numerical settings. Analytic proof settings explicitly enter that identity: sqrt bits 80, atan argument bits 56, atan terms 20 and Machin terms 32. Policy distance factor, sparse threshold and analytic corner cap are also included. A changed setting/source requires a new explicit instance/epoch; caller mutations do not retroactively alter an owned snapshot.

Each receiver box gets a completed immutable per-source lower/upper vector. The hybrid commits the vector only after every selected analytic intersection succeeds and the shared deadline is checked. A cap during analytic calculation can leave valid rational corner entries for reuse, but cannot commit a radial-only coefficient vector that bypasses required analytic work on a later call. Bounds remaining in the private rational corner cache are valid for the same immutable geometry/height/proof settings. New identity instances have separate caches.

Numeric vector bytes and rational corner cache shallow Python-container estimates are reported separately. The latter excludes nested Fraction payloads; full process RSS is the total-memory evidence. Their byte scopes must not be directly compared as equivalent retained heap sizes.

## Caps and result semantics

The owning pipeline starts the unchanged shared 30-second deadline before preparation and supplies it to this API. The inherited wall and 4096 cumulative receiver-slab limits remain. Analytic work additionally permits at most 65,536 new corner evaluations per call, including refinement; this bounds computation, not an arbitrary storage quota. Every source/tile loop, analytic corner and cache commit shares the deadline guard. Explicit `wall_s=None` and `deadline=None` match inherited default-wall/no-external-deadline semantics.

A cap returns UNRESOLVED. Completed upper bounds meeting every budget may return CERTIFIED_RADIATION; a justified lower-bound violation may return DEFINITE_REJECT. Completed straddles remain UNRESOLVED. Late completion, including final hybrid profiling/metadata work, retains only a checked secondary status while the primary result is UNRESOLVED. The pipeline's measured RSS/content gates are additional conditions. No cap is a proof of infeasibility.

## Development evidence and corrections

One deterministic design resolves the four known radiation precision failures without a parameter sweep: the 06 UTC road-2 depart60 mission obtains member-2 lower dose 111.498 kJ/m², proving fixed-mission rejection; near interior control certifies, overlapping sources reject, and the coarse completed-straddle override certifies. These are known development cases, not fresh benefit. Coordinator's full eighteen known cold pipeline regressions retain four incident certificates, eight incident rejections, four control certificates, one control dose rejection and one unknown-support unresolved outcome. See `DIAGNOSIS.md` and raw development records.

Independent review identified an optional-keyword interface defect: the first hybrid final guard attempted `float(None)` for explicit None keywords that the inherited API accepts. The exact rejected module and before-hash are retained under `results/hybrid_radiation_rejected_explicit_none.py.txt` and `results/hybrid_radiation_explicit_none_correction.json`; normalization was corrected before any fresh opening. Source/enclosure arithmetic did not change.

Author tests include compatible coarse/analytic intersections, interior source/receiver points, phase overlap, accumulated dose, threshold straddles, explicit None options, source/geometry/physics/support and every numerical-policy cache dependency, input mutation isolation, atomic cache under analytic caps, masks and deadline-before/after behavior. An initially overstrong lower-peak-rejection test used a source igniting inside a slab, where the inherited peak lower bound can legitimately stay zero. The corrected control begins at its known ignition; the failed assertion is retained and is not called a checker defect. Independent reference/proof review and fresh frozen confirmation remain mandatory before promotion.
