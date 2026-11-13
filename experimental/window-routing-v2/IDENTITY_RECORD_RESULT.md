# Identity record: result (kit `0fffb589…`; acceptance and its amendment in IDENTITY_RECORD_ACCEPTANCE.md)

All measured on one host, alone, with no restart.

**History.**
- First version: c7f893e5, kit bd67ff9d, 4 lines. It passed verification (ledger 134). Its results are kept as
  `results/identity_record/superseded_bd67ff9d_*`.
- The certificates review then raised the checker-module override.
- Measured: the kit's queue job sets `checker_module: adaptive_checker`, so every job runs the override path.
  `adaptive_checker.HybridChecker` subclasses the recorded `hybrid_checker`.
- Two record-only lines were added: `checker_module_override` and `checker_class_mro`. Their amendment was committed
  before the code. This is the current kit, 0fffb589.

| Acceptance line | Result on 0fffb589 |
|---|---|
| Pre-stated test (a) | **pass.** It checks three things: the recorded hashes equal the manifest; the override equals the queue's `checker_module` and `RESULT.checker_module.module`, and the MRO contains it and `hybrid_checker`; every non-builtins module in the MRO is hashed in `checker_identity` or among the override's pinned files (the reviewer's tightening) |
| Pre-stated test (b), a modified scratch copy records its own hash | **pass.** Both tests fail on 192f15cc, which has no record |
| Pins | 6 identity-record worker lines, pinned exactly; all earlier pins pass; seal recomputed (11 files) |
| Full suite + parent runner | **83 passed + 3 skipped**; parent runner ok |
| **G1 panel**, frozen vs 0fffb589, 20 missions × 2 reps, 81 s, 05:19:23–05:48 UTC | **G1 20/20, G3 20/20**. Memory-mapped statuses 0/0. 28 checks within budget, largest 487.5 MiB |
| Record on every V2 row | **40/40**: three hashes equal the manifest; override `adaptive_checker`; MRO `[adaptive_checker, hybrid_checker, builtins]` |
| Reported, not gated | G5 wall 0.895. M1 max 1,545.2 MiB, 0 unmeasured samples. Step 1 reason changes as on 192f15cc |

## Limits (stated in the acceptance, not fixed)
- The hash is of the `.py` file at record time, not of the bytes Python loaded (stale `.pyc`, or an edit after
  import). Kit runs use `-B` and `PYTHONDONTWRITEBYTECODE=1`.
- Pre-existing, and not this change: in the Step 2 block, `_v2_hc.RSS_LIMIT_MB` is read from the default
  `hybrid_checker`. Under this kit's override that is the base class's module, so the value is the base class's gate.
