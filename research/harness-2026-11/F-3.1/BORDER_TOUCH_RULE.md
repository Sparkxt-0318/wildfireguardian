# Headline witnesses that touch the export-grid border (rule; committed before any re-witness run)

- **Requested by:** the assessor (13 Nov, 04:21 and 04:34 UTC), to be stated as a limit of the HEADLINE in the
  widened-graph report.
- **Effect on results:** none. No HEADLINE number changes.
- **Labels:**
  - SCENARIO, not what happened. Graphs are road-limited.
  - CERT = router OR closed footprint; ROUTER = router rule only.

## What is counted

- **Upper bound, stated in every label.** The count is of the stored **witness** (one route per place, field,
  variant, start and horizon) that touches the border.
  - A place whose witness touches the border may have another route that does not.
  - The count is therefore an upper bound on how many HEADLINE results depend on "nothing burning just outside the
    fire-data grid".
  - The exact number would need the run repeated with border-touching roads closed. That is not done here. It is
    possible if the orchestrator decides the upper bound is large.

## Definitions

- **Primary: footprint test, as the widened-graph padding-closed arm uses it.**
  - Consider the closed-rule contact footprint of every leg, evaluated against padding cells. A padding cell is a
    375 m cell on the export lattice outside the export grid (WIDENED_GRAPH_RULE: export grid + 14 cells).
  - The footprint of each leg type:
    - EDGE leg: `cells_touching_box` on the widened lattice with `clip_closed(p0, p1, rect)` not None.
    - WAIT leg, the origin point and the destination dwell point: the same point test.
  - A witness touches the border if any footprint includes a padding cell.
  - Cells are closed rectangles that share their boundary with the export grid. So this is equivalent to: some leg
    segment or point has a point on, or outside, the export-grid rectangle's boundary. The count is computed with the
    footprint test itself; the equivalence is asserted on every witness, and every disagreement is listed.
- **Proxy, reported beside it and labelled "proxy". It is not the count.** It is the larger number because a road in the outer ring need not reach the grid boundary. Such a road has no padding cell in its closed footprint, so the padding-closed arm does not block it. A witness has some leg whose footprint includes a cell in the
  outermost ring of export cells (row 0, row H−1, column 0, column W−1).

## How

- **Packets.** Rebuild the 48 HEADLINE `/2` packets from the v3.7 manifest commands (Leo 819bcb91). The reopening
  packets are not needed.
- **Fields.** For each place, recompute CERT and ROUTER leave-by on the `/2` packet with `deadline_field.core`
  (`backward`, `issue_set`, `witness_greedy`), exactly as `headline.py` does. Store the witness legs.
- **Pass/fail.** Each recomputed leave-by must equal the committed `results/HEADLINE_NR2_summary.json` value for that
  place, field and variant. Every mismatch is listed, and that place is excluded from the count with the exclusion
  stated.
- **Witness check.** Each witness is checked by `full_check` on its `/2` packet. Its result is reported.

## Reported

- **Per region, start, horizon and timing variant, CERT and ROUTER separately:**
  - witnesses;
  - touching the border (footprint test);
  - touching the outer ring (proxy).
- **The static envelope_burnset row** on its own.
- **Not-evaluated rows** have no witness and are not counted. Their number is stated.

## Amendment 1 (committed before any run): which witness per place

- **Leave-by.** The HEADLINE place leave-by is the end of the union, over the place's destinations, of the feasible
  departure sets (`headline.py`). More than one destination can contain that second.
- **Witnesses.** For each destination whose feasible set contains the place's leave-by, `witness_greedy` gives one
  witness at that second. The witnesses of all such destinations are checked.
- **A place counts as touching the border at two levels:**
  - **"any":** at least one of its leave-by witnesses touches. This is the reported upper bound.
  - **"all":** every one of its leave-by witnesses touches. Not every route that departs at the leave-by is
    enumerated, so this is also not exact.
- **Per (place, destination) witness counts** are reported as well.
- **ROUTER witnesses** are full-checked like the CERT ones, and their outcome is reported. A ROUTER witness may fail
  the closed rule; it is not required to pass, and this is not a fault.
