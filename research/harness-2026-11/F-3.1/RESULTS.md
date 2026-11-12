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

## F-DYN multi-hour deadline fields (SCENARIO, not what happened; Nora request #4 pending)

* **Claim file and inputs.** The claim file is `results/FDYN_V31_recorded_starts.json` (commit `505b8d3`), built by
  `deadline_field/fdyn_run.py` on Leo's MANIFEST_v3_1.
  * Coverage: 24 packets = 6 recorded starts × {5 h, 8 h} × {kriged_mean, firms_early}.
  * firms_early is a bracket-start, not a lower bound.
  * Roads are limited to the recorded windows on the interim graphs.
* **Witnesses.** Every exact per-(origin, shelter) deadline witness passes the unchanged full checker and the closed
  replay: **6,288 of 6,288 PASS**. 2 are labelled `upper_bound` because dose could bind over their journey duration;
  both still pass.
* **Caveat.** Fire-set deadlines are few per packet: UA 0–10 of 84 origins, YD 0–2 of 90. **Most witnesses therefore
  test the scenario window, not the fire.**

## Burn-duration sensitivity of feasible-departure holes (Uiseong; rule committed before running)

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
* **Stated limit.** The sensitivity covers the scalar-law v3.1 packets only, not the per-cell envelope packets
  (v3.3 envelope and envelope_burnset). Yeongdeok gets the never-clears arm only, on its packets with holes at f = 1
  (rule addition dated 2026-11-12).
* **What this means.** The contiguous deadline is sensitive to the placeholder burning duration: at f = 2 it moves
  for 2–10 of 84 origins per packet. Deadlines that depend on burn-out are not robust to that law.

## Unknown-support three-way rule at 1 h (all 6 caches)

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

## Issue-order-by on F-DYN v3.1 (post-processing; SCENARIO; latency settings are assumptions)

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
