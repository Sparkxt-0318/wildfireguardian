# Known-failure diagnosis and hybrid correction

All cases in this document are **development evidence** from the previously completed practical checker experiment. Their outcomes were already known. A fresh protocol and independent review must establish any confirmatory benefit. Original strong and practical implementations/results are preserved; no source history, probability, combustion parameter, route or exposure budget is changed.

## Cause classification

The remaining incident dose straddle and three control regressions were consequences of deliberately broad spatial enclosures, not demonstrated source/event or rounding defects. A 375 m cell split into 8×8 radial tiles still has 46.875 m tiles, much larger than the 5 m emission height and some road-to-source gaps. The maximum kernel over a tile multiplied by its entire area overstates flux near its boundary; the minimum kernel multiplied by that area understates it. Receiver refinement alone cannot remove this source-area uncertainty, particularly during fixed-position dwell. This valid conservatism lost practical resolution.

Analytic translated rectangles address the source-area integration directly while retaining entire receiver boxes. Exact phase-overlap integration, incurred exposure and peak/dose units are inherited unchanged. No event is shifted, no simultaneous source is omitted, and no threshold tolerance enlarges a budget. Source birth/burnout handling was not identified as the cause of these four precision failures. Outward floating/rational arithmetic still contributes small numerical widths; it is not the hundreds-of-kJ width seen in the practical near-source cases.

## Quantified before and after

Intervals are kJ/m² including the same incurred dose, full motion, waits and 120-second dwell where specified. In the incident row, the reported interval belongs to member 2. Duplicate deterministic control members have identical intervals. Original strong comparator intervals are retained from its full completed bounds; its incident mission check exhausted the primary cap.

| Case | Original strong | Practical radial | Hybrid | Practical → hybrid dose width |
|---|---|---|---|---:|
| 20220304T060000Z_confirmation-road-2_depart60 | UNRESOLVED | UNRESOLVED [20.127810, 746.977752] | DEFINITE_REJECT [111.497580, 120.360440] | 726.849942 → 8.862859 |
| control_near_interior_peak | CERTIFIED_ADMISSIBLE [35.034079, 39.955713] | UNRESOLVED [6.231439, 163.238916] | CERTIFIED_ADMISSIBLE [35.848903, 39.122703] | 157.007477 → 3.273800 |
| control_overlapping_source_heat | DEFINITE_REJECT [313.551557, 321.403137] | UNRESOLVED [36.880456, 1333.618396] | DEFINITE_REJECT [314.828689, 320.050865] | 1296.737940 → 5.222176 |
| control_completed_threshold_straddle | CERTIFIED_ADMISSIBLE [99.997684, 99.998345] | UNRESOLVED [99.992266, 100.007250] | CERTIFIED_ADMISSIBLE [99.996700, 99.999342] | 0.014984 → 0.002642 |

**Remaining incident, 06 UTC road-2 depart60:** complete practical bounds [20.127810,746.977752] straddled the unchanged 100 budget after two passes. The hybrid gives [111.497580,120.360440], reducing width 726.849942 to 8.862859 kJ/m² (about 82-fold). Its lower bound exceeds 100, so the fixed mission is rejected for cumulative exposure. This does not prove another route is unavailable. Radiation-only cold time was 8.923 s including preparation, versus the previous full practical mission record of 21.829 s; those timing scopes differ and are not a speed ratio. The first hybrid 16 m receiver pass sufficed, with 608 analytic source bounds, 3,621 new rational corners, 331,968 radial tile bounds and 231,016 active source-slab pairs. Event phases and all scenario histories are identical.

**Near interior peak:** the practical dose [6.231439,163.238916] could not accept the path although the original strong rectangle enclosure could. The hybrid [35.848903,39.122703] certifies under 100, and peak upper 2.168492 kW/m² stays below 10. The interior peak is enclosed analytically over the whole chord; no sampled endpoint peak decides the result. Source rectangle integration, rather than additional receiver-only sampling, supplies the missing precision.

**Overlapping active sources:** the original strong lower dose already proved failure. Practical lower 36.880456 was too weak, while upper 1333.618396 was too broad. Hybrid [314.828689,320.050865] restores a justified dose rejection. Overlap in time remains explicit and all sources retain their contribution. The fixed-position dwell is a major reason receiver subdivision could not cure the radial source bound.

**Completed threshold straddle:** practical [99.992266,100.007250] remained unresolved under the deliberately coarse, labelled one-level override. The hybrid retains that exact override and gives [99.996700,99.999342], so the upper bound stays below 100. Because this control has one explicitly ever-active source, the deterministic sparse-realization policy treats its distant rectangle analytically. Precision is recovered without changing incurred99.98, the source realization or the receiver override. The hybrid interval is still broader than the original strong interval [99.997684,99.998345]; no claim of uniformly tighter bounds is made.

## Every labelled control, including non-regressions

| Control | Original strong | Practical | Hybrid complete pipeline | Known hybrid cold s |
|---|---|---|---|---:|
| control_distant_wait_dwell | CERTIFIED_ADMISSIBLE | CERTIFIED_ADMISSIBLE | CERTIFIED_ADMISSIBLE | 0.087356 |
| control_near_interior_peak | CERTIFIED_ADMISSIBLE | UNRESOLVED | CERTIFIED_ADMISSIBLE | 0.137155 |
| control_overlapping_source_heat | DEFINITE_REJECT | UNRESOLVED | DEFINITE_REJECT | 0.307536 |
| control_unknown_source_support | UNRESOLVED | UNRESOLVED | UNRESOLVED | 0.001243 |
| control_budget_equality_no_activity | CERTIFIED_ADMISSIBLE | CERTIFIED_ADMISSIBLE | CERTIFIED_ADMISSIBLE | 0.005104 |
| control_completed_threshold_straddle | CERTIFIED_ADMISSIBLE | UNRESOLVED | CERTIFIED_ADMISSIBLE | 0.015475 |

The distant wait/dwell control was already admissible; it remains admissible with analytic sparse-source precision and fully charged waits/dwell. The equality/no-activity control retains exact incurred [100,100] and zero new heat; explicitly absent source phases avoid near-source tile work, rather than filling unknown observations. Unknown source support remains UNRESOLVED before full admissibility; tighter geometry cannot supply unavailable sources. These controls stay separate from incident forecast evidence.

Coordinator’s complete eighteen known **cold** wrapper regression reports four incident certificates, eight incident fixed-path rejections and no unresolved incident row; controls retain four certificates, one cumulative-dose rejection and one unknown-support unresolved row. Four targeted radiation-only warm checks also reproduce the same bounds/statuses while reusing completed immutable geometry. All known cases remain in the raw ledger, including negative/unsupported outcomes. This is development selection and regression evidence, not fresh acceptance or universal performance.

## Software issues versus representation limits

- No demonstrated correctness defect in the old practical spatial enclosure is used to explain its three control regressions or incident straddle. Intentional conservative bounds are kept as the weaker comparator.
- Independent review found an optional-keyword interface defect in the first new hybrid final guard: explicit `wall_s=None` or `deadline=None` could raise `float(None)` after completed checking. The exact initial module/hash and correction record are preserved; normalization now matches the inherited API. This was corrected before any fresh opening and changes no numerical enclosure or policy.
- An author peak-rejection assertion incorrectly expected a positive lower peak when the source first ignited inside a slab. The inherited lower peak deliberately considers definitely active sources at the slab’s left endpoint and can validly be zero. The test was corrected to start at known ignition; the failed assertion is retained. This weak lower bound remains a possible limitation for other peak thresholds, not a false-acceptance defect.
- Artificial reversed-enclosure fault injection is caught inside the inherited numerical pass and returns UNRESOLVED; the owning pipeline adds defensive API-boundary handling. No actual incompatible same-law intersection has been observed.

## Proof, cache and resource scope

The hybrid intersects compatible radial and rational-analytic enclosures of the same represented integral. Analytically selected sources use a coarse radial enclosure plus translated-rectangle integration; other near sources retain tiled radial bounds. Skipping the extra tiled bound for analytic sources means individual harmless member intervals can broaden relative to the practical checker, even when the binding near-source interval tightens. All sources are still represented, and every upper/lower inequality remains valid. No universal monotone-tightening claim is made.

Cache identity includes complete geometry/events/physics/support, all policy and analytic rounding settings, and explicit source absence. Combined coefficient entries are committed only after all selected analytic work and deadline checking succeed; a cap cannot store a radial-only shortcut for a later warm call. Rational corner cache may retain valid partial work of the same content. The unchanged shared 30-second mission cap, positive slab/corner work limits and final late-result guards retain UNRESOLVED when incomplete. Numeric cache bytes and shallow rational-container byte estimates are separate scopes; process RSS includes nested payloads and other retained worker state.

Author suite currently has 67 passing checks, including whole-box reference comparisons, phase/dose/threshold behavior, source/geometry/physics/support and all numerical-policy identity dependencies, immutable caller snapshots, explicit None compatibility, atomic cache on analytic caps, masks, arithmetic fault injection and deadline crossing. See HYBRID_RADIATION_SPEC.md and independent reviewer evidence for the full argument and boundaries.

## Conservation and physical assumptions

Baseline consumed energy remains 10 kg/m² ×18 MJ/kg ×0.1 =18 MJ/m². The 300 s phase gives 60 kW/m² HRR, radiative fraction0.3 gives 18 kW/m² radiant source density, and transmissivity remains1. Spatial bounds refine the same integral and cannot create or remove source energy. Initial known-burned activity, unknown current cold assumption, unknown future probability0.5, event timing, duration and finite independent scenarios are unchanged.

The source law remains constructed; endpoint-to-flame interpretation, missing forecast support, burning-phase observations, combustion calibration, dependence and physical road exposure are not validated by mathematical precision or faster checking. Fresh separately frozen confirmation is required before Stage2 acceptance. Original search TIMEOUTs remain unresolved and were not rerun; no default promotion, merge, push or deployment is authorized by this development result.
