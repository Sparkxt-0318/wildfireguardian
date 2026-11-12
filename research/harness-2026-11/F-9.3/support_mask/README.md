# F-9.3 support_mask: versioned writer wrapper `wfg.f93.support-writer/1`

- **Design and unknown rule:** `DESIGN.md`, committed before any code at f780cb13, plus correction 1.
- **Code:**
  - `packets_f93.py`: the wrapper;
  - `build_packet_f93.py`: the CLI;
  - `regress.py`: the acceptance run;
  - `test_support_mask.py`: the unit tests.
- **Not touched:** the frozen writer files `integration/src/wfg_latest/packets.py` (sha256 `6b922418…`) and
  `bridge.py` (`f7466e64…`). Nothing under `integration/`, `routing-package/`, `api/` or `routing-api/` changed.

## What it does

- **Without a mask:** `support_mask=None`, or the CLI without `--support-rule`. This is a complete hand-off to the
  frozen writer and CLI.
- **With a mask:**
  - the frozen writer writes the packet first;
  - then only the support channel is rewritten, in HAZARD (south-up) and in the npz `support` (north-up);
  - the packet gets a distinct writer identity: `packet_writer_sha256` = this wrapper, `base_packet_writer_sha256`
    = the frozen writer, and `support_writer {version, rule, mask sha256, counts, provenance}` in HAZARD, REPORT and
    NATIVE_METADATA;
  - scenario ids, breakpoints, flame, flux and every other array are unchanged;
  - the router's validator and the array-law consistency check run on the result.
- **Rules:**
  - `c651_unknown/1`: support = ~(U_state | U_q), from the packet's own masks;
  - `supplied/1`: an explicit mask, which must come with provenance.
- **Refusals:** shape or dtype, a conflict with asserted fire (flame, present fire or ignition), a missing
  provenance, and a rule/mask mismatch.

## Results

Acceptance run (`regress.py`): **15 of 15 recorded c651 packets rebuilt; none are missing an export.** Two
environments were used, Linux x86_64 in both:

| Check (DESIGN.md §Regression) | numpy 2.5.3 / Py 3.13 (`REGRESSION_numpy2.5.3.json`) | numpy 1.26.4 (pinned) / Py 3.12 (`REGRESSION_numpy1.26.4.json`) |
|---|---|---|
| 1. Wrapper without a mask (B) vs frozen CLI (A): HAZARD, REPORT, NATIVE_METADATA bytes | 15 / 15 identical | 15 / 15 identical |
| 1. B vs A: npz array for array; also raw npz bytes | 15 / 15; 15 / 15 | 15 / 15; 15 / 15 |
| 1. B vs A: BUILD_SUMMARY except wall time, out_dir and npz hash | 15 / 15 | 15 / 15 |
| 1. B's `packet_writer_sha256` = frozen `packets.py` | 15 / 15 | 15 / 15 |
| Frozen rebuild A2 vs A: npz bytes | 15 / 15 identical (correction 1) | 15 / 15 |
| 3. Masked (C, `c651_unknown/1`): every hard condition, validator, array law, distinct identity | 15 / 15 pass | 15 / 15 pass |
| 2. Frozen writer rebuild (A) vs the stored frozen packets (macOS build): ids, breakpoints, flame, support exact; flux relative ≤ 1e-9 | **14 / 15**; Uiseong 03-24 09Z fails | **14 / 15**; same packet fails |

**The one failure (item 2) is the frozen writer itself, across platforms. It is not the wrapper.**
- On Uiseong 03-24 09Z, the frozen writer's own rebuild differs from the stored macOS-built packet:
  - relative flux difference up to 4.1e-9 (numpy 2.5.3) or 2.3e-9 (numpy 1.26.4), against the rule's 1e-9;
  - 14 and 6 flux entries respectively;
  - every one of them is at a flux of at most 5.9e-8 kW/m², and the absolute difference is at most 4.4e-16 kW/m².
- Ids, breakpoints, flame and support are exact on all 15 packets.
- The 1e-9 relative rule is reported as **failed** for this packet. The tolerance has not been changed. Whether the
  cross-environment rule needs an absolute floor for near-zero flux is a question for the verifier and the
  orchestrator, not something to change after the run.
- The wrapper's own claims (items 1 and 3) do not depend on it: B and C are compared with A built in the same
  environment.

**Both flux rules, side by side.** Amendment A1 is in DESIGN.md: post hoc, proposed, committed at 7e8420ea before
this evaluation.
- No packet was rebuilt. `amended_rule.py` re-reads the A builds; output in `AMENDED_RULE_RESULTS.json`.
- **Run-time verdict kept.** The existing rule (relative ≤ 1e-9) was the rule in force at run time, so the
  Uiseong 03-24 09Z FAIL stays recorded under it.
- **A1 adopted going forward.** Hannah PASS WITH NOTES, ledger row 37; she reproduced 14/15 and 15/15 on her own
  numpy 1.26.4 and 2.5.4 builds.

| Rule | numpy 2.5.3 / Py 3.13 | numpy 1.26.4 / Py 3.12 |
|---|---|---|
| Existing: flux relative ≤ 1e-9 | 14 / 15 (Uiseong 03-24 09Z FAIL: 14 entries) | 14 / 15 (same packet FAIL: 6 entries) |
| A1 (proposed): relative ≤ 1e-9 **or** absolute ≤ 1e-12 kW/m² | 15 / 15 (0 entries fail) | 15 / 15 (0 entries fail) |

- **Across all 15 packets,** the largest absolute flux difference is 1.1e-15 kW/m², in Yeongdeok 03-25 19Z
  (numpy 2.5.3).
- **Ids, breakpoints, flame and support** are exact on all 15 packets in both environments.
- **Writer identity** is recorded per compared instance, both built and stored. That is the orchestrator's condition
  for keeping the scenario ids.

**Unsupported cells under `c651_unknown/1`** (of the packet window's cells; the same in both environments):

| Packet | Unsupported | Cells |
|---|---|---|
| Hongseong 04-02 07Z / 14Z / 23Z | 269 / 247 / 214 | 324 |
| Miryang 05-31 10Z, 06-01 02Z / 08Z | 175 / 153 / 142 | 187 |
| Uiseong 03-23 01Z, 03-24 09Z, 03-25 17Z | 1,582 / 1,491 / 1,267 | 4,745 |
| Uljin 03-04 03Z / 06Z / 12Z | 2,529 / 2,529 / 2,527 | 3,596 |
| Yeongdeok 03-25 19Z / 23Z, 03-26 08Z | 2,885 / 2,735 / 2,599 | 4,757 |

- Yeongdeok 03-25 19Z: 2,885 = U_state 2,570 + U_q 315, the counts in F-9.3 DESIGN.md.
- No packet had a conflict between unknown and asserted fire.

**Unit tests:** `python3 -m pytest -q research/harness-2026-11/F-9.3/support_mask`, 10 pass. They cover:
- the hand-off is exact;
- six refusals happen before the frozen writer runs;
- the rule on a recorded packet;
- a conflict and a wrong-shape mask are refused with nothing rewritten.

The data-dependent tests skip when `data/routing` is absent; it is not in git.

## Reproduce

```
python3 research/harness-2026-11/F-9.3/support_mask/regress.py --work WORKDIR --out REGRESSION.json
```

- About 1 minute per packet for its 4 builds (62 s measured on Yeongdeok 03-25 19Z).
- Inputs: `data/routing/latest_inputs_try02` and `data/routing/graphs`, which are local data and not in git.

## Consumer rules (Hannah, ledger row 36)

1. **Writer identity in every key.** Masked packets keep the v1 scenario ids. Any cache, comparison or downstream
   key must therefore include `packet_writer_sha256`, or `support_writer` when present. Every tool that compares
   instances prints the writer identity. Thomas's `p1_check.writer_identity` does this on `routing-next`, and Richard
   will once he uses masked packets.
2. **Refuse failed or incomplete builds.** Refuse any packet directory that holds `SUPPORT_WRITE_FAILED`, or has no
   `BUILD_SUMMARY.json`.
   - When a masked build fails a hard condition (for example `SUPPORT_CONFLICT`), the directory still holds the frozen
     writer's unmodified v1-identity files plus that marker.
   - The marker is written before the error is raised. The CLI writes `BUILD_SUMMARY.json` only after success.

## Implemented vs design-only

- **Implemented:**
  - `c651_unknown/1` (DESIGN.md unknown rule 1);
  - `supplied/1` (rule 4).
- **Design-only, not implemented here:**
  - rule 2, arrival rasters (F-DYN);
  - rule 3, perimeter sequences, including the `SUPPORT_TIME_DEPENDENT` refusal.

  An adapter for either would produce a `supplied/1` mask with provenance, or a new named rule. That needs its own
  rule entry and verification.
- **CLI validation (after Hannah's note 1).** The CLI validates `--support-rule` and its arguments **before** any
  build:
  - an unknown rule gives `SUPPORT_RULE_UNKNOWN`;
  - `supplied/1` without a mask file or provenance gives `SUPPORT_PROVENANCE_MISSING`;
  - `c651_unknown/1` with a mask file or provenance gives `SUPPORT_RULE_MISMATCH`.

  Before this fix an unknown rule crashed with a TypeError: it still failed closed, but late. The no-mask hand-off
  path is unchanged. Unit tests: 13 pass.

## Not covered (DESIGN.md)

- Time-dependent support (tier B; perimeter sequences ending before the horizon) and per-member support.
- Wiring into the F-DYN child and the F-9.3 `build()`. That happens on PR #105 after the verdict.
- Option C.
- Richard's and Thomas's tools keep the three-way rule downstream until Hannah passes this.

## Rerun on the current CLI (after Hannah's note 1)

**Result:** every wrapper check passes on the current code (`REGRESSION_numpy2.5.3_v2.json`).
- **Code.** `build_packet_f93.py` is now sha256 `01a3012f…`. `packets_f93.py` is unchanged (`befd94bc…`).
- **Run.** `regress.py` was rerun under numpy 2.5.3 / Py 3.13, rebuilding all 15 packets.
- **Item 1 (mask unused):** 15/15 byte-identical to the frozen CLI. This covers the HAZARD, REPORT and NATIVE_METADATA
  bytes, the npz arrays and bytes, and BUILD_SUMMARY except wall time; the writer identity is still the frozen one.
- **Item 3 (masked):** 15/15 pass, with the same unsupported counts as the first run.
- **Item 2:** unchanged. Uiseong 03-24 09Z fails the existing rule, which was in force at run time, and passes A1.
  That is why `all_ok` is false in the file.
- The earlier `REGRESSION_numpy*.json` files are kept. They record `build_packet_f93.py` `24f918cc…`.
