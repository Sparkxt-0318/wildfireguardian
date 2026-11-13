# Identity record: checker module hashes (acceptance, written before code)

Source: PLAN.md "Identity record, future steps". It was stated by the certificates reviewer, and the test was stated
before code.

## What changes
The worker's per-job identity record (RESULT `checker_identity`) carries, for each of `contact_first`,
`mission_contract` and `hybrid_checker`:
- the module's `__file__`, as imported (read from `sys.modules` right after the worker's own
  `from hybrid_checker import HybridChecker` and `from mission_contract import graph_digest`);
- the sha256 of that file.

This is recording only:
- no import, call, argument or decision changes;
- the new lines carry the marker `# kit-v2 identity record` and are pinned exactly in `tests/test_build_v2.py`, like
  every earlier step's lines.

If a module is not in `sys.modules` at that point, its entry is `{"imported": false}`. A missing entry is never
silently skipped.

## Tests (all must pass)
1. **Pre-stated test (a):** a job run on the built kit records, for all three modules, a path inside the kit and a
   sha256 equal to the kit manifest's entry for that file.
2. **Pre-stated test (b):** a scratch copy of the kit with one module deliberately modified (a comment line appended to
   `contact_first.py`) records that module's **own** hash. That hash differs from the manifest's entry and equals the
   sha256 of the modified file. The other two modules still equal the manifest.
3. **Pins:** `test_build_v2` pins the identity-record worker lines exactly. All earlier steps' pins are unchanged and
   still pass. Overlay seal recomputed.
4. **Full suite** on the new kit, plus the parent runner.

## Verdict identity (the change is recording only, and this is shown, not assumed)
- G1 panel: the frozen kit against the new kit, 20 missions × 2 reps, 81 s, alone on the host, tracked, restarts
  logged.
- **G1 20/20, G3 20/20**, memory-mapped statuses 0/0.
- Every V2 row carries `checker_identity` with the three hashes equal to the manifest.
- Wall and memory are reported, not gated: the change adds three file hashes per job.

## Not in scope
Any change to which module is imported, or to how it is loaded. Any other identity fields.
