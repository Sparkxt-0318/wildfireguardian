# G6a ruling and the checks that follow it (written before the added check runs, and before G6b)

Orchestrator ruling, 2026-11-13 12:23Z: option (b), which includes (a).

## (a) G6a result wording
G6a is recorded as **FAIL AS WRITTEN on the 17 jobs**, in those words, at the top of the result.
- The pre-stated "wall cap" definition (G6A_RUN.md: deadline termination with reason TIMEOUT) is not reinterpreted
  after the run.
- The facts are reported beside it: V2 vs RECORD, the direction of all differences, and their PARENT stop reasons.

## (1) Amended definition, for G6b only (prospective, not applied to G6a)
- **"Time-capped"** covers any PARENT stop whose reason is a time-based cap:
  - a deadline termination (receipt `deadline_termination_requested`, reason TIMEOUT); or
  - `SEARCH_TIMEOUT`.
- **A V2 ≠ PARENT difference is allowed only if all of these hold:**
  - PARENT is UNRESOLVED with a time-capped reason (in every PARENT run of that job);
  - V2 is a checked route;
  - the V2 route contradicts neither the RECORD, the router field (`JOBS_1h_crossref.json` @ 5389803e, router
    feasibility and arrival) nor a certificate (`TIMEOUT_NO_ROUTE_CERTS_1h.json` @ c0e34d4);
  - it passes the added route check (2) below.
- **Every other difference stays a failure.** That includes:
  - V2 UNRESOLVED where PARENT resolved;
  - any refusal ↔ route change;
  - a different arrival on a checked route;
  - V2 refusing where PARENT is UNRESOLVED.
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
- **Pass (2):** all jobs pass both (2a) and (2b), on both builds.

## (3) Post-hoc reading of the 17 (labelled; not a pass)
The result states whether each of the 17 would have been allowed under the amended wording (1) together with (2).
It is labelled **"post-hoc reading under the G6b-only amendment; G6a remains FAIL AS WRITTEN"**.

## Order
1. Finish R.
2. Final comparison and the job list for (2).
3. This file committed (it already is when (2) runs).
4. (2) by the author.
5. (2) by the verifier.
6. The assessor's judgement of (1).
7. The verifier reads (1).
8. G6b only after (1) and (2) are verified.
