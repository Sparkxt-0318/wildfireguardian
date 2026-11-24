# SOURCES

Every number printed or plotted, read by script from the file named. `commit` is the last commit that touched the file (wildfireguardian: `git log -1`; wildfireguardiandata: GitHub commits API); files outside a git repository are identified by SHA-256. Rows marked **DIFFERENT FROM EXPECTED** give the file value, which is what the figure shows.

Machines: F09 and panel (a) of F09b were timed on kcf-bench host B (Intel Xeon 2.10 GHz, one core); panel (b) of F09b on an Apple M5 Pro laptop under load (research/kcf-fastpath, runs/HOST.json). They come from different machines and do not share an axis.

## F01: Title map: Gyeongbuk replay area, 25 March 2025 12:00 KST

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Places on the map** | 174 |  | `research/kcf-replay/per_place.csv` | rows standin == MEASURED, horizon == 8h, issue_kst == 03-25 12:00; lon, lat, departure_state, latest_safe_departure_kst | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e912bfcf` | 174 | Issue hour chosen for variety: 12:00 KST shows 4 departure states, 18:00 KST 3; these are the two hours with a committed forecast raster. |
| **Forecast fire cells drawn (arrival within 8 h, 375 m)** ((not printed)) | 3760 |  | `product/wfg-roadlayer/examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif` | cells with finite arrival minutes <= 480 (0 = burning at the issue hour) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `b8f6c261` |  | max finite arrival 480 min |

- Roads and water: planner/public/kcf-scene/data/basemap.js (© OpenStreetMap contributors (ODbL)).

- Map extent: the Uiseong–Andong region box from scene.js regions.uiseong_andong_2025.bbox; Yeongdeok is left out because at 12:00 KST no Yeongdeok place is affected (DECISIONS.md D15).

## F02: The road is cut before the village

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Place-hours where a road ends the window (exact gap)** | 97 | 46 places | `research/kcf-roadcut/per_unit.csv.gz` | family == R, arm == MEASURED, horizon == 8h, binding == ROAD_CELL, gap_min present; column gap_min | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` | 97 |  |
| **Median gap** (11.8 min) | 11.8 min | 97 place-hours | `research/kcf-roadcut/per_unit.csv.gz` | median (family == R, arm == MEASURED, horizon == 8h, binding == ROAD_CELL, gap_min present; column gap_min) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` | 11.8 min | RESULTS.md line 32 states the same |
| **Largest gap** (159.6 min) | 159.6 min | 97 place-hours | `research/kcf-roadcut/per_unit.csv.gz` | max (family == R, arm == MEASURED, horizon == 8h, binding == ROAD_CELL, gap_min present; column gap_min) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` | 159.6 min |  |
| **Places where the road out is cut before the village is reached** (68 of 174 places) | 68 | 154 place-hours (incl. 51 with no window) | `research/kcf-roadcut/numbers.json` | configs['R/MEASURED/8h'].count_A_road_cut_before_village.places / .places | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` | 68 of 174 | This count (count A) is wider than the histogram's n = 97: it also includes place-hours with no departure window at all, and gaps known only as lower bounds. |
| **Samui-ri, issue 03-25 18:00: T_road_kst** | 03-25 20:39:01 |  | `research/kcf-roadcut/per_unit.csv.gz` | row place_id == osm:node/415158320, issue_kst == 03-25 18:00, MEASURED 8h, family R; column T_road_kst | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` |  |  |
| **Samui-ri, issue 03-25 18:00: T_village_kst** | 03-25 23:18:34 |  | `research/kcf-roadcut/per_unit.csv.gz` | row place_id == osm:node/415158320, issue_kst == 03-25 18:00, MEASURED 8h, family R; column T_village_kst | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` |  |  |
| **Samui-ri, issue 03-25 18:00: gap_min** | 159.6 |  | `research/kcf-roadcut/per_unit.csv.gz` | row place_id == osm:node/415158320, issue_kst == 03-25 18:00, MEASURED 8h, family R; column gap_min | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` |  |  |
| **Samui-ri, issue 03-25 18:00: windows_kst** | 03-25 18:00:00..03-25 20:39:01 |  | `research/kcf-roadcut/per_unit.csv.gz` | row place_id == osm:node/415158320, issue_kst == 03-25 18:00, MEASURED 8h, family R; column windows_kst | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `e3cce1aa` |  |  |

## F03: Comparison grid

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|

- Cell values from the talk brief (prompt 60), not from a committed file: no market-research summary is committed. Korea 1,1,0,0; Technosylva 1,0,0,0; Genasys 0,1,0,0; Watch Duty 1,1,0,0; WildfireGuardian 0,0,1,1.

## F05: Data foundation (wildfireguardiandata v0.1)

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Records with no standard satellite label (US 2018–2020, S3)** | 207508 |  | `results/HEADLINE_NUMBERS.md` | table row S3, column 'no standard label' | Sparkxt-0318/wildfireguardiandata / main / `4effd5ff` | 207,508 |  |
| **Verified / probable / record-only** | 4343, 20913, 182252 |  | `results/HEADLINE_NUMBERS.md` | table row S3, columns verified, probable, record-only | Sparkxt-0318/wildfireguardiandata / main / `4effd5ff` | 4,343 / 20,913 / 182,252 |  |
| **Verified share, Clopper-Pearson 95% interval (%)** | 2.03, 2.16 |  | `results/HEADLINE_NUMBERS.md` | table row S3, verified (lo-hi %) | Sparkxt-0318/wildfireguardiandata / main / `4effd5ff` |  |  |
| **Fires whose first label moved earlier** (45 of 240) | 45 | 240 fires (2023–2025) | `release/live-v0.1/onset_labels.csv` | rows with lead_vs_T0_min present | Sparkxt-0318/wildfireguardiandata / main / `a30d02d6` | 45 of 240 |  |
| **Median lead and bootstrap 95% interval (min)** | 42, 22, 84 | 45 fires | `results/HEADLINE_NUMBERS.md` | item 3 sentence | Sparkxt-0318/wildfireguardiandata / main / `4effd5ff` | 42 min | recomputed median of lead_vs_T0_min = 41.7 min |
| **Patches of the example record** | 3 |  | `release/records-v0.1/patches_us.jsonl.gz` | lines with record_id == fod:1389433: field, old, new, rule | Sparkxt-0318/wildfireguardiandata / main / `8f3e7859` |  |  |
| **Records in the national run** (2.66 million) | 2661383 |  | `release/records-v0.1/run_summary_us.json` | location.n_checked | Sparkxt-0318/wildfireguardiandata / main / `8f3e7859` | 2.66 million |  |
| **National run wall time** (7.9 minutes) | 7.9 min |  | `results/RECORDS_RESULTS.md` | R2 wall time row: 476 s (7.9 min) | Sparkxt-0318/wildfireguardiandata / main / `0e72b257` | 7.9 minutes |  |

## F06: Safety distance and 25 March 2025

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Safety distance R(5 h), 10% target** (3.75 km) | 3.75 km | 28 fires, 20161 issue hours | `research/kcf-margin/numbers.json` | table[fire_set=all28, h=5, cls=all, alpha=0.1].R_km | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | 3.8 km | TALK_NUMBERS rounds 3.75 to 3.8; the figure prints the file value |
| **Held-out (leave-one-fire-out) share of hours beyond R** (6.2%) | 0.0615558 | 28 fires, 20161 hours | `research/kcf-margin/numbers.json` | table[...].lofo_miss | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | 6.2% | 95% interval 0.6–22% |
| **California issue hours plotted (5 h reach, km)** | 20161 | 28 fires | `research/kcf-margin/derived/gofer_reach.csv.gz` | rows with h == 5, column reach_km | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | 20,161 hours |  |
| **Largest 5 h reach in the calibration set** (17.3 km) | 17.3354 km |  | `research/kcf-margin/derived/gofer_reach.csv.gz` | max reach_km at h == 5 | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | 17.3 km |  |
| **Gyeongbuk complete issue hours plotted** | 23 |  | `research/kcf-margin/derived/gyeongbuk_reach.csv` | rows with h == 5 and complete == True, column reach_km | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | 23 hours |  |
| **Largest Gyeongbuk 5 h reach** (40.1 km) | 40.0952 km |  | `research/kcf-margin/derived/gyeongbuk_reach.csv` | max reach_km (h == 5) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `0ead8913` | up to 40.1 km |  |
| **Run hours (10–20 KST) with the answer withheld** (11 of 11) | 11 |  | `research/kcf-abstain/numbers.json` | march25.hours_10_20_kst[*].abstain | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `6457eba9` | 11 of 11 | 'outside all calibration data' = beyond all 20,065 calibration hours of the abstain scoring set (kcf-abstain RESULTS.md); over all 24 hours of the day 22 were withheld (march25.hours[*].abstain) |

## F12: Forecast example: Wapiti 2024

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Wapiti case arrays (initial and later extent, probability)** | 859cddc0f28778a02134 | grid [111, 105], 1024 trajectories | `runs/20261013_observed_stored_validation/cases/859cddc0f28778a02134/m548_prediction.npz` | reference.burned_area[0\|1, 0], m548_prediction.probability[0, 0]; SHA-256 equal to wapiti_spatial_provenance.json source_sha256 | /Users/jp/Desktop/wildfire / file on disk (read only) / `sha256:e522e2e281956fed` |  |  |
| **Trajectories** | 1024 |  | `figure/revision/wapiti_spatial_provenance.json` | n_samples | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:67b98169ca0a2e51` | 1,024 |  |
| **ours: Brier, average precision** | 0.008402, 0.1461 | 25 intervals, 275,961 entries | `figure/revision/wapiti_scores_table.tex` | row 'Our model', columns Brier, AP | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:df1422c508d18b4c` |  |  |
| **FARSITE: Brier, average precision** | 0.023804, 0.0631 | 25 intervals, 275,961 entries | `figure/revision/wapiti_scores_table.tex` | row 'FARSITE', columns Brier, AP | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:df1422c508d18b4c` |  |  |
| **no new burn: Brier, average precision** | 0.00915, 0.0091 | 25 intervals, 275,961 entries | `figure/revision/wapiti_scores_table.tex` | row 'No-new-burn', columns Brier, AP | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:df1422c508d18b4c` |  |  |
| **Cohort: intervals, entries, new burns** | 25, 275,961, 2,525 |  | `template.tex` | sentence 'Evaluation uses 25 available Wapiti survey intervals ...' | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:7b1ea6e80a79dd94` | 25 intervals, 275,961 cells, 2,525 new burns |  |

- Selection (provenance json): After inspecting saved results, select the largest Brier skill versus no-new-burn persistence among Wapiti intervals with at least 100 newly mapped burned cells; break ties by cutoff and endpoint. Deliberately favorable illustration, not representative validation.

## F07: Forward against backward (schematic)

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|

- Schematic on a synthetic 25-junction network; no number is shown. The time bars are illustrative shapes.

## F15

Not built (see README.md).

## F16: Safety zones

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Uiseong 2025: burned cells, baseline d*(7) per cell** | 10955 |  | `research/kcf-radiation/data/fires/cells_KFS_01.csv.gz` | column dstar_7 (m) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Uljin 2022: burned cells, baseline d*(7) per cell** | 1937 |  | `research/kcf-radiation/data/fires/cells_KFS_02.csv.gz` | column dstar_7 (m) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Hongseong 2023: burned cells, baseline d*(7) per cell** | 153 |  | `research/kcf-radiation/data/fires/cells_KFS_05.csv.gz` | column dstar_7 (m) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Miryang 2022: burned cells, baseline d*(7) per cell** | 80 |  | `research/kcf-radiation/data/fires/cells_KFS_11.csv.gz` | column dstar_7 (m) | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Burned cells with d*(7) below 375 m (baseline fuel)** (13,125 of 13,125) | 13125 |  | `research/kcf-radiation/data/fires/cells_KFS_*.csv.gz` | count of dstar_7 < 375 | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` | all 13,125 |  |
| **Largest d*(7), baseline fuel** (281 m) | 280.72 m |  | `research/kcf-radiation/data/fires/cells_KFS_*.csv.gz` | max dstar_7 | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Largest d*(7) over every fuel level** (323 m (Uljin 2022, fuel_high)) | 323.45 m |  | `research/kcf-radiation/data/fires/fires_summary.json` | max over fires and fuel levels of dstar_7_m_p50_90_99_max[3] | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` | largest 320 m | DIFFERENT FROM EXPECTED: RESULTS.md and TALK_NUMBERS say 'max 320 m (Uiseong, high fuel)' (Uiseong fuel_high max = 319.85 m); the summary file holds 323.45 m for Uljin 2022 at fuel_high. The file value is printed. |
| **Share below 375 m, every fire and fuel level** (100%) | 1 |  | `research/kcf-radiation/data/fires/fires_summary.json` | min of share_dstar_7_below_375m over fires and fuel levels | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `d876f6f0` |  |  |
| **Replay front cells: median d*(7)** (25 m) | 24.9 m | 7,644 road cell-hours | `research/kcf-radiation/data/panels/summary.json` | A.front_dstar_7_m_p50_90_max[0] | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `3f5b9159` | 25 m |  |

## F17

Not built (see README.md).

## F08: One backward step and the checker

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Random networks compared with brute force** (12,000) | 12000 |  | `research/kcf-theorem/results/property_tests.json` | counts['closure:cases'] + counts['general:cases'] | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7cb28098` | 12,000 |  |
| **Disagreements with brute force** (0) | 0 | 12000 networks | `research/kcf-theorem/results/property_tests.json` | mismatches | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7cb28098` | 0 |  |
| **Planted bugs caught** (5 of 5) | 5 | 5 planted bugs, 3000 cases per family | `research/kcf-theorem/results/mutation_tests.json` | mutants (keys other than 'None', 'cases_per_family') with counts['*:cases_caught'] > 0 | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `39e18863` | 5 of 5 | unchanged control ('None') caught 0 cases; mutants: shift_off_by_one, ignore_turns, block_at_arrival, wait_through_fire, scalar_deadline |
| **Certificates in uiseong_andong_20250325_1200KST** | 84 |  | `product/wfg-roadlayer/golden/uiseong_andong_20250325_1200KST/MANIFEST.json` | certificates | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `b63a8822` |  |  |
| **Certificates in yeongdeok_20250325_1800KST** | 90 |  | `product/wfg-roadlayer/golden/yeongdeok_20250325_1800KST/MANIFEST.json` | certificates | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `b63a8822` |  |  |
| **Village certificates passing the independent checker** (174) | 174 | 84 + 90 golden manifests | `product/wfg-roadlayer/README.md` | sentence 'All 174 certificates pass `verify_certificate.py`' | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `6e649474` | 174 | The count of passes is stated in README prose; tests/test_certificates.py asserts all 84 Uiseong-Andong pass and samples every 15th Yeongdeok certificate. The manifests give 84 + 90 = 174 certificates. |
| **Random networks per family in the planted-bug test** (3,000) | 3000 |  | `research/kcf-theorem/results/mutation_tests.json` | cases_per_family | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `39e18863` |  |  |

- The left-hand time diagram is a schematic; its intervals carry no numbers.

## F09: Speed: earlier method against the deadline field

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Uiseong–Andong, 23 Mar 01:00: earlier method, cold, scaled** | 13460.7 s | 1523 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: deadline field, cold** | 25.8375 s | 1523 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: ratio** (521×) | 520.974 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: earlier method range over repeats** (whisker) | 13066.1, 15099.5 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: deadline field range over repeats** (whisker) | 21.8746, 30.3532 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: earlier method, cold, scaled** | 14184.7 s | 1518 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: deadline field, cold** | 174.032 s | 1518 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: ratio** (82×) | 81.5063 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: earlier method range over repeats** (whisker) | 13420.1, 14644.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: deadline field range over repeats** (whisker) | 166.492, 185.287 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: earlier method, cold, scaled** | 24465.1 s | 1557 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: deadline field, cold** | 105.91 s | 1557 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: ratio** (231×) | 230.998 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: earlier method range over repeats** (whisker) | 21236.1, 25485.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: deadline field range over repeats** (whisker) | 93.6429, 112.791 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: earlier method, cold, scaled** | 44650.8 s | 1810 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: deadline field, cold** | 282.341 s | 1810 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: ratio** (158×) | 158.145 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: earlier method range over repeats** (whisker) | 44041.1, 46514.3 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: deadline field range over repeats** (whisker) | 221.051, 306.004 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: earlier method, cold, scaled** | 31245.5 s | 1673 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: deadline field, cold** | 294.391 s | 1673 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: ratio** (106×) | 106.136 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: earlier method range over repeats** (whisker) | 30227.6, 32366.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: deadline field range over repeats** (whisker) | 281.267, 318.392 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: earlier method, cold, scaled** | 28861.2 s | 1641 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: deadline field, cold** | 334.915 s | 1641 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: ratio** (86×) | 86.1747 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: earlier method range over repeats** (whisker) | 26641.9, 29808 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: deadline field range over repeats** (whisker) | 303.599, 345.508 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **All six: earlier method total (sum of the six cache medians)** (43.6 h) | 156868 s | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | sum over caches of old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 43.6 h | BENCH.md states 43.6 h (cross-check) |
| **All six: deadline field total (sum of the six cache medians)** (20 min) | 1217.43 s | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | sum over caches of field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 20 min |  |
| **All six: ratio of totals** (129×) | 128.852 | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | ratio of the two sums | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | about 129× | BENCH.md states 129× [114–151] (cross-check) |
| **Disagreements between the field and the earlier method / recorded answers** (0 disagreements in 9,722 cases) | 0 | 9722 cases | `research/kcf-bench/results_hostB/accuracy/*.json` | counts.*_MISMATCH (recorded vs field, recorded vs margin@0, earlier vs field, earlier vs margin@0), summed; n_cases summed | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 0 on 9,722 | 'disagreements.old_unstable' lists earlier-method cases that were decided in one repeat and unresolved in another (time limit); these are not disagreements and are not counted |
| **Timed requests per cache (earlier method)** (200) | 200 |  | `research/kcf-bench/BENCH.md` | §2 Methods: 'a fixed random sample of 200 requests per cache' | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **All six: whiskers (sums of per-cache minima and maxima over repeats)** (whisker) | 148633, 163918, 1087.93, 1298.34 s |  | `research/kcf-bench/results_hostB/summary.json` | sum of old.cold.scaled.min / max and field.field.cold.min / max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  | equal to BENCH.md's 41.3–45.5 h and 18–22 min |

- Machine: Intel Xeon 2.10 GHz, 4 vCPU, Linux 6.18, Python 3.13.18, one pinned core (BENCH.md §1). Cold runs shown. Totals are sums of per-cache medians; their ratio equals the 129× in BENCH.md.

## F09b: Speed with the scalar fast path (separate panel, other machine)

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Uiseong–Andong, 23 Mar 01:00: earlier method, cold, scaled** | 13460.7 s | 1523 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: deadline field, cold** | 25.8375 s | 1523 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: ratio** (521×) | 520.974 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: earlier method range over repeats** (whisker) | 13066.1, 15099.5 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 23 Mar 01:00: deadline field range over repeats** (whisker) | 21.8746, 30.3532 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250323T010000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: earlier method, cold, scaled** | 14184.7 s | 1518 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: deadline field, cold** | 174.032 s | 1518 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: ratio** (82×) | 81.5063 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: earlier method range over repeats** (whisker) | 13420.1, 14644.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 24 Mar 09:00: deadline field range over repeats** (whisker) | 166.492, 185.287 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250324T090000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: earlier method, cold, scaled** | 24465.1 s | 1557 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: deadline field, cold** | 105.91 s | 1557 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: ratio** (231×) | 230.998 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: earlier method range over repeats** (whisker) | 21236.1, 25485.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Uiseong–Andong, 25 Mar 17:00: deadline field range over repeats** (whisker) | 93.6429, 112.791 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['uiseong_andong_2025/20250325T170000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: earlier method, cold, scaled** | 44650.8 s | 1810 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: deadline field, cold** | 282.341 s | 1810 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: ratio** (158×) | 158.145 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: earlier method range over repeats** (whisker) | 44041.1, 46514.3 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 19:00: deadline field range over repeats** (whisker) | 221.051, 306.004 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T190000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: earlier method, cold, scaled** | 31245.5 s | 1673 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: deadline field, cold** | 294.391 s | 1673 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: ratio** (106×) | 106.136 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: earlier method range over repeats** (whisker) | 30227.6, 32366.4 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 25 Mar 23:00: deadline field range over repeats** (whisker) | 281.267, 318.392 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250325T230000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: earlier method, cold, scaled** | 28861.2 s | 1641 cases (200 timed requests x 5 repeats) | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: deadline field, cold** | 334.915 s | 1641 cases, 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: ratio** (86×) | 86.1747 | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].ratios['old/field/cold'].median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: earlier method range over repeats** (whisker) | 26641.9, 29808 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].old.cold.scaled.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **Yeongdeok, 26 Mar 08:00: deadline field range over repeats** (whisker) | 303.599, 345.508 s | 5 repeats | `research/kcf-bench/results_hostB/summary.json` | caches['yeongdeok_2025/20250326T080000Z'].field.field.cold.min/max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **All six: earlier method total (sum of the six cache medians)** (43.6 h) | 156868 s | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | sum over caches of old.cold.scaled.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 43.6 h | BENCH.md states 43.6 h (cross-check) |
| **All six: deadline field total (sum of the six cache medians)** (20 min) | 1217.43 s | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | sum over caches of field.field.cold.median | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 20 min |  |
| **All six: ratio of totals** (129×) | 128.852 | 9722 cases | `research/kcf-bench/results_hostB/summary.json` | ratio of the two sums | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | about 129× | BENCH.md states 129× [114–151] (cross-check) |
| **Disagreements between the field and the earlier method / recorded answers** (0 disagreements in 9,722 cases) | 0 | 9722 cases | `research/kcf-bench/results_hostB/accuracy/*.json` | counts.*_MISMATCH (recorded vs field, recorded vs margin@0, earlier vs field, earlier vs margin@0), summed; n_cases summed | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` | 0 on 9,722 | 'disagreements.old_unstable' lists earlier-method cases that were decided in one repeat and unresolved in another (time limit); these are not disagreements and are not counted |
| **Timed requests per cache (earlier method)** (200) | 200 |  | `research/kcf-bench/BENCH.md` | §2 Methods: 'a fixed random sample of 200 requests per cache' | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  |  |
| **All six: whiskers (sums of per-cache minima and maxima over repeats)** (whisker) | 148633, 163918, 1087.93, 1298.34 s |  | `research/kcf-bench/results_hostB/summary.json` | sum of old.cold.scaled.min / max and field.field.cold.min / max | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `7f9ea3dd` |  | equal to BENCH.md's 41.3–45.5 h and 18–22 min |
| **UA 23 Mar 01:00: field time, deadline field (baseline solver), median and range** | 6.84221, 6.66444, 8.31888 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0323/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 23 Mar 01:00: field time, scalar fast path, median and range** | 2.61084, 2.54136, 2.93211 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0323/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 23 Mar 01:00: ratio of field times** (2.6×) | 2.62069 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/UA0323/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |
| **UA 24 Mar 09:00: field time, deadline field (baseline solver), median and range** | 7.16218, 6.74168, 7.42068 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0324/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 24 Mar 09:00: field time, scalar fast path, median and range** | 2.86961, 2.77977, 3.77102 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0324/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 24 Mar 09:00: ratio of field times** (2.5×) | 2.49588 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/UA0324/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |
| **UA 25 Mar 17:00: field time, deadline field (baseline solver), median and range** | 4.8551, 4.65311, 5.67554 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0325/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 25 Mar 17:00: field time, scalar fast path, median and range** | 2.45901, 2.37295, 2.65701 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/UA0325/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **UA 25 Mar 17:00: ratio of field times** (2.0×) | 1.97441 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/UA0325/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |
| **YD 25 Mar 19:00: field time, deadline field (baseline solver), median and range** | 52.0982, 51.5862, 61.3799 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0325T19/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 25 Mar 19:00: field time, scalar fast path, median and range** | 29.3126, 28.2611, 31.7071 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0325T19/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 25 Mar 19:00: ratio of field times** (1.8×) | 1.77733 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/YD0325T19/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |
| **YD 25 Mar 23:00: field time, deadline field (baseline solver), median and range** | 61.5588, 59.8429, 73.2376 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0325T23/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 25 Mar 23:00: field time, scalar fast path, median and range** | 29.5837, 29.136, 32.8841 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0325T23/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 25 Mar 23:00: ratio of field times** (2.1×) | 2.08083 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/YD0325T23/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |
| **YD 26 Mar 08:00: field time, deadline field (baseline solver), median and range** | 72.7865, 68.8279, 90.0094 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0326/baseline'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 26 Mar 08:00: field time, scalar fast path, median and range** | 32.433, 31.3452, 33.0837 s | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | runs['full/YD0326/scalar'][*].field | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` |  |  |
| **YD 26 Mar 08:00: ratio of field times** (2.2×) | 2.24421 | 5 runs | `research/kcf-fastpath/results/RESULTS.json` | ratios['full/YD0326/scalar'].field.median | wildfireguardian / origin/research/kcf-fastpath / `1e7d02e5` | 1.8 to 2.6× |  |

- Panel b machine: Apple M5 Pro, macOS-27.0.1-arm64-arm-64bit-Mach-O (runs/HOST.json on origin/research/kcf-fastpath); panel a machine: Intel Xeon 2.10 GHz (kcf-bench BENCH.md §1). Different machines, so the panels do not share an axis.

## F10: Camp Fire: closures caught before the report, and the cost

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Held-out road-closed reports placed on the map** | 195 |  | `research/kcf-camp/out/test1_road_state.csv` | rows with class == ROAD_CLOSED and match != not_placed; lat, lon | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `2aa78d1c` | 195 |  |
| **Reports where the method had the road closed by the report time** (170 of 195) | 170 | 195 reports | `research/kcf-camp/out/tests12.json` | test1.strict.MR.hits / closed_scored | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `2aa78d1c` | 170 of 195 | cross-checked against state_MR_strict == HIT in test1_road_state.csv |
| **Median minutes early, caught reports** (153 min) | 153.45 min | 170 reports | `research/kcf-camp/out/test1_road_state.csv` | median of -err_MR_strict over rows with state_MR_strict == HIT | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `2aa78d1c` | 119 min | DIFFERENT FROM EXPECTED. 119 min (numbers.json tests12.test1.strict.MR.time_error_min_closed_rows.median = -118.8) is the median over all 195 closed reports, caught and missed. The figure plots the caught reports only, as asked, so it marks their median. |
| **Passable roads the method had closed** (22 of 23) | 22 | 23 reports | `research/kcf-camp/out/tests12.json` | test1.strict.MR.false_closures / passable_scored | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `2aa78d1c` | 22 of 23 |  |

- No road lines drawn: the Paradise road graph is not committed (DECISIONS.md D12).

## F11a: Village card (exported as printed)

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Card exported** | page 86 (삼의리) |  | `product/wfg-roadlayer/examples/cards/yeongdeok_20250325_1800KST/cards_ko_yeongdeok_2025.pdf` | page 86, rendered at 300 dpi | wildfireguardian / talk/figures (= origin/Main 5ff9aa90) / `6e649474` |  |  |

- Cropped to 1749 x 2481 px at 300 dpi.

## F13: Learned kernels (rebuilt from the vector PDF)

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **3×3: sum used to scale the colour bar** | 0.00279 h⁻¹ |  | `figure/revision/named/kernel_matrix_summary_table.tex` | row 'mixed & $3\times3$', column Sum | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:b3e2aca5feeacb11` |  |  |
| **3×3: rebuilt min / max / mean against the table** | 0.00032087, 0.000369783, 0.00034875 h⁻¹ | 8 cells | `figure/revision/named/kernel_matrix_overview.pdf` | decoded cell colours x vmax | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:1a4ffaf3d81e219a` | table: 0.00032 / 0.000371 / 0.000349 | rebuilt vmax 0.00037; max differs from the table by -0.3%, min by +0.3% |
| **5×5: sum used to scale the colour bar** | 0.00907 h⁻¹ |  | `figure/revision/named/kernel_matrix_summary_table.tex` | row 'mixed & $5\times5$', column Sum | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:b3e2aca5feeacb11` |  |  |
| **5×5: rebuilt min / max / mean against the table** | 0.000208113, 0.000587065, 0.000377917 h⁻¹ | 24 cells | `figure/revision/named/kernel_matrix_overview.pdf` | decoded cell colours x vmax | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:1a4ffaf3d81e219a` | table: 0.000209 / 0.000589 / 0.000378 | rebuilt vmax 0.000587; max differs from the table by -0.3%, min by -0.4% |
| **7×7: sum used to scale the colour bar** | 0.0108 h⁻¹ |  | `figure/revision/named/kernel_matrix_summary_table.tex` | row 'mixed & $7\times7$', column Sum | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:b3e2aca5feeacb11` |  |  |
| **7×7: rebuilt min / max / mean against the table** | 0.00012912, 0.000435781, 0.000225 h⁻¹ | 48 cells | `figure/revision/named/kernel_matrix_overview.pdf` | decoded cell colours x vmax | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:1a4ffaf3d81e219a` | table: 0.000131 / 0.000437 / 0.000225 | rebuilt vmax 0.000436; max differs from the table by -0.3%, min by -1.4% |
| **9×9: sum used to scale the colour bar** | 0.0194 h⁻¹ |  | `figure/revision/named/kernel_matrix_summary_table.tex` | row 'mixed & $9\times9$', column Sum | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:b3e2aca5feeacb11` |  |  |
| **9×9: rebuilt min / max / mean against the table** | 0.000117378, 0.000410824, 0.0002425 h⁻¹ | 80 cells | `figure/revision/named/kernel_matrix_overview.pdf` | decoded cell colours x vmax | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:1a4ffaf3d81e219a` | table: 0.000118 / 0.000413 / 0.000243 | rebuilt vmax 0.000411; max differs from the table by -0.5%, min by -0.5% |
| **Combined: sum used to scale the colour bar** | 0.0428 h⁻¹ |  | `figure/revision/named/kernel_matrix_summary_table.tex` | row 'mixed & Combined', column Sum | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:b3e2aca5feeacb11` |  |  |
| **Combined: rebuilt min / max / mean against the table** | 0.000265839, 0.00167478, 0.000535 h⁻¹ | 80 cells | `figure/revision/named/kernel_matrix_overview.pdf` | decoded cell colours x vmax | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:1a4ffaf3d81e219a` | table: 0.000257 / 0.00168 / 0.000534 | rebuilt vmax 0.00167; max differs from the table by -0.3%, min by +3.4% |

## F14: Reliability, reported model

| shown | value | n | file | field | repo / ref / commit | expected | note |
|---|---|---|---|---|---|---|---|
| **Bin [0.0, 0.01): mean prediction, observed frequency, entries, new burns** | 0.000131, 0.003642, 259164, 944 | 259,164 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.01, 0.02): mean prediction, observed frequency, entries, new burns** | 0.014768, 0.046987, 2639, 124 | 2,639 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.02, 0.05): mean prediction, observed frequency, entries, new burns** | 0.033198, 0.04852, 4019, 195 | 4,019 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.05, 0.1): mean prediction, observed frequency, entries, new burns** | 0.072769, 0.069485, 3454, 240 | 3,454 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.1, 0.2): mean prediction, observed frequency, entries, new burns** | 0.144334, 0.116893, 4132, 483 | 4,132 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.2, 0.5): mean prediction, observed frequency, entries, new burns** | 0.270414, 0.201687, 2489, 502 | 2,489 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Bin [0.5, 1.0): mean prediction, observed frequency, entries, new burns** | 0.550262, 0.578125, 64, 37 | 64 entries | `figure/revision/wapiti_calibration_table.tex` | row of the tabular (Mean q %, Observed %) | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:80d44aa10fc8e63f` |  |  |
| **Lowest bin: share of entries / mean prediction / observed frequency (%)** (93.91%, 0.0131%, 0.3642%) | 93.91, 0.0131, 0.3642 | 275,961 entries | `template.tex` | sentence 'The lowest mixed bin contains ...' | /Users/jp/Desktop/Korea Code Fair/Forecast Research Paper Preprint / file on disk (read only) / `sha256:7b1ea6e80a79dd94` | 93.91%, 0.0131%, 0.3642% |  |

- Error bars are Wilson 95% intervals computed here from the table's entries and new burns; the preprint applies no interval (its caption says so).
