# F-3.1 results: the deadline field on the six recorded planner caches (1-hour panel)

Status: **final 1-hour reproduction numbers, VERIFIED: Nora, request #2, PASS WITH NOTES on all 6 caches (ledger row 25 @4ed6b8cb)**. The F-DYN multi-hour, forecast-ablation,
unknown-support and clean-timing results are reported separately once run. The verified multi-hour work in this cut is in the sections from "Multi-hour work in this cut" on. All numbers below are measured. Anything
not measured is labelled as such.

## What was run

* **Code and inputs.** Code at commit `70f70d7`, run from a clean worktree. The verified commit `c8247d2` also contains changes made after `70f70d7`. These are inactive on these caches: origin = destination admission (0 such jobs), a start-position scope guard, the per-journey dose duration bound in the precondition output, and the `--timing-only` flag. It also contains the opt-in packet modes `extra_blocks`/`present_only` in `real.py` and the `postprocess.py`/`export.py` helpers, which the reproduction does not use. The ablation, unknown-support and F-DYN modules present at `c8247d2` are removed from this frozen branch; they continue on the working branch, with their own verification. Inputs are the frozen routing inputs
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

## Multi-hour work in this cut

This frozen cut adds the verified multi-hour work done after the 1-hour cut (#133): the `no_reentry/1` VARIANT run, `no_reentry/2` acceptance 6a–6d and 7, the 1-h waiting-location sensitivity with the final waiting-rule wording, and the HEADLINE run on `no_reentry/2` with acceptance 8 (nested earlier-arrival half) and the not-evaluated split. Other follow-up work (ablation, provenance, unknown-support, F-DYN v3.x studies, lever, return trips, spotting, rate tier, the acceptance-8 spotting half, the widened graph) stays on the working branch with its own verification.

## Multi-hour `no_reentry/1` VARIANT run, 48 packet pairs (SCENARIO, not what happened; VARIANT, not the headline; VERIFIED: Nora, PASS WITH NOTES, ledger row 67)

**Nora's notes (row 67).**
1. The HAZARD sha256 values in the summary are NOT the canonical v3.6 packet hashes. Example: Uiseong 25T17Z h5 kriged_mean `/1` is bc058bd7 here and e02e5135 canonically. The batch rewrites `--out` to an absolute scratch path, which enters provenance. Results are unaffected. Treat the summary's hashes as the hashes of these scratch builds only.
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
- Each packet is built from the manifest command at its manifest `--out` path. **The HAZARD hashes do not reproduce Nora's builds** (ledger row 72 note 1: e.g. UA 25T17 h5 firms_early `/2` f539a5eb here vs 55dd21b8; `--out` is not the cause). Under investigation via `provenance.identity`; the routing results reproduced exactly (336/336 places).
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
