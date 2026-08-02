# Per-region forward simulation — and what its envelope does not track

**Artifact:** `data/processed/forward_sim_regions.json`
**Script:** `scripts/run_forward_sim_region.py` · **Measured:** 2026-08-02
No new acquisition: every input was already present for all eight fires.

Each fire's hazard field is simulated with the target fire **held out of
training**, on a grid built from its own `fire_manifest.json` bbox, at the
Yeongdeok parameters (500 m, 4 × 3 h, advance 0.3, seed 20250603).

## ⚠ The envelope does not track burned area, and the bias flips sign

| region | reported burn | 12-h envelope | envelope / reported |
|---|---:|---:|---:|
| Yeongdeok 2025 | 3,800 ha | 27,900 ha | **7.34× over** |
| Uiseong-Andong 2025 | 45,000 ha | 2,375 ha | **0.05× — 19× under** |
| Uljin-Samcheok 2022 | 16,302 ha | 6,575 ha | 0.40× — 2.5× under |

The ranking inverts: the fire that burned **twelve times** more than Yeongdeok
produces an envelope **one eleventh** the size.

Part of this is expected and not a defect. The horizon is **12 hours from the
first overpass**, while these events burned for days, so under-prediction of
large multi-day fires is what a 12-hour forecast should do. What is not
explained by the horizon is Yeongdeok going the other way: 7.34× **over** its
own final burned area within 12 hours.

**So the bias is not a scale factor. It changes sign between regions, and no
normalisation can remove it** — dividing by reported area, envelope area or
detections would each impose a different arbitrary correction. The raw values
are reported and the envelope area travels as a column beside every
cross-region result.

### This is a limitation of the forward simulation, not of the routing

The router consumes whatever hazard field it is given and is correct with
respect to it. Nothing above says the routing is wrong; it says the hazard
fields differ in fidelity between regions, so a cross-region routing comparison
is partly a comparison of hazard fields. Keep the two statements apart.

## Boundary guard — both clear

| region | verdict | max edge p | grid |
|---|---|---:|---|
| Uiseong-Andong 2025 | **CLEAR** | 0.0248 (south) | 124 × 128 @ 500 m — 64 × 62 km |
| Uljin-Samcheok 2022 | **CLEAR** | 0.0000 | 135 × 92 @ 500 m — 46 × 68 km |

Uiseong-Andong was the region expected to fill its canvas at 45,000 ha. It did
not come close: the worst edge reads 0.0248 against a 0.3 threshold. **No bbox
needed widening, so the FIRMS manifest values were not departed from.**

## Core growth — Yeongdeok is the static one

Cells at p ≥ 0.5, t = 0 → 720 min:

| region | trajectory | growth |
|---|---|---:|
| Yeongdeok 2025 | 241 → 241 → 241 → 242 → 244 | **+1.2 %** |
| Uiseong-Andong 2025 | 53 → 63 → 71 → 86 → 95 | **+79 %** |
| Uljin-Samcheok 2022 | 103 → 149 → 199 → 249 → 263 | **+155 %** |

Round 2 recorded as a limitation that its routing results were "dominated by the
near-static ≥ 0.5 core, not front advance". That now looks like a **property of
Yeongdeok specifically** rather than of the method: the other two fronts do
advance, one of them by 155 %.

Whether that advance actually changes routing outcomes is not established here —
it is what STEP 2-3 tests.

## Reporting rules

* Never quote an envelope area without its 12-hour horizon.
* Never present the envelope as a burned-area prediction. It is a 12-hour
  ignition-probability forecast from the first overpass.
* Report envelope area beside any cross-region routing comparison; the fields
  differ by up to 12×.
* Yeongdeok's committed field used the larger fire-**acquisition** bbox
  (181 × 147, `docs/grid_extent.md`); these two use their fire's manifest bbox.
  Envelope area is physical and comparable provided nothing is clipped, which
  the boundary guard confirms.
