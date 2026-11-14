# Himawari-9 AHI fire-detection rule for KFS_01 (fixed before any arrival is computed from it)

**Owner and review.** Owner: Leo (orchestrator decision, 2026-11-12). Review: Elena, who consumes the output for her
raw-bracket arm, plus Iris and Nora. **Nothing is tuned after the validation below is seen.** If the rule fails
validation, it is changed **once**, for a stated reason, and validated again.

**Data.** Daniel, `daniel/data-fetch-2` (PR #109, passed by Hannah): 448 AHI pixels inside the KFS_01 export grid,
B07 (3.9 µm) and B14 (11.2 µm) brightness temperatures, nominal 2.5-min cadence.

| File | Window (UTC) | Role |
|---|---|---|
| `kfs01_ahi_20250324T18_20250325T18.npz` (SHA 63dfc2b6…) | 24 Mar 18:00 – 25 Mar 17:57:30 | fire period |
| `kfs01_ahi_20250320T06_20250320T18.npz` (675d5b43…) | 20 Mar 06:00 – 17:57:30 | pre-ignition daytime **baseline** |
| `kfs01_ahi_20250324T06_20250324T18.npz` (f0ac0e5c…) | 24 Mar 06:00 – 17:57:30 | same-hour window, fire already active (validation only) |
| pre-ignition night window, 21 Mar 18:00 – 22 Mar 02:00 | (requested) | night **baseline** |

Ignition was 2025-03-22 02:24 UTC.

## Rule

1. **Baseline per pixel and time-of-day slot.** For pixel p and scan time t, the baseline is the scan at the same UTC
   time of day (nearest scan) in the pre-ignition windows: `B07_base(p, slot)` and `dT_base(p, slot)`, where
   dT = B07 − B14.
   - Daytime slots (06:00–17:57:30 UTC) use 20 Mar.
   - Night slots (18:00–01:57:30 UTC) use 21–22 Mar when delivered.
   - Night slots before that delivery, and 02:00–05:57:30 UTC (no pre-ignition data), use the per-pixel median over
     the pre-ignition windows that exist. That is a weaker baseline, and every result from those slots is flagged
     `weak_baseline`.
2. **Fire at (p, t)** if either:
   - **(a)** `dT(p, t) − dT_base(p, slot) ≥ 15 K` **and** `B07(p, t) − B07_base(p, slot) ≥ 10 K`; or
   - **(b)** `B07(p, t) ≥ 399.9 K` (band-7 saturation). Saturated scans count as fire but carry no intensity
     information, and dT is not used for them.
3. **Persistence.** The first-fire time t_f(p) is the first scan t at which (p, t) is fire **and** at least one of
   the next two scans is also fire (2 of 3). Isolated single-scan flags are not fire.
4. **Bracket per pixel:** (t_prev, t_f], where t_prev is the scan before t_f. `scan_start_utc` is the nominal start,
   so a 2.5-min timing tolerance applies.

## Reading (conservative, fixed)

- **Spatial meaning.** A firing pixel means **fire within about 2 km by t_f**, somewhere in the pixel footprint
  (about 2 × 2 km nominal, larger off-nadir). It is **never** a 375 m cell's own arrival time.
  - Cells are assigned to their nearest AHI pixel centre (EPSG:5179).
- **F-DYN variant `ahi_bounded`.** For a cell inside the kriged footprint whose pixel fires:
  `arrival_hi = min(firms hi, t_f(pixel))` and `arrival_lo = min(firms lo, t_prev(pixel))`. Other cells are unchanged.
  - This treats every burned cell in a firing pixel as possibly burning by t_f. That is **conservative** (earlier),
    not an estimate.
- **Parallax and terrain.** Neither is corrected. Himawari-9 is at 140.7°E, and its view zenith over the area is about
  45°. A flame or plume source 0.5–1 km above the ellipsoid shifts by about 0.5–1 km, mostly toward the
  north-north-west. Terrain of 0–900 m adds up to about 0.9 km. **Pixel-to-cell assignment can therefore be off by
  about one pixel half-width**, and the 2 km reading already absorbs this.
- **Not modelled.** Cloud and smoke can mask fire, which makes t_f late. Thick smoke can also suppress B07.

## Validation (computed once, reported in full, no tuning afterwards)

Polar detections are VIIRS S-NPP, VIIRS NOAA-20 and MODIS from FIRMS; the rule never sees them. A polar detection
belongs to the AHI pixel nearest to it.

| Check | Measure |
|---|---|
| **V1 consistency** | For pixels with ≥1 polar detection inside the AHI window: share where `t_f ≤ first polar detection + 10 min` (caught in time), share where t_f is earlier than the polar detection (and by how much: median and IQR), and share never flagged (missed). |
| **V2 false alarm, pre-ignition** | Pixel-scans flagged fire on 20 Mar 06–18 UTC. The baseline window itself, so this is a self-consistency check only. Reported, not a pass/fail. |
| **V3 false alarm, far from fire** | Share of pixel-hours flagged fire, in the 24 Mar 06–18 and 25 Mar windows, in pixels with no polar detection within 5 km at any time 22–28 Mar. |
| **V4 timing sanity** | Hourly count of firing pixels, plotted beside the polar overpass counts. |

**Pass criteria, fixed now:** V1 caught-in-time ≥ 80% of polar-detected pixels, **and** V3 false-alarm pixel-hours ≤
2%. Fail on either → one stated change, then re-validate.

**Outputs:**
- `ahi_first_fire.npz`: per pixel t_f, t_prev, flags, `weak_baseline`.
- `variants/ahi_bounded.npz`: lo and hi rasters.
- `AHI_VALIDATION.json`.

The 06–10 UTC reading of the coastal run is **not reported as a finding** until this rule passes validation.

## Amendment 1 (Elena's and Iris's reviews; committed before any computation)

This amendment supersedes the corresponding parts above.

1. **Baseline.** Per pixel and time-of-day slot: the **median over all pre-ignition scans at that slot**.
   - Windows: 20 Mar 06:00–18:00, 20 Mar 18:00 – 21 Mar 06:00, and 21 Mar 18:00 – 22 Mar 02:00 UTC (Daniel,
     `5f384555`: SHA 8942f1ee…, 88179935…; plus 675d5b43…).
   - Scans failing the cloud test (item 2) are excluded from the median.
   - Slots with fewer than 2 valid baseline scans are flagged `weak_baseline`. The 02:00–06:00 UTC slots have one
     pre-ignition night (20–21 Mar).
2. **Cold-cloud test.** A scan with `B14 < 265 K` at a pixel is **unknown**: neither fire nor a valid non-detection.
   Saturated B07 overrides it (fire).
3. **Terrain parallax** is corrected deterministically before any pixel-to-cell assignment.
   - Each pixel centre is moved toward the sub-satellite point (Himawari-9 at 140.7°E, 0°N) by z·tan(VZA). z is the
     GLO-30 surface elevation at the pixel centre (F-C1 surface); VZA is the satellite view zenith at the pixel.
   - Plume-height parallax stays uncorrected and is stated: about 0.5–1 km for a 0.5–1 km source height.
4. **Lower bound.** t_lo = the **last valid scan** (not cloud-masked, not missing) before t_f.
   - It means only "no *detectable* fire". It is **not a sound lower bound on arrival**, and is reported as such.
   - Elena's likelihood uses only the upper side (min τ ≤ t_f) unless a detection-probability model is added.
5. **Outputs and meaning** (Iris and Elena):
   - **Pixel-level observation:** `ahi_first_fire.npz`, per pixel (t_lo, t_f], plus flags and the corrected centre.
     Its meaning is "the earliest arrival among this pixel's burned cells is ≤ t_f".
   - **Membership tables:** cell → pixel, nearest-centre after parallax correction; and pixel → cells within its
     footprint plus a 1 km buffer (point-spread function and residual parallax).
   - **`ahi_bounded` (F-DYN):** a **routing envelope only, labelled "not for training"**. Every burned cell of a firing
     pixel gets min(firms hi, t_f). It can only move fire earlier, which makes deadlines conservative. It is not a
     per-cell bracket.
   - **Timing statements (F-C1b):** the AHI time bounds a quantity only when that quantity is a minimum over a set
     containing **all** burned cells of the pixel (buffered set). Otherwise the FIRMS bracket is kept.
6. **Validation additions** (criteria unchanged otherwise, still fixed in advance):
   - V1 is scored and reported **by fire intensity class**, using the FIRMS FRP of the cell's first polar detection
     (FRP < 10, 10–50, ≥ 50 MW). The pass criterion (≥ 80% caught within +10 min) applies to the **≥ 50 MW** class,
     the fires a geostationary sensor can plausibly see. Other classes are reported.
   - V3 is split **day and night** (06:00–09:50 UTC on 25 Mar counts as day).
   - **V5, point-spread bleed:** the false-alarm share in pixels **adjacent** to a firing pixel that have no polar
     detection within their own buffered footprint during 24–26 Mar. Reported; no pass criterion.
