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
