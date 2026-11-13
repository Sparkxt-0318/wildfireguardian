# Support-aware READ path for `PacketModel` (rule; committed before tests and code)

- **Source.** Orchestrator decision, 13 Nov 08:27 UTC, option A. The widened-graph pre-build test failed at F-DYN
  56814382 (`results/WIDENED_PRETEST_PACKETMODEL.json`).
  - `PacketModel` at 969a2ca2 refuses an F-9.3 support-masked packet with
    "PacketError: npz contract violated (current/support/events)".
  - The refusal comes from the replay `Packet` reader's all-true-support contract.
- **Not chosen.**
  - Option B (write all-true support): checkers could then certify padded packets.
  - The untested HAZARD-only path.

## What changes

1. **Which packets get the new path.** `deadline_field.real.load_packet` gains one path, used only when **both** hold:
   - (a) `constructed_arrays.npz` `support` is not all true;
   - (b) the packet declares an F-9.3 support mask: the F-9.3 writer identity (`support_writer`) is present in
     the packet's recorded identity (HAZARD provenance or BUILD_SUMMARY writer_identity), the recorded support rule
     is `supplied/1`, and no `SUPPORT_WRITE_FAILED` marker exists. The marker is refused already. The exact keys
     are fixed in the test, against the pre-test's masked packet, before the code is written.

   A packet with (a) but not (b) is still refused with the reader's own error.
2. **What the path does.** It runs every check of the replay `Packet` reader unchanged, except the single clause
   `not sup.all()`. Those checks are: HAZARD schema, grid, dt, window, affine/CRS, member order, npz shape, current
   cells, finite or NaN events, and the flame-bins-equal-phases consistency check.
   - The tools reader is **not modified**.
   - The path is a separate function in `real.py` and is marked as such.
3. **Support-false cells are recorded on the packet:**
   - `pk.support_masked = True`;
   - `pk.support_false_cells`: router cells, via the reader's own `native_to_router`.
   - `PacketModel` exposes both.
4. **Contact rules ignore support.**
   - Closed and router phases, blocked starts, waits, issue points and dwells are computed exactly as now, from the
     phases.
   - Support is **not** turned into closure here. Padding closure stays the job of `extra_blocks`
     (WIDENED_GRAPH_RULE padding-closed arm).
5. **Checker refusals stay (WIDENED_GRAPH_RULE P5).**
   - `deadline_field.verify.full_check` on a `PacketModel` whose packet is support-masked does **not** run the
     checkers. It returns `full_policy_ok = False`, `full_status = "REFUSED_SUPPORT_MASKED"`,
     `closed_and_router_replay_clear = None`. So no witness on a masked packet can be reported as checked.
   - The tools `Packet` reader, the kit's `check_route` / `exhaustive` support handling and the F-3.2 readers are
     unchanged.

## Tests (committed with the code; all must pass before any padded build)

- **T1, regression.** Every unmasked packet loads and routes byte-identically. On the HEADLINE pairs the independent
  verifier re-ran (UA 25T17Z h5 kriged_mean and firms_early, `/2` and reopening), the new code and 969a2ca2 must agree
  on:
  - per-cell phases, `B["router"]`, `B["closed"]`, and `instance(...)` W/A/IB for every destination;
  - per-place CERT and ROUTER issue sets.

  Compared on the built packets; equality is exact.
- **T2, masked loads.** The F-9.3 masked twin of an unmasked packet loads.
  - Its phases, B, W, A and IB are identical to the unmasked twin's.
  - `support_false_cells` equals the mask's false cells, mapped to router cells.
- **T3, refusals remain.**
  - (a) The tools `Packet` reader still raises on the masked packet.
  - (b) `full_check` on the masked `PacketModel` returns `REFUSED_SUPPORT_MASKED` and does not call the checkers.
  - (c) A packet with support not all true but **no** F-9.3 declaration is still refused by `load_packet`.
  - (d) The kit's `check_route` on the masked HAZARD does not return ok for a route occupying a support-false cell
    (one constructed route). Asserted as the kit's own behaviour, unchanged.
- **T4, the existing suite** passes unchanged (15/15 on the working branch).

## Inputs for T2 and T3

- **The F-9.3 masked packet** is built by Leo's builder (`--support-mask`, `--support-rule supplied/1`,
  `--support-provenance`), following the F-DYN pre-test (UA 25T17Z, 5,068 support-false cells).
- **Its unmasked twin** is the same manifest command without the mask.
- Both are built in scratch. Their npz sha256 values are recorded in the test output and compared with the pre-test
  file's (`d581ba92…` unmasked, `39140349…` masked).

## Verification

The independent verifier checks T1–T4 and the code diff before the F-DYN builder builds any padded packet.

## Amendment 1 (committed before tests and code): test inputs, and the c651 rule

- **Test inputs.** These are the pre-test pair from the F-DYN builder (13 Nov, 08:30 UTC), built from the repo root
  with `python3 -I -B`. All use UA 25T17Z on the recorded window.
  - A, unmasked: `integration/src/wfg_latest/build_packet.py`, npz `d581ba92…`.
  - D, masked, F-9.3 `supplied/1`: `research/harness-2026-11/F-9.3/support_mask/build_packet_f93.py` with
    `--support-rule supplied/1`. The mask is C's `support[0]` (recorded `support_mask_sha256` `a0353243…`). npz
    `39140349…`.
  - C, the same mask declared `c651_unknown/1`, npz `39140349…`.
- **Regression pairs (T1).** These are the HEADLINE `/2` and reopening pairs, UA 25T17Z h5 kriged_mean and
  firms_early, as in the rule.
- **`c651_unknown/1` stays refused.** The new path admits `supplied/1` only. Nothing in the widened work needs
  `c651_unknown/1`. T3 gets a case:
  - (e) C (`c651_unknown/1`, the same npz as D) is still refused by `load_packet`.
- **Which packet is "masked".** The packet with the declared mask, D, must give phases, B, W, A and IB identical to
  A's (T2). `support_false_cells` must be the router image of the false cells of D's npz `support`; D has 1,267 cells
  false in each of the 4 members.
