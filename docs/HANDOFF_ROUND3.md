# Round-3 handoff

**Read this file alone and you can continue.** Written 2026-08-02.

| | |
|---|---|
| branch | **`round3-dev`** (tracks `origin/round3-dev`) |
| HEAD | `75f347a` + this commit |
| baseline tag | **`round2-submitted`** = `4e9dfe3` — the submitted state |
| environment | conda env **`wfg311`**, Python 3.11.15 — see [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| suite | **544 passed, 2 skipped, 0 failed** |
| registry | [`NUMBERS.json`](NUMBERS.json) — 103 entries, 87 reproducible |
| OSM regions | 3 acquired + snapshotted (`MANIFEST.json`, 64 entries) |
| config hash | `51ec446843b6…` — moved from `0b6eb481177a…` by PURE ADDITION at `cc41f12` (two new PHASE-5 keys, no existing value changed). `NUMBERS.json.config_hash_note` records this. |

`docs/figures/*.png` carry three known uncommitted modifications. **Leave them
unstaged**; every commit here used `git add -A -- . ':!docs/figures/*.png'`.

---

## 1. What is done

| PHASE | State | Commit |
|---|---|---|
| 0 — freeze | done — tag `round2-submitted`, branch `round3-dev` | — |
| 1 — reproducibility infrastructure | done | `a465128`, `9de5eae` |
| 2 — DEM slope on OSM edges | done | `b7fc593` |
| 2-C-1 — time-minimising objective | done | `938cd6d` |
| 2-C-2 — w(t) budget sweep | done | `cbc9b45`, `322bfb8` |
| 2-C-3 — hazard time resolution | **NOT started**, deprioritised | — |
| 3 — operational outputs | done | `8e6b60e` |
| 3-B — full-coverage re-run | done | `6612271` |
| sparsity analysis | done | `bc3dfdd` |
| 4 — live-operation feasibility | **NOT started** | — |
| 5 — multi-region | STEP 0–4 done | `466884f`, `5fe86db`, `a0eaf07`, `cc41f12`, `79138d0`, `a32da6b` |
| **canonical-hazard reconstruction** | **done — steps 1–4. See §2-A.** | `141b035`, `9ba83b4`, `6df4fcf`, `05fbfca`, `ed5e6b0`, `815dc02`, `a9b79cb`, `c8851d8`, `75f347a` |
| 6 — delivery layer | **NOT started. This is the next phase.** See §9. | — |

---

## 2. Outputs and headline numbers

> ⚠ **Several subsections below are SUPERSEDED by §2-A.** They record what was
> measured on `routing_demo.npz`, which turned out to be the output of a
> reverted run. Each is marked. The Round-2 figures, the 439 series and the AUC
> are **not** affected.

### The Round-2 figures — verified, mostly NOT reproducible

All 16 declared values matched their artifacts exactly (16/16).

| value | artifact | reproducible |
|---|---|---|
| mean-of-folds AUC **0.890** ± 0.107 | `spread_v2_lofo.json/per_fire_auc` | **yes, bit-identical** |
| **439** = 272 + 167, **143** / **24**, **57** of 143 | `rescue_routing.json` | no |
| 6.1173 → 1.7112 = **72.0 %** | `rescue_routing.json` | no |
| walk-failure **11.4 %** (f=0.3, c=0.5) | `rescue_verify_fc.json` | no |
| **459** = 438 + 18 + 3 | `real_roads_real_hazard.json` | no |
| npz sha256 `5bed5026…18da58` | `routing_demo.npz` | no |

**"Not reproducible" ≠ "wrong".** Three git-ignored inputs changed after the
results were committed: the OSM graph (2026-07-24, **unrecoverable**), the
Overpass responses, and `fire_manifest.json`'s bbox (2026-07-23, recoverable).
See [`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md) and
[`grid_extent.md`](grid_extent.md).

### PHASE 2 — slope ⚠ SUPERSEDED, see §2-A step 2

`real_roads_real_hazard_slope_{30,60,90}.json` · [`slope_integration.md`](slope_integration.md)
Canonical-field values: flat 415/41/2, 30 m 413/42/3, 60 m 414/42/2, 90 m
415/41/2 — and the null result survives.

* 60 m sampling is canonical; **+26.6 %** mean walk time, mean \|slope\| 8.18 %,
  directional asymmetry **20.0 %** of flat time.
* **Counts unchanged**: 440 / 17 / 3 flat *and* slope. A null result, and the
  diagnosis is that the instrument cannot see the effect — not that there is none.
* The committed 407-origin run uses `dz = abs(...)`, i.e. it already applies the
  **conservative uphill-always** convention without ever saying so. Documented;
  the 407 figures were not restated.

### PHASE 2-C-1 — routing objective ⚠ SUPERSEDED, see §2-A step 3

`routing_objective_experiment.json`
The route-level findings below reproduce on the canonical field to three
significant figures; only the bucket counts move.

* `naive_route(objective="time_min")` added; `length_m` remains the default.
* **150 of 460 routes change** (32.6 %); longest walk 444 → 353 min (−91.3 min).
* Flat control changes 0 of 460 — so the 150 are attributable to terrain.
* Bucket counts still unchanged.

### PHASE 2-C-2 — w(t) ⚠ SUPERSEDED, see §2-A step 3

`budget_sweep_experiment.json` · [`budget_sweep.md`](budget_sweep.md)
Canonical-field w: 56.55 / 40.17 / 28.38 / 22.27 / **9.61 %**; ratio 5.89×, not
12.6×; the 600-minute budget still does not bind.

| budget | distance | time | Δ |
|---|---:|---:|---:|
| 30 min | **55.00 %** | 54.78 % | +1 |
| 60 min | 38.26 % | 37.39 % | +4 |
| 90 min | 26.09 % | 25.65 % | +2 |
| 120 min | 19.78 % | 19.13 % | +3 |
| 600 min | **4.35 %** | 5.00 % | −3 |

* Failure rises **12.6×** as the budget tightens. Closes the Round-2 Ⅴ-2
  future-work item.
* The **+3 hazard entries belong to the fire-blind baseline, not to the proposed
  system** — `future_aware_route` never enters the hazard (`both_enter` = 0 at
  every budget, asserted in tests). Do not restate this as a cost of the system.
* Sixth category **`fa_exceeds_budget`** added, strictly additive: at 600 min it
  is 0 and the five originals are still 440/17/3/0/0.

### PHASE 3 / 3-B — operational outputs

`outputs/dispatch/` (44 points) · `outputs/dispatch_full/` (174 points, 3 eps
values) · `rescue_routing_full.json` (441 origins fully serialised)

* Three formats: SMS draft, A4 sheet for the 이장, 마을방송 script.
* **Nothing is ever sent**: `sms.send()` requires a positional `approval_token`
  and `DEMO_MODE` is on unless the env var is exactly `"0"`.
* Full re-run reproduces drift arm B exactly: **441 / 174 / 32**.

### Network drift, sparsity, coverage

* `network_drift_experiment.json` — a **0.047 %** walk-node change moved the
  binary verdict **33 %** (24→32) while the exposure contrast moved **0.56 pp**.
  Binary verdicts are network-sensitive; paired contrasts are not.
* `cluster_sparsity.json` — rescue-needing origins are **2.13× more dispersed**;
  singleton fraction never below **49.2 %** at any non-collapsed radius.
* [`walk_bbox_coverage.md`](walk_bbox_coverage.md) — **the Yeongdeok walk bbox
  covers only 32.6 % of its own predicted fire core** (the 50.4 % figure was
  measured against the reverted run's four-times-smaller core). The origins are
  a spatially biased sample; the direction of the bias is unmeasured. **Not
  fixed — see §2-A.**

### PHASE 5 STEP 2-1 — per-region forward simulation

`forward_sim_regions.json`, `hazard_uiseong_andong_2025.npz`,
`hazard_uljin_samcheok_2022.npz` · [`forward_sim_regions.md`](forward_sim_regions.md)

Re-simulated 2026-08-02 on the corrected DEMs; the values below are the current
ones. Pre-fix they read 2,375 ha / +79 % and 6,575 ha / +155 %.

| region | reported | 12-h envelope | ratio | core growth |
|---|---:|---:|---:|---:|
| Yeongdeok 2025 | 3,800 ha | 27,900 ha | 7.34× **over** | +1.2 % ⚠ |
| Uiseong-Andong 2025 | 45,000 ha | 3,275 ha | 0.07× **under** | **+147.2 %** |
| Uljin-Samcheok 2022 | 16,302 ha | 7,300 ha | 0.45× under | **+183.5 %** |

The bias **flips sign**, so no normalisation removes it. Report raw values with
envelope area as a column. This is a limit of the forward simulation, **not** of
the routing.

⚠ The 27,900 ha above comes from `yeongdeok_forward_sim.json`, a **different**
simulation artifact from the field the routing reads. Under one definition
(p ≥ 0.5, final slice, from each region's routing npz) the areas are
**25,900 / 3,275 / 7,300 ha** — a 7.91× spread. (Yeongdeok's 6,100 ha and its
+1.2 % core growth above are the REVERTED run's field; on the canonical field
they are 25,900 ha and +316.1 %. §2-A.) Use one definition throughout;
`multi_region_comparison.json` does.

### PHASE 5 STEP 2-3 / 4 — multi-region routing and comparison

`real_roads_real_hazard_{uiseong_andong_2025,uljin_samcheok_2022}.json`,
`multi_region_comparison.json` · [`multi_region.md`](multi_region.md)

Identical parameters everywhere (slope 60 m, distance objective, 600-min budget,
stride 18, `osmnx` 2.0.7). Yeongdeok is now **re-run on the canonical field**
(§2-A); the multi-region runner still refuses `--regions yeongdeok_2025` and
every runner exits 4 if a protected artifact moves.

| region | origins | both_safe | FA-only | no_safe | over budget | FA-only % | coverage | depots |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Yeongdeok 2025 | **458** | **414** | **42** | **2** | 0 | **9.17 %** | **32.6 %** | 4 |
| Uiseong-Andong 2025 | 368 | 263 | 91 | 12 | 2 | **24.73 %** | 99.2 % | **0** |
| Uljin-Samcheok 2022 | 393 | 377 | 3 | 10 | 3 | **0.76 %** | 81.5 % | 4 |

⚠ Current values, after BOTH corrections: the DEM fix (which moved
Uiseong-Andong from 346/13/0 and 3.53 %) and the canonical-field switch (which
moved Yeongdeok from 440/17/3 and 3.70 %). See §2-A,
[`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) and
[`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json).

⚠ 영덕 수치는 정본 화재 핵심의 **32.6 %만 덮는** 보행망에서 산출되었습니다.
나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도
알려져 있지 않습니다. 지역 간 비교에서 영덕 행을 인용할 때는 이 열을 반드시
함께 제시하십시오. 짝지어진 대비는 영향받지 않습니다.

Both new regions **reproduce exactly** (re-run into a scratch dir: every count,
every bucket membership list, every slope statistic identical).

Four things that did **not** carry over from Yeongdeok:

1. **`fa_exceeds_budget` is no longer empty at 600 minutes** (9 and 4). The
   three-way split therefore does not sum to N outside Yeongdeok. Carry the
   column.
2. **Slope moves the counts.** PHASE 2's null result was Yeongdeok-specific. And
   it is *not* because the new regions are steeper — Uiseong-Andong is the
   gentlest of the three (mean |slope| 6.36 % vs 8.18 %) and Uljin-Samcheok is
   close to Yeongdeok. Slope now moves origins into `no_safe_route`, not only
   into `fa_exceeds_budget`.
3. **The core-growth hypothesis orders no better than chance at n = 3.**
   Growth +1.2 / +147.2 / +183.5 % against FA-only 3.70 / 24.73 / 0.76 %
   (ρ = −0.5). Two regions support it strongly, one contradicts it strongly.
   What IS established: on a field that actually advances, the same method and
   parameters give a future-aware-only share nearly **seven times** Yeongdeok's,
   so the "quasi-static core" limitation was real and understated the benefit.
   What is NOT established: that the benefit rises with fire speed —
   Uljin-Samcheok advances fastest and benefits least.
   ⚠ The earlier reading (ρ = −1, "fire-blind risk is flat at 4.35/3.53/3.31 %")
   was an artifact of the defective DEM. It now reads 4.35 / **27.99** / 3.31 %.
4. **The Uljin-Samcheok DEM was filling the East Sea with a ramp to −497 m**,
   and that region is in the shared leave-one-out training set for every other
   fire — which is why fixing it moved *Uiseong-Andong* sevenfold.
   [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md). Re-acquired,
   re-simulated, re-routed, snapshotted; both regions now read 0.000 % nodata.

---

## 2-A. The canonical-hazard reconstruction — read this before any number

This is the largest thing that happened in Round 3, and it changes which
artifacts are current.

### How it was found

1. **PHASE 5 STEP 2-3** measured Uljin-Samcheok's walk nodes falling outside its
   DEM. The DEM was re-acquired, and the fresh raster showed the old one had
   **filled the East Sea with a ramp to −497 m** — 49 % of the raster
   ([`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md)). Because the model
   trains leave-one-fire-out on **one shared dataset**, that fiction was
   training data for every other fire.
2. Measuring what that cost required re-running the LOFO. The control arm — the
   same run against the *pre-fix* rasters — **reproduced the committed
   `spread_v2_lofo.json` on every field**, which is what made everything after
   it readable.
3. The Yeongdeok forward-sim measurement then exposed a second, bigger problem:
   `routing_demo.npz` (core 241 → 244 cells) and `yeongdeok_forward_sim.json`
   (6,225 → 27,900 ha) disagree, and a re-run reproduces only the JSON.
4. **The investigation settled it** ([`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json)).
   At commit `01099bf` (2026-07-20) all four artifacts agreed — the JSON carried
   exactly the npz's areas, and `routing_demo.json` carried exactly the npz's
   stored `origin_xy`. Commits `2f7f555` / `ccb0865` **reverted that state on
   2026-07-21**, restoring three of the four. The npz was committed separately
   on 2026-07-24 and still holds the reverted run's field. That run's own
   <!-- forbidden-ok: 0.867 -->
   figures — **0.867 / 138,619 / 2,731** — are all on the HARD forbidden list as
   retired pre-correction values (quoted here as the identifying fingerprint of
   the reverted run; never as a current claim).
   Ruled out along the way: boundary truncation (an order of magnitude too
   small) and every forward-sim parameter (`advance_threshold` 0.30 → 0.99 still
   gives 672 cells, never 244). The model code is byte-identical; the variable
   was the input data.
5. **A canonical field was built** and the affected experiments re-run: steps
   1–4 below.

### What changed, and what did not

| | verdict |
|---|---|
| **Yeongdeok 459-series counts** | **CHANGED.** 440 / 17 / 3 → **414 / 42 / 2**. FA-only share 3.70 % → **9.17 %**. Same network, same parameters — the hazard field alone. |
| **Yeongdeok core growth** | **CHANGED.** +1.2 % → **+316.1 %**. The "quasi-static core" limitation was a property of the reverted field, not of the fire. |
| **headline AUC 0.890** | **UNAFFECTED.** Correcting the DEMs moves mean-of-folds +0.0048 and pooled −0.0017. The `elev_above_source_m` importance rank falls 8 → 15 and far-band AUC falls 0.0357; those are the real changes. `spread_v2_lofo_dem_corrected.json`. |
| **the "sea cells inflate the AUC" hypothesis** | **REFUTED.** Only 99 of 151,904 rows have elevation < 0, minimum −6.9 m, none positive — candidates are drawn within 6 km of the fire, so open ocean is never sampled. Removing them *raises* the AUC; they were hard negatives. |
| **the 439 series** | **UNAFFECTED.** 439/167/24, w ≈ 11.4 %, the 72.0 % exposure reduction and the dispatch outputs come from a different pipeline on a synthetic hazard envelope. Different denominator, lineage and field. |
| **network and terrain quantities** | **UNAFFECTED.** Traversal time +26.594 %, mean \|slope\| 8.18 %, 150 changed routes, the 91.3-minute longest-walk saving — all reproduce to three significant figures, because none depends on the fire. |

### Steps 1–4, and what each found

| step | result |
|---|---|
| **1 — multi-region table rebuilt** | The table had been mixed: two freshly simulated regions beside a Yeongdeok row from the reverted run. Now one lineage. Envelope-area spread 2.23× → **7.91×**. The long-standing 27,900 ha conflict **dissolved** — step-0 area is 6,225 ha in both the canonical field and `yeongdeok_forward_sim.json`; `routing_demo.npz` was the outlier. |
| **2 — slope sweep 30/60/90** | **The PHASE-2 null survives.** Three origins move at *some* spacing, **none at all three**; movement is monotone in the sampling-induced time penalty (+40.4 / +26.6 / +21.0 %), which is the signature of sampling noise. Future-aware routes change for 33–48 % of origins while the verdict does not: terrain changes *how* people walk, not *whether* they reach safety. |
| **3 — objective 2×2 + budget sweep** | Route-level findings reproduce to three significant figures (150 routes, −91.3 min). **The 600-minute budget still does not bind** (`fa_exceeds_budget` = 0). Failure ratio 12.65× → **5.89×** because the FLOOR rose (w(600) 4.35 → 9.61 %), not because the ceiling fell. Baseline hazard entry 20 → 44 — still the fire-blind baseline's, never the system's (`both_enter` = 0 at every budget). |
| **4 — coverage** | **32.6 %**, down from 50.4 %. The bbox did not move; the core quadrupled. |

### ⚠ The coverage decision — settled 2026-08-02, do not relitigate

**Yeongdeok's walk bbox is NOT re-drawn.** The estimate is in
[`yeongdeok_bbox_reacquisition_estimate.json`](../data/processed/yeongdeok_bbox_reacquisition_estimate.json):
a covering bbox would be 1,993 km² (2.14×), ~18,100 nodes, ~980 origins, ~26 MB
— all cheap. What decided it is that **it does not fit the simulation grid**:
west clearance −1.5 km against a 5 km requirement, on a canvas already extended
0.05° west. Meeting it needs ~6.5 km more canvas, which means re-simulating the
hazard field, which means re-running steps 1–3 against a field that may itself
differ. The bbox and the canvas are coupled, and the coupling runs the expensive
way.

Re-acquiring would break: continuity with the committed **439 series**; the
committed **459 series** (unreproducible in principle, not just in practice);
**every Round-3 result** (all on 458 origins); the multi-region comparison's
"identical rule, three regions" design, since Yeongdeok alone would be drawn by
an envelope-derived rule; and any submission figure citing 439, 459, 407,
143/24, 72.0 %, 11.4 % or the dispatch counts.

The price of not re-acquiring is **one thing only**: absolute rates are rates on
the covered third. **Paired contrasts are unaffected** — both arms share the
origins, so the sampling frame cancels — and that is most of what the project
reports.

**The caveat, to be carried by every absolute Yeongdeok rate (verbatim):**

> 영덕 수치는 정본 화재 핵심의 **32.6 %만 덮는** 보행망에서 산출되었습니다.
> 나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도
> 알려져 있지 않습니다. 지역 간 비교에서 영덕 행을 인용할 때는 이 열을 반드시
> 함께 제시하십시오.

It is applied mechanically: `build_numbers.py` appends it to all 27 registry
entries that are absolute Yeongdeok rates or raw origin counts, and **not** to
paired contrasts or to network/terrain quantities. It also appears in
`multi_region.md` (×2), `budget_sweep.md`, `slope_integration.md` and
`walk_bbox_coverage.md`.

---

## 3. Decisions already made — do not relitigate

| decision | why |
|---|---|
| **Synthetic terrain/hazard path is excluded** | `build_real_demo` fabricates a coastline on the eastern 12 % of any bbox. Uiseong-Andong is inland; it would invent a sea that does not exist. |
| **PHASE 5 extends the 459 series, not the 439 series** | The 459 path (`real_roads_real_hazard`) consumes a REAL hazard field. Consequence: 3 buckets, not 4, so the cross-region metric is **"share of origins safe only on the future-aware route"** (Yeongdeok **42/458 = 9.17 %** on the canonical field) — **not w**. Say so in `multi_region.md`. |
| **Simulation canvas extended southward for the two new regions only** | Their ignition points sit near their manifest bbox's southern edge; Uljin's walk bbox fell 4.44 km *outside* its hazard grid, where nodes read p=0 and look safe. Extension biases nothing. `config: grid.simulation_bbox_extension` — Uiseong 0.05°, Uljin 0.09°, Yeongdeok 0.0. **The envelope is bit-identical before and after**, so nothing was being clipped. |
| **Yeongdeok is NOT re-acquired** | Re-confirmed 2026-08-02 on numbers, not discomfort. Coverage is **32.6 %** (not the superseded 50.4 %) and is reported as a covariate. The decisive fact is the canvas coupling, not the download cost. See §2-A. |
| **stride 18, not 3** | `rescue_demo.py:325` replaces the synthetic default 3 with `REAL_OSM_SCAN_STRIDE = 18` on the OSM path. Same stride for all regions; origin counts differ with road density, and that difference is part of the comparison. |
| **`osmnx == 2.0.7` pinned** | Matches `created_with` inside the snapshot graphml. Floating it would put a second variable into every before/after comparison. `make env-check` fails on drift. |
| **Envelope size differences are NOT normalised** | Choosing a denominator would be a new arbitrary decision. Report raw, with envelope area as a column. |
| **Uiseong-Andong runs without depots** | Its 919 km² ignition-centred box contains **no** `amenity=fire_station` in OSM (the wider 3,926 km² manifest box contains six). Widening the tag set or the bbox would break the identical-rule requirement and destroy the comparison. The cross-region metric is resident-side, so it is unaffected; the responder side is recorded as `responder_side_available: false` — **never as zero dispatches**. |
| **OSM cache is per region** | `RescueConfig.osm_cache_path` = `{osm_cache_dir}/{region_name}/`. Fixed filenames previously meant a second region's fetch would overwrite the first. |

---

### PHASE 5 STEP 2-2 — acquisition complete

All three regions are on disk under `data/cache/osm/{region}/` and snapshotted
(`MANIFEST.json`, 64 entries). Provenance in `osm_acquisition.json`, covariates
in `osm_completeness.json`.

| region | area | road km/km² | nodes/km² | geometry | highway | shelter /100 km² | **depot /100 km²** | responder side |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Yeongdeok 2025 | 931 | 1.733 | 9.07 | 67.4 % | 100 % | 5.37 | 0.43 | available |
| Uiseong-Andong 2025 | 919 | **2.332** | 7.27 | **78.6 %** | 100 % | 3.70 | **0.00** | **NOT APPLICABLE** |
| Uljin-Samcheok 2022 | 924 | 1.601 | 7.90 | 68.3 % | 100 % | 2.81 | 0.43 | available |

Relative to Yeongdeok: road density 1.35× / 0.92×, node density 0.80× / 0.87×,
shelter density 0.69× / 0.52×. **Carry this table beside every cross-region
routing number** — otherwise "regions differ" cannot be told from "mapping
differs".

⚠ Write the depot fact as: *발화점 중심 919 km² 범위 내에 OSM에 매핑된
fire_station이 없으며, 더 넓은 3,926 km² 범위에는 6곳이 있습니다.* **Never** as
"Uiseong-Andong has no fire stations."

## 4. Open items

| item | why it is open |
|---|---|
| **PHASE 6 — delivery layer** | **This is the next phase.** Not started. See §9. |
| **`spread_v2_lofo.json` was trained on the defective Uljin-Samcheok DEM** | **This is the next decision.** The headline mean-of-folds AUC is built over the six-fire set that includes `uljin_samcheok_2022`, whose raster filled the sea with a ramp to −497 m, so EVERY fold — including Yeongdeok's — trained on it. The same applies to `routing_demo.npz` and every Yeongdeok number derived from it. **Nothing has been re-run**: those are committed Round-2 artifacts protected by §5.2, and re-running them changes figures the submission cites. The effect is unmeasured and could go either way. [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) §3. |
| ~~DEM re-acquisition~~ — **DONE 2026-08-02** | Both regions re-acquired, validated, snapshotted, re-simulated and re-routed; nodata 0.000 %, sim-grid mean-fill 0.00 %, both pass the gate with no acknowledgement flag. Superseded text: **This was the next action.** Two gaps, one fix. (a) `uljin_samcheok_2022_dem.tif` spans 36.85–37.45 °N while its walk bbox starts at 36.81 °N: **405 of 7,300 walk nodes (5.55 %)**, 6.17 % of elevation samples, timed FLAT. (b) BOTH new regions' simulation canvases were extended south past their DEMs in `a0eaf07`, so **10.0 %** (Uiseong-Andong) and **15.6 %** (Uljin-Samcheok) of simulation cells carry a MEAN-FILLED elevation — hazard is p = 0 in every one of them, so the committed fields are clean, but the fill was silent. `scripts/acquire_region_dem.py` is written, targets the UNION of walk bbox + simulation canvas + existing raster, validates coverage before installing, and refuses to mix providers. It needs `OPENTOPOGRAPHY_API_KEY` (env or the git-ignored `.env`); a keyless request is HTTP 401, confirmed 2026-08-02. **Do not route on a partial DEM and do not substitute AWS-Mapzen tiles.** |
| ~~Promote the hypothesis-refutation decomposition~~ | **Withdrawn.** The "fire-blind risk is near-constant" finding was an artifact of the pre-fix fields; it now reads 9.61 / 27.99 / 3.31 %. §2-A. |
| Which field to PUBLISH | Both `routing_demo.npz` (reverted run) and `routing_demo_canonical.npz` are in the tree with their provenance. The documents lead with the canonical one; **the submission materials have not been touched** and the choice of what to publish is the user's. |
| Shelter-density experiment (within-region refuge decimation) | Requested 2026-08-02 as a way around n = 3: hold terrain and road network fixed, remove refuges at 100/75/50/25 % with repeats, and measure FA-only and `no_safe_route`. Sequenced after the DEM fix; the user will confirm before it starts. |
| PHASE 4 — live-operation feasibility | Never started. Investigation only, no code. |
| PHASE 2-C-3 — hazard time resolution | Deprioritised: `no_safe_route` already moved 3→18 once the budget bound, so the budget was the main blocker. |
| `routing_demo.npz` not reproducible | Cause fully identified and **recoverable** — pin the grid to `bbox.fire_acquisition`. Not done: it would change results. |
| 407-run directionality | Uses `abs(dz)` (conservative). Documented, not changed. |
| `unclassified` in tight-budget buckets | Fixed by `fa_exceeds_budget`. No action. |
| Yeongdeok walk-bbox coverage 50.4 % | Accepted and reported, not fixed. See §3. |

---

## 5. ⚠ Never do these

1. **Never push to `Main`.** All work stays on `round3-dev`. Merging is the
   user's decision.
2. **Never modify a committed artifact.** Especially
   `data/processed/rescue_routing.json` (sha256
   `92248e5a78f930cf68bdd6c48155da8f49a1a8f3c6cebc8c8dea2c5eb98ecc3b`, pinned in
   `tests/test_full_coverage.py`), `real_roads_real_hazard.json`,
   `spread_v2_lofo.json`, `routing_demo.npz`. New results get **new filenames**.
3. **Never regenerate `docs/figures/*.png`.** The submitted documents cite them.
4. **Never re-acquire Yeongdeok's OSM data.** See §3.
5. **Never average, reconcile or substitute the two number sets.** Committed
   439/167/24 and drift 441/174/32 are both correct for their inputs. Registry
   `forbidden_phrasings` enforce this.
6. **Never proceed with a partial graph.** If Overpass fails after 3 retries
   (30/60/120 s backoff), discard the partial result, report, and stop.
7. **Never compare `w` across regions without the OSM-completeness covariates.**
   Road density, node density, geometry share, highway-tag share, POI density —
   otherwise "regions differ" is indistinguishable from "mapping differs".
8. **Never write acquired data only to `data/cache/`.** Snapshot it immediately;
   `data/cache/**` is git-ignored and that is exactly how the Jul-23 graph died.
9. **Never edit `data/raw/firms_data/fire_manifest.json`.** It is the acquisition
   record. Simulation-side changes belong in `config`.
10. **Never quote a short-budget `w` without its budget.** 55 % alone is wrong.
11. **Never write "Uiseong-Andong has no fire stations."** Say: no
    `amenity=fire_station` is mapped in OSM inside its 919 km² walk bbox; the
    wider 3,926 km² manifest bbox contains six.
12. **Never report a cross-region routing number without the completeness
    covariates** from `osm_completeness.json`.
13. **Never call the cross-region metric `w`.** It is the 459-series FA-only
    share (3 buckets). `w` is a 439-series quantity built on a synthetic hazard
    envelope and cannot be computed inland at all.
14. **Never rank the three regions on the FA-only column alone**, and never
    write "correlates" from it. n = 3, three covariates move together, and the
    two orderings that look strongest (core growth, envelope area) both run
    *against* the naive reading. [`multi_region.md`](multi_region.md) §8.
15. **Never mix envelope-area definitions.** 6,100 / 2,375 / 6,575 ha (p ≥ 0.5,
    final slice, routing npz) is one column; the 27,900 ha figure from
    `yeongdeok_forward_sim.json` is a different quantity. Mixing them turns a
    2.77× spread into a fictitious 12×.
16. **Never quote Uljin-Samcheok's slope arm without its DEM gap** (§4).
17. **Never route on a partial DEM, and never mosaic two DEM providers.**
    `dem.nodata_stop_fraction` makes the first a hard stop (exit 5);
    `--acknowledge-dem-gap` records the override in the artifact rather than
    hiding it, and is only for regenerating a historical result. The second has
    no override at all: OpenTopography SRTMGL1 or nothing.
18. **Never re-run Yeongdeok's 459 series into a committed filename.** The
    canonical re-run has its own file; `run_multi_region_routing.py` still
    refuses the region, and every runner exits 4 if a protected artifact moves.
19. **Never quote an absolute Yeongdeok rate without the 32.6 % coverage
    caveat** (§2-A). `w`, the FA-only share, the 95.5 % rescue rate and the raw
    bucket counts are all rates on the covered third. Paired contrasts and
    network/terrain quantities do NOT need it — the frame cancels.
20. **Never present `routing_demo.npz` and `routing_demo_canonical.npz` as
    versions of the same thing.** The first is the output of a reverted run
    whose own figures are HARD-forbidden; the second is the canonical lineage.
    Say which one produced a number.
21. **Never re-draw Yeongdeok's walk bbox** without re-reading §2-A. It does not
    fit the simulation grid, so it is not a bbox change — it is a full
    re-simulation and a re-run of steps 1–3.

---

## 6. Next session: exact commands

```bash
cd ~/Desktop/Korea\ Code\ Fair/wildfireguardian
conda activate wfg311          # or use /Users/jp/miniforge3/envs/wfg311/bin/python
make all-checks                # 103/103, 544 passed 2 skipped, snapshots intact, env clean
```

**PHASE 5 and the canonical-hazard reconstruction are complete.** The DEMs are
already re-acquired and snapshotted, so both regions now pass the DEM gate with
no flag. To regenerate everything from committed inputs, in dependency order:

```bash
python scripts/build_canonical_hazard.py            # -> routing_demo_canonical.npz
python scripts/run_yeongdeok_canonical_routing.py   # -> the 459 scan on it
python scripts/run_multi_region_routing.py          # the two acquired regions
python scripts/build_multi_region_comparison.py     # re-runs nothing
python scripts/run_yeongdeok_canonical_slope_sweep.py       # step 2
python scripts/run_canonical_objective_and_budget.py        # step 3
python scripts/estimate_yeongdeok_bbox_reacquisition.py     # step 4, no network I/O
python scripts/build_numbers.py && make verify
```

Every one of these digest-checks the protected artifacts before and after and
exits 4 if one moves. None writes to a committed filename.

The runner reads `data/snapshots/` only — never `data/cache/` — and records the
sha256 of every protected Yeongdeok artifact before and after, exiting 4 if one
moved. `--limit-origins` exists for smoke tests and writes under a `_SMOKE_`
prefix so a truncated run can never be mistaken for a result.

The walk bboxes, already acquired, are:

| region | walk bbox (W, S, E, N) | area | envelope coverage |
|---|---|---:|---:|
| `uiseong_andong_2025` | **128.550, 36.200, 128.850, 36.500** | 919 km² | 98.9 % |
| `uljin_samcheok_2022` | **129.170, 36.810, 129.470, 37.110** | 924 km² | 84.8 % |

Rule: ignition-centred, Yeongdeok's 0.30° × 0.30° footprint. Both now clear 5 km
of grid clearance on every side (south +5.81 / +5.73 km).

⚠ **`.gitignore` gained exceptions for the STEP 2-1/2-2 artifacts**
(`forward_sim_regions.json`, `hazard_{region}.npz`, `osm_acquisition.json`,
`osm_completeness.json`). They had been produced but never allow-listed past the
`data/processed/**` rule, so they lived in one working tree only — and every
`mr_*` registry entry depends on them. Without the exceptions `make verify`
fails on a fresh clone with "source_file missing".

**If a fourth region is ever added**, acquisition is
`scripts/acquire_region_osm.py`: `network_type="walk"` and `"drive"`, projected
to EPSG:5179, POIs from `{"amenity": ["shelter","community_centre"],
"leisure":["park"]}` and `{"amenity":"fire_station"}`, into
`data/cache/osm/{region}/`, 3 retries with 30/60/120 s backoff, all-or-nothing.
Then **snapshot immediately** — and check the DEM footprint against the walk
bbox before routing, which is the check Uljin-Samcheok needed and did not get:

```bash
python scripts/snapshot_external.py --preset osm    # extend the preset per region first
python scripts/snapshot_external.py --verify
python scripts/measure_osm_completeness.py
python scripts/run_multi_region_routing.py --regions <new_region>
```

Completeness covariates, for comparison against the Yeongdeok baseline:

| metric | Yeongdeok baseline |
|---|---:|
| bbox area | 931 km² |
| road density | **1.733 km/km²** |
| node density | **9.07 nodes/km²** |
| geometry-bearing edges | 67.4 % |
| highway-tagged edges | 100.0 % |
| shelter POIs | 50 → 5.37 / 100 km² |
| depot POIs | 4 → 0.43 / 100 km² |

---

## 7. `make` targets

| target | verifies |
|---|---|
| `make verify` | every `NUMBERS.json` entry re-derived from its artifact **and** the forbidden-string scan. The headline gate. |
| `make verify-numbers` | registry ↔ artifacts only. Exit 1 on any mismatch. |
| `make check-forbidden` | retired values and misleading terms. HARD = exit 1; LABEL = warning. Scope in [`forbidden_check_scope.md`](forbidden_check_scope.md). |
| `make snapshot` | preserve external inputs (OSM + FIRMS manifests) into `data/snapshots/`. |
| `make snapshot-verify` | re-hash the snapshot store against `MANIFEST.json`, through gzip, including digest-only FIRMS entries. |
| `make env-check` | installed packages vs the exact pins in `requirements.txt`. Catches "declared but not installed" — the Round-2 failure that turned 5 real-OSM tests into silent skips. |
| `make config-hash` | print the current config hash and the file digest. |
| `make test` | pytest. |
| `make all-checks` | everything except `snapshot`. |

Override the interpreter with `make verify PYTHON=/path/to/python`.

---

## 8. Where to read next

| file | for |
|---|---|
| [`NUMBERS.json`](NUMBERS.json) | **every reportable number**, with derivation, caveat and forbidden phrasings. Start here before writing any figure into prose. |
| [`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md) | why the 459 numbers cannot be reproduced |
| [`grid_extent.md`](grid_extent.md) | why the npz hash cannot be reproduced |
| [`network_drift.md`](network_drift.md) | how sensitive each quantity is to the road network |
| [`walk_bbox_coverage.md`](walk_bbox_coverage.md) | the 50.4 % coverage finding |
| [`multi_region.md`](multi_region.md) | **the three-region comparison, its covariates and the rules for quoting it** |
| [`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json) | **why `routing_demo.npz` is the orphan of a reverted run** — archaeology, boundary forensics, parameter sweep |
| [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) | the Uljin-Samcheok sea-fill and what it contaminated |
| [`canonical_hazard.json`](../data/processed/canonical_hazard.json) | how the canonical field was built and why its grid is larger |
| [`forward_sim_regions.md`](forward_sim_regions.md) | per-region hazard fields and the canvas extension |
| [`budget_sweep.md`](budget_sweep.md) | w(t) and the fire-blind-baseline attribution |
| [`slope_integration.md`](slope_integration.md) | slope method, the null result, the 407 convention |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | how to rebuild `wfg311` and why 3.11 |
## 9. PHASE 6 — the delivery layer (NOT started, this is next)

Everything PHASE 6 needs is on disk and verified.

### The canonical hazard field

| | |
|---|---|
| field | **`data/processed/routing_demo_canonical.npz`** |
| arrays | `grid_extent`, `haz_times`, `haz_stack`, `obs_times`, `obs_stack`, `ign_xy` |
| grid | 181 × 156 @ 500 m, `bbox.fire_acquisition` extended **0.05° west** |
| slices | 5 at [0, 180, 360, 540, 720] min |
| core | 249 → 1,036 cells at p ≥ 0.5 (6,225 → 25,900 ha) |
| provenance | [`canonical_hazard.json`](../data/processed/canonical_hazard.json) |
| built by | `scripts/build_canonical_hazard.py` |

⚠ **`data/processed/routing_demo.npz` is the REVERTED run's field.** It is
retained, untouched, because the submission cites its digest. Do not consume it
in new work; do not overwrite it.

The routing run on that field is
[`real_roads_real_hazard_canonical.json`](../data/processed/real_roads_real_hazard_canonical.json)
(`scripts/run_yeongdeok_canonical_routing.py`), 458 origins, 414 / 42 / 2.

### The delivery layer as it stands

| | |
|---|---|
| module | `src/wildfireguardian/delivery/` — `sms.py`, `printable.py`, `broadcast.py`, `villages.py` |
| generator | `scripts/generate_dispatch_outputs.py` |
| outputs | `outputs/dispatch/` (44 points) · `outputs/dispatch_full/` (174 points, 3 eps values) |
| input today | `rescue_routing_full.json` — the **439 series**, on a SYNTHETIC hazard envelope |
| formats | SMS draft · A4 sheet for the 이장 · 마을방송 script |
| safety | `sms.send()` requires a positional `approval_token`, and `DEMO_MODE` is on unless the env var is exactly `"0"`. **Nothing is ever sent.** |

### The design question PHASE 6 has to answer first

The delivery layer currently consumes the **439 series** (synthetic hazard,
n_mobile = 307, four buckets, responder side included). The canonical work is
the **459 series** (real hazard, three buckets, resident side only, no depots
for one region). They are different populations with different bucket
definitions.

So: does PHASE 6 re-point delivery at the 459/canonical series, keep it on the
439 series, or emit both? That is a scoping decision, not an implementation
detail, and it should be made before code is written. Whichever is chosen, the
32.6 % coverage caveat (§2-A) applies to any Yeongdeok count that reaches an
operational sheet.

---

