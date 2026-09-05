# The decision register

**What was settled, on what evidence, and what would reopen it.**

Written 2026-09-05 against `c0bd560`. This file **indexes decisions; it does not
hold evidence.** Every row points at the document that carries the measurement,
and where the two ever disagree the linked record wins — a register that becomes
a second source of truth is worse than no register at all.

Until now the decisions of this project were spread across a 1,800-line handoff,
sixty documents and 124 commit messages, and the only way to find out whether a
question was already closed was to know where to look. The cost of that shows up
as relitigation: a settled question re-opened because its record was three files
away from the work.

**Two deliberate omissions.**

1. **No retired number appears here.** The withdrawn severity-vs-direction
   ratio, the reverted run's counts, the superseded coverage figure: each is
   named in its own record with its own caveat, and a register that repeated
   them would be a new place for them to be quoted from.
2. **No decision is made here.** Everything in this file was decided somewhere
   else, by a measurement or by the user. If a row looks wrong, the record it
   links to is what needs fixing.

Bare **§ references are sections of [`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md)**,
which is where most of this was written down first.

## How to read the status column

| status | meaning |
|---|---|
| **SETTLED** | closed. Do not relitigate; the "reopens it" column is the only door back in. |
| **STOPPED** | investigated, then deliberately halted with a written resume condition. Not abandoned, not half-done. |
| **ACCEPTED** | a real limitation, measured, recorded and deliberately **not** fixed. Fixing it would move committed results. |
| **OPEN** | genuinely undecided, and the decision is the user's. |
| **REVERSED** | a decision or a claim that did not survive. Kept, because the reversals are the record. |

The standing rules that came out of these decisions are in
[`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §5 ("Never do these", 21 items, each one
learned from something that went wrong). This register says *why* those rules
exist; §5 says what not to do.

---

## 1. Model and evidence

| decision | status | settled | why, and what reopens it |
|---|---|---|---|
| **The primary spread model is data-driven, not physics-first** | SETTLED | 2026-06 | The Rothermel surface model captured only ~9 % of the burned area, and an apparent crown-fire result was retracted as a foliar-moisture conflation bug. The negative result *is* the reason for the pivot. The physics modules are retained and sound; only the headline capture claim was wrong. [README research log](../README.md#research-log--superseded-approaches-physics-model), [`BLOCKERS.md`](BLOCKERS.md) Sessions 5–7. Reopens: nothing planned. |
| **The canonical estimator is sklearn `HistGradientBoosting`** | SETTLED | 2026-07-23 | The earlier gradient-boosted re-train (`spread_v2_xgb/`, superseded) is kept for provenance and imported by no runtime module; its dependency moved to a legacy extra. Misattributing the canonical model is a HARD violation of `make check-forbidden`, in code comments as well as prose. `3f7c261`, `2cb878a`. Reopens: never — this is a naming fact, not a preference. |
| **Interval estimates are DeLong CIs against stated baselines** | SETTLED | 2026-06-14 | The t-interval it replaced does not apply to an AUC. `022c3bc`, [`auc_intervals.md`](auc_intervals.md). |
| **The severity-vs-direction headline claim is withdrawn, not caveated** | SETTLED | 2026-08-08 | It compared a six-feature sum against a single variable, on a 0.25° (~28 km) weather grid that cannot resolve the local wind the claim is about. The measurement is retained with its limits; the conclusion is not. A third checker severity exists specifically to catch it being restated bare. `9f40127`, `ce3ea64`, `ac7a4ad`, [`forbidden_check_scope.md`](forbidden_check_scope.md). Reopens: a wind product that resolves local wind, plus a like-for-like comparison. |
| **The DEM-corrected LOFO re-run does NOT replace the committed artifact** | SETTLED | 2026-08-02 | The submission cites `spread_v2_lofo.json`; the corrected lineage lives beside it under its own name with its provenance. The correction moves mean-of-folds +0.0048 and pooled −0.0017 — the headline is unaffected — and its control arm reproduces the committed values on the pre-fix rasters. [`dem_defect_2026-08-02.md`](dem_defect_2026-08-02.md), §2-A. |
| **Which lineage the submission materials should publish** | OPEN | — | Both fields are in the tree with their provenance and the documents lead with the canonical one. The submission materials have not been touched, and the choice is the user's. §4, §1.5. |

## 2. The hazard field, and which artifacts are current

| decision | status | settled | why, and what reopens it |
|---|---|---|---|
| **The canonical field is the lineage everything downstream reads** | SETTLED | 2026-08-02 | `routing_demo.npz` turned out to be the surviving output of a run reverted the next day, so everything under it had been measured on a field nobody chose. The investigation that established this is committed (`routing_demo_divergence.json`); the model code was byte-identical, the input data was the variable. §2-A. |
| **The reverted run's output is kept, never presented as a version of the same thing** | SETTLED | 2026-08-02 | Two files that look interchangeable and are not. Say which one produced a number. §5 rule 20. |
| **Committed artifacts are never modified; new results get new filenames** | SETTLED | Round 3 PHASE 0 | Four protected paths are digest-checked and every runner exits 4 if one moves; `run_multi_region_routing.py` refuses Yeongdeok outright. This is what makes "the submitted state is still there" a checkable claim rather than an intention. §5 rules 2 and 18, `make baseline-verify`. |
| **`routing_demo.npz` is not made reproducible** | ACCEPTED | Round 3 | The cause is fully identified and the fix is known (pin the grid to `bbox.fire_acquisition`). Not done, because doing it would change results. §4. |
| **`docs/figures/*.png` are never regenerated** | SETTLED | Round 3 | The submitted documents cite them. §5 rule 3. |

## 3. The sampling frame, and the three regions

| decision | status | settled | why, and what reopens it |
|---|---|---|---|
| **Yeongdeok's walk bbox is NOT re-drawn; 32.6 % coverage is reported as a stated limit** | SETTLED | 2026-08-02, **confirmed final 2026-08-03** | Decided on numbers, not discomfort: a covering bbox is cheap to download but does **not fit the simulation grid** (−1.5 km clearance against a 5 km requirement), so it is not a bbox change but a full re-simulation and a re-run of steps 1–3. The price of not re-acquiring is exactly one thing — absolute rates need a caveat — while **every paired contrast stays valid**, because both arms share the origins and the sampling frame cancels. The caveat is applied mechanically by `build_numbers.py` and travels onto every A4 sheet the live pipeline emits. §2-A, [`walk_bbox_coverage.md`](walk_bbox_coverage.md). ⚠ Reopens: **only** new information about the canvas coupling itself. |
| **The simulation canvas is extended southward for the two new regions only** | SETTLED | PHASE 5 | Uljin's walk bbox fell 4.44 km outside its hazard grid, where nodes read p = 0 and look safe. The envelope is bit-identical before and after, so nothing was being clipped and the extension biases nothing. `config: grid.simulation_bbox_extension`. |
| **`stride 18` on the real-OSM path, identical for all regions** | SETTLED | PHASE 5 | Origin counts then differ with road density, and that difference is part of the comparison rather than noise in it. |
| **Envelope-size differences are not normalised** | SETTLED | PHASE 5 | Choosing a denominator would be a new arbitrary decision. Report raw, with envelope area as a column. |
| **Uiseong-Andong runs without depots, and is recorded as `responder_side_available: false`** | SETTLED | PHASE 5 | Its ignition-centred 919 km² box contains no `amenity=fire_station` in OSM; the wider 3,926 km² manifest box contains six. Widening the tag set or the bbox for one region would break the identical-rule design the comparison rests on. ⚠ **Never** written as "Uiseong-Andong has no fire stations" — §5 rule 11. |
| **The OSM cache is per region** | SETTLED | PHASE 5 | Fixed filenames meant a second region's fetch overwrote the first. `tests/test_osm_cache_isolation.py`. |
| **PHASE 5 extends the 459 series, not the 439 series** | SETTLED | PHASE 5 | The 459 path consumes a real hazard field. Consequence: three buckets, so the cross-region metric is the **share of origins safe only on the future-aware route** (Yeongdeok 42/458 = 9.17 % on the canonical field) — ⚠ never called `w`, which is a 439-series quantity on a synthetic envelope and cannot be computed inland at all. §5 rule 13, [`multi_region.md`](multi_region.md). |
| **The synthetic terrain/hazard path is excluded** | SETTLED | PHASE 5 | `build_real_demo` fabricates a coastline on the eastern 12 % of any bbox. Uiseong-Andong is inland: it would invent a sea. |
| **`osmnx == 2.0.7` is pinned** | SETTLED | PHASE 5 | It matches `created_with` inside the snapshot graphml. Floating it puts a second variable into every before/after comparison. `make env-check` fails on drift. |
| **Cross-region numbers are never quoted without the OSM-completeness covariates** | SETTLED | PHASE 5 | Otherwise "regions differ" cannot be told from "mapping differs". With n = 3 and three covariates moving together, the register also forbids ranking on the FA-only column alone. §5 rules 7, 12, 14. |

## 4. The operational path

| decision | status | settled | why, and what reopens it |
|---|---|---|---|
| **The live pipeline consumes the 459/canonical series** | SETTLED | 2026-08-03 | It follows from the PHASE-6 brief: canonical field, snapshot network, real hazard. The 439 outputs are untouched; the two lineages co-exist with different filenames and different wording (459 sheets say 도보, never 차량). §4. |
| **The claim is "real-time detection on a pre-computed field", never "real-time forecast prediction"** | SETTLED | PHASE 6 | FIRMS NRT publishes within ~3 h; ERA5 publishes on a ~5-day lag, so no hazard field exists for today. A detection decides *whether* and *where* to act; it does not move the surface. The scope strings live once in `live/scope.py` so a retyped caveat cannot drift, and the weather basis is derived from the committed detections rather than typed. [`live_pipeline.md`](live_pipeline.md), §9. |
| **Email is the transmitting channel; SMS stays in demo mode** | SETTLED | PHASE 7 | The Twilio trial account cannot verify a Korean mobile number, so SMS cannot reach the demonstration handset; email reaches the same two audiences. ⚠ The safety claim **changed** with it: not "nothing is ever sent" but "nothing is sent without an approval token". Three independent locks, none skippable, and the absence of a skip is asserted against the AST. [`delivery_channels.md`](delivery_channels.md), §10. |
| **The service layer stops one layer short of a transport** | SETTLED | PHASE 19 | `tests/test_service_layer.py::test_the_service_package_contains_no_web_server` asserts it. The HTTP transport, when it came, was added as a separate thin `api/` layer over the same job model — which is the shape PHASE 19 was built for. [`service_layer.md`](service_layer.md), [`api_layer.md`](api_layer.md). |
| **The routing arithmetic was not touched while the structure moved** | SETTLED | PHASE 19 | A refactor that also improved the routing would make "the answer did not change" unfalsifiable. Structure first, arithmetic later. [`service_layer.md`](service_layer.md) §5. |
| **The one optimisation taken is memoisation of a pure function** | SETTLED | PHASE 20 | The time-expanded hazard table does not depend on `start`, so a 458-origin scan was rebuilding one identical array 458 times. Allowed **because** every origin is handed the same object and the answer cannot move; a 6/6 zero-difference regression against a pre-PHASE-19 worktree is the evidence. Service path only. |
| **Process parallelism, an osmnx settings lock, and delivery-as-service functions are deferred** | SETTLED | PHASE 19 | Decided, not forgotten, and each with a written pick-up condition — process parallelism in particular interacts with concurrency that already exists, so deciding now would be deciding without the number that matters. [`service_layer.md`](service_layer.md) §6.5. |
| **Both screens are kept, and they do different jobs** | SETTLED | PHASE 8 | One demonstrates, one explains a limit. Neither is a draft of the other. §11. |
| **The narrative demo page is kept and re-exported after the console** | SETTLED | 2026-08-06 | It is a six-scene pitch page and does not overlap the operator console, which is why it is worth keeping — but it reads the pre-canonical lineage, so ⚠ **until it is re-exported, do not cite it and do not demonstrate from it**. Re-exporting before the console would mean doing it twice. §4. |
| **A reported photograph yields a coordinate and nothing else** | SETTLED | PHASE 22 | Four EXIF tags are read, the coordinate enters the same gate as every other coordinate, nothing is stored and the filename never leaves the browser. It is a different way of answering "where", not a different pipeline. [`photo_exif.md`](photo_exif.md). |

## 5. The verification layer

| decision | status | settled | why, and what reopens it |
|---|---|---|---|
| **Every reportable number is registered and re-derived from its artifact** | SETTLED | PHASE 1 | Round 2 had no way to answer "is this number still true?" without checking by hand. `make verify` re-derives each entry and scans the prose for retired figures; `verify_numbers.py` holds no knowledge of any specific number, so the registry stays the single source of truth. [`NUMBERS.json`](NUMBERS.json). |
| **"Verified" and "reproducible" are tracked as different properties** | SETTLED | PHASE 1 | Entries whose inputs were destroyed on 2026-07-24 are verified but not reproducible. "Not reproducible" is not "wrong", and before Round 3 there was no way to say which was which. [`network_drift.md`](network_drift.md). |
| **Retired-number rules apply to authored prose (`.md`); word rules apply everywhere** | SETTLED | PHASE 1-F | A retired number misleads exactly when it reads as a current claim, and claims live in prose; a `"n_origins"` inside a JSON artifact is that run's own record and must stay legible. Every skipped match is counted and printed on every run, so the scope can never quietly hide anything. [`forbidden_check_scope.md`](forbidden_check_scope.md). |
| **The gap that scope leaves — generated screens — is recorded, not fixed** | ACCEPTED | 2026-08-06 | Widening the rules to `.html` would flag a batch of existing demo assets at once, and each needs its own decision. Two candidate shapes, and why the second is better, are written down. [`forbidden_check_scope.md`](forbidden_check_scope.md). |
| **Every checker carries a ratchet, and every ratchet entry carries its reason** | SETTLED | PHASE 21–22 | The floor is where the tree stands today and may only go down. An entry in one has been *looked at* — that is the difference between a ratchet and an exemption, and it is why there is deliberately no whole-file escape hatch. [`region_literals.md`](region_literals.md), [`screen_gate_scope.md`](screen_gate_scope.md). |
| **The `NEAR_WINDOW` for the near-label severity is measured, not chosen** | SETTLED | 2026-08-08 | ±10 lines, from a false-positive/detection table across four candidate windows on the tree before and after the caveat pass. The natural way to caveat a table is a block quote above it, which is why the same-line rule the other severity uses cannot work here. `scripts/check_forbidden.py`. |
| **Acquired data is snapshotted immediately, never left in `data/cache/`** | SETTLED | PHASE 1 | `data/cache/**` is git-ignored, and that is exactly how the 2026-07-23 graph died. `make snapshot-verify` re-hashes the store. |
| **The acquisition record is never edited** | SETTLED | PHASE 1 | `fire_manifest.json` defines the training set and is git-ignored, so it would otherwise be changeable with no diff at all; `make baseline-verify` pins its digest. Simulation-side changes belong in `config`. §5 rule 9. |
| **A cited number or a cited prior step is checked against the repository before anything is built on it** | SETTLED | 2026-08-06 (user) | Across three sessions, five instructions arrived carrying findings, measurements and completed work that did not exist here, and two reached the documentation before being caught. Every guard this repository has is registry-based: they catch a *retired* number being re-quoted, and cannot catch a citation whose event never happened. Looking it up is the only defence for that class, and it costs one grep. §4-B. |

## 6. Investigated, then stopped — with the condition to resume

| line of work | status | stopped | the condition |
|---|---|---|---|
| **International portability (PHASE 13)** | STOPPED | 2026-08-03, before any acquisition | A four-minute talk already carries three regions, the live path and the operational outputs; the value of an international arm accrues in 2027. Nothing is half-done on `Main`. ⚠ The unmerged `us-acquisition` branch **does** hold acquisition work, and whether it honoured the resume order is not recorded anywhere — audit it before building on it. Resume order, and the CRS trap that would otherwise manufacture its own headline: §13.7. |
| **Real-time weather (PHASE 14)** | STOPPED | 2026-08-03, on a measurement | The archive question was settled affirmatively first, then the **ceiling** on the cost of switching sources was measured before acquiring anything. No forecast data was ever acquired and no mapping code was written, so there is nothing dormant to maintain. Resume: resolve `days_since_rain` first, and pre-declare the far band as the primary metric — pooled AUC was shown to have no resolving power for this contrast. [`weather_dependency.md`](weather_dependency.md), §14. |
| **Hazard time resolution (PHASE 2-C-3)** | STOPPED | Round 3 | Deprioritised: the budget was the binding constraint, and it moved `no_safe_route` on its own. §4. |
| **Shelter-density experiment** | OPEN | requested 2026-08-02 | A way around n = 3 that holds terrain and network fixed. Sequenced after the DEM fix, not started; the user confirms before it begins. §1.5. |
| **Live-operation feasibility (PHASE 4)** | STOPPED | 2026-08-03 | Superseded: it was scoped as investigation-only, and PHASE 6 built the thing instead. Nothing outstanding. |
| **KMA LDAPS** | STOPPED | PHASE 14 | Recorded, not used: Korea-only, so it conflicts with the portability goal. It stays on file as the natural answer to whether ERA5 can resolve 양강지풍 downslope wind at all. §14.6. |

## 7. Measured, recorded, deliberately not fixed

Each of these is a real defect or a real limit. None is fixed, and the reason is
the same in every case: every committed count in this repository was produced by
this code as it stands, so changing the logic would move all of them at once.
Paired contrasts are unaffected throughout — both arms run through the same code,
so the limit divides out.

| limit | record |
|---|---|
| Five routing-layer places where the mathematics is narrower than its description, including a bucket whose name asserts a cause the code does not establish | [`routing_limitations.md`](routing_limitations.md) |
| `precip_24h_mm` sums nine one-hour accumulations from an 8-of-24-hour sampling and calls it a daily total; both precipitation features are miscalibrated against their own docstrings | §14.4 |
| The 407-run treats slope with `abs(dz)` (conservative) | §4 |
| Two region literals that are correct on every path that can reach them today (a console `aria-label` overwritten on first mount, a build-stdout line reached only when the count is 0 by construction), and one example timestamp in a dataclass comment | [`console_regions.md`](console_regions.md) §10, [`region_literals.md`](region_literals.md) §6 |
| A responder sentence whose EM dash still renders in one place | [`console_regions.md`](console_regions.md) |

## 8. Reversed — decisions and claims that did not survive

The reversals are not an embarrassment to be tidied away; they are most of what
this register is for. A project that cannot say which of its past conclusions it
has dropped cannot be checked at all.

| what was held | status | what happened |
|---|---|---|
| The "quasi-static core" limitation of the Yeongdeok fire | REVERSED | It was a property of the reverted hazard field, not of the fire. On the canonical field the core advances fastest. §2-A. |
| "The DEM defect's effect on the headline is unmeasured and could go either way" | REVERSED | Corrected 2026-08-10: it had been measured the same day the sentence was written, in the same repository. The entry now carries the measurement, and what remains open is only whether the corrected lineage ever replaces the committed artifact. §4. |
| The shelter-search cost figures in the service-layer write-up | REVERSED | Retracted in place 2026-08-06. Both halves were wrong and both had been written from a conversational summary rather than from the code; the multi-destination single search they proposed was already how it worked. [`service_layer.md`](service_layer.md) §5. |
| A VPD unit defect, its permutation-importance jump, and the fix for it | REVERSED | Five independent checks all came back negative (2026-08-10): the cited source line has never existed, both real Magnus formulas carry the conversion in their creation commits, the training table was never clamped, no artifact ranks the feature where it was said to rank, and no commit on any branch, stash or reflog describes such a fix. The approved change altered nothing because there was nothing to change. §4-B addendum. |
| "The fire-blind risk is near-constant" (the hypothesis-refutation decomposition) | REVERSED | Withdrawn: an artifact of the pre-correction fields. §4. |
| "전달 문구는 모사이며 실제 발송하지 않습니다" | REVERSED | Superseded at PHASE 7. The email channel can transmit, so the old wording would now understate the system. The current wording is in §10. |

---

## Where the records live

| for | read |
|---|---|
| the full Round-3 state, and §5's 21 standing rules | [`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) |
| what changed when the hazard field was corrected | [`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §2-A |
| every reportable number, its derivation and its caveat | [`NUMBERS.json`](NUMBERS.json), `make verify` |
| the model, its inputs and its limits | [`MODEL_CARD.md`](MODEL_CARD.md) |
| known limitations by session, including the physics era | [`BLOCKERS.md`](BLOCKERS.md) |
| reproducing any of it from a fresh clone | [`REPRODUCE.md`](REPRODUCE.md) |
