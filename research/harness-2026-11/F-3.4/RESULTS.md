# F-3.4 phase profile of the frozen 20-mission routing workload (interim)

Status: **measured; verified PASS WITH NOTES by Mira (12 Nov, @ b6c94bb)**, from 3+1 fresh runs plus the committed
rows. Data: `results/primary_b81_3rep/` (primary) and
`results/extended_b300_1rep/` (extended budget, one repetition). A clean rerun meeting Iris's acceptance criteria is
queued: five cold and five warm repetitions, per-phase memory, and the 30 s budget plus an uninstrumented control.
It will be added as `results/clean_*`.

## What was measured

- **Workload.** The 20 missions of the frozen request-window panel (`LATEST_PRIMARY` queue order), arm `RDA_CAND`,
  with the kit built by `experimental/window-routing/build_kit.py`. Inputs are the recorded packets
  (`tools/fetch_routing_inputs.py`, 132 files verified).
- **Execution path.** Each execution runs through the kit's own controller (`wfg_controller.run_attempt`, GNU
  `time -v`, family RSS sampler, verified cleanup, outer complete deadline), with the job built exactly as
  `wfg_latest.api.route_and_check` builds it. The offline independent checker is excluded, as in the frozen protocol.
- **Instrumentation.** `phase_worker.py` is launched in place of the worker. It runs the unmodified worker file
  through `runpy`, so the worker's own module-hash checks still pass. It adds `perf_counter` wrappers on named
  functions and an import hook. Phases are exclusive and sum to the controller's launch-to-completion wall time; the
  remainder is reported as *unattributed*.
- **Host.** x86-64 Linux container, 4 vCPU, Python 3.12.3, NumPy 1.26.4. Executions are sequential and nothing else
  ran during the primary run.
- **Budget.** The evaluated budget is 30 s on an Apple laptop. This host is about 2.6–2.8× slower on missions that
  never hit a cap. For example, Uljin FX1 takes 32.9 s here against 12.45 s in the macOS record, and Uiseong FX2 13.5 s
  against 4.97 s. The worker sizes its later search stages (LO/LO2/HI) as fractions of the remaining budget, so an
  arbitrary extended budget changes the work done: at 300 s, Yeongdeok FX2 spent 135 s in search. The primary profile
  therefore uses a **speed-equivalent budget of 81 s** (30 s × 2.7).

## Result (primary: 81 s, cold preparation, 3 repetitions, 60 executions, 1,304 s total)

| Phase group | Share of total wall | Median per execution | Max |
|---|---:|---:|---:|
| Route-check radiation (dose/peak enclosure) | **31.3%** | 1.24 s | 28.8 s |
| Search (Z sweep, EA bound, LO/LO2/HI) | 38.1% | 1.61 s | 67.4 s |
| Per-forecast admission and models (graph preparation, hazard validation, bound model, contact-source and radiation preparation) | 18.3% | 2.10 s | 13.6 s |
| Route-check contact | 2.5% | 0.22 s | 2.1 s |
| Input load and hash binding | 1.7% | 0.20 s | 1.4 s |
| Publication, finalization, exit | 4.7% | 0.74 s | 4.3 s |
| **Start-up and imports** (launch, interpreter, module imports and hash checks) | **0.8%** | 0.15 s | 0.32 s |
| Hazard validation alone | 0.1% | 0.02 s | 0.15 s |
| Unattributed | 2.5% | 0.19 s | 20.2 s |

Coverage: 59 of 60 executions have ≥95% of their wall time attributed, and 97.5% of total wall time is attributed.
The exception is a Yeongdeok FX2 deadline stop at 75%, because a stopped run writes no publication boundary.

Per mission, median of 3 repetitions (seconds; CV is that of complete wall):

| Mission | Outcome | Wall | CV | Radiation (share) | Search | Admission and models | Contact | Start-up |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| hongseong 0700 FN1 | refusal proven | 0.58 | 0.166 | 0 | 0.22 | 0.14 | 0 | 0.13 |
| hongseong 0700 FX1 | refusal proven | 0.63 | 0.074 | 0 | 0.22 | 0.13 | 0 | 0.14 |
| hongseong 1400 FW2 | route, optimum proven | 29.82 | 0.010 | 28.70 (96%) | 0.26 | 0.24 | 0.07 | 0.14 |
| hongseong 2300 FD1 | route, optimum proven | 16.85 | 0.020 | 16.10 (96%) | 0.11 | 0.20 | 0.03 | 0.13 |
| miryang 0531 FN1 | route, optimum proven | 28.68 | 0.002 | 27.56 (96%) | 0.24 | 0.31 | 0.03 | 0.15 |
| miryang 0601T02 FW1 | route, optimum proven | 15.23 | 0.035 | 14.17 (93%) | 0.22 | 0.27 | 0.03 | 0.15 |
| miryang 0601T08 FD1 | refusal proven | 0.79 | 0.042 | 0 | 0.35 | 0.17 | 0 | 0.13 |
| miryang 0601T08 FX1 | refusal proven | 0.83 | 0.033 | 0 | 0.39 | 0.20 | 0 | 0.13 |
| uiseong 0323 FD1 | route, optimum proven | 13.93 | 0.018 | 1.13 (8%) | 3.29 | 5.17 | 1.36 | 0.19 |
| uiseong 0323 FX2 | route, optimum proven | 14.00 | 0.103 | 2.11 (15%) | 3.37 | 5.29 | 0.93 | 0.18 |
| uiseong 0324 FL2 | route, optimum proven | 14.93 | 0.016 | 1.61 (11%) | 3.81 | 5.06 | 1.58 | 0.17 |
| uiseong 0325 FW1 | route, optimum proven | 16.54 | 0.035 | 0.95 (6%) | 4.02 | 8.15 | 1.08 | 0.16 |
| uljin 0300 FD1 | route, optimum proven | 17.82 | 0.035 | 12.93 (73%) | 1.21 | 2.27 | 0.44 | 0.15 |
| uljin 0300 FX1 | route, optimum proven | 32.48 | 0.009 | 25.40 (78%) | 2.01 | 2.08 | 1.11 | 0.14 |
| uljin 0600 FL1 | route, optimum proven | 7.94 | 0.011 | 1.21 (15%) | 2.01 | 2.10 | 0.81 | 0.15 |
| uljin 1200 FW2 | route, optimum proven | 6.92 | 0.013 | 1.96 (28%) | 0.91 | 2.12 | 0.54 | 0.15 |
| yeongdeok 0325T19 FD1 | refusal proven | 38.09 | 0.045 | 0 | 25.06 | 10.44 | 0 | 0.25 |
| yeongdeok 0325T19 FX2 | **unresolved (81 s deadline)** | 81.22 | 0.018 | 0 | 66.87 | 10.11 | 0 | 0.26 |
| yeongdeok 0325T23 FL2 | route (2 reps feasible, 1 optimum) | 72.89 | 0.063 | 1.31 (2%) | 50.30 | 12.93 | 1.98 | 0.24 |
| yeongdeok 0326 FW1 | route, optimum proven | 21.51 | 0.041 | 0.31 (1%) | 3.98 | 11.93 | 0.45 | 0.23 |

## Which efficiency direction (claim, pending verification)

- **Not a persistent service.** Start-up and imports are 0.8% of wall time, with a median of 0.15 s per request.
- **Not per-forecast hazard validation.** `validate_hazard` is 0.1%. Per-forecast admission and models together are
  18%, mostly graph preparation and bound or source models on the large Uiseong and Yeongdeok graphs. The kit's
  authenticated prepared-graph cache already addresses graph preparation; the warm runs will measure it.
- **The cost is the exact-rational radiation enclosure on the published route.** On the 7 routed missions whose
  hazard is present fire only, or nearly so (Hongseong, Miryang, Uljin 0300), it is **73–96% of wall time**. A cProfile of Uljin
  FX1 puts about 88% of that time in `RationalKernel.corner`, the `Fraction` atan series, where `math.gcd` alone is
  about 11.5 of 30 profiled seconds. The constraint it certifies is far from binding: on the 15 routes, the dose upper
  bound is at most 0.33 of budget and the peak at most 0.0005 of budget. Same-forecast request pairs share 0 road
  edges, so a per-forecast cache of route checks would not be reused across them.
- **On the large graphs, search dominates** (Yeongdeok 25–67 s), and Yeongdeok FX2 does not resolve at 81 s here.
- Next step, approved by the orchestrator and Iris, test-first, as an opt-in kit only:
  - A: a certified two-tier enclosure. The existing outward binary64 radial tier decides when it can, guarded at half
    the budget; the exact tier runs otherwise. It requires zero nesting violations over the 80 executions and a
    property test.
  - B: dyadic outward snapping of receiver boxes, so that corners repeat and stay exact.

## Host findings (their own result; specific to THIS host, not to Linux in general)

- **GNU time is required.** The kit's controller runs `/usr/bin/time -v`; without it every route check fails. The
  container image lacked it (`apt-get install time`). `make api-tools` only warns about this.
- **The evaluated 30 s budget does not transfer to this host.** Here, at 30 s, Uljin FX1 times out (wall 30.17 s, still
  inside the whole-road check) although it reproduces the recorded route, arrival 3,119 s, in about 33 s. The full
  30 s run is queued. Mira's container (also x86-64 Linux, Python 3.12.3) is about 2.0× slower than the Mac, and
  there Uljin FX1 completes at 30 s in 24.3 s. Host speed, not the OS, decides this, and the speed-equivalence factor
  (2.7× here) must be measured on each host.
- **Cross-host packet bytes differ.** Rebuilt packets match the frozen ones exactly in arrays, flame sets, breakpoints
  and ids. HAZARD.json flux differs by at most 2.3e-9 relative, from FFT rounding (arm64 macOS vs x86 Linux). Compare
  on the integer instance and on verdicts.

## Not verified / limitations

- Mira verified this profile on 3 missions plus a plain-mode control, and recomputed the committed 60 rows. She did
  not rerun all 60 executions.
- Per-phase memory is not in this run; the harness gained memory capture afterwards. Warm-cache timings are not in
  this run either. Both come from the clean rerun.
- The instrumentation overhead control in the plain runs so far was contended; a clean control is queued.
- Shares on the evaluated macOS host and budget may differ.
- cProfile shares are inflated by profiling overhead and indicate only where time goes.

## Reproduce

```sh
python3.12 -m venv .venv && .venv/bin/pip install -c constraints-routing.txt './integration[packets]' -r api/requirements.txt
.venv/bin/python tools/fetch_routing_inputs.py          # needs GNU time installed for the runs below
.venv/bin/python -B experimental/window-routing/build_kit.py --out /tmp/wkit
# quick (~3 min): one radiation-heavy and one search-heavy mission
.venv/bin/python research/harness-2026-11/F-3.4/run_profile.py --kit /tmp/wkit --out /tmp/f34q --reps 1 --budget 81 \
    --only uljin_2022__20220304T030000Z_FX1,uiseong_andong_2025__20250323T010000Z_FX2,hongseong_2023__20230402T230000Z_FD1
.venv/bin/python research/harness-2026-11/F-3.4/summarize.py /tmp/f34q/ROWS.jsonl
# full primary (~22 min per repetition on this host)
.venv/bin/python research/harness-2026-11/F-3.4/run_profile.py --kit /tmp/wkit --out /tmp/f34 --reps 3 --budget 81
```
