# `envelope_footprint`: ADOPTED (orchestrator decision, option A; amendment 2 to the withdrawn `envelope_sound`)

Adopted 2026-11-12, after Nora's FAIL on the soundness claim of `envelope_sound` (ledger row 28), with Iris's
conditions. **This rule is committed before any computation under it.** The word "sound" is not used for this
variant until Nora passes it.

## Why the lower bound is the event ignition time, on principle

A later per-cell lower bound needs evidence that the cell was **not** burning before some time. These data offer
only non-detections, and a non-detection fails for two independent reasons:

1. **Attribution (Nora).** A detection is assigned to a 375 m cell by the position of its centre. The pixel is
   375–800 m for VIIRS and 1 km for MODIS, so a neighbour's fire can produce the detection that "dates" a cell. That
   cell may have burned before the earlier clear view.
2. **Omission (Iris).** Even with perfect attribution, a clear-sky non-detection does not prove no fire: small or
   cool fire, canopy, smoke and thin cloud can all hide it.

A footprint-aware attribution cannot repair point 1 with these data. FIRMS VIIRS footprints in the window are
0.32–0.47 km, and **0 of 6,104** detections have a nominal footprint wholly inside one 375 m cell. It does not
address point 2 at all.

## Rule

- **Burn set.** The final mapped burn set, as before: finite kriged TOA, any FIRMS detection in the cell, or inside
  a firing AHI pixel's buffered set. That is 16,176 cells.
- **Hazard law, fixed for every start and horizon.** Every burn-set cell, together with every cell that is present
  fire in the export at the start, is **actively burning for the whole window [0, H)**.
  - **No cell is ever marked clear inside the horizon.** That covers cells the export lists as burned or burned out
    at the start, and present-fire cells after the writer's `remaining` time. Both clearings rest on the kriged
    timing and on the placeholder burning duration, so they are not established for any cell (Iris's condition).
  - The law uses **no satellite or kriged timing**.
- **Implementation.** This is in F-DYN code only; the writer is not modified.
  - The F-DYN per-cell path (`_packet_child.py`, `rebuild_members`) writes one interval [0, H) whose flame mask is
    the burn set ∪ the export's present fire, and computes flux from that mask with the writer's own radiation
    model.
  - The ignition schedule passed to the writer is unchanged (lo = 0, hi beyond the horizon, export-burned cells
    skipped). That keeps the writer's own checks valid. Members record ignition times as planned, with extinction at
    infinity.
  - The self-check that the re-implemented loop reproduces the writer's scalar members stays in force.
- **Label.** "BOUND RELATIVE TO THE FINAL MAPPED BURN SET (lo = ignition; no cell cleared within the horizon); says
  nothing about fire outside the mapped burn set; single implementation, not independently checked". The word
  "sound" is used only after Nora passes it.
- **Quantization.** v3.1. Only 0 and H appear, both exact.

## What is reported

- **Blocked road share** per region-start. Under this law the blocked set is the burn set ∪ present fire, so it is
  nearly constant across starts.
- **Per region-start, from Richard's routing field:**
  - the number of origins that still have a checked route under the envelope;
  - the number whose deadline is unchanged from the other rungs.

  These are the decisions that do not depend on fire timing at all, which is the finding.
- **Confirmed-clear counts** (1,575 of 3,228 detected cells): a reported data finding, not a routing input.

## Order of work

1. This commit: the rule.
2. Code: the variant npz (lo = 0 and hi = 10^6 h on the burn set, `timestamp_exact` = true, plus the burn-set mask
   for the static law); the `envelope_footprint` path in `_packet_child.py`; and tests.
3. Sample build plus the blocked road share.
4. A new manifest version (`MANIFEST_v3_2.json`) with `envelope_footprint` in place of `envelope_sound`.
   `MANIFEST_v3_1.json` is not edited.
5. Send to Nora as a delta, with a request to run the pixel-versus-cell argument once against every remaining
   assumption. Richard holds until she passes; then Richard scores and Thomas certifies.
