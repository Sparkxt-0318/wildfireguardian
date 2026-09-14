# Round-3 handoff

**Read this file alone and you can continue.** Written 2026-08-02, updated
2026-08-03 (PHASE 6, 7, 8, 12, 13, 14). §1 is the full Round-3 summary; **§13 is
PHASE 13 — international portability, and §14 is PHASE 14 — real-time weather.
Both were investigated and deliberately stopped.**

| | |
|---|---|
| branch | **`Main`** — ⚠ updated 2026-08-10: Round-3 work happened on `round3-dev`, which has since been merged; every commit from PHASE 22 (2026-08-07) onward is on `Main` directly. The `round3-dev` row below is the historical record. |
| branch (historical) | `round3-dev` (tracked `origin/round3-dev`), HEAD `fb1d011` at the time §1–§14 were written |
| baseline tag | **`round2-submitted`** = `4e9dfe3` — the submitted state |
| environment | conda env **`wfg311`**, Python 3.11.15 — see [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| suite | **1,033 passed, 3 skipped, 0 failed** (measured 2026-08-10 on `dispatch-ordering`, after PHASE 23 added `tests/test_dispatch_ordering.py`; skips = 2 by design + the closed-DEM-gap gate). Historical: 1,021/3 before PHASE 23, 743/2 at `fb1d011`, 544 at PHASE 5. |
| registry | [`NUMBERS.json`](NUMBERS.json) — **141 entries, 125 reproducible** (PHASE 23 added the 5 `dispatch_order_*` entries; PHASE 13 registered the 15 OSM-completeness covariates that §5 rule 12 names) |
| OSM regions | 3 acquired + snapshotted (`MANIFEST.json`, **74 entries** as of 2026-08-10; was 68 — 64 + 4 FIRMS NRT polls — when this file was first written) |
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

### 1.2-b PHASES 19–21 — the service layer, the one safe optimisation, the gates

| PHASE | State | What it produced |
|---|---|---|
| **19 — service layer** | done | `src/wildfireguardian/service/` (7 modules, 2,109 lines): frozen request params, osmnx/numpy global guards, six-stage progress, per-region resource cache, an async job model with cancellation. `tests/test_service_layer.py` (1,101 lines), `scripts/measure_service_layer.py`, [`service_layer.md`](service_layer.md) |
| **20 — routing cost** | done | the per-origin hazard table hoisted out of the scan loop. **Routing 26.5 s → 10.9 s**, warm trigger→list 26.9 s → 11.1 s, cold coordinate→list 29.6 s → 13.8 s |
| **21 — screen gates** | partly | three gates + fonts vendored + CDN removed + palette at AA. **The dashboard screen itself is NOT built.** |

**PHASE 19.** No web server, by design and by test — the package is asserted to
import no HTTP framework. `run_live_detection.run_trigger` is now a printing
console around `service.routing.run_trigger_core`, so FIRMS, replay and manual
converge on one function rather than on an agreement between three. Two
concurrent requests are safe (shared read-only resources, per-job directories)
but not faster: threads, GIL, measured at 43.5 s each against 22 s alone.
Cancellation reaches a running scan, stops in **0.060 s**, and leaves **no
artifact** because routing precedes every write.

**PHASE 20.** The time-expanded hazard table is a pure function of the network,
the hazard, the departure time, the budget and the step — `start` never enters
it — so a 458-origin scan was building the same array 458 times. Now built once
per scan. ⚠ Allowed **because** it is memoisation of a pure function: every
origin is handed the identical object, so the answer cannot move. Regression run
against a pre-PHASE-19 worktree: **6/6 zero-difference** (459 × 3 regions, 439,
building sample, dispatch list, all three delivery formats). Applies to the
SERVICE path only; the batch runners keep their own `classify()` loops and still
take ~25–28 s per arm.

**PHASE 21, done.** Three gates in `scripts/check_screen_assets.py`, wired into
the suite (`tests/test_screen_checks.py`): offline (0 external requests), dashes
(no EM/EN in visible text **or** on a line that writes to the DOM), WCAG
contrast. They immediately found three real defects: `wildfire_demo.html` was
fetching IBM Plex from Google Fonts; `#64748b` measured 3.46:1 against a 4.5:1
bar; and seven EM/EN dashes, four of which the first version of the gate itself
missed because they were set from JavaScript. Fonts are now vendored under
`web/assets/fonts/` (SIL OFL, licences committed), subset to KS X 1001's 2,350
syllables — derived from the EUC-KR wansung byte range, not typed from a list —
at 505 KiB → 214 KiB. `#64748b` → `#7c8ba1` (4.75:1). Both screens pass all
three gates.

⚠ **The font choice was decided by measurement and it went against the
expectation.** IBM Plex Sans KR beats Pretendard on Hangul ink height at 13 px
(11.36 px vs 10.75 px), has uniform digit advances by default, and subsets
smaller — but has **no U+2192**, nor any arrow at all. A 1.3 KiB three-glyph
Pretendard subset is bound by `unicode-range` to U+2192/2191/2193 and the
fallback was verified by rendering, not assumed. `docs/font_measurement.json`.

**PHASE 21, NOT done: the dashboard screen.** ⚠ **SUPERSEDED — PHASE 22
(2026-08-07/08) built it.** The API (`src/wildfireguardian/api/`, four
endpoints, [`api_layer.md`](api_layer.md)) is the transport, and
`web/console.html` is the dashboard: three regions in one built file, map
click → live calculation → progress → dispatch list
([`console_regions.md`](console_regions.md)). The sentence below is the
state as of 2026-08-06 and is kept as the record of what PHASE 21 itself did
not do: nothing had been built then beyond `demo/operator_screen.html`
(PHASE 8, replay-only, no solver) and the service layer underneath.


### 1.2-c PHASE 23 — the dispatch ordering, measured against alternatives

⚠ **The one finding in this file that goes against a headline contribution.**
Contribution ② is "배차 목록을 시한이 임박한 순서로 정렬한다". It had never been
compared with any other ordering. It now has been, over 270 configurations
(4 arms × 2 windows × 3 service times × 3 delays × 5 team counts), against
nearest-first, closure-first, the unsorted scan order and 200 seeded shuffles.

**It wins 3.6 % of the time, ties 36.7 %, loses 59.7 % — and at the committed
75-minute responder window it wins 0 of 180.** All thirteen wins sit at an
exploratory 240-minute window. The mechanism is measured, not guessed: at
W = 75 the operational window shuts before the corridors do, so the homes share
one deadline (영덕 합성 6 distinct deadlines over 142 homes, 영덕 real **2** over
124, 울진·삼척 real **2** over 116) and the sort key carries almost no
information, while nearest-first saves 6–13 minutes per round trip and converts
that into extra trips.

⚠ **One arm was approved for exclusion and then not excluded.** STEP 0
recommended dropping 영덕 real for zero power, on the branch-only closure
measurement at `vehicle_cutoff` **0.30** (40/40 closures at t=0, one distinct
time). At `Main`'s **0.70** the profile is 42 at t=0 **and 3 at t=180** — two
distinct times, not one. Dropping an arm on a premise that shifted under a
different threshold is the §4-B failure, so it was run. It then produced the
worst result for the shipped ordering of any arm: 13 rescues at 8 teams against
nearest-first's 24, below both the unsorted order (16) and the random mean
(15.7).

Two things this does NOT do. It does not change `rescue.py::capacity_triage`,
which is still the shipped model, and it does not move
`rescue_capacity.json` — 8 teams / 14.4 %, unreachable 6/24/66 are unchanged.
It does introduce a **travel-aware occupancy rule** in a new file, because the
shipped rule (`free_at = departure + service`) makes travel free and is
therefore ordering-blind on the Yeongdeok list.

**⚠ Contribution ②, restated — SETTLED 2026-08-10. Use this wording.**

> **기여 ② 는 「어느 진입로가 언제 닫히는지를 계산해 제시하는 것」입니다.**
> 그 정보로 배차 목록을 정렬하는 것은 **운용 창이 회랑 폐쇄 시각을 넘어설
> 때에만** 유효하며, **커밋된 W = 75분은 그 조건을 만족하지 않습니다.**

The information is the contribution: `ingress_survival_time_min` per home is a
value nothing else in this project — or in the systems it is compared against —
computes, and it separates the regions sharply (영덕 real 45 closures, 42 of them
at t=0; 울진·삼척 real 7 closures, 5 of them stepping through 180/360/540 min).
The *ordering* built on it is conditional, and the condition is measurable: 13 of
360 cells favour it and **all thirteen are at W = 240**.

⚠ **Never quote ② without the condition.** The accurate sentence is not "our
ordering is best" but "it holds only under this condition, and the current
configuration is not that condition". Dropping the conditional clause re-asserts
exactly what this experiment refuted; the registered `dispatch_order_*` forbidden
phrasings block the "검증되었다 / 최적" family.

⚠ **The output ordering was NOT changed, and is not to be.** Nearest-first
rescues more in all four arms at the committed cell (24 vs 19 / 19 / 16 / 13),
but changing the sort would move the print order of every A4 sheet, SMS draft and
마을방송 script and desynchronise them from the committed `outputs/dispatch*`.
`printable.py::DISPATCH_HEADING` and `live/pipeline.py::WALK_DISPATCH_HEADING`
stay as they are. What this phase licenses is **stating the condition in the
documents and the presentation**, not re-sorting the shipped output.
[`dispatch_ordering.md`](dispatch_ordering.md) §8.

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
future-aware-only share **2.7×** Yeongdeok's, so the quasi-static
limitation was real and understated the benefit. ⚠ This sentence read "nearly
**seven times**" until 2026-09-03: that ratio was computed against the **retired**
영덕 share from the reverted run, not the canonical one. On the canonical field the
ratio is 2.7× (`docs/ssot_audit_2026-09-03.md` §2). What is **not**: that the
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

⚠ **PHASE 20 (2026-08-06) more than halved the routing line — for the SERVICE
path only.** The per-origin hazard table in `future_aware_route` is invariant
across a scan's origins and was being rebuilt 458 times; it is now built once
(`build_time_expanded_field`). Measured on the same machine, same coordinate,
before and after:

| | before | after |
|---|---:|---:|
| routing, 458 origins | 26.5 s | **10.9 s** |
| trigger → dispatch list (warm) | 26.9 s | **11.1 s** |
| manual coordinate → dispatch list (cold) | 29.6 s | **13.8 s** |

The counts, the routes and every delivered format are **bit-identical** — the
hoist is memoisation of a pure function, and the six-way regression is in
[`service_layer.md`](service_layer.md) §6.0.

⚠ **The BATCH runners are unchanged and still take ≈ 25–28 s per arm.** They
carry their own `classify()` loops and call `future_aware_route` with no field.
The rows above therefore still describe them; only the live/manual/replay path
is faster. Extending the hoist into the batch runners is a follow-up and needs
the same gate, because those scripts produce committed numbers.

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
| `spread_v2_lofo.json` trained on the defective Uljin-Samcheok DEM | Every fold saw the sea-fill. ⚠ *Corrected 2026-08-10: the effect IS measured* — `spread_v2_lofo_dem_corrected.json` (same day as this entry was first written): mean-of-folds +0.0048, pooled −0.0017, far-band −0.0357. What remains open is only whether a re-run ever REPLACES the committed artifact the submission cites — that choice is the user's. §4 |
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

> ⚠ Yeongdeok's `+1.2 %` below is the REVERTED run's field; on the canonical
> field it is **+316.1 %** (§2-A). The full note is a dozen lines down, which is
> too far for a reader who is scanning the table.

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
   method and parameters give a future-aware-only share **2.7×**
   Yeongdeok's, so the "quasi-static core" limitation was real and understated
   the benefit. ⚠ This sentence read "nearly **seven times**" until 2026-09-03,
   which is the ratio against the **retired** 영덕 share from the reverted run —
   inconsistent with the canonical shares listed two lines above, whose ratio is
   2.7× (`docs/ssot_audit_2026-09-03.md` §2).
   What is NOT established: that the benefit rises with fire speed —
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
| **headline AUC 0.890** | **UNAFFECTED.** Correcting the DEMs moves mean-of-folds +0.0048 and pooled −0.0017. The `elev_above_source_m` importance rank falls 8 → 15 and far-band AUC falls 0.0357; those are the real changes. `spread_v2_lofo_dem_corrected.json`. | <!-- collision-ok: 0.89 — the MEAN-OF-FOLDS headline (lofo_mean_of_folds_auc), not the pooled 0.905 (lofo_rowweighted_pooled_auc); this row's job is to report the DEM correction's effect on both, so both words appear. -->

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

> The **full register** — this table plus the coverage decision, the two
> deliberate stops, the accepted limits and the reversals, each with the
> condition that would reopen it — is [`DECISIONS.md`](DECISIONS.md). This
> section stays as the short list a PHASE-5 reader needs in place.

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
<!-- collision-ok: 5.2 — part of the DEM-defect narrative in this cell, not lofo_fold_rows_max_over_min (208.9). -->
| **`spread_v2_lofo.json` was trained on the defective Uljin-Samcheok DEM** | The headline mean-of-folds AUC is built over the six-fire set that includes `uljin_samcheok_2022`, whose raster filled the sea with a ramp to −497 m, so EVERY fold — including Yeongdeok's — trained on it. The same applies to `routing_demo.npz` and every Yeongdeok number derived from it. ⚠ *Corrected 2026-08-10: this entry used to end "the effect is unmeasured and could go either way", which contradicted §2-A in the same file — the effect was measured the same day this was written* (`spread_v2_lofo_dem_corrected.json`: mean-of-folds +0.0048, pooled −0.0017, far-band −0.0357, `elev_above_source_m` rank 8→15; its control arm reproduces the committed values on the pre-fix rasters). What is still true: **no committed artifact has been replaced** — those are Round-2 artifacts protected by §5.2, the registry headline still reads from `spread_v2_lofo.json`, and whether to ever publish the corrected lineage instead is the user's decision. [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md) §3. |
| ~~DEM re-acquisition~~ — **DONE 2026-08-02** | Both regions re-acquired, validated, snapshotted, re-simulated and re-routed; nodata 0.000 %, sim-grid mean-fill 0.00 %, both pass the gate with no acknowledgement flag. Superseded text: **This was the next action.** Two gaps, one fix. (a) `uljin_samcheok_2022_dem.tif` spans 36.85–37.45 °N while its walk bbox starts at 36.81 °N: **405 of 7,300 walk nodes (5.55 %)**, 6.17 % of elevation samples, timed FLAT. (b) BOTH new regions' simulation canvases were extended south past their DEMs in `a0eaf07`, so **10.0 %** (Uiseong-Andong) and **15.6 %** (Uljin-Samcheok) of simulation cells carry a MEAN-FILLED elevation — hazard is p = 0 in every one of them, so the committed fields are clean, but the fill was silent. `scripts/acquire_region_dem.py` is written, targets the UNION of walk bbox + simulation canvas + existing raster, validates coverage before installing, and refuses to mix providers. It needs `OPENTOPOGRAPHY_API_KEY` (env or the git-ignored `.env`); a keyless request is HTTP 401, confirmed 2026-08-02. **Do not route on a partial DEM and do not substitute AWS-Mapzen tiles.** |
| ~~Promote the hypothesis-refutation decomposition~~ | **Withdrawn.** The "fire-blind risk is near-constant" finding was an artifact of the pre-fix fields; it now reads 9.61 / 27.99 / 3.31 %. §2-A. |
| Which field to PUBLISH | Both `routing_demo.npz` (reverted run) and `routing_demo_canonical.npz` are in the tree with their provenance. The documents lead with the canonical one; **the submission materials have not been touched** and the choice of what to publish is the user's. |
| **`demo/wildfire_demo.html` is on the PRE-CANONICAL lineage** | **DECIDED 2026-08-06: keep the page, re-export it, and do that AFTER the operator dashboard** — re-exporting first would mean doing it twice. It is a 6-scene narrative pitch page and does NOT overlap `operator_screen.html`, which is the operator console; that is why it is worth keeping. But `scripts/export_demo_data.py` reads `routing_demo.json` and `routing_demo.npz`, the artifacts §2-A identifies as the reverted run's lineage, so the canonical figures a presenter would say aloud (458 / 414 / 42 / 2, 9.17 %) appear nowhere on it. It carries no HARD-forbidden value and labels its own hazard and terrain SYNTHETIC. ⚠ **Until re-export, do not cite it and do not demonstrate from it.** Provenance is recorded at the top of the exporter. |
| **`make check-forbidden` does not scan generated screens** | Retired-number rules apply to `.md` only, so a `.html` demonstration screen carrying a retired figure passes silently — which is how the row above went unnoticed. ⚠ **Recorded, deliberately NOT fixed:** widening the rules would flag a batch of existing demo assets at once and each needs its own decision. Two candidate shapes, and why the second is better, in [`forbidden_check_scope.md`](forbidden_check_scope.md) §"The gap this scope leaves". |
| Shelter-density experiment (within-region refuge decimation) | Requested 2026-08-02 as a way around n = 3: hold terrain and road network fixed, remove refuges at 100/75/50/25 % with repeats, and measure FA-only and `no_safe_route`. Sequenced after the DEM fix; the user will confirm before it starts. |
| ⚠ **`us-arm-b` WIP is parked in a git stash, not on any branch** | **PHASE 24 (2026-08-11) stashed it to switch branches, and stashes are invisible to `git log`, `git status` and `git branch` — if a session does not know it is there, it is lost.** `stash@{0}`, message **`PHASE24-preserve: us-arm-b WIP (spread_v2/model.py crs param, us_arm_b.json, run_us_lofo.py)`**, taken **on branch `us-arm-b`**. Contents: `src/wildfireguardian/spread_v2/model.py` +18/−1 (adds an opt-in `crs=` parameter to `footprint_iou_lofo`, defaulting to `None` → `EPSG:5179`, so every Korean call site and every committed Korean number is unchanged), plus untracked `data/processed/us/us_arm_b.json` and `scripts/run_us_lofo.py`. **To restore: `git checkout us-arm-b && git stash pop stash@{0}`** — check the index first, the stash list shifts as entries are added. ⚠ Do **not** pop it onto `ordering-boundary` or any Round-4 branch: it is US-transfer work (§ `us_transfer_arm0.md`, `us_comparison_table.md`) and does not belong in the Korean lineage. ⚠ Note `stash@{1}` is a **different**, older entry (`arm-b-session: figure pngs from dispatch-ordering`) and is not this work. |
| ~~PHASE 4 — live-operation feasibility~~ | **SUPERSEDED 2026-08-03.** It was scoped as investigation-only; PHASE 6 built the thing instead, and PHASE 12 added a second trigger into it. Nothing is outstanding. |
| PHASE 2-C-3 — hazard time resolution | Deprioritised: `no_safe_route` already moved 3→18 once the budget bound, so the budget was the main blocker. |
| `routing_demo.npz` not reproducible | Cause fully identified and **recoverable** — pin the grid to `bbox.fire_acquisition`. Not done: it would change results. |
| 407-run directionality | Uses `abs(dz)` (conservative). Documented, not changed. |
| `unclassified` in tight-budget buckets | Fixed by `fa_exceeds_budget`. No action. |
| **PHASE 16 findings are branch-only** | The whole dispatch-degeneracy investigation lives on **`hazard-resolution`** (11 ahead of `Main`, 58 behind, never merged): 32 files, ~38.5k insertions — 4 docs (`hazard_time_resolution.md`, `impassability_threshold.md`, `threshold_provenance.md`), 7 scripts, 4 test files, a new `routing/impassability.py`, `rescue.py` +97, and ~994 lines of registry. **What it established, and `Main` records nowhere:** the Yeongdeok real field's dispatch key degenerates because every closing corridor closes at t=0; time resolution (`6ed4edd`), the impassability threshold (`1c16630`) and a short horizon (`1b166fc`) were each tested and ruled out; the **corridor definition** is the cause (`1b166fc`); and the non-circular replacement `T_close` = latest feasible departure was built, validated and **shipped as an OPT-IN with the default unchanged** (`eeca0c6`). **Why the alternative was not adopted IS recorded** — in the `1b166fc` and `eeca0c6` commit bodies and in that branch's `hazard_time_resolution.md`: key B's survival is biased upward because `rescuer_route` selects a corridor *for* surviving (circular), key B conflates "when the fire cuts this approach" with "how much detour the network offered", and switching the default would re-order every committed dispatch list. ⚠ **Not merged here, and it should not be merged wholesale**: the branch also *adopts* `p_cut = 0.30` (`9ce563f`) and carries re-run `*_pcut030` artifacts, which is a routing-behaviour change to Round-2/3 numbers and is the user's decision. **DECIDED 2026-08-10** — (a) carry the *record* only: this row plus [`dispatch_ordering.md`](dispatch_ordering.md) §3, **prose, no numbers imported**. Done. (b) **DO NOT import** `closure_time_distribution.json` / `hazard_time_resolution.json` as registered artifacts. They were produced at cutoff **0.30** while `Main`'s config is **0.70**, and a registry holding two cutoffs' numbers side by side is the failure mode this repository has hit repeatedly. Any figure from that branch must be quoted with its branch AND its cutoff, or not at all. (c) the `p_cut = 0.30` adoption, `impassability.py` and the `ingress_deadline_mode` opt-in stay out until separately approved. |
| **The T_close deadline key is untested against ordering** | PHASE 23 compared four orderings under the **committed** deadline key (`ingress_survival − responder_ETA`, shortest-corridor mode). The `hazard-resolution` branch also built a non-circular alternative — `RescueConfig.ingress_deadline_mode = "latest_feasible_departure"`, T_close = the latest departure at which some depot still has a hazard-free route in (`eeca0c6`, opt-in, default unchanged). **Whether the ordering comparison comes out differently under that key has never been measured**, and the code is not on `Main`, so PHASE 23 did not test it. ⚠ Recorded, deliberately NOT done now. It is the natural next question only if (c) above is ever approved — testing it first would mean importing branch code to answer a question about a key this repository does not ship. |
| ~~Yeongdeok walk-bbox coverage~~ | **CLOSED 2026-08-03.** It is **32.6 %** on the canonical field (the superseded 50.4 % was measured against the reverted run's four-times-smaller core). Accepted, reported as a covariate, and carried by every absolute Yeongdeok rate. Not fixed, and not to be fixed — §2-A. |

---

## 4-B. ⚠ A process failure, recorded because it will recur

Across the PHASE 19–21 sessions, **five separate instructions arrived carrying
findings, measurements and completed work that did not exist in this
repository.** Each was approved in good faith as though a prior step had
produced it. Examples, all verified absent at the time:

| cited as established | what the repository held |
|---|---|
| "two service functions were polluting the numpy global seed" | none were. `convergence()`/`spatial_bias()` use `default_rng(seed)`; a measured request leaves the global digest unchanged |
| a PHASE-20 STEP 0 with options 1(a)/1(b)/3(a)/3(b)/3(c) and "26.6 s → 12.3 s" | no such investigation had been run |
| "1(a) multi-destination single search" as an optimisation to make | **already implemented** — `naive_route` runs 1.00 Dijkstras per origin, measured |
| "78 % of the time is the shelter search", "458 × 26 = 11,908 Dijkstra" | 13.5–28.2 % depending on region; ~458 solves, not ~11,908 |
| a completed PHASE 20 with "6/6 zero-diff", "_pick_best preserved", "20.7 s" | no code changed; no `_pick_best` exists anywhere; `20.7` appeared in no artifact |
| a STEP -1 with EN-dash width findings, a 34.2 s measurement, a "skill v2" | none existed; the progress model has 6 stages, not 22; `34.2` occurs once, as a latitude |

**Two of these reached the documentation before being caught.** The
"11,908 Dijkstra / 78 %" figure was written into `service_layer.md` from a
conversational summary rather than from the code, and had to be retracted in
place (§5 of that file). That is the failure mode to guard against: a number
that enters the docs by agreement rather than by measurement looks exactly like
one that did not.

**The standing rule, set by the user on 2026-08-06:**

> 앞으로 제가 특정 수치나 이전 작업을 인용하면, 저장소에서 확인되지 않는
> 경우 진행하지 말고 그 사실을 보고하십시오.

So: **before acting on a cited measurement or a cited prior step, check that it
exists.** `git log`, `grep`, the artifact. If it is not there, say so and stop —
do not reconstruct it, and do not build on it. Every one of the six rows above
was caught that way, and the cost of checking was a single grep each time.

⚠ This is not a remark about anyone's care. It is a property of long sessions
with a summarising context: a plausible number, once spoken, is indistinguishable
from a measured one unless somebody looks. This project's entire value is that
its numbers can be looked up. Look them up.

### ⚠ Round-4 addendum (2026-08-10): the VPD story — five checks, all negative

Two claims were cited across several sessions and used as premises for
approved work: **「VPD 단위 결함」** (a Magnus formula fed Kelvin, located at
`features.py:296`) and **「순열 중요도 11위→3위」**. When finally checked, all
five lines of evidence came back negative:

1. **`features.py:296` has never existed.** The file peaked at 273 lines in
   every revision on every branch (`spread_v2_xgb` variant: 197), and no
   revision of any `features.py` ever contained a Magnus computation.
2. **Both places that do hold a Magnus formula are correct from birth.**
   `spread_v2/weather.py vpd_kpa()` (created `c9e8f2f`) and
   `spread_v2_xgb/era5.py _relative_humidity()` (created `690008f`) carry the
   K→°C conversion in their creation commits; the only later commit touching
   either file is the package rename.
3. **The training data was never clamped.** The canonical table (151,904 rows,
   rebuilt in-memory, matching the pinned shape exactly) has `vpd_kpa` with
   0 NaN, 0 zeros, 0 negatives, range 0.20–3.56 kPa. Legacy Build A has no VPD
   feature at all.
4. **No artifact ranks `vpd_kpa` 3rd.** Committed rank 12 (+0.00097),
   DEM-corrected rank 11 (+0.00150, `spread_v2_lofo_dem_corrected.json`).
   Nothing on `us-acquisition` either.
5. **「-0.0004」, cited as the measured instantaneous-weather dependency and
   used to argue the spread layer was not worth improving, also has no
   basis.** The measured dependency is mean-of-folds **−0.0204** (A2 shuffle,
   `weather_dependency.json`) — 50× larger. The single repository value near
   −0.0004 is the Yeongdeok per-fire delta of the **DEM correction**
   (−0.00048, in `spread_v2_lofo_dem_corrected.json` `_meta`) — a different
   quantity entirely.

**And no change ever entered the tree under that name.** A message search over
every branch, the stash and the reflog finds no commit describing a VPD fix, a
unit fix, or a Magnus fix; the one commit message mentioning VPD is `c9e8f2f`,
which lists it as a derived feature. The approved "fix" changed nothing,
because there was nothing to change.

The correct sentence, wherever the 0.00097 figure appears: *0.00097 is the
committed, pre-DEM-fix importance; after the DEM correction it reads 0.0015.*
Never "before/after the VPD unit fix" — no such event exists in this
repository.

⚠ **Why this survived until five checks all came back negative:** every guard
this repository has is registry-based — retired tokens, forbidden phrasings,
protected digests. Those catch a *retired* number being re-quoted. They cannot
catch a citation whose event **never happened**, because there is nothing on
file to match against. The §4-B rule — look the citation up before building on
it — is the only defence for this class, and it is what caught it.

### ⚠ Round-4 addendum (2026-08-10): a branch-only artifact quoted as a Main fact

PHASE 23 opened with this premise, carried across several turns:

> 「회랑 폐쇄 시각 분포 — 영덕: t=0 에 0 %, 중앙값 360분으로 이미 측정됨」

**The measurement exists. It is not Yeongdeok's, and it is not on `Main`.**

`data/processed/closure_time_distribution.json` (`run_closure_time_distribution.py`,
commit `6491386`) lives **only on the `hazard-resolution` branch** — 11 commits
ahead of `Main`, 58 behind, never merged. Neither the artifact, the script nor
`docs/impassability_threshold.md` is in the working tree. What it measured, at
`vehicle_cutoff = 0.30` (a threshold adopted on that branch; `Main`'s config is
0.70):

| region / field | corridors | closed | at t=0 | after t=0 | never | t=0 share | closure times |
|---|---:|---:|---:|---:|---:|---:|---|
| **Yeongdeok REAL** | 118 | 40 | **40** | **0** | 78 | **100.0 %** | one value: 0.0 |
| Yeongdeok synthetic | 105 | 105 | 39 | 66 | 0 | 37.1 % | 0…150 min, 7 values |
| **Uljin-Samcheok REAL** | 114 | 17 | 1 | 16 | 97 | **5.9 %** | 0/180/360/540 → **median 360** |
| Uljin-Samcheok synthetic | 107 | 107 | 0 | 107 | 0 | **0.0 %** | 15…150 min, 7 values |
| Uiseong-Andong | — | — | — | — | — | N/A | zero mapped fire stations |

The cited profile — 0 % at t=0, median 360 — is **Uljin-Samcheok**. Yeongdeok's
real field is its exact opposite: every closure lands at t=0, one distinct
closure time, `sequential_closure_supported = false`. Two errors compounded —
the wrong region, and a branch-only result treated as an established Main fact.

**This is a new failure mode, distinct from the VPD one above.** There the cited
event never happened anywhere. Here it did happen, was measured carefully, and
was written down — on a branch that was never merged. `git log --all` finds it;
`ls` and `grep` over the working tree do not. So the §4-B check has to be
`git log --all` / `git branch -a --contains`, not just a working-tree grep, and
the answer must carry **which branch** and **under which config** the number was
produced.

It was caught before any work was built on it, and it changed the experiment:
Uljin-Samcheok was added as the second arm. **The exclusion it seemed to justify
did not survive re-measurement either** — at `Main`'s cutoff of 0.70 Yeongdeok's
real field has 42 closures at t=0 *and 3 at t=180*, two distinct times rather
than one, so the arm was run instead of dropped. That is the same lesson twice:
a number produced under a different config is a different number.
[`dispatch_ordering.md`](dispatch_ordering.md) §3.

⚠ **Also open, and separate:** that whole PHASE-16 investigation — the dispatch
degeneracy, its cause, and the alternative key that was reported but not adopted
— exists nowhere on `Main`. See §4 「PHASE 16 findings are branch-only」.

### ⚠ Round-4 addendum (2026-08-13): a claim counted one measurement nine times

PHASE 25 STEP 0 was a census of every defect this repository found in itself,
asked for in support of a claim of the form 「one system, three regions, N real
defects, decision shift measured for the first time」. **All three quantities in
that sentence were checked, and none survived.**

The census produced 156 confirmed defect records. Nine of them claimed a shift
in the routing classification. Walking the five commits that touch
`multi_region_comparison.json` and reading the same JSON path at each shows the
counts move in exactly **two** places — `9ba83b4` (DEM re-acquisition) and
`815dc02` (canonical-field switch). **The nine records are nine descriptions of
two events.** 「Three regions」 fails for a second reason: event 1 moved two
regions, event 2 moved one, and **no defect moved all three.** Novelty was never
investigated at all.

⚠ The census counts themselves (156 records, 9 claiming a shift) are a **session
tally with no committed artifact** — the same shape §8.1 of `decision_shift.md`
names as uncatchable. Quote them as such or not at all. A "thirty" figure also
circulates for this project; it is the **2026-08-09 Round-4 review's**
confirmed-findings count, not a census figure from this pass.

⚠ **This is a new failure mode again, and it is the quietest one yet.** The VPD
case was a citation whose event never happened. The closure-profile case was a
real measurement from the wrong branch. Here **every individual record is true**
— each was verified against an artifact — and the error is only in the
*aggregation*. Nothing in the registry can catch it: each row checks out, and
no gate counts distinct root causes. The defence is the same as §4-B's, applied
one level up: before quoting a count of findings, check whether the findings are
independent.

The scoped claim, the two caveats that must travel with it, the 7-key partition
correction and the two-axis distinction are all in
[`decision_shift.md`](decision_shift.md). The three retired sentence shapes are
registered in `scripts/check_forbidden.py` as `kind="claim"` rules.

⚠ **One correction this produced, recorded here because it changes a stated
control:** `multi_region.md` said 440/17/3 → 414/42/2 was "attributable to the
hazard field **alone**". Only one input changed, but that input is
simultaneously a different run, a corrected-DEM lineage and a larger canvas, and
the **denominator moved 460 → 458** because the origin frame is a function of
the field. Corrected in place; `decision_shift.md` §4.2.

⚠ **And one thing that survives only by luck.** Event 1 fixed three faults in
one commit — the sea-fill ramp, the 405-node footprint gap and the canvas
mean-fill — and **no artifact decomposes the Uiseong-Andong routing movement
into them.** Never attribute that movement to the sea-fill specifically; the
attribution in the `9ba83b4` body is prose reasoning, not a measurement.

A decomposition is nonetheless still *possible*, because the **defective rasters
are on disk** — `data/raw/firms_CANONICAL_TEST/uljin_samcheok_2022_dem.tif`
(`4850941d…`) and `…/uiseong_andong_2025_dem.tif` (`14288109…`), both matching
`dem_acquisition.json` `.acquisitions[*].replaced.sha256`. ⚠ But `data/raw/**`
is git-ignored and `data/snapshots/` holds only the *corrected* bytes, so these
files are **in no commit and would not survive a fresh clone. Do not delete
them.** (An earlier draft of this addendum said the bytes were unrecoverable and
the decomposition impossible in principle; both were wrong — `decision_shift.md`
§7.2, §10.)

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
22. **Never headline a COUNT of defects with a measured decision shift.** Two
    events move the routing classification, not nine and not thirty; a third and
    fourth exist on the responder axis and must be labelled as a different
    classification. **And never write 「three regions」 into that claim** — event
    1 moved two regions, event 2 moved one, none moved three. Registered as
    `kind="claim"` rules in `check_forbidden.py`.
    [`decision_shift.md`](decision_shift.md) §1.
23. **Never merge the two four-way classifications.** The routing axis
    (`both_safe` / `naive_into_FA_safe` / `no_safe_route` / `fa_exceeds_budget`,
    n = 458/368/393) and the responder axis (`rescue_routing.json`
    `.four_way_counts`, n = 439) have different names, denominators, lineages
    and hazard fields. Also: it is a **7-key** partition with three keys
    structurally empty in Korean runs, and `fa_exceeds_budget`'s code condition
    names no budget. `decision_shift.md` §2.
24. **Never describe the reverted-field 440/17/3 → 414/42/2 as a single-variable
    contrast**, and never write "N origins were reclassified" for it. The
    canonical field differs from the reverted one on three axes at once, and the
    denominator moved 460 → 458 because the origin frame is a function of the
    field — so the per-origin ledger that would settle the split does not exist
    **for this pair**. ⚠ It *does* exist for the DEM event and for the
    flat-vs-slope contrast (`origin_nodes_by_bucket`,
    `bucket_movement_vs_flat_control`), so check before assuming either way, and
    when you do quote a movement count say which definition it is: leaving
    `both_safe` and changing bucket are different numbers (Uiseong-Andong 83 vs
    90). `decision_shift.md` §3.2, §4.2.

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
   `--npz-out` / `--json-out`) pointing outside `data/processed`.** ⚠ **The
   second half of this rule used to read "The scripts all take one; the danger
   is the default, not the flag." That is false, and it was corrected
   2026-08-13 (PHASE 25 STEP 0).** Eighteen scripts reference `data/processed`
   and expose no out-flag at all; **ten of them write into it**:
   `run_forward_sim_region.py` (`forward_sim_regions.json` +
   `hazard_{fire_id}.npz`, `OUT_DIR` hardcoded at `:65`; its whole argparse
   surface is `--fires --cell-m --n-steps --step-hours --advance-threshold
   --p-cut --seed --walk-margin-km --acknowledge-fuel-gap`),
   `export_demo_data.py` (`demo_data.json` — **no `ArgumentParser` anywhere in
   the file**, `OUT` hardcoded at `:73`), `measure_weather_dependency.py`,
   `verify_rescue_routing.py`, `derive_walk_failure.py`, `crown_sensitivity.py`,
   `diagnose_crown.py`, `waf_sensitivity_sweep.py`, `run_ablation.py`
   (`yeongdeok_2025_ablation.json`) and `run_yeongdeok_validation.py`
   (`yeongdeok_2025_validation_results.json`) — the last two also with no
   `ArgumentParser` at all. For these the danger **is
   the absence of the flag**, and "re-run it to a scratch `--out`" is not an
   available path without editing the script first. Three more
   (`make_rescue_figures.py`, `make_routing_figures.py`,
   `make_ordering_boundary_figure.py`) write `docs/figures/*.png`, which §5.3
   forbids regenerating. [`decision_shift.md`](decision_shift.md) §7.2.
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
| [`DECISIONS.md`](DECISIONS.md) | **every decision this project has made** — settled, stopped, accepted, open and reversed — with the record that holds the evidence and the condition that would reopen it |
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
| [`service_layer.md`](service_layer.md) | **PHASE 19 — the service layer (job model, resource cache, progress, cancellation, guards) and PHASE 20 — the one result-invariant optimisation, plus §5.3 the optimisations DELIBERATELY NOT taken and why** |
| [`api_layer.md`](api_layer.md) | **PHASE 22 STEP 0 — the four endpoints; §1.11 the live-calculation refusal; §1.12 the console build input that can vanish** |
| [`photo_exif.md`](photo_exif.md) | **PHASE 22 STEP 2 — a coordinate out of a reported photograph, and the processing rules that are tested rather than promised** |
| [`console_regions.md`](console_regions.md) | **PHASE 22 STEP 3 — three regions in one built file, the measured payload decision, and the per-region reset** |
| [`screen_gate_scope.md`](screen_gate_scope.md) | **what the dash gate covers and why; ⚠ both of its original reasons were measured and found wrong, and it cannot see strings that arrive as JSON payload** |
| [`region_literals.md`](region_literals.md) | **⚠ READ §0. One region's values typed into text every region reads — the same defect three times, why single-region verification cannot reveal it, and the check now in `make verify`** |
| [`routing_limitations.md`](routing_limitations.md) | **Round-4 (2026-08-10): five measured limits of the routing layer — the bucket that names a cause the code does not establish, the objective-vs-report estimator gap, the slice-quantised 남은 시간, the non-Markov clock, the row-weighted importance. Recorded, deliberately not fixed; paired contrasts unaffected.** |
| [`dispatch_ordering.md`](dispatch_ordering.md) | **⚠ PHASE 23 (2026-08-10) — contribution ② measured against three alternative orderings over 360 configurations, four arms. The result is largely NEGATIVE: 시한 임박 순 beats 가까운 순 in 3.6 % of cells and in **0 of 180** at the committed 75-minute window. §3 records the arm that was approved for exclusion and then run anyway; §6 has the measured mechanism; §8 the three ways the claim can honestly be restated. Read it before writing contribution ② into any submission text.** |
| [`ordering_boundary.md`](ordering_boundary.md) | **⚠ PHASE 24 (2026-08-11) — the W axis of PHASE 23 filled in from 2 points to 12 (60…600), 2,160 cells. It does NOT reopen PHASE 23: that run's W=75 and W=240 values were re-derived cell by cell here, 3,744 values, **0 differences**. ⚠ **확정 서술 (§0, §7): 마감 기반 정렬이 이기는 셀이 존재하는 조건은 W ≥ 120분이나, 경계를 넘어도 규칙이 개선되지 않습니다. W = 600 에서도 승률 12.2 %, 패배율 68.3–82.8 % 로 커밋된 창(51.1 %)보다 높고, 평균 차이는 12개 W 전부 음수입니다. 승리 115개 중 100개가 지연 60분이며, 축 최초 승리 셀은 나머지 세 축이 동시에 최유리 끝값입니다. 즉 이것은 경계가 아니라 모서리이며, 유효 영역이라 부를 수 있는 것이 존재하지 않습니다.** This **strengthens** PHASE 23 rather than softening it: PHASE 23 measured invalidity at one committed point, PHASE 24 measured that opening the window 8× produces no valid region. Never write "조건만 맞추면 유효하다" — it takes all four axes at their extremes, 36 of 2,160 cells (1.7 %), to reach a win rate of even 50.0 %. **No single threshold exists** — not in W (min winning 120, max non-winning 600: the ranges fully overlap) and not in the distinct-deadline count (non-monotone; 1,580 non-winning cells sit at or above the lowest winning value). ⚠ **§6.3: PHASE 23 §6's mechanism is NOT a complete explanation** — it accounts for the floor (2 distinct deadlines → 0 wins in all 465 cells) but not for the 0 % at 6 and 7 distinct deadlines, and the outcome keeps moving (17.8 points, 영덕 real) while the count is frozen. The count is a label for (arm × W), not a free variable; §6.3 lists the three measurements that would be needed and states plainly that none was manufactured. §8.1: `W = 75` is marked `# ASSUMED` at `config/default.yaml:365` with **no measured basis anywhere in the tree** — quote the block there verbatim, and the limit statement is **「이 실험은 실제 운용이 경계의 어느 쪽인지 말할 수 없습니다」**. Read §1 before quoting anything.** |
| [`weather_dependency.md`](weather_dependency.md) | **PHASE 14 — how much of the model's skill is instantaneous weather, and the ceiling on a forecast-source swap** |
| [`baseline_phase13.json`](baseline_phase13.json) | **the frozen Korean baseline — every `data/processed` digest, the four PROTECTED paths, the LOFO shape, and the sha256 of the git-ignored `fire_manifest.json`. `make baseline-verify`.** |
| [`firefighter_consultation.md`](firefighter_consultation.md) | **현직 소방관 1인 비공식 구술 자문 (N = 1, 2026-08-28 작성). 임정호·이양원 교수, 안희영 센터장 자문과 동일한 성격 — 전문가 판단의 기록이지 측정이 아니며, 「현장 실무자 자문」으로만 인용합니다. 수치 0건, 등록 0건, 코드·설정·산출물 변경 0건.** ⚠ **§1 — 「시간 예산」이라는 개념이 현장 의사결정에 존재하지 않음을 확인**했습니다 (「실측값 미확보」로 적지 마십시오). 철수 판단은 경과 시간이 아니라 「살아서 나올 수 있는가」의 실시간 평가입니다. 이는 [`dispatch_ordering.md`](dispatch_ordering.md) 의 **W = 75 에서 마감 기반 정렬 0/180** 과 **독립적인 출처가 같은 방향을 가리키는** 사례이며, `config/default.yaml:365` 의 `# ASSUMED` 인 `W` 에 대응하는 현장 대응물이 없음을 뜻합니다 — ⚠ 두 근거를 하나로 접어 「입증됐다」로 쓰지 마십시오. **§3 — 「지금 불이 안 보이니까」 대피하지 않는다는 진술이, 병목이 탐지·예보가 아니라 전달·구조에 있다는 프로젝트 전제를 현장에서 직접 확인한 가장 강한 증거**입니다. 동시에 §3.2 가 그 반대면을 기록합니다 — 원인은 순응 실패이고 **순응은 본 시스템의 범위 밖**입니다. **§2** 조건부 우회가 현장 관행과 구조적으로 일치(⚠ 축이 다르고 커버리지 단서 필요), **§4** 우리 목적함수는 소방(인명 최소화) 쪽이며 산림청(확산 저지)이 아님, **§5** 실질 가치가 「도달 불가 판정」보다 「다수 가구 우선순위 배정」에 있을 수 있다는 함의(결정 아님), **§7** 대원이 GPS를 쓰지 않으므로 전달 계층 산출물이 좌표가 아니라 도로명·랜드마크여야 한다는 **장비 수준의** 제약. **§8 미확인 — 소속·직급·성함, 익명 처리 동의 여부(기본값 익명), 인터뷰 일시, 시간 범위, 의성 고립 사례의 출처 대조.** |
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
> 산출이 불가합니다. 더 넓은 3,926 km² 범위에는 6곳

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

⚠ **Addendum 2026-08-10: the paragraph above is true of `Main` ONLY, and a
next session planning from it would plan wrong.** On 2026-08-04 the
**`us-acquisition` branch** (unmerged, 4 commits) acquired **five California
fires**, added the archive-FIRMS (`_SP`) acquisition path that §13.6 item 7
records as missing, routed them, and ran an **Arm 0 transfer measurement**
(a later commit records the Arm 0 non-advance as seed-dependent). Its
acquisition by-products sit git-ignored in this working tree
(`data/snapshots_us/` holds the DEM/fuel tif payloads LOCAL-ONLY by that
branch's own recorded .gitignore policy — digests committed, payload
refetchable). **Whether that branch honoured this section's resume order
(PHASE 0.5 bundle isolation → PHASE 1 CRS before acquisition) is not
recorded anywhere** — audit it before building on the branch, and do not
re-acquire from zero without first looking at what it already holds.

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

---

## 14. PHASE 14 — real-time weather, MEASURED AND STOPPED (2026-08-03)

Branch **`realtime-weather`**, merged to `round3-dev`. Full write-up:
[`weather_dependency.md`](weather_dependency.md).

**Status: stopped on a measurement, not on a blocker.** The question was whether
ERA5 (~5-day lag) could be replaced by forecast data and what that would cost.
Before acquiring anything, the **ceiling** on that cost was measured. **No forecast
data was ever acquired.**

### 14.1 The archive question was settled first — affirmatively

`⚠ 소급 취득이 안 되면 실험 자체가 성립하지 않는다` was the brief's own first-order
question. Measured, not estimated:

| | |
|---|---|
| AWS `noaa-gfs-bdp-pds` | GFS 0.25°, **full forecasts f000–f384**, from **2021-01-02** (the `gfs.20210101/` prefix exists but holds **zero** `pgrb2` objects) |
| all six fire dates | **present, all four cycles** — verified `gfs.20220304`, `20220531`, `20230402`, `20230411`, `20250322` |
| **measured publication lag** | **+3 h 34 m … +3 h 51 m** for `f003` (`Last-Modified` on the `.idx`), against ERA5's ~5 days. Confirmed live: at 12:15 UTC the 12Z `f003` returned **404** |
| ECMWF IFS open data | earliest **2023-01-18** — **misses the two 2022 fires**. Cannot serve a six-fire retrain |
| TIGGE | covers the dates but is **6-hourly** — 4 of the 8 samples the pipeline needs |

⚠ **`miryang_2022` is NOT outside the archive.** `gfs.20220531` has all four
cycles. Any exclusion of that fire has to rest on some other reason.

### 14.2 The measurement that ended the phase

`scripts/measure_weather_dependency.py` → `weather_dependency.json`, six LOFO arms
on the identical dataset (rebuilds to the canonical **151,904 / 2,989**).

| arm | mean-of-folds | **far band** | pooled |
|---|---:|---:|---:|
| **A0** all sixteen | 0.8943 | 0.8408 | 0.9036 |
| **A2** shuffle the 6 instantaneous weather | −0.0204 | **−0.0344** | −0.0055 |
| **A1** drop those 6 | −0.0321 | **−0.1127** | −0.0084 |
| **A3** drop all 7 weather | **+0.0084** | **−0.2285** | −0.0316 |
| **A4** drop `days_since_rain` | **+0.0270** | **+0.0533** | −0.0143 |

**⚠ The ceiling is NOT noise, and the metric decides what you see.** On pooled AUC
the contrast is −0.0055 — no resolving power. On the **far band** it is −0.0344
<!-- collision-ok: 0.1127 — this is wxdep_drop_far_band_delta (−0.1127); wxdep_drop_all_weather_far_band (0.6124) is asserted on the next line. -->
shuffled and −0.1127 dropped. Removing weather entirely collapses the far band to
**0.6124**: *without weather this model cannot do far-field prediction at all.*

**⚠ And the top-ranked feature makes the model WORSE out-of-fold.** Dropping
`days_since_rain` (permutation importance **+0.07726, rank 1**) *raises*
mean-of-folds **+0.0270** and the far band **+0.0533** while lowering pooled
−0.0143 — `gangneung_2023` alone moves **+0.1705**. The mechanism is in the data:
the feature counts from the start of the ERA5 window where no sampled step
exceeds 1 mm, and for three of six fires (gangneung, uiseong_andong, yeongdeok)
the window contains **zero** wet samples — so for half the training set the
feature is anchored to an acquisition decision, not to rain. *(Corrected
2026-08-10: this entry previously said it "equals the window length exactly
(2.88/6.88/6.88 d)" and is "a per-fire constant"; the canonical table measures
otherwise — one value per overpass step, e.g. gangneung a single 0.125 d,
uiseong_andong 17 values 0.25–5.25 d. The measured wording is in
`weather_dependency.md` §3②; the ablation deltas are unaffected.)*

**⚠ Every weather ablation moves mean-of-folds and the far band in OPPOSITE
directions.** "Is weather important to this model?" has opposite answers on the
two metrics and both are real.

### 14.3 What may and may not be said

> 순간 기상 자료원 교체의 성능 저하 **상한**은 폴드평균 −0.0204, 원거리대
> −0.0344입니다 (해당 특징을 완전히 셔플한 경우). 실제 예보는 그 양들에 대해
> 일부 정보를 보유하므로 실제 저하는 이보다 작습니다. **전환은 실측되지
> 않았습니다.**

⚠ **Never** write "we switched to forecast data", "the switch costs nothing", or
"weather does not matter". None was done and none is known. `days_since_rain`
cannot be rebuilt from a forecast at all (a forecast has no precipitation history
before initialisation), so keeping it means **reanalysis access is still
required** — the configuration is not full real-time operation.

Four registry entries carry these with their forbidden phrasings:
`wxdep_shuffle_far_band_delta`, `wxdep_drop_far_band_delta`,
`wxdep_drop_days_since_rain_mean_delta`, `wxdep_drop_all_weather_far_band`.

### 14.4 A pre-existing defect the phase surfaced

The ERA5 request samples **8 of 24 hours** per day and `tp` is a **one-hour**
accumulation. So `precip_24h_mm` sums nine one-hour accumulations and calls the
result a 24-hour total — at most **0.375×** the true figure, and phase-dependent.
A 12-hour 0.5 mm/h event (6 mm) never trips the 1 mm threshold in any phase. Both
precipitation features are miscalibrated against their own docstrings. **Not
fixed** — fixing it re-requests ERA5 at all 24 hours and moves the committed
baseline.

### 14.5 Resume condition

1. **Resolve `days_since_rain` first.** If it is largely an acquisition artifact,
   the agreed "keep it on ERA5" design preserves the artifact *and* pays the
   mixed-source cost, while the drop configuration is cleaner and scores better.
2. **Pre-declare the far band as the primary metric.** Pooled AUC was shown to
   have no resolving power for this contrast.
3. Then acquire. The mapping is worked out and is in `weather_dependency.md` §6
   and the phase record: four of five ERA5 variables map to GFS with **no
   conversion**; only precipitation breaks, and it breaks differently in each
   model (GFS `APCP` is kg m⁻² with **two** records — a 6-h resetting bucket and a
   run-total — while the repo assumes metres; IFS `tp` is monotone-cumulative in
   metres, which would pin `days_since_rain` at 0 forever **silently**, because
   the units match ERA5).
4. ⚠ Confirm the GRIB2 earth-relative wind flag with one header read before
   writing any code; a wrong assumption silently rotates every bearing.

**No GFS mapping code was written.** There is nothing dormant to maintain.

### 14.6 LDAPS — recorded, not used

KMA LDAPS (~1.5 km) is excluded from this experiment because it is Korea-only and
conflicts with the portability goal. It is recorded here as the **Korea-only
high-resolution alternative**, and it is the natural answer to the question of
whether ERA5's ~31 km effective resolution can see 양강지풍 downslope wind at all —
which `weather_dependency.md` §4 flags as unresolvable with the current data.
