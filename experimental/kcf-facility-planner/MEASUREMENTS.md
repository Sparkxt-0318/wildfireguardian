# Measurements (2026-11-11, this worktree)

Host: Linux x86_64 container, 4 CPUs, Python 3.13.18, standard library only, network not used. Values below were observed in this run; they are not benchmarks and are not comparable with the research release timings.

## Actual interface, offline

`python3 measure.py` runs `cli.py --case ABS.json --output ABS.json` as a separate process for 21 inputs (7 contract fixtures, 7 delays each for the two demo fixtures), 3 repetitions. The raw output is written to `out/measurements.json`, which is ignored by git.

* All 21 results replayed cleanly with the independent replay, and the `wfg_sipp` cross-check passed on every trip.
* Process wall time (median of 3) was 0.061–0.093 s per case, mostly interpreter start-up.
* In-planner `wall_s` was at most 0.0011 s.

| Input | Status | final_unload_s | Checked people |
|---|---|---|---|
| contract normal | CHECKED_ROUTE | 13 | 12/12 |
| contract delayed (V2 ready 10; e1 closed [10,30]) | CHECKED_ROUTE | 25 (V2 switches to e3/e4) | 12/12 |
| contract no_route | MODEL_SCOPED_NO_ROUTE | null | 0/12 |
| contract missing_input | MISSING_INPUT | null (conditional 11) | 0/6 |
| contract horizon_boundary (H=11) | CHECKED_ROUTE | 11 (= horizon) | 6/6 |
| contract horizon H=10 | MODEL_SCOPED_NO_ROUTE (OUT_OF_HORIZON) | null | 0/6 |
| contract shuttle | CHECKED_ROUTE | 28 (return e6→e7→e8; U-turn forbidden) | 12/12 |
| demo two-vehicle, V2 +0/+5/+10 min | CHECKED_ROUTE | 2100 / 2400 / 3400 | 12/12 |
| demo two-vehicle, +15/+20 min | MISSING_INPUT | null | 6/12 |
| demo two-vehicle, +25/+30 min | MODEL_SCOPED_NO_ROUTE | null | 6/12 |
| demo shuttle, +0 min | CHECKED_ROUTE | 5000 | 12/12 |
| demo shuttle, +5/+10 min | MISSING_INPUT | null | 6/12 |
| demo shuttle, +15…+30 min | MODEL_SCOPED_NO_ROUTE | null | 6/12 |

`python3 demo.py --export out/` precomputed 122 plans (2 cases × 0–60 min) in 2.7 s, producing a 1.85 MB self-contained HTML file.

A headless Chromium session (the pre-installed Playwright) loaded the live server page and the exported `file://` page, the latter with networking disabled. In both it changed the delay and switched cases. It recorded no page errors and no requests outside 127.0.0.1 or `file:`.

## Correctness evidence

* **Unit tests:** `python3 -m unittest discover -s tests` passes 32 tests. These cover normal, delayed, no-route, missing-input, horizon-boundary and shuttle cases, plus capacity, the window/early-arrival rule, turn persistence, cap → UNRESOLVED, invalid input, CLI atomic output, isolated replay mutations for every rule, the demo outcomes and review regressions.
* **Random oracle comparison:** `tests/oracle.py` is a second-by-second brute force written from the contract.
  * In the test suite (seed 20261111), 20,000 random cases matched on status, `final_unload_s`, checked people and the conditional final: 6,173 CHECKED_ROUTE, 539 MISSING_INPUT, 13,288 MODEL_SCOPED_NO_ROUTE.
  * An ad-hoc run of 60,000 more cases (seeds 1–3) gave 0 mismatches and 0 gated witnesses: 19,005 / 1,618 / 39,377.
  * Every witness also passed the replay and the `wfg_sipp` cross-check, which uses SIPP, the brute-force lattice and the JS-1..JS-8 and JS-11 predicate.

## Adversarial review

Four independent AI reviewers looked at contract conformance, an independent oracle, replay soundness, and status/explanation logic. Each claim was then checked by a separate verifier.

The independent-oracle reviewer found no disagreements. Five confirmed issues (low or minor severity) were fixed and have regression tests:
1. When the gate withheld a witness, it left the group-coverage fields stale.
2. Replay did not check schema_version, integer types or status/conditional consistency.
3. Counterfactual diagnostics ignored the cap and time limit.
4. A capped diagnostic could produce a false `NO_PATH_IN_ROAD_MODEL`.
5. A MISSING_INPUT witness listed unknown inputs for a vehicle that already had a checked schedule.

While re-testing, the stricter replay caught one more defect: a zero-length unknown interval was reported as touched. It was fixed in `solver.overlapping` and has a regression test.

Points the reviewers judged ambiguous are documented under "Interpretation notes" in SCHEMA.md: self-loop re-entry, the INVALID_INPUT status, and reason codes when several groups fail.

## Not measured

There is no human or judge usability test and no comparison with the archived Uiseong–Andong records, which are not available here. No thermal, physical or field validation was done.
