# BENCH_PLAN: one fair comparison of routing methods (frozen before any timing)

Written 19 Nov 2026 and committed before any timing run. Nothing in sections 1 to 9 changes after the first benchmark
number exists. A mistake found later is corrected by a dated amendment at the bottom, never by editing this text.

## 0. Why this exists

`research/kcf-evidence/TALK_NUMBERS.md` says of the deadline field "Speed is not claimed": the old checks were timed on
a Mac running 13 workers, the field on a Linux container that was loaded by a concurrent build. This run puts every
method on one machine, one thread, one set of inputs, with repeats and ranges. It also compares the margin field
(`research/kcf-idea-routing`), whose own benchmark compared it only with the deadline field and never with the old
method.

## 1. Machine and conditions

* One machine for everything: this cloud container. Intel Xeon 2.30 GHz, 4 virtual cores, 16 GiB, Linux 6.18.44
  x86_64, CPython 3.13.18, numpy 2.5.3. It is a virtual machine on a shared host, so neighbours cannot be ruled out.
  That is what repeats, an interleaved order and a fixed CPU probe (below) are for. The probe, `/proc/loadavg` and the
  steal counter in `/proc/stat` are logged before and after every block.
* Every timed process is pinned to one core with `taskset -c 3` and run with `OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`. OLD's worker processes inherit the pin. All three methods are single thread.
* Nothing else of this study runs while a timed block runs. I do not run tests, builds or other computations in the
  session during the run. `git` and log reads happen between blocks (a pause flag makes the driver wait before the next
  block). The driver itself sleeps while a block runs.
* The OS page cache is not dropped. "Cold" is defined by what the method does (section 3), not by the disk.
* No API key is used anywhere in this run. The folder "wildfire 3 (1)" on the user's computer was **not reachable**
  from this session (no computer attached; `list_computer_folders` returned no folders), so the finals forecast and
  heat data were taken from the repository and from the SHA-256-verified release archive
  (`tools/fetch_routing_inputs.py`, 132 files verified). The six caches below are the committed `planner/cache` files,
  checked against `planner/cache/INDEX.json`.
* Code: base `Main` at `5a31155d` (PR #218, which contains #217) plus branch `research/kcf-idea-routing` at
  `a471eee1` (not merged into `Main`), merged into this working branch at `dd8fe2d5`. The commit of the harness is
  recorded in every result file. A dirty tree makes the driver refuse to start.

## 2. Inputs

**Six recorded caches**, the 1-hour planner caches: `uiseong_andong_2025/{20250323T010000Z, 20250324T090000Z,
20250325T170000Z}` (43,826 edges) and `yeongdeok_2025/{20250325T190000Z, 20250325T230000Z, 20250326T080000Z}`
(111,924 edges). 9,722 recorded route checks in total.

**A case** is one recorded route-check request of a cache: origin node, destination node, dwell, destination window,
departure offset, limits. All `route_checks` entries of a cache are the cases of that cache. A case is answered
"journey exists" or "no journey" and, if it exists, with an arrival second.

**The OLD sample.** For each cache, `random.Random(20261119).sample(sorted(job_ids), 200)`. The same 200 cases are used
in every repeat, cold and warm. They are written to `cases/<cache>.json` by `make_cases.py` before any timing.

**Rule variant.** FIELD and MARGIN use the `cert` rule: the router's rule OR the closed-footprint whole-road rule. It is
the variant that reproduced every recorded checked route in F-3.1 and it matches OLD's full policy (route checked by
the whole-road check). The preconditions that the full policy reduces to contact (`full_policy_reduces_to_contact`,
per distinct limits and incurred dose) are computed by FIELD and MARGIN and are inside their timed region.

## 3. Methods, and what is timed

All three answer the same case. Inputs are read from the same frozen files.

**a. OLD**: the finals-submission method: one departure at a time, one request, the kit v3 worker (`RDA_CAND`,
`rda_worker_v1_1.py`) launched by the kit controller, full policy, with its mandatory whole-road journey check, 30 s
complete-request budget and 3,072 MiB guard. The call is `wfg_latest.api.route_and_check` as the API makes it (request
built by `api/requests_build.py`), with `check=False` (the offline independent checker is not part of the request). The
case is decided if the verdict is `checked_route` or `model_no_route` (the API's own classification,
`api/verdict.py`); anything else is "unresolved" and is counted and not used for agreement.
Time per case = the controller's `external_launch_to_completion_wall_s` (process start to reaped exit). Peak memory per
case = the worker's maximum resident set from `/usr/bin/time -v`.
* **OLD cold**: as recorded: the worker prepares the graph from scratch (`COLD_FAST`).
* **OLD warm**: the kit's own warm option: `AUTHENTICATED_ARTIFACT`, a private prepared-graph store. One untimed priming
  request per cache fills the store; every timed request is then a store hit. It is still a fresh process per case.
* OLD is run on the 200-case sample only (a full run is about 9,700 checks at several seconds each, times 5 repeats,
  times 2 modes). The cache's time is **scaled**: per-case mean of the sample times the number of cases of the cache.
  This is an estimate and is labelled as scaled everywhere. Its sampling uncertainty is reported (section 6).

**b. FIELD**: the deadline field of `research/harness-2026-11/F-3.1` (`PacketModel.instance`, `backward`, `issue_set`,
`witness`), unchanged. One backward field per destination spec (node, dwell, window) of the cache, for the `cert`
variant. Every case of the spec is read off it: journey exists = departure in the issue set of the origin; arrival = the
`witness` arrival. Timed over **all cases of the cache** (the natural unit of this method: it answers every departure
second of every origin of a spec at once).

**c. MARGIN**: the margin field of `research/kcf-idea-routing` (`margin_field.field.margin_field`, fast path, pure
Python, default settings, acceptance variant `keep`). Same specs, same instances, same cases.
* **MARGIN-1** (one margin): `margin_field(inst, 60)`; each case read at margin 60 s (`issue_set_at`), with the
  arrival from the witness of `field_at(fld, 60)`.
* **MARGIN-10** (ten margins): one `margin_field(inst, 600)`; each case read at the ten margins
  `round(600 i / 9)`, i = 0..9 (0, 67, 133, 200, 267, 333, 400, 467, 533, 600). Decisions only, no witnesses.
  Margin 0 is one of the ten, so MARGIN-10 also answers the original question.

**Timed region of FIELD and MARGIN**: instance construction, the preconditions, the field pass, the read-off of every
case. Not timed: reading the cases file, the accuracy comparison, `check_fixed_point`, and the independent route check
(F-3.1's `full_check`). Because OLD's answer includes a whole-road check of its route and FIELD's does not, a separate
row times FIELD plus `full_check` on the witnesses of the OLD sample cases (section 7, row "FIELD + route check").

**Cold and warm for FIELD and MARGIN**: one fresh process per (method, cache, repeat). The first timed pass is **cold**: it
includes building `PacketModel` (graph and packet load, rule tables). A second timed pass in the same process, with
everything loaded and warmed, is **warm**. So each process gives one cold and one warm number; five processes give five
of each.

**Reported alongside, not claimed:** the recorded per-check compute times in the caches (sum 147,900 s on the Mac with
13 workers) are context only. They are not used in any ratio.

## 4. Repeats and order

* At least 5 repeats of every (method, cache, mode). Repeat-major order: repeat 1 runs all six caches, then repeat 2,
  and so on; the cache order is rotated each repeat and the method order within a cache is reversed on even repeats, so
  slow drift hits every method alike.
* A block is: one FIELD process, one MARGIN-1 process, one MARGIN-10 process, OLD cold on the 200 cases, OLD warm on the
  200 cases (priming request first, untimed).
* Per-case OLD times, per-process FIELD/MARGIN times, probe values and load readings are all kept (`results/*.jsonl`,
  append-only, resumable). A run that crashes is resumed, never silently dropped; failures are counted in BENCH.md.

## 5. Memory

* FIELD and MARGIN: peak resident set of the process (`ru_maxrss`, which is the kernel's high-water mark) at the end of
  the cold pass and at the end of the warm pass, and the resident set just after `PacketModel` is built and the cases
  are loaded (baseline, before any field). Increment = peak minus baseline. One process covers a whole cache.
* OLD: worker maximum resident set per case from `/usr/bin/time -v`; median and maximum over the 200 cases. One worker
  process handles one case.
* These are not the same thing (a one-case process against a whole-cache process); both are reported and the ratio is
  given as peak over peak, and as peak over peak at the same unit of work where that can be formed (FIELD per spec).
  No `tracemalloc` is used while timing.

## 6. Accuracy

* **b and c against a, on every case a decides** (the 200-case sample of each cache, cold run of repeat 1): OLD
  `checked_route` must be "journey exists" and OLD `model_no_route` must be "no journey" in FIELD, and in MARGIN at
  margin 0 (taken from MARGIN-10 and from a MARGIN pass with M = 0). For checked cases the arrival second is compared
  too. Reported: cases, decided, agreed, disagreed (each listed), unresolved by OLD, and OLD's repeatability (the 5
  repeats must give the same verdict on every case; any flip is listed).
* **b against c at margin 0, all cases of every cache** (about 9,722): every case's answer and arrival, and the issue
  set of every origin of every spec.
* **c at a non-zero margin against b run on the widened instance** (the existing field on `widen(inst, m)`, which is the
  definition of the margin answer): for MARGIN-1 (m = 60) and for all ten margins, on all cases of the specs of the 200
  sample cases of each cache. This check is outside every timed region and is run once.
* **Sampling uncertainty of the scaled OLD time**: a 95% bootstrap over the 200 sampled cases (10,000 resamples) of the
  per-case mean time, reported next to the repeat range. The two intervals are different things and are not merged.

## 7. What is reported

One table in `BENCH.md` with, per cache and method (OLD scaled, FIELD, MARGIN-1, MARGIN-10) and per mode (cold, warm):
wall time median and range over repeats, peak memory, and agreement. Then ratios OLD / FIELD, OLD / MARGIN-1,
OLD / MARGIN-10, FIELD / MARGIN-1, FIELD / MARGIN-10, each as median with a range
`[min OLD / max NEW, max OLD / min NEW]` (the widest interval the repeats allow). Extra rows: FIELD at the
200-case sample specs only (the worst case for a field, which pays per spec however few cases it answers), and
FIELD + route check. Machine, operating system, Python version, commits and the probe log are recorded in `BENCH.md`.

## 8. What counts as a win

All statements are per cache and per mode (cold, warm) and are about this machine and these six caches.

* **Time.** A new method is **faster** than a comparison method on a cache if the lower end of the ratio range is above
  1. It is **slower** if the upper end is below 1. Otherwise **not distinguished**. A headline of "faster" needs
  "faster" on all six caches, in both cold and warm, against the method named. Where a method is slower on any cache or
  mode, `BENCH.md` says so in the table's own words and in the five `TALK_NUMBERS` lines.
* **Accuracy.** A win needs zero disagreements: FIELD and MARGIN at margin 0 against every decided OLD case, FIELD
  against MARGIN at margin 0 on every case, and MARGIN at each non-zero margin against the widened existing field. One
  disagreement anywhere means no accuracy win; it is listed and described.
* **Memory.** Reported with ranges and no pass or fail rule. Where a new method needs more, `BENCH.md` says so.
* No claim for other machines, other caches, compiled implementations (numba is not installed; none is timed), or the
  scaled OLD time beyond its stated intervals.

## 9. What had been seen when this was written

Not blind. Before this commit:
* one OLD request (UA 03-23, job `rc_006f70fffb6d41c0b3f9`) run once here as a smoke test: 6.7 s wall, 303 MiB, verdict
  `checked_route`, arrival 2,172 s, equal to the recorded route's verdict;
* the published numbers of the branch `research/kcf-idea-routing` (BENCH.md, round 1, on a Mac) for FIELD against
  MARGIN: MARGIN slower than FIELD for one field on the three Yeongdeok caches (0.55 to 0.61), faster from 2 margins up;
* F-3.1's `RESULTS.md`: FIELD reproduced every recorded route and no-route, 0 disagreements, field time 42 to 379 s per
  cache on a loaded container.
Harness development runs will be made after this commit. Their timings are discarded and their output directory is
deleted before the benchmark starts; the benchmark itself starts from an empty `results/` and a fresh run id.

## Amendments

* **A1, 19 Nov 2026, before any timing run (harness development runs only, discarded).** Two additions, no change to
  any rule above.
  (i) Method **FIELD-D** (`field_dec`): FIELD with decisions only, no witness extraction. It is the like-for-like
  comparator of MARGIN-10, which also gives decisions only; FIELD (with witnesses) stays the comparator of MARGIN-1 and
  of OLD. Same repeats, same cold/warm rule. Other extra rows are named `field_sample` (FIELD, witnesses, on the specs
  of the 200 sample cases and answering only those cases) and `field_check` (`field_sample` plus `full_check` on every
  witness), as in section 7.
  (ii) An untimed memory probe (`run_field.py --memprobe`): resets the kernel's peak counter before each spec and records
  the peak after it, to give peak memory per spec for FIELD and MARGIN. It never runs inside a timed task.
