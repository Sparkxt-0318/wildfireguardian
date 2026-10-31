# Track 1A plan and source-reading notes

## Reading notes

Read README.md, PROJECT_STRUCTURE.md, FUTURE_EXTENSIONS.md, shared interfaces, the complete track prompt, bridge module contract and BASE_SETTINGS, heat classes, road_bounds.py and radiation_bounds.py, and both routing evidence READMEs and the request-window protocol before implementation. Integration is excluded by the graph, so these files were read directly after coverage checking. Parent graph generation was 2026-10-30T02:10:29Z; own graph is wfg-next-1a-20261030.

The v1 bridge is independent Bernoulli per-cell ignition and uniform sub-hour timing. It uses a finite horizontal isotropic source sheet, the exact solid angle divided by 4 pi, radiative fraction 0.30, and density fuel*consumed_fraction*heat/duration. The transfer is bounded by 1/2. With duration about 3970.46 seconds the global flux cap is about 0.703 kW/m2. This is a global finite-source sum cap because disjoint sheets subtend at most a hemisphere, not merely a single-cell maximum. Present fire is a scalar maximum-remaining enclosure, so inferring exact past ignition phases from it would be unjustified.

road_bounds.py splits complete driving, waiting and destination stay into spatial boxes and exact time intervals, sums directed source coefficients under exact represented source phases, and preserves unresolved when bounds do not decide. RadiationBounds provides exact rational activity and outward radial tile bounds. Its finite-source sheet law cannot be silently reused as a flame-front law. The adapter will preserve the source and contact functions and never claim new mathematical assurance by importing their names.

## Mathematical corrections to the prompt

- For tau(x)=x/R, the advancing front moves in +grad(tau), not -grad(tau). Both signs are documented, with propagation using the positive sign.
- A contour of a bilinear field is generally curved. Marching-squares straight segments are an explicit polygonal approximation, not an exact bilinear contour.
- A receiver normal aimed at an emitter centre does not maximize integrated flux for every rectangle. Use the exact polygon projected-solid-angle vector for the maximizing receiver where its hemisphere contains the emitter.
- A lower bound based on a source active at only one instant in an interval need not be positive. A rigorous general lower bound is zero.
- A fixed cutoff radius cannot imply a uniform relative error. The default sums all represented segments; optional truncation reports an absolute omitted bound.
- Medical dose values and construction bands are contextual references, not route thresholds or vehicle-tenability guarantees.

## Steps

1. Implement deterministic NumPy-only polygonal front geometry, Byram intensity, sourced wind tilt, exact rectangular view factors, flux, conservative monotone enclosures and dose integration.
2. Test closed forms, propagation, circular/isolated contours, unsupported cells, numerical enclosures and dose.
3. Produce reproducible source-backed physics tables and parameter sweeps before any routing experiment. Preserve failed comparisons; never tune to routing outcomes.
4. Only if physics gates pass, copy the required checker source with hashes and replay exact sealed Korean and Caldor journeys, then policy ablations under unchanged missions and resource controls. Incomplete certificates remain unresolved.
5. Publish evidence, scope limitations and source manifests, commit and report acceptance gates to the orchestrator.
