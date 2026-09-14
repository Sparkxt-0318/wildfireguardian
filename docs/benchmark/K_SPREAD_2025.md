# K-SPREAD-2025 — an open benchmark for short-horizon wildfire spread prediction in Korea

**Status: protocol v0.1, pre-registered 2026-09-14, before any entrant is run.** Decided by
the author on 2026-09-14: the benchmark is built before the 2026-10-16 freeze. Rules here
are frozen once the first entrant runs; changes after that are versioned (v0.2 …) and every
result names the version it was scored under.

## 1. Why a benchmark

No Korean operational system publishes a spread-prediction score against observed
footprints. NIFoS's 산불확산예측시스템 reports no accuracy metric (the 30 % and 5 m figures
of 2026-02 are plan statements), and its own post-mortem of March 2025 records that the
27 m/s gusts were not anticipated. 경기도's G-DAPS publishes none. Claims of the form
「we beat X」 are therefore unfalsifiable until a protocol exists that anyone can run. This
page is that protocol; whoever defines it fairly and publicly sets the terms.

## 2. Events and clocks

- **Events:** the six fires in the canonical dataset (`spread_v2_lofo.json`): 영덕 2025,
  의성·안동 2025, 울진·삼척 2022, 강릉 2023, 홍성 2023, 밀양 2022. Any later addition needs a
  FIRMS record and a 시군구-level 접수 time and is added as a new version.
- **Issue time T0 per event:** the timestamp of the first FIRMS detection in the event's
  acquisition box (the canonical dataset's slice 0). A second clock, T0' = the 산림청
  접수 time from 산불상태별 이력 (data.go.kr 15121205), is recorded when available and
  reported beside T0; it is not the scoring clock in v0.1.
- **Horizons:** T0 + 3 h, 5 h and 8 h. The 5 h and 8 h horizons are the doctrine's own
  (immediate evacuation; 재난취약자).
- **Complex rule:** 영덕 2025 and 의성·안동 2025 are one complex and are never in an
  entrant's training set when the other is scored (`docs/leakfree_fold.md`).

## 3. Inputs allowed at T0 (the 「forecast」 track)

Anything observable at or before T0, and forecasts *issued* at or before T0:
- fire: FIRMS detections up to T0;
- terrain: the committed 5 m / SRTM DEM;
- fuel: 임상도 1:5000 attributes (임종, 임상, 수종, 영급, 경급, 수관밀도) and the land-cover
  map;
- weather: KMA AWS / ASOS observations up to T0; 산악기상관측망 observations up to T0; the
  most recent KMA 초단기예보 / 단기예보 **issued before T0**.

Using any observation after T0 (later winds, later detections) puts the entrant in the
**hindcast track**, reported in a separate table, never beside forecast-track scores.

## 4. Target and truth

- **Target:** a per-cell probability of being fire-affected by T0 + h, on a 100 m grid over
  the event's acquisition box (500 m entrants are upsampled by nearest neighbour and say so).
- **Truth:** the cumulative FIRMS detections at the first overpass at or after T0 + h,
  classed per cell under the declared bounds of `docs/regrade_three_way.md` (A1–A6):
  **detected** (fire-affected by then), **indeterminate** (the cell is first detected in
  the gap between the last overpass before T0 + h and the first after), **not detected**
  (assumed unaffected; an assumption, not verified absence). Scoring never interpolates
  detections into smooth truth.

## 5. Metrics

Per event and horizon, then the mean over events and the worst event:

1. **ROC-AUC** over detected vs not-detected cells (indeterminate cells excluded).
2. **IoU at p ≥ 0.5** against the detected mask, with the indeterminate cells counted
   separately as 「unscorable」 and reported.
3. **Arrival-time error at road nodes** (minutes): for every walk-network node the
   canonical routing scans, the model's first crossing of p ≥ 0.5 minus the observed first
   detection of its cell, signed; reported as median absolute error and as the share of
   nodes the model calls safe that the observation calls burned (the false-safe rate).
4. **Decision shift:** the number of buildings (도로명주소 주건물, 영덕 only in v0.1) whose
   last-safe-departure class (`docs/last_safe_departure.md`) changes between the entrant
   and the observation-graded truth.

Metric 3 is the one that matters for evacuation; metrics 1–2 are for comparability with
the literature; metric 4 is for this project.

## 6. Entrants in v0.1

| id | what | inputs | status |
|---|---|---|---|
| E0 persistence | fire-affected at T0 stays; nothing spreads | FIRMS to T0 | baseline |
| E1 wind-cone | the T0 fire line advanced along the observed/forecast wind at a fixed rate per 30 min, 읍면동-scale smoothing (the G-DAPS class of method, as described in press; not G-DAPS) | FIRMS, KMA wind | to build |
| E2 Rothermel-class | a surface-fire rate-of-spread model on 임상도 fuel classes, DEM slope and KMA wind (the class of the 2003-lineage national system; not NIFoS's implementation) | FIRMS, DEM, 임상도, KMA | to build |
| E3 WFG canonical | the committed spread_v2 GBM at 500 m, leave-complex-out | as committed | exists (leak-free fold) |
| E4 WFG gust-aware | spread_v2 retrained with station gusts, 임상도 fuel classes, 100 m | + AWS, 산악기상, 임상도 | to build |
| E5 NIFoS issued maps | the 산불확산예측 maps issued during the 2025 fires, if obtained by 정보공개청구 | — | pending the author's request |

Every entrant is scored on the same events, clocks, truth and code. E1 and E2 are
labelled proxies; they are never called G-DAPS or NIFoS.

## 7. Discipline

Leave-one-complex-out for anything trained; thresholds and hyper-parameters fixed on the
other events; the protocol frozen before the first run; scoring code, data manifests and
per-event results public in this repository under `data/processed/benchmark/`; every
number quoted on a judge-facing surface registered through the additive registrars.

## 8. What the benchmark cannot say

That any entrant predicts the fire; it predicts what FIRMS saw at 375–500 m with a
detection floor. Nothing about passability, households or other regions than the six.
