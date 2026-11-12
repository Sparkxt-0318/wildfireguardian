# `no_reentry/2` acceptance 6–8: Richard's side (rule; committed before any run)

Source: F-DYN `NOREENTRY2_RULE.md` §6 (Leo, c22a59d9). Runs start only after Leo's `/2` sample packets exist and
after the `no_reentry/1` variant batch is written up.

## Inputs (independent of the `/2` plan)

- **Time base.** Hours since t0 = 2025-03-22T02:24:00Z. Integer ms: a = round(arrival_h × 3.6e6); h = start − t0 in
  ms. C0 = {cells with a ≤ h} (inclusive) ∪ {export cells with `source_burned_area_valid & source_burned_area == 1`}.
- **Export.** The file the manifest command names: the recorded `exports/KFS_01/FORECAST_<start>.npz`, or the
  synthetic export under `--synthetic-export-dir`.
- **Raster per variant, key `arrival_h`.**
  - kriged_mean: `KFS_01_pswt_ok_toa.tif` band 1;
  - firms_early: `variants/firms_early.npz`;
  - envelope: lo = `firms_early.npz`;
  - envelope_burnset: `envelope_burnset_lo.npz`.
- **Never a dilated raster.**
- **B0 per member.** B0 = C0 minus the cells whose `/1` phase (my reader, `load_packet`) starts at 0 and runs to ≥ H.
  It includes export-burned cells with a later `/1` birth.

## Acceptance 6 (pass/fail)

- **6a Phases.** For every member s and every cell c, the `/2` phase set must equal the `/1` phase set with every c in
  B0 replaced by [0, ≥H). No other cell may differ. Every mismatch is listed.
- **6b Field.** For every origin, compare:
  - CERT and ROUTER leave-by on the `/2` packet;
  - on `/1` + `extra_blocks = {c ∈ B0: 0}` (closed and router rules from 0 to the horizon).

  Equal is defined after 9-significant-digit rounding, as rerun_compare. Issue sets are compared on the 30-min grid.
- **6c Witnesses.** Every `/2` CERT leave-by witness is checked by `full_check` on the `/2` HAZARD and on the `/1`
  HAZARD. The full checker reads HAZARD, so it cannot see `extra_blocks`; the `/1` + extra_blocks side of the comparison
  is therefore 6b's field (issue sets), not a checker replay. Pass: every witness is contact-clear on `/2` (and,
  necessarily, on `/1`, where B0 is open). Full-policy outcomes on both are counted for 7.
- **6d Counts.** My |B0| per member, split into export_burned_not_present and variant_burned_out, must equal the plan
  meta `no_reentry2.added_at_0`.
- **Reported only, not pass/fail.**
  - Reopening + extra_blocks(C0 at 0) against `/2`.
  - |C0 \ (burn set ∪ present fire)|.

## Acceptance 7 (reported)

- **DOSE/PEAK budget-code differences.** `/2` vs reopening and `/2` vs `/1`, per region, with Uiseong separate.
- **Radiation-convention-limited (burned-out ground held at burning intensity).** A job counts here when:
  - it is contact-feasible on `/2`;
  - its witness fails `full_check` on the `/2` packet with DOSE or PEAK codes only;
  - and the same witness passes on `/1` + extra_blocks, where B0 cells block but do not radiate.

  These jobs have their own column. They are never merged into ROUTER refusals.
- **Label.** Every dose and peak column carries Leo's `fdyn.no_reentry_flux` label verbatim.

## Acceptance 8 (reported; MULTIHOUR_HEADLINE_RULE.md amendment 19:15 UTC, unchanged)

- **Nested hazards only.** The check is run on `/2` across:
  - spotting dilation d = 0 ⊆ 500 ⊆ 1000 ⊆ 2000 m, rebuilt with Nora's clamp a_d = max(dilate(a), t_start);
  - an earlier-arrival variant vs kriged_mean, but only where that variant's arrival is pointwise ≤ kriged_mean on
    every cell of the window.

  If the arrival is not pointwise earlier or equal, that pair is not nested. It is reported as "not nested" with the
  count of cells where it is later, and it is not tested.
- **What is checked.** No place's leave-by may get later under the larger hazard (CERT and ROUTER). A route lost under
  the larger hazard is not a violation.
- **Violations.** Every violation is listed and explained. None is suppressed.

Assumption line on every multi-hour output, and the waiting-rule label on every table with NO_ROUTE.
