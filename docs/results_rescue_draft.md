# Rescue-aware evacuation routing — results (DRAFT)

> **Round 2 · Phase 1 — real-data flip (2026-07).** The `[src: rescue_*.json]`
> citations below resolve to **real-OSM** outputs (road/refuge/depot geometry
> flipped from synthetic; fire hazard + terrain still synthetic pending FIRMS), and
> every number in this draft has been updated to match. The pre-flip synthetic
> baseline (N = 452; four-way 154/34/244/20; `w` ≈ 33–45 %; 264/58 % needs-rescuer;
> etc.) is preserved at `data/processed/rescue_baseline_synthetic/` and in the OLD
> column of `docs/REPORT_ROUND2_P1.md`, which also has the full OLD-vs-NEW table.

> **DRAFT for the author to edit.** Every quantitative claim is tagged with its
> committed source as `[src: file / key]`. Citations not yet in the repo
> bibliography are flagged `[CITE: …]` (not fabricated); unsourced numbers would be
> `[TODO: source]`. Single-fire (영덕) proof-of-concept on real OSM roads/refuges/
> depots with a synthetic-and-tagged fire hazard + terrain — no multi-fire claims;
> no "lives saved" conversions; absolute magnitudes are illustrative,
> contrasts/directions are the result.

## Claims ledger

| claim | strength | source |
|---|---|---|
| **On real roads, most elders can self-evacuate — but 167/439 (38 %) still need a rescuer** | **headline, directional** (23–55 % across assumptions) | `[src: rescue_verify_fc.json / needs_rescuer, walk_failure]` |
| **~11 % of mobile residents cannot self-evacuate on foot** (range ≈ 9–17 % across the walk cutoff), independent of the immobility assumption — down sharply from ≈40 % (33–45 %) on the synthetic lattice | **robust, assumption-light** | `[src: rescue_verify_fc.json / walk_failure]` |
| **dispatch delay 0→60 min raises the unreachable set, sharply** (6→66 at baseline cutoff — steeper than the synthetic lattice's 6→34) | **robust direction, sharper on real roads** | `[src: rescue_verify.json / robustness_verdict.dispatch_delay_trend; rescue_sweep_2d.png]` |
| **new: 63 of 143 dispatchable homes are reachable only via a survival-aware detour** (their direct ingress corridor is already cut before the direct ETA) | **real, reported — not tuned away** | `[src: rescue_capacity.json / n_dispatch_direct_corridor_cut_reachable_by_detour; REPORT_ROUND2_P1.md §3]` |
| resident / responder exposure contrasts (≈83 % lower; ≈72 % lower / ≈3.6×) | **illustrative magnitude, robust direction** | `[src: rescue_verify_fc.json / reconciled_block; rescue_routing.md §4a]` |
| `saved` ≈ 10 (rescue-reachable-refuge walk) — down from 34 on the synthetic lattice | **real but small(er)** | `[src: rescue_verify_fc.json / grid]` |
| specific dispatch list / which homes unreachable | **illustrative** | `[src: rescue_routing.json / dispatch_top20, unreachable_homes]` |

---

## 1. Setup

We evaluate rescue-aware evacuation on the 2025 영덕(Yeongdeok) wildfire extent — the
anchor casualty event (part of the 2025 의성–안동 wildfire complex: ~27 deaths total — 8 in
영덕 — victims predominantly residents in their 60s–80s in rural villages
`[src: 서울환경연합 2026 회고(23명은 2025-03-26 시점); 세계일보·한겨레 2025-03-26; README.md]`). The router consumes the project's data-driven spread hazard as a
time-sliced per-cell ignition-probability surface — the foundation this builds on
(leave-one-fire-out **mean-of-folds ROC-AUC 0.90 ± 0.07**, range 0.78–0.98; pooled
0.867, far-band 0.821 pooled
`[src: data/processed/spread_v2_lofo.json; docs/MODEL_CARD.md]`; forward-simulated
footprint IoU **~0.40**
`[src: docs/ROUTING_INTEGRATION_REPORT.md]`). N = **439** candidate elderly-home
origins are scanned on a **real OpenStreetMap walk** network (Round 2 · Phase 1;
~6× denser than the pre-flip synthetic lattice, so the scan stride was adapted to
keep N near the synthetic scale); responders use a separate real OSM **drive**
network; shelters (대피소, 50 of them) and responder depots (119안전센터, 4 of them)
are likewise **real OSM POIs** here, each with a clearly-labelled synthetic
fallback for when the OSM cache/network is unavailable. Only the fire **hazard**
and **terrain** remain `source="synthetic"`, pending the FIRMS bundle
`[src: data/processed/rescue_verify_fc.json / sources]`.

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
sweep cell, **`w` ≈ 11 % at the baseline walk cutoff 0.5** (11.3 / 11.4 / 14.1 % at
`f` = 0.15 / 0.30 / 0.45 — i.e. **~flat across `f`**, max spread 3.5 points at any
fixed cutoff, as expected for a walkability-independent random immobility draw), and
**ranges ≈ 9–17 % across the walk cutoff** (17 % at the conservative 0.40 cutoff,
9 % at the permissive 0.60) `[src: rescue_verify_fc.json / walk_failure]`. This is
sharply lower than the pre-flip synthetic lattice's ≈40 % (33–45 %) — real
pedestrian connectivity lets many more mobile elders reach a refuge on foot. The
identity `needs_rescuer ≈ f·N + (1−f)·w·N` reproduces every cell to ±0.3
`[src: rescue_verify_fc.json / walk_failure.per_cell]`.

**Headline:** *on real 영덕 roads (fire hazard still synthetic), roughly one in
nine residents who can physically walk still cannot reach safety on foot* — down
from roughly two in five on the pre-flip synthetic lattice, and a number that does
**not** depend on the immobility placeholder. The exact percentage is illustrative
(single-fire PoC + synthetic fire/terrain); the order of magnitude (~9–17 %) is the
assumption-light result, and the drop from the synthetic lattice is a genuine
walkability signal, not an artifact of the immobile-fraction assumption.

## 3. Result 2 — spine, robust direction: responder delay drives unreachability

On the full-N vehicle×delay sweep at the baseline vehicle cutoff, the **unreachable**
set rises **monotonically with responder dispatch delay: 6 → 11 → 24 → 51 → 66** over
0 → 15 → 30 → 45 → 60 min, and the trend is monotone for *every* vehicle cutoff
`[src: rescue_verify.json / robustness_verdict.dispatch_delay_trend; docs/figures/rescue_sweep_2d.png]`.
This penalty is markedly **sharper on real roads**: the pre-flip synthetic lattice's
same bracket only rose 6 → 15 → 20 → 25 → 34 — real corridors have less redundancy
against a delayed responder than the synthetic lattice did. This is the direct
computational echo of the 영덕 event, where the fire reached designated evacuation
areas before many residents or responders could act
`[CITE: World Weather Attribution / contemporaneous reporting — 영덕 2025 timeline]`,
and of the documented finding that responder/caregiver delay is itself a cause of
death for people who cannot self-evacuate
`[CITE: vulnerable-population evacuation review — responder/caregiver-delay mortality]`.
The *direction* is robust — and now even more pronounced; the absolute counts are
illustrative.

## 3b. Result 2b — new finding: dispatchable ≠ direct-corridor-open

A real-road-only finding with no synthetic-lattice analogue. On the synthetic
lattice, every dispatchable home also had a surviving **direct** responder
corridor, so unlimited rescue units recovered all of dispatch (`capacity_deferred →
0`). On **real roads this breaks**: **63 of the 143** dispatch-reachable homes are
reachable **only via a survival-aware detour** — their direct ingress corridor is
already cut before the responder's direct ETA (`closing_window < 0`). The capacity
model credits only the direct corridor, so those 63 homes are deferred even with
unlimited units; unlimited units instead recover the **deadline-feasible** subset,
**80 of 143** `[src: rescue_capacity.json / n_dispatch_deadline_feasible,
n_dispatch_direct_corridor_cut_reachable_by_detour]`. This is a genuine consequence
of real road topology (alternate routes the synthetic lattice simply did not have)
and is **reported, not tuned away** — the verify script's capacity invariant was
corrected from the synthetic-only assumption to the mathematically-correct one. It
is arguably the single most important new result of the real-data flip: geometry
alone caps timely rescue at 85.6 % of demand (143/167), and within that reachable
85.6 %, a further 63/143 need a detour rather than the direct corridor.

## 4. Result 3 — rescue-routing contrasts (illustrative magnitude, by route type)

Two distinct, non-comparable metrics (both `prob·min`, labelled by route type
`[src: rescue_verify_fc.json / resident_exposure.route_type, responder_exposure.route_type]`):

- **Resident (pedestrian routes):** future-aware routing cuts predicted-hazard
  exposure **≈83 %** vs the fire-blind naive route (mean **9.16 → 1.59 prob·min**);
  the additional rescue-reachability restriction (policy c) now costs essentially
  nothing (paired 2.22 → 2.22 over the same 155 origins, re-routing **0** residents
  off a cut-off refuge — down from 2 on the synthetic lattice, since with 50 real
  refuges most safe walks already land on a rescue-reachable one)
  `[src: rescue_verify_fc.json / reconciled_block; rescue_routing.md §4a]`.
- **Responder (vehicle routes):** the survival-aware ingress cuts exposure **≈72 %
  (≈3.6×)** vs a fire-blind shortest path (**6.12 → 1.71 prob·min**, over 143
  dispatched homes) — a *larger* relative advantage than the synthetic lattice's
  ≈54 %, even though both absolute numbers are ~20× larger (real vehicle corridors
  traverse more hazard cells than the short synthetic-lattice hops did)
  `[src: rescue_verify_fc.json / reconciled_block]`.

The vehicle scale (~1.7–6) and the pedestrian scale (~1.6–9) are **not**
comparable — they reflect different route lengths and speeds, not different
safety — though on real roads they now happen to sit in a broadly similar numeric
range (on the synthetic lattice the vehicle scale was ~0.08 vs a pedestrian ~3–24).

## 5. Result 4 — the "38 %", decomposed and demoted

At baseline (`f`=0.30, walk cutoff 0.50) **167/439 = 38 %** cannot self-evacuate on
foot `[src: rescue_verify_fc.json / needs_rescuer.baseline_pct]`. This is **not a
robust number**: across the assumption grid it ranges **23–55 %** (100–240), and
**halving the assumed immobile fraction to 0.15 drops it to 25 %** (108/439)
`[src: rescue_verify_fc.json / needs_rescuer]`. Reported honestly it is
`needs_rescuer = f·N + (1−f)·w·N` — **a model-derived ~11 % walk-failure (`w`) plus
an assumed immobile add-on** — and should never appear as a bare "38 %" any more
than the pre-flip "58 %" should have. The robust content is (a) the assumption-light
`w` (§2, now ≈9–17 % vs the synthetic lattice's ≈33–45 %) and (b) the monotone rise
with `f` and with a harsher walk cutoff `[src: rescue_verify_fc.json / monotonicity]`.

## 6. Result 5 — `saved` (small(er), honest)

The new resident-side method *saves* **≈10** origins — down from ≈34 on the
pre-flip synthetic lattice: residents whose fire-blind walk would enter the fire
but whose future-aware walk to a **rescue-reachable** refuge is safe `[src:
rescue_verify_fc.json / grid]`. The count shrank because real 영덕 has 50 refuges
(24 rescue-reachable) versus the synthetic 20 (19 rescue-reachable) — with more
rescue-reachable refuges available, most residents whose naive walk is unsafe
already reach *some* rescue-reachable refuge via ordinary future-aware routing, so
the marginal origins the rescue constraint *uniquely* saves are fewer. This looks
worse for the feature's headline count and is reported as-is: it is the rescue
layer's marginal *pedestrian* benefit — real, but small relative to the
rescuer-side burden (§5).

## 7. Honest negatives

The **unreachable set is always nonzero** (24 at baseline; 0–72 across the
assumption and vehicle grids) and is **reported, never imputed** — some origins
have no safe route under any policy, walking or driven `[src:
rescue_verify_fc.json / grid; rescue_routing.json / unreachable_homes]`. The
surviving-ingress layer *reduces* the unreachable set; it does not eliminate it.
Separately, of the homes that **are** dispatch-reachable, 63/143 need a
survival-aware detour rather than the direct corridor (§3b) — another honest
negative the capacity model now reports rather than assumes away.

## 8. Limitations

- **(a) Immobility is a random, spatially-uniform placeholder.** Real immobility
  clusters with age, health, and social isolation, so while the population *counts*
  are stable, *which* homes are immobile — and therefore the specific dispatch list
  and which homes are unreachable — are **seed-dependent and illustrative**
  `[src: src/wildfireguardian/routing/rescue_demo.py / _immobile_homes]`. The
  assumption-light `w` (§2) is the part that survives this caveat.
- **(b) Shelters, depots, and road access are now real OpenStreetMap data (Round 2
  · Phase 1); the fire hazard and terrain remain synthetic-on-real and tagged**,
  pending the FIRMS bundle. Absolute reachability is still illustrative because of
  the synthetic hazard/terrain; the robust result is the contrast/direction
  `[src: rescue_verify_fc.json / sources]`. Real loaders exist for 공공데이터포털
  대피소 and 119안전센터 / OSM `amenity=fire_station`, and are what produced this
  run's 50 refuges / 4 depots `[src: docs/data_sources.md]`.
- **(c) Single-fire (영덕) proof-of-concept** — not multi-fire validated, not
  operational.
- **(d) The spread hazard is a risk *ranking*, not a perimeter forecast.** Report AUC
  (mean-of-folds 0.90 ± 0.07; pooled 0.867) and footprint IoU (~0.40 forward-sim;
  the 0.866 single-step IoU is "next overpass given the current burn", not a
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
