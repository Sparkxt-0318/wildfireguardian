# Sound envelope variant and confirmed-clear criterion (fixed before computing)

Orchestrator and Iris soundness correction, 2026-11-12.

**The problem.** Non-detection is not absence of fire. The FIRMS "bracket start" (the previous overpass with any
detection in the grid) is **not** a lower bound on arrival. So `firms_early` and `envelope` are relabelled
"bracket-start, not a lower bound".

This file defines the confirmed-clear criterion and `envelope_sound`. Both are committed before any count or packet
is computed.

## 1. Confirmed-clear view of a cell at a polar overpass t_p

A polar overpass (from the FIRMS pass list, exact times) is a **confirmed-clear view** of a 375 m cell iff **all**
of the following hold:

1. **Instrument: VIIRS** (S-NPP or NOAA-20; 375 m I-band). MODIS (1 km) passes never count as a confirmed-clear view
   of a 375 m cell.
2. **AHI cloud-free.** t_p lies inside AHI observation coverage (2025-03-24 06:00 – 03-25 17:57:30 UTC). At the AHI
   scan nearest t_p (within 2.5 min), the cell's AHI pixel (nearest parallax-corrected centre, `ahi_membership.json`)
   **and all its neighbours** (line and column ±1) have **B14 ≥ 265 K** (no cold cloud) and B07 is not saturated.
3. **No detection near the cell in that pass:** no detection within 750 m of the cell centre (VIIRS off-nadir
   footprint).

Not testable, and stated with every count:

- thick smoke over the cell (smoke is warm at 11 µm and passes the cloud test);
- warm low cloud;
- fire below the VIIRS detection threshold (small or cool fire);
- day/night sensitivity: night passes are more sensitive, but day passes are not excluded.

Outside AHI coverage, no view is confirmed clear.

## 2. `envelope_sound` (routing envelope; conservative by construction)

For each cell that ever burns (finite kriged TOA, or any FIRMS detection, or inside a firing AHI pixel's buffered
set), at a start h:

- **lo_sound** = the latest confirmed-clear view of that cell before its first polar detection (or, if never detected,
  the latest confirmed-clear view at all). **If there is none, it is the event's ignition time**, t0 = 2025-03-22
  02:24 UTC (0 h).
- **End of burning = still burning at the horizon end.**
  - A sound per-cell **upper bound on arrival does not exist** in these data. Detections are pixel-level (VIIRS
    375–800 m off-nadir, MODIS 1 km, AHI 2 km) and prove fire **somewhere in the footprint**, not in the 375 m cell.
  - Since burning ends at arrival + T, any finite hi that is not a sound upper bound can end burning too early, which
    is anti-conservative.
  - So the end is set beyond the horizon: the cell burns on [max(lo_sound − h, 0), H).
- **Present fire and burned cells at the start** stay as in the recorded or synthetic export, which is the writer's
  fixed law. Those cells are not re-ignited. Their own extinction follows the writer's present-fire enclosure. This
  is a stated limit: the export's burned state comes from the kriged field.
- **Built** with the per-cell-law path (envelope packets): `hi_rel` is set to H. The kit's independent checker does
  not apply, so results are labelled "single implementation, not independently checked".

**Expected outcome**, stated in advance: most footprint cells that have not burned by the start will be blocked from
t = 0 to H. If so, that **is** the honest conservative envelope and is reported as such, with the fraction of road
cells blocked per packet.

## 3. Reported counts (computed after this commit)

- **Per detected cell:** confirmed-clear previous view (yes/no), overall and per built packet.
- **Per packet:** cells blocked for the whole horizon, road cells blocked, and the median blocked fraction of the
  horizon over road cells.

## 4. Scoring set

`envelope_sound` is **added** to the scoring set, by this rule, before any deadline is computed on it. The build
criterion union is re-evaluated with it (and with `ahi_bounded` once Nora passes the AHI rule). Starts that become
built are recorded, and every start is reported as before.

## Amendment 1 (one stated change; made before any packet or deadline used the variant)

**Error in §2.** For never-detected cells, "the latest confirmed-clear view at all" is **not** a lower bound. A clear
non-detection at t_p means either the fire had not yet arrived, or it had **already burned out**. Without a later
detection the second case cannot be excluded.

- **Detected cells:** the bound holds. A cell first detected burning at t_d cannot have burned out before an earlier
  clear view t_p < t_d (one burn per cell), apart from the untestable sub-threshold case.
- **Corrected rule:** lo_sound = the latest confirmed-clear VIIRS view **before the first detection** for detected
  cells. For **never-detected cells, lo_sound = the ignition time (0 h)**.

The first computation (1.2 s, counts only, no packet, no deadline) used the erroneous clause. It is superseded and
not reported.

## Status: WITHDRAWN as a bound (Nora FAIL on the soundness claim, ledger row 28; orchestrator checkpoint)

**What passes.** The counts, the commit order, amendment 1 and the bracket-start relabels all pass. The claim
**"sound" fails**.

**The hole.** For a detected cell, the rule takes the first detection as fire *in that 375 m cell*. In fact a
detection is attributed by the position of its centre, and the pixel is 375–800 m for VIIRS and 1 km for MODIS. A
neighbour's fire can cause it. The cell may then have burned out before the clear view t_p, so lo = t_p is above its
true arrival. This is the same footprint argument §2 uses against a finite hi.

**Exposure, among the 2,662 cells with lo > 0:**

- 400 are anchored by MODIS alone;
- 397 have a kriged central arrival earlier than lo (299 by more than 1 h);
- 1,401 have an adjacent cell detected before lo.

**Consequences:**

- `envelope_sound` is withdrawn as a bound as of this checkpoint.
- The pinned `MANIFEST_v3_1.json` (sha 1c2e73db…) is **not edited**. Its `soundness` string for the 122
  `envelope_sound` entries is superseded by this section. `fdyn/manifest.py` and `fdyn/_packet_child.py` now carry
  the withdrawn label for any future build or manifest.
- Nothing has been scored on it.
- The name "sound" is used for nothing until a rebuilt variant passes.

A fix is proposed in `ENVELOPE_FOOTPRINT_RULE.md`. It is not yet adopted.
