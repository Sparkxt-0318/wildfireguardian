# Build brief — K-SPREAD-2025 benchmark (protocol: docs/benchmark/K_SPREAD_2025.md)

Written 2026-09-14 in the author's HQ session. Decision: benchmark before the 2026-10-16
freeze. Harness stays paused; laptop sessions on `auto/dev` only. Read
`docs/auto/CHARTER.md` §3 first. The protocol page is frozen; this brief says what to build
and in what order, and what cannot start until the author's data arrives.

## Stage 0 — the author's acquisitions (blocking for E1, E2, E4, E5)

`docs/auto/briefs/DATA_VERIFICATION_REPORT.md` found none of the six items on 2026-09-13
and names the exact route for each. The author must obtain, in this order of value:
1. 임상도 1:5000 경상북도 (FGIS free request; the report's item 4 gives the acceptance test:
   polygon count inside the canonical box, field names) — needed by E2 and E4.
2. KMA API Hub key **and** the March 2025 bulk AWS/ASOS files with 최대순간풍속 for
   2025-03-20 → 03-31 including the 지점정보 table (report items 1–2; note 영덕 and 의성 may
   be AWS, not ASOS) — needed by E1, E2, E4.
3. 산악기상관측망 history for March 2025 (report item 3; whether the API serves history is
   unsettled; files are the fallback) — improves E4.
4. data.go.kr key for 산불상태별 이력 / 산불발생정보 (report item 5) — the T0' clock.
5. 정보공개청구 to 국립산림과학원 for the 2025 issued 확산예측 maps (report item 6) — E5.
Store keys only under `~/.config/wildfireguardian/` (mode 600); raw files under
`data/raw/<layer>/` with a MANIFEST.json (sha256, source, date). Nothing raw is committed.

## Stage 1 — scorer first (no new data needed; start now)
- `scripts/benchmark/score_kspread.py`: reads an entrant's per-event probability stacks
  (npz: `grid_extent`, `times_min`, `stack` at 100 m or 500 m, plus `entrant.json` with
  inputs used and track), builds truth from the committed detections at each horizon under
  `docs/regrade_three_way.md` A1–A6, computes the four metrics of protocol §5, and writes
  `data/processed/benchmark/<entrant>/<event>.json` + a `leaderboard.json`.
- Entrants E0 (persistence) and E3 (WFG canonical, leave-complex-out: reuse
  `scripts/run_leakfree_yeongdeok_fold.py`'s fitting for every fold) must run end to end on
  committed data alone. This proves the scorer before any external data exists.
- `tests/test_kspread_scorer.py`: synthetic event where truth is known; metrics re-derive
  by hand; indeterminate cells never enter AUC/IoU; the complex rule is enforced.
- `docs/benchmark/results_v0.1.md`: the leaderboard as it stands (E0, E3), with the
  protocol version and what is missing.

## Stage 2 — proxies (needs Stage 0 items 1–2)
- E1 wind-cone: advance the T0 line along the wind vector at a fixed rate derived from the
  other five events (fit once, leave-one-out), smooth to 읍면동, hourly steps.
- E2 Rothermel-class: surface rate of spread from 임상도 fuel class → a declared fuel-model
  mapping (write it down in `docs/benchmark/fuel_mapping.md` before running), slope from
  the DEM, wind from AWS/ASOS at T0 and the forecast issued before T0; elliptical growth.
Both are labelled proxies in every table.

## Stage 3 — the gust-aware WFG model (needs Stage 0 items 1–3)
- Features: replace ERA5 wind with terrain-interpolated station wind and gust (AWS +
  산악기상), add 임상도 fuel classes, run at 100 m (the 5 m DEM already exists). Same GBM,
  same seed, leave-complex-out. New filenames; `spread_v2_lofo.json` and the canonical npz
  untouched.
- Report it on the benchmark like any other entrant; also re-run the routing decision
  shift (protocol metric 4) so the finals can say whether the environmental inputs changed
  which buildings are stranded.

## Stage 4 — E5 if the 정보공개청구 returns anything
Digitise the issued maps to the 100 m grid with their issue times; score in the forecast
track only if the issue time ≤ T0 + horizon, else hindcast.

## Report back
`docs/auto/briefs/K_SPREAD_BENCHMARK_REPORT.md`: what ran, the leaderboard, what could not
run and why, and the sentence the finals can defend. Gates green before every push.
