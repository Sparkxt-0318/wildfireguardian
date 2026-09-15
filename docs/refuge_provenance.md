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
