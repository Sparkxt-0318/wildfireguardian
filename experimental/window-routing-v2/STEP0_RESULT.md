# Step 0 result (scaffold): PASS on every criterion of STEP0_ACCEPTANCE.md (840caf3)

**Run.** 12 Nov 2026, 15:14–15:43 UTC, this host.
- 20 missions × 2 reps, frozen request-window kit and v2 (`kit-v2-step0`, manifest `b37e0c79…`) interleaved per
  mission, plain mode, 81 s.
- Data: `results/step0/` (ROWS.jsonl.gz, G1_COMPARE.{json,txt}, G2.jsonl, G2B.json, KIT_IDENTITY.json).

| Criterion | Result |
|---|---|
| **G1** (19 identical sets + FL2 rule) | **20/20 identical** (FL2: FEASIBLE@1922 in both kits, both reps) |
| UNRESOLVED → certified changes (expected 0) | **0** |
| **G2** (both checkers, fresh processes) | **28/28** v2-published routes: whole-road CERTIFIED_ADMISSIBLE and independent ok |
| **G2b** (Thomas, `thomas/routing-next` @ e3cc617) | 39 run folders: **38 PASS, 1 NOT_APPLICABLE_STATUS, 0 violations** (see note) |
| **G3** (shares within 1e-4) | 20/20 |
| **G5** (wall ≤ +10%; memory ≤ +10% and ≤ 3,072 MiB) | summed median wall ratio **1.007**; memory within limits on 20/20 |
| kit_identity | present in **40/40** V2 RESULTs and in 0/40 FROZEN RESULTs |

**Tests.**
- `tests/test_build_v2.py`: 10/10.
- Parent tests on v2: 31/32. The one failure is `test_18`, provenance against the parent seal; it differs exactly
  on the overlay file, which `run_parent_tests.py` checks.

**Note on G2b.**
- **Folder excluded:** `V2/r1/yeongdeok 0325T19 FX2`. That run was stopped at the deadline: UNRESOLVED, RESULT written
  by the worker's failure path, with no `RESULT.decision`. The frozen kit does the same.
- **Why:** on that folder `g2b.py` falls back to `decision_from_worker_record(..., graph=...)`, a signature that
  `decision/journey_decision.py` does not accept (TypeError). It was reported to Thomas.
- **Effect:** an UNRESOLVED decision carries no route and no refusal claim, so G2b has nothing to test there.
- **Rep 2 of FX2** was included: it has RESULT.decision and its verdict is NOT_APPLICABLE_STATUS.
