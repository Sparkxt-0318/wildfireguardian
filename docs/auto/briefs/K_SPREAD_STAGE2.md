# Build brief — K-SPREAD-2025 Stage 2: the forecast-track field

Written 2026-09-14 by HQ. Runs in parallel with the author's 정보공개청구 (Stage 0 item 6);
it does not wait on it. Protocol: `docs/benchmark/K_SPREAD_2025.md` v0.1, frozen. Stage 1
report: `docs/auto/briefs/K_SPREAD_BENCHMARK_REPORT.md`. Read `docs/auto/CHARTER.md` §3 first.

## The question
Stage 1 established that the committed field (E3) is a **hindcast**: `spread_v2.forward_sim`
advances with ERA5 reanalysis at times after T0. Stage 2 builds the first fields that could
have been **issued at T0** and scores them under the same truth, so the project can say what a
forecast buys instead of what a reconstruction buys.

## Entrants to build (new names, new artifacts; E3 untouched)
- **F1 — frozen weather.** The same model and the same simulator, but every step after T0
  uses the weather observed **at T0** (wind, humidity, temperature held constant). This is
  the strictest "issuable at minute 0" field with no forecast product at all.
- **F2 — observed mountain weather, gust-aware.** Same simulator; weather after T0 from the
  산악기상관측망 record now in `data/raw/` (94 경북 stations, 10 m wind, gusts; see
  `docs/auto/briefs/DATA_ACQUISITION_STATUS.md` item 3 and `docs/mountain_weather_*.md`),
  interpolated to the grid with terrain-aware inverse distance. This is a **hindcast with
  the right wind** — label it as such; it measures the ERA5-vs-station gap, not forecast skill.
- **F3 — KMA forecast at T0** (only if the author's apihub 활용신청 for 초단기예보/단기예보
  archives lands; otherwise record 「not run: input missing」). This is the only true
  forecast-track entrant.
- **E1 proxy — wind-cone extrapolation** of the T0 detection footprint (the G-DAPS class),
  and **E2 proxy — Rothermel-family rate of spread** on 임상도 fuel classes with the T0 wind
  (the NIFoS class). Both labelled proxies, never named as those systems.

## Scoring
`scripts/benchmark/score_kspread.py`, unchanged: metrics 1–4 at 3/5/8 h, truth at m = 0,
leave-one-complex-out where training is involved (F1/F2 reuse E3's fitted model; no refit).
Report the leaderboard side by side with E0 and E3 in `docs/benchmark/results_v0.2.md`,
rendered from artifacts, and the decision-shift metric on the 19,250 buildings for each.

## Discipline
New filenames; nothing registered; no judge surface touched; `python scripts/auto/gates.py
--mode full` exit 0 read directly; stage by explicit path; **check GitHub's `auto-gates` run
after pushing** (a laptop green is not the gate); report to
`docs/auto/briefs/K_SPREAD_STAGE2_REPORT.md` with what ran, what could not, and the numbers.

## Ownership split (HQ, 2026-09-15)
Two sessions touch Stage 2. To avoid two artifacts for one field:
- **Session A (the NH-062 / `docs/forecast_track.md` session)** owns **F1** under the Stage 2
  name and definition (frozen T0 weather, E3's fitted model reused, no refit; a one-off refit
  digest may be recorded as evidence and is not the artifact).
- **Session B (this brief's agent)** owns **F2**, the **E1/E2 proxies**, and **F3** if the KMA
  forecast archive lands.
- Before writing any entrant bundle, check `data/processed/benchmark/<entrant>/` exists; the
  first writer wins, the second records 「already built by <report>」 and moves on.
- Both render into `docs/benchmark/results_v0.2.md` from artifacts; neither registers anything.
