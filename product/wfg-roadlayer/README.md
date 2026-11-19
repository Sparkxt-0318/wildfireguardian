# wfg-roadlayer · 마을별 마지막 도로 차단 시각

> **모델 출력 · 참고용 · 명령 아님 / Model output · advisory · not an order.** Every sheet, every CSV row and every
> certificate says so.

One offline command-line tool. Give it **a fire-arrival raster** (minutes from the issue time to fire arrival, per
cell), **the issue time** and **a region**; it gives, for every village and care facility:

1. one **CSV row** (Korean, with an English copy): the government-style stage from fire arrival (준비 / 실행대기 /
   즉시 실행, 8 h and 5 h thresholds as settings), every safe departure window, the time the last road out is cut, the
   gap between that and fire arrival, the route and shelter, and a **flag where the road is cut before the stage
   would reach 즉시 실행**;
2. a **one-page A4 PDF per 읍·면** (Korean and English), villages sorted by earliest road cut-off;
3. a **certificate per village** plus the independent checker of `research/kcf-theorem`, so any answer can be
   re-verified without this tool.

No new science: the road closures follow `research/kcf-replay/replay.py`, the deadlines come from the unchanged F-3.1
field (`research/harness-2026-11/F-3.1/deadline_field/core.py`, vendored byte for byte) and the certificates are
checked by `research/kcf-theorem/checker.py` (vendored byte for byte) and the recursion of its Theorem 2.

이 도구는 화재 도달 래스터, 발표 시각, 지역 이름을 받아 마을마다 단계, 안전 출발 시간대, 마지막 도로가 끊기는 시각,
그 시각과 화재 도달의 차이, 경로와 대피소, 그리고 '즉시 실행' 단계가 되기 전에 도로가 끊기는 경우의 경고를 냅니다.
읍·면마다 A4 한 쪽, 마을마다 이 도구 없이 다시 검증할 수 있는 인증서가 함께 나옵니다. 입력 형식은 [INTERFACE.md](INTERFACE.md).

## Quick start

Python 3.11+. From this folder (`product/wfg-roadlayer` in the repository):

```bash
python3 -m pip install -r requirements.txt
```

Once, with network: road graphs (from the research release archive) and the Korean font (NanumGothic, OFL), each
verified by SHA-256, into `~/.cache/wfg-roadlayer` (or `$WFG_ROADLAYER_CACHE`). Village, facility and shelter
points and the 읍·면 table are bundled in the repository.

```bash
python3 roadlayer.py setup
```

The worked example, 25 March 2025, 의성·안동 and 영덕, in one command (offline):

```bash
python3 roadlayer.py example
```

A run of your own:

```bash
python3 roadlayer.py run --region 영덕 --issue-time 2025-03-25T18:00+09:00 --raster arrival.tif
```

`python3 -m wfg_roadlayer …` is the same as `python3 roadlayer.py …`. Exit status: 0 done, 2 refused (REFUSED.txt
says which input), 1 error. Regions: `yeongdeok_2025` (영덕, with neighbouring 영양·청송 villages) and
`uiseong_andong_2025` (의성·안동).

`setup` also accepts local files, for a machine that never goes online: `--archive WFG-evaluated-routing-inputs-20261015.zip`,
`--data-routing <repo>/data/routing` (after `tools/fetch_routing_inputs.py`), `--font-wheel koreanize_matplotlib-0.1.1-py3-none-any.whl`.

## Output

```
<out>/ko/마을별_도로차단_<region>.csv        one row per village or facility (UTF-8 with BOM, opens in Excel)
<out>/en/villages_road_cut_<region>.csv      the same in English
<out>/ko/sheets/<시군>_<읍면>.pdf            one A4 page per 읍·면
<out>/en/sheets/<county>_<town>.pdf          the same in English
<out>/certificates/                          instance.json.gz, villages/<id>.json, checker.py, verify_certificate.py
<out>/run.json                               inputs and their SHA-256, settings, counts, file hashes, run time
```

The run time is printed at the end of every run and stored in `run.json`.

### What the columns mean

| column | meaning |
|---|---|
| 현재 단계 / stage now | from fire arrival at the village: ≤ 5 h 즉시 실행, ≤ 8 h 실행대기, otherwise 준비 (`[stage]` in the settings). "판단 불가" when the fire does not reach the village within a horizon shorter than 8 h |
| 화재 도달 / fire arrival | first arrival in the 375 m road cell of the village's road entry point (진입 지점) |
| 안전 출발 가능 시간대 / safe departure windows | every departure second with a checked route to one of the village's 3 nearest shelters, merged into windows; also per shelter |
| 출발 마감 / leave by | end of the window that starts at the issue time (rounded down to the minute). When the road is not cut inside the horizon there is no deadline, and the column says so |
| 마지막 도로 차단 / last road out cut | the first second at which no departure has a route (leave-by + 1 s). "발표 시각 이전": already cut. "차단 없음": not cut inside the horizon (the latest departure is set by the horizon, not by fire) |
| 차단 후 화재 도달까지 / gap | fire arrival minus road cut, minutes (rounded down). How long a village is cut off before the fire reaches it |
| 도로 차단 시점의 단계 / stage when cut | the stage from the time left until fire arrival at the moment the road is cut |
| 경고 / flag | **예** when the road is cut while more than 5 h remain until fire arrival, i.e. before the stage would reach 즉시 실행. "판단 불가" when fire arrival is beyond the horizon and the horizon left after the cut is under 5 h |
| 대피소·경로 / shelter, route | the earliest-arrival route at the last departure (the last road out) and at the issue time; OSM way ids |
| 계산 거부 사유 / refusal | the village gets no number (entry point more than 2 km from the road network, no data at its entry cell, no road path) |

Times are KST. Window starts are rounded up and deadlines, cuts and arrivals down to the minute, so a shown time is
never later than the computed one. Exact seconds after the issue time are in the last columns.

### Refusals

The tool refuses to output a number when an input is missing or stale and says which (exit 2, `REFUSED.txt` and
`REFUSED.json` in the output folder, nothing else written):

| code | when |
|---|---|
| `FIRE_INPUT_MISSING`, `FIRE_INPUT_UNREADABLE` | no raster/packet, or it cannot be read |
| `ISSUE_TIME_MISSING`, `ISSUE_TIME_INVALID`, `ISSUE_TIME_CONFLICT` | no issue time, no time zone, or it differs from the raster's `WFG_ISSUE_TIME` |
| `HORIZON_MISSING`, `HORIZON_CONFLICT`, `CRS_MISSING`, `UNITS_INVALID` | the raster does not say its horizon or coordinate system, or not in minutes |
| `FIRE_INPUT_UNCOVERED` | a road cell has no fire data (nodata or outside the raster). `--assume-uncovered-not-reached` reads them as not reached, and every page says so; a village whose own entry cell has no data still gets no number |
| `FIRE_INPUT_STALE`, `ISSUE_TIME_IN_FUTURE` | as-of minus issue time over 90 min, or the issue time ahead of as-of. As-of is the clock; `--as-of` sets it for a replay and every page then says "재현" |
| `ROADS_STALE`, `PLACES_STALE` | the road graph or the place points older than 365 days at the issue time |
| `REGION_MISSING`, `REGION_UNKNOWN`, `DATA_NOT_SET_UP`, `DATA_CORRUPT`, `GRID_MISMATCH` | region, cache or packet problems |

The limits are in `wfg_roadlayer/settings.toml`; copy it, edit, and pass `--settings`.

### Re-verifying an answer without the tool

```bash
python3 <out>/certificates/verify_certificate.py <out>/certificates
```

Standard library only; it imports nothing but `checker.py` next to it. For each village it re-derives every closure
from the per-cell fire arrival, checks that closures are permanent and shelters open from second 0 (hypotheses
M1–M4 of `research/kcf-theorem/THEOREM.md`), recomputes each shelter's latest departure with the Theorem 2(b)
recursion (which proves both "a route exists up to L" and "none at L + 1"), runs `checker.check_route` on every
witness route, and checks the road-cut kind, stage and flag. It does not re-read the raster: `run.json` gives its
SHA-256 and the resampling rule.

## The worked example (25 March 2025)

```bash
python3 roadlayer.py example
```

writes `wfg-roadlayer-example/uiseong_andong_20250325_1200KST/` and `wfg-roadlayer-example/yeongdeok_20250325_1800KST/`
(CSV, 14 + 10 sheets per language, 84 + 90 certificates). The two issue times follow the fire: 의성·안동 at 12:00 KST,
the first hour of the replay; 영덕 at 18:00 KST, the first hour at which the reconstruction cuts roads there, before
the 19:30 order for all nine 읍·면 (`research/kcf-replay/SOURCES.md`). 12:00 was picked for 의성·안동 because it shows a flagged village; every
hour is in [examples/SCAN.md](examples/SCAN.md).

**Fire input.** `examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif` and `…T0900Z…` (10 KB each, EPSG:5179, the
KFS_01 375 m lattice over both regions) are written by `examples/build_example_raster.py` from what the repository
already has: the known fire area before the issue time (`research/kcf-replay/fire_discs.json`, FIRMS + Himawari
hotspots, `HOTSPOT_RULE.md`) and the MEASURED spread margin R(h) (`research/kcf-replay/MEASURED_RULE.md`, frozen R(5 h),
R(8 h) from `research/kcf-margin`). Arrival = the replay's closure time of each cell, horizon 8 h. It is a
reconstruction, not a forecast. The run is a replay, so it is given `--as-of` = the issue time and every page says so.

**What the sheets show** (golden files in `golden/`):

| | 의성·안동, 12:00 KST | 영덕, 18:00 KST |
|---|---:|---:|
| villages and care facilities | 86 | 91 |
| road already cut at the issue time | 34 | 0 |
| last road out cut inside 8 h | 16 | 22 |
| not cut inside 8 h | 34 | 68 |
| refused (entry point > 2 km from the road network) | 2 | 1 |
| flag: road cut before 즉시 실행 | **1** (동변리) | 0 |
| largest gap, road cut → fire arrival | 동변리 326 min | 삼의리 (영양 석보면) 159 min |

* **동변리 (의성군 점곡면)** is in 실행대기: fire reaches it at 17:33, so the stage would become 즉시 실행 at 12:33. Its last
  road out (to 점곡초등학교, 7 min) is cut at **12:06**, 326 minutes before the fire and 27 minutes before the stage changes.
* **창길리 (의성군 안평면)**: every road out is already cut at 12:00, but the fire reaches the village only at 15:13.
* **지품리 (영덕군 지품면)**, first on the 영덕 list: leave by 18:19; the road is cut at 18:19, the fire arrives at 18:19.
  The kcf-replay timeline gives the same 18:19 (`research/kcf-replay/RESULTS.md` §4, MEASURED, 18:00).

**Agreement with the research it packages.** For all 174 checkable places the state (inside the fire area / no safe
departure / cut / not cut), the government step and the latest departure to the minute equal
`research/kcf-replay/per_place.csv` (MEASURED, 8 h) at these hours (`tests/test_replay_consistency.py`); over all 13
hours the tool counts 349 place-hours with a road cut inside the horizon, the 349 of `RESULTS.md` §5. Shelters can
differ only between equally late shelters (this tool takes the earliest arrival). All 174 certificates pass
`verify_certificate.py`.

**Run time** (printed by every run; 4-core Intel Xeon 2.1 GHz container, Python 3.13):

| | 4 worker processes (default on 4 cores) | 1 worker process |
|---|---:|---:|
| 의성·안동 (86 places, 30 shelter passes, 43,826 road edges) | 4.3 s | 9.6 s |
| 영덕 (91 places, 151 shelter passes, 111,924 road edges) | 53.7 s | 199.2 s |

The output is byte-identical whatever the number of workers.

## Village cards (마을 대피 카드)

```bash
python3 roadlayer.py cards --region 영덕 --issue-time 2025-03-25T18:00+09:00 --raster arrival.tif [--card-settings my.toml]
```

```bash
python3 roadlayer.py cards-example
```

The second writes the cards for all 174 checkable places of the worked example, plus the replay overlap check
(about 3 minutes). The committed result is in [examples/cards/](examples/cards/), and the half-page summary is
[examples/cards/SUMMARY.md](examples/cards/SUMMARY.md). Same inputs, refusals and field as `run`; no new science.

**Outputs:**

| file | contents |
|---|---|
| `cards_ko_<region>.pdf` / `cards_en_<region>.pdf` | One A5 page per place, in black and white. A map shows the exits, the dangerous road, the trigger line and the shelters. The key facts are leave-by with and without clearance, leave-by with the margin, trigger time, shelter, exits, dangerous road, forest share, departure order and van pickup. "모델 출력 · 참고용 · 명령 아님" is printed at the top and bottom. |
| `audit_<region>.csv` | One row per place, refused places included. Every value carries its status: CITED, DERIVED or ASSUMED. |
| `pickup_<region>.csv` | Van routes stop by stop. Also lists places not served within the horizon and places whose road is already cut. |
| `cards.json` | Settings, data hashes, counts and file hashes. |
| `OVERLAP.md`, `overlap.json` | Produced by `cards-example` only: the overlap check. |

**What each item is:**

* **Exits.** The number of routes from the village's road entry node to any shelter that share no road piece. An
  edge and its reverse edge are one piece; a one-way edge is a piece in its direction only. By Menger's theorem this
  equals the fewest road pieces whose loss cuts the village off. The count is fire-independent and ignores turn
  restrictions. The routes drawn are the quickest set of that many disjoint routes (successive shortest paths).
  Code: `wfg_roadlayer/exits.py`.
* **Dangerous road.** The road stretch inside one 375 m road cell whose loss cuts the most exits; 375 m cells are
  the unit by which the model closes roads. The village's own entry cell is excluded. Ties go to the cell nearest
  the village, and the card names the OSM way that carries the routes there. A whole OSM way is not used as the
  unit: a village part-way along a way would always lose both directions with it.
* **Forest share.** The share of each exit route's length with mapped OSM wood or forest within 50 m. This comes from
  the planner basemap (`tools/build_edge_attrs.py` → `data/edges/`). **The conifer share is not available**: the
  repository has no Korean forest-type map (`research/kcf-idea-forecast/SURVEY.md`), and the basemap keeps no
  `leaf_type`. The 50 m is ASSUMED, because Korean OSM forest polygons stop at the road corridor.
* **Clearance time.** Vehicles ÷ the capacity of the narrowest road on the route. The route is the one at the
  leave-by time, or exit 1 when there is no route.
  * Households are cited totals split equally over the 법정리 (ASSUMED; `tools/build_households.py` →
    `data/households/`).
  * Vehicles per household is 1.198 (DERIVED, Gyeongbuk).
  * Capacity is 1,700 vehicles/h/direction for two-lane roads (CITED, KHCM 2013) and 800 for village roads
    (ASSUMED).
  * Every source is in `data/traffic_sources.json`.
* **Leave-by.** Shown with and without clearance: with clearance, the first car must leave by leave-by − clearance
  so that the last one leaves by leave-by.
* **Trigger line.** The field is run a second time with every closure moved `margin_min` earlier (default 30). This
  gives the latest departure that keeps the margin everywhere on the route and at the shelter. That departure minus
  the clearance time is the trigger time. The trigger line is the input forecast's fire-arrival isochrone at the
  trigger time: if fire crosses it before the village has left, the margin is gone.
* **Departure order.** Villages whose routes share a road in the same direction leave one after another: latest
  deadline last, latest-start scheduling, with each convoy taking vehicles ÷ the shared road's capacity.
* **Pickup list.** Vans (default 3 × 15 seats, ASSUMED) start at the most-used shelter and visit the places with
  residents assumed to have no car, earliest leave-by first. The no-car share is a setting (default 0.36, ASSUMED,
  from KREI's 2010 census figure); care facilities count as 30 residents (ASSUMED). The roads are fire-free. A stop
  reached after the place's leave-by is marked; planning stops at the horizon.
* **Overlap check.** Places flagged single-exit or dangerous-road against the places with the earliest replay
  cut-off (`research/kcf-replay/per_place.csv`, MEASURED, 8 h, first quartile per region), as counts.

Settings are in `wfg_roadlayer/cards.toml`: copy it, edit it, and pass it with `--card-settings`.

## Heat option (radiant heat, off by default)

`--heat` (or `[heat] enabled = 1` in a settings file) closes a road piece when the radiant flux from the approaching
front would exceed a threshold (default 4.7 kW/m², `--heat-threshold 7` or `2.5` for the other graded levels), not
only when the fire reaches its 375 m cell. The method is research/kcf-radiation (published methods only; METHOD.md):
spread rate from the arrival raster, Byram intensity with fuel from the bundled Copernicus 2019 land-cover class
(`data/fuel/`, built by `tools/build_heat_fuel.py`), Van Wagner crown test, Byram / Thomas flame length, Albini flame
tilt, solid-flame radiation. A piece closes when the front comes within the safe distance d* of it; the closure is
never later than without heat. Wind, humidity and air temperature are one value per run (`[heat]` settings; defaults
ASSUMED: 7 m/s, 30 %, 10 °C). The certificates carry the per-piece closure seconds and still verify without the tool.

It is off by default: HEAT_DEFAULT_REASON. The option needs a raster on the road grid's 375 m EPSG:5179 lattice or a
packet (other rasters are refused with HEAT_INPUT_UNSUPPORTED). Radiation only: no convection, embers or smoke; the
thresholds are for people outside a vehicle (research/kcf-radiation/RESULTS.md, Limits).

## Tests

```bash
python3 -m pip install -r requirements-test.txt
```

```bash
python3 -m pytest -q tests
```

* `test_golden.py`: `example` reproduces `golden/` exactly (CSV, certificates, helpers byte for byte; PDFs byte for
  byte under the same reportlab version), each sheet is one page with the notice, each region runs under 5 minutes.
* `test_refusals.py`: every refusal above, plus "no number on a refused village" and "an old output folder is not
  overwritten".
* `test_replay_consistency.py`: the example equals `research/kcf-replay/per_place.csv` (MEASURED, 8 h) place by place.
* `test_certificates.py`: the shipped verifier passes every certificate and fails tampered ones.
* `test_vendor_and_sources.py`: vendored code byte-identical to the research files; masks equal `replay.py`'s; 읍·면 table
  complete and consistent with the 시·군 labels.
* `test_cards.py`: exits and the dangerous road on graphs with known answers; card settings refusals; departure-order
  arithmetic; overlap counts; `cards-example` gives 174 cards in each language, with the notice on every page, and
  audit invariants (with clearance ≤ without, trigger ≤ margin leave-by ≤ leave-by, every assumed value marked).
* `test_geotiff_and_resampling.py`: LZW / Deflate / PackBits / float predictor / big-endian / tiled GeoTIFFs; the
  earliest-pixel rule, nodata, out-of-extent, not-reached values, and a raster in EPSG:5186.

After a reviewed change to the output: `python3 tests/update_golden.py`.

## Data and limits

* **Roads:** OpenStreetMap historical snapshot 2025-03-21 (ODbL), the routing graphs of the research release;
  40 km/h assumed, missing oneway two-way, no congestion, no return trips.
* **Villages, facilities, shelters:** the planner's OSM extract of 2026-10-17 (newer than the fire) with 시·군 labels
  from V-World BND_SIGUNGU_PG (2025-06-30); 3 nearest shelters by straight line with distinct road entry points;
  travel between a place and its entry point is not modelled; places more than 2 km from the road network get no number.
* **읍·면:** `data/towns/<region>.csv`, built by `tools/build_towns.py` from the 법정동코드 table (리 → 읍·면, in
  the PyPI wheel PublicDataReader 1.1.1.post2, SHA-256 pinned). 165 of 177 origins by a unique 법정리 name; the other
  12 are estimates and carry † on the sheets (see `data/sources.json`). For 영덕 every assignment agrees with the OSM
  읍·면 boundaries of the planner basemap (90/90).
* **Fire:** a cell closes at the earliest arrival of any pixel overlapping it and never reopens (Corollary 3 of
  `research/kcf-theorem/THEOREM.md`: safe, may give up later departures after burn-out). Smoke, embers, heat dose and
  road capacity are outside the model.
* **Worked-example fire:** a reconstruction from satellite detections with a straight-line spread allowance, not a
  forecast and not the Forest Service product (`research/kcf-replay/RESULTS.md` §7 lists its limits).
