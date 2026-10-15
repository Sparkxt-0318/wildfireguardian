# WildfireGuardian latest-forecast completion kit (15 October 2026)

One immutable kit for the bounded latest-forecast research campaign of `latest_forecast_routing_completion_20261015_v1`.

## Contents

- `routing_candidate/`, `phaseB/`, `decision/`, `checking/`: copied byte-for-byte from the historical repaired routing kit
  (ZIP SHA-256 `59fa306a...`). Arm RDA_BASE is the reviewed reference worker (`phaseB/baseline_worker.py`), arm RDA_CAND
  the reviewed candidate worker (`phaseB/rda_worker_v1_1.py`). Both run full policy: the same graph, hazard packet, request,
  limits, incurred exposure, destinations and dwell, mandatory runtime whole-road check and authoritative decision.
- `runner/`: launcher `wfg_native.py` (v2), lifecycle-repaired controller `wfg_controller.py` (2.1: verified ownership by
  process group, refreshed lineage with start-time identity and parent lineage; unknown is never clean; lease withheld
  on unclean cleanup), tally `native_tally.py` (v2, two repetitions, regions from each job), report `native_report.py`
  (v2); unchanged: independent checker, witness whole-road check, preflight control worker, lease client.
- `queues/`: `LATEST_PRIMARY` (80 attempts: 20 missions in five regional groups x 2 arms x 2 repetitions, 30 s complete
  request deadline, 3,072 MiB guard, fast cold preparation in both arms, regions interleaved, ABBA per mission),
  `LATEST_PREFLIGHT_CONTROLS` (six controller lifecycle controls), `LATEST_PREFLIGHT_REAL` (one unscored real attempt).
- `INPUT_BINDING.json`: every input (5 road graphs, 15 latest-forecast hazard packets, 20 re-keyed requests) by
  workspace-relative source path and SHA-256, plus the latest input freeze it came from. Inputs are copied into
  `inputs/latest/` and verified at launch.
- `CANDIDATE_MANIFEST.json`: SHA-256 of every kit file; the launcher refuses to run if a file changed or code was added.

## Running (native macOS)

`<env python> runner/wfg_native.py all --workspace <workspace>` (background, under `caffeinate -i -s`). It takes the shared
lease only from a documented FREE record and the local lock, records the environment, copies inputs, runs the preflight gate,
the 80-attempt queue, offline independent checking (120 s cap per attempt, never retried) and the tally, then writes
`NATIVE_SUMMARY_primary.json/.md`. `status` is read-only. Nothing waits or schedules.

## Scope

Resolution is model-relative benchmark resolution under the frozen classes, not accuracy and not physical safety. The hazard
packets use the declared scalar maximum-remaining present-fire enclosure under construction law `wfg.hazard.construction/1`.
Independent continuous-road radiation enclosure and global optimum/refusal proof obligations remain open.
