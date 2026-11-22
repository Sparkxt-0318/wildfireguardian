# TALK_NUMBERS: what the presenter can say, and where it comes from

Built from `Main` at PR #188 (`9dbe458`); sections 8–13 added from Main at PR #220. Every value is copied from a committed file; nothing is recomputed. The hash in each row is the last commit that touched the cited file (`git log -1 -- <file>`). **UNTRACED** = no committed file holds it. All results are model-relative, and none is a field validation. Hard stop: Thu 19 Nov 2026, 12:00 Shanghai.

## 1. Deadline field (F-3.1), six recorded planner caches, 1-hour panel

Files: `research/harness-2026-11/F-3.1/RESULTS.md` (§1, §2, §5) and `results/SUMMARY_final_70f70d7.json` (`jobs`, `job_mismatches`, `recorded_compute_s_sum`, `field_compute_s_cert_only`). Hashes: RESULTS.md `37e9664`, JSON `c8247d2`.

| item | value | n |
|---|---|---|
| Recorded checked routes reproduced (same arrival second, identical legs) | **7,771 / 7,771**; recorded no-routes 1,468 / 1,468 also infeasible | 9,722 jobs |
| Disagreements with any recorded route or no-route | **0** | 9,722 |
| Unresolved cases decided | **297 of 297**: 199 checked (witness passes the unchanged checker), 98 no-route proofs. They are status changes, not disagreements | 297 |
| Planner deadline equals recorded | 528 of 530 origins. The other 2 were recorded UNRESOLVED and the field resolves them | 530 |
| Recorded-check time | 147,900 s in total (RESULTS §5): 16,006 / 14,749 / 22,448 / 35,200 / 30,786 / 28,711 s, per file in the order UA 03-23, UA 03-24, UA 03-25, YD 03-25 19Z, YD 03-25 23Z, YD 03-26 | 6 files |
| Field time (`cert`, per file, same order) | 42 / 379 / 235 / 350 / 339 / 366 s | 6 files |
| **Measured on one machine (kcf-bench-mac)**: recorded method per job, median wall | **5.3 / 5.2 / 6.6 / 11.0 / 9.4 / 9.1 s** (95% intervals within ±0.4 s), same order | 3,593 jobs run (500 per file, 1,093 for UA 03-24) |
| Measured: field, whole file, median wall over 3 repeats | **14 / 85 / 50 / 158 / 159 / 178 s**, same order | 6 files, all jobs |
| Measured speed ratio, identical job sets only (recorded method ÷ field, wall) | **208× / 125× / 222× / 43× / 34× / 25×**, same order (CPU: 247× / 147× / 259× / 50× / 40× / 30×) | the 3,593 jobs both ran |
| Measured peak memory, largest single process | recorded method 777 / 746 / 931 / 1,463 / 1,217 / 1,011 MiB; field 437 / 659 / 796 / 1,002 / 680 / 734 MiB. **The field never used more memory than the recorded method** | 6 files |
| Measured agreement | same departure second 3,593 / 3,593; same verdict 3,525 / 3,593; both-checked routes with the same arrival second and legs 2,886 / 2,886; every route of both valid under the unchanged checker. The 68 differences are all recorded-method `unresolved` that the field decides (67 also unresolved in the recorded cache; 1 kit worker error on a recorded checked route) | 3,593 jobs |

Files for the measured rows: `research/kcf-bench-mac/RESULTS.md` (table, §1, §3) and `research/kcf-bench-mac/results/RESULTS.json`; protocol `research/kcf-bench-mac/PLAN.md` (Amendments 1–4).

**Does not show:** a total time over all 9,722 jobs. The recorded method was measured on 3,593 jobs, not every job, so no all-job sum or ratio is claimed, and the 147,900 s recorded total (13 workers) is not comparable with the single-process figures. The ratio varies 25–222× with how many jobs share a destination; on 50-job sets it falls to 22–39×. The machine was a working Mac under load (1-minute load 2.6–6.1 median, up to 34), with Python 3.13 instead of the recorded 3.12. The older field times above (42–379 s) are from a Linux container and are superseded by the measured rows. The field also answers every departure second, not one.

## 2. Safety margin (kcf-margin): R beyond the known perimeter, 10% target, 28 California fires (GOFER)

File: `research/kcf-margin/numbers.json` → `table` (`fire_set=all28, cls=all, alpha=0.1`); `RESULTS.md`. Hash `0ead891` (protocol `746d005`).

| horizon | R | held-out (leave-one-fire-out) miss | 95% interval | fires |
|---|---|---|---|---|
| 5 h | **3.75 km** (3.8) | **6.2%** (`lofo_miss` 0.0616) | 0.6–22% | **28** (20,161 issue hours) |
| 8 h | **5.03 km** (5.0) | **6.6%** (0.0662) | 0.7–23% | **28** (20,077 hours) |

**Does not show:** a promise for any one fire or hour. It is an average over fires like these. The interval spans the target, and the fire is the unit (hours within a fire are not independent). The gust column comes from ERA5 read as a perfect forecast (ASSUMED). The margin did not transfer to a second population: on NIROPS it is exceeded on 0.26% of pairs, i.e. over-wide there.

## 3. 25 March 2025, Gyeongbuk (one fire, one day, no rate)

Files: `research/kcf-margin/numbers.json` → `gyeongbuk_stress` (`summary`, `hourly`); `derived/gyeongbuk_reach.csv`; `worst_hour_reference_km`. Hash `0ead891`.

| item | value | n |
|---|---|---|
| Hours the frozen margin failed (5 h) | **10:00–20:00 KST, 11 consecutive hours**, at both targets, class and all-hours margin. The all-hours margin also failed at 21 and 22 KST (13 of 23 in total). Class margin: 11 of 23 | 23 complete issue hours |
| Same, 8 h | class margin 13 of 20; all-hours 12 of 20 | 20 hours |
| Largest 5 h reach | **40.1 km** (issue 16 KST); 8 h largest 50.3 km (14 KST) | |
| Largest reach in the calibration set | **17.3 km** (5 h; North Complex, 5 km separate-fire rule); 29.8 km at 8 h. Without the separation rule 57.3 km (5 h) | 20,161 hours |

**Does not show:** actual perimeters. Reach is built from VIIRS plus AHI detections (about 0.4–2 km pixels, ASSUMED proxy). The comparison is against a 28-fire California margin, so it shows the margin is out of distribution here. It does not test the method on Korean fires.

## 4. Gust test (kcf-gust): KMA ASOS hourly primary, ERA5 secondary

Files: `research/kcf-gust/RESULTS.md`; `work/gust_hours_kma.json`; `work/kma_asos_hourly.json` (fields `gst_ws`, `gst_tm`); `work/gust_hours.json` (ERA5). Hashes: RESULTS and `gust_hours_kma.json` `dbd9738`; raw KMA `7f74c9e`; ERA5 `06d5a08`.

| item | value | n |
|---|---|---|
| Gusts at 10 and 11 KST, KMA | **no gust ≥10 m/s recorded** at any of the 4 stations at either stamp (0 means "none ≥10", not "calm") | 4 stations |
| Gusts at 10 and 11 KST, ERA5 | 10.6 and 12.6 m/s | 5 points |
| First gust ≥20 m/s, KMA | **25.0 m/s, Cheongsong (ASOS 276), 18:15 KST**, in the 19:00 stamp row. Daily file: 25.1 m/s. Yeongdeok 25.4 m/s at 21:56 | |
| First ≥20 m/s, ERA5 | 21.0 m/s at the 15:00 stamp (Yeongyang cell) | |
| Issue hours held at the frozen gust-class R, KMA | 5 h: **12 of 23**; 8 h: **8 of 20** | |
| Same, ERA5 | 5 h: 14 of 23; 8 h: 9 of 20 | |
| Fires behind the ≥20 m/s class | **9** (0 of 9 missed in calibration, CI 0–34%) | 9 |

**Does not show:** that gusts could have warned at 10–11 KST. They did not, in either series. Only a window reaching 7–8 h ahead sees a ≥20 gust, and R(8 h) = 12.0 km would have missed a 34.7 km reach. Limits: Yeongyang has no KMA station; values are whole m/s; the forward class reads the realised series as a perfect forecast (ASSUMED). No rate is claimed.

## 5. Replay (kcf-replay), 174 places, 25 Mar 2025, 12:00–24:00 KST

Files: `research/kcf-replay/RESULTS.md` §3 and §5; `score.json` (`steps_by_issue`, `score`); `per_place.csv` (`government_step`). Hash `e912bfc`.

| arm | leave-now, 12:00 | leave-now, 17:00 | place-hours with a departure shown, 5 h / 8 h | route reached before the shown departure, 5 h / 8 h |
|---|---|---|---|---|
| ORDINARY | 43 | 83 | 118 / 164 | 44 / 73 |
| RUNNING (8.2 km/h) | 142 | 174 | 952 / 1,093 | 100 / 108 |
| WORST | 156 | 174 | 855 / 930 | 26 / 26 |
| MEASURED | 45 | 84 | 297 / 349 | 137 / 181 |
| MEASURED+GUST (ERA5, PROVISIONAL) | 69 | 84 | 394 / 492 | 201 / 280 |
| MEASURED+GUST (KMA) | 69 | 84 | 351 / 482 | 199 / 280 |

n = 174 places per cell (2,262 place-hours per arm). "Leave now" means R(5 h) ≥ distance.

**Does not show:** performance, and the arms cannot be ranked, because the denominators are different sets of place-hours. The fire is reconstructed from detections, including those after the issue hour, and ends at 26 Mar 02:58 KST. Closures are permanent. 1,077 of 2,262 place-hours are already inside the known fire. RUNNING and WORST stand-ins rest on press-reported rates. The ERA5 arm is PROVISIONAL.

## 6. Heat (kcf-heat), model-to-model

Files: `research/kcf-heat/DERIVATION.md` §1; `FDS_CHECK.md`; `data/b1_voxel_check.json`; `data/b2_fds_compare.json` (`bins`); `ROUTING_EFFECT.md`; `data/routing_1h/SUMMARY.json` (`total`); `data/multihour/summary_dwell_{count,exclude}.json`. Hashes: DERIVATION, FDS_CHECK, B JSONs and 1-h SUMMARY `934db92`; ROUTING_EFFECT and multihour `c3fab07`.

| item | value | n |
|---|---|---|
| Old cap and cause | **0.703 kW/m²** (χcH/2T = 0.3·18,608/(2·3,970.46); F-3.1 measured max 0.702). Cause: a point's 11.5 s burn is spread over the 3,970 s (66 min) a front takes to cross a 375 m cell, i.e. 345× too diffuse, and it is a flat sheet seen from below | |
| Closed form vs FDS voxel sum | **9–11% high** (ratios 1.09–1.11 at d = 3–30 m, edge 20 kW/m³); same-run rerun 0.97–1.11 per bin | 10 snapshots; 189 samples |
| FDS radiometers vs both | voxel sum is **6× (1–3 m) to 98× (40–60 m)** above FDS, and the closed form **6.6× to 109×** | 4 to 48 per bin |
| 1-hour panel, leave-by moved by heat | **6 of 508** (median 84 s, range 76–346 s); 1 place loses its route | 530 origins |
| 1-hour panel, moved by the dose limit | 4 / 4 / 3 of 507 at 92 / 105 / 290 TDU (up to 453 s); none lose a route | 507 |
| Multi-hour (48 scenario packets): heat step | 28 of 286 places, 84–350 s | 286 places |
| Multi-hour: places moved by the dose limit (stay counted) | **22 / 21 / 16** at 92 / 105 / 290 TDU; **largest shift 529 s** (92 TDU). Stay excluded: 21 / 19 / 12, also up to 529 s | 286 places |

**Does not show:** that the closed form is right. It fails the factor-of-three gate against FDS, so v2 stays on HOLD and the form is only a conservative screening law relative to the models. FDS radiometry is itself unverified against measurement, and there is no measured flux anywhere. Multi-hour runs are F-DYN scenarios, not what happened. Whether the shelter stay is outdoors is UNVERIFIED (it alone removes 2 routes).

## 7. Demo

| URL | what it shows | traced to |
|---|---|---|
| https://sparkxt-0318.github.io/wildfireguardian/ | Static planner, no server. It replays the committed 2025 caches (Uiseong–Andong and Yeongdeok, 3 inputs each, 9,722 route checks), carries a test-data badge, and has the "25 March 2025 replay" scenario: 13 issue-hour slider, witness route at the leave-by, six named places with press-reported times labelled single-source | `README.md:4`, `planner/README.md` (`747211f`) |

It is the **only** URL in the repo. The last Pages deploy was run #76 at `e783ebc` (PR #187, 17 Nov 12:01 UTC), conclusion success (GitHub Actions). PR #188 did not touch the planner, so no deploy followed it. **Not checked from here:** I could not fetch the live page (proxy 403), so open it before the talk. Only three replay packs are wired (`planner/src/data/replayPacks.ts`): RUNNING, MEASURED and MEASURED+GUST (ERA5, PROVISIONAL). **The KMA arm is not in the live demo**, and no heat or gust-test view is either. The demo is a replay of recorded fire inputs, not a live forecast.

## 8. Congested leave-by (kcf-queue), 174 places, 25 Mar 2025, MEASURED 8 h, assumed parameters

Files: `research/kcf-queue/RESULTS.md`, `results/numbers.json`, `results/extra.json`, `results/t1_bruteforce.json`, `results/t3_mutation.json`. **Model output with assumed demand and capacity; no real traffic counts, no driver-behaviour data; the answer is a guaranteed-safe lower bound, not the exact optimum.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Free-flow field reproduced from my closure fields and recursion | **2,262 / 2,262** rows equal | 2,262 place-hours | `results/t0_free_flow_reproduction.json` | that the closure field is right, only that it is the published one |
| Solver vs exhaustive vehicle-by-vehicle search: accepted start times that brute force rejects | **0** | 66,000 start times, 6,000 random small networks | `results/t1_bruteforce.json` | exactness: 66 cases (0.10 %) are feasible by brute force and missed by the solver; small networks only |
| Unlimited capacity equals the existing deadline field | **0 differences** | 6,000 random instances (90,000 start seconds) | `results/t2_unlimited_capacity.json` | anything about congestion |
| Altered certificates rejected by the independent checker | **2,080 / 2,080**, 0 unaltered rejected (38) | 17 mutant families | `results/t3_mutation.json` | a certificate whose data and data hash were both replaced; it proves feasibility of the listed schedule, not that a later start fails |
| Village place-hours that clear / cannot clear, middle parameters | **1,064 / 55** (23 places have at least one failing hour; 4 never clear) | 1,119 place-hours at 137 places | `results/numbers.json` (`MID.classes`) | the 1,077-village-place-hour excluded part: 1,028 already inside the fire area, 50 with no free-flow window; 5 care facilities not evaluated |
| Leave-by earlier than the card's free-flow figure, median / max | **30.0 / 41.4 min** | 1,064 | `numbers.json` (`MID.shift_vs_L0_contested`) | congestion: this is almost all the 30-min mobilisation spread (assumed uniform ramp) |
| Queue delay beyond the spread, middle: place-hours ≥ 5 min, and max | **115** (12 places); max **11.4 min**; none ≥ 15 min | 1,064 | `numbers.json` (`MID.queue_effect_counts`) | real queues; capacity is per road piece, no junctions, zero-length point queues |
| Same, adverse parameters (HIGH) | **231** ≥ 5 min, **200** ≥ 15 min, max **53.6 min** | 1,025 | `numbers.json` (`HIGH`) | which adverse value is realistic: all five values are assumed |
| Sharing roads with neighbouring villages changed the answer | middle **0**; adverse **2** place-hours (max 34.5 min) | 1,064 / 1,025 | `numbers.json` (`sharing_effect_counts`) | that sharing does not matter: neighbours are one hop and released at the issue hour; only 11 of 287 cut-limited place-hours overlap their release window |
| Most-binding road: 일직점곡로 (secondary, OSM way 30043762, 의성) | binds for **3 places** (7 place-hours); no road binds for more than 3 | 287 cut-limited clearing place-hours | `results/extra.json` | a queue: the binding element is the road whose closure ends the window |

## 9. Learned margins at equal miss rate (kcf-adaptive2), 28 California fires, 5 h

Files: `research/kcf-adaptive2/RESULTS.md` (main table, §1), `numbers.json`. Hash `cdb4695`. Values copied, not recomputed. **Model output on reconstructed data. Every method was calibrated to a 10% miss rate on its training fires.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Quantile-loss model vs fixed margin, flagged area at 10% target | **0.846** (0.737 to 0.946); 278.4 vs 328.9 km²; lower on 22 of 28 fires; 0.78 without the three largest fires | 28 held-out fires, 20,065 issue hours | `RESULTS.md` Answer 1 | a gain in Korea (next row), or a promise per fire; fires are the unit |
| Per-fire Kalman adaptation vs fixed margin | **1.50** (1.085 to 2.004); vs its own non-adaptive twin 1.19 (1.04 to 1.42) | 28 | `RESULTS.md` main table, Answer 2 | that adaptation can never help; it shows this form does not |
| Reptile meta-learning with test-time adaptation vs fixed margin | **0.97** (0.82 to 1.15); vs its own starting point 1.01 (0.97 to 1.06) | 28 | same | an advantage for meta-learning |
| Oracle that rescales per fire-day (gate) | **24.5%** gain (9.1 to 40.5); per-fire oracle **−11.2%** (−30.5 to +7.6) | 28 | `RESULTS.md` §1 | a method: the oracle uses the fire's future. The gain is time structure inside a day, not which fire it is |
| Learning curve | area ratio about 0.85 from 4 to 24 training fires; 19 archive fires add nothing at 5 h (0.880 vs 0.866) | 4 to 24 fires | `RESULTS.md` §1 and Answer 4 | a gain from more data in general |
| Transfer to Korea with California margins | every learned method flags more area than the fixed margin; on 25 March all but three missed the 10–20 KST run, and the three that held used margins of hundreds to thousands of km | 12 Korean fires; 1 day | `RESULTS.md` Answer 5 | a Korean rate. No rate is claimed |

**Does not show:** a finding for Korea. All 28 California fires were scored here, and Korea and 25 March were used as a transfer test only. Two of the three amendments were written after seeing results (RESULTS §8).

## 10. Online quiet/run tracker (kcf-adaptive3), 10% miss rate

Files: `research/kcf-adaptive3/RESULTS.md` (Answer, results table), `numbers.json`. Hash `3dd8f15`. Rules committed at `0bf1917` before any result. **Two of three targets failed.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Target A: Korean run fire-days warned at the gust rule's alarm burden | **4 of 9** (gust rule 4 of 9). **FAILED**; raised alarms on 11 of 34 fire-days without a run, gust rule none | 9 run fire-days, 4 fires | `RESULTS.md` Answer table, point 1 | that 4 of 9 differs from 5 of 9; no rate is given |
| Target B: flagged area on 12 Korean fires | **83.6 vs 51.5 km²**, ratio **1.62** (1.04 to 2.09). **FAILED** | 12 fires, 756 issue hours | same | an advantage in Korea; it flags 62% more area |
| Target C: California held-out vs QUANTILE | 225.6 vs 237.6 km², ratio **0.95** (0.89 to 0.99); 0.99 read at exactly 10% miss. **Passed** | 12 fires, 6,605 hours | same | that the hourly update causes it: update off 220.6 km² (ratio 1.02, 0.96 to 1.08); forecast off 228.9 km². The version with both off was NOT RUN |
| 25 March 2025 | run probability crossed the alarm at 09 KST (one hour before the first run hour); margin 3.5 to 10 km vs reach 5 to 40 km; **11 of 12 hours from 09 to 20 KST missed** | 1 day | `RESULTS.md` point 3 | a warning that would have helped: the state moved and the margin still missed |

**Does not show:** a test on fires never seen. The Korean fires were already examined in kcf-adaptive2 and kcf-aloft; the 12 California fires called held-out were held out only inside this folder.

## 11. Attributing misses and an expected-error file (kcf-adaptive4), 10% miss rate, 5 h

Files: `research/kcf-adaptive4/RESULTS.md` (Answer, points 1–6), `numbers.json`. Hash `f693843`. Frozen at `bcb94a5` before the held-out run; protocol `4808fc6`. **Targets A and C failed, B passed.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| A. 25 March, hours 09–20 KST held (needed more than 1 of 12) | TARGETED held **1 of 12**; same model, no update, held 3; the published rule held 12 by flagging 11,481 km². **FAILED** | 12 hours | `RESULTS.md` Answer table | that the published rule helps: it flags 21 times the fixed margin's area in Korea |
| B. Miss rate on 12 Korean fires, leave-one-fire-out | **9.2%** (3.6% to 15.4%), at **2.4 times** the fixed margin's area. Passed | 12 fires | same, point 4 | efficiency: the pass costs 2.4 times the area |
| C. TARGETED vs no update, 5 h reach error | **−0.031 km, −8.1%**, interval −0.086 to +0.031 (includes zero). **FAILED** | 24 held-out fires | same, point 3 | any improvement; the interval includes zero. California alone: −4.7% (includes zero) |
| Wind-proportional base model vs fixed margin | **1.05** (0.90 to 1.20) California; **1.81** (1.41 to 2.28) Korea; learned k = 0.023 at 5 h | 12 + 12 fires | same, point 1 | that wind-proportional margins are better than a constant |
| Miss attribution, 5 h, California development / held-out | wind 21% / 21%; start area 23% / 23%; coefficient 15% / 6%; timing 13% / 12%; **unexplained 28% / 38%** | development 16 fires; held-out 12 | same, point 2 | which term is truly the cause: swapping in the truth is a measurement with a large remainder |
| Miss attribution, Korea (Choi hours) and 25 March | Korea: unexplained **58%** (97% by missed area). 25 March: coefficient 35%, timing 5%, wind −10%, start area 0%, **unexplained 70%**; with all four terms at truth 7 of 10 missed hours are still missed | 12 Korean fires; 1 day | same | a cause for 25 March |
| Expected-error file: share of rows above the stated 0.9 / 0.95 / 0.99 quantile | California **10.7 / 5.4 / 1.0%**; Korea 10.2 / 6.1 / 1.6% (median off: 61.9% above it); **25 March: 30% of rows above the 0.99 quantile** | held-out rows; 1 day | same, point 6 | reliable error on a day like 25 March |

**Allowed sentence:** "The forecast attributes 72% of its California misses and 42% of its Korean misses at 5 hours to one of its own four terms, and corrects only that term each hour." Not allowed: that it finds the cause of each miss, or that it cuts error (interval includes zero).

## 12. One-pass margin field (kcf-idea-routing), six recorded planner caches

Files: `research/kcf-idea-routing/SUMMARY.md`, `BENCH.md` (plan `BENCH_PLAN.md` frozen at `7f274a6` before any number), `METHOD.md`, `results/`. Hashes: SUMMARY `95d96f5`, BENCH `f62bc32`, METHOD `a471eee`. Python, pure, one laptop (macOS arm64). **Verdict in the file: NEW, PROVED AND FASTER, with the limits below as part of it.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Agreement with the existing field and brute force | **0 mismatches**; about 3.5 billion comparisons on the six recorded hours; five planted bugs all caught | 12,000 random graphs; 6 caches | `BENCH.md` Accuracy, `SUMMARY.md` | that the existing field is right, only that the two agree |
| Speed, several margins | **1.5×–4.7×** at 2 margins; **4.8×–15.7×** at 16; **150×–1,500×** for all 601 margins (0 to 600 s) | 6 caches | `BENCH.md` | a speed-up for today's single answer |
| Speed, one field at margin 0 | **1.7×–3.2×** faster on the 3 Uiseong–Andong caches; **0.55×–0.61×, i.e. slower,** on the 3 Yeongdeok caches | 6 caches | `BENCH.md` | "faster for one field": that claim fails |
| Memory | one margin pass peaks at 1.5–2× one existing pass; about one eighth of 16 existing fields kept | 6 caches | `BENCH.md` | |
| Leave-by times unchanged when every closure moves 10 min | **1,457 of 1,482** place–shelter leave-by times | 1,482 | `SUMMARY.md` | that closure times are known: travel times are treated as certain |

**Does not show:** a connection to the planner or app (none), a comparison against a compiled version of the existing sweep (none), timing on more than one machine. Novelty is "not found in searches" (three prior-art searches, `survey_notes/`); not finding is not proof it does not exist. The general level-by-level fact is a known theorem (Bruns and Godefroid, 2004).

## 13. Traffic validation (kcf-validate), corrected 15-minute analysis

Files: `research/kcf-validate/RESULTS.md` (table rows 1, 1a–1d), `numbers.json`. Hash `4333cd8` (PR #217). **Replaces the first 15-minute reading.** My first mapping of volume files to road sections used TCS correlation and was wrong for all 12 conzones used; the "conzones near 의성 stayed open" finding is withdrawn, and the old outputs are kept for audit. Amendments 13–16 were written before the outcomes they touch.

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Closure runs inside official closure sections vs outside | **20 of 24** conzone-directions inside show a closure run in 22–27 March; **3 of 46** outside do (all adjacent to closed sections) | 70 conzones with data (93 named intervals), 4,658,008 rows, 150 runs; routes 0300 and 0550 | `RESULTS.md` row 1a | closure of the model's cells or of any other route |
| Volume-derived onset minus official effective time | **0 min** (25 Mar 18:00, 의성~예천, 2 of 8); **+17.5** (+10 to +70; 4 of 6) 24 Mar 15:35; **−41** (−56 to −11; 3 of 12) 25 Mar 21:26; **−82.5** and **−110.5** at 25 Mar 15:30 and 15:58 (volume already near zero 1–2 h before) | 17 official event-sections | row 1b | accuracy of the model: this compares volume with the official time |
| Model issue hour minus median volume onset | RD1 −30, RD3 −120, RD4 −60, RD7 −15, RD8 −630, RD6 −615 min; RD2 +90, RD5 +150 | 8 rows, 2–6 of 6–12 directions each | row 1c | errors: these are bounds, since the model value is "closed by the issue hour"; RD2 and RD5 cannot be compared |
| Outbound surge before closure | median max V/B 0.11 (max 2.21); 2 runs ≥ 1.5, both westbound (away from the fire); no surge beyond day-of-week variation | 142 runs | row 1d | that no evacuation traffic occurred: only these sections were measured, and a surge in the direction of the fire is not excluded elsewhere |
| Daily files (before the 15-minute file) | route 030 G1 median day/baseline 1.07, 0.93, 0.37, 0.17, **0.02, 0.01** (22→27 Mar); controls stay at 0.80–0.96 | 38 section-directions | row 1 | closure times: daily totals cannot give them |

**Does not show:** the closure time of any single road at the model's cell level, or what any official should have done. Baseline is a weekend mean (caveat stands).  Anything quoted from the first TCS-correlation mapping (conzones near 의성 staying open) must not be used.

## 14. Radiant heat by published methods (kcf-radiation), replaces the kcf-heat law

Files: `research/kcf-radiation/RESULTS.md`, `data/panels/summary.json`, `data/panels/exploratory_front_only.json`, `data/panels_a7/summary_{old,new}.json`, `data/panels_a7/A7_leave_by_changes.csv`,
`data/fires/fires_summary.json`, `data/c1_butler_cohen.json`, `data/c2_fds.json`, `data/c3_flames.json`,
`data/c4_sensitivity.json`. Hash `3f5b915` (protocol frozen at `aac1b28`); rows marked A7 from the rerun of 2026-11-20 (PROTOCOL A7). Model output; no measured flux at a road.

| item | value | n | source | does not show |
|---|---|---|---|---|
| Safe distance at 7 kW/m2 vs the 375 m cell | **below 375 m in 100 %** of burned cells, every fuel level; max 320 m (Uiseong, high fuel) | 13,125 cells, 4 fires | `fires_summary.json` | safety at a road: radiation only, thresholds for people outside vehicles |
| Replay front cells: safe distance at 7 / 4.7 / 2.5 kW/m2 | median **25 / 36 / 63 m**, 90 % 104 / 139 / 212 m | 7,644 road cell-hours | `summary.json` (`A.front_*`) | the position of the front inside a 375 m cell |
| Lead the heat term adds before contact (4.7 kW/m2) | median **2.4 min**, 90 % 5.6, max 8.5 | 7,644 | `summary.json` (`A.front_lead_4.7`) | any lead from convection or embers |
| Uncertainty of one crown-fire cell's safe distance (7 kW/m2) | **133 m**, range **60-301 m** over flame T 1090-1400 K, fuel low-high, 4 view factors | 72 settings | `c4_sensitivity.json` | which setting is right; flame temperature dominates |
| Butler-Cohen "4 x flame height" | reproduced at **3.5 H** (20 m front); long front **8.3 L** (Rossi: 8 L) | H = 1-10 m | `c1_butler_cohen.json` | that 4 H is safe for a long front: it is not |
| Against FDS (C064 grass fire) | **19-115x above** FDS radiometers; 1.2-1.7x a resolved propane burner | 9 distance bins; 3 gauges | `c2_fds.json` | which is right: model-to-model only |
| Crown flame length vs ICFME observations | within a factor **1.7** on all 11 plots (observed fronts 25-40 m) | 11 plots | `c3_flames.json` | flux; surface-fire flames run high (safe side) |
| Replay leave-by times moved, 4.7 kW/m2 (unchanged by A7) | **337 of 1,134** (median 3.7 min, max 28 min), 12 lose the window; old law 350 (7 lost) | 1,134 place-hours | `summary.json` (`A.variants.baseline_4.7`) | physics: most of the shift is the 375 m cell rule, as for the old law |
| Finals packets, lost leave-now windows, 4.7 kW/m2, before and after A7 (2026-11-20) | **22 of 425 → 2 of 425** (7 kW/m2: 22 → 1; 2.5: 25 → 2); times changed 24 → 4; old law 0 | 425 place-inputs | `panels_a7/summary_{old,new}.json` | that the artefact is gone: 12 of the 20 recovered windows come from 6 packets with no real-gradient cell, where the known fire gets no flame at all; 2 windows still lost |
| Effect of A7 on the replay | **3 of 1,134** leave-by times at 7 kW/m2 (12 → 9 lost); **none** at 4.7 and 2.5 | 1,134 place-hours | `panels_a7/summary_{old,new}.json` | an improvement on the replay: 41 % of the known-fire cells take donor rates that are themselves at the 150 m/min cap |
| Road layer heat option | `--heat`, **off by default**; certificates still verify with it on; uses the A7 rule | 2 worked examples | `product/wfg-roadlayer/README.md` | a validated default: the 375 m cell rule still sets most of the timing change |

## 15. Robust routing (kcf-robust): does the margin field improve an outcome? Twin primary, 25 Mar 2025 secondary

Files: `research/kcf-robust/RESULTS.md`, `PROTOCOL.md`, `out/twin_scores.json`, `out/replay_scores.json`, `out/official_scores.json`, `out/fragility_174.csv`. **Model output on a synthetic twin and a reconstruction; no claim about what happened to people.**

| item | value | n | source file | does not show |
|---|---|---|---|---|
| Pre-registered test: a robust rule with fewer failed evacuations than CURRENT, interval excluding 0, at equal or less lead given up | **none of 3 passes** (time-robust, reach-robust, forecast-aware) | 2,160 place-pairs, 12 twin fires | `out/twin_scores.json` (`verdict`) | that robustness cannot help; only that it did not here, with 5 baseline failures to beat |
| Failed evacuations, twin: CURRENT / time-robust / reach-robust / fastest / forecast-aware | **5 / 0 / 1 / 7 / 4** (of 210 / 0 / 30 / 26 / 127 advised) | 2,160 | `out/twin_scores.json` (`summary`) | time-robust's 0 is no advice at all: it advises no departure and misses 57 of 221 cut-offs |
| Reach-robust vs CURRENT: failures, and lead time given up | **−4 [−9, 0]**; gives up **+29 min** more [+8, +91] | 12 fire clusters | `out/twin_scores.json` (`bootstrap`) | a significant gain: the interval reaches 0 |
| Forecast-aware vs CURRENT: failures; lead given up; false cut-offs | **−1 [−6, +3]**; **−30 min** [−63, +3]; false **73 vs 146** | 2,160 | `out/twin_scores.json` | fewer failures; it misses more (20 vs 12 of 221) |
| Margin field equals the timing slack L − t (permanent closures) | **56 / 56** pairs at t = 0; every second where fire binds | 56 origin–shelter pairs | `out/check_margin.json` | the case of roads that reopen, which this product does not model |
| CURRENT reproduces kcf-validate's twin baseline | **2,160 / 2,160** place-pairs; 12 / 221 missed, 146 / 1,939 false | 2,160 | `out/twin_scores.json` (`baseline_check`) | anything new; it is the harness check |
| 25 Mar alert times: closest rule (median abs. minutes, first / median village) | forecast-aware **32 / 28 min**; CURRENT 126 / 53 min | 12 alert units | `out/official_scores.json` | causality or order: rank correlations 0.3–0.6 overlap for all rules |
| 25 Mar against the detection record: CURRENT failed evacuations | **184 / 349** advised; the fire ran **2.3–4.3 h** ahead of every rule's median leave-by | 2,262 place-hours | `out/replay_scores.json` | a perimeter: truth is the detection record (RECONSTRUCTED) |
| Fragility table: village-hours with no safe departure now / tolerating < 1 km extra reach | **1,128 / 2,262**; **76** below 1 km | 174 places x 13 hours | `out/fragility_174.csv` | a forecast of failure; the reach column is "if the fire goes this much further than the input" |
| Product `--fragility` vs independent research pass | **2,262 / 2,262** reach and timing values equal; binding road 512 / 549 | 2,262 | `out/fragility_check.json` | why the binding road differs in 37 reach cases (not examined; the reach values themselves agree) |

## 16. Real household and building numbers for the 174 places (kcf-buildings), 25 Mar 2025, queue model rerun

Files: `research/kcf-buildings/RESULTS.md`, `per_place_real.csv`, `compare_mid.json`, `SOURCES.md`. **Register counts (2025-02) at the 읍·면·동 level, estimates per village; model output, not what happened to people.**

1. Households, residents and residents 65+ come from the interior ministry's **2025-02** 읍·면·동 counts; all 174 places are matched; no 리 register exists, so each village is its 읍·면·동 split equally over its 법정리 (**ESTIMATED**) (`SOURCES.md`).
2. Vehicles in the 137 queue places: **29,399 assumed → 29,094 real (−1.0 %)**; median village 192 → 148; 8 villages up and 34 down by more than 20 % (range 0.62–3.18×) (`compare_mid.json`).
3. Place-hours that cannot clear (MIDDLE, CONTESTED): **55 → 60 of 1,119**; 5 in, 0 out, at 의성읍 도동리·상리리·원당리 and 봉양면 분토리 (`compare_mid.json`).
4. Leave-by times that change: **16 of 1,119 (1.4 %) at 6 of 137 villages**, up to 25.3 min earlier; none of the 90 영덕 places changes (`compare_mid.json`).
5. The building register needs a key that is not in the folder; OSM holds only **231 buildings for the 174 places** (132 have none), so buildings at risk are lower bounds and vehicles are a province ratio, not a district count (`per_place_real.csv`).

## 17. Four routing methods on one machine (kcf-bench), six recorded planner caches, 5 repeats

Files: `research/kcf-bench/BENCH.md` (the table, ratios with ranges, accuracy, limits), `BENCH_PLAN.md` (committed before any timing), `results_hostB/summary.json`, `results_hostB/accuracy/`. Hash: BENCH.md and the summary `7f9ea3d`. Machine: Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18, one pinned core, nothing else of the study running during a timed task (two short git operations are logged). The four methods: the old one-departure-at-a-time method (OLD), the deadline field (FIELD), the margin field at one margin (MARGIN-1) and at ten margins (MARGIN-10).

| item | value | n |
|---|---|---|
| Time against the old method | OLD over all 9,722 cases, scaled from 200 timed requests per cache: **43.6 h** cold (41.3–45.5) and **37.8 h** warm (35.1–39.9). The deadline field answers them all in **20 min** (18–22). Ratio **129×** cold [114–151], **111×** warm [98–134]. Every new method is faster than OLD on every cache, cold and warm | 72 of 72 comparisons; 12,000 timed OLD requests |
| Margins, with the slow case | Ten margins (0–600 s) take **15.4 min** against **15.9 min** for the field at one margin without routes: **1.0× [0.9–1.2], about the same**. **Slower:** the margin field at one margin with routes takes **26.3 min** against 20.3 for the field, ratio **0.69–0.95**, clearly below 1 on the three Yeongdeok caches and on UA 03-23 warm | 6 caches, 5 repeats |
| Accuracy | **0 disagreements.** The field and the margin field at margin 0 match all **11,283** requests OLD decided, and each other on all 9,722 cases. 76,392 answers at the nine non-zero margins of the ten and 8,488 at 60 s equal the existing field on the widened instance. OLD left **717 of 12,000** requests unresolved (507 at its 30 s limit, 210 with the origin already in flame, where the field says no journey) | 9,722 cases; 12,000 requests |
| Memory, with the higher case | Peak resident memory: field 195–924 MB per whole-cache process; OLD 302–1,278 MB (median) per request. **Higher:** field 535 and margin field at one margin 562 MB against OLD's 302 MB on UA 03-24, and 670 against 652 on YD 03-26. The decision-only field and ten-margin field are lower everywhere (189–423 MB) | 6 caches |
| Conditions | OLD is scaled from a fixed random sample (sampling interval in BENCH.md), not run on every case. One machine, one pinned core on a shared virtual host; the container restarted twice during collection and one OLD block straddled a restart. Everything is logged | 240 timed tasks, 0 failed |

**Does not show:** a speed-up for a single departure (not measured), other machines, or a total that is comparable with section 1's Mac rows: that study used different job sets (up to 500 per file) and found 25–222×; the two are separate datasets and are not combined. A compiled version of either method was not timed. All results are model-relative.


## Ten likely judge questions

1. **Is the deadline field just faster, or is it right?** It reproduced all 7,771 recorded routes and 1,468 no-routes with zero disagreements, and it decided all 297 unresolved cases (row 1). Speed is not claimed: no clean summed timing is committed, and the host differs from the one that recorded the checks (row 1).
2. **Why trust the 5 h and 8 h margin?** At the 10% target it was exceeded on 6.2% and 6.6% of held-out hours, but the intervals reach 22–23% on 28 fires (row 2). It is an average over California fires, not a promise for one hour.
3. **Does your margin work in Korea?** Not on 25 March: it failed for 11 consecutive hours, 10:00–20:00 KST, with reach up to 40.1 km (row 3). The calibration set's largest reach is 17.3 km, so that fire lies outside it.
4. **Why not make the margin bigger?** No margin from 28 fires could have covered 40.1 km against a calibration maximum of 17.3 km (row 3). A larger one would be unusable elsewhere: the NIROPS check (row 2) shows an over-wide margin on small fires.
5. **Could gusts have warned you?** No. KMA recorded no gust ≥10 m/s at 10–11 KST, and the first ≥20 m/s was 25.0 m/s at Cheongsong at 18:15 (row 4). ERA5 read 10.6–12.6 m/s then, and gust class helped only 12 of 23 hours (KMA).
6. **The ≥20 m/s class has few fires. Is it reliable?** It rests on 9 fires, with 0 of 9 missed and a 0–34% interval (rows 2 and 4). It says almost nothing, and we state that on every slide that uses it.
7. **Did your tool beat what officials did?** We make no such claim. The replay shows what a screen would have displayed, and its arms have different denominators and cannot be ranked (row 5).
8. **Your replay arms differ a lot. Which is right?** 142 places are in leave-now at 12:00 under RUNNING but 45 under MEASURED, because R(h) differs (row 5). That spread shows the result depends on R(h); we do not pick a winner. The KMA arm equals the ERA5 arm at 12:00–22:00.
9. **Does heat change the routes?** Rarely on one hour: 6 of 508 leave-by times moved, median 84 s (row 6). Over hours the dose limit moves 16–22 of 286 places, by up to 529 s (row 6).
10. **Is your heat law validated?** No. It is 9–11% above the voxel sum of the same FDS fire, but FDS's own radiometers read 6–109× lower than it (row 6). It is a conservative screening law relative to models, and no measured flux is used.

## Spot fires ahead of the front (research/kcf-spot)

1. California, 28 GOFER fires: **460 confirmed spot fires** seen by VIIRS (≥ 1 km ahead, gap burned later), 2.3 per 100 fire-hours; median 3.0 km, 90th percentile 10.1 km (`kcf-spot/derived/measure.json`).
2. Only **92 of them (95%: 21–189) are wind-driven**: 188 lie downwind against 96 upwind; the rest are scatter, separate ignitions or gaps in detection (`measure.json`).
3. Korea, 15 fires: **2 confirmed spots**; 25 March 2025: **1** (24 March, 11.7 km), and **none in any hour of the 25 March run**, even with the Himawari gap rule loosened to 2 km (`kcf-spot/RESULTS.md`).
4. Satellites miss small spots: VIIRS saw **13 of 39** detached fires under 10 ha that airborne infrared mapped on the Dixie fire (33%; 19–50%) (`derived/airir_dixie.csv`).
5. Forecast gust does not measurably raise the chance of a spot: **+0.12 per m/s (−0.09 to +0.24)**, interval includes zero (`derived/fit.json`).
6. **99.8%** of satellite-seen spots lie beyond Albini's published maximum spotting distance; the published short-range model does not describe them (`fit.json`).
7. The fitted chance that a road cell is lit by a spot never exceeded **1.3%** on 25 March (8 h ahead); **no road cell** entered the 10% zone in any hour (`derived/roadlayer_spot_20250325_summary.csv`).
8. Adding the spot layer to the fixed margin held **1 of 12 hours** on 25 March 09–20 KST, the same as the margin alone (`derived/tests.json`).
9. The layer explained **0 of 258** held-out misses that kcf-adaptive4 left unexplained; even removing every observed spot cell would explain only 13 (5%) (`tests.json`).
10. On 25 March the fire's hot area grew by up to **12.7 km in one hour**, with every new patch within 2 km of cells lit that hour: at satellite scale the run was a fast front, not detached jumps (`kcf-spot/RESULTS.md`, point 4).

## Camp Fire road states, burnovers and movements (research/kcf-camp)

1. NIST's Camp Fire workbook: **2,264 unique reports** (575 cross-sheet copies removed); a blind second reader agreed with the first on 83.7% of 652 road rows (**kappa 0.72**); **202 road-closed, 24 passable** (`kcf-camp/RESULTS.md`, Data).
2. Scored at the reports, not against one rebuilt field: each road report is held out with every fire report within **500 m and 60 min** (812 of 1,596 removed) (`kcf-camp/PROTOCOL.md`).
3. The closure rule on reports alone closed the road by the reported time at **37 of 195** road-closed reports (**19%**, 95% CI 14–25%); 97 never closed (`kcf-camp/numbers.json`).
4. With the frozen spread margin R(h): **170 of 195 (87%, 82–91%)**, a median **119 min early** (95% CI 92–157) (`numbers.json`).
5. The same margin had **22 of 23 roads closed that crews were seen driving** (96%, 79–99%); 19 of those reports describe driving through fire, 3 an open road (`kcf-camp/RESULTS.md`, Test 1).
6. By 12:00 the margin had **36%** of the study area's 2,121 road cells (Paradise, Concow, Magalia) closed, against 8% with no margin (post hoc context, `out/context_closed_share_posthoc.json`).
7. Burnovers (NIST TN 2252 Table 30, all **23 placed**): **16 of 23 (70%, 49–84%)** closed or inside the 30-min margin 30 min before they began with the margin; **9 of 23** with none (`numbers.json`).
8. The margin left 7 open 30 min ahead: the first burnovers in Concow and east Paradise (07:50–08:30), when there were too few earlier reports to grow from, plus Edgewood Ln and Clark Rd at Airport Rd (`kcf-camp/RESULTS.md`, Test 2).
9. Neither documented movement is feasible in the deadline field under any variant: the Fire Station 82 cell had fire from 11:02 (convoy left ~12:00), the Firland Dr cell from 09:01 (engines left 13:58) (`out/test3_movements.json`).
10. What it means: closures that never reopen cannot represent "burned over, now passable"; one fire, firefighter reports, not residents; the CAL FIRE AVL CSV (281 apparatus) would test hundreds of real trips (`kcf-camp/RESULTS.md`, limits).

## Reopening after burn-out (research/kcf-reopen)

1. Burn-out time frozen before scoring: **τ = 240 min** (low 105, high 465), the 80th percentile of how long 75 Camp Fire road cells were still reported blocked after fire was first seen there; literature flaming times are 37 s–24 min at a point, and kcf-radiation A7 uses none (`kcf-reopen/out/tau.json`).
2. Fire crews were back in a burned cell a median **81 min** after the first fire report there (131 cells), and **125 min** after the last blocked report (37 cells) (`tau.json`).
3. With the window, passable reports the no-margin rule had closed fell from **2 to 0 of 23**, and vehicle observations in closed cells from **210 to 132 of 429** (`out/camp_tests12.json`).
4. The guard failed: **16 of 195** blocked-road reports fall in a cell the rule had already reopened (no margin: hits 37 → 21; spread margin: 170 → 154); still 4 at τ = 465 min (`camp_tests12.json`).
5. Neither documented movement becomes feasible at τ = 240: the roads would reopen only at **15:39** for the 12:00 convoy and **17:21** for the 13:58 engines (post hoc, `out/camp_test41_route_cells_posthoc.json`).
6. With the margin no burnover warning is lost; without it the two **9 November burnovers** (Coutolenc Rd, Concow Fire Station 37) are lost: those cells burned again more than 7.75 h after the first reports (`out/t43_burnovers.csv`).
7. Korea, 13 expressway closures with 15-minute traffic: the model would reopen sections between **69 h before and 40 h after** traffic came back; 중앙선 의성~예천 stayed empty until 28 March (`out/korea_reopen_sections.csv`).
8. Routing stays exact with reopening: **6,000** random instances, 0 disagreements with brute force, 16,273 witnesses valid; all 174 product certificates of the worked example verify with reopening on, and a one-second tampered claim fails (`results/routing_property.json`).
9. The margin field now differs from plain slack: below it for **40 of 6,268** twin and **422 of 5,062** replay pairs, by up to 7.3 h (never with permanent closures); kcf-robust's verdict on the twin is unchanged (`out/robust_window.json`).
10. 25 March 2025 replay: for responders **162 of 174 places** gain a later window (1,063 place-issues get a departure where there was none); for residents **0**. In the product it is `--reopen`, off by default (`robust_window.json`, `product/wfg-roadlayer/INTERFACE.md`).
