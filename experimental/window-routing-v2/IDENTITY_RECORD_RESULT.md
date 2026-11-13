# Identity record: result (kit `bd67ff9d…`; acceptance in IDENTITY_RECORD_ACCEPTANCE.md, committed before code)

All measured on one host, alone, with no restart.

| Acceptance line | Result |
|---|---|
| Pre-stated test (a): recorded hashes equal the manifest | **pass** on bd67ff9d. It **fails** on 192f15cc, which has no record, so the test discriminates |
| Pre-stated test (b): a modified `contact_first.py` in a scratch kit records its own hash; the other two equal the manifest | **pass** on bd67ff9d; fails on 192f15cc |
| Pins | `test_build_v2` pins the 4 identity-record worker lines exactly. All earlier pins pass. Seal recomputed (11 files) |
| Full suite + parent runner | **83 passed + 3 skipped** (81 earlier + 2 new); parent runner ok (`results/identity_record/SUITE.txt`) |
| **G1 panel**, frozen vs bd67ff9d, 20 missions × 2 reps, 81 s, 04:31:52–05:00 UTC | **G1 20/20, G3 20/20**. Memory-mapped statuses 0/0. 28 checks, all within budget, largest 487.6 MiB |
| `checker_identity` on every V2 row | **40/40 V2 runs** carry it, and all three hashes equal the manifest in all 40 (`results/identity_record/V2_CHECKER_IDENTITY.jsonl`) |
| Reported, not gated | G5 wall 0.898. M1 max 1,551.3 MiB, 0 unmeasured samples. Step 1 reason changes as on 192f15cc (FX2 LATE_RESULT → SEARCH_TIMEOUT; FL2 no LATE_RESULT) |

The verdicts are those of 192f15cc's panel. FL2 is OPTIMUM@1922 on both V2 reps, and FROZEN is FEASIBLE@1922 or
UNRESOLVED.

## Ideas and gaps
- The record reads `sys.modules[...].__file__` after import. A module loaded from a zip or a frozen importer has no
  file to hash, and is recorded as `imported: false`. That never happens in this kit.
