# Validation limitations and reviewer defense

> ## ⚠️ Session 5 correction (supersedes the Session-4 framing below)
>
> A mentor review invalidated two Session-4 claims. Both are corrected here
> and the stale text further down is kept only for provenance:
>
> 1. **The "multiplicative coupling, interaction ratio = 1.000" was
>    TAUTOLOGICAL** and is **retracted**. Rothermel R is separable in
>    moisture and wind, so that ratio is identically 1 for any separable
>    model — it carries no physical information. The honest measure is the
>    dimensional cross-partial ∂²R/∂M∂U; see
>    `docs/methodology/interaction.md`.
> 2. **The Session-4 "24 h burned area +25 %" was two errors cancelling**,
>    not validation. It used an *inflated* wind (10-m wind fed to Rothermel
>    without a Wind Adjustment Factor) plus disc-ignition area injection.
>    With the corrected midflame WAF (Andrews 2012) the surface model
>    **under-predicts the front by ~90 %** at every horizon (it cannot
>    capture the crown/spotting-driven run). The real target is **per-horizon
>    front accuracy**, reported honestly in
>    `docs/OVERNIGHT_REPORT_SESSION5.md` — the surface model, alone, does
>    not predict this event.
>
> Net honest status after Session 5: real terrain (SRTM); physically-correct
> midflame wind; literature-anchored Korean live fuel (surface bed
> provisional); and a spread model that is demonstrably **insufficient**
> for the Yeongdeok front without crown/spotting physics. The project's
> defensible contribution is the **future-front-aware routing spine**
> (`docs/figures/route_away_from_front.png`), which is correct *given* a
> front prediction, plus the corrected, honest physics.

---

This document is the frank, pre-emptive limitations section for the
writeup. It lists every challenge a forestry or CS reviewer could raise
about the Yeongdeok 2025 validation, and our honest response to each.

The guiding principle: **a modest, honestly-reported result is more
defensible than an impressive un-reproducible one.** Where the model is
weak, we say so and name a concrete fix.

---

## Challenge 1 — "The observed perimeter is not real ground truth."

**True.** The observed perimeter is APPROXIMATE — wind-aligned ellipses
reconstructed from public reporting (KFS preliminary ~3,800 ha + news
coverage of the 3–4 h coast-reaching timeline), not a KFS shapefile.
Every feature is tagged `provenance: "approximate, reconstructed from
public reporting"`.

**Response.** We never claim model-vs-truth. The IoU compares two
reconstructions. We quantify how much this matters: perturbing the
approximate perimeter (±20 % area, ±500 m centroid) gives the IoU ranges
in the table below. The fix is Round-2 ingestion of the real KFS
perimeter shapefile — the single highest-value next action.

| Horizon | IoU (baseline) | IoU range under perturbation |
|--------:|---------------:|------------------------------|
| 1 h | 0.48 | 0.00 – 0.50 (very fragile — fire is tiny) |
| 3 h | 0.21 | 0.15 – 0.26 |
| 6 h | 0.23 | 0.18 – 0.30 |
| 24 h | 0.15 | 0.11 – 0.19 (most robust) |

The 1 h IoU is fragile because the fire is small enough that a 500 m shift
de-overlaps the polygons entirely. The 24 h IoU is the most robust — which
is why we lead with the 24 h **burned-area** metric, not IoU.

---

## Challenge 2 — "The wind is synthetic."

**True.** No KMA API key was available this session, so the wind is a
reconstruction of the March 2025 양강지풍 episode from public KMA/news
reporting (sustained westerly 10–15 m/s, peak Mar 22–23). It is tagged
`synthetic=True`.

**Response.** The reconstruction captures the qualitative pattern but is
not the measured time series. We use the mean midflame wind (~4 m/s after
canopy reduction) over the wind-driven phase. Round 2 wires up
`load_aws_wind(source='kma')`. Wind is the single largest source of the
model's mid-horizon under-prediction (see Challenge 5).

---

## Challenge 3 — "The fuel raster is 100 % synthetic Korean Pinus."

**True.** The fuel-type raster is a uniform Korean Pinus fill; KFS 임상도
stand classification is Round 2.

**Response.** Yeongdeok is predominantly Pinus densiflora, so a uniform
Pinus assumption is a defensible first approximation for this site. It
would be wrong for mixed-stand regions (Central Mountain Belt), which we
explicitly do not validate.

---

## Challenge 4 — "The Korean Pinus fuel parameters are guessed."

**Partly true.** They are analog values adapted from Anderson FM10 with
adjustments for Pinus densiflora needle morphology and litter depth,
explicitly flagged as analog in `docs/methodology/korean_fuel_model.md`.

**Response.** They reproduce the right order of magnitude; absolute spread
rates may shift ±30 % with real Korean field-fuel-load data (KFRI / KIFM
literature, Round 2). The qualitative results (LFMC×wind coupling,
relative-to-baseline performance) are insensitive to these ±30 % shifts.

---

## Challenge 5 — "The model under-predicts the 3–6 h growth badly."

**True.** At 3 h the model predicts ~123 ha vs observed-approx ~600 ha;
at 6 h ~385 ha vs ~1,500 ha. The model loses to the isotropic baseline at
3 h and 6 h.

**Response.** This is genuine missing physics, not a discretisation
artifact (we fixed the discretisation warm-up — see Challenge 8). The real
event's explosive mid-game run was driven by **spotting and crown fire**
(ember showers igniting fuel hundreds of metres ahead) and **gusts to
25 m/s**, none of which a surface-spread CA with mean 4 m/s wind models.
Concrete fixes: (a) real KMA wind including gusts; (b) a spotting /
crown-fire ignition module (a documented Round-2 feature). We report this
gap openly rather than tuning parameters to mask it.

---

## Challenge 6 — "IoU ~0.15 at 24 h is low."

**True**, in absolute terms.

**Response.** Three points. (1) It is against an approximate perimeter, so
it measures reconstruction agreement, not skill against truth. (2) The
more defensible headline is the **24 h burned-area error of +25 %**
(predicted ~4,750 ha vs reported ~3,800 ha) — right order of magnitude.
(3) The model decisively beats the persistence null model (100×) and beats
the wind-ignorant isotropic baseline at the 24 h horizon, demonstrating
that the Rothermel+wind physics adds real skill over naive nulls.

---

## Challenge 7 — "Is the isotropic baseline a strawman?"

**Fair question.** We configured it fairly: it grows as a circle at the
**same** mean Rothermel head-fire rate the model uses, from the **same**
initial disc the model is given (`BaselineConfig.initial_radius_m`). It is
not handicapped. In fact it BEATS our model at 3 h and 6 h, which is why we
can't dismiss it — and we don't.

---

## Challenge 8 — "Did you tune the disc-ignition radius to get good numbers?"

**No, and we show the sensitivity.** The disc radius is set by a physics
rule — head-fire rate × a 15-min sub-grid establishment time ≈ 155 m
(7.6 ha) — independent of the observed perimeter. The resulting 7.6 ha is
much smaller than the observed +1 h size (~50 ha), so we are not
pre-loading observed area. We publish the full radius-sensitivity table
(`docs/methodology/spread_warmup.md`): larger radii would raise the
horizon-averaged IoU further, but we reject them because they would exceed
the observed early size (circular). The qualitative conclusion (disc ≫
point for early IoU) holds across the whole range.

---

## Challenge 9 — "Single validation site."

**True.** Only Yeongdeok 2025 is validated end-to-end. Uljin/Samcheok 2022
and Goseong 2019 have manifests but are not run (they need the same
real-data ingestion).

**Response.** Three-site validation is the documented Round-2 plan
(`docs/methodology/validation_strategy.md`). The infrastructure is
region-parameterised, so adding sites is data ingestion, not new code.

---

## Challenge 10 — "Can I reproduce these numbers?"

**Yes, deterministically.** The cellular automaton has no RNG in the
single-run path; `run_validation_with_baselines` is bit-for-bit
reproducible (asserted in `tests/test_validation_robustness.py`).
`scripts/run_yeongdeok_validation.py` regenerates the locked results JSON
from fixed inputs. The SRTM DEM is the only external dependency and is
auto-downloaded from a public archive.

---

## What is genuinely solid

- The Rothermel multi-class implementation reproduces Andrews 2018 Table 7
  reference values (tested).
- The real SRTM terrain is correct (East Sea at 0 m, Taebaek foothills to
  ~820 m, slopes to 43°).
- The wind is now physically correct: 10-m → midflame via the Andrews 2012
  Wind Adjustment Factor (closed Korean pine canopy WAF ≈ 0.10).
- The moisture–wind interaction is reported honestly as the dimensional
  ∂R/∂U (m/min per m/s), dry vs moist — NOT the retracted tautological
  ratio.
- The future-front-aware routing spine is correct given a front prediction
  (tested: it never enters the front when a safe route exists; returns "no
  safe route" when none does).
- Every synthetic / provisional / approximate input is labelled in code and docs.

## What is NOT solid (the honest headline)

- The **surface spread model under-predicts the Yeongdeok front by ~90 %**
  at every horizon once the wind is physically correct. It cannot, alone,
  predict this event — the real run was crown/spotting-driven. The
  prediction does not work yet; we say so plainly.

## What needs Round 2 before any operational claim

Real KFS perimeter, real KMA wind (incl. gusts), KFS 임상도 fuel, Korean
field fuel parameters, a spotting/crown-fire module, and multi-site
validation. Until then this is a **planning-stage prototype with a
defensible methodology**, not an operational forecast.
