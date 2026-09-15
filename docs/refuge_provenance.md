# Refuge provenance: OpenStreetMap refuges versus 행정안전부 designated sites (WFG-073, paper gap G6)

**Status: the rule below (§2) was pre-registered and committed BEFORE the run. §3 is
appended by `scripts/run_refuge_provenance.py`; nothing above the §3 line is edited
afterwards.** Docs and `data/processed/` only. Nothing is registered in
`docs/NUMBERS.json` and nothing reaches a judge-facing surface; that is an HQ decision
after the numbers exist.

## 1. Why

Every refuge in this project's results is an OpenStreetMap point. The canonical 영덕
partition — 458 origins, `both_safe` 414 / `naive_into_FA_safe` 42 / `no_safe_route` 2
in `data/processed/real_roads_real_hazard_canonical.json` → `arms.slope_digraph_canonical`
— is produced by snapping the committed `osm-shelters` snapshot (50 refuge POIs) onto the
walk graph. The 행정안전부 주소정보누리집 agency-designated subset for 영덕군 has been
committed since 2026-09-04 under `data/processed/external/juso_yeongdeok/`
(`docs/juso_yeongdeok.md`) and nothing has ever been re-routed against it.

So no result in the repository says how much of that partition is a statement about
**where OpenStreetMap thinks refuges are** rather than about **where designated refuges
actually are**.

**What this bears on, and what it does not.** It bears on every ABSOLUTE 영덕 rate — the
414, the 42, the 2, and anything derived from them as a share of 458 — because all of
them are conditional on one refuge set. It does **not** bear on the paired contrast
between the fire-blind and the forecast-aware router, because both arms of that contrast
route to the *same* refuge set, whichever set that is; changing the refuge set changes
both arms together. The contrast is the project's headline claim and this experiment
cannot confirm or undermine it. It can only tell the reader what the absolute numbers are
conditional on.

## 2. The rule, fixed before the numbers exist

Decided by HQ; recorded here before `scripts/run_refuge_provenance.py` was run.

### 2.1 Which layers are refuge candidates

The **primary designated set** is exactly two layers from
`data/processed/external/juso_yeongdeok/`:

| layer | 이름 | features |
|---|---|---:|
| `samul_eqout_point.geojson` | 지진옥외대피장소 (earthquake outdoor evacuation site) | 64 |
| `samul_coolingcen_point.geojson` | 무더위쉼터 (cooling centre) | 17 |

`samul_eqwav_point.geojson` (지진해일긴급대피장소, tsunami emergency evacuation site, 92
features) is **EXCLUDED from the primary arm**: a 지진해일 assembly point is coastal by
construction and is selected for a hazard whose geometry is the opposite of a wildfire's.
It is run instead as a **separate, labelled third designated arm**
(`designated_plus_tsunami`), so that the choice is visible in the artifact rather than
hidden inside it. **The tsunami arm is never the headline.**

Not refuges, and not used: `minwon_agencies.geojson` (55 민원행정기관 — schools, offices,
police, fire, post offices; these are WFG-074's depots and notification targets, not
refuges), `samul_firehydr_point.geojson` (23 소화전), `samul_busst_point.geojson`
(3 버스정류장). Empty in this county's cut and therefore unusable either way:
`samul_lifesav_point.geojson` (인명구조함, 0) and `samul_emerwat_point.geojson`
(비상급수시설, 0). Every layer's feature count is recorded in the artifact whether the
layer is used or not.

### 2.2 Extent — clip first, then snap

`docs/juso_yeongdeok.md` warns that the two sets are **not on one extent**. The designated
counts are county-wide, with roughly 77–84 % of each layer inside the canonical 영덕 walk
box (`manifest.json` → `inside_canonical_box_share`), while the router's refuges are
counted inside that box alone. **The two sets must never be differenced as they stand.**

So: **CLIP the designated points to the canonical walk box first** —
`bbox.multi_region_walk_bbox.yeongdeok_2025` = (129.250, 36.300, 129.550, 36.600) in
WGS84 — **and only then snap** to the walk graph with the same `net.nearest_node` call the
committed run uses. Per layer, the artifact reports how many features fell inside the box
and how many were dropped.

### 2.3 The arms

Four arms, all on the **same 458 origins**, the **same canonical hazard field**
(`data/processed/routing_demo_canonical.npz`) and the **same parameters** as the committed
run: `origin_scan_stride` 18, `p_cut` 0.5, 600 min budget, 10 min step, slope-adjusted
DiGraph. The origin rule (`candidate_origins`) does not read the refuge set, so the origin
list is identical across arms by construction.

| arm | refuges |
|---|---|
| `osm` | the committed `osm-shelters` snapshot — the refuge set every existing result uses |
| `designated` | the primary designated set only (§2.1), clipped (§2.2) |
| `union` | both sets together |
| `designated_plus_tsunami` | primary designated set + the tsunami layer — a labelled sensitivity, never the headline |

Reported for every arm: the three-bucket partition (`both_safe` / `naive_into_FA_safe` /
`no_safe_route`), the refuge POI count, and the number of distinct walk-graph nodes those
POIs snap to.

### 2.4 Reproduction gate, hard

Arm `osm` MUST reproduce the committed
`data/processed/real_roads_real_hazard_canonical.json` → `arms.slope_digraph_canonical`
**exactly**: 458 origins, `both_safe` **414**, `naive_into_FA_safe` **42**,
`no_safe_route` **2**, from **50** refuge POIs snapping to **46** shelter nodes.

If arm `osm` does not reproduce those exactly, the run **STOPS**, writes what it got, and
the other three arms are **not** reported as comparable. Nothing is tuned to make it
reproduce.

### 2.5 Grade every arm on the observation too

Each arm is also graded against the observed FIRMS footprint using the three-way rule
**already pre-registered** in `docs/regrade_three_way.md` §2–§3 — declared evidence bounds
A1–A6, verdicts *admissible for all* / *indeterminate* / *inadmissible for all*, at miss
allowances m ∈ {0, 1, ∞}. That rule is imported, not restated, so this run cannot mean
something different by「admissible」. `data/processed/routing_demo_canonical.npz` carries
`obs_stack` on the same grid. The observed grading is the number that survives the choice
of hazard field, and now also the choice of refuge set.

### 2.6 The reading rule, fixed now

The partition **「depends on refuge provenance」** if the `designated` arm's
`no_safe_route` count **or** its `naive_into_FA_safe` count differs from the `osm` arm's
by **more than a third of the OSM value** — i.e. more than 14 on the 42, or more than
0.67 (so, more than 1 site, i.e. a difference of 2 or more) on the 2.

Otherwise: **「the absolute rates are robust to refuge provenance.」**

Either way the run reports **how many designated sites are within snapping distance of an
OSM refuge already counted** — i.e. how many designated sites snap to a walk-graph node
that is already in the OSM arm's shelter-node set — because a large overlap is itself the
answer: it would mean the two provenances name largely the same places and the question
dissolves rather than being settled by the partition.

### 2.7 What the run will not be able to show

Fixed here so it cannot be softened later: this run cannot say whether any designated site
is a wildfire refuge (the 사물주소 categories are earthquake, tsunami and heat), whether a
site is open or staffed during a spring wildfire, or what its capacity is
(`docs/juso_yeongdeok.md`, "What it does not show"; NH-012 b). It cannot say which refuge
set is *correct*. It is a sensitivity of the committed partition to one input, nothing
more.

## 3. Results

_(appended by `scripts/run_refuge_provenance.py`; nothing above this line is edited after the run)_

_Run 2026-09-15T04:48:01Z at `fa308fb`; artifact `data/processed/refuge_provenance_yeongdeok.json`; 458 origins in every arm; reproduction gate (§2.4) **PASSED**._

### 3.1 The four arms

| arm | refuge POIs | snapped nodes | both_safe | naive_into_FA_safe | no_safe_route | other |
|---|---:|---:|---:|---:|---:|---:|
| osm (committed) | 50 | 46 | 414 | 42 | 2 | 0 |
| designated (primary) | 68 | 68 | 440 | 16 | 2 | 0 |
| union | 118 | 113 | 435 | 21 | 2 | 0 |
| designated_plus_tsunami (sensitivity) | 139 | 131 | 447 | 9 | 2 | 0 |

### 3.2 Extent: what the clip to the canonical walk box dropped (§2.2)

| layer | features | inside walk box | dropped |
|---|---:|---:|---:|
| `samul_eqout_point` | 64 | 54 | 10 |
| `samul_coolingcen_point` | 17 | 14 | 3 |
| `samul_eqwav_point` | 92 | 71 | 21 |

Every layer in the folder, used or not:

| layer | features | used as a refuge candidate? |
|---|---:|---|
| `minwon_agencies` | 55 | no — depots (WFG-074) |
| `samul_busst_point` | 3 | no |
| `samul_coolingcen_point` | 17 | yes — primary |
| `samul_emerwat_point` | 0 | no — empty |
| `samul_eqout_point` | 64 | yes — primary |
| `samul_eqwav_point` | 92 | sensitivity arm only |
| `samul_firehydr_point` | 23 | no |
| `samul_lifesav_point` | 0 | no — empty |

### 3.3 Observed three-way grading (docs/regrade_three_way.md §2–§3, A1–A6)

| arm | route | m | admissible for all | indeterminate | inadmissible for all | unsupported | not reached |
|---|---|---|---:|---:|---:|---:|---:|
| osm (committed) | fire-blind | 0 | 329 | 91 | 38 | 0 | 0 |
| osm (committed) | fire-blind | 1 | 329 | 91 | 38 | 0 | 0 |
| osm (committed) | fire-blind | inf | 329 | 91 | 38 | 0 | 0 |
| osm (committed) | forecast-aware | 0 | 351 | 86 | 19 | 0 | 2 |
| osm (committed) | forecast-aware | 1 | 351 | 86 | 19 | 0 | 2 |
| osm (committed) | forecast-aware | inf | 351 | 86 | 19 | 0 | 2 |
| designated (primary) | fire-blind | 0 | 347 | 75 | 36 | 0 | 0 |
| designated (primary) | fire-blind | 1 | 347 | 75 | 36 | 0 | 0 |
| designated (primary) | fire-blind | inf | 347 | 75 | 36 | 0 | 0 |
| designated (primary) | forecast-aware | 0 | 358 | 84 | 14 | 0 | 2 |
| designated (primary) | forecast-aware | 1 | 358 | 84 | 14 | 0 | 2 |
| designated (primary) | forecast-aware | inf | 358 | 84 | 14 | 0 | 2 |
| union | fire-blind | 0 | 347 | 77 | 34 | 0 | 0 |
| union | fire-blind | 1 | 347 | 77 | 34 | 0 | 0 |
| union | fire-blind | inf | 347 | 77 | 34 | 0 | 0 |
| union | forecast-aware | 0 | 358 | 84 | 14 | 0 | 2 |
| union | forecast-aware | 1 | 358 | 84 | 14 | 0 | 2 |
| union | forecast-aware | inf | 358 | 84 | 14 | 0 | 2 |
| designated_plus_tsunami (sensitivity) | fire-blind | 0 | 343 | 94 | 21 | 0 | 0 |
| designated_plus_tsunami (sensitivity) | fire-blind | 1 | 343 | 94 | 21 | 0 | 0 |
| designated_plus_tsunami (sensitivity) | fire-blind | inf | 343 | 94 | 21 | 0 | 0 |
| designated_plus_tsunami (sensitivity) | forecast-aware | 0 | 360 | 82 | 14 | 0 | 2 |
| designated_plus_tsunami (sensitivity) | forecast-aware | 1 | 360 | 82 | 14 | 0 | 2 |
| designated_plus_tsunami (sensitivity) | forecast-aware | inf | 360 | 82 | 14 | 0 | 2 |

The forecast-only bucket (`naive_into_FA_safe`) of each arm, forecast-aware route:

- **osm (committed)** (n = 42): m=0: adm 9 / indet 16 / inadm 17; m=1: adm 9 / indet 16 / inadm 17; m=inf: adm 9 / indet 16 / inadm 17
- **designated (primary)** (n = 16): m=0: adm 0 / indet 12 / inadm 4; m=1: adm 0 / indet 12 / inadm 4; m=inf: adm 0 / indet 12 / inadm 4
- **union** (n = 21): m=0: adm 0 / indet 13 / inadm 8; m=1: adm 0 / indet 13 / inadm 8; m=inf: adm 0 / indet 13 / inadm 8
- **designated_plus_tsunami (sensitivity)** (n = 9): m=0: adm 0 / indet 5 / inadm 4; m=1: adm 0 / indet 5 / inadm 4; m=inf: adm 0 / indet 5 / inadm 4

### 3.4 Overlap between the designated sites and the OSM refuges (§2.6)

- **designated**: 68 designated points inside the walk box; **1** of them snap to a walk-graph node that is already in the OSM arm's shelter-node set (1.5 %). Distance to the nearest OSM refuge POI: min 34 m, median 1329 m, max 6646 m; 3 within 100 m, 14 within 250 m, 19 within 500 m. <!-- collision-ok: 1.5 — a SHARE OF DESIGNATED SITES in per cent, not a walk time in minutes; it collides by digits only with the registered l0_walk_time_to_refuge_* medians -->
- **designated_plus_tsunami**: 139 designated points inside the walk box; **1** of them snap to a walk-graph node that is already in the OSM arm's shelter-node set (0.7 %). Distance to the nearest OSM refuge POI: min 34 m, median 1015 m, max 6646 m; 3 within 100 m, 21 within 250 m, 41 within 500 m. <!-- collision-ok: 0.7 — a SHARE OF DESIGNATED SITES in per cent, not a walk time in minutes; it collides by digits only with the registered l0_walk_time_to_refuge_* medians -->

### 3.5 The reading rule (§2.6), applied

- |Δ `naive_into_FA_safe`| = **26** against a threshold of 14.00 (a third of the OSM arm's 42).
- |Δ `no_safe_route`| = **0** against a threshold of 0.67 (a third of the OSM arm's 2).

**Verdict: the partition depends on refuge provenance.**

### 3.6 What this run does NOT show

- It says nothing about the paired fire-blind versus forecast-aware contrast. Both arms of that contrast route to the same refuge set, whichever set it is, so changing the refuge set moves both together. This is a sensitivity of the ABSOLUTE rates only.
- None of the 사물주소 categories is a designated **wildfire** refuge — they are earthquake, tsunami and heat. Whether a listed site would be opened, staffed or large enough during a spring wildfire is unknown (NH-012 b, `docs/juso_yeongdeok.md`).
- It does not say which refuge set is correct. The designated list is an agency record of 2025-03-01; OSM is a volunteer record of 2026-07-24. Neither was verified on the ground.
- The grading inherits every assumption of `docs/regrade_three_way.md` A1–A6: fire exposure under the model's own admissibility rule rather than road passability, never-detected cells assumed unaffected, node sampling only. No count here is a safety rate.
- Nothing here is registered in `docs/NUMBERS.json` and nothing is on a judge-facing surface.

## 4. Reading (written after the run; §2 and §3 are unedited)

**The partition depends on refuge provenance, and the dependence is large.** The
forecast-only bucket — the project's headline count, the 42 — falls to **16** when the
router aims at the agency-designated sites instead of the OSM points, a drop of 26 against
a pre-registered threshold of 14. The `no_safe_route` count is **2** in every arm.

**The mechanism is density, not disagreement.** The two provenances are not naming the
same places: only **1** of the 68 designated points inside the walk box snaps to a node
already in the OSM shelter set, and the median designated site is 1.3 km from the nearest
OSM refuge POI. The designated set puts **68** shelter nodes on the graph where the OSM
set puts 46, spread differently, so more origins have a refuge whose shortest walk never
enters the forecast hazard at all — they move from the forecast-only bucket into
`both_safe` (414 → 440). The `union` arm sits between the two (21), and the tsunami
sensitivity arm, with 131 nodes, drives the bucket down furthest (9). **The direction is
monotone in refuge density**, which is the reading to hold: a denser refuge set gives the
fire-blind router more chances to be accidentally right, so the forecast's measured
advantage shrinks.

**What this does and does not do to the project's claim.** It does not touch the paired
contrast: in every arm the fire-blind route is the one that enters the forecast hazard and
the forecast-aware route is the one that does not, on the same refuge set, and the
forecast-aware router is never worse. What it does is put a number on how conditional the
*absolute* rate is. 42/458 = 9.2 % is not a property of 영덕; it is a property of 영덕
**with the OSM refuge set**. On the designated set the same quantity is 16/458 = 3.5 %.
Any sentence that quotes the 42 as a count of households the forecast saves must carry the
refuge set it was measured on.

**The observed grading moves the same way and not in the forecast's favour.** Of the OSM
arm's 42 forecast-only routes, 9 are admissible under every declared bound; of the
designated arm's 16, **none** is — they are 12 indeterminate and 4 inadmissible for all.
The forecast-only class on the designated set is smaller *and* less of it survives the
observation. Arm for arm, though, the forecast-aware route is graded better than the
fire-blind one under every refuge set (e.g. designated: 14 inadmissible versus 36), so the
direction of the forecast's help is the one thing all four arms agree on.

**The honest summary for the paper**: the direction of the result is robust to refuge
provenance; its magnitude is not, and the OSM set is the one that flatters it.
