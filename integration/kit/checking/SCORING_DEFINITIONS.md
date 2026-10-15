# Scoring definitions (frozen; unchanged from the KLB regional campaign)

Source of truth: `runner/native_tally.py` (the KLB `regional_tally.py`, sha256 a50c7f36..., with asserted
substitutions that change no class rule) and `decision/journey_decision_v2_1.py` (sha256 80adfc0b...).

## Deadline and on-time rule (controller, A3 semantics)

- Complete budget 30 s per request, measured from immediately before the timed command is launched to process
  completion. Graph preparation, admission, search, the mandatory whole-road check, the decision and publication are all
  inside it. In the primary campaign, preparation is the fast cold preparation (COLD_FAST) in both arms.
- At the deadline: SIGTERM to the attempt's process group, 3 s, then SIGKILL.
- Memory guard: sampled process-family RSS above 3,072 MiB stops the attempt the same way; never on time.
- On time: no memory stop, no termination, exit code 0, wall at most 30 s, RESULT authority_final true and
  PUBLICATION_BOUNDARY result_published_before_deadline true.

## Authoritative decision (journey_decision_v2_1, applied to RESULT plus the outer receipt plus JOB)

Successful journey statuses: CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN, CHECKED_JOURNEY_CENTRE_OPTIMUM,
CHECKED_JOURNEY_FEASIBLE. Refusal statuses: FULL_MODEL_REFUSAL_PROVEN, CENTRE_MODEL_REFUSAL_ONLY. Otherwise UNRESOLVED
(with a reason) or an input/identity failure status. A success requires on-time publication, the runtime whole-road
check CERTIFIED_ADMISSIBLE bound to the published route by content, and verified identities.

## Class of a completed attempt (`class`)

1. No independent checker output for an attempt with a RESULT: INDEPENDENT_CHECK_MISSING.
2. Independent contradictions reported: CONTRADICTION.
3. Successful journey: CONTRADICTION unless the independent trajectory is VALID, independent whole-road contact is CLEAR
   and the runtime whole-road check is CERTIFIED_ADMISSIBLE; CONTRADICTION if a dispute (below) is not cleared;
   ROAD_ONLY_ROUTE if the independent cell-centre model is not FEASIBLE; VERIFIED_FULL_OPTIMUM if the authoritative status
   is CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN; otherwise VERIFIED_ROUTE.
4. FULL_MODEL_REFUSAL_PROVEN: CERTIFIED_REFUSAL if the independent verdict is INDEPENDENTLY_CERTIFIED_REFUSAL;
   CONTRADICTION if a dispute is not cleared; otherwise UNSUPPORTED_REFUSAL_CLAIM.
5. CENTRE_MODEL_REFUSAL_ONLY: CENTRE_REFUSAL_ONLY.
6. Otherwise by unresolved reason: REJECTED_CANDIDATE (witness rejected by the whole-road check), TIMEOUT (search
   timeout published), LATE (late result), UNKNOWN_CHECK (a check-related reason), else the status or reason text.

Dispute: a FULL_OPTIMUM claim with an independent NOT_OPTIMAL_COUNTEREXAMPLE, or a FULL_MODEL refusal with
REFUSAL_CONTRADICTED or FEASIBLE_ROUTE_EXISTS. It is cleared only if the offline whole-road check of the independent
witness (`witness_wholeroad.py`, 150 s) returns DEFINITE_REJECT.

## Regional class (`regional_class`) and slot states

- MEMORY_GUARD_EXCEEDED if the guard triggered or the timed command's maximum RSS exceeded 3,072 MiB.
- WORKER_FAILED if the process exited non-zero without a deadline termination (exit code and last error line kept).
- NO_PUBLICATION if a LATE row exited by itself without an authoritative result.
- Otherwise the class above.
- Slots with no folder are NOT_RUN; folders without a receipt are INTERRUPTED (never relaunched). Both are unresolved
  with null measurements.

## Reporting class (`reporting_class`, rule N1 of the KLB pre-scoring note)

A deadline-terminated attempt that is not resolved is reported as DEADLINE_STOP (forced_kill kept separately).
Otherwise the reporting class equals the regional class. The raw regional class stays next to it.

## Resolution and counting

- Resolved classes: VERIFIED_ROUTE, VERIFIED_FULL_OPTIMUM, CERTIFIED_REFUSAL. Nothing else is resolved; in particular
  ROAD_ONLY_ROUTE, UNSUPPORTED_REFUSAL_CLAIM, CENTRE_REFUSAL_ONLY, TIMEOUT, REJECTED_CANDIDATE and DEADLINE_STOP are not.
- A mission is resolved (stable) only if all three repetitions of that arm are resolved.
- Counts are reported per region and per arm: missions resolved in all three repetitions (route and refusal missions
  separately), resolved attempts out of attempts, reporting classes, on-time attempts, wall, CPU, RSS.
- Never pooled across regions, hosts (native and Linux), workloads (primary cold and warm option), repetitions or
  overlapping panels, and never expressed as an accuracy percentage. Repetitions are not incidents; Yeongdeok and
  Uiseong-Andong are two crops of one 2025 incident group.
- Optimality scope: VERIFIED_FULL_OPTIMUM means the authoritative status CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN (the
  runtime road-bound certificate), an independently VALID trajectory, CLEAR contact, a FEASIBLE cell-centre model and no
  uncleared independent counterexample. It does not require an independent optimality certificate; the independent
  verdict (for example INDEPENDENTLY_CERTIFIED_OPTIMAL, a cell-centre-model statement) is recorded per row.
