# G6a result: **FAIL AS WRITTEN on the 17 jobs**

Rules: G6_RULE.md, G6A_RUN.md (committed before any G6 run), G6A_RULING.md (the orchestrator's ruling, plus the
assessor's additions, committed before the added checks ran).

The pre-stated "wall cap" definition (deadline termination with reason TIMEOUT) is not reinterpreted after the run.
On 17 jobs, V2 publishes a checked route where PARENT stopped UNRESOLVED on its own `SEARCH_TIMEOUT`. That is outside
the wall-cap exception, so under the rule as written they are G6 failures.

**Counting note (stated, not decided by the author).**
- G6_RULE says a wall-cap UNRESOLVED is an exception, "listed and rerun once". The 47 wall-cap differences reproduced
  on their single V2 rerun.
- Under G6_RULE's text they are the listed exception, so the failures are the **17**. That is the ruling.
- `tools/g6_compare.py` stays stricter: it counts any difference left after the rerun, so it reports **64**.
- Both numbers are given here.

## Facts reported beside the verdict
All measured. Kits:
- V2: `0fffb589…` (Main 149b5b25, identity record; built from Main and byte-identical to the verified kit);
- PARENT: frozen `b6770404…`.

Run on one host, 3 workers, 81 s, guard 3,072 MiB. G6 runs are never used for timing claims.

| | Result |
|---|---|
| **V2 vs RECORD** | **705/705 allowed** by G6_RULE's table |
| **Timeout contradictions by V2** | **0**: none of the 98 certified-no-route timeouts became a route, and none of the 199 feasible ones became a refusal (TIMEOUT_NO_ROUTE_CERTS_1h @ c0e34d4) |
| V2 vs PARENT differences | **64, all in one direction: PARENT UNRESOLVED → V2 checked route (FULL_OPTIMUM_PROVEN)**. All are TIMEOUT-stratum Yeongdeok: 62 from 0325T19 and 2 from 0325T23 |
| PARENT stop on those 64 | **47** deadline termination (LATE_RESULT, wall cap): 16 in both PARENT runs, 31 in one run with SEARCH_TIMEOUT in the other. **17** SEARCH_TIMEOUT in both PARENT runs, at about 78–81 s |
| Phase R (47 wall-cap jobs rerun once on V2) | **47/47 reproduce the same V2 checked route** |
| FL2-type list (PARENT P1 ≠ P2, committed before V2 ran) | 34 jobs, all UNRESOLVED ↔ checked_route |
| PARENT vs RECORD (pre-existing kit differences, listed) | 702 allowed; 3 ROUTE-stratum arrival differences |
| Equal-arrival ties (different legs, same arrival) | 25, listed |
| raw_status differences (judged against PARENT {P1, P2}) | 63, listed. PARENT's own P1-vs-P2 raw_status variation is 34 |
| Kit identity / input and request hashes | 0 mismatches. Every V2 row carries kit identity 0fffb589 and the checker identity record |
| Harness errors | 0 in 2,162 job runs (P1 705, P2 705, V 705, R 47) |

## Added check on the 64 new routes (G6A_RULING.md (2); author's build; the verifier's build is pending)
| Check | Result |
|---|---|
| **Headline: V2 arrival = router-field optimum** (crossref @ 5389803e) | **64/64**. The optimum is confirmed from both sides on every route, so no witness test was triggered. 0 routes on jobs the router field calls infeasible |
| (2a) Both frozen checkers, fresh interpreters (`tools/g2_recheck.py`) | **64/64**: whole-road CERTIFIED_ADMISSIBLE, and the independent checker ok with no codes |
| (2c) Optimality, g2b @ deeb7c2 | **64/64 PASS "attains the relaxation optimum"**. g2b's relaxation optimum equals the router-field optimum on all 64 |
| (2d) Time | **64/64 published on time**, inside the 81 s user limit. V2 wall 28.6–50.5 s, median about 33.5 s |
| Exposure | Largest peak 0.0063 kW/m² against a limit of 10. Smallest dose margin 98.995 kJ/m² against 100. Per job in `results/g6a/added_check/NEW_ROUTES_64.json` |

**Not verified by G6a:** tie-break behaviour among equal-arrival routes on these 64 jobs, because PARENT has no route to
compare. It rests on the jobs where V2 equals PARENT exactly.

## Post-hoc reading under the G6b-only amendment; G6a remains FAIL AS WRITTEN
Under G6A_RULING.md (1), the closed time-cap list, with (2):
- the 17: PARENT is `SEARCH_TIMEOUT` (on the closed list) in both runs; V2 is a checked route, on time, at the
  router optimum; both checkers and g2b pass. **Each of the 17 would have been allowed.**
- The 47 would also have been allowed on the same tests.
- All 64 would be counted as "allowed differences: optimum confirmed", never as unchanged and never as pass.

V2 wall time for the 17, against PARENT's SEARCH_TIMEOUT stop at about 78–81 s: 29.2, 31.2, 31.6, 32.3, 32.5, 32.5,
32.7, 32.9, 33.4, 34.5, 39.5, 40.3, 40.6, 43.3, 48.7, 49.1, 50.5 s.

## Concentration
- All 64 differences are Yeongdeok TIMEOUT-stratum: 62 from start 0325T19 and 2 from 0325T23.
- These are the missions where Step 3's work budget lets Z finish. PARENT stops these jobs on time-based caps.

## Runs and restarts (RUNLOG.txt, per-phase RESTARTS.log)
- Harness smoke test before P1: 4 PARENT jobs in scratch, never compared.
- P1: stopped by the 2 h task limit at 628. P2: stopped by the 2 h limit at 577, then by a container restart at 589.
  Each time, the 3 in-flight jobs were renamed `_restartN` and rerun.
- V: 705/705, 10:41:47–12:21:48Z, no restart. R: 47/47, 12:22:32–12:32:51Z, no restart.
- The added check was first started detached by mistake. It was killed before any output and relaunched as a tracked
  task.

## Ideas and gaps
- The verifier's independent run of (2) on their own build is pending (G6A_RULING order, step 5).
- G6b must not start until the verifier has read (1) and verified (2).
- The 34 PARENT FL2-type flips suggest 3-worker timing variance near the 81 s cap (hypothesis, untested). G6b could
  report whether V2's outcomes vary between two V2 runs on the same jobs.
