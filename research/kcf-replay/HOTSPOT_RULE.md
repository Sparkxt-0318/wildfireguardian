# Known-fire-area rule (frozen before any outcome was looked at)

Written and committed before computing any replay hour, any closure, any deadline, or reading any documented fire
arrival against the reconstruction. The only data looked at while writing it: the pre-ignition AHI baselines
(file-level max/percentiles printed in the session log) and the FIRMS file headers.

## Issue times

Thirteen issue times `T` = 2025-03-25 03:00, 04:00, …, 15:00 UTC (12:00 … 24:00 KST). At `T` only rows with a
timestamp **strictly before** `T` are used (FIRMS: `acq_date`+`acq_time` overpass time; AHI: `scan_end_utc` of the
confirming scan). Delivery latency is NOT modelled (FIRMS NRT latency is typically hours; AHI minutes). This is a
known optimistic choice and is stated in RESULTS.md.

## FIRMS (committed country archives, `research/harness-2026-11/data-fetch/small/firms/`)

* Files: `viirs-snpp_2025_Republic_of_Korea.csv`, `viirs-jpss1_2025_Republic_of_Korea.csv`, `modis_2025_Republic_of_Korea.csv`.
* Box lon 128.2–129.7, lat 36.1–36.8; `acq` time ≥ 2025-03-22 00:00 UTC (KFS_01 ignition 02:24 UTC on 22 March).
* Keep VIIRS `confidence` ∈ {n, h} (drop `l`); keep MODIS `confidence` ≥ 30. Keep `type` = 0 where the column exists.
* Each detection = fire somewhere within **0.375 km** (VIIRS) or **1.0 km** (MODIS) of its centre.

## Himawari-9 AHI (`research/harness-2026-11/data-fetch-2/ahi_kfs01/`), "fire within about 2 km"

* Baseline (pre-ignition, fire-free): the two 20 March windows together (2025-03-20 06:00 to 2025-03-21 05:57:30 UTC,
  576 scans, every UTC hour of the day covered). For each pixel `p` and UTC hour-of-day `hh`:
  `base7[p,hh]` = max B07 and `baseD[p,hh]` = max (B07 − B14) over baseline scans whose UTC hour is hh−1, hh or hh+1
  (mod 24).
* A scan flags pixel `p` when **B07 ≥ base7 + 10 K and (B07 − B14) ≥ baseD + 10 K**. Saturated B07 (≥ 399.9 K) counts as
  passing the B07 test (it is a lower bound).
* **Persistence:** a pixel becomes a hotspot at the `scan_end_utc` of the second of two **consecutive** flagged scans
  (2.5 min cadence). From then on it stays in the known fire area ("so far").
* Each hotspot = fire somewhere within **2.0 km** of the pixel centre.
* Held-out false-alarm check (not an outcome): the same rule, with the same 20 March baselines, applied to the
  pre-ignition night 2025-03-21 18:00 – 2025-03-22 01:57:30 UTC. The count of hotspots it produces is reported as is.
  The thresholds are NOT changed after seeing that count; if it is non-zero, the count is reported as the rule's
  false-alarm level.
* Coverage limit: 448 pixels on the KFS_01 grid (EPSG:5179 x 1085250–1174125, y 1815750–1845375). Fire outside
  that rectangle is seen only by FIRMS.

## Known fire area and distance

Known fire area at `T` = union of discs (radius above) around every kept FIRMS detection and AHI hotspot before `T`.
Distance from a road cell (375 m routing-grid cell centre) to the known fire area = min over discs of
max(0, centre distance − disc radius). Cells inside a disc have distance 0 (closed at `T`).

## Closure stand-ins for R(h) (until research/kcf-margin lands)

`R(h)` = distance the fire front can cover in `h` hours. Closure time of a road cell = `T + h*` where `R(h*)` = its
distance. Three labelled stand-ins, fixed here:

| label | R(h) | source |
|---|---|---|
| ORDINARY | 0.341 km/h × h | PT-FireSprd median forward rate (Benali et al. 2023), the repo's own reference spread rate |
| RUNNING | 8.2 km/h × h | "시간당 8.2㎞", peak-period rate of this fire: Ajunews 2025-03-27 (unnamed 산림 당국 official) and YTN 2025-03-28 (own satellite analysis, 25 March from 03:00). Not a named 산림청/국립산림과학원 release (see SOURCES.md) |
| WORST | 3 km + 8.2 km/h × h | RUNNING plus a 3 km spotting allowance (Nocut 2025-10-02: "3km 이상 떨어진 비화"; 뉴스서울 says 2 km) |

A road cell's closure is permanent (closed from closure time to the end of the horizon). An edge is blocked for start
second `t` if its occupancy [t, t + D] meets a closed cell along its chord (the F-3.1 router rule with a phase
[closure, beyond H)), exactly as `PacketModel(extra_blocks=…)` builds it.

## Government step per place (YTN 2025-04-16: 화선 known → 도달거리 5시간 이내 위험구역, 8시간 이내 잠재적 위험구역; 취약계층 사전 대피)

At `T`, distance d of the place's 진입 지점 cell: if `R(5 h)` ≥ d → **LEAVE NOW** (위험지역); else if `R(8 h)` ≥ d →
**PREPARE, VULNERABLE FIRST** (잠재 위험지역); else no step.

## Latest safe departure

F-3.1 deadline field (one backward pass per shelter, `research/harness-2026-11/F-3.1/deadline_field/core.py`) on the
planner's road graph with the closures above, horizon H = 5 h and 8 h from `T`, each place's planner candidate
shelters (from the planner cache request at 2025-03-25 19:00 UTC for Yeongdeok, 17:00 UTC for 의성·안동). Latest safe
departure = max over the place's shelters of the latest departure second in the issue set; the road = the earliest-
arrival witness at that second; the shelter = the shelter that attains it. If a route is never cut inside H, the
departure is reported as "not cut within H" (capped by H minus travel), not as a deadline.

## Score

For places with a latest safe departure (cut within H) at some issue time: count how often the route was cut by the
reconstructed fire (the known fire area at a LATER issue time, distance 0 = inside a disc) at a time earlier than the
latest safe departure shown. Count only; no interpretation.
