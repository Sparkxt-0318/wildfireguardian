# Decisions

Dated, one line of reason each. Interface changes also bump `hazard_contract.CONTRACT_VERSION`.

- **2026-10-31** — Program started in a Claude Code cloud container, not on the Mac.
  Reason: the session was launched in the cloud; work that needs no Mac data proceeds here,
  data-dependent work is flagged as blocked rather than replaced with synthetic data.
- **2026-10-31** — `claude/ecstatic-keller-fm31to` mirrors `next/integration`.
  Reason: the cloud session must push its designated branch; Siyeong's branch layout is kept.
- **2026-10-31** — Bench lock = Python `fcntl.flock` on `<main checkout>/program/.bench.lock`
  via `program/benchlock.py`. Reason: stock macOS lacks `flock(1)`; one file shared by all
  worktrees.
- **2026-10-31** — Per-folder `.gitignore` files instead of editing the root `.gitignore`.
  Reason: the root is part of the frozen release.
- **2026-10-31** — No torch in the cloud venvs for now. Reason: the CPU wheel index is blocked
  and the PyPI Linux wheel set is over 1 GB (needs approval); c651 needs Mac data anyway.
- **2026-10-31** — `hazard_contract` v1 (`CONTRACT_VERSION = "1.0"`) published on `next/integration`.
  Reason: shared interface before track agents start.
- **2026-10-31** — `SegmentHazard` gains `dose_lower`/`dose_upper` (kJ/m²) beyond the specified
  fields. Reason: peak-flux bounds alone cannot certify a cumulative-exposure violation.
- **2026-10-31** — Reference flux law = the `wfg_latest` finite-cell sheet law (`sheet_solid_angle_v1`),
  with `HeatSource` adding `consumed_fraction` and emission/receiver heights. Reason: the oracle
  must reuse the router's physics; the law caps flux at q_rad/2 = 0.70 kW/m², so with the
  repo's parameters the 10 kW/m² peak budget never binds and contact + dose decide.
- **2026-10-31** — Contact uses closed cells (the existing checker's "whole-road" rule);
  `segment_uniform` adds the router's uniform-motion occupancy. Reason: the API already requires
  whole-road CLEAR for a checked route; it is the stricter of the two rules.
- **2026-10-31** — `from_wfg_packet` applies rule 4 with no opt-out: missing native probability or
  unknown burned state ⇒ unsupported. Reason: the user's rule; it leaves 32–100% of Korean road
  cells unsupported (question for Siyeong whether a labeled "packet policy" mode is wanted).
- **2026-10-31** — Geometry touching the grid's outside or a query past `horizon_s` ⇒ unsupported;
  sources outside the grid are not modelled. Reason: unknown is not unburned; producers pad grids.
- **2026-10-31** — `hazard_contract` 1.0.1 (format unchanged, `CONTRACT_VERSION` stays 1.0): fixes from an
  independent adversarial review (12 confirmed findings, each now a regression test). Reason: two
  false-safe paths (polygon holes filled; float time drift in `query_uniform`) and ten smaller
  honesty gaps. Behaviour changes: polygons use GeoJSON nesting with holes kept; `from_wfg_packet`
  default `present_fire="enclosure"` (what the router used) and also reads
  `mask__unknown_cumulative_state`; geographic / Web Mercator CRSs refused (interface tightening —
  needs Siyeong's confirmation); interval policy treats unknown emission as unbounded.
- **2026-10-31** — Contact that happens only after `horizon_s` is `unresolved` in the oracle
  (`BEYOND_HORIZON`), never `model_no_route`; `hazard_contract` query semantics unchanged (such a
  query already returns `supported=False`). Reason: the set says nothing after its horizon. To confirm
  with Siyeong (evacplan ASSUMPTIONS question 4).
- **2026-10-31** — The oracle may use two non-public `hazard_contract` helpers (`scenario.uniform_pieces`,
  `geometry.polyline_cells`) for exact slack and the relaxed check, guarded by a consistency test.
  Reason: no public "touch intervals" query exists; adding one is an interface change (ask first).
- **2026-10-31** — Caldor region builder = OSM roads via osmnx + CMS provider file + Census geocoder +
  `from_perimeters`. Reason: the repo has no usable Caldor/Rim graph or hazards (the sealed study is on
  the Mac). Build blocked here (hosts refused); no instance fabricated.
- **2026-10-31** — SYNTHETIC (and planned Caldor) hazards burn persistently (48 h, packet heat
  parameters), so burned roads stay closed. Reason: conservative default; to confirm with Siyeong
  (evacplan ASSUMPTIONS question 7).
- **2026-10-31** — All Track C methods run single-threaded; B3 runs HiGHS in a child process (OR-Tools
  bundles libhighs 1.11, highspy is 1.15) and the child's start-up counts in B3's runtime; `ortools` and
  `highspy` are the `[solvers]` extra. Reason: equal resources at equal wall clock (question 17).
- **2026-10-31** — Track C comparison rule for time-limited methods: every method runs 3 repeats (seeds 0-2)
  at the same budget; the leaderboard shows mean and min-max; a method "beats B2" only if its **minimum** dev
  total exceeds B2's **maximum**. Reason: the Phase 0 review showed B2 (seedless, time-limited guided local
  search) moves by about 67 residents between reruns — one instance flips 155/0 ↔ 88/67 with search depth.
- **2026-10-31** — `ortools` capped below 9.15 for B2, and each track commits a `requirements.lock` of the venv
  that produced its results. Reason: a fresh install resolved ortools 9.15.6755, whose Python wrapper rejects
  `SetAllowedVehiclesForIndex` arguments (B2 crashed, 7 tests failed), and numpy 2.5, which dropped `np.trapz`.
- **2026-10-31** — scikit-learn 1.5.2 (Track A logistic baseline) and hypothesis (property tests in all three
  packages) are in use although rule 8 does not list them. Reason: installed by the orchestrator at setup;
  scikit-learn 1.5.2 is the frozen `forecast` package's own `baseline` extra and `wildfire.baselines` fits the
  same logistic model with it. Needs Siyeong's confirmation (else: refit with scipy.optimize). **Approved by Siyeong 2026-11-01.**
- **2026-10-31** — Track A's Phase 0 data notes used survey-interval metadata of the six US-2024 test fires
  (NIROPS catalog provenance: survey times, no outcomes) and Korean test-fire window counts from
  `events.json` to discuss the lead. No outcomes or scores were read. Reported to Siyeong (rule 5); the 24 h
  lead rests on the Korean dev label MAE.
- **2026-10-31** — Interim bar for "beats B2": the best B2 dev total observed at the same budget with the same
  search code, currently **1750** (Phase 0 review run at `957e6720`; B2's search code is unchanged since, only
  diagnostics were added), not the 1682 of the three committed repeats. Reason: on a quiet host the three
  repeats were identical (1682 delivered, 68 unresolved); on a busier host the seedless search stopped
  earlier and got 1750 / 0. The bar must not depend on host load. To confirm with Siyeong (alternative: a
  pre-registered B2 solution limit).
- **2026-10-31** — Track C refusals that hold even with nothing burning get their own cause,
  `UNSERVABLE:NO_TRIP_BY_HORIZON`; the state stays scoped `model_no_route` (evacplan ASSUMPTIONS #74,
  question 12). Reason: review C-M3, the old label blamed contact. Only the label changed; the oracle's trip
  verdicts did not.
- **2026-10-31** — Track C tests regenerate test-set instances only with `EVACPLAN_MILESTONE=1`, which is
  set only at milestones Siyeong approves. Reason: rule 5 (review C-M4: the suite rebuilt all 10 test
  instances in memory for its fingerprint checks).
- **2026-10-31** — Track C result rows (`evacplan/results/*.csv`) are committed with the leaderboard; plans
  and oracle results (`results/runs/`, ~120 MB) stay ignored; the harness dirty check skips generated rows.
  Reason: the rows existed only on the ephemeral cloud host; Track A already commits its rows.
- **2026-10-31** — Track A decision truth from Choi reconstructions: the 8-neighbour ring of the
  finite-arrival mask burns from its burned neighbours' earliest ignition to their latest extinction. Rows
  also record the centre-in verdict, and reports count `truth_ring_flips`. Reason: review A-M1, the
  centre-in mask made partly burned edge cells truth-safe, which biased false-safe low. Calling those cells
  unknown instead would have dropped 220 of 296 truth-safe requests in the verifier's SYNTHETIC check. This
  approximates the all-touched rule until KFS perimeter polygons exist; to confirm with Siyeong
  (firecast-lab README question 4).
- **2026-10-31** — Track A leaderboard = sums of additive per-window terms with whole-fire bootstrap
  intervals. Spread-skill uses fixed member-sd bins, because deciles cannot be pooled across windows. Runs
  that scored different cells or windows are refused. Reason: review A-M4, the metrics were coded but no run
  produced them. Bins to confirm with Siyeong.
- **2026-11-01** — Siyeong's checkpoint 2 answers (recorded here; they override earlier entries where they differ):
  1. **Data access deferred.** The program stays in this cloud session. The Track A real-data leaderboard and the
     Caldor instance resume later on the Mac. No data is invented in the meantime.
  2. **Track C batch 1 approved:** E1, E4 and E3 on the SYNTHETIC dev set, at most 3 agents at once, timed runs
     through the bench lock. E4's validity check: on S instances the bound must be ≥ B3's achieved value;
     otherwise it is a bug.
  3. **Comparison rule** (replaces the 3-repeat rule of 2026-10-31):
     - Every method runs 5 repeats (seeds 0-4) on a quiet machine.
     - The leaderboard reports the median and [min-max].
     - A method beats B2 only if its worst of 5 repeats exceeds both B2's best observed total (1750 on this host,
       Phase 0 review run) and the best-of-baselines total (the per-instance best of any baseline, summed: 1751).
     - Every row records its host, and times are never compared across hosts. On the Mac, the baselines are
       re-run.
  4. **Dose.** B2 stays as specified; E1 handles dose through the oracle. Report the peak-flux and
     cumulative-dose distributions of the SYNTHETIC instances next to the real Korean panel (peak about
     0.7 kW/m²). If the SYNTHETIC hazards are much hotter, tell Siyeong before tuning to them.
  5. **Margin.** No change to the problem definition. Rows report the residents delivered with slack ≥ 0, 5, 15
     and 30 min, the leaderboard plots delivered vs required margin, and E3 recommends the default margin.
  6. **scikit-learn 1.5.2 and hypothesis are approved.**
  7. **Track A's test-fire metadata numbers in DATA_NOTES stay.**
  8. **Fresh holdout.** Propose a truth source for 2025 US fires, with its limits: a proposal only, no downloads.
- **2026-11-01** — The Korean panel for the hazard-intensity comparison uses the dev fires' router packets only
  (Uljin 2022, Hongseong 2023, Miryang 2022). The `uiseong_andong_2025` and `yeongdeok_2025` packets belong to
  the KR-2025 test season and are not read. Reason: rule 5.
