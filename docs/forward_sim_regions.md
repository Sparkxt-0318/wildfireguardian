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

## The simulation canvas was extended southward — and the fire did not change

Both new regions' ignition points sit near the southern edge of their manifest
bbox, so an ignition-centred walk bbox had no southern clearance: Uiseong-Andong
+0.00 km, Uljin-Samcheok **−4.44 km**, i.e. its routing extent fell *outside*
its own hazard grid, where nodes read p = 0 and every origin looks safe. That is
an optimistic bias, so the canvas was extended rather than the bbox moved or
clipped — moving it north would sample away from the fire, clipping it would
change the density denominator, and extending biases nothing.

| region | manifest bbox | south extension | grid before → after |
|---|---|---:|---|
| Uiseong-Andong 2025 | (128.40, 36.20, 129.10, 36.75) | **0.05° = 5.55 km** | 124 × 128 → **135 × 128** (62 → 68 km tall) |
| Uljin-Samcheok 2022 | (129.10, 36.85, 129.60, 37.45) | **0.09° = 5.55 km** | 135 × 92 → **155 × 92** (68 → 78 km tall) |

Recorded as `grid.simulation_bbox_extension` in `config/default.yaml`, per region
and per edge, so the canvas is readable without running anything.
`fire_manifest.json` is the **acquisition** record and was not edited.

### The envelope is bit-identical before and after

| region | envelope area (ha) | cells ≥ 0.5 | p ≥ 0.5 extent |
|---|---|---|---|
| Uiseong-Andong | 1325 / 1575 / 1775 / 2150 / 2375 — **identical** | 53 / 63 / 71 / 86 / 95 — **identical** | **identical** |
| Uljin-Samcheok | 2575 / 3725 / 4975 / 6225 / 6575 — **identical** | 103 / 149 / 199 / 249 / 263 — **identical** | **identical** |

**Nothing was being clipped.** The extension bought clearance for the *routing*
extent, not room for the fire. This matters for the section above: the finding
that the envelope does not track burned area is **not** a canvas artifact, and
the 2,375 ha and 6,575 ha figures were not under-reported by truncation.

Uiseong-Andong's worst southern edge did fall from 0.0248 to 0.0000, so a faint
southern tail below the 0.3 threshold now sits inside the canvas — too weak to
move the envelope, and now no longer touching an edge at all.

### ⚠ Yeongdeok is not extended — a deliberate asymmetry

Yeongdeok's grid, envelope and walk bbox stay exactly as committed. Extending it
would change the committed field and break continuity with every 439/459 figure
the submission cites. So two regions sit on a manifest bbox + a stated southern
extension, and one sits on the fire-acquisition bbox with no extension. The
canvases are not built by one rule; the per-region parameters say so explicitly.

## Boundary guard — both clear

Values are for the **extended** canvas (the pre-extension run was also clear):

| region | verdict | max edge p | grid |
|---|---|---:|---|
| Uiseong-Andong 2025 | **CLEAR** | 0.0000 (was 0.0248 pre-extension) | 135 × 128 @ 500 m — 64 × 68 km |
| Uljin-Samcheok 2022 | **CLEAR** | 0.0000 | 155 × 92 @ 500 m — 46 × 78 km |

Uiseong-Andong was the region expected to fill its canvas at 45,000 ha. It did
not come close: the worst edge reads 0.0248 against a 0.3 threshold. **No bbox
needed widening, so the FIRMS manifest values were not departed from.**

## Core growth — Yeongdeok is the static one

> ⚠ **영덕 행은 제출 시점 기록입니다.** 241 → 244 (+1.2 %) 는 되돌려진 실행의
> 위험면(`routing_demo.npz`) 위에서 측정된 값입니다. **정본 위험면 위 재산출값은
> 249 → 1,036 셀, 성장 +316.1 %** 이며, 「준정적 핵심」이라는 기술은 화재의 성질이
> 아니라 그 위험면의 성질이었습니다 ([`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §2-A).
> 나머지 두 지역 행은 각자의 위험면에서 측정된 값으로 영향받지 않습니다.
> 수치를 지우지 않는 것은 이것이 그 실행의 기록이기 때문입니다.

Cells at p ≥ 0.5, t = 0 → 720 min:

| region | trajectory | growth |
|---|---|---:|
| Yeongdeok 2025 ⚠ | 241 → 241 → 241 → 242 → 244 | **+1.2 %** ⚠ |
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
