# Early-action list: build rule and pass criteria (written 13 Nov, before any build)

> **Staff and agency use only (owner decision, option a). Not resident-facing.** SCENARIO from a fire
> reconstruction, not what happened. Every route is "checked" only in the project's sense: a witness passes the
> full checker on the as-built packet. That says nothing about road condition on the day.

The list follows DESIGN.md §1–§2 (the routing author's text, @ c9989fce → 4b23211b). This file fixes **how** the list
is built and **what must hold** before anyone reads it. The assessor reads this rule before the build. The independent
verifier checks the output.

## 1. Inputs (pinned; read only, never recomputed)

| Input | Where | Pin |
|---|---|---|
| Per-place CERT and ROUTER leave-by per variant, `/2` headline | F-3.1 `results/HEADLINE_NR2_summary.json` | branch `claude/f31-deadline-field` @ 97f080c2; ledger row 72 |
| Row classes with the not-evaluated state | F-3.1 `results/HEADLINE_NR2_not_evaluated_split.json` | same commit; ledger row 73 |
| Edge-of-grid indicator (three Yeongdeok places) | F-3.1 `results/BORDER_TOUCH_NR2.json` | same commit; ledger row 80 |
| Widened-graph classes | F-DYN `results/WIDENED_RESULTS_UA.json`, `WIDENED_RESULTS_YD.json` | leo/f-c1-see-before-leave; ledger rows 82/82a (YD pending) |
| Place names, entry nodes, departure grid, H | F-DYN `_data/INSTANCE.json` | 819bcb91 |
| Packets | MANIFEST_v3_7 `no_reentry/2` | sha256 7c178267… |
| Checker | `deadline_field/headline.py` @ 54bcb96e + kit `routing-package/routing/independent.py::check_route` | file sha256 41fcfee2… |

Every input file's sha256 is recorded in the output header. A mismatch with the pins above stops the build.

## 2. Units and membership

- **A list unit** is a (region, start, horizon, place). There are 1,044: UA 3 starts × 2 horizons × 84 places, and YD 3
  × 2 × 90.
- **Timing variants:** kriged_mean, firms_early and envelope. envelope_burnset is shown as its own static row and never
  enters membership (DESIGN §1).
- **Departure grid:** INSTANCE `depart_offsets_s`, 0 to H − 1,800 in 1,800 s steps.
- **Feasible set per variant:** [0, leave_by] when a CERT leave-by exists, and empty when it does not.
  - This rests on the headline's measured prefix property: 0 of 48 packets had a non-prefix set (ledger row 72;
    DESIGN §2).
  - The list carries the flag "prefix (measured on the `/2` headline, ledger row 72)". It is not recomputed here,
    because the per-place issue sets are not in the committed files.
- **In the §1 set at grid departure t:** no variant's feasible set contains t. The CERT field is used throughout.
- **On the list:** the unit is in the §1 set at one or more grid departures **and** is not "not evaluated" (§3).

## 3. Not evaluated (rule 0): kept off the list, counted separately

- **Which units:** any unit whose split-table class is `not_evaluated` under **any** of the three timing variants.
  The count of units that are not evaluated under only some variants is reported.
- **Wording:** the adopted label, verbatim: "start point on ground the model shows as burned before this start time:
  not evaluated". It is followed by the state line from the split file.
- **Counts:** per region, start, horizon and variant, with "inside" and "touches" separate, exactly as in the split
  table. They are never added to a no-route count.

## 4. Cause label: exactly one per listed unit

- **Per variant:** each variant's split class maps to a label:
  - `no_route_origin_point_in_flame_at_departure` → **1**;
  - `lost_route_depends_on_no_reentry` → **1b**, flagged **"depends on the no-re-entry rule"**;
  - `no_route_fire_limited_within_loaded_graph` → **2**;
  - `no_route_possibly_road_limited` → **3**;
  - `route` → none.
- **Per unit:** the label of highest precedence over the three variants, in the order 1 → 1b → 2 → 3. Rule 0 was
  removed first.
- **When all three variants have a route at H but none at some earlier grid time:** this cannot happen under the prefix
  property. If it is met, it is an error that stops the build.
- **When a variant has a route (`route`) and another does not:** the label comes from the variants without a route. A
  unit whose three variants all have a route still enters the list if, at some grid departure after the earliest
  leave-by, every variant has passed its own leave-by. Its label is then **"every route closes within the horizon"**
  (internally: `closes_in_horizon`).
  - It is not a §1 cause, because the field shows the route closing. The precedence stays as above, and this label is
    used only when no variant carries 1–3.
- **Agency wording:** the label texts are DESIGN §1's, verbatim, each with "modelled".
- **Label 3 units:** they are shown with "undetermined: map window too small" and are excluded from every count of
  places without a road escape (DESIGN §1).

## 5. The columns, per listed unit

1. **Place:** the INSTANCE name (Korean, then romanised) and the origin id.
2. **Cause label (§4)**, plus the "depends on the no-re-entry rule" flag where it applies.
3. **For each of kriged_mean, firms_early and envelope,** the pair **"last computed time with a route / next computed
   time, none"**:
   - last = the largest grid departure ≤ leave_by; next = last + 1,800 s;
   - if next ≥ H, the pair reads "none up to the horizon (H)";
   - **a horizon-censored variant** (leave_by at H or later, or `horizon_censored`): "route at every computed time to H";
   - **a variant with no route:** "none at any computed time";
   - times are written as the offset from the start, and as KST clock time.
4. **The earliest of the three pairs.** It carries the label "earliest of the three variants computed; the fire may
   close roads earlier than any of them" (DESIGN §2). It is not a bound.
5. **envelope_burnset row:** the static final-footprint row from the headline, with its label verbatim.
6. **Waiting-rule dependence:** see §6.
7. **Departure grid step:** 1,800 s.
8. **Edge-of-grid indicator:** for 축산리, 옥계리 and 항리 (YD), on every row where they appear: "within one cell of
   the grid edge; radiant heat from fire outside the grid is not modelled". This is a contact-test caveat only (ledger
   row 80). The one-cell ring is an indicator, not a bound.
9. **Widened-graph class:** only for the candidate rows that the widened-graph rule re-ran. It is shown **only** as the
   class text:
   - "route found by the router on the widened graph, to the listed destinations; not independently checked";
   - "undetermined: depends on fire outside the export grid";
   - "no route found by the router on the widened graph to the listed destinations; not independently checked".

   It carries no time, no route geometry and nothing from the padding-open arm (WIDENED_GRAPH_RULE §2.2). The YD class
   is marked "verification pending" until the verifier's YD re-run passes.

## 6. Waiting rule

- **Header wording:** the list header carries the final (R) wording verbatim (DESIGN §1, WAITING_SENSITIVITY_RULE.md
  @ 1b792c77), with the range [0, H) and the 1,800 s step named. Single-departure statements, if any, carry (S).
- **Per-unit column:** "depends on the waiting rule" is filled only from a committed `/2` multi-hour "waiting allowed
  everywhere" run, if the routing author has one. Otherwise the column reads **"not computed for the `/2` multi-hour
  field"** on every row. It never says "no".
- **Sensitivity row:** the always-reported sensitivity row ("waiting allowed everywhere") is cited in the header, with
  its source.

## 7. Header of the list (every output file)

- The staff and agency label, and "SCENARIO, not what happened".
- The checker and its file sha, the packet manifest sha, and the numpy version.
- The (R) waiting wording.
- The map-edge bullet, verbatim from DESIGN §2: contact only; the three YD places named; heat not covered.
- The prefix flag.
- "earliest of the three variants … not a bound".
- The not-evaluated counts.
- The input file sha256 values.

## 8. Outputs

- `AIR-EXTRACT/results/EARLY_ACTION_LIST.json`: every unit with its fields, plus the counts.
- `AIR-EXTRACT/results/EARLY_ACTION_LIST.md`: tables per region, start and horizon, in the column order of §5.
- The builder is `AIR-EXTRACT/build_early_action.py`, committed before it is run.

## 9. Pass criteria (fixed now; any failure stops the list from being used)

- **E1, pairs.** For every listed unit and variant with a leave-by:
  - last is a grid departure, last ≤ leave_by and last + 1,800 > leave_by, or the censored or "none" wording applies
    as §5 says;
  - the earliest pair equals the minimum over the three variants.
- **E2, not evaluated.** No not-evaluated unit is on the list. The not-evaluated counts equal the split table's,
  per region, start, horizon and variant, for "inside" and "touches".
- **E3, membership.** Every listed unit has at least one grid departure t at which no variant's [0, leave_by] contains
  t. Every unit that is not evaluated and has such a t is listed.
- **E4, labels.** Every listed unit has exactly one label from {1, 1b, 2, 3, closes_in_horizon}, and the precedence
  is honoured. Label 3 units are excluded from the no-escape counts.
- **E5, reconciliation.** Listed + not evaluated + never in the set = 1,044, per region, start and horizon.
- **E6, edge caveat.** Every row for 축산리, 옥계리 and 항리 carries the caveat. No other row does.
- **E7, widened.** A widened class appears only on re-run candidate rows. Its text is one of the three strings in §5,
  and no time or geometry comes from the widened runs.
- **E8, ROUTER.** No refusal-grade statement is made. "No checked route" is read from CERT only. The CERT/ROUTER
  agreement count is reported (DESIGN §1: on the headline they agree on every place).
- **E9, wording.** The files contain no resident-facing text, and every label string is verbatim from DESIGN or the
  split file. A test checks the forbidden phrases: "safe", "no road escape" as a bare claim, "deadline", "no result
  depends on what burns outside the grid", and bare "no route".

## 10. Amendment 1 (13 Nov; from the assessor's read of 075e7b07, before any build)

The assessor's seven changes are adopted as written. The routing author's pins are added. These sections override §2–§9
wherever they differ.

**Pins (routing author, 13 Nov).**
- **Leave-by:** `places[*].nr_cert.per_variant.<variant>.leave_by_s` + `horizon_censored` in HEADLINE_NR2_summary.json.
  It was written once at 54bcb96e and is unchanged since; it is on Main via #170, and 97f080c2 carries the same bytes.
  sha256 017dbf1f566b4a2a….
- **Split:** HEADLINE_NR2_not_evaluated_split.json @ 50535521, also on Main via #170.
- **Waiting:** no `/2` multi-hour "waiting allowed everywhere" run exists. The only one is the 1-h panel (ledger row 50:
  0 changes, with the 14/14 multi-hour control flips). So the column reads "not computed for the `/2` multi-hour
  field" on every row.

**A1 (§3, replaces "any variant").** Every unit falls into exactly one of these groups:
- **(a) Evaluated under all three timing variants:** it goes to membership (A2).
- **(b) Not evaluated under all three:** off the list and counted, as before.
- **(c) Mixed:** its own table, headed **"timing variants disagree on whether the modelled fire has already reached the
  start point"**. It shows the pairs for the evaluated variants and "not evaluated" for the others.

**A2 (§2, the second table).** For the group (a) units:
- **The main list** is unchanged: at one or more grid times, every variant has closed (the intersection).
- **A second table, "no checked route under some variants only",** with the same columns. It holds every group (a)
  unit that is not on the main list but, at one or more grid times, has one or two variants without a route.
- **The rest** are "never in the set".
- **E5 reconciles over five groups:** main + some-variants + never + (c) + (b) = 1,044, per region, start and horizon.

**A3 (§7, absence line).** Every output file carries, verbatim: **"one fire, March 2025, that day's wind. A place not
on this list has not been shown to have a road escape."** E9 asserts that it is present.

**A4 (§4, the new label).**
- **Wording:** "a checked route at the start under every variant; none from a later computed time under every variant
  (modelled fire); cause of closing not classified".
- **Counting:** these units get their own count. They are **not** added to any no-escape total, because no
  reachable-set boundary test has been run at the closing time.
- **New column:** beside the unit label, the per-variant labels (from the split classes).

**A5 (§5, clock times).** Every clock time carries its date and "(replay)", for example "2025-03-25 19:30 KST
(replay)".

**A6 (E3, corrected).** Every listed unit has a grid t at which no variant's [0, leave_by] contains t. Every **evaluated**
unit (group a) with such a t is on the main list.

**A7 (E9).** "trapped" and "escape route" are added to the forbidden phrases.

**E9 scope (13 Nov, at the first build; recorded before the list is used).** The first build failed E9 on two strings
that are pinned verbatim, not list wording:
- the module name `deadline_field/headline.py` in the checker line;
- "…so no route on these graphs can touch it" in the verified map-edge bullet (ledger row 80).

The test now matches "deadline" as a whole word, and the scan skips exactly those two pinned strings. Every other
phrase and place is scanned as before. No label, count or pair changed.
