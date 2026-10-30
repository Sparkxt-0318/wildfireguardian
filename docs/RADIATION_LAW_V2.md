# Radiation law v2, prototype and open gates

Status: HOLD. The library supplies a mathematical optical model and tests, but the empirical gate and frozen-panel campaign are incomplete. It is an opt-in overlay; no frozen integration source or threshold changes.

## Source and receiver geometry

Each declared line segment supports a diffuse planar emitter with uniform radiative exitance E (kW/m2). Tilt produces a planar parallelogram. The radiance is E/pi. For a differential receiving patch with normal n, the dimensionless view factor is the integral of the nonnegative receiver cosine over the source's solid angle, divided by pi. Clipping the polygon at the receiver horizon implements the nonnegative cosine. The exact polygon edge-angle vector follows [Walton, NISTIR 6925, equation 5](https://doi.org/10.6028/NIST.IR.6925). Unit tests compare a centred rectangle closed form, the small-source far field and the infinite-width wall limit.

For worst_case, each panel uses its own maximizing receiver normal when its angular patch lies within that normal's forward hemisphere. Otherwise the orientation envelope is one. Summing these separate maxima encloses a common real receiver orientation; it is not itself a single body orientation. The receiver height is an explicit optional scenario parameter, default ground level. The operator includes both leading and trailing contour panels as a declared approximation, rather than a resolved luminous volume. No occlusion is modeled.

For an infinitely wide vertical wall of height h and a ground receiver with horizontal normal facing it, F=h/(2 sqrt(h^2+d^2)). That is a different geometry from a receiver oriented to maximize a finite panel. Treating these two values as interchangeable would be an error.

## Front geometry and intensity

The affine transform maps pixel corners to projected metres; interpolation nodes are pixel centres. Marching squares returns straight segments approximating the generally curved bilinear isochrone. Saddle connectivity uses a fixed quad-centre rule. The rate uses the quad's mean gradient, R=min(Rmax,1/|grad tau|), an explicit approximation. The advancing direction is +grad tau/|grad tau|; tau=x/R demonstrates the sign. Flat active fields have no identified moving front and are refused. Planar, circular, isolated and affine-shear tests exercise these cases.

Byram intensity is I=H w R, with H in kJ/kg, consumed w in kg/m2, and R in m/s, giving kW/m. L=0.0775 I^0.46 is an empirical, fuel-specific relation. Putnam tilt is atan(1.4 U/sqrt(g L)), as reproduced in [Weise and Biging 1996, equations 3 and 5](https://www.fs.usda.gov/psw/publications/weise/psw_1996_weise000.pdf). Wind-free flames are vertical. The defaults and their source status are recorded in provenance(); the numerical spread cap is not asserted as a universal physical maximum.

Unknown ignition cells are excluded from geometry and recorded, then refused by point flux unless the caller explicitly chooses a counterfactual exclusion. Infinity denotes no ignition; interpolation between finite and infinite times is not identified. An explicit finite never-time surrogate is a different scenario. The frozen bridge's scalar maximum-remaining activity enclosure does not identify exact past per-cell ignition phases, so it is refused rather than converted to guessed flames. Extinction maps are supported when they provide aligned finite positive residence durations. A default point residence and a coarse-cell crossing duration have different meanings.

The dangerous near-front zone is subcell in scale. The library evaluates source endpoints and receiver positions in metres, not cell-centre distances. The claim that thermal limits can bind only inside or at the edge of a burning coarse cell does not follow universally: sufficiently tall/wide sources, multiple fronts, terrain, wind and different receiver geometry can change that conclusion. Current-front positions inferred from coarse data remain model assumptions.

## Conservative enclosure argument

Each quad has at most two leading and two trailing segments. The implemented finite-panel view factor is clipped to [0,1], so each term is at most E. For a time interval, include every quad whose leading or trailing corner-time range intersects it. Sum four times its represented emissive power, using exact Fraction accumulation followed by upward binary64 conversion and an extra ulp. The lower bound is zero. Each point-model segment belongs to an included quad and is bounded by a term of that sum. Enlarging the interval only adds candidate quads; box bounds are independent of box location and thus cannot shrink on enlargement. This proves containment and monotonicity for the implemented model, with a deliberately loose global bound.

The proof does not establish exact bilinear front geometry, physical fire flux, or tight continuous-route bounds. A checker that cannot decide from the interval must return unresolved. Random interior evaluations are regression tests, not proof. A positive lower bound cannot be inferred merely because a source is active somewhere in the interval. Tighter geometric and time-dependent enclosures remain required for useful route certificates.

No distance cutoff is enabled by default. For omitted panels an absolute envelope is sum E_i, because each view factor is at most one. A radius alone cannot yield a uniform relative error: retained flux can approach zero while omitted sources remain. A useful small tail bound requires finite omitted area, geometry, separation and source-strength bounds. No unproved percentage is claimed.

## Dose and threshold discussion

Linear dose is the integral of q dt in kJ/m2. TDU is the integral of q^(4/3) dt with q in kW/m2 and t in seconds. dose() analytically integrates this expression for a piecewise-linear flux interpolation; it does not certify flux between unsampled moving-front evaluations. [HSA's guidance](https://www.hsa.ie/media/4oap0mec/tlup-guidance-feb-2023-final.pdf) gives the contextual Eisenberg probit convention with a=-14.9 and b=2.56. Switching to W/m2 shifts a downward by b*(4/3)*ln(1000). No clinical endpoint, death probability or vehicle shielding is calculated here. The prompt's detailed injury-dose thresholds were not verified in a primary source and are not adopted as policy.

AS 3959 exposure-band names are descriptive construction vocabulary, not route-admission or vehicle-tenability limits. Existing mission peak and dose caps are unchanged. Thermal thresholds cannot substitute for smoke, convection, embers or occupant conditions. The quoted passenger-vehicle burnover numbers were not independently located in their primary report and are not used to infer a travel allowance.

## Physics comparison limits

The full source ledger separates author measurements, idealized model values, synthesis quotations, missing source values and incomparable geometry. The Morandini comparison cannot use shrub height as flame height, plot width as luminous front width, or ground receivers in place of the actual sensor geometry. Cohen's ideal-panel model values are not measured fluxes. Its experimental ignition findings do not support the prompt's only-contact assertion. Published model consistency does not validate a real fire or evacuation.

| Law | Emitting geometry | Receiver | Present-fire scope |
|---|---|---|---|
| Frozen v1 | Uniform horizontal finite-cell isotropic source sheet | Common upward receiving plane | Scalar maximum-remaining activity enclosure |
| Prototype v2 | Polygonal leading/trailing solid-flame panels | Per-panel worst orientation or specified normal | Explicit past per-cell phases required |

Routing replay, the constraint ablation, complete copied-checker regression, binding maps and complete-request cost study remain NOT_RUN behind the empirical gate. No universal speedup, continuous-road physical accuracy, field validation or deployment readiness is claimed.
