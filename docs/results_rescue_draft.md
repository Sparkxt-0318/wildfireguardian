# Rescue-aware evacuation routing — results (DRAFT)

> ⚠️ **DO NOT CITE THESE NUMBERS / 제출·인용 금지 — SUPERSEDED.** Every quantitative value in
> this draft (N = 452; four-way 154/34/244/20; `w` ≈ 40 %; 264/58 % needs-rescuer) is the
> **pre-flip synthetic baseline**. The committed real-OSM values are **N = 439**, four-way
> **262 / 10 / 143 / 24**, needs-rescuer **38.0 % (167)**, walk-failure **`w` = 0.091–0.174**.
> Cite `docs/REPORT_ROUND2_P1.md` (authoritative OLD-vs-NEW table), never this draft.

> **Round 2 · Phase 1 — real-data flip (2026-07).** The `[src: rescue_*.json]`
> citations below now resolve to **real-OSM** outputs (road/refuge/depot geometry
> flipped from synthetic; fire hazard + terrain still synthetic pending FIRMS). The
> synthetic values quoted in this draft (N = 452; four-way 154/34/244/20; `w` ≈ 40 %;
> 264/58 % needs-rescuer; etc.) are the **pre-flip** baseline, preserved at
> `data/processed/rescue_baseline_synthetic/`. For the current real numbers and the
> OLD-vs-NEW table see `docs/REPORT_ROUND2_P1.md`.

> **DRAFT for the author to edit.** Every quantitative claim is tagged with its
> committed source as `[src: file / key]`. Citations not yet in the repo
> bibliography are flagged `[CITE: …]` (not fabricated); unsourced numbers would be
> `[TODO: source]`. Single-fire (영덕) proof-of-concept on synthetic-and-tagged
> auxiliary data — no multi-fire claims; no "lives saved" conversions; absolute
> magnitudes are illustrative, contrasts/directions are the result.

## Claims ledger

| claim | strength | source |
|---|---|---|
| **~40 % of mobile residents cannot self-evacuate on foot** (range ≈ 33–45 % across the walk cutoff), independent of the immobility assumption | **robust, assumption-light** | `[src: rescue_verify_fc.json / walk_failure]` |
| **dispatch delay 0→60 min raises the unreachable set** (6→34 at baseline cutoff) | **robust direction** | `[src: rescue_verify.json / robustness_verdict.dispatch_delay_trend; rescue_sweep_2d.png]` |
| resident / responder exposure contrasts (≈85 % lower; ≈halved) | **illustrative magnitude, robust direction** | `[src: rescue_verify_fc.json / reconciled_block; rescue_routing.md §4a]` |
| "58 % need a rescuer" | **directional only** (43–70 % across assumptions) | `[src: rescue_verify_fc.json / needs_rescuer, walk_failure]` |
| `saved` ≈ 34 (rescue-reachable-refuge walk) | **real but small** | `[src: rescue_verify_fc.json / grid]` |
| specific dispatch list / which homes unreachable | **illustrative** | `[src: rescue_routing.json / dispatch_top20, unreachable_homes]` |

---

## 1. Setup

We evaluate rescue-aware evacuation on the 2025 영덕(Yeongdeok) wildfire extent — the
anchor casualty event (part of the 2025 의성–안동 wildfire complex: ~27 deaths total — 8 in
영덕 — victims predominantly residents in their 60s–80s in rural villages
`[src: 서울환경연합 2026 회고(23명은 2025-03-26 시점); 세계일보·한겨레 2025-03-26; README.md]`). The router consumes the project's data-driven spread hazard as a
time-sliced per-cell ignition-probability surface — the foundation this builds on
(leave-one-fire-out **mean-of-folds ROC-AUC 0.89 ± 0.11**, range 0.68–0.97; pooled
0.905, far-band 0.877 pooled
`[src: data/processed/spread_v2_lofo.json; docs/MODEL_CARD.md]`; forward-simulated
footprint IoU **~0.40**
`[src: docs/ROUTING_INTEGRATION_REPORT.md]`). N = **452** candidate elderly-home
origins are scanned on an OSM-style **walk** network; responders use a separate
**drive** network; shelters (대피소) and responder depots (119안전센터) have real-source
loaders **and a clearly-labelled synthetic fallback used here, tagged
`source="synthetic"`** `[src: data/processed/rescue_verify_fc.json / baseline_config]`.

Each origin lands in exactly one of four buckets: **already-safe** (a mobile
resident's fire-blind walk is safe); **saved** (mobile, naive walk unsafe, but a
future-aware walk to a *rescue-reachable* refuge is safe); **no-walk-rescuer-reaches**
(cannot self-evacuate but a responder can reach); **unreachable** (cannot walk out
*and* no responder route survives). **Immobility is assigned as a random, spatially
uniform fraction `f` (a placeholder)** `[src: src/wildfireguardian/routing/rescue_demo.py
/ _immobile_homes]`: a random `f·N` origins are forced onto the rescuer path
regardless of whether they could have walked out.

## 2. Result 1 — spine, assumption-light: the walk-failure rate `w`

The "need a rescuer" count contains the immobility guess as an additive term:
`needs_rescuer = f·N + (1−f)·w·N`, where **`w` = the fraction of *mobile* origins that
cannot walk to safety** even with future-aware routing — the part the model earns
*independent of the immobility assumption*. Measured over the mobile pool of each
sweep cell, **`w` ≈ 40 % at the baseline walk cutoff 0.5** (0.41 / 0.40 / 0.41 at
`f` = 0.15 / 0.30 / 0.45 — i.e. **~flat across `f`**, max spread 0.04, as expected for
a walkability-independent random immobility draw), and **ranges ≈ 33–45 % across the
walk cutoff** (45 % at the conservative 0.40 cutoff, 33 % at the permissive 0.60)
`[src: rescue_verify_fc.json / walk_failure]`. The identity
`needs_rescuer ≈ f·N + (1−f)·w·N` reproduces every cell to ±0.3
`[src: rescue_verify_fc.json / walk_failure.per_cell]`.

**Headline:** *under this synthetic 영덕 geometry, roughly two in five residents who
can physically walk still cannot reach safety on foot* — a number that does **not**
depend on the immobility placeholder. The exact percentage is illustrative
(single-fire PoC + synthetic geometry); the order of magnitude (~40 %) is the
assumption-light result.

## 3. Result 2 — spine, robust direction: responder delay drives unreachability

On the full-N vehicle×delay sweep at the baseline vehicle cutoff, the **unreachable**
set rises **monotonically with responder dispatch delay: 6 → 15 → 20 → 25 → 34** over
0 → 15 → 30 → 45 → 60 min, and the trend is monotone for *every* vehicle cutoff
`[src: rescue_verify.json / robustness_verdict.dispatch_delay_trend; docs/figures/rescue_sweep_2d.png]`.
This is the direct computational echo of the 영덕 event, where the fire reached
designated evacuation areas before many residents or responders could act
`[CITE: World Weather Attribution / contemporaneous reporting — 영덕 2025 timeline]`,
and of the documented finding that responder/caregiver delay is itself a cause of
death for people who cannot self-evacuate
`[CITE: vulnerable-population evacuation review — responder/caregiver-delay mortality]`.
The *direction* is robust; the absolute counts are illustrative.

## 4. Result 3 — rescue-routing contrasts (illustrative magnitude, by route type)

Two distinct, non-comparable metrics (both `prob·min`, labelled by route type
`[src: rescue_verify_fc.json / resident_exposure.route_type, responder_exposure.route_type]`):

- **Resident (pedestrian routes):** future-aware routing cuts predicted-hazard
  exposure **≈85 %** vs the fire-blind naive route (mean **24.06 → 3.55 prob·min**);
  the additional rescue-reachability restriction (policy c) costs little (paired
  3.42 → 3.47 over the same 185 origins, re-routing 2 residents off a cut-off refuge)
  `[src: rescue_verify_fc.json / reconciled_block; rescue_routing.md §4a]`.
- **Responder (vehicle routes):** the survival-aware ingress **≈halves** exposure vs a
  fire-blind shortest path (**0.172 → 0.079 prob·min**, over 244 dispatched homes)
  `[src: rescue_verify_fc.json / reconciled_block]`.

The vehicle scale (~0.08) and the pedestrian scale (~3–24) are **not** comparable —
they reflect different route lengths and speeds, not different safety.

## 5. Result 4 — the "58 %", decomposed and demoted

At baseline (`f`=0.30, walk cutoff 0.50) **264/452 = 58 %** cannot self-evacuate on
foot `[src: rescue_verify_fc.json / needs_rescuer.baseline_pct]`. This is **not a
robust number**: across the assumption grid it ranges **43–70 %** (196–315), and
**halving the assumed immobile fraction to 0.15 drops it to 47 %** (211/452)
`[src: rescue_verify_fc.json / needs_rescuer]`. Reported honestly it is
`needs_rescuer = f·N + (1−f)·w·N` — **a model-derived ~40 % walk-failure (`w`) plus an
assumed immobile add-on** — and should never appear as a bare "58 %". The robust
content is (a) the assumption-light `w` (§2) and (b) the monotone rise with `f` and
with a harsher walk cutoff `[src: rescue_verify_fc.json / monotonicity]`.

## 6. Result 5 — `saved` (small, honest)

The new resident-side method *saves* **≈34** origins: residents whose fire-blind walk
would enter the fire but whose future-aware walk to a **rescue-reachable** refuge is
safe `[src: rescue_verify_fc.json / grid]`. These are coastal-refuge-driven (the
refuges that stay rescue-reachable across the vehicle knobs); it is the rescue layer's
marginal *pedestrian* benefit — real, but small relative to the rescuer-side burden.

## 7. Honest negatives

The **unreachable set is always nonzero** (20 at baseline; 1–40 across the assumption
and vehicle grids) and is **reported, never imputed** — some origins have no safe
route under any policy, walking or driven `[src: rescue_verify_fc.json / grid;
rescue_routing.json / unreachable_homes]`. The surviving-ingress layer *reduces* the
unreachable set; it does not eliminate it.

## 8. Limitations

- **(a) Immobility is a random, spatially-uniform placeholder.** Real immobility
  clusters with age, health, and social isolation, so while the population *counts*
  are stable, *which* homes are immobile — and therefore the specific dispatch list
  and which homes are unreachable — are **seed-dependent and illustrative**
  `[src: src/wildfireguardian/routing/rescue_demo.py / _immobile_homes]`. The
  assumption-light `w` (§2) is the part that survives this caveat.
- **(b) Shelters, depots, and road access are synthetic-on-real and tagged.** Absolute
  reachability is illustrative; the robust result is the contrast/direction
  `[src: rescue_verify_fc.json / baseline_config]`. Real loaders exist for 공공데이터포털
  대피소 and 119안전센터 / OSM `amenity=fire_station` `[src: docs/data_sources.md]`.
- **(c) Single-fire (영덕) proof-of-concept** — not multi-fire validated, not
  operational.
- **(d) The spread hazard is a risk *ranking*, not a perimeter forecast.** Report AUC
  (mean-of-folds 0.89 ± 0.11; pooled 0.905) and footprint IoU (~0.40 forward-sim;
  the 0.874 single-step IoU is "next overpass given the current burn", not a  <!-- forbidden-ok: 0.874 -->
  from-scratch footprint) together: the model ranks at-risk cells well but
  does not pinpoint the exact perimeter `[src: data/processed/spread_v2_lofo.json;
  docs/ROUTING_INTEGRATION_REPORT.md]`.
- **(e) Overpass-scale time resolution (hours, not minutes)** — rules out tactical use
  `[src: docs/ROUTING_INTEGRATION_REPORT.md]`.
- **(f) ERA5 (~31 km) understates valley-scale 양강지풍 / Föhn winds** that drive East-Coast
  spring fires; downscaled LDAPS-class wind is a future upgrade `[CITE: KMA LDAPS /
  양강지풍 downslope-wind reference]`.
- **(g) Forward-simulation error compounds** with horizon (IoU drifts to ~0.40 by
  3–12 h) `[src: docs/ROUTING_INTEGRATION_REPORT.md]`.

---

### Modelling lineage / differentiation (for the intro, citations TBD)

Shelter-in-refuge / be-rescued as a protective action `[CITE: Cova et al. — referenced
in src/wildfireguardian/routing/rescue.py]`; agent/network evacuation-modelling lineage
and how this differs (a *survival-of-the-ingress-corridor constraint on top of a
predicted hazard*, not an agent simulation) `[CITE: WUIVAC; WUI-NITY]`. These
references are **not yet in the repo bibliography** — add them before publication.
