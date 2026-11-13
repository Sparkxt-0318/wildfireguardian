# "Not evaluated" state for the HEADLINE (`no_reentry/2`): labelling rule (committed before re-tabulating)

- **Source.** The assessor's verdict on the HEADLINE run 54bcb96e, adopted in full by the orchestrator (13 Nov,
  04:21 UTC).
- **Scope.** No new field runs. The rule (`NOREENTRY2_RULE.md`, c22a59d9) is unchanged. This is a labelling and
  re-tabulation of the committed run.

## The state

- **Label, verbatim:** "start point on ground the model shows as burned before this start time: not evaluated".
- **Explanatory line, verbatim:** "Under the no-re-entry rule nothing is computed from this point. This says nothing
  about whether people are there or whether roads are passable."
- **Never** written as "no route", "trapped" or "safe".

## Membership (per region, start, horizon, place, timing variant)

- **B0.** B0 is recomputed per (region, start, horizon, variant) with Leo's code at 819bcb91, unchanged:
  - `fdyn/build.py` main is called with the v3.7 manifest `/2` command;
  - the run is stopped inside `add_b0`, before any packet is written;
  - B0 per member = the cells that `add_b0` sets to birth 0, i.e. C0 ∧ ¬present fire ∧ (`/1` birth ≠ 0).
  - The per-member |B0| must equal the plan meta `no_reentry2.added_at_0[k].b0_total`. This is checked and
    reported.
- **Router cells.** Export pixel → router cell by cell centre (as in acceptance 6). A router cell is in B0 if its
  centre pixel is in B0 in any member. Whether all members agree is reported.
- **Start point p.** The INSTANCE `entry_node` coordinates in the graph the run used.
- **inside:** the router rule's point cell (`grid.cell_of(p)`) is in B0.
- **touches:** p is not inside, but some cell that the closed rule's point test reaches (`cells_touching_box(p)` with
  `clip_closed(p, p, rect)` not None) is in B0.
- **The state uses inside OR touches.** This matches the CERT origin test the run used. Both are reported
  separately.

## Counting rules

1. **First in cause precedence.** The state comes ahead of "origin already inside the modelled fire area at that
   departure time".
   - It applies even if the point also meets present fire.
   - It is not in the no-road-escape set, and not an air candidate.
   - It has its own count in every table.
2. **inside and touches** are reported separately. The state uses both.
3. **Per timing variant:** kriged_mean, firms_early, envelope. The static envelope_burnset row gets its own split.
4. **Every headline count of places without a route is shown split** into this state and the rest. Unsplit no-route
   counts are not quoted. The unsplit counts in the 54bcb96e RESULTS section are replaced.
5. **Static final-footprint row:** these rows are their own stratum. They are not mixed into its counts.

## The other rows that lost their route from `/1` to `/2`

- **Which rows.** A route on `/1` (row 67), none on `/2`, and not in the state above.
- **Labels.** They stay "no checked route", with:
  - the flag "depends on the no-re-entry rule";
  - the cause label "every road exit crosses ground the model shows as already burned".
- **Kept split.** Their existing no-route split (fire-limited / possibly road-limited) is kept alongside.

## Pass/fail

- **B0 count check.** Per-member |B0| must equal the plan meta for every (region, start, horizon, variant).
- **Consistency.** Every place in the state must have a CERT origin-in-flame at t = 0 on `/2` (no-route split
  `origin_point_in_flame_at_departure`). Any exception is listed.
