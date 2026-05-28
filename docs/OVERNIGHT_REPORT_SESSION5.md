# Overnight build session 5 — report (REFOCUS: fix the physics, build the spine)

Date: 2026-05-28. Branch: `claude/dreamy-knuth-NlgfH`.

A mentor review invalidated two Session-4 claims and refocused the project.
This session implemented the corrections and built the new core (the
routing spine). **Scientific honesty over impressiveness throughout** — the
headline finding is partly negative and reported as such.

---

## 0. Test count vs baseline

| | tests |
|---|---|
| Session 4 baseline | 228 |
| **Session 5** | **258** (+30; 0 regressions) |

New: `test_wind.py` (12), `test_interaction.py` (5), `test_future_front.py`
(9), `test_empirical_interaction.py` (6), plus smoke-tree import cases.
Removed: `test_lfmc_wind_decomposition.py` (5 — the retracted tautology).

```
$ python -m pytest tests/ -q
258 passed in ~4 s
```

---

## 1. WAF result: wind factor at Yeongdeok before vs after

**The root bug.** Rothermel's φ_w needs **midflame** wind; the code fed raw
10-m/station wind straight in. Fixed in `spread_model/wind.py` (Andrews
2012 RMRS-GTR-266 WAF).

- Korean pine closed-canopy WAF (sheltered; crown base 3.6–5.2 m) = **0.10**.
- Mar 22 mean 10-m wind 13.9 m/s → **midflame 1.39 m/s** (old ad-hoc ×0.30
  gave 4.17 m/s; raw-into-Rothermel gave the full 13.9).
- **Wind factor (1 + φ_w) at the 2025 condition:**
  - raw 10-m wind fed to Rothermel (the bug): **115×**
  - WAF-corrected midflame: **5.3×**

The previously-reported "wind-alone 12.76×" was itself an artifact of
treating 12 m/s as midflame; with realistic 10-m winds and the WAF, the
defensible wind factor is ~5×. Unsheltered WAF reproduces Andrews 2012
(fuel depth 1 ft → 0.36, tested).

## 2. Korean fuel parameters adopted

**Measured (cited):** foliar live moisture **119 %** (avg crown 105.3 %);
crown bulk density 0.29–0.47 kg/m³, crown base 3.6–5.2 m (Lee et al. 2018,
*J. Korean Soc. Forest Sci.* 107(4):412–421); stand-loading basis NIFoS
1,434-plot model (*Forests* 2022, 13(9):1372). → `live_moisture_default =
1.19`; crown structure → the canopy WAF.

**Provisional surface bed (flagged, NOT measured):** needle-litter load
0.7 kg/m², depth 0.08 m, SAV 6000 m⁻¹, dead m_x 0.30. Tagged `PROVISIONAL`
in code and `docs/methodology/korean_fuel_model.md`; the Korean papers give
*crown* fuel, not the ground litter bed the surface model needs.

## 3. Cross-partial (replaces the retracted ratio)

The Session-4 "multiplicative coupling, ratio = 1.000" was **tautological**:
Rothermel R = K·g(M)·f(U) is separable, so the four-corner ratio is
identically 1 for *any* separable model. **Retracted everywhere.**

Honest, dimensional measure (`spread_model/interaction.py`), Korean Pinus,
representative **midflame** wind 1.5 m/s:

- ∂R/∂U on **dry** fuel (dead 6 %) = **1.01 m/min per m/s**
- ∂R/∂U on **moist** fuel (dead 20 %) = **0.61 m/min per m/s**
- ∂²R/∂M∂U = **−2.01** (m/min per m/s per moisture-fraction) — drier fuel
  makes wind more dangerous.

**Separability note (the honest caveat):** the slope ratio
∂R/∂U(dry)/∂R/∂U(moist) = **1.6427, exactly constant across all U** (tested
to <1 %). So the cross-partial's sign is structurally guaranteed and the
ratio carries no information beyond g(M), f(U). The genuinely novel question
— does *real* spread exceed this separable baseline? — is scaffolded in
Deliverable 6. Figure: `docs/figures/interaction_fanning.png`.

## 4. Per-horizon front accuracy (the honest negative result)

Re-ran Yeongdeok 2025 with corrected WAF + real Korean fuel, 50 m cells
(needed so R·residence ≥ cell, else the slow front stalls — a resolution
requirement, documented). Front metrics added: fraction-of-observed
captured, front-position error (Hausdorff + mean boundary), area error.

| Horizon | pred ha | obs ha | area err | captured | IoU | front mean err |
|--------:|--------:|-------:|---------:|---------:|----:|---------------:|
| 1 h | 0 | 50 | −99% | 1% | 0.01 | 0.3 km |
| 3 h | 4 | 600 | −99% | 1% | 0.01 | 1.1 km |
| 6 h | 14 | 1500 | −99% | 1% | 0.01 | 1.7 km |
| 12 h | 68 | 2800 | −98% | 2% | 0.02 | 2.1 km |
| 24 h | 326 | 3800 | **−91%** | 9% | 0.09 | 2.1 km |

**The wind fix did NOT rescue the prediction — it made the (correct) wind
slower, so the surface model now under-predicts by ~90 %.** This is honest:
the real Yeongdeok run was crown/spotting-driven, which a Rothermel surface
model fundamentally cannot reproduce.

**Cancellation exposed (24 h area, with vs without disc ignition):**
both = **326 ha** (−91 %). Identical, because at the corrected slow rate the
principled disc radius is sub-cell. This proves the Session-4 "+25 %" was
the *inflated wind* (too-fast spread) plus *disc-injection* cancelling — not
validation. `data/processed/yeongdeok_2025_validation_results.json` stores
both runs.

## 5. The spine: route away from the predicted future front

New core (`routing/future_front.py`, `notebooks/05_*.ipynb`,
`docs/figures/route_away_from_front.png`). Time-expanded routing over a
georeferenced network: each node carries the time the predicted front
reaches it; a time-dependent Dijkstra prunes any node the evacuee would
reach after the front (within a safety margin), targeting a reachable
shelter; reports route, **latest safe departure**, and **clearance margin**.
Elderly walk speed 0.6 m/s.

**Danger-scenario contrast (the headline of the spine):**
- **Naive** (nearest shelter, fire-blind): 1000 m to the near west shelter
  — **walks INTO the advancing front** (`enters_front = True`).
- **Future-aware**: 3600 m to the far east shelter — **never enters the
  front** (`enters_front = False`), **clearance margin 45 min**.

Tests confirm: valid paths; future-aware route never intersects the front
when a safe route exists; returns "no safe route" when the front overtakes
all shelters; naive vs future-aware diverge in the danger scenario.

**Honest dependency**: the router consumes a *predicted* front. Because the
surface model under-predicts (§4), the demo drives the router with a
*prescribed* wind-driven front (clearly labelled), and the routing is only
as safe as the front feeding it. Improving the front (crown/spotting) is the
upstream priority.

## 6. (Stretch, done) Empirical super-multiplicativity test scaffold

`spread_model/empirical_interaction.py`: XGBoost on a **clearly-labelled
synthetic** dataset, recovering ∂²R/∂M∂U from the fitted surface and
comparing to the Rothermel separable baseline.

- Separable synthetic data → empirical −2.95 vs Rothermel −2.30 →
  **not flagged super** (correct).
- Injected super-multiplicative data → empirical −9.89 →
  **detected** (correct).

This proves the test *can* detect super-multiplicativity; running it on
**real** fire+weather data (data-access session) is the genuinely-novel
experiment it sets up. All data here is synthetic; no empirical claim made.

---

## 7. Data provenance table (after Session 5)

| Input | Status | Source |
|-------|--------|--------|
| DEM | ✅ REAL | NASA SRTMGL1 30 m (AWS Mapzen) |
| Wind reference height → midflame | ✅ CORRECT | Andrews 2012 WAF |
| Korean live-fuel moisture (119 %) | ✅ MEASURED | Lee et al. 2018 |
| Korean crown structure / WAF inputs | ✅ MEASURED | Lee et al. 2018 |
| Korean **surface** fuel bed | ⚠️ PROVISIONAL | best-estimate, flagged |
| Wind time series | ⚠️ SYNTHETIC | March 2025 reconstruction (no KMA key) |
| Fuel-type raster | ⚠️ SYNTHETIC | 100 % Korean Pinus fill |
| Observed perimeter | ⚠️ APPROXIMATE | reconstructed from public reporting |
| Routing road network | ⚠️ SYNTHETIC | grid on real Yeongdeok location (no OSM) |
| Routing demo front | ⚠️ PRESCRIBED | stand-in (surface model under-predicts) |
| Empirical-interaction data | ⚠️ SYNTHETIC | scaffold only |
| Cross-partial / separability | ✅ EXACT | analytic Rothermel structure |

## 8. What's still broken / next-session priorities

1. **Crown-fire / spotting module** — the #1 gap. Without it the spread
   model under-predicts wind-driven Korean pine fires by ~90 %. This is the
   prerequisite for a trustworthy front to feed the routing spine.
2. **Real KFS perimeter** — turns validation from reconstruction-vs-
   reconstruction into model-vs-truth.
3. **Real KMA wind** (incl. gusts) — needs an API key.
4. **Korean surface-litter fuel data** — replace the provisional bed.
5. **Real OSM network + per-resident mobility** for the routing spine.
6. **Run the empirical super-multiplicativity test on real data.**

## 9. API keys this session

**None present** (`FIRMS_API_KEY`/`MAP_KEY`, `KMA_API_KEY`/`KMA_SERVICE_KEY`
all absent). Deliverables 1–6 need no keys and are complete; real FIRMS/KMA
ingestion remains Round-2.

## 10. Net honest status

The project's two defensible contributions after this session:
1. **Corrected, honest physics**: midflame WAF; the dimensional cross-partial
   (not a tautological ratio); literature-anchored Korean live fuel.
2. **The future-front-aware routing spine**: a correct, tested algorithm that
   keeps evacuees out of the fire's *future* footprint — the novelty anchor.

The spread model alone does **not** predict the Yeongdeok front (it lacks
crown/spotting physics); we report this plainly rather than masking it with
cancelling errors as Session 4 did.
