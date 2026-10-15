# Verification that remains open

None of these items is closed by this integration, by the native campaign, or by numerical sampling.

## Radiation enclosure (open)

1. **Continuous-road dose enclosure.** The runtime whole-road check (`adaptive_checker.HybridChecker` and its supporting
   modules, for example `ivkernel.py`, `hybrid_radiation.py`, `radiation_bounds.py`, `road_exposure.py`) computes an outward enclosure of each member's integrated
   dose along the continuous road trajectory, including incurred dose and the destination dwell. No independently
   authored implementation has validated that enclosure. The independent checker's road samples (every 5 m and 1 s) are
   non-certifying: a sample inside the enclosure is a consistency check and cannot bound the dose between samples.
2. **Continuous-road peak bound.** The same applies to the peak flux upper bound along the road (limit 10 kW/m2). Sampled
   peaks below the runtime upper bound do not establish the maximum.
3. **Adaptive refinement path.** When the baseline radiation object is UNRESOLVED, the certificate comes from the
   adaptive fallback. Any audit must read the final adaptive enclosure, not the baseline field. The 16 m receiver span is
   the initial numerical spatial subdivision, not a physical receiver dimension.
4. **Road lower bounds used for the candidate's optimum and refusals.** The candidate's FULL_OPTIMUM and full-model
   refusal certificates rest on runtime road lower bounds (`road_bounds.py`, `zsweep.py`, LO/LO2/HI stages). They are not
   independently validated; independent optimality and refusal verdicts exist only in the cell-centre model.
5. **Numerical margins.** The independent checker distinguishes exact phases without margin from conservative phases
   with rounded-extinction and FFT margins. On the FUP1 reconciliation missions the runtime and independent cell-centre
   totals agreed to about 2.5e-4 kJ/m2 (router_metric_agreement AGREE); that is a reported tolerance on those missions,
   not exact agreement and not a general bound.

## Contract and representation (open, unchanged)

6. **Representation.** Missions were calibrated in the cell-centre model (X missions: budget max(1, 1.25 D), incurred
   0.3 B, so the comparator's runtime cell-centre total is 1.1 B when the floor is inactive; independent no-margin
   ratios are slightly below 1.1, for example 1.099884588), while publication is gated by the road model. ROAD_ONLY_ROUTE
   stays unresolved. Receiver geometry is the remaining identified major difference; exclusive causal attribution was
   not proved by a direct cell-centre re-evaluation.
7. **"Never accepts a road-inadmissible route"** holds only under the explicit assumption that the runtime road
   certificate is sound (items 1 to 4).
8. **Omitted-source audit.** The earlier omitted-source audit defect (double-counted incurred dose in that audit only)
   is preserved with its supplement; it is not re-run here.
9. **Physical validity** of either exposure model is not claimed. Resolution is model-relative benchmark resolution.

## What would close items 1 to 4

An independently authored continuous-road verifier (interval or rigorous enclosure arithmetic over the same source law,
receiver trajectory, scenarios and time window), run offline on every published journey and refusal, with its own
source custody. Until then, report CERTIFIED_ADMISSIBLE as a runtime certificate only.
