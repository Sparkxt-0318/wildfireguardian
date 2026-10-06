# Reproduce the preparation integration

Python 3.11+ and standard library only. No dependencies were added or installed. Exact measured Python/platform and frozen source/input hashes are in `evidence/CONFIRM_FREEZE.json`. The measurement runtime is `/Users/jp/miniforge3/envs/wfg311/bin/python`. After copying this directory to another compatible machine, Python 3.11+ suffices; candidate and verifier paths are relative to this delivery. The historical vendor/research artifacts are retained as evidence and are not production dependencies.

From this output directory:

```sh
python3 -B baseline/run.py check
python3 -B candidate/run.py check
python3 -B review/adversarial_review.py
python3 -B verify_delivery.py
python3 -B verify_delivery.py --patch-output work/new-patch-verification
python3 -B candidate/run.py solve --input candidate/fixtures/example.json
python3 -B candidate/run.py replay --input candidate/evidence/CONTINUITY_REPLAY_FIXTURE.json
python3 -B candidate/run.py replay --prepare-graph --input candidate/evidence/CONTINUITY_REPLAY_FIXTURE.json
```

`candidate/run.py check` verifies 21 frozen package code/test hashes, runs 84 tests, compares raw/prepared deterministic replay and checks the preserved full-road witness. The separate review script creates a fresh timestamped run and checks the actual session/fallback/CLI APIs against the preserved baseline and bounded exhaustive references. Its earlier failed runs and coordinator-found repair remain archived, not overwritten. `verify_delivery.py` verifies delivery/source/confirmation hashes. Its optional patch-output must be absent; it applies `CANDIDATE.patch` to a fresh baseline copy, verifies exact changed-file bytes and runs that patched package's checks.

On the shared WildfireGuardian Mac, road-scale checks and every reported timing run must use the established exclusive measurement wrapper. From this directory, reproduce confirmation into a new output:

```sh
/Users/jp/miniforge3/envs/wfg311/bin/python   /Users/jp/Documents/Codex/2026-09-24/fu/outputs/routing_specialized_research_20261003_v1/coordination/run_locked.py   --mode exclusive --owner routing_preparation_reproduction   --label 'frozen preparation integration reproduction' --   /Users/jp/miniforge3/envs/wfg311/bin/python -B reproduce.py --out work/new-confirmation
```

Use the same wrapper around the road-scale package/patch checks above on this Mac. Light tiny review work under 10 seconds needs no lock. On another machine:

```sh
python3 -B reproduce.py --out work/new-confirmation
```

Never rerun `freeze` over archived evidence. The runner validates frozen code and exact inputs, refuses an existing output and performs three interleaved paired repetitions. It starts fresh child processes with a 120-second watchdog and retains all errors, timeouts, unsupported outcomes and regressions. 9 modes each on one tiny continuity fixture and one simple Nangok-road query, plus cold/repeated session modes on one bounded distant-road search: 120 rows / 60 pairs. The three road representations share one geography and generated hazard assumptions; they are not independent fire incidents. No tuning was performed on final timing results.

Raw repeated session means initialization+admission+three complete plan/commit/retained cycles+reset. Hazard-update mode adds two full copied hazard updates; checked session charges full contents comparisons at all operations. Replay covers actual process-local event handling. Return mode charges preparation and two primary/recorded-return facades; the tiny case is TIMEOUT plus CHECKED_ROUTE, and the simple-road case is PROVEN_INFEASIBLE plus a refused UNSUPPORTED return. Both negative and successful outcomes are preserved. Replacement charges update construction/rebuild and post-replacement admission/plan/check/reset; the preserved comparator explicitly resets and constructs a new raw session because it has no replacement API. One-shot CLI process timing charges interpreter, imports, parse, preparation, planning/checking and JSON output; no cross-process cache exists.

`aggregate.py` recomputes complete non-timing result equality, deterministic search counters, every paired latency/regression and extra unchanged-baseline witness arithmetic. Generation fields are normalized only for the replacement comparator, whose fresh raw object starts at a different generation; full original outputs remain in rows, and stale-result rejection is separately adversarially tested. Exhaustive tiny oracle evidence lives in the separately owned review. Extra road witness checking never recertifies a global road optimum/refusal.

```sh
python3 -B aggregate.py evidence/confirm
```

`CANDIDATE.patch` is against the preserved delivered raw source; `INTEGRATION_ONLY.patch` is against the verified immutable-preparation parent. Both include lifecycle documentation and current package hash records. Parent/copied historical evidence is explicitly labelled by the root handoff and the candidate manifest; authoritative new review/timing evidence is at top level.

The initial partial benchmark and freeze were preserved under `evidence/pre_repair_partial/` and `PRE_REPAIR_FREEZE.json` after a strict-reset control-input admission bug was found by source audit. `CORRECTNESS_AMENDMENT.json` records the repair and fresh freeze on unchanged inputs. Those partial rows are not used for adoption or inferential timing summaries.


To rerun the separately frozen connected diagnostic into a new directory (use the same exclusive wrapper on the shared Mac):

```sh
python3 -B diagnostic_hard.py run --out work/new-connected-diagnostic
python3 -B aggregate_hard.py work/new-connected-diagnostic
```

Its candidate source is exactly the main candidate, inputs/order/caps are separately frozen, and it retains all 18 rows / 9 pairs including primary TIMEOUT and checked returns. It is supplemental, never pooled as a confirmatory promotion result.
