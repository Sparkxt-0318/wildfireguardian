# `no_reentry/2`: no re-entry, including cells burned out before the start (rule; APPROVED, written before any code)

**Status.**
- **Approved.** The draft (34e18880) was approved by the orchestrator (2026-11-12 22:30 UTC). Richard confirmed §1
  and §3 (22:31 UTC). Their conditions and precisions are in **§6 (amendments at approval)**. Where §6 and §1–§5
  differ, **§6 governs**.
- No code before this commit.

**Source.** Richard's ruling, in F-3.1 `MULTIHOUR_HEADLINE_RULE.md` on `claude/f31-deadline-field`:

> The person-facing default is the stricter reading: a cell that has burned is closed for the whole horizon,
> **including** cells that burned out before the start (closed on [0, H)). Leo adds transform **no_reentry/2**
> (= no_reentry/1 plus pre-start burned-out cells closed on [0, H); own writer identity; manifest v3.7; rule first;
> Nora verifies).

F-BASE `DESIGN.md` (harness/s-d1-next) makes `/2` the default once Nora passes v3.7. Until then, `no_reentry/1`
(v3.6 @ ff3c031c) is a labelled variant only.

## 1. Law

`no_reentry/1` (NOREENTRY_RULE.md) is unchanged. `/2` adds one set per member. Every cell in
**C0 = cells that had burned at or before the start** is active on **[0, H)**. C0 is the union of:
- **(a) export-burned cells.** The recorded (or synthetic) export's known-burned cells:
  `source_burned_area_valid & source_burned_area == 1`. That is the writer's own `known_burned` (bridge.py), with
  present fire included.
- **(b) variant cells before the start.** Cells whose own variant arrival is finite and at or before the start:
  - kriged_mean and firms_early: the arrival raster a ≤ h;
  - envelope: the bracket start lo ≤ h.

C0 is everything that has burned. Within it, three kinds of cell are already active on [0, H) under `/1`:
- present fire (R = H);
- variant cells still burning at the start (catch-up birth 0);
- envelope cells with lo ≤ h < hi + T.

What `/2` adds is the rest of C0, the **burned-out-at-start set B0**:
- export-burned cells that are not present fire;
- variant cells before the start that `/1` takes as burned out. The plan records these as
  `variant_cells_before_start_not_in_export.taken_as_burned_out`.

**What does not change.** Cells born after the start are unchanged: they are closed on [b, H) as in `/1`.

**One consequence: the placeholder burning duration no longer matters for blocking.** In `/1` and in reopening, T
decides whether a pre-start cell is "still burning" (blocked) or "burned out" (open). In `/2`, every cell in C0 is
blocked on [0, H) whatever T is. That T is the export's `contract__cell_duration_s`, 3,970.46 s (1.10 h), the placeholder flagged unsourced by Sofia.

`envelope_burnset` already blocks the burn set ∪ present fire on [0, H). Its `/2` packet therefore has the same
content as its `/1` packet if **C0 ⊆ burn set ∪ present fire**. This is checked (acceptance 3). If it fails, the
`/2` burnset packet blocks burn set ∪ C0, and the difference is reported.

## 2. Implementation

The mechanism is the one `envelope_burnset` already uses: **birth 0 in the plan, with T = R = H**.
- **Plan (build.py `--no-reentry2`).**
  - Start from the `/1` plan.
  - Set the member's birth to 0 on B0. Do not touch present fire: the writer raises PRESENT_FIRE if a current cell
    draws an ignition.
  - Set `meta.transform = "no_reentry/2"`.
  - Record the counts in the plan meta, as `no_reentry2.added_at_0` = {export_burned_not_present, variant_burned_out}.
- **Child.**
  - It is the `/1` path (the `noreentry_construct` wrapper) with the transform name checked as `/1` or `/2`.
  - The scalar law with T = R = H turns birth 0 into [0, H). HAZARD and the arrays then express one law, and the
    builder self-check applies unchanged.
  - No new member loop.
- **Precedent for the writer's checks.** Birth 0 on export-burned, non-current cells is what `envelope_burnset` does
  today on its burn set minus present fire. Those packets pass the writer, the router validator and the array check
  (Nora PASS row 32; PACKET_CONSISTENCY_RULE.md A). The `/2` sample is checked again on every one of them
  (acceptance 2 and 5).
- **Frozen files.** The writer files `packets.py` and `bridge.py` are not touched. Only the existing injection points
  are used.

## 3. Flux: the decision is open; F1 is proposed

`/2` cells radiate because they are active. Under F1 (`/1`'s accepted convention), **B0 cells radiate at burning
intensity for the whole horizon, although they had burned out before the start.** That is the burnset convention,
which Iris accepted: no cell is cleared on the placeholder T. It is conservative, but it can raise dose and peak a
lot in places where most of the window had already burned. Uiseong is 99.7% of the window in the burn set.
- **F1 (proposed).** As `/1`, with this label in the packet identity, as `fdyn.no_reentry_flux`:
  "burning intensity held to the horizon, including cells burned out before the start; raises dose and peak vs
  reopening and vs no_reentry/1; contact set equals Richard's closed-from-0 field".
- **Not offered: flux without B0.** It would be constructible in the F-DYN loop, but HAZARD flux would then not
  follow from the arrays. That makes it HAZARD-only, refused by array readers, and the orchestrator ruled out
  hand-assembled contact-only packets for `/1`.
- **Reported, not asserted.** The flux change vs `/1` and vs reopening (acceptance 4). Dose/peak verdict changes are
  counted by Richard's pipeline, as for `/1`.

## 4. Identity

- **Settings.** `fdyn.transform = "no_reentry/2"`, `source_law_version = "wfg.fdyn.no-reentry-scalar/2"`, plus
  `fdyn.no_reentry` text naming C0, B0 and the counts. The settings digest, construction id and scenario ids
  therefore differ from both `/1` and reopening.
- **BUILD_SUMMARY.** `writer_identity.transform = "no_reentry/2"`.
- **Labels.**
  - The variant label + "no re-entry; also closed from the start where burned out before it (default for
    person-facing outputs once Nora passes)".
  - `/1` keeps its packets and becomes "VARIANT: no re-entry after the start; cells burned out before the start stay
    open", as in Richard's ruling.

## 5. Manifest

- **`MANIFEST_v3_7.json`, schema `wfg.fdyn.manifest/8`.**
  - The 976 v3.6 entries, with their commands verbatim (488 reopening, 488 `no_reentry/1`).
  - Plus 488 `no_reentry/2` entries, one per (region, start, H, variant), with `--no-reentry2`, under
    `packets_v37_noreentry2/`.
- **Earlier manifests.** `MANIFEST_v3_6.json` is not edited, and `/1` is not superseded: it remains the labelled
  variant.
- **Burnset label.** The ENVELOPE_BURNSET_RULE.md label is held for "the next manifest", so it goes into v3.7 on the
  burnset entries of all three transforms:
  - "static final-footprint bound (no timing; identical across starts)";
  - the mandated wording: "burn set = kriged footprint ∪ FIRMS ∪ buffered AHI (16,176 cells; 10,955 kriged, 4,940
    AHI-buffer-only, 281 FIRMS-only)".

  This is a label only: no reopening or `/1` command changes.

## Acceptance (stated before code)

**Samples.** Yeongdeok 25T11Z h5, all 4 variants (as `/1`), plus one Uiseong start (the most-burned window), all 4
variants.

1. **No change elsewhere.** Builds without `--no-reentry2` are byte-identical to v3.6:
   - reopening HAZARD per the per-numpy table;
   - the `/1` HAZARD equal to its v3.6 build.
2. **Self-check and identity.**
   - The builder self-check is consistent.
   - The router validator passes.
   - The identity carries `no_reentry/2`, `no-reentry-scalar/2` and the F1 label.
   - The scenario ids differ from `/1`'s and reopening's.
3. **Own derivation.** For every member and every HAZARD bin [l, r) of the `/2` packet:
   - the flame set must equal (the `/1` packet's flame set in that bin) ∪ B0;
   - B0 must be recomputed independently from the export npz and the variant raster, not taken from the plan;
   - the B0 counts must equal the plan meta counts.

   Also reported: C0 \ (burn set ∪ present fire), which is expected to be empty, and the burnset `/2` vs `/1`
   content.
4. **Flux, reported.** Per sample: max and integrated flux for `/2` vs `/1` vs reopening.
5. **Array path.** The `/2` packets, envelope included, are scalar-law consistent (`fdyn/consistency.py`).
6. **Exact match to Richard's closed-from-0 field.** Richard's reader is run on the `/1` and `/2` packets. Per member:
   - the `/2` phases must equal the `/1` phases ∪ {c: [0, ≥ H) for c in B0};
   - and they must equal his own closed-from-0 arm, if he has one, built from the v3.6 reopening packet plus the
     export.
7. **Verdict changes, reported.** Dose/peak verdict changes `/2` vs `/1`, from Richard's full-checker pipeline as
   decided for `/1`.

## Verification

- Nora verifies.
- Richard confirmed §1, and §3 for his exposure columns, on 2026-11-12. See §6.

## 6. Amendments at approval (2026-11-12; committed before any code)

### 6.1 Time base, inputs and the inclusive comparison (Richard i; his request for exact paths)

**Time base.**
- Every arrival raster is in **hours since t0 = 2025-03-22T02:24:00Z**, the Choi 2026 convention. `read_raster`
  checks its `t0_utc` and refuses any other.
- Comparisons are in **integer milliseconds since t0**, as in `ignitions.py`:
  - a = round(arrival_h × 3,600,000);
  - h = (start − t0) in ms, a whole minute.
- **C0 uses a ≤ h, inclusive.** An arrival exactly at the start is in C0. Under `/1` such a cell is already a catch-up
  ignition at 0, so it is not in B0.

**Export npz, per region and start.** Keys: `source_burned_area_valid & source_burned_area == 1`.
- **Recorded starts.** `data/routing/latest_inputs_try02/exports/KFS_01/FORECAST_<start>.npz` exists for 6 starts:
  - 20250323T010000Z, 20250324T090000Z, 20250325T170000Z: Uiseong;
  - 20250325T190000Z, 20250325T230000Z, 20250326T080000Z: Yeongdeok.
- **All other starts.** The synthetic export
  `research/harness-2026-11/F-DYN/_data/synthetic_exports/FORECAST_<start>.npz`, written by
  `fdyn/synthetic_export.py` from the published kriged TOA (sha256 `fe81f945…`).
- **Which one applies.** The manifest entry's `cmd` decides (`--synthetic-export-dir` present or not). Of the 976 v3.6
  entries, 96 use recorded exports and 880 use synthetic ones. Both are the same KFS_01 grid (79 × 237).

**Variant rasters**, from the manifest `cmd`, key `arrival_h`, grid checked against the export:

| Variant | C0 raster (`--arrival`) | Used as |
|---|---|---|
| kriged_mean | `research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_toa.tif` (band 1) | a |
| firms_early | `research/harness-2026-11/F-DYN/_data/variants/firms_early.npz` | a |
| envelope | `research/harness-2026-11/F-DYN/_data/variants/firms_early.npz` | lo (hi = `firms_constrained.npz`, not used for C0) |
| envelope_burnset | `research/harness-2026-11/F-DYN/_data/variants/envelope_burnset_lo.npz` | lo = 0 h on all 16,176 burn-set cells |

For envelope_burnset this makes C0 ⊇ the burn set at every start. Its `/2` content is therefore expected to equal its
`/1` content; this is checked under acceptance 3.

### 6.2 B0 includes export-burned cells with a later variant birth (Richard ii)

B0 is **not** only "cells with no `/1` phase". Some cells are export-burned (not present fire) while the variant
raster places their arrival after the start.
- **Under `/1`.** The plan skips every export-burned cell (`burned_at_start`), so `/1` gives these cells no phase.
- **Under `/2`.** These cells are in B0 and are active on [0, H).

**General rule.** For every c in B0, the `/2` phase is [0, H), and it **replaces** any `/1` phase [b, H) of c.
- **The per-bin check:** `/2` flame in bin [l, r) = `/1` flame ∪ B0.
- **The per-member phase check:** `/2` phases = `/1` phases with every c in B0 set to [0, ≥ H).

### 6.3 Never from a dilated raster; no dilation packets in v3.7 (Richard iii; orchestrator)

- C0 is computed **only from the variant's own arrival raster** listed in 6.1, plus the export. It is never computed
  from a spotting-dilated raster.
- Dilated rasters are clamped a_d = max(dilate(a), t_start) (Nora), so dilation adds nothing to C0.
- **No dilation packets enter MANIFEST_v3_7.** Dilation experiments use Richard's clamp fix on his side. His earlier
  dilation runs created artificial pre-start "burned-out" cells, and `/2` is only for timing variants where cells
  really burned before the start.

### 6.4 Flux: F1 accepted, with two conditions (orchestrator; Richard)

F1 is accepted as the conservative convention, with the label in §3 (verbatim, `fdyn.no_reentry_flux`).
- **(a) Acceptance 7 counts.** Acceptance 7 reports, through Richard's pipeline, the requests whose **DOSE or PEAK
  verdict differs**:
  - from the reopening packet;
  - from `/1`.

  Both are reported **per region, Uiseong separately**, and stated as counts. No claim is made that `/2` exposure is
  a bound.
- **(b) Separate refusal column.** Any refusal that arises only from B0 radiation is reported in its own column,
  **"radiation-convention-limited (burned-out ground held at burning intensity)"**. It is never merged with
  contact-limited refusals.
  - **The reason.** The contact set is the rule. The flux on burned-out ground is a convention, and the reader must
    be able to separate the two.
  - **Who reports it.** Richard's pipeline, which compares the checker codes of the same witness on `/2` and on
    `/1` + extra_blocks (6.5).
- **Placeholder T.** As stated in §1, blocking under `/2` no longer depends on the placeholder burn duration T. T
  still enters flux, through the F1 consumed-fraction scaling.

### 6.5 Acceptance 6 as Richard will run it (replaces §Acceptance item 6)

Richard's never-clears arm (`PacketModel(duration_factor="never")`) only extends phases the packet already has. A
cell burned out before the start has no flame bin, so that arm never closes it. **`/2` is therefore compared with
`/1` + extra_blocks, not with "never".**

Richard builds a closed-from-0 check in his reader:
- **His own C0.** He recomputes C0 from the export npz and the variant raster of 6.1. Then B0 = C0 minus the cells
  already active at 0 in `/1`. He does not take it from the plan meta.
- **Phase check, per member.** `/2` phases == `/1` phases with every c in B0 set to [0, ≥ H).
- **Field check.**
  - field(`/2` packet) == field(`/1` packet + extra_blocks {c ∈ B0: 0}), on CERT and ROUTER, for every origin.
  - The full_check verdicts of the witnesses are compared too. The extra_blocks path closes the router and closed
    rules from 0 to H.
- **Counts.** His B0 counts against the plan meta `no_reentry2.added_at_0`.
- **Reported, not accepted.** reopening + extra_blocks(C0 at 0) vs `/2`. This one is a check only: from reopening,
  in-window cells reopen and would not match.

Richard commits his acceptance-6 rule in F-3.1 before running anything.

### 6.6 Monotonicity, and Marcus's instances (orchestrator)

- **Acceptance 8, reported by Richard.** Across nested hazards no place's leave-by gets later. The nested hazards are
  earlier-arrival variants vs kriged_mean where pointwise earlier-or-equal, and dilations through his clamp fix
  (outside v3.7). This is the property in his MULTIHOUR_HEADLINE_RULE.md, now run on `/2`.
- **Marcus.** Marcus's instances are built from these `/2` packets once Nora passes v3.7.

### Order of work

1. This commit: the rule.
2. Code: `build.py --no-reentry2`, the child (transform check for `/1` or `/2`), `manifest.py` for v3.7, and tests.
3. The `noreentry2_check.py` sample run (acceptance 1–5), and the B0 counts.
4. The Richard, then Nora, steps that follow.
