# Step 0 acceptance (scaffold): written and committed BEFORE the Step 0 panel run

**What Step 0 changes.**
- The overlay is exactly one file: `phaseB/rda_worker_v1_1.py`. It is the parent file plus 3 lines that write
  `kit_identity` (read from the kit's `KIT_IDENTITY.json`) into the worker's STATE.
- No search, check, decision or publication logic changes.

**Kit.** Built by `build_kit_v2.py --parent <request-window kit> --out <scratch>/kit-v2-step0`.
Manifest sha `b37e0c79…`, 62 files, `candidate_id` `WFG-request-window-routing-v2-20261112`.

**Tests already run (before this file):**
- `tests/test_build_v2.py`: 10/10 pass. It covers identity, that only declared files differ, that the manifest
  matches, that queue hashes point at the v2 worker, that the parent is unchanged, and that the builder refuses an
  existing output, frozen or parent paths, and a changed parent.
- `tests/run_parent_tests.py`: the parent's 32 tests, byte-unchanged, run on the v2 kit. 31 pass. The one failure is
  `test_18`, a provenance test comparing the stack to the PARENT's sealed hashes. The only differing file is the
  overlay file, as the runner checks mechanically.

**Panel.** `tools/g1_panel.py`: 20 missions × 2 reps, FROZEN (request-window kit) and V2 interleaved per mission,
plain mode, 81 s, this host. Evaluated with `tools/g1_compare.py`; G2 by `tools/g2_recheck.py` on every V2-published
route.

**Acceptance. Step 0 passes iff all of the following hold.**
- **G1.** Identical (status, arrival) sets on the 19 missions other than Yeongdeok 0325T23 FL2, and FL2 within
  {UNRESOLVED, FEASIBLE@1922, OPTIMUM_PROVEN@1922}.
  - PLAN §2 said "all 20 sets identical" for Step 0. FL2 is cap-sensitive between runs of the same kit, so the FL2 rule
    applies here as in G1. This clarification is made before the run.
- **Expected count of UNRESOLVED → certified changes: 0.** Any such change fails Step 0, since the scaffold changes no
  logic.
- **G2.** 100% of V2-published routes are accepted by both the unchanged whole-road checker and `routing.independent`,
  each in a fresh process.
- **G2b.** Applied once Thomas's script exists; reported separately, not blocking Step 0.
- **G3.** Shares within 1e-4.
- **G5.** Summed median wall V2/FROZEN ≤ 1.10. Per-mission peak memory ≤ +10% and ≤ 3,072 MiB.
- **kit_identity.** Present in every V2 RESULT.json and absent (null) in every FROZEN one.
