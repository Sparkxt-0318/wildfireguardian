# PROPOSED: `envelope_footprint`, replacing the withdrawn `envelope_sound` (not adopted; no computation under it)

Status: **proposal to Iris and the orchestrator**, after Nora's FAIL on the soundness claim of `envelope_sound`
(ledger row 28). Nothing is built, and the word "sound" is not used, until the variant is adopted, built and passed
by Nora.

## Rule

For every cell in the burn set (finite kriged TOA, any FIRMS detection, or inside a firing AHI pixel's buffered set,
the same set as before):

- **lo = event ignition time t0** (0 h) for **every** cell. Satellite non-detections are not used at all.
- **hi = beyond the horizon** (unchanged). Burning lasts from max(t0 − h, 0) to H.
- **Present fire and burned cells at a start** stay as in the recorded or synthetic export (the writer's fixed law),
  unchanged. This is still a stated limit: the export's burned state comes from the kriged field.
- **Per-cell law path** as before: `hi_rel` = H, with no independent checker. Labelled "single implementation, not
  independently checked".
- **Quantization: v3.1.** lo = 0 and hi = 10^6 h are exact.

**Meaning.** Every cell that burns at any time in the event is treated as hazardous from the start of the window to
its end, unless the export already has it burned at that start. This is the only per-cell lower bound these data
support. It uses no satellite timing, so no detection-to-cell attribution question arises.

## Cost, measured on the existing `envelope_sound_lo` (descriptive; no packet, reach or deadline)

- **Cells that change:** only the 2,662 cells that had lo > 0. 13,514 of 16,176 are already at t0.
- **Their lo moves to t0, from a median of 85.7 h after t0** (p10 63.4 h, p90 87.4 h, max 87.4 h, which is
  25 Mar about 14:00–16:00 UTC).
- **For any start before about 25 Mar 16 UTC**, these cells burn from t = 0 of the window instead of from their
  confirmed-clear view. For later starts nothing changes, because their lo was already before the start.
- **Expected effect on reach:** the blocked fraction of road cells rises from the current 46–75%, mainly for
  23–25 Mar starts. This is measured only after adoption, with the reach table, and is not used to choose the rule.

## Would footprint-aware attribution give a tighter bound? No

The alternative was to keep a confirmed-clear lo only where the detection's pixel footprint lies wholly inside the
cell, using VIIRS 375 m only.

- The FIRMS VIIRS footprints in the event window (6,104 detections, 21–28 Mar) are **0.32–0.47 km** on scan and
  track (median 0.46 and 0.47 km).
- With the nominal footprint centred on the detection, **0 of 6,104** lie wholly inside one 375 m grid cell.
- So the footprint condition is never met, and footprint-aware attribution yields **no cell** with lo > t0.
- A sub-cell-accurate attribution would need finer geolocation than FIRMS gives (pixel footprint and geolocation
  error about 375 m or more). That is not available here.

## Recommendation

Adopt `envelope_footprint` as defined above. It is the honest floor of the ladder: with these sensors, a per-cell
bound says that the final burn footprint is hazardous for the whole horizon. The confirmed-clear counts (1,575 of
3,228) remain a reported finding about how often a clear view exists, not a routing input.

## If adopted: order of work

1. Commit this file as adopted, renaming PROPOSED to ADOPTED. No other change.
2. Write `envelope_footprint_{lo,hi}.npz`: lo = 0 on the burn set, hi = 10^6 h, with timestamp_exact = true.
3. Run the reach table and the blocked fractions.
4. Write a new manifest version adding `envelope_footprint` in place of `envelope_sound`. `MANIFEST_v3_1.json` is
   not edited.
5. Send to Nora.
