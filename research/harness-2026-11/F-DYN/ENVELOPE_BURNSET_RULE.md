# `envelope_burnset` (adopted as `envelope_footprint`; renamed after Nora's PASS): ADOPTED (orchestrator decision, option A; amendment 2 to the withdrawn `envelope_sound`)

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

## How to read the blocked road share (definition; added after the owner's question; no rule change)

- **Unit.** A *road cell* is a 375 m cell of the KFS_01 grid crossed by at least one segment of a routed edge in the
  region's road graph. A road cell is *blocked* under `envelope_footprint` when it lies in the flame mask. Under the
  static law the flame mask is the final mapped burn set (∪ present fire) for the whole window [0, H). The routing
  packet blocks any edge with a segment in a flame cell. It is a count of cells, not of edges or of kilometres.
- **Uiseong-Andong**: 1,646 of 1,656 road cells (99.4%).
  - Edges: 43,512 of 43,826 directed edges touch the burn set.
  - Nodes: 22,995 of 23,158 lie in it.
- **Yeongdeok**: 1,115 of 1,590 road cells (70.1%).
  - Edges: 76,541 of 111,924 directed edges touch the burn set.
- **Why it is so high: graph extent.** The road graph is the c651 replay's recorded road set, a window around the
  fire: 73 × 65 cells for Uiseong and 73 × 65 for Yeongdeok. 4,729 of Uiseong's 4,745 window cells (99.7%) lie in
  the final burn set. For Yeongdeok it is 3,508 of 4,757 (73.7%).
- **Origins and destinations.**
  - Uiseong: all 84 origin entry nodes and all 30 destination nodes lie in the burn set.
  - Yeongdeok: 62 of 90 origins and 100 of 151 destinations.
- **Comparison: road cells burning at one instant** (`REACH_footprint_context.json`; packet law = birth to birth +
  T + Q, plus export present fire). Values are min / median / max over all starts.

  | Region | Instant | kriged_mean | firms_early |
  |---|---|---|---|
  | Uiseong | start | 0 / 0.3% / 6.2% | 0 / 0.3% / 8.6% |
  | Uiseong | +5 h | 0 / 0.4% / 8.3% | 0 / 0.4% / 6.2% |
  | Yeongdeok | start | 0 / 0 / 21.8% | 0 / 0 / 24.2% |
  | Yeongdeok | +5 h | 0 / 0 / 3.5% | 0 / 0 / 7.2% |

- **What the number says.** Nearly the whole Uiseong road window lies inside the area that eventually burned. A
  bound that makes every eventually-burned cell hazardous for the whole window, because these data cannot say *when*
  each cell burned, therefore blocks almost all of it.
- **What it does not say.** It does **not** say that 99% of the real roads were burning or impassable at any moment
  in March 2025: at any one instant the timing scenarios burn 0–9% of Uiseong road cells. It says nothing about roads
  outside the graph window.

## Nora: PASS WITH NOTES (ledger row 32); rename and label (label-only change, orchestrator)

- **Verdict.** Nora re-derived the burn set from the raw TOA, FIRMS and AHI membership: 16,176 cells (10,955
  kriged, 281 detection-only, 4,940 AHI-only), identical to ours.
  - The sample rebuild has flame equal to the burn set for the whole window, and nothing is cleared.
  - Blocked shares and the manifest reproduce.
- **Pixel-versus-cell pass:**
  - (i) Attribution can only add burn-set cells. All 7,573 cells touched by the nominal footprints of all 6,852 FIRMS
    detections lie inside the burn set.
  - (ii) Present fire and burned cells only add.
  - (iii) Radiation uses the writer's own centre model on the static mask.
  - (iv) The scalar self-check validates the writer path, **not** the override. Her direct packet-versus-burn-set
    comparison is the only check of the override, so the label keeps "single implementation, not independently
    checked".
- **Rename.** `envelope_footprint` → **`envelope_burnset`** ("footprint" could be confused with the pixel
  footprint). The arrays are identical. Files: `variants/envelope_burnset_{lo,hi}.npz`, `fdyn/burnset.py`, this
  file.
- **Label.** "SOUND RELATIVE TO THE FINAL MAPPED BURN SET (fire never mapped is outside it): lo = ignition, no cell
  cleared within the horizon; single implementation, not independently checked". The bare word "sound" is never
  used.
- **Manifest.** `MANIFEST_v3_3.json` (wfg.fdyn.manifest/4). `MANIFEST_v3_2.json` (sha d4dcf43b…) is kept and listed
  as superseded.
