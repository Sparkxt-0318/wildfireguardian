# Round-3 handoff

**Read this file alone and you can continue.** Written 2026-08-02, updated
2026-08-03 (PHASE 6, 7, 8, 12, 13). §1 is the full Round-3 summary; **§13 is
PHASE 13 — international portability, investigated and deliberately stopped.**

| | |
|---|---|
| branch | **`round3-dev`** (tracks `origin/round3-dev`) |
| HEAD | `fb1d011` + this commit |
| baseline tag | **`round2-submitted`** = `4e9dfe3` — the submitted state |
| environment | conda env **`wfg311`**, Python 3.11.15 — see [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| suite | **743 passed, 2 skipped, 0 failed** (was 544; PHASE 6 +44, PHASE 7 +47, PHASE 8 +66, PHASE 12 +21, PHASE 13 +21) |
| registry | [`NUMBERS.json`](NUMBERS.json) — **118 entries, 102 reproducible** (PHASE 13 registered the 15 OSM-completeness covariates that §5 rule 12 names) |
| OSM regions | 3 acquired + snapshotted (`MANIFEST.json`, 68 entries — 64 + 4 FIRMS NRT polls) |
| config hash | `8e29a6cc4a99…` — moved from `05c6feae1dff…` by PURE ADDITION (the PHASE-13 `fuel:` block; a rebuild moved **0** registered values). Earlier lineage below. Superseded text: `05c6feae1dff…` — moved from `faf90a81b7e6…` by PURE ADDITION (the PHASE-6 `live:` block; no existing value changed, and re-running `build_numbers.py` moved **only** the per-entry `config_hash` stamp, 0 values). Earlier lineage: `0b6eb481177a…` → `51ec446843b6…` at `cc41f12`. `NUMBERS.json.config_hash_note` records why this is expected. |

`docs/figures/*.png` carry three known uncommitted modifications. **Leave them
unstaged**; every commit here used `git add -A -- . ':!docs/figures/*.png'`.

---

## 1. Round 3 in full — read this section and you know where things stand

Round 3 started from `round2-submitted` (`4e9dfe3`). Twelve phases later the
project has three things it did not have: **an evidence layer** that can answer
"is this number still true?", **a corrected hazard field** that moved the
headline routing result, and **a working operational path** from a fire being
reported to a dispatch list in about thirty seconds.

### 1.1 The three things that actually changed

**① Every number is now checkable.** `docs/NUMBERS.json` holds all 103
reportable values with their derivation, caveat and forbidden phrasings;
`make verify` re-derives each from its artifact and scans the prose for retired
figures. 87 of 103 are reproducible from current inputs — the other 16 are
*verified but not reproducible*, because the OSM graph behind them was
overwritten on 2026-07-24 and is unrecoverable. That distinction is the point:
"not reproducible" is not "wrong", and before Round 3 there was no way to say
which was which.

**② The hazard field was wrong, and fixing it moved the headline.** Two
independent defects, found in that order:

* `uljin_samcheok_2022_dem.tif` **filled the East Sea with a ramp to −497 m**
  across 49 % of the raster — and because the model trains leave-one-fire-out on
  one shared dataset, that fiction was training data for *every* fold.
* `data/processed/routing_demo.npz` turned out to be the surviving output of a
  run that was **reverted the next day**. Everything downstream of it had been
  measured on a field nobody had chosen.

Rebuilt on a canonical field, Yeongdeok's 459-series counts moved
**440 / 17 / 3 → 414 / 42 / 2**, the future-aware-only share **3.70 % → 9.17 %**,
and core growth **+1.2 % → +316.1 %** — the "quasi-static core" limitation was a
property of the reverted field, not of the fire. **The headline AUC 0.890 is
unaffected** (§2-A).

**③ It runs.** A detection — satellite *or* phoned in — triggers routing on the
pre-computed surface and produces the three delivery formats unattended, with a
single-file offline screen for the demonstration.

### 1.2 Phase by phase

| PHASE | State | What it produced | Commit |
|---|---|---|---|
| 0 — freeze | done | tag `round2-submitted`, branch `round3-dev` | — |
| **1 — reproducibility infrastructure** | done | `NUMBERS.json` registry, snapshot store, `config/default.yaml`, `make verify / check-forbidden / snapshot-verify / env-check` | `a465128`, `9de5eae` |
| **2 — DEM slope on OSM edges** | done | 60 m canonical sampling; **+26.6 %** traversal time, mean \|slope\| **8.18 %**, directional asymmetry **20.0 %** — and a **null result** on the bucket counts | `b7fc593` |
| **2-C-1 — time-minimising objective** | done | **150 of 458 routes change (32.8 %)**; longest walk 444 → 353 min (**−91.3 min**); flat control changes 0 | `938cd6d` |
| **2-C-2 — w(t) budget sweep** | done | w = 56.55 / 40.17 / 28.38 / 22.27 / **9.61 %**; ratio **5.89×**; sixth bucket `fa_exceeds_budget` added, strictly additive | `cbc9b45`, `322bfb8` |
| 2-C-3 — hazard time resolution | **NOT started** | deprioritised: the budget was the binding constraint | — |
| **3 — operational outputs** | done | three formats — SMS draft, A4 sheet for the 이장, 마을방송 script. `outputs/dispatch/` (44 points) | `8e6b60e` |
| **3-B — full-coverage re-run** | done | `outputs/dispatch_full/` (174 points, 3 eps); reproduces drift arm B exactly **441 / 174 / 32** | `6612271` |
| sparsity analysis | done | rescue-needing origins are **2.13× more dispersed**; singleton fraction never below **49.2 %** | `bc3dfdd` |
| 4 — live-operation feasibility | **superseded** | PHASE 6 built the thing this was to investigate | — |
| **5 — multi-region** | STEP 0–4 done | three regions acquired, snapshotted, simulated and routed under one identical rule | `466884f` … `a32da6b` |
| **canonical-hazard reconstruction** | done, steps 1–4 | the corrected field and everything re-run on it. **§2-A** | `141b035` … `75f347a` |
| **6 — live detection pipeline** | done | FIRMS NRT polling + offline replay → routing → three formats. §9, [`live_pipeline.md`](live_pipeline.md) | `5a7cfc5` |
| **7 — email delivery channel** | done, one caveat | approval-gated Gmail SMTP. **The verification send did not complete — outbound SMTP is blocked on this network.** §10, [`delivery_channels.md`](delivery_channels.md) | `353a3fe` |
| **8 — operator screen** | done, two regions | single-file offline screens: 의성·안동 (시연용) and 영덕 (한계 설명용). §11, [`operator_screen.md`](operator_screen.md) | `1e8e828`, `ac96a75`, `6f94e39` |
| **12 — manual ignition trigger** | done | a reported coordinate routes at once; the FIRMS path is untouched. §12, [`manual_trigger.md`](manual_trigger.md) | `f666c76` |

PHASES 9–11 were not defined; the numbering jumps to 12 as the brief did.

### 1.3 The numbers that are new in Round 3

Nothing here existed at `round2-submitted`. **Every absolute Yeongdeok figure
carries the 32.6 % coverage caveat** (§2-A); the paired contrasts do not need it.

**The canonical Yeongdeok field** — `routing_demo_canonical.npz`, sha256
`81b4e4d1…`, 181 × 156 @ 500 m, five slices at 0–720 min:

| | |
|---|---|
| core at p ≥ 0.5 | 249 → **1,036 cells** (6,225 → **25,900 ha**) |
| core growth | **+316.1 %** |
| 459-series scan | **458 origins → 414 / 42 / 2** |
| future-aware-only share | **9.17 %** |
| future-aware rescue rate | **95.5 %** of the origins whose fire-blind route is unsafe |

**The three-region table** — identical parameters everywhere (slope 60 m,
distance objective, 600-min budget, stride 18, `osmnx` 2.0.7):

| region | origins | both_safe | FA-only | no_safe | over budget | FA-only % | coverage | envelope | core growth | depots |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 영덕 2025 | 458 | 414 | 42 | 2 | 0 | **9.17 %** | **32.6 %** | 25,900 ha | +316.1 % | 4 |
| 의성·안동 2025 | 368 | 263 | **91** | 12 | 2 | **24.73 %** | **99.2 %** | 3,275 ha | +147.2 % | **0** |
| 울진·삼척 2022 | 393 | 377 | 3 | 10 | 3 | **0.76 %** | 81.5 % | 7,300 ha | +183.5 % | 4 |

Envelope-area spread **7.91×**. ⚠ Never rank the regions on the FA-only column
(rule 14) — n = 3 and three covariates move together. What **is** established:
on a field that actually advances, the same method and parameters give a
future-aware-only share nearly **seven times** Yeongdeok's, so the quasi-static
limitation was real and understated the benefit. What is **not**: that the
benefit rises with fire speed — 울진·삼척 advances fastest and benefits least.

**Measured operational timings** — all on the reference machine, A4 PDF
conversion excluded throughout (it runs after the list exists and scales with
village count, ~2.7 s per sheet):

| | |
|---|---|
| routing, 458 origins | **≈ 25 s** (24.9 – 29.0 across runs) |
| render three formats × 29 villages | **≈ 0.06 s** |
| FIRMS trigger → dispatch list (warm) | **≈ 25 s** |
| **manual coordinate → dispatch list** | **≈ 30 s cold** (29.6 s median of 5), 26.8 s warm |
| A4 PDF, 29 sheets | +79 s · 65 villages +175 s |
| operator screen, full replay at 60× | 12.4 min (12.0 with `--skip-preroll`) |

**What was refuted or corrected**, and is not to be restated:

* the "sea cells inflate the AUC" hypothesis — **refuted**: only 99 of 151,904
  rows have elevation < 0, and removing them *raises* the AUC;
* "fire-blind risk is flat across regions" — an artifact of the defective DEM;
  it reads 9.61 / 27.99 / 3.31 %;
* Yeongdeok coverage **50.4 % → 32.6 %** — the bbox did not move, the core
  quadrupled;
* the 27,900 ha vs 6,225 ha conflict — **dissolved**; `routing_demo.npz` was the
  outlier.

### 1.4 What a next session should know before touching anything

1. **Read §2-A before quoting any Yeongdeok number.** Two artifacts look
   interchangeable and are not: `routing_demo.npz` is a reverted run's output,
   `routing_demo_canonical.npz` is the canonical lineage.
2. **The coverage decision is closed** (§2-A, confirmed 2026-08-03). 32.6 % is
   reported as a stated limit; Yeongdeok is not re-acquired.
3. **The safety claim changed at PHASE 7.** "Nothing is ever sent" is no longer
   true — the email channel can transmit, behind an approval gate. Use the
   wording in §10.
4. **Run `make all-checks` first.** 103/103 registry entries, 722 tests,
   snapshots intact, environment pinned.
5. **§5 is the list of things that must never be done.** It is 21 items long
   because each one was learned from something that went wrong.

### 1.5 Still open

| item | why |
|---|---|
| `spread_v2_lofo.json` trained on the defective Uljin-Samcheok DEM | **the next decision.** Every fold saw the sea-fill. Nothing has been re-run: those are committed Round-2 artifacts the submission cites. Effect unmeasured, could go either way. §4 |
| Which field to PUBLISH | both are in the tree with their provenance; the documents lead with the canonical one. **The submission materials have not been touched** — the choice is the user's. |
| PHASE 7's verification send | blocked by this network, not by the credential. Run it from a network that permits outbound SMTP. |
| Shelter-density experiment | requested 2026-08-02 as a way around n = 3; sequenced, not started. |
| PHASE 2-C-3 — hazard time resolution | deprioritised. |
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
* ⚠ **The safety claim changed at PHASE 7.** "Nothing is ever sent" was true
  while every channel wrote files; the email channel can transmit. State it as:
  *전달 문구는 자동으로 발송되지 않으며, 승인 권한을 가진 사람이 명시적으로
  확인한 뒤에만 발송됩니다. 발송 함수는 승인 토큰 없이 호출될 수 없습니다.*
  `sms.send()` still requires a positional `approval_token` and `DEMO_MODE` is
  on unless the env var is exactly `"0"`.
  [`delivery_channels.md`](delivery_channels.md).
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
   On the canonical lineage: growth **+316.1** / +147.2 / +183.5 % against
   FA-only **9.17** / 24.73 / 0.76 %. Two regions support it, one contradicts it
   strongly. What IS established: on a field that actually advances, the same
   method and parameters give a future-aware-only share nearly **seven times**
   Yeongdeok's, so the "quasi-static core" limitation was real and understated
   the benefit. What is NOT established: that the benefit rises with fire speed —
   Uljin-Samcheok advances fastest and benefits least.
   ⚠ The earlier reading (ρ = −1, "fire-blind risk is flat at 4.35/3.53/3.31 %")
   was an artifact of the defective DEM. On the canonical lineage it reads
   **9.61 / 27.99 / 3.31 %** — Yeongdeok's w(600) rose 4.35 → 9.61 with the
   field switch (§2-A step 3), and Uiseong-Andong's 3.53 → 27.99 with the DEM
   fix. *(Corrected 2026-08-03: this line previously carried Yeongdeok's
   reverted-field 4.35 beside two canonical values, contradicting §4. The growth
   and FA-only figures above were the reverted run's, too.)*
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

### ⚠ The coverage decision — settled 2026-08-02, **CONFIRMED FINAL 2026-08-03**

> **Decision (user, 2026-08-03): do NOT re-acquire. Report 32.6 % as a stated
> limit.** The reasoning, in the user's own terms: the bbox and the simulation
> canvas are coupled, so re-acquiring means re-running steps 1–3 in full; and
> the price of not re-acquiring is **exactly one thing** — absolute rates need a
> caveat — while **every paired contrast remains valid**, because both arms share
> the origins and the sampling frame cancels. Paired contrasts are most of what
> the project reports.
>
> This closes the item. It is no longer an open question, and it is not to be
> reopened without new information about the canvas coupling itself.

The caveat is applied mechanically (see below) and now also travels onto
operational artifacts: every A4 sheet the PHASE-6 live pipeline emits carries it
in its banner block, because those sheets carry absolute Yeongdeok counts
(`docs/live_pipeline.md` §7).

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
`multi_region.md` (×2), `budget_sweep.md`, `slope_integration.md`,
`walk_bbox_coverage.md`, the `bbox.multi_region_walk_bbox` comment in
`config/default.yaml`, and — as of PHASE 6 — `live/scope.py`, from which it
reaches **every A4 dispatch sheet the live pipeline emits**.

Where it is deliberately NOT applied, and why: paired contrasts (flat vs slope,
distance vs time) and network/terrain quantities (traversal time, changed
routes, the longest-walk saving). Both arms of a paired contrast are drawn from
the same origins, so the sampling frame divides out; the terrain quantities do
not depend on the fire at all.

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
| Yeongdeok 2025 | 895 | 1.803 | 9.43 | 67.4 % | 100 % | 5.58 | 0.45 | available |
| Uiseong-Andong 2025 | 896 | **2.390** | 7.45 | **78.6 %** | 100 % | 3.79 | **0.00** | **NOT APPLICABLE** |
| Uljin-Samcheok 2022 | 890 | 1.663 | 8.21 | 68.3 % | 100 % | 2.92 | 0.45 | available |

⚠ **These densities moved on 2026-08-03 and no COUNT changed.** `bbox_area_km2`
projected the four bbox corners into EPSG:5179 and returned the area of their
axis-aligned bounding RECTANGLE, which is strictly larger than the projected
quadrilateral — and EPSG:5179 cannot be evaluated outside Korea at all. It is now
geodesic on the WGS84 ellipsoid. Areas fell 931.3 → 895.3, 918.7 → 896.5 and
924.2 → 889.5 km² (+4.02 / +2.48 / +3.90 % inflation removed), so every density
rose by that much. Walk nodes, edges, length, geometry share, highway share and
both POI counts are bit-identical before and after.

Relative to Yeongdeok: road density 1.33× / 0.92×, node density 0.79× / 0.87×,
shelter density 0.68× / 0.52×. **Carry this table beside every cross-region
routing number** — otherwise "regions differ" cannot be told from "mapping
differs".

⚠ Write the depot fact as: *발화점 중심 919 km² 범위 내에 OSM에 매핑된
fire_station이 없으며, 더 넓은 3,926 km² 범위에는 6곳이 있습니다.* **Never** as
"Uiseong-Andong has no fire stations."

## 4. Open items

| item | why it is open |
|---|---|
| ~~PHASE 6 — live detection pipeline~~ | **DONE 2026-08-03.** FIRMS NRT acquisition, trigger → 459-series routing on the canonical field → all three delivery formats, plus an offline replay mode. [`live_pipeline.md`](live_pipeline.md), §9. Its own open limits are listed there §9; the two that matter are that the hazard surface is fixed (ERA5 lag — not fixable without a real-time weather source) and that **no trigger has ever fired on a live detection**, which needs an actual fire in the bbox. |
| ~~The 439-vs-459 delivery scoping question~~ | **DECIDED 2026-08-03: the live pipeline consumes the 459/canonical series.** It follows from the PHASE-6 brief (canonical field, snapshot network, real hazard). The 439 outputs under `outputs/dispatch*` are untouched and still generated by `generate_dispatch_outputs.py`; the two lineages now co-exist with different filenames and different wording (459 sheets say 도보, never 차량). |
| **`spread_v2_lofo.json` was trained on the defective Uljin-Samcheok DEM** | **This is the next decision.** The headline mean-of-folds AUC is built over the six-fire set that includes `uljin_samcheok_2022`, whose raster filled the sea with a ramp to −497 m, so EVERY fold — including Yeongdeok's — trained on it. The same applies to `routing_demo.npz` and every Yeongdeok number derived from it. **Nothing has been re-run**: those are committed Round-2 artifacts protected by §5.2, and re-running them changes figures the submission cites. The effect is unmeasured and could go either way. [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) §3. |
| ~~DEM re-acquisition~~ — **DONE 2026-08-02** | Both regions re-acquired, validated, snapshotted, re-simulated and re-routed; nodata 0.000 %, sim-grid mean-fill 0.00 %, both pass the gate with no acknowledgement flag. Superseded text: **This was the next action.** Two gaps, one fix. (a) `uljin_samcheok_2022_dem.tif` spans 36.85–37.45 °N while its walk bbox starts at 36.81 °N: **405 of 7,300 walk nodes (5.55 %)**, 6.17 % of elevation samples, timed FLAT. (b) BOTH new regions' simulation canvases were extended south past their DEMs in `a0eaf07`, so **10.0 %** (Uiseong-Andong) and **15.6 %** (Uljin-Samcheok) of simulation cells carry a MEAN-FILLED elevation — hazard is p = 0 in every one of them, so the committed fields are clean, but the fill was silent. `scripts/acquire_region_dem.py` is written, targets the UNION of walk bbox + simulation canvas + existing raster, validates coverage before installing, and refuses to mix providers. It needs `OPENTOPOGRAPHY_API_KEY` (env or the git-ignored `.env`); a keyless request is HTTP 401, confirmed 2026-08-02. **Do not route on a partial DEM and do not substitute AWS-Mapzen tiles.** |
| ~~Promote the hypothesis-refutation decomposition~~ | **Withdrawn.** The "fire-blind risk is near-constant" finding was an artifact of the pre-fix fields; it now reads 9.61 / 27.99 / 3.31 %. §2-A. |
| Which field to PUBLISH | Both `routing_demo.npz` (reverted run) and `routing_demo_canonical.npz` are in the tree with their provenance. The documents lead with the canonical one; **the submission materials have not been touched** and the choice of what to publish is the user's. |
| Shelter-density experiment (within-region refuge decimation) | Requested 2026-08-02 as a way around n = 3: hold terrain and road network fixed, remove refuges at 100/75/50/25 % with repeats, and measure FA-only and `no_safe_route`. Sequenced after the DEM fix; the user will confirm before it starts. |
| ~~PHASE 4 — live-operation feasibility~~ | **SUPERSEDED 2026-08-03.** It was scoped as investigation-only; PHASE 6 built the thing instead, and PHASE 12 added a second trigger into it. Nothing is outstanding. |
| PHASE 2-C-3 — hazard time resolution | Deprioritised: `no_safe_route` already moved 3→18 once the budget bound, so the budget was the main blocker. |
| `routing_demo.npz` not reproducible | Cause fully identified and **recoverable** — pin the grid to `bbox.fire_acquisition`. Not done: it would change results. |
| 407-run directionality | Uses `abs(dz)` (conservative). Documented, not changed. |
| `unclassified` in tight-budget buckets | Fixed by `fa_exceeds_budget`. No action. |
| ~~Yeongdeok walk-bbox coverage~~ | **CLOSED 2026-08-03.** It is **32.6 %** on the canonical field (the superseded 50.4 % was measured against the reverted run's four-times-smaller core). Accepted, reported as a covariate, and carried by every absolute Yeongdeok rate. Not fixed, and not to be fixed — §2-A. |

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
| **`make baseline-verify`** | **every tracked `data/processed` artifact, the four PROTECTED paths, and the sha256 of the git-IGNORED `fire_manifest.json`, against [`baseline_phase13.json`](baseline_phase13.json). The check `make verify` cannot do — see below.** |
| **`make baseline-freeze`** | RE-record that baseline. Deliberate; say so in the commit message. |
| `make test` | pytest. |
| `make all-checks` | everything except `snapshot`. |

### ⚠ Why `make verify` is not enough, and the scratch-output convention

Added PHASE 13 PHASE 0, before any US work.

`make verify` re-derives every registered number **from its artifact**. So if a
re-run moves an artifact *and* `build_numbers.py` is re-run over the moved
artifact, the two agree and `make verify` passes — while the number has silently
changed. **The registry is a consistency check, not a fixity check.**

That is exactly what the US port invites. The port re-runs Korean producing
scripts (to re-derive the same quantity under a new cluster threshold, a new
observation-reference stamp, a new permutation-importance pass), and **every one
of those scripts defaults to writing into `data/processed`** —
`run_routing_integration.py` alone writes `spread_v2_lofo.json`,
`yeongdeok_forward_sim.json`, `routing_demo.json` and `routing_demo.npz`. Several
of those artifacts are **irreproducible** ([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md)).

**The convention, for the duration of the port:**

1. **Never re-run a Korean producing script without an explicit `--out` (or
   `--npz-out` / `--json-out`) pointing outside `data/processed`.** The scripts
   all take one; the danger is the default, not the flag.
2. **`make baseline-verify` before and after any such run.** It is in
   `make all-checks`, so a full check already covers it.
3. **A deliberate change is a `make baseline-freeze` plus a sentence in the
   commit message.** An undeclared move is the failure this exists to catch.

⚠ **The four `PROTECTED` paths are not enough.** `run_multi_region_routing.py`
digests four files and exits 4 if one moves — that covers the 459 series and
nothing else. Not `spread_v2_lofo.json` (the headline AUC), not
`routing_demo_canonical.npz` (the canonical field), not the eight per-region
hazard fields. The freeze is a superset; both are kept.

⚠ **And the manifest.** `data/raw/firms_data/fire_manifest.json` is git-ignored
but it **is the training-set definition**: `data.list_fires()` returns every
entry with no filter, and that list feeds `features.build_dataset` in nine
scripts. Adding one US fire silently retrains every LOFO fold and rewrites the
headline AUC — **with no diff, because the file is not tracked.** Its sha256 now
sits in a tracked file, so the contract exists even though the file cannot carry
it. `(n_rows, n_positives) = (151904, 2989)` is pinned in the same record.

Override the interpreter with `make verify PYTHON=/path/to/python`.

---

## 8. Where to read next

| file | for |
|---|---|
| [`NUMBERS.json`](NUMBERS.json) | **every reportable number**, with derivation, caveat and forbidden phrasings. Start here before writing any figure into prose. |
| [`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md) | why the 459 numbers cannot be reproduced |
| [`grid_extent.md`](grid_extent.md) | why the npz hash cannot be reproduced |
| [`network_drift.md`](network_drift.md) | how sensitive each quantity is to the road network |
| [`walk_bbox_coverage.md`](walk_bbox_coverage.md) | the coverage finding — **32.6 %** on the canonical field; the superseded 50.4 % is retained there as a labelled record |
| [`multi_region.md`](multi_region.md) | **the three-region comparison, its covariates and the rules for quoting it** |
| [`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json) | **why `routing_demo.npz` is the orphan of a reverted run** — archaeology, boundary forensics, parameter sweep |
| [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) | the Uljin-Samcheok sea-fill and what it contaminated |
| [`canonical_hazard.json`](../data/processed/canonical_hazard.json) | how the canonical field was built and why its grid is larger |
| [`forward_sim_regions.md`](forward_sim_regions.md) | per-region hazard fields and the canvas extension |
| [`budget_sweep.md`](budget_sweep.md) | w(t) and the fire-blind-baseline attribution |
| [`slope_integration.md`](slope_integration.md) | slope method, the null result, the 407 convention |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | how to rebuild `wfg311` and why 3.11 |
| [`live_pipeline.md`](live_pipeline.md) | **PHASE 6 — the live detection pipeline, replay mode, and the measured timings** |
| [`delivery_channels.md`](delivery_channels.md) | **PHASE 7 — SMS vs email, the approval gate, and the changed safety claim** |
| [`operator_screen.md`](operator_screen.md) | **PHASE 8 — the two demonstration screens and what each is for** |
| [`manual_trigger.md`](manual_trigger.md) | **PHASE 12 — the manual ignition trigger and its measured latency** |
| [`baseline_phase13.json`](baseline_phase13.json) | **the frozen Korean baseline — every `data/processed` digest, the four PROTECTED paths, the LOFO shape, and the sha256 of the git-ignored `fire_manifest.json`. `make baseline-verify`.** |
| **§13 of this file** | **PHASE 13 — the portability investigation, the four defects it found, why McKinney 2022, the four-arm design, and the resume condition** |

---

## 9. PHASE 6 — the live detection pipeline (DONE 2026-08-03)

Full write-up: [`live_pipeline.md`](live_pipeline.md). This section is the
summary and the rules for quoting it.

`scripts/run_live_detection.py` · `src/wildfireguardian/live/` (5 modules) ·
`tests/test_live_pipeline.py` (44 tests)

### ⚠ The scope statement — carry it, verbatim, with every PHASE-6 number

    화점 탐지: 실시간 (FIRMS NRT)
    기상 자료: 2025-03-25 12:25 UTC 기준 (ERA5는 약 5일 지연 발행)

This is **「실시간 탐지 + 사전 계산 위험면 기반 결정」**, never
**「실시간 예보 기반 예측」**. FIRMS NRT publishes hotspots within ~3 h of
overpass; ERA5 publishes on a **~5-day lag**, so no hazard field exists for
today. The surface routed on was simulated once, from the weather of the fire it
was built for, and is held fixed. A detection decides *whether* and *where* to
act; it does not move the surface.

The strings live in `live/scope.py` — one definition, so a retyped caveat cannot
drift — and reach every console screen, A4 sheet, broadcast script, SMS draft
and JSON record. Tests fail if either line is missing.

The weather basis is **derived, not typed**: `pipeline.weather_basis` reads the
committed detections CSV and re-runs the same 90-minute overpass clustering the
forward simulation used, so it cannot drift away from the field it labels. A
test asserts the literal `2025-03-25` does not appear in that function.

### What it does

| step | |
|---|---|
| 6-A | poll FIRMS NRT over the registered bbox (default 3 h); new hotspot = coordinate absent from every previous poll, de-duplicated at **375 m** (one VIIRS pixel); every acquisition snapshotted immediately |
| 6-B | a new in-region hotspot runs the **459-series scan on `routing_demo_canonical.npz`** with the snapshot walk graph and refuge POIs, then renders all three PHASE-3 formats |
| 6-C | `--replay` replays a past fire's committed hotspots in time order, **fully offline**, at a speed multiplier (default 60×) |
| 6-D | `outputs/live/{replay,live}/{timestamp}/` — `RUN.json` carries inputs, the triggering hotspot, the field path **and sha256**, the weather basis, per-stage timings, and the outputs |

### It reproduces the committed result

| | origins | both_safe | FA-only | no_safe | over budget |
|---|---:|---:|---:|---:|---:|
| `real_roads_real_hazard_canonical.json` | 458 | 414 | 42 | 2 | 0 |
| **live pipeline** | **458** | **414** | **42** | **2** | **0** |

That is the design: the same computation with a different trigger, not a second
implementation. The origin rule is pinned line-for-line against the batch scan.

### ⚠ Measured timings — say "about 25 seconds", not "a few seconds"

Full 458-origin scan on the reference machine, from `RUN.json`:

Two triggers in the committed replay run:

| stage | trigger 1 | trigger 2 |
|---|---:|---:|
| load hazard npz + graph + POIs | 2.98 | — (warm) |
| **routing** | **26.72** | **24.87** |
| cluster + render 3 formats × 29 villages | 0.15 | 0.07 |
| **trigger → the dispatch list (warm)** | **26.87** | **24.93** |
| process start → the dispatch list (cold) | 29.86 | 27.92 |
| — A4 PDF conversion, 29 sheets (**separate**) | 79.15 | 77.99 |

The spread is first-run warm-up; trigger 2 is the steady state. Across three
full runs routing measured **24.9 – 28.2 s** — quote **"about 25 seconds"**, and
treat 30 s as the safe upper bound.

Routing is 99 % of it. The delivery layer — the part that looks slow — is 40 ms.
*Warm* is what a running service exhibits (field and graph loaded once at
start-up); *cold* is process start to the list.

⚠ **PDF conversion is reported separately and excluded from the headline.**
Headless Chrome is ~2.7 s per sheet, so 29 villages cost ~78 s — three times the
routing — but it runs *after* the list already exists in every text format, and
it scales with the number of villages rather than with the decision.
`warm_total_with_pdf_s` (≈ 104 s) is in `RUN.json` for when the printed sheets
are what is being waited on. The first full replay run reported the conflated
104 s as its headline; the split was added to stop that.

### ⚠ Rules for PHASE 6

1. **Never describe this as forecasting.** See the scope statement above.
2. **Never quote a PHASE-6 Yeongdeok count without the 32.6 % caveat.** These are
   absolute counts reaching an operational sheet; the caveat is in the sheet's
   banner block for exactly that reason (§2-A, rule 19).
3. **Never point the pipeline at `routing_demo.npz`.** It is refused by name at
   start-up; do not remove that check.
4. **Replay must stay offline.** It imports no HTTP client, and the tests assert
   that against the **import AST** and by running a full replay with the socket
   layer disabled. Adding a network fallback to replay would destroy the one
   property that makes it the demonstration path.
5. **Never say the live branch has been demonstrated end to end.** The API has
   been exercised for reachability and credentials; **no trigger has ever fired
   on a live detection**, because that needs an actual fire in the bbox. Replay
   is what has been run end to end.
6. **`OUT_OF_SCOPE` is a label, never a filter.** When the triggering hotspot is
   beyond `field_applicability_radius_km` the outputs are still produced and
   stamped with the distance. Suppressing a real detection is worse than
   publishing a stamped one.

### ⚠ The applicability anchor is the FIELD's core, not the manifest's ignition

For `yeongdeok_2025` these differ by **17 km**: `fire_manifest.json` records
129.05, 36.43, which falls **outside the walk bbox entirely**, while the observed
first-overpass core sits at 129.222, 36.466. Anchoring on the manifest put every
genuine in-region detection out of scope — the first smoke run reported 28.6 km
and `OUT_OF_SCOPE`, which is how it was found. Both distances are recorded.

### What was added to the delivery layer, and why it is safe

`printable`, `sms` and `broadcast` were written for the 439 series, whose
unreachable points are places a **vehicle** cannot reach. The 459 series is
resident-side and on foot, so saying 차량 would describe a computation that was
not performed. The additions are **purely additive**, and every default is the
original string:

* `sms.compose_family_walk` / `compose_welfare_walk` — new functions;
* `broadcast.compose(mode=…)` — defaults to `"vehicle"`, the committed wording;
* `printable.render_html(banner_lines=…, dispatch_heading=…, …)` — defaults are
  the committed headings.

Tests assert both directions: the walk variants never say 차량, and the defaults
still produce the 439 wording, so committed `outputs/dispatch*` sheets render
byte-identically.

⚠ **The scope statement costs page space.** Putting the mandated strings in five
bordered banner boxes pushed the largest cluster (9 rows) onto a **second A4
page**, breaking PHASE 3's one-page-per-village rule. Nothing was dropped:
the block was compacted to **two** boxes (mode banner alone; scope statement and
both lines merged), and the standing 32.6 % qualifier moved to the **footer**
beside the fixed cautions. **29 of 29 sheets now fit one page**, and a test
asserts every mandated string survives, so page space can never be bought by
deleting a caveat.

### Credentials, as found

`.env` holds `FIRMS_MAP_KEY` (verified against the live API) and
`OPENTOPOGRAPHY_API_KEY`. **No Twilio credentials (0 of 3)**, so the SMS layer
stays in `DEMO_MODE` and composes drafts only — recorded in every `RUN.json`
under `notes`. It changes nothing: this PHASE composes drafts and stops, so a
configured Twilio account would not be used either. **Nothing was sent.**

### Config

A new `live:` block in `config/default.yaml`, a **PURE ADDITION** — no existing
value moved, and no registered number depends on the new keys. The config hash
therefore moves again, exactly as it did at `cc41f12`;
`NUMBERS.json.config_hash_note` already records that this is expected.


---

## 10. PHASE 7 — the email delivery channel (DONE 2026-08-03)

Full write-up: [`delivery_channels.md`](delivery_channels.md).

`src/wildfireguardian/delivery/email.py` · `scripts/send_dispatch_email.py` ·
`tests/test_email_delivery.py` (47 tests)

### ⚠ The safety claim changed. Use the new wording everywhere.

The old statement — *"SMS 전달은 모사이며 실제 발송하지 않습니다"* — was true
while every channel wrote files. The email channel can transmit, so repeating it
now would understate the system. **Say this instead:**

> 전달 문구는 자동으로 발송되지 않으며, 승인 권한을 가진 사람이 명시적으로
> 확인한 뒤에만 발송됩니다. 발송 함수는 승인 토큰 없이 호출될 수 없습니다.

### Why email

The Twilio **trial** account cannot verify a Korean mobile number without a paid
upgrade, so SMS cannot reach the demonstration handset. Email reaches the same
two audiences — 가족 and 복지사 — so the transport changed and the claim did not.
`sms.py` is **not** deleted and stays in `DEMO_MODE`.

⚠ `.env` now holds `TWILIO_*`. **Presence of credentials does not mean SMS can
send** — the account restriction is what blocks it. Never read
`sms.credentials_present() == True` as "SMS is live".

### Three independent locks, all of which must be open

1. `--confirm-send` on the command line;
2. a **typed confirmation word in full** (`발송확인` / `SEND`) — not `y/N`;
3. `email.send`'s own gate: positional mandatory `approval_token`,
   `dry_run=True` by default, and a hard recipient check against
   `DEMO_RECIPIENT`.

There is **no flag that skips step 2**, and that is enforced against the AST:
the test parses the script and asserts the single `dry_run = False` assignment
sits inside a branch that has just called `confirm_or_abort()`. A future `--yes`
shortcut fails the suite. Aborting exits **3**, and nothing is recorded.

### ⚠ The verification send did NOT complete

Outbound SMTP is blocked on this network — ports 25, 465 and 587 all time out
while HTTPS 443 works, both inside and outside the tool sandbox. So:

* the app password was **never presented to Gmail**; a `TimeoutError` implies
  **nothing** about whether the credential is valid;
* one real attempt is recorded (`failure_kind: network`, 30.06 s);
* the script now checks reachability **before** asking a person to confirm, so a
  blocked port cannot spend an operator's authorisation. It stays DRY RUN, says
  why, and exits 0.

**To finish the verification, run it from a network that permits outbound SMTP.**
The Gmail API over HTTPS would work here but needs OAuth rather than an app
password — separate work, not part of this phase.

### Two defects this phase found

1. **The email script scraped the A4 HTML** to recover each village's points.
   Its unreachable-row detector tested the row's *inner* HTML for the `unreach`
   class, which lives in the `<tr>` tag the regex had already stripped — so every
   unreachable point was parsed as a dispatch point and its checkbox column
   became its route note. Fixed at the source: `live.pipeline.deliver` now writes
   the points **structurally** into `MANIFEST.json`. A rendering is not a data
   source.
2. **"확인 불가" is the wrong label in the 459 series.** An absent closing window
   there is a *positive* statement — the place never reaches p ≥ 0.5 within the
   12-hour horizon — not missing data. The email says `12시간 내 미도달`; the A4
   sheet still says `확인 불가`. **The A4 layer was deliberately not edited**
   (out of scope), so the divergence is recorded rather than hidden. Wording
   only; no count changes.

### Never do these

1. **Never send to any address other than `DEMO_RECIPIENT`.** Enforced in code,
   before a connection opens.
2. **Never write the app password anywhere** — not a log, not an artifact, not
   an exception. An SMTP 535 can quote the credential it rejected; the failure
   path scrubs it to `<REDACTED>` and a test proves it.
3. **Never add a path that skips the typed confirmation.**
4. **Never delete `sms.py`** — two channels coexist.
5. **Never modify the A4 or 마을방송 layers from the email path.** The fixed
   cautions are *imported* from `printable.FOOTER_LINES` so they cannot drift.

---

## 11. PHASE 8 — the operator screen (DONE 2026-08-03)

Full write-up: [`operator_screen.md`](operator_screen.md).

`scripts/build_operator_screen.py` → `demo/operator_screen.html` ·
`tests/test_operator_screen.py` (66 tests)

One self-contained HTML file, opened from `file://`, replaying a PHASE-6 run in
the order a judge follows it: **탐지 → 위험면 → 경로 → 출동 목록**.

| | |
|---|---|
| size | ~125 KB, one file |
| network requests | **1** — the file itself |
| console errors | 0 |
| viewport | 1920×1080, **no scroll** (`scrollHeight` 1080 = `innerHeight`) |
| full replay at 60× | **12 minutes** (720-minute horizon) |
| dispatch rows | 44, all visible — 880 px of table in a 954 px pane |

### It draws, it does not fetch

No tiles, no basemap, no CDN, no storage API. Coordinates are projected at
**build** time with the same `pyproj` transformer the routing used, and written
in as SVG. The hazard surface is quantised into four bands and run-length
encoded — the field is sparse (249 cells ≥ 0.10 at t=0), so all five slices cost
~40 KB rather than a raster.

The map shows all **458** origins in three colours, both **real** route
polylines for a `naive_into_FA_safe` origin, and the **walk-network bbox** as a
dashed outline — the fire runs 45 km west and the network stops at the box, so
32.6 % coverage becomes something a judge can see rather than a footer figure to
be taken on trust.

### ⚠ Rules

1. **Never add a fetch, a tile layer, a CDN or a storage call.** Enforced: each
   forbidden API is asserted absent from executable source individually.
2. **Never let the screen show a figure the committed run does not.** A test
   compares its counts against `real_roads_real_hazard_canonical.json`
   (458 / 414 / 42 / 2).
3. **The string "FIRMS NRT" must stay** — it names the detection source on the
   status bar. What is banned is a polling *mechanism*, not the word.
4. **`viz.json` is a VISUALISATION artifact and stays separate from the
   operational ones.** Sheets, scripts and drafts are coordinate-free by
   requirement; a map is nothing but coordinates. Do not merge it into
   `MANIFEST.json`. The dispatch rows on screen carry place labels only.
5. **The 25-minute pre-roll is a presentation device**, chosen for legibility.
   The minutes are real and empty — the field's t=0 *is* the first overpass — and
   the clock says `탐지 전 N분` rather than pretending otherwise.

### ⚠ TWO screens, and they do different jobs — keep both

Same builder, same pipeline; only `--region` changes.

| | **의성·안동 2025** — 시연용 | **영덕 2025** — 한계 설명용 |
|---|---|---|
| origins | 368 | 458 |
| **FA-only** | **91 (24.7 %)** | 42 (9.2 %) |
| no_safe / over budget | 12 / 2 | 2 / 0 |
| **coverage** | **99.2 %** | **32.6 %** |
| villages / points | 65 / 105 | 29 / 44 |
| rows shown | 45 of 105 + 「… 외 60곳」 | 44 of 44 |
| depots in walk bbox | **0** → responder side N/A | 4 |
| the point | the network covers the fire, so the result is the region's | the fire runs 45 km **west out of the dashed box** — 32.6 % made visible |

의성·안동 leads because its result is a statement about the region rather than
about a third of it. 영덕 follows because its dashed walk-bbox outline is the
easiest way to point at the coverage limit. **A presentation that shows only
the first is selling something** — that is why both are kept.

⚠ Do NOT quote the two FA-only shares as a ranking (rule 14: n = 3, the
covariates move together). The honest statement is that on a field which
actually advances, the same method and parameters give a much larger benefit —
not that benefit rises with fire speed.

### ⚠ 의성·안동 has no responder side, and the screen says so

Its 919 km² walk bbox contains no `amenity=fire_station` mapped in OSM, so the
status bar carries:

> 이 지역은 walk bbox(919 km²) 내에 OSM에 매핑된 소방서가 없어 구조자 측
> 산출이 불가합니다 — 더 넓은 3,926 km² 범위에는 6곳

Generated from the depot count in `viz.json`, so it appears for any region with
zero and never for one with some. **Never shorten it** to "의성·안동에는 소방서가
없습니다" (rule 11) — a test bans that phrasing in the built file.

**No responder route was removed, because none was ever drawn.** The 459 series
is resident-side for every region: both lines are the resident's (fire-blind and
future-aware). What changed is that the screen now *states* the responder side
is not applicable instead of leaving its absence unexplained.

### Demo window — `--start-at`, `--paused-on-load`

`--list-triggers` prints when the routing actually fired:

| region | trigger 1 | trigger 2 |
|---|---:|---:|
| 의성·안동 2025 | **t+77 min** | t+463 min |
| 영덕 2025 | t+0 min | t+333 min |

⚠ **Trigger times are OVERPASS moments, not hotspot arrival times.** A trigger
fires when an overpass completes and its batch is diffed against the seen-set.
For Yeongdeok the two coincide; for 의성·안동 they are **77 minutes apart**, and
the first version of this screen showed 「계산 중」 at t=0 for a run that did not
route until t+77. Read from `RUN.json`'s overpass list, never inferred.

`outputs/live/screens/uiseong_andong_2025_demo.html` — built with
`--start-at 47 --paused-on-load` — is the four-minute-talk file. At 60× one
wall-clock second is one field minute, so it is a **60-second window**: 30 s of
context, trigger at 30 s, 12 s of 계산 중, list complete at 60 s. Then pause and
take questions.

The fill is a **fixed duration** (18 field min) rather than a fixed rate, so the
beat is the same length for 44 rows and for 45-of-105. That is what makes
trigger → complete list exactly 30 s, and the 60-second window possible.

**Moving the start point reproduces the state exactly.** Structurally: every
drawn thing is a function of `t`, and `T_START` appears in exactly three places
(definition, clock initial value, reset target) — a test pins that count.
Empirically: nine start points were built and their rendered DOM compared
against the state computed independently from the payload; all nine matched,
including the hotspot fade pattern.

⚠ `--start-at` overrides `--skip-preroll`. ⚠ `requestAnimationFrame` does not
run in a hidden tab, so the replay freezes when backgrounded and resumes where
it left off — no time jump.

### `--skip-preroll`

At 60× the 25-minute pre-roll costs **25 seconds** of wall clock, and a
four-minute talk may not have it. `--skip-preroll` starts at the moment of
detection: **12.0 min** instead of 12.4. The trade is that the screen opens
mid-trigger and the "nothing detected yet" beat is lost. Both variants are built
for 의성·안동.

### Costs nothing extra to produce

Both routes are already solved for every origin and were previously discarded;
`--collect-routes N` (default 12) simply retains the polylines. The run is
unchanged: 458 origins, 414 / 42 / 2, same as every canonical run.

---

## 12. PHASE 12 — the manual ignition-point trigger (DONE 2026-08-03)

Full write-up: [`manual_trigger.md`](manual_trigger.md).

`scripts/run_manual_trigger.py` · `tests/test_manual_trigger.py` (21 tests)

```bash
python scripts/run_manual_trigger.py --lat 36.4436 --lon 129.3696 --reported-by "119 신고"
```

In real operation a fire's location arrives from a **119 call, a watch-tower or
a CCTV operator** long before a satellite sees it — VIIRS revisits about every
12 h, then FIRMS NRT publishes ~3 h after the overpass. There is no reason to
wait. **Both triggers coexist**; the FIRMS and replay branches are untouched.

### Three sources, recorded distinctly

    trigger_source: "firms_nrt" | "replay" | "manual"

Top-level in `RUN.json`, and in `viz.json` and the screen payload.

### ⚠ The trigger time means something different per source

| source | trigger time is |
|---|---|
| `firms_nrt`, `replay` | **a satellite overpass** — when an instrument observed |
| `manual` | **when the coordinate was entered** — when a person reported |

Stated in four places: the console, `scope.trigger_at_meaning`, the screen's
status bar (`트리거 시각 = 좌표 입력 시각 (위성 통과 시각 아님)`), and the
detection line itself — 「발화점: 수동 입력 · {시각}」, which does **not** say
`FIRMS NRT` because no instrument was involved. `scope.detection_line()` picks
the wording by source; the PHASE-6 mandated line is unchanged for every
pre-existing caller.

### Identical downstream — structurally, then measured

The script hands a one-point trigger to `run_live_detection.run_trigger`, the
same function FIRMS and replay call. A test asserts it via the AST and forbids
this script from calling `route_region` / `deliver` / `write_viz` /
`build_run_record` directly, which would fork the path.

Measured on the same coordinate: counts, villages, points, every point, SMS
drafts, hazard digest, weather basis, parameters and applicability **all
identical**. The one difference is the 마을방송 script's first line — replay
prepends 「재생 모드입니다.」 and a real report must not.

### Measured: coordinate in hand → dispatch list

Five runs, `--no-pdf`, idle machine: cold **29.6 s median** (26.2–30.2), of
which routing **26.7 s**; warm **26.8 s**. A4 PDF (+79 s for 29 sheets) is
excluded, as everywhere else. **Say "about 30 seconds from a 119 call to a
dispatch list."**

### ⚠ Rules

1. **Never remove the FIRMS or replay branch.** Three doors, one room.
2. **Never present a manual trigger time as an overpass time**, or a manual
   trigger as a FIRMS detection.
3. **Never route a coordinate outside the registered walk bbox.** Exit 3, before
   any routing — the network, refuges and surface exist only inside it, so a
   list for a coordinate outside would be invented evidence.
4. **No geocoding.** Latitude and longitude only; a test forbids a geocoder.
5. **`--trigger-source` is required when a region has runs from more than one
   source.** `--region` used to take the newest of any, which silently built a
   FIRMS screen out of a manual run.

---

## 13. PHASE 13 — international portability, INVESTIGATED AND STOPPED (2026-08-03)

**Status: stopped deliberately, not blocked.** Investigation and design are complete;
acquisition was never started and is deferred past the October final. §13.7 is the
resume condition.

### 13.1 What it was for, and what it produced instead

The brief was to find out **what breaks** when the pipeline is pointed at a US
fire — a demonstration of portability, not a port. It did that. It also found
**four real defects in the repository as it stands**, none of them about
internationalisation, which is the more useful outcome.

| | found | state |
|---|---|---|
| **① CRS predicate** | `routing/slope.py:235` tested membership in `("epsg:5179", "epsg:5179")` — the same string twice | **fixed** `24407eb` |
| **② caveat drift** | `delivery/email.py` held a second, hand-retyped `COVERAGE_CAVEAT_KO` that had lost its closing sentence | **fixed** `24407eb` |
| **③ fuel-tile gap** | `miryang_2022`: 176 km² of LAND read `burnable_frac = 0` because the `N36E129` WorldCover tile was never fetched — and `features.py:151` gates candidacy on it, so those cells were EXCLUDED FROM PREDICTION. Nothing raised. | **gate added** `825aba9` |
| **④ planar bbox area** | `bbox_area_km2` returned the axis-aligned bounding RECTANGLE of the 5179-projected corners, inflating every Korean denominator 2.5–4.0 % | **fixed** `825aba9` |

⚠ **Two more were found and are NOT fixed.** They are the open items in §13.6.

Everything in §13 was verified against the tree. Two claims that circulated
during the phase and turn out to have **no basis in this repository** are recorded
here so they are not re-adopted: there is no `_bbox_from_grid` round-trip
anywhere in the tree, and there is no `httpx` stub — `httpx` is not imported,
not used and not installed; `raise_for_status` appears zero times. The HTTP layer
is `urllib.request.urlopen` at exactly three call sites, and all three fail loudly
on 4xx/5xx (tested locally on 401/403/404/429/500).

### 13.2 The Korea-specific assumptions, in one table

Six-dimension read-only audit, **210 findings, 635 file:line citations verified**.
Full detail lives in the phase transcript; the load-bearing results:

**EPSG:5179 does not fail outside Korea — it succeeds, wrongly.** Measured at
Paradise, CA (39.755 N, 121.62 W): local scale **1.4352×**, area **2.06×**,
grid-north **−120.71°** from true north, and **both axes inverted** (moving east
decreases x). No exception. At McKinney (41.85 N, 122.6 W): scale **1.3991×**, a
500 m projected cell is **357.4 ground m = 12.77 ha** against Korea's 25.00 ha.
Under the correct EPSG:32610 the same measurements give 0.9996× and −0.27°.

* `"EPSG:5179"` appears as a quoted literal at **46 sites across 33 `.py` files**.
  `config/default.yaml:46` has a `project.crs` key; it is read at **two** call
  sites and **drives no transform**. Changing it makes the provenance record lie.
* Two independent definitions of the constant (`utils/regions.py:65`,
  `spread_v2/grid.py:28`), each with its own import-time transformer pair.
* The committed hazard `.npz` files carry **no CRS key**. Four writers, ~15
  readers, each re-assuming 5179; and `CoarseGrid` / `Grid` / `RoadNetwork` have
  no field to put one in.
* **The region registry is split.** `utils/regions.py:387 ALL_REGIONS` is seven
  hardcoded presets (code edit); `config/default.yaml:106 multi_region_walk_bbox`
  is region-keyed data read at ten sites (config edit). Proof they diverge:
  `uiseong_andong_2025` is in the config table and the manifests and **absent from
  `ALL_REGIONS`** — and it runs. Seven further hand-maintained region lists exist
  and are already out of step with each other.
* **Place names do not crash and are not coordinates.** `pipeline.py:449` composes
  nearest-named-OSM-POI + Korean bearing + metres, so a US run emits
  `"Riverside Park 북쪽 320m"` — real English POI names in Korean grammar. If no
  refuge is named at all the third branch gives `"군집 3"`.
* **The hard blockers in the delivery layer are numeric, not linguistic:**
  `broadcast.MAX_SENTENCE_CHARS = 15` code points, `sms.MAX_CHARS = 90`,
  `printable.MAX_PAGES = 1`. English needs ~2–2.5× the glyphs. These are design
  decisions to be re-argued, not strings to be translated.
* **The village concept is geometric and transfers; the 이장 concept is
  institutional and does not.** DBSCAN eps = 500 m, `min_samples = 1`, no POI, no
  boundary. The delivery contract is *N clusters → N sheets, addressee
  unspecified, acknowledgment in ink* — there is nothing US-shaped to remove and
  an entire recipient-resolution layer to add.
* **Timezones are already clean on the operational path** (UTC-aware or pure
  durations throughout). Two real defects sit off it: `data_io/weather.py`'s
  naive-KST diurnal term, and naive warning times in the validation cases.

### 13.3 Why the target fire moved off Camp Fire 2018

Criterion 1 was the fuel epoch, and it reframed the test. **ESA WorldCover v200 is
a full-calendar-year composite, 01 Jan – 31 Dec 2021** (PUM V2.0 §3.4.3), with no
documented burn handling. So the safe test is not *"epoch year < fire year"* but
**"the landcover reference year ENDS before ignition."**

All six Korean fires pass it — landcover precedes the fire by 1–4 years, mean 2.33.
Dixie 2021 **fails**: 47 % of the compositing window is post-ignition. Camp 2018
and North Complex 2020 invert outright.

Criterion 2 pointed the opposite way, and that is the finding. **FEDS** (NASA/UCI)
is the only 12-hourly perimeter product and matches the pipeline's horizon exactly
— probed record counts: Camp **43**, North Complex **149**, Dixie **255**,
**Park 0**, all 2022 **0**. The GeoMAC archive ends 2020-04-30; WFIGS Daily has
4/2/0/0 California large-fire records for 2020/21/22/23. **The two criteria are
anti-correlated because both are era-dependent in opposite directions.**

Criterion 3 settled it. Against the project's own ignition-centred 0.30° box
(Korean predicted-envelope ratios 0.04–0.28×):

| fire | burned km² | fire/box | |
|---|---:|---:|---|
| Oak 2022 | 77.9 | **0.09×** | inside the Korean range |
| **McKinney 2022** | **243.4** | **0.29×** | **= Yeongdeok's 0.28×** |
| Mosquito 2022 | 310.8 | 0.36× | |
| Camp 2018 | 620.5 | 0.73× | tight |
| North Complex 2020 | 1,290.7 | **1.51×** | overflows |
| Park 2024 | 1,738.5 | **2.03×** | overflows |
| Dixie 2021 | 3,898.4 | **4.56×** | overflows |

**Three of the four headline candidates are larger than the box meant to contain
them.** McKinney 2022 was chosen because it is the only candidate that is
epoch-clean on the ALREADY-HARDCODED fuel layer *and* fits the footprint rule —
zero data-source change, which is the only configuration in which a Korea-vs-US
comparison stays interpretable.

### 13.4 The four-arm design (agreed, not executed)

| arm | what | answers |
|---|---|---|
| **0** | run end-to-end, report **only** structural facts — nodata, coverage, gate outcomes, cluster counts, stage completion. **No IoU.** | portability alone |
| **A** | Korea-trained model, zero-shot on the US fire | the transfer measurement |
| **B** | US-internal leave-one-out over N=5 (McKinney + Mosquito + Borel + Rum Creek + Oak) | the ceiling |
| **C** | `validation/baselines.py` on the US fire | the floor |

Reported as **C < A < B**, never A alone. **Arm A alone says nothing**; a starved
B (N=3 trains each fold on 2 fires against Korea's 5) can produce C < B < A, which
is an artifact and not a transfer finding.

⚠ **Portability and model transfer are different questions and must not be mixed.**
A model trained on six Korean fires is *expected* to lose accuracy in California.
If Arm 0 passes and A is low, that is **portability succeeded + transfer degraded**
— two sentences, written separately.

**Confound-neutralisation rules**, all five plus one:
0. **artifact-write isolation** — every Korean producing script defaults to
   writing into `data/processed`; the first careless re-run overwrites
   irreproducible artifacts. This is why §13.5 exists.
1. fuel measurement fixed (WorldCover v200/2021 on both sides)
2. observation reference fixed (FIRMS hotspots on both sides — this is what keeps
   the committed IoU 0.37–0.40 quotable)
3. cluster threshold reported at 90/60/30 min on both sides
4. envelope coverage carried as a column
5. permutation importance recomputed — and readable **only after** the CRS work,
   for the reason in §13.6.

⚠ **DEM source is a sixth rule.** It is currently in neither config nor the
registry. See §13.6.

### 13.5 What PHASE 13 actually changed in the tree

Four commits. **No committed Korean result moved**: `make verify` 118/118 with
**0 pre-existing registry values changed**, 743 passed / 2 skipped / 0 failed.

| commit | |
|---|---|
| `24407eb` | ① CRS predicate → `_is_analysis_crs()`, CRS **identity** comparison. All three Korean walk networks rebuilt under old and new predicates and compared by sha256 — **bit-identical**. ② `email.py` now imports the caveat from `live.scope`; one definition. |
| `825aba9` | ③ fuel-coverage gate. ④ geodesic `bbox_area_km2`. Plus two findings recorded: the shelter-layer composition, and the `goseong_2019` correction. **15 completeness covariates registered** (103 → 118 entries) — HANDOFF §5 rule 12 names them, and until now the registry could not check them. |
| `fb1d011` | the baseline freeze — §13.5.1 |

**13.5.1 `make baseline-verify`, and why `make verify` was not enough.** `make
verify` re-derives every registered number **from its artifact**, so an artifact
and its registry entry can move **together** and still agree. It is a consistency
check, not a fixity check. `scripts/freeze_baseline.py` records all 58 tracked
`data/processed` artifacts, the four `PROTECTED` paths, the config hash, the LOFO
shape, and **the sha256 of the git-ignored `fire_manifest.json`**.

⚠ **That last one is the point.** `fire_manifest.json` **is the training-set
definition** — `data.list_fires()` returns every entry with no filter, feeding
`features.build_dataset` in nine scripts. Adding one US fire silently retrains
every LOFO fold and rewrites the headline AUC, **with no diff, because the file is
not tracked.** A tracked sha256 creates the contract the file cannot carry.

**13.5.2 The fuel gate measures uncovered LAND, not uncovered area.** A coastal
bbox is legitimately uncovered over the sea — `gangneung_2023` is 17.61 %
uncovered and 17.2 pp of that is the East Sea. Crossing the uncovered mask with
the DEM separates the causes: uncovered **land** is 0.00 % for every fire whose
tiles were fully fetched, 2.05 % for `uiseong_andong` (warn) and 12.08 % for
`miryang` (stop, exit 6). ⚠ Replacing the DEM-based land test with a
WorldCover-derived one **destroys the gate** — measured: it reports 0.00 % for
every fire, because the uncovered cells are precisely the cells WorldCover has no
data for. The gate is enforced in `run_forward_sim_region.py` and deliberately
**not** on the LOFO training path, where it would drop `miryang` and move the
committed AUC.

### 13.6 Open, and NOT fixed

1. **⚠ `data_io/raster.py:252` returns a different elevation product per
   hemisphere.** The AWS terrain-tiles archive is a multi-source composite.
   Verified by HTTP HEAD on the archive's own metadata: a US tile reports
   `x-amz-meta-x-imagery-sources: ned13/imgn39w121_13.tif` (USGS NED/3DEP); a
   Korean tile reports `srtm/N35E128.tif, gmted/…, etopo1/…`. **Same bucket, same
   code path, two different missions** — and `raster.py:527-537` stamps a
   hardcoded SRTMGL1 V003 citation on the result regardless. Nothing in the repo
   would catch it. HANDOFF §5 rule 17 forbids exactly this mixture; the pinned
   path (`acquire_region_dem.py`, OpenTopography SRTMGL1, test-locked) is safe,
   the unpinned one is not. **This is a defect that only a multi-region port could
   surface — in a single-country study both sides are the same and it is
   invisible.**
2. **Five of eight DEMs are not snapshotted** — `goseong_2019`,
   `gangneung_donghae_2022`, `gangneung_2023`, `hongseong_2023`, `miryang_2022`.
   **Three of those are in the six-fire LOFO training set**, and
   `data/raw/firms_data/` is git-ignored. §5 rule 8 is in live violation.
3. **The DEM set is already inhomogeneous within Korea**: `int16`/−32768 for the
   two 2026-08-02 re-acquisitions, `float32`/NaN for the other six. All are 1.00″
   EPSG:4326, so resolution is consistent — but `validate()` has **no dtype gate**
   (it checks CRS, resolution, coverage and nodata, and reads dtype nowhere).
4. **⚠ No integrity check against a published checksum.** `validate()` computes
   and *records* a sha256 but has nothing to compare it to; there is no
   provider-published digest fetched, no file-size floor and no magic-byte test.
   What actually guards the file is `rasterio.open()` parsing it (a truncated or
   structurally corrupt GeoTIFF fails there) plus the ≤50 % nodata gate. So
   **byte-level corruption inside a well-formed, parseable GeoTIFF with <50 %
   nodata would pass every check.** Nothing suggests this has happened — the
   recorded digests are stable and the two re-acquisitions succeeded on attempt 1
   — but it is a stated limit of the validator, not a property it guarantees.
   (Note also that the 2026-07-20 manual bundle validated by TIFF magic bytes,
   which this script does not, so the two acquisition routes do not check the same
   things.)
5. **Six of eight DEMs have no acquisition record.** `dem_acquisition.json` covers
   only the two 2026-08-02 re-acquisitions.
6. **The two `fire_manifest.json` files.** `data/raw/…` (git-ignored, what
   executes, defines the training grid) and `docs/data_provenance/…` (committed,
   the 2026-07-20 acquisition record, read by no code). All six shared fires
   diverge — Yeongdeok's ignition by **29.7 km**. Deliberately not reconciled;
   the larger issue is that the runtime file defines the headline AUC's grid and
   is untracked.
7. **No archive-FIRMS acquisition code.** `live/firms.py:315-320` hard-refuses any
   non-`_NRT` source. All eight Korean CSVs are `_SP` products acquired manually.
   `scripts/merge_firms.py` already implements the merge and the UTC timestamp
   join; only the download and argparse are missing.

### 13.7 The stop, and the resume condition

**Stopped 2026-08-03 by the user, after STEP 3 and before any acquisition.** The
reasoning, in the user's terms: a four-minute talk already carries three regions,
the live path and the operational outputs, and there is no room for a fourth
country; judges are looking at depth of validation, not at a country count; and
the value of an international arm accrues at ISEF and IEEE, which is 2027.

**Nothing is half-done.** No US data was acquired, no US region exists in any
registry, `mckinney` appears in the tree exactly once — in
`tests/test_baseline_freeze.py`, asserting it is **absent** from the frozen
baseline. The four defects that were fixed are Korea-side fixes that stand on
their own.

**To resume**, in order:

1. `make all-checks` — the baseline freeze must still be intact.
2. **PHASE 0.5 — bundle isolation, before any acquisition.** Separate
   `$WFG_FIRMS_DIR` (the seam exists at `data.py:148`), plus the
   `(151904, 2989)` assertion added to `run_routing_integration.py` — today only
   `build_canonical_hazard.py:117-127` makes it.
3. **PHASE 1 — CRS parameterisation, `spread_v2` only.** ⚠ It must precede
   acquisition, and the reason is not obvious: at 122.6 W both axes invert, so
   every US detection falls outside the grid, `cells.empty` fires,
   `overpass_snapshots` returns `[]`, and the fire is **silently skipped** — the
   acquisition would validate while the fire is invisible. The routing, delivery
   and operator-screen stacks are **not** needed for any of the four arms;
   `features`/`forward_sim`/`model`/`data`/`weather` contain exactly one 5179
   mention and it is a docstring.
4. Fix §13.6 items 1–3 first; they are cheap and two of them are live rule
   violations.
5. **Then** decide on PHASE 2 acquisition.

⚠ **Before resuming, re-read §13.4's fifth confound rule and §13.6 item 1
together.** The distance features `dist_to_fire_m`, `active_frac_1500m` and
`active_frac_3000m` carry combined permutation importance **0.0900** — more than
the single top feature `days_since_rain` (0.0773) — and under a wrong CRS all
three shift the same way, so the Korea-trained decay under-predicts, the envelope
comes out small, IoU is depressed, and **Arm A reads "the model does not transfer"
as a projection artifact.** The experiment would manufacture its own headline.
Same class of hazard for the ERA5 window: `days_since_rain` is anchored to the
series start, Korean support is 2.38–8.88 d, and a 41-day McKinney window drives
it 4.5–6× outside that support — **generated by an acquisition decision, not by
weather.** The fix is a config-stated window CAP (11 days leaves all six Korean
fires untouched at max 10.88), **not** a switch to the active-detection window,
which was measured and would move Korea too (`gangneung_2023` → 0.09 d).
