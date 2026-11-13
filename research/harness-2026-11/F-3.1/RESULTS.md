# F-3.1 results: the deadline field on the six recorded planner caches (1-hour panel)

Status: **final 1-hour reproduction numbers, VERIFIED: Nora, request #2, PASS WITH NOTES on all 6 caches (ledger row 25 @4ed6b8cb)**. The F-DYN multi-hour, forecast-ablation,
unknown-support and clean-timing results are reported separately once run. All numbers below are measured. Anything
not measured is labelled as such.

## What was run

* **Code and inputs.** Code at commit `70f70d7`, run from a clean worktree. The verified commit `c8247d2` also contains changes made after `70f70d7`. These are inactive on these caches: origin = destination admission (0 such jobs), a start-position scope guard, the per-journey dose duration bound in the precondition output, and the `--timing-only` flag. It also contains the opt-in packet modes `extra_blocks`/`present_only` in `real.py` and the `postprocess.py`/`export.py` helpers, which the reproduction does not use. The ablation, unknown-support and F-DYN modules present at `c8247d2` were removed from the frozen 1-hour cut (PR #133); on this working branch they are present for the follow-up claims below, with their own verification. Inputs are the frozen routing inputs
  (`tools/fetch_routing_inputs.py`, SHA-verified) and the six committed `planner/cache` files (SHA as in `INDEX.json`).
* **Host.** This Linux x86_64 container: 4 cores, Python 3.13.18. numpy was 2.x at process start, and 1.26.4 was
  installed into site-packages during the run. numpy is used only to read arrays; all contact arithmetic is exact
  rational. 4 processes ran in parallel.
* **Fields.** For every destination spec of a file (node, dwell, window), one backward field per rule variant:
  * `router`: the full-policy router's sampling rule;
  * `cert`: the router rule OR the closed-footprint whole-road rule;
  * `free`: no fire at all, the control.
* **Jobs read off the fields.** Every route-check job of the file is read off them: 9,722 jobs. That includes
  originals replaced by re-checks, and the research checks.
* **Witness checks.** Every `cert` witness was checked by the **unchanged** full-policy checker
  (`routing-package/routing/independent.py::check_route`: flame, peak, dose including the dwell, continuity, turns,
  admission, opening, horizon) **and** by the closed-footprint replay (`tools/explain_deadlines/replay.py`).
* **Certificate.** Every field passed `core.check_fixed_point`, the order-independent unique-fixed-point check.

Reproduce one file (about 20 to 45 min with verification; `--timing-only` skips the certificate check and the
full-checker pass):

```sh
python3 tools/fetch_routing_inputs.py
cd research/harness-2026-11/F-3.1
python3 -m deadline_field.reproduce ../../../planner/cache/uiseong_andong_2025/20250323T010000Z.json --out /tmp/f31/ua0323.json
python3 -m deadline_field.analyze /tmp/f31/ua0323.json
```

The committed summaries are in `results/`:
* `SUMMARY_final_70f70d7.json`: the per-file tables below;
* `DEADLINES_per_origin.json`: 530 origins, recorded and field deadlines;
* `AT_ISSUE_cells.json`;
* `UNRESOLVED_cells_resolved.json`;
* `ISSUE_ORDER_BY_1h.json`.

## 1 Reproduction of every recorded verdict

| file | jobs | checked = recorded (identical route) | no-route = recorded | AT_ISSUE (origin point in flame) | recorded UNRESOLVED → field |
|---|---:|---:|---:|---:|---|
| UA 03-23 01Z | 1,523 | 1,188 (1,188) | 335 | 0 | none |
| UA 03-24 09Z | 1,518 | 1,158 (1,158) | 354 | 6 | none |
| UA 03-25 17Z | 1,557 | 1,029 (1,029) | 399 | 90 | 39 checked |
| YD 03-25 19Z | 1,810 | 1,400 (1,400) | 161 | 54 | 122 checked, 73 no-route |
| YD 03-25 23Z | 1,673 | 1,486 (1,486) | 138 | 0 | 26 checked, 23 no-route |
| YD 03-26 08Z | 1,641 | 1,510 (1,510) | 81 | 36 | 12 checked, 2 no-route |
| **total** | **9,722** | **7,771 (7,771)** | **1,468** | **186** | **199 checked, 98 no-route** |

* **Zero disagreements** with any recorded `checked_route` or `model_no_route`.
* Every recorded checked route is reproduced with the **same arrival second and the identical leg sequence**: 7,771
  of 7,771, under the `cert` variant.
* Every recorded no-route is infeasible in both the `router` and `cert` fields.
* **AT_ISSUE.** All 186 recorded `AT_ISSUE_FAILURE` cells have the origin point in flame under the router's own
  at-issue rule at that departure second. The field states them as definite "no journey departing this second",
  not unresolved.
* **Recorded UNRESOLVED (297).** 199 are feasible in the `cert` field, and the witness passes the unchanged full
  checker. 98 are infeasible under the `router` rule, which is a no-route proof within the model. These are changes
  in status against the recorded cells (an accuracy gain), not disagreements.

## 2 Deadlines: window-set and fire-set, with the fire-free control

* **Planner deadlines.** The planner deadline (latest offset with a checked attempt) equals the recorded one for
  **528 of 530** origins, in both the `router` and `cert` variants.
* **The two others.** Both are research origins whose recorded cells were UNRESOLVED and are resolved by the field:
  * YD 19Z FX2: recorded "no deadline". Field: checked at +0/+10 min, proven no-route from +20 min, exact 968 s.
  * YD 23Z FL2: recorded +0 min. Field: checked at +10 and +20 min, exact 1,558 s.

Class (`cert` field compared with the `free` control):

| class | origins | matched |
|---|---:|---:|
| fire-set: deadline differs from the fire-free control | 17 | 16; the other is FX2 above |
| window-set: deadline equals the fire-free control | 136 | 135; the other is FL2 above |
| censored at the last planner offset (+50 min) | 355 | 355 |
| no checked departure | 22 | 22 |

At 1-second resolution (comparing the uncapped exact deadlines of the `cert` and `free` fields over all 530 origins),
the fire moves **52** deadlines. 39 of these also differ at grid resolution; that count includes origins with no checked
departure. The other **13** are fire-shortened only within a 10-minute step, so the grid table above counts them as
window-set (Nora's note). 478 are identical at both resolutions.

As Iris predicted, the fire sets only **17 of 530** deadlines on this panel (grid resolution, origins with a deadline). The other 491 that have a deadline are
window-set or censored, which a fire-free search would also reproduce. Reproducing the fire-set ones is the
non-trivial part: 16 of 16, and FX2 is resolved rather than contradicted.

## 3 Witnesses and certificates

* **Deadline witnesses.** Each exact per-(origin, shelter) deadline witness, departing at the deadline second, was
  checked: **1,482 of 1,482 PASS** the unchanged full checker and the closed replay. In **1,482 of 1,482** cases,
  departing one second later is infeasible in the field.
* **Job witnesses.** Every feasible job, at its recorded departure: **7,970 of 7,970 PASS** (7,771 recorded-checked
  plus 199 resolved-unresolved).
* **Precondition.** The full policy reduces to contact on every request; this is checked per request, including
  incurred dose. Max flux is 0.702 kW/m². Max non-flame flux is 0.01555 kW/m², which bounds dose at ≤ 56 kJ/m² plus
  the incurred dose.
* **Intervals per state.** Max **1** in every field. No feasible-departure set has a hole.

## 4 Exact (1 s) deadline compared with the 10-minute grid

Exact latest departure minus grid deadline, over origins with a deadline:
* it is positive for **every** origin with a deadline (**508 of 508** = 530 − 22 with no checked departure);
* median by file: 293 / 298 / 288 / 397 / 394 / 396 s;
* max 584 s.

Within the planner's own range [0, +50 min], the exact deadline differs from the grid answer at 49 / 49 / 42 / 4 / 5
/ 4 origins. The others are censored at +50 min.

## 5 Compute and memory (host caveats)

* **Recorded cost.** The 9,722 recorded checks sum to **147,900 s** of per-check compute on the evaluated Mac (13
  workers).
* **Field time.** Field time per file for the `cert` variant (including issue sets and witnesses) was 42 s for UA
  03-23 and 339 to 366 s for the Yeongdeok files (112k-edge graph). The UA 03-24 and 03-25 figures (379 s and 235 s)
  are inflated by a concurrent numpy source build.
* **Clean timing pending.** A clean single-process `--timing-only` run is still to be done, so no summed ratio is
  claimed beyond the per-file figures above. This host runs the kit about 2.6 to 2.8 times slower than the Mac
  (Priya's measurement), which makes any ratio conservative.
* **Verification cost.** The full-checker verification is reported separately: 1,040 to 1,556 s per file, about
  0.4 to 1 s per witness.
* **Memory.** Peak RSS per process was 460 to 1,130 MiB. The kit's own dense per-request sweep
  (`zsweep.EarliestArrivalBound`) stores int16 [H × E]: about 315 MB at 43,826 edges and about 806 MB at 111,924
  edges, per request.

## 6 Issue-order-by (post-processing, assumptions)

Leave-by minus alert latency minus door-to-door time, under three settings (labelled assumptions): low 15+15 min,
median 99+30 min, high 180+60 min. The results are in `results/ISSUE_ORDER_BY_1h.json`.

**At the 1-hour horizon this output is degenerate.** Every leave-by is at most 3,480 s, bounded by the horizon, so
under the median and high settings every village's issue-by time is already past at the input time. That is an
artefact of the horizon, not a finding about the fire. It becomes meaningful only on the multi-hour F-DYN workload.

## Verifier notes (Nora, request #2)

* The identical-route check is not vacuous: every recorded route is rebuilt from legs that hash to its `route_sha256`
  (minimum 15 legs) and compared tuple for tuple. But none of the 1,188 UA 03-23 recorded routes contains a WAIT leg,
  so the identity check barely exercises waits. Across all six caches only 3 recorded checked routes have waits
  (`tools/explain_deadlines` README).
* The kit's frozen `ffi_independent_checker` was also run:
  * 8/8 sampled resolved UNRESOLVED witnesses were INDEPENDENTLY_CERTIFIED_OPTIMAL, with the whole road CLEAR and the
    same arrival;
  * 5/5 sampled router-infeasible UNRESOLVED cells were RELAXATION_INFEASIBLE.
* The 6 highest-dose deadline witnesses (up to 85.4 kJ/m² with incurred dose) all arrive at 3,480 = H − dwell. Their
  next-second infeasibility is therefore set by the window, not the fire.

## Not verified / limits

* Physical safety is not claimed. This is a model-relative contact field on the declared lattice, members and rules.
* The `cert` variant is stricter than the router. A deadline from it is attained by a route that passes **both**
  rules. It is never later than what the router itself could find.
* Origin = destination is modelled (`Instance.AN`) but never occurs in these caches.
* Cross-host claims should compare the integer instance and verdicts, not float flux.

## Forecast ablation and provenance (separate claims; verifier Owen: PASS WITH NOTES)

* Forecast ablation at 1 h. The claim file is `results/FORECAST_ABLATION_1h.json` (claim at `50a7ac2`). It is produced
  by `deadline_field/ablation.py`, and its committed summary by `--summary-from` (byte-identical). Its numbers: 22 of
  530 place deadlines move earlier with the c651 forecast (by up to 24.6 min), with 0 status changes.
  **Present-fire-only deadlines are contact-field counterfactuals, not policy-checked deadlines.** Their witnesses are
  not checked against a present-only full policy, and the UA 03-24 FL2 present-only witness meets forecast flame on the
  recorded packet.
* Deadline provenance. The claim file is `results/DEADLINE_PROVENANCE_1h.json` (claim at `f0577de`, built by
  `deadline_field/provenance.py`). Its counts: window 478, present_fire 8, forecast_dependent 22, no_checked_route 22.
  The builder asserts the monotonicity its label precedence relies on: cert ≤ free, and c651 ≤ present ≤ free. Labels
  use uncapped 1-second deadlines. "window" at 1 h means the scenario horizon and travel time bind, not that the place
  is safe.

## F-DYN multi-hour deadline fields (SCENARIO, not what happened; VERIFIED: Nora request #4, PASS WITH NOTES, ledger row 33)

* **Claim file and inputs.** The claim file is `results/FDYN_V31_recorded_starts.json` (commit `505b8d3`), built by
  `deadline_field/fdyn_run.py` on Leo's MANIFEST_v3_1.
  * Coverage: 24 packets = 6 recorded starts × {5 h, 8 h} × {kriged_mean, firms_early}.
  * firms_early is a bracket-start, not a lower bound.
  * Roads are limited to the recorded windows on the interim graphs.
* **Witnesses.** Every exact per-(origin, shelter) deadline witness passes the unchanged full checker and the closed
  replay: **6,288 of 6,288 PASS**. 2 are labelled `upper_bound` because dose could bind over their journey duration;
  both still pass.
* **Caveat on the `exact` / `upper_bound` label (Priya, Thomas).** The exactness precondition (journey duration ≤
  (dose − incurred) / max non-flame flux) uses the cell-binned **packet** flux, not a bound on the whole-road
  checker's enclosure. So the label is a **predictor**, not a proof of full-policy exactness. The witness verdicts
  themselves (6,288/6,288 PASS by the unchanged checker) do not depend on it.
* **Caveat.** Fire-set deadlines are few per packet: UA 0–10 of 84 origins, YD 0–2 of 90. **Most witnesses therefore
  test the scenario window, not the fire.**
* **Verifier notes (Nora, request #4).**
  * **Reproduction.** Nora rebuilt 3 of the 24 packets (UA 24T09 h5, UA 25T17 h5, YD 25T19 h5; all kriged_mean) and
    reran them; they match the claim rows exactly. The 30-min grid is INSTANCE `depart_offsets_s`.
  * **Independent checks.** All 8 fire-set deadline witnesses at UA 24T09 are INDEPENDENTLY_CERTIFIED_OPTIMAL and
    whole-road CLEAR, with departure + 1 s RELAXATION_INFEASIBLE. Both UA 24T09 holes are confirmed (the hole second
    is relaxation-infeasible and the reopen route is valid).
  * **Witness arrivals.** The greedy witness is feasible, not earliest. The kit calls 3 hole-reopening witnesses
    NOT_OPTIMAL_COUNTEREXAMPLE, but they are valid and CLEAR. No claim rests on witness arrival times.
  * **Fire-set witnesses.** Every sampled fire-set witness arrives at 17,880 s = H − dwell. Fire lengthens the route,
    but the window still binds the deadline.
  * **The 2 `upper_bound` rows are exact in effect.** The witness passes the full policy, and the contact field
    excludes departure + 1 s.

## Burn-duration sensitivity of feasible-departure holes (Uiseong; rule committed before running; VERIFIED: Nora request #5, PASS WITH NOTES, ledger row 35)

* **Setup.**
  * The rule, `BURN_DURATION_SENSITIVITY_RULE.md`, was committed at `6cfab3e` before any number was computed.
  * The summary is `results/BURN_DURATION_SENSITIVITY_uiseong.json`, built by `deadline_field/burn_sensitivity.py`
    and its `--summary-from` option.
  * Inputs: the 12 Uiseong v3.1 packets.
  * Each burning period is scaled by f: drawn ignitions burn [b, b + f·T), present fire burns [0, f·R).
    "never" = no cell clears within the horizon.
  * The fields with f ≠ 1 are **contact-field counterfactuals**, not policy-checked.
* **Baseline check.** f = 1 reproduces the v3.1 feasible-departure sets exactly: 1,008 of 1,008 (origin, packet)
  unions are identical.

| packet (Uiseong) | origins with a hole, f = 1 / 0.5 / 2 / never | contiguous deadline changed vs f = 1: 0.5 / 2 / never |
|---|---|---|
| 03-23 01Z 5 h firms_early | 3 / 3 / 1 / **0** | 1 / 8 / 23 |
| 03-23 01Z 5 h kriged_mean | 3 / 3 / 2 / **0** | 3 / 2 / 23 |
| 03-23 01Z 8 h firms_early | 3 / 3 / 3 / **0** | 1 / 9 / 25 |
| 03-23 01Z 8 h kriged_mean | 3 / 3 / 3 / **0** | 3 / 10 / 24 |
| 03-24 09Z 5 h firms_early | 2 / 2 / 1 / **0** | 1 / 7 / 10 |
| 03-24 09Z 5 h kriged_mean | 2 / 2 / 2 / **0** | 2 / 9 / 14 |
| 03-24 09Z 8 h firms_early | 2 / 2 / 2 / **0** | 7 / 6 / 14 |
| 03-24 09Z 8 h kriged_mean | 2 / 2 / 3 / **0** | 8 / 6 / 14 |
| 03-25 17Z 5 h firms_early | 27 / 27 / 25 / **0** | 7 / 8 / 20 |
| 03-25 17Z 5 h kriged_mean | 27 / 27 / 24 / **0** | 5 / 2 / 9 |
| 03-25 17Z 8 h firms_early | 27 / 27 / 27 / **0** | 3 / 6 / 23 |
| 03-25 17Z 8 h kriged_mean | 28 / 27 / 27 / **0** | 2 / 2 / 9 |

* **Holes under never-clears.** No hole survives never-clears in any packet. Under the committed rule, the holes are
  burn-out under the placeholder burning-duration law. They are a model finding, never shown to residents, and the
  merged rule (contiguous window only) stands. No hole needed classification by cause.
* **Direction and size of the deadline changes.** They are monotone in the expected direction. Changes are in seconds,
  f minus f = 1, over the origins that keep a deadline:

  | f | origins | min | median | max |
  |---|---|---|---|---|
  | 0.5 (later) | 39 | +34 | +356 | +3,660 |
  | 2 (earlier) | 73 | −18,916 | −1,420 | −2 |
  | never (earlier) | 166 | −24,849 | −4,780 | −1 |

* **Deadlines lost or gained.** Never-clears removes the contiguous deadline of 1 origin per 03-23 packet, and of 4
  (kriged_mean) or 15 (firms_early) per 03-25 packet. In these origins a present-fire cell that would have burned out
  stays burning. At f = 0.5, 2 firms_early origins at 03-25 gain one.
* **Verifier notes (Nora, request #5).**
  * **Order.** Commit times confirm the rule came before the result. The claim sha matches.
  * **Reproduction.** Nora re-ran UA 25T17Z h5 kriged_mean (1 of 12 packets). Counts, per-origin deadline changes and
    hole lists are all identical.
  * **Never-clears.** All 84 unions are [0, x] or empty.
  * **Baseline.** The f = 1 unions equal her own fdyn_run unions for 84 of 84 origins.
  * **Nesting.** never ⊆ ×2 ⊆ ×1 ⊆ ×0.5 holds for every origin.
  * **Not done.** The Oracle check on a small cut was not run; the nesting check covers the same direction.
  * **Why the label stays.** With f ≠ 1 the router ends are no longer bin-aligned, so these fields remain contact
    counterfactuals and are not policy-checked.
* **Yeongdeok, never-clears arm only** (rule addition 2026-11-12, committed first at `b96c2d6`).
  * Summary: `results/BURN_DURATION_SENSITIVITY_yeongdeok.json`.
  * Packets: the 8 v3.1 packets with holes at f = 1 (03-25 19Z and 03-26 08Z × 5 h, 8 h × kriged_mean,
    firms_early).
  * Baseline: f = 1 reproduces the v3.1 unions, 720 of 720.
  * Origins with a hole, f = 1 → never: 03-25 19Z 6 / 3 → **0**; 03-26 08Z 2 → **0**. No hole survives.
  * Contiguous deadlines changed under never-clears: 03-25 19Z 4–7 per packet, of which 2–3 disappear; 03-26 08Z 0.
  * **VERIFIED: Nora request #7, PASS WITH NOTES, ledger row 40.**
    * Order: the rule came before the claim, and the claim sha matches.
    * Nora re-ran YD 25T19Z h5 kriged_mean (1 of 8 packets) and got identical results.
    * Her f = 1 unions equal her own fdyn_run unions (90 of 90).
    * Every never-clears union is [0, x] or empty, never ⊆ f = 1 for every origin, and every change is negative or a
      removal.
* **Stated limit.** The sensitivity covers the scalar-law v3.1 packets only, not the per-cell envelope packets
  (v3.3 envelope and envelope_burnset). Yeongdeok gets the never-clears arm only, on its packets with holes at f = 1
  (rule addition dated 2026-11-12).
* **Sources (Sofia, literature check).**
  * Flaming residence at a point is seconds to about a minute: 34–74 s for crown fire (Taylor et al. 2004), and
    tr = 384/σ min for surface fuels (Andrews 2018).
  * Smouldering lasts hours, but that is ground heat, not a road-blocking time.
  * No published number was found for how long a road stays unsafe after the front passes.
  * So reopening a cell within the horizon rests on an unsourced assumption. Since every hole vanishes under
    never-clears, **the holes depend on that assumption and are not physically supported**.
* **Dose-limit variation is a stated gap.** No HAZARD-based FED function exists that could be called beside the
  unchanged checker. Priya's F-4.2 fractional dose uses an assumed flame model, not packet flux, and is not a library
  function. A HAZARD-based FED integral would have to be written fresh and verified on its own. The FED limits 0.3 and
  0.1 are **not** from F-4.2: RADIANT_PLAN.md has flux ceilings of 2.5 and 1.0 kW/m² and FD ≥ 1 (80 TDU).
* **What this means.** The contiguous deadline is sensitive to the placeholder burning duration: at f = 2 it moves
  for 2–10 of 84 origins per packet. Deadlines that depend on burn-out are not robust to that law.

## Unknown-support three-way rule at 1 h (all 6 caches; VERIFIED: Nora request #8, PASS WITH NOTES, ledger row 43)

* **Files.** The summary is `results/UNKNOWN_THREEWAY_1h.json`, built by `deadline_field/threeway.py` and its
  `--summary-from` option.
* **Tiers.** A = all unknown blocked from 0; B(v) and R(v) as in `deadline_field/unknown.py`.
* **Scope of "checked".** Pessimistic "checked" means contact-feasible only: the dose/peak precondition for
  hypothetical unknown sources is not established.

| tier | jobs unresolved (range over caches) | origins losing their deadline (per cache) |
|---|---|---|
| A | 27–60% | 24–56 |
| B1.5 | 27–60% | 20–55 |
| B8.2 | 27–60% | 22–56 |
| R1.5 | 1–5% | 0–1 |
| R8.2 | 3–21% | 0–5 |

* **Which field each label uses (Iris, Clara).**
  * The `optimistic` flag and every tier label in this section and in `results/threeway_jobs/` are against the
    **CERT** field (router OR closed footprint).
  * A CERT "no_route" alone does **not** support a refusal: the closed rule can block an edge-time the kit's router
    allows.
* **Recorded-unresolved jobs with no route.** 284 job rows: 186 at-issue (the router's own at-issue rule) and 98 kit
  timeouts.
  * The 98 timeouts are infeasible in the **ROUTER-only** field, and CERT agrees on all 284.
  * 90 of the 98 are originals that the planner replaced with re-checks. All 90 re-checked to kit model_no_route
    (Clara), which is independent agreement. The other 8 remain unresolved in the planner.
  * Promotion to kit refusals is held pending Thomas's review of the whole-road checker. The ROUTER-only NO_ROUTE
    certificates are exported by `deadline_field/export_timeouts.py`.
* **Verifier notes (Nora, request #8).**
  * **Rerun.** UA 23T01 re-run (1 of 6 caches): all 1,523 per-job rows and the summary are identical.
  * **Masks.** Her own masks from the npz equal `unknown.masks` (953 / 629 / 364), and the R8.2 start times are
    identical for all 513 cells.
  * **Nesting.** Over all 9,722 jobs × 5 tiers: no_route iff optimistic is infeasible, and the nesting
    A ⊆ B8.2 ⊆ B1.5, R8.2 ⊆ R1.5, A ⊆ R8.2, B ⊆ R holds with 0 violations.
  * **Spot check.** 3 tier-A unresolved jobs were checked: their optimistic witnesses cross 12–20 A-blocked cells.
* **ROUTER-only columns (VERIFIED: Nora request #15, PASS, ledger row 59, at 666dee26).**
  * `results/threeway_jobs/*.json` now carry `optimistic_router` and `<tier>_router` (from `threeway --variant
    router`, e772df1), plus `origin_deadlines_router`.
  * **On all 9,722 one-hour jobs, the ROUTER-only labels equal the CERT labels**: the optimistic field and every tier
    (A, B1.5, B8.2, R1.5, R8.2). So at 1 h the closed-footprint rule changes no three-way label. The CERT labels above
    are refusal-grade only through this equality, and only for these 1-h caches.
  * From now on, every tier and horizon reports both by default.
  * **Nora's checks.** 9,722/9,722 jobs keep every CERT key and value (only router keys added); her own `--variant
    router` run on UA 23T01Z reproduces the committed columns (0 diffs). Router and CERT feasible sets over the whole
    [0, H] are identical on 254/254 (UA 23T01Z) and 253/253 (UA 25T17Z) (spec, origin) pairs, optimistic field, so the
    equality there is not an artefact of sampled departures. Pessimistic tiers and Yeongdeok were not checked this way.

## Issue-order-by on F-DYN v3.1 (post-processing; SCENARIO; latency settings are assumptions; VERIFIED: Nora request #9, PASS, ledger row 44)

* **Files.** `results/ISSUE_ORDER_BY_FDYN_v31.json`, built by `deadline_field/fdyn_issue_by.py`.
* **Definitions.**
  * Leave-by is the **contiguous** deadline (merged rule).
  * Issue-by = leave-by − alert latency − door-to-door time.
  * Settings: latency 1.5 h or 2 h, each with 30 min door-to-door, plus the 1-h panel's low / median / high.
* **Count categories, per packet.**
  * future: the issue-by time is after the start.
  * past: the issue-by time is before the start, i.e. the order is already late.
  * late_window_only: no departure at the start, feasible only after a gap. The resident line is "no checked route at
    the start, do not wait for an order"; the staff note says the later window is not the deadline.
  * no_route: no feasible departure at all.
* **Results at a 2 h latency.**

  | start | future | past | late_window_only | no_route |
  |---|---:|---:|---:|---:|
  | UA 03-23 01Z | 81–82 | 2–3 | 0 | 0 |
  | UA 03-24 09Z | 83 | 1 | 0 | 0 |
  | UA 03-25 17Z | 57–58 | 15–17 | 9–12 | 0 |
  | YD 03-25 19Z | 84–87 | 0–2 | 3–4 | 0 |
  | YD 03-25 23Z | 90 | 0 | 0 | 0 |
  | YD 03-26 08Z | 88 | 0 | 2 | 0 |

* **Horizon censoring.** In Yeongdeok, 79–86 of 90 leave-bys lie within 10 min of the horizon. Their issue-by is
  bounded by the scenario horizon, so it is not a finding about the fire. The corresponding figure for UA is 21–36
  of 84.
* **Placeholder dependencies.** A leave-by whose witness is dose `upper_bound` carries two placeholder dependencies:
  the burning-duration law and the dose limit. This applies to 1 origin in each of YD 03-25 19Z 5 h kriged_mean and
  firms_early.
* **Note on the F-DYN exact-minus-grid statistics above.** `exact_cert` in the F-DYN claim file is the end of the
  last feasible interval. For the origins with a hole, it is not the resident-facing contiguous deadline. Both are
  in the file: `union_cert` holds every interval.

## F-DYN v3.3 envelope variants (SCENARIO, not what happened; VERIFIED: Nora request #6, PASS WITH NOTES, ledger row 36)

*Wherever envelope_burnset is quoted in this file:* "burn set = kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only)". It is a static final-footprint bound: no timing,
identical across starts. See MULTIHOUR_HEADLINE_RULE.md.

* **Files and inputs.**
  * Claim: `results/FDYN_V33_envelope_report.json`, built by `deadline_field/fdyn_v33_report.py` from 24 runs of
    `deadline_field/fdyn_run.py`.
  * Leo's MANIFEST_v3_3 (sha aaed2402…, commit 4463892) for the 6 recorded starts × {5 h, 8 h}.
  * For per-cell-law packets, phases are read from the HAZARD flame bins, so the field follows the router's law.
    envelope_sound is withdrawn and not scored.
* **Labels.**
  * envelope: bracket-start, not a lower bound.
  * envelope_burnset: sound relative to the final mapped burn set (fire never mapped is outside it); single
    implementation, not independently checked.
* **Witnesses.** All pass the unchanged full checker and the closed replay:
  * envelope: 3,120 of 3,120 (1 is upper_bound);
  * envelope_burnset: 438 of 438.
* **Which representation each checker read** (stated after Nora row 34: on v3.3 envelope and burnset packets the raw
  `constructed_arrays.npz` disagree with HAZARD.json; the arrays under-block).
  * **Field.** Phases come from the HAZARD flame bins (`real.load_packet`, per-cell path), not from the arrays.
  * **Full checker** (`routing-package/routing/independent.check_route`, unchanged). It reads **HAZARD.json** (flame,
    flux bins, dose) and the graph. It does not read the arrays.
  * **Closed replay** (`tools/explain_deadlines/replay.first_contact`). It reads `pk.phases`, which for these
    packets my reader rebuilt **from the HAZARD flame bins**. It is therefore consistent with HAZARD, but **not
    independent of the field's own reading of the packet**.
  * **Router sampling rule** (`Packet.contact_router`). It reads the HAZARD flame bins.
  * **Arrays.** None of my checks read the arrays. The kit's ffi checker, which Nora uses, does. Its verdicts on
    these packets are therefore against the under-blocked arrays and are not part of my claim.
  * **What the passes mean.** Each pass is against HAZARD.json, the representation the field uses. Only
    `check_route` is independent of my code. Burnset will be rerun on Leo's MANIFEST_v3_4 (arrays equal HAZARD)
    once Nora passes it.
* **Verifier notes (Nora, request #6).**
  * **Blocked roads.** Nora rebuilt YD 25T19 h5 burnset: HAZARD has one bin [0, 18000], and the flame cells equal
    the burn set she derived from the raw inputs. Her own recount of blocked roads matches both regions exactly.
  * **Field.** Her fdyn_run on that packet matches report row 13 exactly.
  * **Not checked.** The envelope upper_bound witness was not looked at, and the other 23 packets were not re-run.
  * **No independent check yet.** The arrays still disagree with HAZARD, and the kit's independent checker reads the
    arrays. So no independent check of these witnesses is possible yet: only the full checker and the closed replay
    on HAZARD.
  * **v3.4 (Nora row 37).** Leo's MANIFEST_v3_4 fix passes: the burnset arrays now equal HAZARD, and the HAZARD is
    identical to v3.3's.
  * **v3.4 rerun (VERIFIED: Nora request #16, PASS, ledger row 63).** All 24 envelope and envelope_burnset packets were rebuilt from MANIFEST_v3_4 (Leo
    faa89c4) and rerun through `fdyn_run` with full-checker witnesses (`results/FDYN_V34_RERUN_vs_V33.json`, built by
    `deadline_field/rerun_compare.py`; it lists both runs' HAZARD hashes per packet).
    * **Result.** 24 of 24 packets give the same classes, deadlines, pieces, witnesses and check rows as v3.3. The
      only differences are in the last float digits (equal at 9 significant digits) and in file paths.
    * **Why the HAZARD hashes differ.** On a rebuilt YD 25T19 h5 envelope_burnset pair, the two HAZARD.json files
      differ only in provenance and identity: settings_digest, construction_id, the scenario and member ids derived
      from it, the interpretation text, and the embedded absolute path of the radiation module. The flame, flux and
      dose content is identical. The other 23 pairs were not rebuilt for this check.
    * **Nora's check.** She rebuilt 2 pairs from MANIFEST_v3_3 and v3_4 (UA 25T17 h5 envelope, YD 25T19 h5
      envelope_burnset) and ran fdyn_run on all 4: 0 keys differ, even before rounding, on her host. The flame, flux
      and breakpoints are identical. For YD burnset the HAZARD diff is exactly the 6 identity and provenance paths.
    * **Writer identity not available.** In 7 of the 24 outputs (written before fdyn_run recorded it) the
      writer_identity key is absent. In the other 17 it is present, but both fields (packet_writer_sha256,
      support_writer) are null, because the v3.4 BUILD_SUMMARY.json does not carry them.
* **Counts.** Origins with a checked route at the start (contiguous deadline), and origins whose contiguous deadline
  is unchanged against kriged_mean (v3.1, same start and horizon). Summed over the 3 starts per region:

  | region | horizon | envelope: checked / unchanged | envelope_burnset: checked / unchanged | kriged_mean checked |
  |---|---|---|---|---|
  | Uiseong (252) | 5 h | 235 / 222 | 0 / 0 | 243 |
  | Uiseong (252) | 8 h | 235 / 219 | 0 / 0 | 243 |
  | Yeongdeok (270) | 5 h | 265 / 262 | 81 / 78 | 264 |
  | Yeongdeok (270) | 8 h | 265 / 261 | 81 / 78 | 264 |

  The counts per region-start are in the claim file.
* **envelope_burnset blocked roads** (`results/BURNSET_BLOCKED_ROADS_v33.json`, built by
  `deadline_field/burnset_blocked.py`). These are roads blocked for the whole horizon under both rules, at every start:
  * Uiseong: 43,512 of 43,826 (99.28%);
  * Yeongdeok: 76,541 of 111,924 (68.39%).

  Every burn-set cell burns from t = 0 and never clears. Both regions share one 237 × 79 grid and the same
  16,176-cell burn set: the 2025 fire spread from Uiseong into Yeongdeok. The burn set is quoted as
  "burn set = kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only)". In Uiseong, therefore, no origin has a
  route under this envelope. **For Uiseong routing the variant is uninformative, not a finding about the fire.**
* **envelope vs kriged_mean is not ordered.** At YD 03-25 19Z 5 h, origin osm:node/415160165 is feasible from 0 under
  envelope ([0, 17706]) but only from 6,071 s under kriged_mean. Envelope deadlines are therefore not a bound on
  kriged_mean deadlines in either direction. This is consistent with the bracket-start label.

## Deadline ladder per place and start (F-DYN; SCENARIO; not yet verified)

* **What it shows.** For every place, start and horizon, the contiguous deadline under each variant, with its label:
  * envelope_burnset: sound relative to the final mapped burn set (fire never mapped is outside it); single
    implementation, not independently checked;
  * firms_early: bracket-start, not a lower bound;
  * kriged_mean: central scenario;
  * envelope: bracket-start, not a lower bound.
* **Files.** `results/DEADLINE_LADDER_FDYN.json`, built by `deadline_field/ladder.py`.
* **The variants are not nested,** so the ladder is a list, not an interval. Spread = max − min over the variants that
  give a deadline:
  * **Uiseong:** median spread 0 s. Origins with spread > 30 min, per start: 03-23 2; 03-24 0–1; 03-25 5–6. Max spread
    up to 22,480 s at 8 h. Burnset gives no deadline anywhere.
  * **Yeongdeok:** median 0 s. Origins with spread > 30 min: 03-25 19Z 2; the other starts 0, with max 96 s. 27 of 90
    origins have a deadline in all four variants (those outside the burn set's road cut).
* **Flags per origin.**
  * Hole in some variant: UA 2–28, YD 0–6 per start.
  * Dose upper_bound in some variant (two placeholder dependencies): 1 origin, YD 03-25 19Z 5 h.
* **Not included.** The forecast-dependent flag on F-DYN needs present-only F-DYN fields, which were not run.
  envelope_sound is withdrawn.

## Rate-assumed tier: test of 8.2 km/h against the detections (rule `RATE_ASSUMED_RULE.md`, committed first at 8a16dc2; VERIFIED: Nora request #10, PASS WITH NOTES, ledger row 45)

* **Tier label.** "rate-assumed, 8.2 km/h (reported orally, method unpublished; documented 12-h mean ≈4.25 km/h incl.
  spotting)". Never "bounded".
* **Files.** `results/RATE_REFUTATION_8p2.json`, built by `deadline_field/rate_refute.py`.
* **Data.** 5,114 FIRMS detections: 2025-03-21 to 03-29, in grid, type 0, inside the final kriged footprint; 44
  overpasses. Brackets follow `firms_early`.
* **Test of record: per-detection minimum implied rate.** The orchestrator accepted it.
  * r_j = slowest spread from any earlier-bracketed detection that explains detection j.
  * n = 5,091; p50 0.03, p90 0.10, p99 0.23, **max 1.48 km/h**.
  * 0 detections exceed 8.2.
* **Result: uninformative about 8.2 km/h (low power), not contradicted.** This is not support. The test's largest
  lower bound (1.48) is below the documented written 12-h mean. Its power is low because intermediate overpasses chain
  each detection to a nearby earlier one.
* **Documented interval, checked directly in the detections.** KFS: fire-line 51 km in ≤ 12 h, 25 Mar 14:00 → 26 Mar
  02:00 KST.
  * Nearest overpasses: 25 Mar 05:06 and 17:26 UTC, a 12.33 h gap.
  * The new detections in that interval lie up to **49.25 km** from the extent detected by 05:06. The farthest is at
    36.4918 N, 129.4389 E (Yeongdeok coast) at 17:26 UTC.
  * Implied mean **3.99 km/h**. The detections reproduce the documented ≈4 km/h.
* **Context only, not decisive: front advance between consecutive overpasses.** This is the maximum distance of the
  new detections from the cumulative earlier extent, divided by the gap.
  * Over gaps of ≥ 3 h, the largest is **7.0 km/h**: 45.2 km in 6.45 h, 25 Mar 05:58 → 12:25 UTC.
  * Short gaps (≤ 0.4 h) give up to 47 km/h. These are confounded by different sensor swaths covering different
    areas, not spread.
* **Literal all-pairs statistic.** Max 3,747 km/h. It is dominated by simultaneous detections on separate fronts and
  is not decisive.

## Rate-assumed tier sensitivity at 1 h (rule `RATE_ASSUMED_RULE.md` §1, committed first at 8a16dc2; VERIFIED part 1: Nora request #12, PASS WITH NOTES, ledger row 53)

* **Files.** `results/RATE_ASSUMED_SENSITIVITY_1h.json`, built by `deadline_field/rate_sensitivity.py`.
  * A, R1.5 and R8.2 come from the verified three-way runs (Nora row 43).
  * R16.4 is new, through the same code (`threeway --only-tiers R16.4`). Its recomputed optimistic field equals the
    base one for every origin (asserted).
* **Scope.** CERT contact field; pessimistic "checked" is contact-only. Labels: "rate-assumed, v km/h"; Tier A = all
  unknown support blocked from 0.
* **Counts per origin against the optimistic field.**
  * **Removed** = loses its deadline.
  * **Moved** = deadline earlier; the shift (optimistic − variant) is given in seconds as median / max.

| cache | Tier A removed / moved | R1.5 | R8.2 | R16.4 |
|---|---|---|---|---|
| UA 03-23 01Z | 34 / 1 | 0 / 11 (1,445 / 1,877) | 5 / 6 (2,859 / 2,915) | 6 / 28 (258 / 3,024) |
| UA 03-24 09Z | 30 / 3 | 0 / 3 (489 / 686) | 0 / 15 (500 / 1,406) | 0 / 33 (909 / 1,945) |
| UA 03-25 17Z | 24 / 0 | 0 / 4 (11 / 2,335) | 1 / 19 (1,248 / 3,070) | 5 / 19 (2,220 / 3,189) |
| YD 03-25 19Z | 56 / 2 | 1 / 5 (1,435 / 2,177) | 3 / 47 (942 / 3,123) | 4 / 54 (2,191 / 3,370) |
| YD 03-25 23Z | 56 / 3 | 0 / 4 (1,624 / 2,132) | 1 / 34 (1,131 / 3,232) | 3 / 56 (1,864 / 3,416) |
| YD 03-26 08Z | 55 / 3 | 0 / 2 (1,588 / 1,588) | 0 / 27 (1,471 / 3,232) | 1 / 53 (1,722 / 3,380) |

* **Tier A moved shifts.** Median / max per cache: UA 03-23 100 / 100; UA 03-24 489 / 686; UA 03-25 —; YD 03-25 19Z
  107 / 107; YD 03-25 23Z and 03-26 08Z 107 / 673.
* **Reading.**
  * Doubling the assumed rate (8.2 → 16.4 km/h) removes 0–6 deadlines per cache and moves 19–56; the median shift per cache is 4–37
    minutes.
  * Tier A removes 24–56 per cache.
  * B16.4 (Iris) follows when its runs finish.
* **Verifier notes (Nora, request #12 part 1).**
  * **Reproduction.** She reran R16.4 on all 6 caches; the summary is identical, and the recomputed optimistic field
    equals the base one (6 of 6).
  * **Nesting.** A ≤ R16.4 ≤ R8.2 ≤ R1.5 ≤ optimistic, per origin and per job: 0 violations.
  * **Masks.** Her own ceil(d / v) start times from the npz masks equal mine at every rate.
  * **Counts.** Her independent recount matches the claim.
  * **"Median" is the upper median.** With 2 moved origins (YD 03-26 08Z R1.5) it equals the maximum (1,588 s); the
    lower median there is 231 s.
  * **R16.4 is close to Tier A.** At 16.4 km/h every unknown cell is blocked within the hour in 5 of 6 caches (YD
    03-26 08Z: 2,548 of 2,599 cells). In effect, R16.4 is Tier A with a ramp of up to 1 h.
* **Addendum: B16.4 (Iris).** Tier B at 16.4 km/h blocks U_state from 0 and U_q from d / v. File
  `results/RATE_ASSUMED_SENSITIVITY_1h_with_B16p4.json`; the A / R entries are unchanged from the verified file.
  **VERIFIED: Nora request #12 addendum, PASS WITH NOTES, ledger row 57.**
  * **Nora's checks.** Her B16.4 runs reproduce the file exactly. Her own tier-B start times equal mine. The nesting
    A ≤ B16.4 ≤ B8.2 ≤ B1.5 ≤ optimistic and B16.4 ⊆ R16.4 hold with 0 violations.
  * **Order.** The rule addition (dfd02ec, 15:41:17) came before the runs. It did **not** come before the code: the
    tier was added in 41a2ae7 at 15:41:01, 16 s earlier.
  * **Reporting.** In Yeongdeok, B16.4 is identical to Tier A, so it is reported as **"= A (YD)"**, not as a separate
    bound.

  | cache | B16.4 removed / moved (median / max s) |
  |---|---|
  | UA 03-23 01Z | 28 / 7 (2,369 / 3,218) |
  | UA 03-24 09Z | 28 / 5 (686 / 2,369) |
  | UA 03-25 17Z | 23 / 1 (2,369 / 2,369) |
  | YD 03-25 19Z | 56 / 2 (107 / 107) |
  | YD 03-25 23Z | 56 / 3 (107 / 673) |
  | YD 03-26 08Z | 55 / 3 (107 / 673) |

  * In Yeongdeok, B16.4 equals Tier A on every count. In Uiseong it removes 23–28 deadlines, against 24–34 under
    Tier A.
  * Reason: U_state is blocked from 0 under B, and it dominates the unknown cells.
* **One-hour tool only.** At 8.2 km/h a rate bound reaches 41 km in 5 h. These tiers are not extended to 5 h or 8 h
  (MULTIHOUR_HEADLINE_RULE §4).

## ROUTER-only field on Priya's 12 F-DYN kit requests (VERIFIED: Nora request #11, PASS, ledger row 50)

* **Files.** `results/FDYN_KIT_REQUESTS_router_field.json` (ac80919), built by `deadline_field/kit_requests.py`.
* **Inputs.** 5 h, v3.1 packets rebuilt from MANIFEST_v3_1. The HAZARD sha differs between hosts only by an embedded
  absolute module path (fixed in v3.5); the content-hash scenario ids match.
* **Counts.** 0 NO_ROUTE, 2 AT_ISSUE, 10 FEASIBLE.
  * Every feasible witness passes the unchanged checker and the closed replay.
  * That includes the 4 Uiseong requests the kit never resolved (arrivals 372 s and 52 s).
* **Nora's independent checks.**
  * The kit's ffi_independent_checker calls 8 witnesses INDEPENDENTLY_CERTIFIED_OPTIMAL and CLEAR.
  * …166 is valid and CLEAR but NOT_OPTIMAL: the greedy witness is feasible, not earliest (4,356 s vs the kit's
    3,953 s).
  * The 2 at-issue requests are RELAXATION_INFEASIBLE, with the origin's cell in flame in bin [0, 300).
* **Consequence (orchestrator).** The kit-checker dominance review is dropped: no unresolved multi-hour request is a
  hidden refusal.
* **Labels.** SCENARIO; road-limited graph (graphs_interim); assumes no fire outside mapped or forecast cells.

## Timing lever vs destination lever (rule `LEVER_RULE.md`, committed first at 48d2be0; VERIFIED: Nora request #13, PASS WITH NOTES, ledger row 58)

* **Label.** Model statements on scenarios (F-DYN, not what happened). Free-flow only: no traffic is modelled, so
  any route effect is ~0 by construction. Roads are limited to graphs_interim.
* **Files.** `results/LEVER_TIMING_VS_DESTINATION.json`, built by `deadline_field/lever.py --summary-from`.
* **Setup.**
  * 48 packets: v3.3 manifest, 6 starts × {5 h, 8 h} × 4 variants.
  * CERT contact field, one field per destination of the region.
  * Reference departure t_ref = 150 min after the start (2 h alert + 30 min door-to-door, an assumption).
  * Lever A: depart 30 / 60 / 120 min earlier, same destinations. Lever B: same departure, any candidate destination.
* **Results at t_ref, per packet, among place-starts not checked at t_ref.**
  * **Lever B rescues none (free-flow only):** B-only = 0 and both = 0 in all 48 packets and at every shift.
  * Lever A rescues 0–6 per packet. The largest counts are at UA 03-25 17Z: A rescues 1 / 1–2 / 4–6 of 6 at
    30 / 60 / 120 min.
  * Not every lever-A count rises with the shift. At UA 03-25 envelope it is 1 / 0 / 4 at 30 / 60 / 120 min, because
    the feasible-departure sets have holes.
  * Yeongdeok: every place is already checked at t_ref, except under envelope_burnset (63 of 90 neither).
  * envelope_burnset in Uiseong: all 84 are neither (no route anywhere).
* **Arrival gain where both rescue.** There are no "both" cases at t_ref, so it is not applicable.
* **Sensitivity over all grid departures ≥ 120 min.**
  * B-only = 0 everywhere.
  * 18 "both" rescues, all at the last grid departure before the horizon (UA 03-24 09Z, H − 30 min), where lever A
    also rescues. Their arrival gains were not computed (primary t_ref only).
* **Not run.** The 1-h cache part of the rule (t_ref = 50 min, s = 30 min) has not been run yet; this is a gap.
* **Verifier notes (Nora, request #13).**
  * **Reproduction.** She re-ran 5 of the 48 packets; all are identical, including the sensitivity grid and the
    1 / 0 / 4 case.
  * **B = 0, checked independently.** Thomas's SIPP router (the router rule, which is weaker than CERT) finds
    NO_ROUTE from all 6 unchecked UA 25T17 kriged origins to all 30 destinations at 9,000 s.
  * **Lever A.** SIPP finds a route exactly for my A rescues and NO_ROUTE for every "neither". All 8 A-rescue
    witnesses are INDEPENDENTLY_CERTIFIED_OPTIMAL and CLEAR.
  * **Counting.** The "18 both" in the sensitivity are 1 origin × 3 shifts × 6 packets, i.e. **6 distinct cases**.
  * **Label.** "Free-flow only" applies to every lever-B number.
  * **Code fix.** `lever.py`, `return_trip.py`, `fdyn_run.py` and `burn_sensitivity.py` fell back silently to the
    first INSTANCE entry when `--start` matched no start tag. They now raise. The fallback never fired: INSTANCE.json
    holds exactly the 6 recorded starts used here.
* **Reading (model statement).** On these scenarios the timing lever is the only one that rescues. Choosing another
  shelter at the same departure never turns "no checked road" into "checked". This is consistent with free-flow
  routing with no congestion.

## Return trips (rule `RETURN_TRIP_RULE.md`, committed first at 7e05a75; VERIFIED WITH NOTES: Nora request #14, PASS WITH NOTES, ledger row 64)

* **Label.** Model statements on scenarios (F-DYN v3.3, 5 h, kriged_mean and firms_early; not what happened). CERT
  contact field. Roads are limited to graphs_interim.
* **Files.** `results/RETURN_TRIPS_FDYN.json`, built by `deadline_field/return_trip.py --summary-from`.
* **Setup.**
  * Outbound at the start to the own destination with the earliest arrival (exact witness).
  * Return from that destination to the entry node, departing at arrival + dwell + Δ.
* **Important caveat: these packets reopen burned cells.** The runs use the as-built packets with the fixed
  burning-duration reopening. A return that becomes checked at a longer delay does so because the fire burned out
  under the placeholder law. Under the **no-re-entry** default of the multi-hour headline rule such returns would not
  reopen. These counts are therefore a research row, never person-facing.

| start | variant | outbound not checked | return not checked at Δ = 30 / 60 / 120 min | beyond horizon (120 min) |
|---|---|---:|---|---:|
| UA 03-23 01Z | both | 0 | 0 / 0 / 0 | 0 |
| UA 03-24 09Z | both | 0 | 0 / 0 / 0 | 0 |
| UA 03-25 17Z | kriged_mean | 9 | 4 / 14 / 16 | 0 |
| UA 03-25 17Z | firms_early | 12 | 11 / 11 / 0 | 1 |
| YD 03-25 19Z | kriged_mean | 4 (+1 not computed) | 0 / 1 / 1 | 0 |
| YD 03-25 19Z | firms_early | 3 (+1 not computed) | 0 / 1 / 1 | 0 |
| YD 03-25 23Z | both | 0 | 0 / 0 / 0 | 0 |
| YD 03-26 08Z | both | 2 | 0 / 0 / 0 | 0 |

* **Reading the table.**
  * "Outbound not checked" = no checked route at the start.
  * "Not computed" = the exact earliest-arrival witness exceeded its 2 GiB memory cap.
  * UA 03-25 17Z firms_early drops from 11 to 0 at 120 min. That is reopening under the placeholder law, which is
    the caveat above in action.
* **Implementation note.** The YD runs (and the remaining runs after a memory kill) use the
  one-destination-field-at-a-time version of `return_trip.py`. The selection logic is unchanged: earliest arrival,
  ties to the lowest node id.

* **Nora's checks (row 64).**
  * UA 03-25 17Z h5 kriged_mean and firms_early, rerun with the current `return_trip.py`: counts and not-checked lists
    identical to the committed file.
  * All 34 `return_not_checked` cases (kriged_mean; Δ30: 4, Δ60: 14, Δ120: 16) are RELAXATION_INFEASIBLE by the kit's
    independent checker.
  * 3 of 8 sampled origins checked so far: every own-destination witness is INDEPENDENTLY_CERTIFIED_OPTIMAL and CLEAR,
    and the claimed outbound destination is the argmin (259 / 52 / 4,283 s). The rest are still running.
* **Notes from Nora, and what changed.**
  * firms_early has 1 beyond_horizon at Δ60 as well (the file is right; my message said Δ120 only).
  * **Partial memory caps.** If one own destination's witness hit the 2 GiB cap and another succeeded, the origin kept
    the successful one as "earliest" without a flag. `return_trip.py` now records `outbound_partial_cap` and
    `capped_destinations`. The committed runs predate this. Full caps (no outbound arrival at all) are recorded: 1
    origin in YD 03-25 19Z, both variants. Partial caps in these runs are **not known**; the YD 03-25 19Z rows are to
    be rerun with the flag.
  * The start-tag fallback: `--start` with no INSTANCE match now raises (current code; the reviewed commit 7f657fb
    still had the fallback).
  * Reopening-law caveat as stated: these are research-variant packets (fixed burning duration, reopening).

## Spotting-distance envelope, 5 h (SCENARIO, not what happened; research variant: reopening packets as built; VERIFIED WITH NOTES: Nora request #17, PASS WITH NOTES, ledger row 61)

* **Rule.** `SPOTTING_RULE.md`, committed before tabulating. **Files.** `results/SPOTTING_ENVELOPE_h5.json`, built by
  `deadline_field/spot_summary.py` from 24 `fdyn_run` outputs (v3.3 builder, Leo 4463892; packet HAZARD hashes are
  in the file).
* **What it is.** Leo's isotropic `dilate(a, d, lag 0 s)` on the kriged_mean TOA, d ∈ {0, 500, 1000, 2000} m. Lag 0
  was meant to make every shift an upper bound under the dilation rule. **It does not** (construction artefact,
  below). There is no wind field, so there is no downwind shape. Nothing is claimed about actual spotting distances in 2025.
* **Field.** CERT contact field. Contiguous deadline (merged rule). Per region-start and d, never pooled.
* **Control.** At d = 0 all 6 starts equal the kriged_mean field on every place (CERT and FREE sets; 0 places
  differ). The control file is the v3.1 kriged_mean run; the rule names v3.3. Their content is identical (Nora
  row 61: the d = 0 HAZARD flame, flux, support and breakpoints equal v3.3 kriged_mean).
* **Witnesses.** 6,264 witnesses, all pass the unchanged full checker and the closed replay (exact or upper_bound);
  every next second is infeasible.

| region-start | d (m) | earlier | shift (s): median (upper) / max | before start | later | no route at d = 0 | witnesses |
|---|---|---|---|---|---|---|---|
| UA 03-23 01Z | 0 | 0 | – | 0 | 0 | 0 | exact:PASS 252 |
| UA 03-23 01Z | 500 | 5 | 1145 / 5515 | 0 | 4 | 0 | exact:PASS 252 |
| UA 03-23 01Z | 1000 | 13 | 525 / 14815 | 2 | 3 | 0 | exact:PASS 252 |
| UA 03-23 01Z | 2000 | 8 | 525 / 2652 | 0 | 5 | 0 | exact:PASS 252 |
| UA 03-24 09Z | 0 | 0 | – | 0 | 0 | 0 | exact:PASS 252 |
| UA 03-24 09Z | 500 | 0 | – | 0 | 9 | 0 | exact:PASS 252 |
| UA 03-24 09Z | 1000 | 7 | 106 / 8422 | 0 | 7 | 0 | exact:PASS 252 |
| UA 03-24 09Z | 2000 | 8 | 2312 / 12965 | 0 | 8 | 0 | exact:PASS 252 |
| UA 03-25 17Z | 0 | 0 | – | 0 | 0 | 9 | exact:PASS 252 |
| UA 03-25 17Z | 500 | 19 | 369 / 6607 | 2 | 0 | 9 | exact:PASS 250, upper_bound:PASS 2 |
| UA 03-25 17Z | 1000 | 17 | 939 / 4800 | 4 | 0 | 9 | exact:PASS 252 |
| UA 03-25 17Z | 2000 | 22 | 3248 / 13719 | 5 | 1 | 9 | exact:PASS 246, upper_bound:PASS 6 |
| YD 03-25 19Z | 0 | 0 | – | 0 | 0 | 4 | exact:PASS 269, upper_bound:PASS 1 |
| YD 03-25 19Z | 500 | 2 | 9116 / 9116 | 2 | 0 | 4 | exact:PASS 269, upper_bound:PASS 1 |
| YD 03-25 19Z | 1000 | 3 | 4692 / 11112 | 2 | 1 | 4 | exact:PASS 268, upper_bound:PASS 2 |
| YD 03-25 19Z | 2000 | 4 | 15912 / 17592 | 2 | 2 | 4 | exact:PASS 270 |
| YD 03-25 23Z | 0 | 0 | – | 0 | 0 | 0 | exact:PASS 270 |
| YD 03-25 23Z | 500 | 0 | – | 0 | 0 | 0 | exact:PASS 270 |
| YD 03-25 23Z | 1000 | 2 | 5956 / 5956 | 1 | 0 | 0 | exact:PASS 270 |
| YD 03-25 23Z | 2000 | 1 | 16646 / 16646 | 1 | 0 | 0 | exact:PASS 270 |
| YD 03-26 08Z | 0 | 0 | – | 0 | 0 | 2 | exact:PASS 270 |
| YD 03-26 08Z | 500 | 0 | – | 0 | 0 | 2 | exact:PASS 270 |
| YD 03-26 08Z | 1000 | 0 | – | 0 | 0 | 2 | exact:PASS 270 |
| YD 03-26 08Z | 2000 | 0 | – | 0 | 0 | 2 | exact:PASS 270 |

* **Places that move later: a construction artefact (Nora row 61).** Dilating the whole raster also moves cells
  that were **not** burned at the start (per the export) to arrivals before the start. The builder then treats them as
  burned out before the start, so they are not phases and their roads open.
  * **Measured.** On UA 03-24 09Z, d = 500 m: 97 of the 135 phase cells of the d = 0 packet are dropped (their
    dilated arrivals are 4,227–47,988 s before the start; all 18 present cells stay). 9 places move later. Under the
    never-clears arm on the same two rebuilt packets, 10 move later and none earlier. Nora reproduced the d = 0 and
    d = 500 rows exactly.
  * **Consequence.** Here spotting makes places **safer**. The shifts are **not** upper bounds, even under the
    dilation rule, and "moves earlier" can be understated. These rows are not for any non-research use.
  * **Fix before any non-research use.** a_d = max(dilate(a), t_start) for cells not burned at the start (or dilate
    only post-start arrivals). Then nothing can move later. Not done yet.
  * **Reproducibility.** The batch script is now committed (`batch/spot_batch.py`; it builds in Leo's worktree at
    4463892 from `fdyn/variants.dilate` outputs).
* **Route side.** Priya's matching route-side count (clearance below d) is not in yet. It will be reported next to
  these counts, not merged with them.
* **Assumption line.** Assumes no fire outside mapped or forecast cells; no conservative unknown-support tier exists
  at multi-hour.

## Multi-hour `no_reentry/1` VARIANT run, 48 packet pairs (SCENARIO, not what happened; VARIANT, not the headline; VERIFIED: Nora, PASS WITH NOTES, ledger row 67)

**Nora's notes (row 67).**
1. The HAZARD sha256 values in the summary are NOT the canonical v3.6 packet hashes. Example: Uiseong 25T17Z h5 kriged_mean `/1` is bc058bd7 here and e02e5135 canonically. The batch rewrites `--out` to an absolute scratch path, which enters provenance. Results are unaffected. Treat the summary's hashes as the hashes of these scratch builds only. *(Correction, ledger row 72a: the `--out` explanation is withdrawn; the hashes differ because of the numpy version, 1.26.4 here vs 2.5.x, through `members.flux` float rounding only.)*
2. The earlier-variant-later rows are the `/1` pre-start burn-out effect, as with spotting (row 61). They are expected to vanish under `/2` (acceptance 8). This is not shown yet.
3. Nora re-ran 2 of the 48 pairs (Uiseong 25T17Z h5 kriged_mean and firms_early). Both reproduced exactly.

**Label.** VARIANT (`no_reentry/1`): no re-entry after the start; cells burned out before the start stay open.
- Rule: `MULTIHOUR_HEADLINE_RULE.md` with its amendment of 19:15 UTC. The headline is `no_reentry/2` (v3.7, Leo, with Nora).
- Graphs are road-limited to the recorded windows.
- **Assumption:** no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour.
- **Waiting rule:** waiting is allowed only at graph dead-end nodes (as supplied in graph.json; rule undocumented).
- CERT = router OR closed footprint. ROUTER = router rule only. Refusal-grade statements come only from ROUTER.
- "Exact" is relative to the time-dependent model.
- firms_early and envelope: bracket-start, not a lower bound.
- envelope_burnset is its own static row. Burn set = kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only).

**Coverage.** 48 pairs: v3.6 `no_reentry/1` + reopening × 4 variants × 6 recorded starts × {5 h, 8 h}.
- Runner: `deadline_field/headline.py`; batch: `batch/headline_batch.py`.
- Leo's code at 046a6f31, MANIFEST_v3_6.
- 0 build or run failures.
- Every packet's BUILD_SUMMARY writer_identity.transform = `no_reentry/1`.
- Summary: `results/HEADLINE_NR1_VARIANT_summary.json`, per place, packet and variant. The raw per-pair outputs stay in scratch.

| check (totals over 48 pairs) | result |
|---|---|
| CERT leave-by witnesses, full checker on the `/1` packet | 9,058 / 9,058 PASS |
| same witnesses on the reopening packet | 9,058 / 9,058 PASS |
| next second infeasible | 9,058 / 9,058 |
| exactness precondition met (full policy = contact) | 9,036; 22 not met (still full-checker PASS) |
| acceptance 7: budget-code (PEAK/DOSE) differences, `/1` vs reopening | 0 of 9,058 requests |
| verdict differences on the 30-min grid (175,392 units) | 14,954, all "no re-entry infeasible / reopening feasible"; none the other way |
| non-prefix feasible sets | 0 |
| no-route place rows: origin point in flame at departure | 950 |
| no-route place rows: fire-limited within loaded graph | 98 |
| no-route place rows: possibly road-limited (ROAD-LIMITED) | 32 |

**Earlier-arrival variant with a LATER leave-by than kriged_mean.**
- This is the count the 19:15 amendment requires: 166 (place, field, variant) rows over 45 (region, start, horizon, place).
- Every such row has a kriged_mean leave-by; none comes from kriged_mean having no route.
- Shift: median 10,065 s, maximum 20,888 s, minimum 2 s.
- CERT rows by start:
  - Uiseong 23T01Z: 56;
  - Uiseong 24T09Z: 15;
  - Yeongdeok 25T19Z: 6;
  - Yeongdeok 25T23Z: 4;
  - Uiseong 25T17Z: 2.
- CERT and ROUTER give identical counts.

| | U h5 | U h8 | YD h5 | YD h8 |
|---|---|---|---|---|
| firms_early (CERT = ROUTER) | 21 | 19 | 2 | 3 |
| envelope (CERT = ROUTER) | 17 | 16 | 2 | 3 |

- **Nesting, measured on the rasters.** firms_early arrival is ≤ kriged_mean on all 10,955 cells (2,364 earlier, 8,591 equal, 0 later). So firms_early vs kriged_mean is a nested pair, and every firms_early row above breaks monotonicity under `/1`.
- **Expected cause, not yet shown:** pre-start burn-out. Under `/1`, a cell whose earlier arrival puts its burn-out before the start is open from 0. Under kriged_mean the same cell is still burning or not yet burned.
- **The test** is acceptance 8 on `/2` (`NOREENTRY2_ACCEPTANCE_RULE.md`). If the rows disappear there, the cause is confirmed. Any row that remains is listed and explained.
- envelope (lo = firms_early, hi = firms_constrained) is not pointwise nested with kriged_mean by construction. Its rows are reported, not tested.

## `no_reentry/2` acceptance 6a–6d and 7, Richard's side (rule `NOREENTRY2_ACCEPTANCE_RULE.md`, committed first at ed87b5bb; VERIFIED: Nora, PASS, ledger row 68)

**Scope.**
- Labels: SCENARIO, not what happened. Graphs are road-limited.
- **Waiting rule:** waiting is allowed only at graph dead-end nodes (as supplied in graph.json).
- **Assumption:** no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour.
- Samples: Leo's 8 `/2` samples (819bcb91, MANIFEST_v3_7 sha256 7c178267…). These are Yeongdeok 25T11Z and Uiseong
  24T09Z, h5, 4 variants each. Each is built as a `/1` + `/2` pair from the manifest commands, into scratch paths, so
  the hashes are of these builds and are not canonical.
- B0 is recomputed independently from the export npz and the variant raster: router-cell centre → pixel; integer ms;
  a ≤ h inclusive.
- Yeongdeok 25T11Z has no INSTANCE entry. Its places are taken from the 25T19Z entry, recorded per sample.
- Runner: `deadline_field/noreentry2_accept.py`; batch: `batch/nr2_accept_batch.py`.
- Summary: `results/NOREENTRY2_ACCEPTANCE_6_7.json`.

| sample (h5) | B0 mine = plan meta (export-burned not present + variant burned out) | 6a phase mismatches | 6b origins equal (CERT, ROUTER; leave-by and 30-min grid) | 6c witnesses contact-clear on `/2` and `/1` | 7 radiation-convention-limited |
|---|---|---|---|---|---|
| U 24T09Z kriged_mean | 1,032 = 1,032 (1,032 + 0) | 0 | 252 / 252 | 125 / 125 | 0 |
| U 24T09Z firms_early | 1,186 = 1,186 (1,032 + 154) | 0 | 252 / 252 | 120 / 120 | 0 |
| U 24T09Z envelope | 1,087 = 1,087 (1,032 + 55) | 0 | 252 / 252 | 120 / 120 | 0 |
| U 24T09Z envelope_burnset | 0 = 0 | 0 | 252 / 252 | no witnesses (no origin has a route) | 0 |
| YD 25T11Z kriged_mean | 2,197 = 2,197 (2,197 + 0) | 0 | 270 / 270 | 270 / 270 | 0 |
| YD 25T11Z firms_early | 2,527 = 2,527 (2,197 + 330) | 0 | 270 / 270 | 220 / 220 | 0 |
| YD 25T11Z envelope | 2,215 = 2,215 (2,197 + 18) | 0 | 270 / 270 | 220 / 220 | 0 |
| YD 25T11Z envelope_burnset | 0 = 0 | 0 | 270 / 270 | 73 / 73 | 0 |

**Result: PASS on all 8.**
- 6a: `/2` phases = `/1` phases with B0 set to [0, ≥H), and no other cell differs.
- 6b: the `/2` field equals the `/1` + extra_blocks{B0: 0} field for every origin.
- 6c: every witness is contact-clear and passes the full checker on both packets.
- 6d: my B0 and its split equal Leo's plan meta. replaced_later_birth = 0 everywhere.
- 7: 0 jobs refused only because burned-out ground radiates. The witnesses checked are leave-by witnesses only.
- Self-test (`/1` fed in as `/2`, YD 25T19Z kriged_mean): 6a mismatches = |B0| = 7,457 exactly. 94 origins differ in
  6b, as expected.

**Nora (row 68).**
- She ran the runner on her own v3.7 builds of U 24T09Z and YD 25T11Z kriged_mean. Both are equal to these rows.
- All 8 B0 counts were matched independently in row 66.
- Notes:
  - 7 covers leave-by witnesses only. It is not a `/2` dose or peak statement.
  - YD 25T11Z takes its places from the 25T19Z entry.
- The headline rerun and acceptance 8 are unblocked.

## Waiting-location sensitivity, 1-h panel (rule `WAITING_SENSITIVITY_RULE.md`, committed first at 28251ca; runner b472b40; VERIFIED: Owen, PASS WITH NOTES, ledger row 50)

**Owen's reproduction and controls (row 50).**
- Reproduced exactly: the 3 Uiseong caches and Yeongdeok 25T19Z.
- The switch is not inert:
  - The flag takes waitable nodes from 554 to 23,158 of 23,158.
  - The whole feasible-departure sets are identical, not only the recorded departure, for all 506 (spec, origin,
    field) on Uiseong 25T17Z.
  - Positive control: with the same core, waiting everywhere enlarges the feasible set in 111 of 1,726 random
    (instance, origin) pairs and never shrinks one.
- Notes:
  - Yeongdeok 25T23Z and 26T08Z were not re-run.
  - The scope is 1 h only. Marcus's multi-hour 14/14 flips stand.

**Labels.**
- SENSITIVITY: waiting allowed at every node (not the supplied graph rule).
- Default: waiting is allowed only at graph dead-end nodes. This is documented as the default by the orchestrator's
  decision of 13 Nov.
- Wording (S) for these single-departure job verdicts: "The trip starts at the stated time. Once moving, a stop is
  allowed only at a road dead end (a graph dead-end node), which may be a short detour off the route; waiting is not
  allowed at any other node, including the start unless it is itself a dead end. Other departure times are separate
  results."
- Field: the optimistic (frozen packet) field. CERT and ROUTER are computed separately. The full checker reads the
  same modified graph.

**Scope.** The 6 planner caches, 9,722 jobs and 530 origins. Summary: `results/WAITING_SENSITIVITY_1h.json`.

| cache | jobs | origins | CERT feasible→feasible / no_route→no_route | ROUTER (same) | flips | faults | origin deadline changes |
|---|---|---|---|---|---|---|---|
| Uiseong 23T01Z | 1,523 | 86 | 1,188 / 335 | 1,188 / 335 | 0 | 0 | 0 |
| Uiseong 24T09Z | 1,518 | 85 | 1,158 / 360 | 1,158 / 360 | 0 | 0 | 0 |
| Uiseong 25T17Z | 1,557 | 85 | 1,068 / 489 | 1,068 / 489 | 0 | 0 | 0 |
| Yeongdeok 25T19Z | 1,810 | 92 | 1,522 / 288 | 1,522 / 288 | 0 | 0 | 0 |
| Yeongdeok 25T23Z | 1,673 | 91 | 1,512 / 161 | 1,512 / 161 | 0 | 0 | 0 |
| Yeongdeok 26T08Z | 1,641 | 91 | 1,522 / 119 | 1,522 / 119 | 0 | 0 | 0 |

- **Result.** At 1 h, allowing waiting at every node changes NO job verdict, CERT or ROUTER (0 of 9,722; 0 NO_ROUTE
  flips), and NO origin deadline (0 of 530). It also produces no faults.
- **The multi-hour picture differs.** Marcus's F-DYN (c) set has 14/14 NO_ROUTE → ROUTE under all-waitable. That
  multi-hour sensitivity is reported separately; this table must not be read as covering it.
- **Multi-hour arm of the rule.** Per the rule, it runs on the headline arm, `no_reentry/2`, once that exists. It has
  not been run yet.
- **Cost.** The Yeongdeok caches peak at 11.4–12.2 GB RSS under all-waitable. One run was killed for running out of
  memory while running alongside other jobs, and was rerun alone.

## Multi-hour HEADLINE run on `no_reentry/2`, 48 packet pairs (SCENARIO, not what happened; HEADLINE; VERIFIED: Nora, PASS WITH NOTES, ledger row 72 (the run and acceptance 8; the not-evaluated split is a separate request); no-route counts split per `NOT_EVALUATED_LABEL_RULE.md`, file `results/HEADLINE_NR2_not_evaluated_split.json`)

**Labels.**
- SCENARIO, not what happened. Graphs are road-limited: roads are limited to the recorded windows.
- **Assumption:** no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour.
  The static final-footprint row shows whether the road crosses the eventual burn area, not when it was safe to leave.
- **Fields:** CERT = router OR closed footprint; ROUTER = router rule only. Refusal claims come only from ROUTER.
- "Exact" is relative to the time-dependent model.
- firms_early and envelope: bracket-start, not a lower bound.
- envelope_burnset is its own static row. Burn set = kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940 AHI-buffer-only, 281 FIRMS-only).
- **Arm:** HEADLINE arm (`no_reentry/2`). A cell that has burned is closed for the whole horizon, including cells burned out before the start.
- **Dose and peak** (witness full checks, acceptance 7) carry the packet's `fdyn.no_reentry_flux` label verbatim:
  "burning intensity held to the horizon, including cells burned out before the start; raises dose and peak vs reopening and vs no_reentry/1; contact set equals Richard's closed-from-0 field".
- **Waiting rule (R):** Each departure time in [0, H], every integer second (verdicts on the 30-min grid), is a separate trip. Leaving later is how waiting at the start place is represented. Once moving, a stop is allowed only at a road dead end (a graph dead-end node), which may be a short detour off the route; waiting is not allowed at any other node.
  - The rule is not monotone in departure time.
  - Non-prefix feasible sets in this run: 0. Every leave-by below is a prefix leave-by.

**Coverage.** 48 pairs: v3.7 `no_reentry/2` + reopening × 4 variants × 6 recorded starts × {5 h, 8 h}.
- Leo's code at 819bcb91, MANIFEST_v3_7 (sha256 7c178267…).
- Each packet is built from the manifest command at its manifest `--out` path. **Environment: numpy 1.26.4, Python 3.13.18** (pinned for this stream). The HAZARD hashes recorded in the summary are numpy-1.26.4 hashes, not the hashes the F-DYN builders get on numpy 2.5.x (ledger row 72a: rebuilt on numpy 1.26.4 they equal these exactly, e.g. UA 25T17 h5 firms_early reopening 5bbcc2d51ee5 and `/2` f539a5ebf319; on numpy 2.5.x only `members.flux` differs, by float rounding).
- **Exposure numbers (open note).** Dose, peak and the radiation-convention-limited column read flux, and every exposure figure here is from numpy 1.26.4. Cross-environment size, measured on one packet pair (ledger row 72a, UA 25T17 h5 firms_early): max |Δflux| 1.7e-15 kW/m², max relative 3.8e-10. Margins in this run: the closest witness dose to the 100 kJ/m² limit is 96.11 (relative margin 3.9e-2, over 9,684 full checks on `/2` and reopening); the largest packet flux is 0.703 kW/m² against the 10 kW/m² peak limit; 0 DOSE/PEAK codes. So no flag or threshold label can flip at that size. Per-packet quantification on all 48 pairs across numpy versions is not done; cross-environment reproducibility of exposure figures beyond that packet pair is not yet established.
- Runner: `deadline_field/headline.py`; batch: `batch/headline_nr2_batch.py`.
- 0 build or run failures. Every packet's writer_identity.transform = `no_reentry/2`.
- Summary: `results/HEADLINE_NR2_summary.json`, per place, packet and variant. The raw per-pair outputs stay in scratch.

| check (totals over 48 pairs) | `/2` HEADLINE | (`/1` VARIANT, row 67) |
|---|---|---|
| CERT leave-by witnesses, full checker on the `/2` packet | 4,842 / 4,842 PASS | 9,058 / 9,058 |
| same witnesses on the reopening packet | 4,842 / 4,842 PASS | 9,058 / 9,058 |
| next second infeasible | 4,842 / 4,842 | 9,058 / 9,058 |
| exactness precondition met (full policy = contact) | 4,838; 4 not met (still full-checker PASS) | 9,036; 22 |
| acceptance 7: budget-code (PEAK/DOSE) differences vs reopening | 0 of 4,842 requests | 0 of 9,058 |
| verdict differences on the 30-min grid (175,392 units) | 64,169, all "no re-entry infeasible / reopening feasible"; none the other way | 14,954 |
| non-prefix feasible sets | 0 | 0 |
| no-route rows, split (NOT_EVALUATED_LABEL_RULE.md): start point on ground the model shows as burned before this start time: not evaluated | 1,114 (inside 1,114, touches 0) | – |
| no-route rows: route on `/1`, none on `/2` (flag "depends on the no-re-entry rule") | 248 (fire-limited 88, possibly road-limited 160) | – |
| no-route rows: origin already inside the modelled fire area at that departure time | timing variants 74; static envelope_burnset row 876 (separate stratum) | – |
| no-route rows: fire-limited within loaded graph (other) | timing variants 68; static row 6 | – |
| no-route rows: possibly road-limited (ROAD-LIMITED; other) | timing variants 16; static row 0 | – |

PASS = full policy OK and closed/router replay clear. The not-evaluated split is VERIFIED: Nora, PASS WITH NOTES, ledger row 73 (note applied: the timing variants and the static envelope_burnset row are shown as separate strata).

**`/2` vs `/1`, per place (1,044 (region, start, horizon, place) rows × 3 timing variants = 3,132 per field; CERT and ROUTER identical).**

| | CERT | ROUTER |
|---|---|---|
| same leave-by | 1,580 | 1,580 |
| no route on both | 198 | 198 |
| route on `/1`, no route on `/2`: not evaluated / depends on the no-re-entry rule | 1,074 / 248 | 1,074 / 248 |
| `/2` leave-by earlier (median 116 s, max 311 s) | 32 | 32 |
| `/2` later, or route on `/2` only | 0 | 0 |

- **Split of the rows that lost their route (`NOT_EVALUATED_LABEL_RULE.md`, committed first at da167134; B0 recomputed with Leo's `build.main` stopped inside `add_b0`; per-member |B0| = plan meta on all 48 packets; members agree; 0 consistency exceptions):**
  - **"start point on ground the model shows as burned before this start time: not evaluated": 1,074, all inside (touches 0).** "Under the no-re-entry rule nothing is computed from this point. This says nothing about whether people are there or whether roads are passable." These are not "no route", not in the no-road-escape set and not air candidates. A further 40 rows in this state already had no route on `/1`, so the state totals 1,114 rows.
  - **248 stay "no checked route"**, flagged "depends on the no-re-entry rule", with cause "every road exit crosses ground the model shows as already burned". Their existing split: fire-limited 88, possibly road-limited 160.
- **Why.** `/2` differs from `/1` only on B0 (acceptance 6a, ledger row 68). The not-evaluated state comes from the rule closing the start point's own cell, not from a search.
- **Per start and variant, 5 h** (8 h identical on every count). Unsplit no-route counts are not quoted. The static envelope_burnset row has no B0 cells (0 not evaluated); it is shown as its own row.

| start | variant | places | route | not evaluated (inside / touches) | lost route, depends on the no-re-entry rule | no route: origin already inside the modelled fire area at that departure time | no route: fire-limited | no route: possibly road-limited |
|---|---|---|---|---|---|---|---|---|
| Uiseong 23T01Z | kriged_mean | 84 | 56 | 8 (8 / 0) | 19 | 0 | 1 | 0 |
| Uiseong 23T01Z | firms_early | 84 | 54 | 10 (10 / 0) | 19 | 0 | 1 | 0 |
| Uiseong 23T01Z | envelope | 84 | 54 | 10 (10 / 0) | 19 | 0 | 1 | 0 |
| Uiseong 23T01Z | envelope_burnset (static row) | 84 | 0 | 0 (0 / 0) | 0 | 84 | 0 | 0 |
| Uiseong 24T09Z | kriged_mean | 84 | 51 | 20 (20 / 0) | 13 | 0 | 0 | 0 |
| Uiseong 24T09Z | firms_early | 84 | 47 | 22 (22 / 0) | 15 | 0 | 0 | 0 |
| Uiseong 24T09Z | envelope | 84 | 47 | 21 (21 / 0) | 13 | 1 | 2 | 0 |
| Uiseong 24T09Z | envelope_burnset (static row) | 84 | 0 | 0 (0 / 0) | 0 | 84 | 0 | 0 |
| Uiseong 25T17Z | kriged_mean | 84 | 29 | 42 (42 / 0) | 4 | 6 | 2 | 1 |
| Uiseong 25T17Z | firms_early | 84 | 12 | 43 (43 / 0) | 6 | 7 | 13 | 3 |
| Uiseong 25T17Z | envelope | 84 | 12 | 42 (42 / 0) | 6 | 8 | 13 | 3 |
| Uiseong 25T17Z | envelope_burnset (static row) | 84 | 0 | 0 (0 / 0) | 0 | 84 | 0 | 0 |
| Yeongdeok 25T19Z | kriged_mean | 90 | 52 | 33 (33 / 0) | 0 | 3 | 1 | 1 |
| Yeongdeok 25T19Z | firms_early | 90 | 50 | 36 (36 / 0) | 1 | 3 | 0 | 0 |
| Yeongdeok 25T19Z | envelope | 90 | 50 | 36 (36 / 0) | 1 | 3 | 0 | 0 |
| Yeongdeok 25T19Z | envelope_burnset (static row) | 90 | 27 | 0 (0 / 0) | 0 | 62 | 1 | 0 |
| Yeongdeok 25T23Z | kriged_mean | 90 | 50 | 39 (39 / 0) | 1 | 0 | 0 | 0 |
| Yeongdeok 25T23Z | firms_early | 90 | 49 | 39 (39 / 0) | 2 | 0 | 0 | 0 |
| Yeongdeok 25T23Z | envelope | 90 | 49 | 39 (39 / 0) | 2 | 0 | 0 | 0 |
| Yeongdeok 25T23Z | envelope_burnset (static row) | 90 | 27 | 0 (0 / 0) | 0 | 62 | 1 | 0 |
| Yeongdeok 26T08Z | kriged_mean | 90 | 48 | 39 (39 / 0) | 1 | 2 | 0 | 0 |
| Yeongdeok 26T08Z | firms_early | 90 | 48 | 39 (39 / 0) | 1 | 2 | 0 | 0 |
| Yeongdeok 26T08Z | envelope | 90 | 48 | 39 (39 / 0) | 1 | 2 | 0 | 0 |
| Yeongdeok 26T08Z | envelope_burnset (static row) | 90 | 27 | 0 (0 / 0) | 0 | 62 | 1 | 0 |

**Acceptance 8, earlier-arrival half** (`NOREENTRY2_ACCEPTANCE_RULE.md` §8; MULTIHOUR_HEADLINE_RULE.md amendment 19:15 UTC).
- **Nested pair tested:** firms_early vs kriged_mean. On the rasters firms_early arrival is ≤ kriged_mean on all 10,955 cells (2,364 earlier, 8,591 equal, 0 later).
- **Result:** 0 violations, CERT and ROUTER. The leave-by half rests on 520 comparable rows per field (514 equal + 6 earlier); the 52 rows where firms_early has no route are direction-consistent but are not leave-by comparisons (ledger row 72 note 3). No place has a later firms_early leave-by, or a firms_early route where kriged_mean has none.
  - Per field, over 1,044 rows: equal 514, firms_early earlier 6, firms_early no route with kriged_mean route 52 (a lost route is not a violation), no route on both 472.
- The classes above ("no route", "none on both") are monotonicity comparison classes, not counts of places without a route. They include rows in the not-evaluated state; the place counts are the split table above.
- **envelope vs kriged_mean:** not nested (lo = firms_early, hi = firms_constrained). Reported, not tested. Its counts are the same as firms_early, with 0 later rows.
- **The 166 `/1` rows** (earlier variant later than kriged_mean, row 67) have no `/2` route for the variant (ledger row 72 note 2: "no `/2` route", not "ordering fixed"; 142 lose both routes, 24 lose the variant's route, 0 stay comparable). Every one went by losing the variant's route, none by a leave-by moving earlier:
  - 71 per field: no route on both;
  - 12 per field: variant no route, kriged_mean route.

  This is consistent with the expected cause (pre-start burn-out open under `/1`), shown as: the B0 closure removes those routes.
- **Spotting-dilation half:** not run yet. It needs rebuilds with the clamp a_d = max(dilate(a), t_start); the rule goes in first.

**Possibly road-limited on `/2` (re-run candidates for the widened-graph rule).**
- 34 (region, start, place), each at both 5 h and 8 h:
  - Uiseong 23T01Z: 17;
  - Uiseong 24T09Z: 10;
  - Uiseong 25T17Z: 6;
  - Yeongdeok 25T19Z: 1.
- "Possibly road-limited" is a reachability heuristic at t = 0 (the reachable set touches a graph-window boundary node). It does not show that the window is the cause.

## Acceptance 8, spotting-dilation half, on `no_reentry/2` (rule `SPOTTING_NR2_ACCEPT8_RULE.md`, committed first at bfc67ae4; VERIFIED: Nora, PASS WITH NOTES, ledger row 77)

**Labels.**
- SCENARIO, not what happened. Graphs are road-limited.
- Isotropic dilation with no wind field. Nothing is claimed about actual spotting distances in 2025.
- This is a research check of monotonicity, not a spotting result.
- CERT = router OR closed footprint; ROUTER = router rule only.
- **Assumption:** no fire outside mapped or forecast cells; no conservative unknown-support tier exists at multi-hour.
- **Waiting rule (R):** Each departure time in [0, H], every integer second, is a separate trip. Leaving later is how waiting at the start place is represented. Once moving, a stop is allowed only at a road dead end (a graph dead-end node), which may be a short detour off the route; waiting is not allowed at any other node.
- **Environment:** numpy 1.26.4, Python 3.13.18.

**Hazards.**
- Base: kriged_mean.
- a_d = a where a ≤ start; otherwise a_d = max(dilate(a, d, lag 0), start). Dilation uses Leo's `fdyn.variants.dilate` at 819bcb91, unchanged.
- Nesting was checked before any build on all 6 starts:
  - a_0 = a on every cell;
  - 0 cells out of order for 0 ≤ 500 ≤ 1000 ≤ 2000.
- Clamped cells (start | d = 500 / 1000 / 2000):
  - UA 23T01Z: 116 / 290 / 714
  - UA 24T09Z: 182 / 420 / 956
  - UA 25T17Z: 681 / 1,590 / 3,335
  - YD 25T19Z: 679 / 1,498 / 3,044
  - YD 25T23Z: 532 / 1,216 / 2,532
  - YD 26T08Z: 497 / 1,130 / 2,299
- The batch passes the dilated raster as `--arrival`, so C0 is computed from it, and every clamped cell (arrival = start, inclusive) enters C0. UA 25T17Z, from ledger row 77: C0 = 4,673 / 5,354 / 6,263 / 8,008 cells for d = 0 / 500 / 1000 / 2000; each increment equals the clamped count. This departs from the wording of `NOREENTRY2_RULE.md` §6.3 ("never computed from a spotting-dilated raster"). **Dilation adds nothing to B0:** B0 = 3,168 at every d there. A clamped cell already has `/1` birth 0, and B0 excludes those cells, so `/2` closes nothing beyond `/1` because of the dilation. Rewording the rule and the builder docstring is a builder-side note.

**Run.**
- 24 pairs: 6 recorded starts × d ∈ {0, 500, 1000, 2000} m, h5.
- Builds: `/2` + reopening from the v3.7 manifest commands, with `--arrival`, `--arrival-variant` and `--out` replaced. Every packet's transform is `no_reentry/2`.
- Runner `deadline_field/headline.py`, unchanged. Batch `batch/spot_nr2_batch.py`; comparison `deadline_field/spot_nr2_compare.py`.
- Files:
  - `results/ACCEPT8_SPOTTING_NR2.json`;
  - `results/ACCEPT8_SPOTTING_NR2_rasters_meta.json` (raster sha256 and the nesting checks).
- 0 build or run failures.

**Control (pass/fail): PASS on all 6 starts.** At d = 0 every place's CERT and ROUTER leave-by and no-route status equals the committed HEADLINE `/2` kriged_mean h5 row.

**Witnesses.**
- Every `/2` CERT leave-by witness passes the full checker on its own packet and on the reopening packet, with every next second infeasible.
- 0 failing witnesses, so no place is excluded.
- The exactness precondition is not met on 7 witnesses, all UA 25T17Z (d = 0: 2, 500: 3, 1000: 2); they still pass the full checker.

**Result: 0 violations, CERT and ROUTER.** No place has a later leave-by under the larger dilation, or a route under d′ where d has none. CERT and ROUTER counts are identical.

| start | 0→500 equal / earlier / lost / none on both | 500→1000 | 1000→2000 | 0→2000 |
|---|---|---|---|---|
| UA 23T01Z | 56 / 0 / 0 / 28 | 55 / 1 / 0 / 28 | 49 / 0 / 7 / 28 | 49 / 0 / 7 / 28 |
| UA 24T09Z | 49 / 0 / 2 / 33 | 42 / 6 / 1 / 35 | 39 / 2 / 7 / 36 | 38 / 3 / 10 / 33 |
| UA 25T17Z | 8 / 20 / 1 / 55 | 8 / 18 / 2 / 56 | 1 / 23 / 2 / 58 | 1 / 23 / 5 / 55 |
| YD 25T19Z | 46 / 2 / 4 / 38 | 43 / 4 / 1 / 42 | 34 / 5 / 8 / 43 | 34 / 5 / 13 / 38 |
| YD 25T23Z | 45 / 1 / 4 / 40 | 43 / 0 / 3 / 44 | 33 / 2 / 8 / 47 | 33 / 2 / 15 / 40 |
| YD 26T08Z | 45 / 0 / 3 / 42 | 42 / 0 / 3 / 45 | 33 / 2 / 7 / 48 | 33 / 2 / 13 / 42 |

- "Lost" (a route under d, none under d′) and "none on both" are monotonicity comparison classes, not counts of places without a route. They include places in the not-evaluated state (`NOT_EVALUATED_LABEL_RULE.md`), which this check does not split.
- The row-61 artefact (spotting making places safer) cannot occur here: no place moves later.
