# No-re-entry packet transform (rule; DRAFT until Richard and Marcus confirm the definition; fixed before any code)

Orchestrator, 2026-11-12: person-facing multi-hour outputs now default to **no re-entry**. Richard's definition is
in F-3.1 `MULTIHOUR_HEADLINE_RULE.md` §1 @53def3b (claude/f31-deadline-field): "a cell that has burned is closed
from its birth to the end of the horizon". That is `PacketModel(duration_factor="never")` in `deadline_field/real.py`.
Every packet phase keeps its birth and has its end set past the horizon:
- present fire: [0, ∞);
- an ignition at b: [b, ∞);
- cells burned out before the start are not phases, so they stay open.

## Transform

**1. Law.** Within each member:
- a cell born at b (b ≥ 0, in the member's own plan) is active on **[b, H)**;
- present fire is active on **[0, H)**;
- nothing else is active. Burned-out-at-start cells are not blocked, as in Richard's arm. `envelope_burnset` keeps
  its own law, which already blocks its burn set on [0, H).

**2. Implementation.** The law is built through the writer's **scalar law**:
- `burning_duration_s` = H and R = H. That gives [b, b + H) ⊇ [b, H), and [0, H).
- This is the mechanism `envelope_burnset` uses (PACKET_CONSISTENCY_RULE.md A).
- HAZARD and the arrays therefore express one law, and the builder self-check applies unchanged.
- Births are the variant's own plan:
  - kriged_mean and firms_early: the ignition plan;
  - envelope: the bracket-start lo. With T = H the per-cell end disappears, so the **no-re-entry envelope is a
    scalar-law packet with consistent arrays, not HAZARD-only**;
  - envelope_burnset: unchanged content, but the identity is new (see 4).

**3. Flux. OPEN QUESTION for Richard and Marcus.** The writer computes flux from the active sets, so a cell active
to H also radiates to H.
- **Proposal: F1.** `consumed_fraction` = cf0 · H / T0. The heat-release-rate density fuel · ΔH · cf / T is then
  unchanged: a cell radiates at its burning intensity until H. This is conservative and is the burnset convention.
- **Consequence.** Dose and peak on no-re-entry packets are **higher** than on the reopening packet. Richard's
  "never" arm changes contact phases only, and reads flux from the as-built packet.
- **So like-for-like holds for flame/contact only, not for exposure, unless one of these is chosen:**
  - **F2:** contact-only transform. Flux is copied from the reopening packet bin by bin. That is not
    constructible through the writer, and would be a hand-assembled HAZARD, i.e. HAZARD-only with refused arrays.
  - **F1, accepted** as the stated conservative reading, with exposure results labelled.
- I recommend F1, labelled "no re-entry; burning intensity held to the horizon (conservative)". Decision pending
  Richard, Marcus and the orchestrator.

**4. Identity.**
- The transform enters the F-DYN settings as `fdyn.transform = "no_reentry/1"` with
  `source_law_version = "wfg.fdyn.no-reentry-scalar/1"`. The settings digest, construction id and scenario ids
  therefore differ from the reopening packet: a different hazard gets different ids.
- `NATIVE_METADATA` / `REPORT` carry the transform name.
- The frozen writer files are untouched (injection points only).
- The reopening packet keeps its identity and is labelled "research variant: fixed burning duration, reopening after
  burn-out (unsourced; Sofia)".

**5. Manifest.**
- `MANIFEST_v3_6.json` = the v3.5 entries, unchanged (reopening; byte-identical builds), plus one `no_reentry`
  entry per (region, start, H, variant) with `--no-reentry`, under `packets_v36_noreentry/`.
- Labels: the variant label + "no re-entry (default for person-facing outputs)".

## Acceptance (stated before code)

1. **No transform.** Every builder path without `--no-reentry` gives packets byte-identical to v3.5. Test:
   Yeongdeok 25T11Z h5 kriged_mean HAZARD equals the per-numpy table (`6940f293…` / `5716c09e…`).
2. **Self-check.** The builder self-check (consistency.py) passes on a no-re-entry sample of every variant.
3. **Equivalence to Richard's arm (contact).** For every member and every HAZARD bin [l, r) of the no-re-entry
   packet, the flame set equals {cells with a v3.5-packet phase birth b ≤ l}. The births come from the v3.5 packet's
   own arrays: ignition_time_s, and current_active at birth 0. Checked on a sample per variant. Where Richard's
   `PacketModel(never)` is importable, its phase starts are compared directly too.
4. **Flux.** It is reported, not asserted: per sample, max and total flux vs reopening, as F1 implies.
5. **Envelope.** The no-re-entry envelope packet passes the array path (not refused), with arrays consistent with
   HAZARD.

## Verification

Nora verifies. Richard and Marcus confirm the definition (§1, §3) before code.

## Orchestrator decision (2026-11-12, after the draft): approach approved; F1 accepted with conditions

- **Approved:**
  - the scalar law with T = R = H;
  - its own identity;
  - `MANIFEST_v3_6`;
  - the acceptance tests as listed.
- **F1 accepted as the conservative reading, provided it is labelled.**
  - **The label.** "burning intensity held to the horizon; raises dose and peak vs reopening; contact set equals
    Richard's never-clears".
  - **Where it goes:** in the packet identity, as `fdyn.no_reentry_flux` in the settings, and therefore in
    HAZARD / REPORT / NATIVE_METADATA. It also goes in the README.
- **No hand-assembled HAZARD-only contact-only packet.**
- **Acceptance additions:**
  6. **Exact match to Richard's field.** The contact/flame sets equal Richard's no-re-entry field exactly. Where his
     `PacketModel(duration_factor="never")` is importable, compare against its phases on the same v3.5 packet: every
     cell's phase start equals the no-re-entry packet's first flame bin, and no flame bin ends before H.
  7. **Verdict-change count.** Count the requests (F-DYN `requests.py`, the same INSTANCE requests) whose dose or
     peak verdict differs between the reopening and no-re-entry packets. It is expected to be about 0, since flux is
     far below the limits. It is **reported, not asserted**.
- **Start condition.** Code starts only after Richard and Marcus confirm the definition (§1).

## Richard's confirmation (2026-11-12)

- **Q1, the definition: confirmed.** It is exactly his `PacketModel(duration_factor="never")`:
  - each packet phase keeps its birth, and both ends are set to 10^12;
  - present fire is [0, ∞), and an ignition at b is [b, ∞);
  - burned-out-at-start cells are not phases, so they are not blocked.
  - Births are aligned to 300 s bins, so acceptance 3/6 must agree exactly. Richard will also check our packet cell by
    cell against his arm on the v3.5 reopening packet.
- **Q2, flux: F1 accepted for his headline exposure columns.** His label: "exposure: no re-entry, burning intensity
  held to the horizon (F1, conservative)". Both his label and the orchestrator's go into the README; the identity
  gets the orchestrator's.
  - **His conditions:**
    - the builder self-check passes;
    - the writer identity is in BUILD_SUMMARY.
  - He does not need a contact-only flux copy.
- **Still waiting on Marcus** (S1/S2 benchmark).

## STATUS (2026-11-12): acceptance 1–6 pass; 7 not run (blocked as stated below)

**Code and manifest.**
- Code at 86f73d17: `fdyn/build.py --no-reentry`, `fdyn/_packet_child.py`, `fdyn/manifest.py`.
- `MANIFEST_v3_6.json`, `wfg.fdyn.manifest/7`: 976 entries. They are the 488 v3.5 entries verbatim (transform
  `reopening`) plus 488 `no_reentry/1`.

**Results** (`NOREENTRY_CHECK.json`, `fdyn/noreentry_check.py`; Yeongdeok 25T11Z h5, all 4 variants, numpy 2.5.3):

1. **No transform.** The reopening build of kriged_mean has HAZARD `6940f293…` = v3.5.
2. **Self-check and identity.** The builder self-check is consistent on all 4. The identity carries
   `transform no_reentry/1`, `source_law_version wfg.fdyn.no-reentry-scalar/1` and the F1 label. The scenario ids
   differ from the reopening packet's.
3. **Own derivation.** Flame in every bin equals {cells with reopening birth b ≤ l}: 0 mismatches on all 4.
4. **Flux, reported.**
   - Max flux 0.701 → 0.702 kW/m² for kriged_mean, firms_early and envelope; burnset 0.703, unchanged.
   - Integrated flux × 2.30 (kriged_mean), × 2.58 (firms_early), × 1.57 (envelope); burnset unchanged. Burnset
     content is identical by construction; its identity is new.
5. **Array path.** The array law is consistent on all 4, including `envelope`, which is now scalar-law and not
   refused.
6. **Richard's reader.** `deadline_field.real.load_packet` @13d89793 was run on both packets of each variant:
   - 0 cell-set differences;
   - 0 birth differences;
   - 0 no-re-entry phases ending before H.

**Acceptance 7 (dose/peak verdict-change count): not run.**
- `fdyn/noreentry_verdicts.py` used `routing-package`'s solver.
- Its validator rejects these packets (`EVIDENCE_CLASS`: RESEARCH_CONSTRUCTION needs fixture or mentor evidence).
- Its graph validation takes 190 s per call on the full-grid graph.
- So it is the wrong tool for these packets. The count needs the research router / full checker that Richard's
  headline pipeline already runs on both packets.
- **Proposal:** Richard reports the count from his full-checker witnesses on the reopening and no-re-entry packets of
  each run. Orchestrator to decide.
- Peak cannot flip: max flux 0.70 kW/m² against the 10 kW/m² budget. Dose can, because the integrated flux rises.

### Acceptance 7 delegated (orchestrator, 2026-11-12)

- **Who runs it.** Richard's headline pipeline reports the dose/peak verdict-change count as a row in his multi-hour
  results, under his committed rule:
  - the same witness is checked by the full checker on the reopening packet and on the no-re-entry packet;
  - the count is the requests whose PEAK/DOSE codes differ.
- **No second router is run here.**
- **Why.** `routing-package`'s validator rejects RESEARCH_CONSTRUCTION packets (`EVIDENCE_CLASS`), and its full-grid
  graph validation takes 190 s per call.
- **Meanwhile the F1 label stands:** integrated flux × 1.6–2.6; peak unchanged at 0.70 kW/m²; dose may flip.

### Nora: PASS WITH NOTES, ledger row 56 (@1fa85140)

- **Her checker:** `verification/nora_nr_check.py` on `verification/nora-fire`.
- **Inputs:** built from `MANIFEST_v3_6.json` (sha `b9b1e853`) under numpy 2.5.4: Yeongdeok 25T11Z h5 × 4 variants
  in both transforms, plus Uiseong 25T17Z h5 kriged_mean in both.
- **Her results:**
  - **(a)** The reopening builds are byte-identical to her v3.5 builds, in all 5 files.
  - **(b)** `consistency.check` is True on all 5 no-re-entry packets.
  - **(c)** Her own derivation finds 0 mismatches in all 5. No birth falls strictly inside a no-re-entry bin, no cell
    leaves flame before H, and the no-re-entry flame cells equal the reopening ever-flame cells.
  - **(d)** The no-re-entry envelope passes all 5 readers she probed; its v3.5 twin is still refused by all 5.
  - Identity, flux and commands match ours; 24 tests pass.
- **Notes, recorded here:**
  1. **Wording correction.** The reopening entries keep their **commands verbatim**; each entry gains two keys
     (`transform`, `transform_label`). "Entries verbatim", in STATUS above and in the manifest's superseded reason,
     is inaccurate. The manifest file is not edited, because its sha `b9b1e853` is in use. This note is the
     correction.
  2. **Envelope certification label.** The kit checker now accepts the no-re-entry `envelope`. Any
     INDEPENDENTLY_CERTIFIED result on it is relative to the bracket-start envelope, which is **not a lower bound**,
     and that label stays attached to every such result.
  3. **Exposure label.** Acceptance 7 is open and delegated to Richard. Peak cannot flip; dose can (integral
     × 1.6–2.6). Exposure results stay F1-labelled until the count exists.
  4. **Coverage.** Byte identity of the reopening path was checked on Yeongdeok 25T11Z only. Nora's Uiseong sample
     covered consistency and derivation.

### Richard: no-re-entry packets equal his never-clears arm (claude/f31-deadline-field, results/NOREENTRY_CHECK_v36.json)

- **Setup.** `MANIFEST_v3_6` @1fa85140; Uiseong 25T17Z h5, all 4 variants. Our `no_reentry/1` packet against
  `PacketModel(reopening packet, duration_factor="never")`.
- **Reader.** The no-re-entry packets load through the unchanged scalar reader (HAZARD_FLAME_EQUALS_NPZ_PHASES).
- **Cells.** 0 member-set differences, 0 birth differences, 0 phases ending before H.
- **Edge blocks.**
  - ROUTER rule: identical on all 43,826 edges.
  - CLOSED rule: they differ on 2,085 / 2,970 / 3,254 / 43,512 edges, **only at or after the horizon**. The scalar law
    expires at b + H; the arm uses +∞. No journey can use those times.
- **Feasible-departure sets.** Identical for all 2,520 (origin, destination) pairs in each variant.
- **For Marcus.** A per-edge EB/WB comparison must be cut at H, or compare the feasible sets.

### Correction: writer identity in BUILD_SUMMARY (Richard, 2026-11-12)

- **What was wrong.** The builder did not write the writer identity into `BUILD_SUMMARY.json`. Only HAZARD, REPORT
  and NATIVE_METADATA carried it, so Richard's condition ("writer identity in BUILD_SUMMARY") was **not met**, as I
  had claimed.
- **Fixed.** `_packet_child.py` now adds `BUILD_SUMMARY.writer_identity`:
  - `packet_writer_sha256`, `base_packet_writer_sha256` and `support_writer`, copied from the written HAZARD identity;
  - `source_law_version` and `transform` (`reopening` or `no_reentry/1`);
  - `no_reentry_flux`;
  - `fdyn_builder_sha256` of `build.py` and `_packet_child.py`.
- **Packets unaffected.** The other packet files are unchanged. Rebuilt Yeongdeok 25T11Z h5 kriged_mean, reopening
  and no-re-entry: HAZARD, REPORT, NATIVE_METADATA and npz sha256 are identical to the earlier builds (`6940f293`,
  `509c3496`).
- **Manifest unchanged.** `MANIFEST_v3_6` regenerates byte-identical.
