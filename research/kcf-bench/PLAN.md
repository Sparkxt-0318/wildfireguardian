# kcf-bench PLAN: method A against method B, time, memory and accuracy, one machine

Status: **FROZEN** at the commit that adds this file, before any run (smoke test included). Any later change to
this plan is added below as a dated amendment, with its reason; nothing above the amendments is edited.

Base: `Main` at `5a31155d` (contains `beed15c7`). Branch `research/kcf-bench`. No existing file is changed; the
harness only imports. Hard stop: **Fri 20 Nov 2026, 12:00 Asia/Shanghai**.

## 1 Question

On one machine, single process, same Python: what do the two methods cost (wall, CPU, peak memory) on the six
recorded planner caches, do they give the same answers on every job both run, and how does B grow with graph size?

## 2 Methods (unchanged code, imported)

* **A, the recorded per-departure method** (`run_a.py`). One job at a time through the planner's own worker entry
  point `api/runner.py::execute`, with the spec `api/app.py::_new_route_job` builds for a recorded-fire, full-policy
  route check and the job's recorded request parameters: candidate route (`wfg_latest.api.route_and_check`, arm
  `RDA_CAND`, kit `integration/kit`, 30 s budget, 3072 MiB guard) plus the full-journey check, then the API verdict.
  This is the path that produced the cache `route_checks`. The kit launches its own frozen child process per job, as
  it did for the recorded checks. `run_independent_check` is false, as recorded.
* **B, the F-3.1 deadline field** (`run_b.py`). `deadline_field.core.backward` under the `cert` rule, the variant
  under which F-3.1 reproduced every recorded route (RESULTS.md section 1). Same steps as
  `deadline_field/reproduce.py::run --variants cert --timing-only`: packet model, precondition per (limits, incurred),
  one backward field per destination spec (node, dwell, window) over the jobs' start nodes, then for each job its
  issue set and a forward witness at its departure second. B's verdict for a job: `checked_route` if a witness
  exists at that second, else `model_no_route`. With a job list, only those jobs' destination specs and start nodes
  are run.

## 3 Inputs and sampling

The six committed caches `planner/cache/*/*.json` (SHA-256 as in `INDEX.json`) with the frozen routing inputs
(`data/routing`, from `tools/fetch_routing_inputs.py`). Same inputs for both methods.

**Running A in full exceeds 8 hours.** The recorded A compute is 147,900 s over 9,722 jobs (41 h), measured with 13
workers in parallel on a Mac; even at twice that speed one process needs about 20 h. So the sampling rule applies:

* **Smallest cache = UA 03-24** (`20250324T090000Z`): fewest jobs (1,518) and least recorded compute (14,749 s).
  A runs **all 1,518** of its jobs.
* **Each other cache:** a fixed random sample of **500 jobs**. Rule (`common.py::sample_jobs`):
  `random.Random("20261120:<cache name>").sample(sorted(job ids), all)` gives a fixed permutation; the sample is its
  first 500. Jobs are run in permutation order, so a run cut short by the hard stop is still a random sample (its
  size is reported). UA 03-24 also runs in its permutation order.
* **Repeat set:** the first 50 jobs of each cache's permutation (a subset of pass 1).

All six caches are in B's runs in full.

## 4 Measurement (identical for both methods)

Each measured command runs as the child of a fresh `measure.py` process, with Python
`/Users/jp/miniforge3/bin/python3` (3.13.13) for both methods:

* **wall** `perf_counter` launch to exit; **CPU** user + system of all waited descendants (`RUSAGE_CHILDREN`);
* **peak memory** `ru_maxrss` of `RUSAGE_CHILDREN` = peak resident set of the **largest single process** in the
  command's process tree. Same definition for both. A runs two processes at once (the worker and the kit child), so
  A's worker and largest kit child peaks are also recorded separately (`run_a.py` `.proc.json`) and their sum is
  reported as an upper bound on A's concurrent tree peak. B is one process.
* **per job, A only:** wall and CPU (self + children) around each `execute` call, plus the kit's own `compute_s`.
* 1-minute load average before and after every command, and per A job, is recorded. "Nothing else running" is
  asked of the user; the load average is the evidence of whether it held. It is reported, not used to drop runs.

## 5 Accuracy (untimed, after the timing runs)

For every job A ran in pass 1, against B's full-cache run (repeat 1), `compare.py`:

1. same verdict (A's `checked_route` / `model_no_route` / `unresolved` against B's);
2. same departure second; for jobs both call checked, same arrival second and identical leg sequence;
3. route validity of **each** method's route under the **unchanged** checker `deadline_field.verify.full_check`
   (`routing-package/routing/independent.py::check_route` plus the closed-footprint replay). A's legs are rebuilt
   with `tools/explain_deadlines/plans.py::reconstruct_legs`, which must hash to A's `route_sha256`.

**Disagreement** = any job where 1 fails, or 2 fails, or exactly one method's route is invalid, or a route of either
method fails the checker. Reported as a count, and **each one is listed** (job id, both verdicts, both times, checker
codes). Jobs A leaves `unresolved` while B decides them are counted as disagreements and also shown as their own
sub-count. A's agreement with the recorded cache result is reported alongside, as context.

## 6 Scaling (B only)

B's time and memory against graph size: the six caches (43,826 and 111,924 edges) and three synthetic grids
(`synth.py`, frozen generator in its docstring, seed 20261120): side 250, 354, 500 = 249,000, 499,848 and 998,000
directed edges, five destination specs and 100 origins each. One run per grid; each stops itself (recorded) after
30 min or 12 GiB. Reported per destination spec (backward time, issue+witness time) and per run (wall, CPU, peak).

## 7 Order of runs (`run_all.sh`), strictly sequential, nothing of mine in parallel

0. `jobs`, `host`, then **`smoke`**: A on 3 jobs, B on the same 3, compare, synth side 30. Crash test only; its
   numbers are **excluded** from every result. A fix found here is committed with a note; the protocol does not change.
1. `b`: B, **3 repeats**, each repeat over the six caches: full cache; A's pass-1 job set (five sampled caches);
   the 50-job repeat set.
2. `synth`.
3. `a`: A pass 1: UA 03-24 first 500 of its permutation, the five 500-job samples, then UA 03-24's other 1,018.
4. `arep`: A repeats 2 and 3 on each cache's 50-job repeat set.
5. `compare`.

**Deviation from "3 repeats" for A, stated up front:** A gets 3 repeats only on the 50-job repeat set of each cache
(300 jobs); pass 1 is one repeat. Three full repeats of A's sampled design need about 45 h, past the hard stop. B gets
3 full repeats everywhere.

## 8 Reporting rules

* **Time.** B: per cache, median and range over 3 repeats of wall and CPU. A: per-job wall and CPU on each cache's
  pass-1 jobs: median and mean with **95% bootstrap intervals** (10,000 resamples, seed 20261120); total measured wall
  for the jobs it ran; on the repeat set, per-job median and range over the 3 repeats. **No extrapolated A total is
  presented as measured.**
* **Speed ratio only on jobs both ran:** A's measured process wall (and CPU) for its pass-1 job set divided by B's
  for the identical job set (`B pass1` runs; for UA 03-24, B's full run, since A ran every job). Median over B's 3
  repeats. No summed ratio over jobs A did not run.
* **Memory.** Per method per cache, peak as in section 4. **If B's peak exceeds A's on any cache, that is said
  plainly.**
* **One table**: method by cache, with time, memory and agreement. Machine (CPU model, cores, RAM), OS, Python,
  library versions and the commit of each method (last commit touching `api/`, `integration/` for A, and
  `research/harness-2026-11/F-3.1/deadline_field/` for B; plus the commit recorded in the cache provenance for A,
  `f8765a68`) go with it.
* `research/kcf-evidence/TALK_NUMBERS.md` **row 1** (section 1, the time rows and their "does not show" note) is
  updated with the measured figures and the files they come from.
* **Hard stop.** `KCF_BENCH_STOP_AT` stops A from starting a new job after Fri 20 Nov 03:00 (pass 1) and 06:30
  (repeats) Shanghai time; compare and write-up follow. Whatever is done at 12:00 is reported as done, with what was
  not run named.

## 9 Known limits (stated before running)

* Python 3.13.13 for both; the recorded A checks used 3.12.1. A's kit is run as it is, under this interpreter.
* The machine is the user's working Mac (Apple M5 Pro, 5 performance + 10 efficiency cores, 24 GB). Before the run
  swap was 5.9 GB used and the disk had 3.4 GB free. macOS may place a process on efficiency cores; this is not
  controlled.
* A's 30 s budget is wall-clock; on a slower or loaded core A can return `unresolved` where it would not otherwise.
  Such jobs are reported, not rerun.

## Amendment 1 (Thu 19 Nov 2026, 21:05 Shanghai; after phase 1 `b` had started, before `synth`, `a`, `arep`)

**Reason.** The plan's schedule assumed it was 07:15 Shanghai; the clock read was wrong (the sandbox ignored `TZ`).
It is 21:05, so about 15 h remain, not 29. B is fast (UA 03-23 full cache in under 20 s), A is the long phase
(smoke: about 5–6 s per job, so pass 1 is roughly 8–10 h). Nothing measured so far was looked at beyond the smoke
test's crash check and the one file size, and no measured number changes any rule below.

**Changes.** Nothing else in the protocol changes.
* `synth` per-grid cap: **10 min** (was 30 min) of in-process time, checked between destination specs; specs done
  before the cap are reported per spec, as before.
* `KCF_BENCH_STOP_AT` (no new A job starts after): pass 1 **Fri 07:45** Shanghai (was 03:00); repeats **Fri 09:15**
  (was 06:30). `compare` and the write-up follow.
* If A pass 1 is cut short, the jobs it did run in each cache's permutation order are the sample, with their count.

## Amendment 2 (Fri 20 Nov 2026, 06:10 Shanghai; after phase 3 `a` stopped on a full disk, before `arep`)

**What happened.** At 04:20 Shanghai the disk filled (not from this harness: `runs/` is 93 MB and each A job's work
directory is deleted after it). A's YD0326 sample was at job 255 of 500: its jobs 217–255 (permutation positions
216–254) returned `INTERNAL_ERROR: No space left on device`; then the worker itself crashed, so YD0326's process-level
measure file was never written. UA0324's other 1,018 jobs and phase `arep` did not run. The user freed space; about
0.9 GiB was free at 06:05.

**Changes.** Nothing else in the protocol changes.
* The 39 disk-failed YD0326 rows are moved, unchanged, to `runs/a/YD0326.pass1.enospc_excluded.jsonl`. They are not
  A results (A never ran them to completion) and are reported only as this note. The 216 rows before them are kept.
* New phase `aresume`: A on YD0326's permutation positions 216–499 (`runs/jobs/YD0326.pass1_resume.json`), appended to
  the same file, then UA0324's other 1,018 jobs, as phase `a` would have. Same stop times as Amendment 1 (pass 1 Fri
  07:45, repeats Fri 09:15).
* `run_a.py` starts no new job when free disk is below 300 MiB (`KCF_BENCH_MIN_FREE_MIB`), and says so; the jobs run
  before that are the sample, in permutation order, as for the time stop.
* YD0326's A process wall/CPU is the sum of its two measured processes for the resumed part only; for the speed ratio
  on YD0326 the sum of A's per-job wall and CPU over its jobs is used instead, and labelled so.

## Amendment 3 (Fri 20 Nov 2026, 06:12 Shanghai; disk ran out again at 06:06)

The free-disk guard stopped `aresume` after 6 YD0326 jobs (06:06); the disk then reached zero, so `arep` stopped and
`compare` did not run. One A job uses about 1 MB of disk (measured on one extra, unrecorded job), so the space is
taken by something else on the machine. No A row failed: the 6 jobs completed normally and are kept (YD0326 now 222
done, in permutation order). The empty guard-stopped files (`UA0324.tail`, YD0326 resume measure file, the two empty
`repeat.r2` runs) are moved to `runs/excluded_guard_stops/`. The resume measure file of those 6 jobs was lost with
them; their per-job times are kept. `aresume` restarts from YD0326 position 222 (`YD0326.pass1_resume2.json`), then
UA0324's other 1,018, then `arep` and `compare`, under the same stop times. Nothing else changes.

## Amendment 4 (Fri 20 Nov 2026, 09:55 Shanghai; after `compare`, before the write-up)

A pass 1 stopped at 07:45 as set, with UA0324 at 1,093 of 1,518 jobs (in permutation order). B never ran that exact
job set (its UA0324 runs were the full cache), so for the speed ratio rule (jobs both ran) B is run now on
`runs/jobs/UA0324.pass1_ran.json`, 3 repeats, measured exactly as phase `b` (`runs/b/UA0324.pass1ran.r*.json`). The
repeats stopped at 09:15 with complete repeat-2 sets only for UA0323 and UA0324 (UA0325: 8 of 50); the repeat-set
ratio is reported only for those two. Nothing else changes.
