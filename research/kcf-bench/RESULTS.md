# kcf-bench RESULTS: method A against method B on one machine (time, memory, accuracy)

Protocol: `PLAN.md` (frozen at `0fdcbb28`), Amendments 1–4 at its end. All numbers come from files under `runs/`;
`results/RESULTS.json` is the machine-readable summary (`summarize.py`). Written Fri 20 Nov 2026, before 12:00 Shanghai.

* **A** = the recorded per-departure method: `api/runner.py::execute`, candidate route by the kit (`RDA_CAND`, 30 s
  budget) plus the full-journey check, one job at a time (`run_a.py`).
* **B** = the F-3.1 deadline field, `cert` rule: one `deadline_field.core.backward` per destination spec, each job read
  off it with an issue set and a witness (`run_b.py`).

## The table (method by cache)

Time for **A** is per job, measured on the jobs A ran: median, with its 95% bootstrap interval (10,000 resamples). Time
for **B** is per run, over the whole cache: median of 3 repeats, with the range in brackets. Memory is the peak
resident set of the largest single process, measured the same way for both (`measure.py`, `RUSAGE_CHILDREN`). For A
it is the maximum over its pass-1 processes. For B it is the maximum over its 3 full-cache repeats. Agreement covers
every job A ran (section 3).

| cache | edges | jobs (A ran / cache) | A wall per job, s | A CPU per job, s | B wall, whole cache, s | B CPU, whole cache, s | A peak MiB | B peak MiB | same verdict | same departure s | routes valid A / B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| UA 03-23 | 43,826 | 500 / 1,523 | 5.29 (5.11–5.48) | 6.15 (5.94–6.35) | 13.7 [13.6–14.7] | 13.6 [13.5–14.6] | 777 | 437 | 500 / 500 | 500 / 500 | 390/390, 390/390 |
| UA 03-24 | 43,826 | 1,093 / 1,518 | 5.18 (5.07–5.35) | 6.06 (5.93–6.26) | 85.4 [78.1–108.6] | 84.8 [77.6–105.7] | 746 | 659 | 1,087 / 1,093 | 1,093 / 1,093 | 819/819, 819/819 |
| UA 03-25 | 43,826 | 500 / 1,557 | 6.60 (6.25–6.97) | 7.62 (7.22–8.05) | 50.0 [46.3–65.6] | 49.3 [46.0–64.3] | 931 | 796 | 470 / 500 | 500 / 500 | 337/337, 337/337 |
| YD 03-25 19Z | 111,924 | 500 / 1,810 | 10.98 (10.86–11.16) | 12.66 (12.54–12.86) | 157.9 [138.5–159.9] | 155.1 [137.8–157.4] | 1,463 | 1,002 | 483 / 500 | 500 / 500 | 421/421, 421/421 |
| YD 03-25 23Z | 111,924 | 500 / 1,673 | 9.36 (9.30–9.43) | 10.81 (10.74–10.88) | 159.4 [142.5–176.9] | 157.3 [142.1–172.4] | 1,217 | 680 | 500 / 500 | 500 / 500 | 456/456, 456/456 |
| YD 03-26 | 111,924 | 500 / 1,641 | 9.13 (9.08–9.23) | 10.61 (10.51–10.71) | 177.7 [163.8–182.5] | 174.3 [163.1–176.9] | 1,011 (resumed part only) | 734 | 485 / 500 | 500 / 500 | 463/463, 464/464 |
| **all** | | **3,593** | | | | | | | **3,525 / 3,593** | **3,593 / 3,593** | **2,886/2,886, 2,887/2,887** |

Per-job means, with 95% intervals:

| cache | A mean wall per job, s | A mean CPU per job, s |
|---|---|---|
| UA 03-23 | 5.77 (5.59–5.96) | 6.74 (6.52–6.97) |
| UA 03-24 | 5.74 (5.62–5.86) | 6.74 (6.60–6.89) |
| UA 03-25 | 7.41 (7.12–7.71) | 8.55 (8.21–8.90) |
| YD 03-25 19Z | 11.46 (11.24–11.69) | 13.20 (12.95–13.47) |
| YD 03-25 23Z | 9.74 (9.60–9.89) | 11.25 (11.08–11.42) |
| YD 03-26 | 9.47 (9.31–9.63) | 10.98 (10.79–11.17) |

Measured A wall totals (no total is extrapolated):

| cache | jobs | A wall, s |
|---|---|---|
| UA 03-23 | 500 | 2,887 |
| UA 03-24 | 1,093 | 6,275 |
| UA 03-25 | 500 | 3,705 |
| YD 03-25 19Z | 500 | 5,729 |
| YD 03-25 23Z | 500 | 4,870 |
| YD 03-26 | 500 | 4,734 (sum of per-job wall, see Amendments 2–3) |

**Memory, plainly.** B's peak memory did **not** exceed A's on any cache. B's full-cache peak (437–1,002 MiB) is below
A's largest single process (746–1,463 MiB) on all six caches. It is also below on the identical job sets: B's peak on
A's pass-1 job set was 444–736 MiB. A runs two processes at once (worker and kit child), so A's concurrent tree can
reach more than its largest single process: the upper bound worker + largest kit child is 1,137–2,016 MiB.

One caution on memory: in the excluded smoke test (3 jobs), B's peak (418 MiB) was above A's (396 MiB). On a handful
of jobs, B's fixed cost (graph, packet, field) can therefore outweigh A's.

## 1 Speed ratio, only on jobs both methods ran

Each ratio is A's measured time for a job set divided by B's measured time for the **identical** job set. B's time is
the median of 3 repeats. A ran its job set once (pass 1).

| cache | jobs | A wall, s | B wall, s (median [range]) | ratio wall | ratio CPU | basis |
|---|---|---|---|---|---|---|
| UA 03-23 | 500 | 2,887 | 13.9 [12.9–15.6] | **208×** | 247× | A process wall/CPU |
| UA 03-24 | 1,093 | 6,275 | 50.3 [49.9–51.0] | **125×** | 147× | A process wall/CPU; B run on the same 1,093 jobs (Amendment 4) |
| UA 03-25 | 500 | 3,705 | 16.7 [16.0–22.8] | **222×** | 259× | A process wall/CPU |
| YD 03-25 19Z | 500 | 5,729 | 132.4 [125.0–156.4] | **43×** | 50× | A process wall/CPU |
| YD 03-25 23Z | 500 | 4,870 | 143.6 [135.5–149.1] | **34×** | 40× | A process wall/CPU |
| YD 03-26 | 500 | 4,734 | 188.6 [145.7–194.8] | **25×** | 30× | sum of A per-job wall/CPU (A's first process never wrote its measure file, Amendment 2) |

The ratio depends on how many jobs share a destination spec, because B pays one field per spec. In the UA samples, 500
jobs fall on about 31 specs; in the YD samples they fall on up to 152 specs. On a smaller set B's fixed start-up (load
cache, packet model) weighs more. The 50-job repeat sets show this:

| cache | A wall, repeat 1 (pass 1) | A wall, repeat 2 | B wall, 3 repeats | ratio, repeat 1 | ratio, repeat 2 |
|---|---|---|---|---|---|
| UA 03-23 | 308 s | 277 s | 7.8 s [7.7–8.3] | 39× | 35× |
| UA 03-24 | 375 s | 252 s | 11.4 s [11.3–14.7] | 33× | 22× |

**No total ratio over all jobs is claimed.** A ran 3,593 of 9,722 jobs, and an all-cache figure would rest on jobs A did
not run.

## 2 Repeats of A (the deviation is stated in PLAN 7)

The plan gave A three repeats on each cache's 50-job repeat set. Disk stops cost time, and the 09:15 stop ended the
repeat phase. **Only UA 03-23 and UA 03-24 have a second complete repeat; no cache has a third.**
* UA 03-25 has 8 of 50 jobs in repeat 2. The other caches have none.
* Per-job medians on the repeat sets:

  | cache | repeat 1 | repeat 2 | same verdict in both |
  |---|---|---|---|
  | UA 03-23 | 5.59 s | 4.60 s | 50 / 50 |
  | UA 03-24 | 6.97 s | 4.64 s | 50 / 50 |

* A's per-job time moves by up to about a third between repeats. The 1-minute load average was 13.2 (median) during
  UA 03-24 repeat 1 and 3.5 during repeat 2.
* B's three repeats on the full caches differ by up to 39% (UA 03-24: 78–109 s), also under load.

## 3 Accuracy (every job A ran, against B's full-cache repeat 1; checker `deadline_field.verify.full_check`, unchanged)

* **Departure second:** equal on **3,593 / 3,593** jobs.
* **Verdict:** same on **3,525 / 3,593**. **68 disagreements**, listed below.
* **Jobs both call `checked_route`** (2,886):
  * same arrival second on **2,886 / 2,886**;
  * identical leg sequence on **2,886 / 2,886**.
* **Route validity under the unchanged checker:**
  * A's 2,886 routes are all valid. Legs were rebuilt with `reconstruct_legs`, and each hash matched A's `route_sha256`.
  * B's 2,887 routes are all valid.
  * No route of either method failed the checker. No job had exactly one valid route.
* **Every disagreement is A `unresolved` while B decides.** These form the sub-count named in PLAN 5:
  * **67** are A raw status `AT_ISSUE_FAILURE`, where B says `model_no_route`. The recorded cache result for each of
    these is also `unresolved`, so A reproduced its recorded answer. B resolves them as no-route, as in F-3.1, where
    all 297 recorded unresolved jobs were decided.
  * **1** (YD 03-26 `rc_130cceebb834401c94e1`) is A `UNRESOLVED / WORKER_ERROR`: the kit child exited with code 120
    after 4.2 s, with no memory guard and no deadline stop. B says `checked_route`, and its route passes the checker.
    **The recorded result is `checked_route`.** On this one job, A failed on this machine where it had succeeded
    when recorded.
* **A against the recorded cache verdicts:**

  | cache | same as recorded |
  |---|---|
  | UA 03-23 | 500 / 500 |
  | UA 03-24 | 1,093 / 1,093 |
  | UA 03-25 | 489 / 500 |
  | YD 03-25 19Z | 457 / 500 |
  | YD 03-25 23Z | 487 / 500 |
  | YD 03-26 | 495 / 500 |

  This is context, not part of the A-against-B test (see `compare/*.json`, `recorded_verdict`).

### The 68 disagreements

| # | cache | job | depart (s) | A verdict (raw status / reason) | B verdict | recorded | A wall (s) |
|---|---|---|---|---|---|---|---|
| 1 | UA0324 | `rc_decca81d3ed4450e8c50` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 2 | UA0324 | `rc_650da339b71b4e1e90e8` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.9 |
| 3 | UA0324 | `rc_2d8dd550ed0041069f7a` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.5 |
| 4 | UA0324 | `rc_5be11ffc9fb3480f88cb` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 2.7 |
| 5 | UA0324 | `rc_985a3f755c384c44b2ce` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 2.6 |
| 6 | UA0324 | `rc_7a8e92545daa4957b603` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 2.6 |
| 7 | UA0325 | `rc_7e921bb72f204a0aafac` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.5 |
| 8 | UA0325 | `rc_7f450581295a4488a575` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.5 |
| 9 | UA0325 | `rc_bcc636a104b74a22b2c0` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 10 | UA0325 | `rc_195bf9e9358242fb8c76` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 11 | UA0325 | `rc_ce79bafa05ff4490bc3b` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 12 | UA0325 | `rc_6b05ffcede414b82a7bf` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 13 | UA0325 | `rc_58a838f891474dae8eb4` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.4 |
| 14 | UA0325 | `rc_c93ab852ae894edcbcea` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 15 | UA0325 | `rc_954538be16f3416797b1` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 16 | UA0325 | `rc_aeee5448ed234183ab62` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 17 | UA0325 | `rc_27c166cc36a14c8b92a6` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 18 | UA0325 | `rc_d268444613e4452f8015` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 19 | UA0325 | `rc_e024f21db0b64f3ca7eb` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 20 | UA0325 | `rc_ab39aa57d74e4d34818c` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 21 | UA0325 | `rc_f2615abb379d46d29402` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 22 | UA0325 | `rc_2526d7509d824f14be2b` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 23 | UA0325 | `rc_e84ab1e5181946f6afa4` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 24 | UA0325 | `rc_2ad70b08ebe54d738976` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 25 | UA0325 | `rc_dd2fc78e5252436899b8` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 26 | UA0325 | `rc_1ab2a9ac87bd435a9c03` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 27 | UA0325 | `rc_d15174c723964b21965b` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 28 | UA0325 | `rc_3abcdd5918394f86b6c8` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 29 | UA0325 | `rc_166f54ec59014005983b` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 30 | UA0325 | `rc_3e6c4438ad17453fa4ec` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 31 | UA0325 | `rc_04ab1ecf1abb40a1a51f` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 32 | UA0325 | `rc_b1f3796beafc47d5af42` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 33 | UA0325 | `rc_adf35e2b5ff8492bb03a` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.2 |
| 34 | UA0325 | `rc_0d7e7d1ff5c8433da040` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 35 | UA0325 | `rc_01f418744b54427a99a7` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 36 | UA0325 | `rc_eb32aaa10d604d01b8f2` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 3.3 |
| 37 | YD0325T19 | `rc_c5658c02c06f45d39180` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 38 | YD0325T19 | `rc_c1d27736f0dd4af8bf56` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.8 |
| 39 | YD0325T19 | `rc_90f8617e41104045ab3c` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 40 | YD0325T19 | `rc_14c8da26365744448616` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 41 | YD0325T19 | `rc_ce86855b2549466d9b5b` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.1 |
| 42 | YD0325T19 | `rc_fc02841bec9545d4a6d2` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 43 | YD0325T19 | `rc_0d532a2a952340f6a941` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 44 | YD0325T19 | `rc_05a6bdd7f2aa45fa8092` | 2400 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 45 | YD0325T19 | `rc_1cbcb43239f74274bab3` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.2 |
| 46 | YD0325T19 | `rc_2aa8e35c260842d9b987` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.9 |
| 47 | YD0325T19 | `rc_cded4def2f024ef3aa06` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 48 | YD0325T19 | `rc_98040d19ef454a179a0f` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 49 | YD0325T19 | `rc_cd6b7fcd45594f6ab87d` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.9 |
| 50 | YD0325T19 | `rc_2822f11473a54e14adc8` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.9 |
| 51 | YD0325T19 | `rc_9085dd107287482ca81d` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.9 |
| 52 | YD0325T19 | `rc_b8b0fc7349be416fba93` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 53 | YD0325T19 | `rc_1d516dd8e7ae457ea514` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 6.0 |
| 54 | YD0326 | `rc_902e74ec0aba4881b571` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.3 |
| 55 | YD0326 | `rc_6087115a298b4252b11f` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.4 |
| 56 | YD0326 | `rc_a7c17ad9dc3b48e3a592` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.4 |
| 57 | YD0326 | `rc_692d15479b5e4ecd93e4` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.4 |
| 58 | YD0326 | `rc_a78b29b7fffa46c88151` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.4 |
| 59 | YD0326 | `rc_8794f66267234d24bfe3` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.3 |
| 60 | YD0326 | `rc_7620f18d352344e6a627` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.2 |
| 61 | YD0326 | `rc_130cceebb834401c94e1` | 3000 | unresolved (UNRESOLVED / WORKER_ERROR) | checked_route | checked_route | 5.4 |
| 62 | YD0326 | `rc_c6cfe24a914a4de1bc5a` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.6 |
| 63 | YD0326 | `rc_1776e660ee964a28a5a1` | 3000 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.7 |
| 64 | YD0326 | `rc_3a3fb298599a4d3a8d7e` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.4 |
| 65 | YD0326 | `rc_82d0c17825bd4050a2a4` | 0 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.7 |
| 66 | YD0326 | `rc_71e8bd17f98542a18160` | 1200 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.2 |
| 67 | YD0326 | `rc_2e4a85ee8a734eaf97f2` | 600 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.5 |
| 68 | YD0326 | `rc_fd3439fe1cdc47e3a73d` | 1800 | unresolved (AT_ISSUE_FAILURE / AT_ISSUE_FAILURE) | model_no_route | unresolved | 5.5 |

## 4 Scaling of B with graph size

The caches are the measured B full-cache runs above, at 43,826 and 111,924 directed edges. The synthetic graphs are
grids from `synth.py` (seed 20261120), each with 5 destination specs and 100 origins. Each synthetic grid ran once
and finished all 5 specs.

| graph | directed edges | specs | B wall, s | B CPU, s | B peak MiB | backward field per spec, s |
|---|---|---|---|---|---|---|
| UA 03-23 / 03-24 / 03-25 | 43,826 | 31–32 | 13.7 / 85.4 / 50.0 | 13.6 / 84.8 / 49.3 | 437 / 659 / 796 | — |
| YD 03-25 19Z / 23Z / 03-26 | 111,924 | 152–153 | 157.9 / 159.4 / 177.7 | 155.1 / 157.3 / 174.3 | 1,002 / 680 / 734 | — |
| synthetic grid side 250 | 249,000 | 5 | 17.7 | 17.4 | 424 | 2.05, 1.82, 1.64, 1.36, 1.36 |
| synthetic grid side 354 | 499,848 | 5 | 20.9 | 20.6 | 571 | 2.06, 2.79, 3.49, 3.67, 3.25 |
| synthetic grid side 500 | 998,000 | 5 | 27.9 | 27.4 | 1,072 | 4.38, 4.44, 3.48, 3.64, 2.56 |

Across the synthetic grids, a 4× increase in edges raised B's peak memory 2.5× and its backward time per spec about
2×. The fire is synthetic, so these graphs test size only, not hazard realism. The caches have far more destination
specs per run (31–153) than the grids (5). Cache run times therefore scale with the number of specs, not with edges.

## 5 Machine, software, commits

* **Machine:** Apple M5 Pro, 15 cores (5 performance + 10 efficiency), 24 GB RAM. macOS 27.0.1 (26A434), arm64.
* **Software:** Python 3.13.13 (conda-forge, `/Users/jp/miniforge3/bin/python3`) for both methods. numpy 2.5.0,
  pyproj 3.7.2, scipy 1.18.0, shapely 2.1.2. `PYTHONHASHSEED=0`.
* **Commits:**
  * Method A: last commit touching `api/` and `integration/` is `5fa19a27`. The recorded A checks in the caches came
    from `f8765a68` (API 1.8.0, Python 3.12.1, 13 workers).
  * Method B: `deadline_field` at `37e96645`.
  * Benchmark harness: base `5a31155d`, plan `0fdcbb28`, amendments `740af12c`, `ab0ebe10`, `390b1bc1` and
    `0bb3984f` (Amendment 4).

## 6 What was not as planned (read before quoting)

* **The machine was not idle.** It was the user's working Mac. The 1-minute load average before B's runs was 2.8–10.4.
  During A jobs the median load per cache was 2.6–6.1, and the maximum reached 34.3 (UA 03-24). Load is recorded per
  run and per job; no run was dropped for it.
* **The disk filled three times**, from something other than this harness: one A job uses about 1 MB, and `runs/` is
  under 100 MB. The consequences:
  * **04:20:** 39 YD 03-26 jobs failed with `No space left on device`. They are set aside in
    `runs/a/YD0326.pass1.enospc_excluded.jsonl` and are not A results. The same jobs were rerun later and are in the
    sample. YD 03-26's first A process lost its measure file, so its process-level wall, CPU and peak are missing.
  * **06:06:** the 300 MiB free-disk guard stopped A cleanly.
  * **During the repeats:** the disk filled again. The repeat phase also had about 49 minutes between processes with
    no job running (07:57–08:46), which this harness does not explain.

  See Amendments 2–4. Amendment 3 says the 6-job resume process's measure file was lost. It was kept, in
  `runs/excluded_guard_stops/`, and is not used; those 6 jobs' per-job times are in the sample.
* **UA 03-24 was not run in full by A.** The 07:45 stop came at 1,093 of 1,518 jobs, in permutation order, so the
  1,093 are a random sample.
* **A's repeats are incomplete** (section 2).
* **One overlap with my own process.** A stray run of `summarize.py`, started by mistake and stopped within about a
  minute, overlapped A's YD 03-26 jobs at sample positions 218–221 (about 22:05:30–22:06:10 UTC). Those 4 jobs are
  kept and flagged here.
* **Python version.** Python 3.13.13 is not the recorded 3.12.1. A's kit ran unchanged under it.
