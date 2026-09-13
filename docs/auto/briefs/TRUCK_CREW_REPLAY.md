# Build brief — Truck-crew replay tool (영덕 2025-03-25)

Written 2026-09-13 in the author's HQ session. This is the specification another agent
builds from. The HQ session owns strategy; this brief owns scope. Harness stays paused;
work happens in laptop sessions on `auto/dev`, never `Main`.

## What it is
A single-page, offline tool for a vehicle crew waiting at a depot (119안전센터 / 산불진화차
거점) that replays the real 2025-03-25 영덕 fire from the committed hazard field and shows,
one vehicle at a time, the next pickup, the corridor and its closing minute, the abort rule,
the egress and the refuge, with acknowledge / arrived / delivered / aborted buttons
timestamped locally. Everything it shows is graded afterwards against the observed FIRMS
footprint so the finals can state what the sheet got right and wrong on a fire that burned.

## Non-goals (do not build)
Live forecasting on a new ignition (a five-second "wiring" demo comes later); person-level
capacity, queues, traffic; any judge-facing README/screen/Q&A change; any change to a
committed artifact or number.

## Inputs that already exist (read, never rewrite)
- Hazard: `data/processed/routing_demo_canonical.npz` (`haz_stack`, `haz_times`, `obs_stack`, `obs_times`).
- Scenario builder: `scripts/run_rescue_routing_real_hazard.py::build_scenario` (real OSM walk/drive, 50 refuges, 4 depots, 444 sampled origins) and `scripts/run_rescue_routing_full.py::materialise_snapshots`.
- Building origins (주건물, 19,959 → 19,250 routed): `data/processed/external/juso_buildings_yeongdeok/`, `data/processed/building_origin_routing_juso_main_yeongdeok.json`, and `src/wildfireguardian/buildings/` (`source="juso_main"`).
- Rescue pipeline and helpers: `src/wildfireguardian/routing/rescue.py` (`rescuer_route`, `rescuer_reachable`, `assess_destinations`, `node_survival_time`, `ingress_corridor`), `rescue_demo.py`, `margins.py` (`round_trip_margin`).
- A working one-home-per-trip fleet scheduler with deadlines: `scripts/run_vehicle_pickup_intervention.py` (EDF, load/unload, egress to nearest rescue-reachable refuge).
- Observed grading rule and code: `docs/regrade_three_way.md`, `scripts/regrade_three_way.py::classify_route`, `scripts/grade_building_origins_observed.py`.
- Printable/PDF path: `src/wildfireguardian/delivery/printable.py` (headless Chrome), `scripts/generate_dispatch_outputs.py`.
- Offline-screen pattern: `scripts/finals.template.html` + `scripts/build_finals.py` (no external assets; `check_screen_assets.py`).
- Doctrine numbers to display beside the clock: 5 h immediate evacuation, 8 h for 재난취약자 (docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md §Update 2026-09-10).

## Deliverables
1. `scripts/build_truck_crew_replay.py` → `data/processed/truck_crew_replay_yeongdeok.json`:
   per vehicle (k = 4, one per OSM depot; also k = 2, 6) the ordered trips from the scheduler
   on the 주건물 population's rescue-needing nodes (immobile draw + no-safe-walk class), each
   with: pickup walk node + drive node + buildings behind it, ingress route geometry, ETA,
   corridor closing minute (forecast), margin, **abort rule** (latest minute to be at the
   pickup = closing − 12; fallback corridor = second-best depot route if any), egress route,
   refuge, delivery minute. Plus the **observed grading** of every ingress and egress leg
   (admissible / indeterminate / inadmissible under `regrade_three_way` A1–A6, cell membership)
   and the counts the finals will quote: trips ordered, reached before the observed closure,
   not reached, aborted-by-rule.
2. `web/truck_crew_replay.html` (built from `scripts/truck_crew_replay.template.html` by the
   build script; no external assets; opens from `file://`): a clock slider 0–720 min with
   markers at 5 h and 8 h; a map (SVG or canvas from the EPSG:5179 geometry, no tiles);
   the four state buttons with local timestamps persisted in `localStorage`; a "print this
   vehicle" A4 view and a KML/GeoJSON download of the vehicle's trips (note: viewers in the
   artifact sandbox cannot download, so also write the files to `outputs/truck_crew_replay/<stamp>/`).
3. `docs/truck_crew_replay.md`: rule declared before the run (scheduler, deadline, abort rule,
   grading), results, what it does NOT show (buildings ≠ households; one home per trip; the
   deadline is the forecast's; the observation is FIRMS at 500 m; 영덕 only).
4. `tests/test_truck_crew_replay.py`: artifact counts re-derive; every trip's abort minute ≤
   closing minute − margin; the HTML has no external asset; the printed page ≤ 1 page.

## Discipline (from docs/auto/CHARTER.md; read it first)
- New results → new filenames; never modify a committed artifact; never regenerate `docs/figures/*.png`.
- Numbers on judge-facing surfaces only through the additive registrars; this build touches none.
- Before push: `python scripts/auto/gates.py --mode full` must exit 0 (read the exit code, never pipe to tail); stage by explicit path; `git pull --rebase origin auto/dev`; push `auto/dev`. Use `git -c url."https://github.com/".insteadOf="git@github.com:"` on this laptop (ssh hangs). Python: `.auto/venv/bin/python` (3.11).
- Gate lessons: `check-declared-deps` forbids new imports (use geopandas, not pyogrio); `check-number-collisions` flags bare numbers beside registered anchors (write words or add `<!-- collision-ok: v -->`); rebuild `docs/artifact_manifest.json` after staging a new artifact; JUDGE_QA Q29a and README §5 ① must carry no digits.
- Report back in one file: `docs/auto/briefs/TRUCK_CREW_REPLAY_REPORT.md` — what was built, the counts, what did not work, open questions for HQ.

## Success line for the finals (to be filled with measured numbers)
「2025년 3월 25일 영덕 실제 화재에서, 이 화면이 4대의 차량에 내린 N건의 출동 지시 중 M건은
위성이 관측한 화선이 도달하기 전에 도착했고, K건은 이 화면이 스스로 중단 규칙으로 취소했다.」
