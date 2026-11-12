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

## Not covered (DESIGN.md)

- Time-dependent support (tier B; perimeter sequences ending before the horizon) and per-member support.
- Wiring into the F-DYN child and the F-9.3 `build()`. That happens on PR #105 after the verdict.
- Option C.
- Richard's and Thomas's tools keep the three-way rule downstream until Hannah passes this.
