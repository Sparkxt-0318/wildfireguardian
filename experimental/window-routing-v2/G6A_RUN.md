# G6a run procedure (operational rule; written before the runner, and before any G6 run)

G6_RULE.md stays the rule. This file fixes how G6a is run and compared. Where this file is silent, G6_RULE.md
governs. Nothing here loosens G6_RULE.md.

## Kits
- **V2:** the identity-record kit, manifest `bd67ff9d…`. That is Step 2 + Step 3 + the identity record (4 recording
  lines in the worker).
  - The orchestrator decided (option B, 2026-11-13 04:15Z) to land the identity record first, through its own
    tests, G1 panel, verification and cut, and then run G6a once, on the kit that goes forward. So G6a, G6b and Step 6
    refer to one manifest.
  - G6a does not start until that cut is on Main and its manifest is confirmed equal to `bd67ff9d…`. If the cut
    changes the manifest, this line is amended before the run.
  - Its KIT_IDENTITY is checked on every V2 row, and every V2 row also carries `checker_identity` (the three checker
    module hashes).
- **PARENT:** the frozen request-window kit (`window-kit`, unchanged).

## Sample
`G6A_SAMPLE.json` as committed (seed 20261112): 705 jobs = 297 TIMEOUT + 186 AT_ISSUE + 150 ROUTE + 72 NOROUTE. It is
not redrawn.

## Inputs (re-verified before every job)
- Packet: `data/routing/latest_inputs_try02/packets/<region>/<input_time>`. Its HAZARD.json sha256 must start with
  the G6_RULE prefix for that input.
- The packet's member ids must carry the cache's `scenario_set_id`.
- Graph: `data/routing/graphs/<region>/graph.json`, sha256 prefix as in G6_RULE.
- Checked once at selection time: all 8 prefixes match.

## Request (rebuilt exactly as the API does)
`api.requests_build.build_request` with:
- start node, destination node, `depart_offset_s`, `dwell_s` and `destination_window` from the cache's
  `route_checks[job].request`;
- limits = `api.requests_build.effective_limits(request)`;
- scenario ids, horizon, valid_from, version, `time_origin` and dt from the packet's HAZARD.json (as `api/runner.py`
  does).

A job whose request the builder rejects is listed as INPUT_REJECTED for both kits. It is reported, not compared.

## Running a job
- One fresh interpreter per job (`tools/g6_job.py`), through F-3.4 `run_profile.run_one` with explicit
  graph/packet/request paths.
- Budget 81 s complete. Controller guard 3,072 MiB. `--mode plain`.
- No `rss_limit_mb` beyond what the rebuilt request carries.

## Phases, in this order (each must finish before the next starts)
1. **P1:** PARENT on all 705 jobs.
2. **P2:** PARENT on all 705 jobs again.
   - **Before V2 runs,** the FL2-type exception list (jobs whose P1 and P2 outcomes differ) is computed, committed and
     sent to the independent verifier.
3. **V:** V2 on all 705 jobs.
4. **R:** V2 rerun once, only for jobs where V2 ≠ PARENT and either side is UNRESOLVED with a wall-cap reason (G6_RULE
   exception). The rerun outcome replaces the first V2 outcome for the comparison, and both are listed.

## Tracking and checkpointing
- One harness-tracked task drives `tools/g6_run.py` with 3 workers.
- Each finished job appends one row to `<phase>/ROWS.jsonl`. A restart skips jobs already in ROWS.
- A job folder without a row is renamed `_restartN` and logged in `RESTARTS.log`.
- Relaunching after the 2 h task limit, or after a container restart, is a logged restart, not a rerun.
- G6 runs are never used for timing claims (G6_RULE). Wall and memory are reported, not judged.

## Outcome of a job (both kits, the same extraction)
- **verdict, reason_code:** `api.verdict.classify(decision, receipt, result, None, 3072)`, the API's own classifier.
- **raw_status:** the decision's `authoritative_status`.
- **arrival_s,** and **route:** `edge_ids`, `times_s` and `waits` from `api.runner.route_feature` on the decision's
  journey (the planner's own route form).
- **wall_cap:** true when the receipt shows a deadline termination and the reason is TIMEOUT.

## Comparisons (per G6_RULE; computed by `tools/g6_compare.py`)
- **G6 failure:** V2 ≠ PARENT.
  - Equality means the same verdict and, for checked_route, the same arrival_s.
  - Identical route triples (edge_ids, times_s, waits) are reported. Different routes with equal arrival are listed
    as "equal-arrival ties", not failures (G6_RULE: "unless another route has the same arrival").
  - A raw_status difference with the same verdict and arrival (for example FEASIBLE vs OPTIMUM) is listed, not a
    failure.
  - For FL2-type jobs (P1 ≠ P2), V2 is compared with the set {P1, P2}.
- **Against the RECORD,** for both kits and per G6_RULE's table:
  - checked_route needs identical arrival_s;
  - model_no_route needs FULL_MODEL_REFUSAL_PROVEN;
  - AT_ISSUE_FAILURE needs AT_ISSUE_FAILURE;
  - timeouts must not contradict the router-only field at c0e34d4 (`TIMEOUT_NO_ROUTE_CERTS_1h.json`, sha256 prefix
    886e4e7e): the 98 NO_ROUTE_CERT jobs must not become checked routes, and the 199 FEASIBLE_IN_ROUTER_FIELD jobs
    must not become refusals.
  - PARENT ≠ RECORD is listed as a pre-existing kit difference.
  - V2 ≠ RECORD while V2 = PARENT is not a G6 failure.
- **A timeout contradiction by V2** is a G6 failure even if PARENT shows the same contradiction. That would be a
  soundness finding, reported first.

## Pass
G6a passes if:
- there are 0 G6 failures and 0 V2 timeout contradictions, after the R phase;
- every V2 row carries kit identity `bd67ff9d…` (or the manifest named above, if amended);
- the PARENT input and request hashes equal V2's on every job.

Everything else is reported:
- PARENT ≠ RECORD;
- ties;
- raw_status differences;
- the FL2-type list.

## Then
The independent verifier checks the rows, the exception list and the comparison. Power statements are as in G6_RULE
(routes ≤ 2.0%, no-routes ≤ 4.2%; timeouts and AT_ISSUE complete).
