# AHI detection: outputs and validation

**Rule:** `AHI_RULE.md` @469796e, amendment 1 @def5016. Both were fixed before computing, and the rule was run once
with no tuning. Code: `fdyn/ahi.py` (committed before running).

## Validation: PASS by the pre-fixed criteria, with stated caveats

**Criteria** (fixed in advance): V1 caught-within-10-min share ≥ 80% for FRP ≥ 50 MW, **and** V3 far-from-fire
false-alarm share ≤ 2%.

**V1, by FRP class.** Pixels are those with polar FIRMS detections inside the AHI window; "caught" means the AHI first
fire is no later than the first polar detection + 10 min.

| FRP class | Pixels | Caught in time | Missed | AHI earlier than polar, median (IQR) |
|---|---:|---:|---:|---|
| ≥ 50 MW | 34 | **34 (100%)** | 0 | 2.4 h (1.1–4.4) |
| 10–50 MW | 81 | 80 (98.8%) | 0 | 4.2 h (3.2–5.7) |
| < 10 MW | 136 | 121 (89.0%) | 9 | 10.1 h (7.6–10.8) |

**V2.** The rule applied to its own pre-ignition baseline windows flags 0 of 344,064 pixel-scans. This is a
self-consistency check only.

**V3, far-from-fire false alarms.** 77 pixels have no polar detection within 5 km during 22–28 Mar.

| Period | Flagged pixel-hours | Share |
|---|---:|---:|
| All | 52 / 2,849 | **1.83% (pass)** |
| **Day** | 52 / 1,386 | **3.75%: above 2%** |
| Night | 0 / 1,694 | 0% |

**V5, point-spread bleed.** **82 of 146** pixels next to a firing pixel are flagged, although they have no polar
detection within their own buffered footprint on 24–26 Mar. That is high: a pixel's t_f can come from a neighbour's
heat. Use the buffered membership (2 km disc) for any minimum constraint (Elena).

**Other properties:**

- **Weak baseline everywhere.** All 365 firing pixels are flagged `weak_baseline`: each time-of-day slot has a single
  pre-ignition day or night (fewer than 2 valid scans).
- **Left-censoring.** 62 pixels fire in the first scans of the 24 Mar 06 UTC window, because fire was already active
  on the 24th. Their t_f is an upper bound only and t_lo is empty.
- **Parallax.** The terrain parallax shift has median 217 m and max 808 m.
- **Saturation.** Band-7 saturation sets t_f for only 1 pixel.

## Coastal run: "AHI indicates" (not established; caveats above)

AHI first-fire times on 25 Mar cluster between **06:24 and 09:24 UTC (15:24–18:24 KST)**: 62, 38 and 76 pixels per
hour. A further 26 / 14 / 23 pixels follow from 09:24 to 12:24 UTC.

This is consistent with the documented accounts: 지품 smoke about 16:30 KST and flames 17:55 KST, 매정리 about
20:40 KST. It is consistent with MODIS 12:25 UTC, and many hours earlier than the kriged burst at 16:24 UTC.

Pixel-level meaning only: **"some burned cell within about 2 km had fire by t_f"**.

## Files

- `ahi_first_fire.npz`: per pixel t_f and t_lo (hours since t0 = 2025-03-22 02:24 UTC), flags, parallax-corrected
  centre (EPSG:5179), VZA and shift.
- `AHI_VALIDATION.json`: everything above.
- `ahi_membership.json`: cell→pixel (nearest) and pixel→cells (within 2 km).
- `ahi_bounded_{lo,hi}.npz`: routing envelopes, **NOT FOR TRAINING**.
