# Wiring support_mask into the F-9.3 build() and the F-DYN child (rule; fixed before any code)

Orchestrator, 2026-11-12, after #152 merged. The writer wrapper is `support_mask/` on Main (Hannah rows 36, 37 and
41), and the unknown rule is `support_mask/DESIGN.md`. This file fixes **how** each build path obtains and applies a
mask. Verifiers: Hannah (wrapper use) and Nora (F-DYN packets).

## 1. Default: nothing changes

- `ArrivalScenario` gains `support` (default `None`). F-DYN `build.py` gains `--support-mask NPZ --support-rule R
  --support-provenance JSON` (default absent).
- With the default, every path is byte-identical to before. That covers c651, zones, rasters, perimeter sequences
  and every F-DYN manifest entry. A regression test shows it.

## 2. Which source gets which mask

Native north-up, on the packet grid; True = supported.

| Source | Mask | How it is applied |
|---|---|---|
| c651 | `c651_unknown/1`, derived inside the wrapper | F-9.3 `build()` calls `support_mask/build_packet_f93.py --support-rule c651_unknown/1`, the verified CLI, instead of the frozen `build_packet.py`. Only when `sc.support == 'c651_unknown/1'`. |
| arrival_raster (F-DYN, KFS_01 export grid) | **no unknown cells**: see note A below | The mask is all-true, so **no mask is applied**. |
| perimeter_sequence | `supplied/1`: support = `known['inside_declared_domain']` (inside P_n when no domain is declared) | Passed to F-DYN `build.py`, then the child. Static only: see the refusal in §3. |
| zones (API adapter) | **not wired** | The API child (`api/adapters/_zone_packet_child.py`) is outside this work's scope (no API change). Stated, not done. |

**A. Arrival rasters have no unknown cells on this grid** (support_mask DESIGN.md rule 2; F-9.3 DESIGN.md
item 6).
- Inside the mapped grid, a cell outside the final perimeter is observed no-fire.
- Cells outside the grid are not in the packet.
- So the mask is all-true, and **an all-true mask is never applied**.

**B. Never apply an all-true mask** (all source types). The wrapper would change the writer identity without changing
any content, and v1 and masked packets would be told apart for no reason.
- An all-true mask is therefore handed off: the frozen writer's identity is kept.
- The decision is still recorded in `BUILD_SUMMARY.json` (`fdyn.support` / `F93_INTERFACE.json` `support`), never
  in packet files: `{"rule": …, "unsupported_cells": 0, "applied": false, "reason": "all cells supported"}`.

## 3. Hard conditions: the build fails on any of them

- **Perimeter sequences, time-dependent unknown.**
  - If any cell inside the domain lies in no polygon (no fire up to t_n, unknown after it) and t_n is before the
    packet horizon, the build refuses with `SUPPORT_TIME_DEPENDENT`.
  - support_mask DESIGN.md rule 3. A static mask cannot express this.
- **Mask shape.** The mask must be the full KFS_01 export grid (79 × 237) or the packet grid. With a window it is
  cropped to the window exactly as the ignition plan is (`r0:r1+1`, `c0:c1+1`). Anything else raises
  `SUPPORT_SHAPE`.
- **Order inside the F-DYN child:**
  1. the frozen writer runs;
  2. `support_mask.packets_f93.apply_support` runs: this does the wrapper's own self-check, validator and array-law
     check;
  3. for `envelope` only, the NaN-array rewrite (PACKET_CONSISTENCY_RULE.md B);
  4. the builder self-check (`fdyn/consistency.py`).

  The mask is applied before the NaN rewrite because the wrapper's array-law check needs real arrays.
  `meta['arrays_sha256_as_written']` then records the masked arrays before the NaN rewrite.
- **Wrapper conditions all hold:** `SUPPORT_CONFLICT`, router validator, identity, and `SUPPORT_WRITE_FAILED` on
  failure.

## 4. What is not changed

- No F-DYN manifest entry gains a mask: per note A, rasters stay all-true. **MANIFEST_v3_5 is unchanged and no new
  manifest is issued.**
- A masked F-DYN packet arises only from a perimeter sequence today, or later from the padded grid (orchestrator
  decision (b), with its own rule).
- Frozen writer, frozen CLI, `support_mask/` files and API: unchanged.

## 5. Acceptance tests (stated before the code)

1. **Default unchanged.**
   - The existing F-9.3 tests pass unchanged: c651 byte-identical to the direct build, zones identical to the API
     adapter, and perimeter-sequence ingestion.
   - The F-DYN tests pass.
   - One F-DYN manifest entry built with the new `build.py` and no support arguments is sha256-identical to the v3.5
     packet: Yeongdeok 25T11Z h5 kriged_mean, `6940f293…`.
2. **c651 through `build()` with `support='c651_unknown/1'`.** Byte-identical, for HAZARD, REPORT, NATIVE_METADATA
   and npz, to `build_packet_f93.py --support-rule c651_unknown/1` directly, for Yeongdeok 03-25 19Z. 2,885
   unsupported cells.
3. **arrival_raster with an all-true mask.**
   - The packet is sha256-identical to the no-mask build: not applied, frozen identity.
   - BUILD_SUMMARY records `applied: false`.
4. **Perimeter sequence, horizon ≤ t_n, with a declared domain smaller than the grid.**
   - The masked packet carries the wrapper identity.
   - Unsupported cells equal the count outside the domain.
   - The wrapper self-check, array law and builder self-check all pass.
   - Flame, flux, ids and breakpoints equal the unmasked build of the same scenario.
5. **Perimeter sequence, horizon > t_n, with in-domain no-polygon cells:** refused with `SUPPORT_TIME_DEPENDENT`.
6. **Envelope rule with a mask:** apply, then the NaN rewrite, then the builder self-check reports the array path
   REFUSED, and the HAZARD support equals the mask.

## Correction 1 (before any test ran; found while writing test 6)

**What was wrong.** §3 and test 6 assumed a mask can be applied to the per-cell `envelope` variant before its
NaN-array rewrite. It cannot:
- `envelope` arrays as written by the frozen writer carry the scalar law, while its HAZARD carries per-cell ends.
  They are inconsistent by design (PACKET_CONSISTENCY_RULE.md B), which is why they are NaN'd.
- The verified wrapper's `apply_support` runs the array-law check and would refuse them (`PACKET_INCONSISTENT`).
- The merged wrapper is not modified.

**Corrected rule:**
- A support mask is applied only to **scalar-law** packets: the sampled rule (`*_sampled`), `kriged_mean`,
  `firms_early` and `envelope_burnset`.
- A mask requested with the per-cell `envelope` variant or rule is refused **before any build**:
  - F-DYN `build.py`: `SUPPORT_ENVELOPE_UNSUPPORTED`;
  - `ArrivalScenario.validate`: `SUPPORT_NOT_WIRED`.
- Test 6 becomes: a mask with the `envelope` rule is refused before building, and no output directory is created.
- Test 4 uses the `sampled` rule.

**Effect.** A per-cell envelope with unknown cells needs a writer path that can express both, e.g. option C. Until
then, unknown cells in an envelope scenario are handled downstream under the three-way rule, as before.

## STATUS: acceptance passes (code 5b3177d8, 2026-11-12)

`tests/test_support_wiring.py`: 5 of 5 pass (Python 3.13, numpy 2.5.3).
1. **Default unchanged.** The F-DYN `build.py` build of Yeongdeok 25T11Z h5 kriged_mean, without support arguments,
   has HAZARD sha256 `6940f293…`, which equals v3.5 (Nora row 41).
2. **c651 through `build()`** with `support='c651_unknown/1'` is byte-identical to `build_packet_f93.py` directly:
   all 4 files, 2,885 unsupported cells.
3. **All-true supplied mask:** all 4 files are sha256-identical to the no-mask build, and BUILD_SUMMARY
   `fdyn.support.applied = false`.
4. **Perimeter sequence (sampled, horizon = t_n = 4 h; domain = grid minus a 15 × 37 corner box):**
   - ids, breakpoints, flame and flux equal the unmasked build;
   - the wrapper identity is present, with base = the frozen writer;
   - unsupported cells = 555 = the box;
   - HAZARD support equals the flipped domain;
   - builder self-check consistent, and no failure marker.
5. **Perimeter with horizon 5 h > t_n:** refused with `SUPPORT_TIME_DEPENDENT`, and no output.
6. **Envelope with a mask:** refused before build in both entry points (`SUPPORT_NOT_WIRED`;
   `SUPPORT_ENVELOPE_UNSUPPORTED`), and no output.

**Existing suites unchanged:** F-9.3 `test_iface.py` (3), F-DYN `tests/` (24) and `support_mask/` (13): 40 of 40 pass.

**Verifiers:** Hannah (wrapper use) and Nora (F-DYN packets).

### Nora: PASS WITH NOTES, ledger row 42 (F-DYN side)

- **Order.** Rule 15:34:43 → correction 15:36:37 → code 15:39:23 → acceptance 15:42:15.
- **Tests.** test_support_wiring 5 of 5; F-DYN 24 of 24.
- **Her own builds** of Yeongdeok 25T11Z h5 kriged_mean, with her own masks:
  - **No mask:** HAZARD `6940f293`.
  - **All-true mask:** all 4 files byte-identical to the no-mask build; `applied=false`.
  - **20 × 50 block mask** (1,000 cells false): the self-check passes; ids, breakpoints, flame and flux equal the
    unmasked build; HAZARD support equals her mask in every bin; `applied=true`.
  - **`envelope` + mask:** `SUPPORT_ENVELOPE_UNSUPPORTED`, with no output.
- **Note, a stated limitation.** Masked packets currently have **no independent check** and **cannot be read by
  array-contract readers**.
  - The replay `Packet`, the kit's `ffi_independent_checker` and Richard's `PacketModel` (d731b3a) all **refuse** a
    packet with npz `support = false`, because their contracts require all-true support.
  - That is safe, since they fail closed.
  - The router itself reads HAZARD support: `UNSUPPORTED` routes, and withheld global claims.
  - Richard's HAZARD-only path (0f96a26) was not tested.
  - Until a reader that accepts support masks exists and is verified, results on masked packets are router-only.
    They are labelled "single implementation, not independently checked".
  - **F-3.2 certificates (Thomas, 2026-11-12, `thomas/routing-next` 97dd5a5f).**
    - **The finding.** F-3.2's ContactModel path never read `support`, so before this fix it would have issued
      certificates on a masked packet as if it were fully supported.
    - **The fix.** `routable_contact_model` now refuses any packet with an unsupported entry.
    - **Past results.** None were affected: every packet used had full support.
    - **Consequence.** **F-3.2 issues no certificate on an F-9.3 masked packet** (CERTIFICATE_SPEC §5.3). Certifying
      only routes that avoid unsupported cells would need its own design, and none is planned.
    - **Binding.** Thomas verified it on Leo's Yeongdeok 25T19Z pair (plain / `c651_unknown/1`):
      - npz sha256 match (`f93307eb…` / `1c39f2fd…`);
      - the binding digest A differs only through `support`, and W differs;
      - a certificate on the frozen packet is rejected against the masked twin (`BIND_A`).

### Hannah: PASS WITH NOTES, ledger row 50 (wrapper side); notes handled

- **Her checks.**
  - Commit order verified.
  - Default HAZARD is identical before and after the wiring in both of her environments (numpy 2.5.4 `6940f293`;
    numpy 1.26.4 `5716c09e`).
  - A forced child failure gives `SUPPORT_CONFLICT`, the failure marker, and no BUILD_SUMMARY.
  - `build.py` refusals return rc 1 with no output directory.
  - Tests: 5 + 16 + 24 pass.
- **Note 1, environment-pinned hash.** Test 1's v3.5 hash is now a per-numpy-version table: 2.5 → `6940f293…`,
  1.26 → `5716c09e` (prefix, hers). For an unrecorded numpy version that one assertion is skipped, and the skip is
  printed. The all-true comparison does not depend on the environment and always runs.
- **Note 2, interpreter.** The test now launches `build.py` with `sys.executable`, not a bare `python3`.
- **Note 3, scope limit, now stated.** `support_args` assumes the **KFS_01 export grid (79 × 237) and
  t0 = 2025-03-22T02:24Z**, the same constants as the F-9.3 adapters.
  - For any other event it fails closed: the shape check runs first and raises `SUPPORT_SHAPE`.
  - t0 is used only by the perimeter time check, and is never reached for another grid.
  - Generalising both means deriving them from the scenario's export when a second event is wired.
- **Note 4, failure marker.** The F-DYN child now also writes `SUPPORT_WRITE_FAILED` when the builder consistency
  check fails after a mask was applied. Before this, only the missing BUILD_SUMMARY signalled it.

### Hannah: PASS, ledger row 52 (@5e965d77)

- Row-50 notes 1–4 are closed.
- test_support_wiring passes 5 of 5 under both numpy 1.26.4 and 2.5.4; F-DYN 24 of 24.
- The 1.26 entry in test 1's hash table is now her full-length hash, `5716c09e70b285ce…5d4326`.
