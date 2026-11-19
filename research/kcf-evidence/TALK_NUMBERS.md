# TALK_NUMBERS: what the presenter can say, and where it comes from

Built from `Main` at PR #188 (`9dbe458`). Every value is copied from a committed file; nothing is recomputed. The hash in each row is the last commit that touched the cited file (`git log -1 -- <file>`). **UNTRACED** = no committed file holds it. All results are model-relative, and none is a field validation. Hard stop: Thu 19 Nov 2026, 12:00 Shanghai.

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

**Does not show:** a clean total-time ratio. RESULTS §5 says the clean single-process run is "still to be done" and "no summed ratio is claimed". `TIMING_RUN.sh` exists, but **no `TIMING_<host>.json` is committed, so a clean summed ratio is UNTRACED.** The recorded times are from the Mac with 13 workers; the field times are from a Linux container that runs the kit 2.6–2.8× slower than the Mac. The UA 03-24 and 03-25 field times are inflated by a concurrent build. The field also answers every departure second, not one.

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
