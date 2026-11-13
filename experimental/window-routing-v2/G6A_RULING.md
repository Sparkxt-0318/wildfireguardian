# G6a ruling and the checks that follow it (written before the added check runs, and before G6b)

Orchestrator ruling, 2026-11-13 12:23Z: option (b), which includes (a).

## (a) G6a result wording
G6a is recorded as **FAIL AS WRITTEN on the 17 jobs**, in those words, at the top of the result.
- The pre-stated "wall cap" definition (G6A_RUN.md: deadline termination with reason TIMEOUT) is not reinterpreted
  after the run.
- The facts are reported beside it: V2 vs RECORD, the direction of all differences, and their PARENT stop reasons.

## (1) Amended definition, for G6b only (prospective, not applied to G6a; revised to the assessor's criteria before any check ran)
- **Time-capped: a closed list, read from PARENT's own output.** A PARENT run is time-capped only if
  `outcome.verdict == unresolved`, `outcome.reason_code == TIMEOUT`, and `outcome.raw_reason` is one of:
  - `LATE_RESULT`: deadline termination (`api.verdict.classify`, LATE/no publication branch);
  - `DEADLINE_STOP`: deadline termination without a decision reason (classify's deadline branch);
  - `SEARCH_TIMEOUT`: the PARENT solver's own time-based search cap.

  No other code counts, and the list is not extended after a run. In G6a, PARENT's time-capped stops were only
  `LATE_RESULT` (with deadline termination) and `SEARCH_TIMEOUT`.
- **A V2 ≠ PARENT difference is allowed only if ALL of these hold:**
  1. PARENT is time-capped (closed list above) in **every** PARENT run of that job;
  2. V2's final outcome is a checked route;
  3. **V2 finished inside the job limit a kit user has:** the same 81 s complete budget, with on-time publication
     (receipt `on_time_complete_publication` true, and `complete_wall_s` ≤ 81). V2's wall time is reported beside the
     cap PARENT stopped at (its deadline, or its SEARCH_TIMEOUT time). A V2 route that needed more time is listed
     separately as "resolved only with more time" and is **not** allowed;
  4. the V2 route contradicts neither the RECORD, the router field (`JOBS_1h_crossref.json` @ 5389803e: router
     feasibility and arrival) nor a certificate (`TIMEOUT_NO_ROUTE_CERTS_1h.json` @ c0e34d4);
  5. it passes the added route check (2) below.
- **Status claimed.** An allowed difference is counted as a **checked route**. V2's optimality claim
  (FULL_OPTIMUM_PROVEN) is reported as **verified** only if (2c) independently confirms it. Otherwise it is reported as
  "optimality claimed, not independently verified".
- **These stay failures, explicitly:**
  - PARENT route or refusal → V2 UNRESOLVED;
  - PARENT UNRESOLVED for a reason not on the closed list (a memory gate, a worker error, a cleanup failure, an
    at-issue failure, a state cap);
  - PARENT UNRESOLVED → V2 refusal;
  - any refusal ↔ route change;
  - any change of arrival where both have a route.
  - A change of legs at equal arrival stays an "equal-arrival tie", listed as G6_RULE allows, and is never folded
    into the allowed differences.
- **Counting.** G6b reports allowed differences as their **own count**, beside the unchanged count and the failures,
  never folded into "pass", with a per-stratum and per-input (region, start) breakdown. A concentration is stated: in
  G6a, all 64 differences are Yeongdeok TIMEOUT-stratum, 62 of them from 0325T19.
- **Reviews before G6b runs:** the assessor judges whether this definition can hide a real regression, and the
  verifier reads it.

## (2) Added check on every new V2 route (rule fixed here; run after this file is committed)
**Jobs:** every job where the final V2 outcome (after the R rerun) is a checked route and PARENT is UNRESOLVED in a
PARENT run. The first comparison has 64 such jobs. The exact list is written by the comparison before the check
runs.

For each job:
- **(2a) Full checker, independently.** The published V2 route is re-checked in a fresh interpreter, by both frozen
  checkers: the frozen kit's whole-road HybridChecker (status must be CERTIFIED_ADMISSIBLE), and the routing package's
  independent checker (ok, no codes). Tool: `tools/g2_recheck.py`, with the frozen kit's checkers.
  - Run by the author, and independently on the verifier's own build.
- **(2b) Not earlier than the router field's optimum.** V2 arrival_s ≥ `router.arrival` for that job in
  `JOBS_1h_crossref.json` @ 5389803e (sha256 prefix e3e1acae).
  - The router field is the kit's own contact rule, solved as a field, so no admissible route can arrive earlier.
  - `router.feasible` must be true. A V2 route on a job the router field calls infeasible is a contradiction and a
    failure.
  - Equality and strict inequality are both reported, with the count of each. `cert.arrival` is reported beside it,
    not judged.
- **(2c) Optimality, independently (assessor criterion 2).** For each route claimed FULL_OPTIMUM_PROVEN, the
  certificates reviewer's `xcheck/g2b.py` @ deeb7c2 (relaxation optimum on the job's own instance) must give PASS
  ("attains the relaxation optimum"). A job without PASS keeps "optimality claimed, not independently verified".
  That is reported, but it does not fail (2), because (2) is about the route's soundness.
- **(2d) Time.** V2's `complete_wall_s` and on-time publication are reported for each job, beside PARENT's stop
  time and reason (assessor criterion 1).
- **Pass (2):** all jobs pass both (2a) and (2b), on both builds. (2c) and (2d) are reported per job.

## (3) Post-hoc reading of the 17 (labelled; not a pass)
The result states whether each of the 17 would have been allowed under the amended wording (1) together with (2).
It is labelled **"post-hoc reading under the G6b-only amendment; G6a remains FAIL AS WRITTEN"**.
The V2 wall time for each of the 17 is given next to PARENT's SEARCH_TIMEOUT stop of about 78 s.

## Order
1. Finish R.
2. Final comparison and the job list for (2).
3. This file committed (it already is when (2) runs).
4. (2) by the author.
5. (2) by the verifier.
6. The assessor's judgement of (1).
7. The verifier reads (1).
8. G6b only after (1) and (2) are verified.
