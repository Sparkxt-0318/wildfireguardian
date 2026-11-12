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
* **ROUTER-only columns.** These will be added next to the CERT labels (`threeway --variant router`). From now on,
  every tier and horizon reports both by default.

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
    identical to v3.3's. The burnset field results above therefore carry over to v3.4. They have not been rerun, so
    the packet hashes in the claim are v3.3's.
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
  16,176-cell burn set: the 2025 fire spread from Uiseong into Yeongdeok. In Uiseong, therefore, no origin has a
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
