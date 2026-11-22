# kcf-buildings: real household, resident, vehicle and building numbers for the 174 places, and what they change

Frozen protocol: `PROTOCOL.md` (commit `a4ae3c7e`, amendment 1 `c35aeb68`, both before any household, vehicle or queue
result). Sources, dates and hashes: `SOURCES.md`. Per-place table (174 places, every figure with a status):
`per_place_real.csv`. Rerun outputs: `research/kcf-queue/results_real/`. Comparison code: `compare.py`,
`compare_mid.json`, `compare_lh.json`.

**Model output on reconstructed fire and road data and on register counts or estimates built from them. It is not what
happened to people and not advice to any official.**

## What was and was not found (read this first)

* **Measured:** households, population and residents aged 65 or over for every 읍·면·동 of the five 시·군, from the
  interior ministry's resident-registration statistics, **month-end 2025-02** (one month before the fire).
  All 174 places were matched to a 읍·면·동 (of the 169 villages: 162 by a unique 법정리 name, 6 by nearest neighbours, 1 by
  name stem; of the 5 care facilities: 4 by nearest neighbours, 1 by name stem; the `towns` table of `wfg-roadlayer`).
* **Not found:** any register **per 리**. The ministry publishes 시·도, 시·군·구 and 읍·면·동 only. So the figures per
  village are **ESTIMATED**: the 읍·면·동 count divided equally over its live 법정리 (the same idea as the assumed arm, now
  with measured 읍·면·동 totals for every 읍·면 instead of a county average for 안동·의성·청송·영양).
* **Not reachable:** the building register (건축물대장) and VWorld need a key. The folder "wildfire 3 (1)" holds only
  `DATA_INDEX.md` (no key, no household or building data) and `DATA_GO_KR_KEY` is not set. The fallback was open
  footprints: Microsoft has no Korea row and Google Open Buildings does not cover Korea, so **OpenStreetMap as of
  2025-03-21** was used. It is far too sparse (about 17,300 mapped buildings in the three search boxes; 231 of them
  assigned to the 174 places; 132 of the 174 places have none). Buildings are therefore **a lower bound of what is
  mapped, not a count**, and were not used to split households.
* **Vehicles** are **not** a district rate: the MOLIT/KOSIS table by 시·군·구 could not be read (portal that did not
  render, a download behind a CAPTCHA that was not bypassed). Vehicles = the province ratio (1.2008 = 1,552,434 Gyeongbuk
  vehicles at 2024-12 ÷ 1,292,811 Gyeongbuk households at 2025-02) × village households: **ESTIMATED**.

## The result, in one table (MIDDLE parameters, CONTESTED scenario, same 1,119 place-hours at 137 places)

Same code, same fire arm, same roads, shelters, spread (30 min), smoke factor and capacities; **only the demand differs**.
Assumed = households of the equal split of a county or 읍·면 total × 1.198 vehicles per household (the committed
`results/place_hours.csv.gz`; reproduced on a sample before the rerun). Real = village households from the 읍·면·동 count
of 2025-02 × 1.2008.

| measure | assumed | real | change |
|---|---:|---:|---|
| vehicles per village, median (range) | 192 (73–455) | 148 (72–610) | 8 villages up by more than 20 %, 34 down by more than 20 %, 95 within 20 % |
| vehicles, all 137 places | 29,399 | 29,094 | −1.0 % |
| card clearance N ÷ 800 veh/h, median (Q1–Q3, max), minutes | 14.4 (8.5–28.6, 34.1) | 11.1 (8.2–28.6, 45.8) | the maximum is a 의성읍 village |
| place-hours that cannot clear | **55** of 1,119 | **60** of 1,119 | 5 go in, 0 go out (4 places: 원당리, 도동리, 상리리, 분토리) |
| place-hours whose leave-by changes by ≥ 1 min | — | 11 (all earlier; 7 by ≥ 10 min) | with the 5 that stop clearing: **16 of 1,119** (1.4 %) at **6 of 137** villages |
| largest leave-by change | — | 25.3 min earlier (도동리 at 12:00 KST) | median change 0.0 min |
| queue delay (spread-free start − leave-by), median / max | 0.12 / 11.4 min | 0.12 / 25.4 min | place-hours with ≥ 5 min delay: 115 → 133 |
| 영덕군 (90 places): place-hours with any change | — | **0** | the assumed arm already used 읍·면 totals there |
| certificates (independent checker) | — | **0 invalid of 2,120** MIDDLE answers checked | LOW and HIGH: 0 invalid of 1,241 and of 1,190 checked |

**Which villages change most.** By demand: 의성읍 도동리, 상리리, 원당리 (192 → 610 vehicles, +218 %; the 읍 has few 법정리
for a large 읍 population); 풍천면 인금리, 어담리 (192 → 397, +107 %); 안평면 하령리 (192 → 119, −38 %); the 남후면 villages
(192 → 129, −33 %). By leave-by: 도동리 (25.3 min earlier at 12:00–15:00 KST, cannot clear at 16:00 and 17:00) and 상리리 (25.3 min earlier at
12:00–14:00, cannot clear at 15:00); 풍천면 인금리 (1.2 min earlier at 12:00–14:00) and 어담리 (1.2 min at 12:00); 봉양면 분토리 and
의성읍 원당리 stop clearing at 15:00 KST.
In all other 131 villages the leave-by is unchanged to the minute at every hour.

**Reading.** Real household counts move who is crowded (a few 의성읍 and 풍천면 villages) but hardly move the outcome of the
model: the total number of vehicles is the same to 1 %, and 777 of 1,119 place-hours were already limited by the 8 h horizon
rather than by the fire (kcf-queue RESULTS), where demand does not decide the answer. This says nothing about other days,
other fires, other speeds, or about the 읍 villages' true size, which depends on how the 읍 population is spread over its 법정리.

### Second table: LOW and HIGH parameter sets (do not read as an effect of the data alone)

In the assumed arm LOW and HIGH also scaled households (× 0.7, × 1.4) and vehicles per household (0.9, 1.5). Real counts are
not scaled (PROTOCOL §4), so these rows mix the data change with removing that band.

| set | cannot clear, assumed → real | go in / go out | leave-by changed ≥ 1 min among those that clear both | ≥ 10 min |
|---|---:|---|---:|---:|
| LOW (N median 101 → 148) | 34 → 47 | 13 / 0 | 301 of 1,072 | 66 |
| HIGH (N median 336 → 148) | 94 → 94 | 3 / 3 | 264 of 1,022 | 215 |

## Per-place data (`per_place_real.csv`)

For each of the 177 rows of the household tables (174 are the places of the replay): households, residents, residents 65+,
vehicles (all with status), the 읍·면·동 totals they come from, OSM-mapped buildings by use (house, apartment, care facility,
school, other, unknown), and facility names from OSM (schools, care homes, 경로당, health). Statuses: `ESTIMATED (MEASURED
읍면동 2025-02 / n 법정리)`, `ESTIMATED (province ratio 1.201)`, `MAPPED in OSM 2025-03-21 (lower bound, not a count)`,
`ASSUMED` (care facilities keep the old 30 residents, none with a car; no register gave their residents). Facilities named:
의성군공립요양병원 (care), 영덕효요양병원 (care), 강구정보고등학교, 강구중학교, 강구초등학교, 영덕야성초등학교.
Totals: 29,309 households in the 169 villages (29,654 in the assumed arm).

## Village cards and fragility table (`product/wfg-roadlayer`)

Every card now has one line "세대·주민·건물" with households, residents and residents aged 65+ (each marked measured /
estimated / assumed), buildings at risk of buildings mapped (OSM, lower bound) and households in cells the fire reaches within
the horizon (estimated). The audit CSV has the same figures with status columns; the fragility CSV and page get the same.
"Buildings at risk" = mapped buildings in a 375 m cell the input fire field reaches within the horizon. **No fire is spread
from building to building.** The card's queue line (`data/queue_leaveby.csv`) comes from the real-demand rerun; the assumed one
is kept as `queue_leaveby_assumed.csv`, and the earlier household tables as `data/households_assumed/`. Test suite:
91 passed, 1 skipped (includes the new `test_demand.py`); `research/kcf-queue/test_checker.py`: 37 passed.

## Limits

* **Register dates.** MOIS 2025-02 (households, residents, 65+); OSM 2025-03-21; 법정동코드 table of 2022-09 (the count of
  live 법정리); vehicles MOLIT 2024-12 (Gyeongbuk) over MOIS households 2025-02. The fire (21–28 March 2025) is after all of them.
* **Villages that could not be matched.** None at the 읍·면·동 level. Estimates in the assignment: 6 villages
  (`legal_ri_ambiguous_nearest`) and 1 (`name_contains_legal`) have an estimated 읍·면; 4 안동 urban 동 have no 법정리 match
  (only 용상동, a care facility, appears among the places); 괴시리전통마을 and 괴시리 share one 법정리 and each takes a full share
  (a double count, as in the assumed arm); 3 villages of the household table (고곡리, 상의리, 화신리) are not among the 174 places.
  지품면 and 축산면 include their 출장소 (sub-office) counts.
* **Within a 읍·면·동 the split is equal.** A 법정리 that holds the town gets the same as an empty one. This is the main reason the
  village numbers are estimates, and it drives the few large changes (의성읍).
* **65+ share** is the 읍·면·동 share (42 % in 영해면): it understates old villages and overstates young ones.
* **Buildings** are OSM-mapped only (about 5 % of what stands there); most places show 0 mapped buildings. Care facilities and
  schools are the named OSM ones, not the register's.
* **Vehicles** are a province ratio, registered where registered, not parked or driven there; no vehicles of visitors.
* The queue model's limits are unchanged (`research/kcf-queue/PROTOCOL.md` §7).
* **Disk and sandbox:** the machine's disk had about 0.9 GB free for part of the run; nothing was deleted.

## Five lines for `research/kcf-evidence/TALK_NUMBERS.md`

1. Households, residents and residents 65+ now come from the interior ministry's **2025-02** 읍·면·동 counts; all 174 places are matched; no 리 register exists, so each village is that 읍·면·동 split equally over its 법정리 (**ESTIMATED**) (`kcf-buildings/SOURCES.md`).
2. Vehicles in the 137 queue places: **29,399 assumed → 29,094 real (−1.0 %)**; median village 192 → 148; 8 villages up and 34 down by more than 20 % (range 0.62–3.18×) (`compare_mid.json`).
3. Place-hours that cannot clear (MIDDLE, CONTESTED): **55 → 60 of 1,119**; 5 in, 0 out, at 의성읍 도동리·상리리·원당리 and 봉양면 분토리 (`compare_mid.json`).
4. Leave-by times that change: **16 of 1,119 (1.4 %) at 6 of 137 villages**, up to 25.3 min earlier; none of the 90 영덕 places changes (`compare_mid.json`).
5. Buildings: the register needs a key that is not in the folder; OSM holds only **231 buildings for the 174 places** (132 have none), so buildings at risk are lower bounds and vehicles are a province ratio, not a district count (`per_place_real.csv`).
