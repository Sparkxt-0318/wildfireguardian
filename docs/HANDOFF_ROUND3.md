# Round-3 handoff

**Read this file alone and you can continue.** Written 2026-08-02.

| | |
|---|---|
| branch | **`round3-dev`** (tracks `origin/round3-dev`) |
| HEAD | `cc41f12` + this commit |
| baseline tag | **`round2-submitted`** = `4e9dfe3` — the submitted state |
| environment | conda env **`wfg311`**, Python 3.11.15 — see [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| suite | **504 passed, 1 skipped, 0 failed** |
| registry | [`NUMBERS.json`](NUMBERS.json) — 42 entries, 26 reproducible |
| OSM regions | 3 acquired + snapshotted (`MANIFEST.json`, 64 entries) |
| config hash | `0b6eb481177a…` |

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
| 5 — multi-region | STEP 0, 1, 2-1, **2-2 done**; **2-3 (routing) is next** | `466884f`, `5fe86db`, `a0eaf07`, `cc41f12` |

---

## 2. Outputs and headline numbers

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

### PHASE 2 — slope

`real_roads_real_hazard_slope_{30,60,90}.json` · [`slope_integration.md`](slope_integration.md)

* 60 m sampling is canonical; **+26.6 %** mean walk time, mean \|slope\| 8.18 %,
  directional asymmetry **20.0 %** of flat time.
* **Counts unchanged**: 440 / 17 / 3 flat *and* slope. A null result, and the
  diagnosis is that the instrument cannot see the effect — not that there is none.
* The committed 407-origin run uses `dz = abs(...)`, i.e. it already applies the
  **conservative uphill-always** convention without ever saying so. Documented;
  the 407 figures were not restated.

### PHASE 2-C-1 — routing objective

`routing_objective_experiment.json`

* `naive_route(objective="time_min")` added; `length_m` remains the default.
* **150 of 460 routes change** (32.6 %); longest walk 444 → 353 min (−91.3 min).
* Flat control changes 0 of 460 — so the 150 are attributable to terrain.
* Bucket counts still unchanged.

### PHASE 2-C-2 — w(t)

`budget_sweep_experiment.json` · [`budget_sweep.md`](budget_sweep.md)

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
  covers only 50.4 % of its own predicted fire core.** The 459 origins are a
  spatially biased sample; the direction of the bias is unmeasured.

### PHASE 5 STEP 2-1 — per-region forward simulation

`forward_sim_regions.json`, `hazard_uiseong_andong_2025.npz`,
`hazard_uljin_samcheok_2022.npz` · [`forward_sim_regions.md`](forward_sim_regions.md)

| region | reported | 12-h envelope | ratio | core growth |
|---|---:|---:|---:|---:|
| Yeongdeok 2025 | 3,800 ha | 27,900 ha | 7.34× **over** | +1.2 % |
| Uiseong-Andong 2025 | 45,000 ha | 2,375 ha | 0.05× **under** | +79 % |
| Uljin-Samcheok 2022 | 16,302 ha | 6,575 ha | 0.40× under | +155 % |

The bias **flips sign**, so no normalisation removes it. Report raw values with
envelope area as a column. This is a limit of the forward simulation, **not** of
the routing.

---

## 3. Decisions already made — do not relitigate

| decision | why |
|---|---|
| **Synthetic terrain/hazard path is excluded** | `build_real_demo` fabricates a coastline on the eastern 12 % of any bbox. Uiseong-Andong is inland; it would invent a sea that does not exist. |
| **PHASE 5 extends the 459 series, not the 439 series** | The 459 path (`real_roads_real_hazard`) consumes a REAL hazard field. Consequence: 3 buckets, not 4, so the cross-region metric is **"share of origins safe only on the future-aware route"** (Yeongdeok 18/460 = 3.9 %) — **not w**. Say so in `multi_region.md`. |
| **Simulation canvas extended southward for the two new regions only** | Their ignition points sit near their manifest bbox's southern edge; Uljin's walk bbox fell 4.44 km *outside* its hazard grid, where nodes read p=0 and look safe. Extension biases nothing. `config: grid.simulation_bbox_extension` — Uiseong 0.05°, Uljin 0.09°, Yeongdeok 0.0. **The envelope is bit-identical before and after**, so nothing was being clipped. |
| **Yeongdeok is NOT re-acquired** | Would break continuity with every committed 439/459 figure the submission cites. Coverage (50.4 %) is measured and reported as a covariate instead. Not ideal, and the document says so. |
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
| **PHASE 5 STEP 2-2 — OSM acquisition** | **This is the next action.** bboxes are fixed (§6). |
| PHASE 5 STEP 2-3, STEP 4 | Blocked on 2-2. |
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

---

## 6. Next session: exact commands

```bash
cd ~/Desktop/Korea\ Code\ Fair/wildfireguardian
conda activate wfg311          # or use /Users/jp/miniforge3/envs/wfg311/bin/python
make verify && make test       # expect 42/42 and 504 passed, 1 skipped
```

**PHASE 5 STEP 2-3 — routing.** Acquisition is done; the next action is to run
the 459-series routing per region with parameters identical to Yeongdeok (slope
60 m, distance objective, 600-min budget), writing
`real_roads_real_hazard_{region}.json`. Then STEP 4:
`multi_region_comparison.json` + `docs/multi_region.md`.

The walk bboxes, already acquired, are:

| region | walk bbox (W, S, E, N) | area | envelope coverage |
|---|---|---:|---:|
| `uiseong_andong_2025` | **128.550, 36.200, 128.850, 36.500** | 919 km² | 98.9 % |
| `uljin_samcheok_2022` | **129.170, 36.810, 129.470, 37.110** | 924 km² | 84.8 % |

Rule: ignition-centred, Yeongdeok's 0.30° × 0.30° footprint. Both now clear 5 km
of grid clearance on every side (south +5.81 / +5.73 km).

Acquisition must: use `network_type="walk"` and `"drive"`, project to EPSG:5179,
fetch POIs with `{"amenity": ["shelter","community_centre"], "leisure":["park"]}`
and `{"amenity":"fire_station"}`, write into
`data/cache/osm/{region}/`, retry 3× with 30/60/120 s backoff, and **snapshot
immediately**:

```bash
python scripts/snapshot_external.py --preset osm    # extend the preset per region first
python scripts/snapshot_external.py --verify
```

Then the completeness metrics, same method as the Yeongdeok baseline:

| metric | Yeongdeok baseline |
|---|---:|
| bbox area | 931 km² |
| road density | **1.733 km/km²** |
| node density | **9.07 nodes/km²** |
| geometry-bearing edges | 67.4 % |
| highway-tagged edges | 100.0 % |
| shelter POIs | 50 → 5.37 / 100 km² |
| depot POIs | 4 → 0.43 / 100 km² |

Then STEP 2-3 (routing, params identical to Yeongdeok: slope 60 m, distance
objective, 600-min budget, output `real_roads_real_hazard_{region}.json`) and
STEP 4 (`multi_region_comparison.json`, `docs/multi_region.md`).

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
| [`forward_sim_regions.md`](forward_sim_regions.md) | per-region hazard fields and the canvas extension |
| [`budget_sweep.md`](budget_sweep.md) | w(t) and the fire-blind-baseline attribution |
| [`slope_integration.md`](slope_integration.md) | slope method, the null result, the 407 convention |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | how to rebuild `wfg311` and why 3.11 |
