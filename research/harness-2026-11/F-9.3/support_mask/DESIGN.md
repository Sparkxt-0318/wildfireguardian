# F-9.3 support_mask: a versioned writer wrapper and the rule for what counts as unknown

Rule fixed **before any code** (orchestrator go-ahead, 2026-11-12). The F-9.3 design note (`F-9.3/DESIGN.md`, on the
F-DYN / F-9.3 working branch, PR #105) names this as the one writer change the superset needs. This file is the
design for it. The full F-9.3 interface is not on Main yet, so this sub-folder is self-contained.

## Why a wrapper, not an edit

- The writer `integration/src/wfg_latest/packets.py` (blob `7863ed66…`, sha256 `6b922418…`) and `bridge.py`
  (blob `70c9a6e1…`, sha256 `f7466e64…`) are frozen:
  - `research/postmerge-fixes-20261031/FROZEN_GIT_BLOBS.json`;
  - `research/routing/manifests/LATEST_INPUT_FREEZE.json`.
- The writer also stamps `packet_writer_sha256 = sha256(packets.py)` into every packet.
- **Decision (orchestrator).** A new versioned writer goes **outside the kit**, here. It imports the frozen
  `packets.py` and wraps `write_regional_packet`. Nothing under `integration/`, `routing-package/`, `api/` or
  `routing-api/` changes.

## Interface

- `packets_f93.write_regional_packet(*args, support_mask=None, support_rule=None, support_provenance=None, **kw)`.
- CLI `build_packet_f93.py`: the frozen `build_packet.py` arguments plus `--support-rule`.

**`support_mask=None` (default): complete hand-off.**
- The call is exactly `packets.write_regional_packet(*args, **kw)`, and the CLI is exactly `build_packet.main(argv)`.
- No byte of output comes from this wrapper. `packet_writer_sha256` therefore still names the frozen `packets.py`.

**`support_mask` given:**
- **Shape.** A boolean array `[H, W]` on the packet grid (the window when the packet is regional), in native
  **north-up** row order, the same order as `constructed_arrays.npz`. `True` = supported. A static mask only (see
  "Not covered").
- **Order of work.**
  1. The frozen writer writes the packet first, all-true support, with its own validation.
  2. The wrapper then rewrites only the support channel:
     - `HAZARD.json` members' `support[k]`: the mask flipped to south-up, row 0 = south, for **every** member and
       every bin;
     - `constructed_arrays.npz` `support`: the mask broadcast to `[S, H, W]`.
- **Unchanged:** scenario ids, breakpoints, flame, flux, every other array, and the construction assumptions.
- **Distinct writer identity.** In `HAZARD.json` `provenance.identity`, `REPORT.json` and `NATIVE_METADATA.json`
  `identity`:
  - `packet_writer_sha256` becomes the sha256 of `packets_f93.py`;
  - `base_packet_writer_sha256` keeps the frozen writer's hash;
  - `support_writer` = `{version: "wfg.f93.support-writer/1", rule, support_mask_sha256, unsupported_cells,
    provenance}`.

  `provenance.flame_semantics` is unchanged. A `support_semantics` string is added to the provenance. A masked packet
  therefore can never be read as a v1 packet.
- **Scenario ids are kept on purpose.** The members are the same realizations: identical flame and flux. The
  optimistic packet (v1, all-true) and the masked packet must be comparable member by member, with the same
  `incurred` and `dose` keys. The writer identity, not the id, distinguishes them.
- `BUILD_SUMMARY` / summary `files_sha256` are recomputed. The writer's original hashes are kept as
  `files_sha256_as_written_by_base`.

## What counts as unknown (support = false)

Unknown means **the source says nothing about this cell**. It is **not** "no fire". It applies only to cells of the
packet grid.

1. **c651 forecast packets, rule `c651_unknown/1`.** The mask is derived from the packet's own
   `constructed_arrays.npz`, as written by the frozen writer, in native north-up order (Iris's flags, F-9.3
   DESIGN.md §"Unknown cells" item 4):
   - `U_state = mask__unknown_cumulative_state`: burned state unknown, with no reconstructed arrival;
   - `U_q = mask__policy_assigned_zero & ~mask__known_burned & ~U_state`: the native probability is missing and
     q = 0 was assigned by policy;
   - `support = ~(U_state | U_q)`.
2. **Arrival rasters (F-DYN reconstructions).**
   - Cells inside the mapped grid but outside the final perimeter are **observed no-fire**, so they are supported.
   - Cells outside the mapped grid are unknown. They are not on the F-DYN full grid, so the mask is all-true there.
3. **Perimeter sequences.**
   - Cells outside the product's declared domain (or outside P_n when no domain is declared) are unknown.
   - Inside the domain, cells in no polygon are no-fire up to t_n and unknown after it. A static mask can express
     this only when t_n ≥ the packet horizon. Otherwise the build **refuses** (`SUPPORT_TIME_DEPENDENT`).
4. **Supplied masks, rule `supplied/1`.** Any other mask is accepted only with a non-empty `support_provenance`
   saying where it came from. It is recorded verbatim.

## Hard conditions: the build fails on any of them

- **No conflict with asserted fire.** support = false is never written on a cell the packet itself asserts fire on.
  Such a cell is one with:
  - flame in any member and any bin; or
  - present fire (`current_active`); or
  - a finite ignition time in any member.

  Any overlap raises `SUPPORT_CONFLICT` with the count. The mask is never altered to make the build pass.
- **The masked hazard passes the router's own validator** (`validate_hazard`, as vendored by the build).
- **Self-check:**
  - support in HAZARD equals the flipped mask in every member and bin;
  - the npz `support` equals the broadcast mask;
  - HAZARD ids, breakpoints, flame and flux are equal to the base output, parsed and compared exactly;
  - every npz array except `support` is equal in dtype, shape and values;
  - REPORT assumptions are unchanged.
- **Array-law consistency** (F-DYN `PACKET_CONSISTENCY_RULE.md` §C): the array path and HAZARD express the same law.
  The check is inlined (it mirrors `F-DYN/fdyn/consistency.py`) and runs on the masked packet; it must pass.
- **Shape and dtype:** a mask whose shape is not `[H, W]` or that is not boolean is refused (`SUPPORT_SHAPE`).

## What the router does with it (read from `routing-package/routing`, unchanged)

- A route that occupies an unsupported cell, at any sampled time, gets `UNSUPPORTED` from the checker
  (`core.py`, `independent.py`). The route is not checked.
- Any false entry anywhere withholds the **global** optimality and infeasibility claims (`_globally_supported`).
- Under Iris's three-way rule, the masked packet is therefore the router-native form of the **pessimistic, tier A
  (strict)** instance. A route through an unknown cell cannot be "checked". "no-route" still comes only from the
  optimistic (v1) packet. The router itself also refuses to claim infeasibility on the masked packet.
- **Tier B (speed-bounded, time-dependent) is not expressible** with a static mask.

## Regression (acceptance)

1. **Mask unused.** Every recorded c651 packet whose export is present here is built twice, in the same environment:
   with the frozen `build_packet.py` and with `build_packet_f93.py` without a mask.
   - Required equal: `HAZARD.json`, `REPORT.json` and `NATIVE_METADATA.json` byte for byte; `constructed_arrays.npz`
     array for array (names, dtype, shape, bytes); `BUILD_SUMMARY.json` except `hazard_construction_wall_s`.
   - Why the npz is compared by array, not raw bytes: `np.savez_compressed` stamps the zip member time, so two builds
     of the frozen writer are not byte-identical either. This is checked and reported.
   - The count of packets is stated, and so is any packet that cannot be rebuilt.
2. **Mask unused, against the frozen stored packets.** The F-9.3 comparison rule: ids, breakpoints, flame and support
   exact; flux within relative 1e-9. The numpy and scipy versions are recorded.
3. **Mask used (`c651_unknown/1`)** on the same packets:
   - all hard conditions hold;
   - unsupported cell counts per packet are reported;
   - the router validator accepts the result;
   - writer identity differs from v1;
   - the array-law check passes.
4. **Refusals:** shape, dtype, conflict and missing provenance each raise their error. A test proves it.

## Not covered (stated)

- Time-dependent support (tier B; perimeter sequences ending before the horizon) and per-member support.
- Wiring into the F-DYN child and the F-9.3 interface `build()`. That is on PR #105, after Hannah's verdict.
- Option C (the per-cell law in the writer and the independent checker).
- Richard's and Thomas's tools keep applying the three-way rule downstream until Hannah passes this.
