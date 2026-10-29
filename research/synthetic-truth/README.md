# Synthetic-truth validation of routing decisions (observing system simulation experiment), track 1C-3

**Headline (15 frozen Korean windows, 20 missions, 100 withheld trajectories per window; a "case" is one (window, truth, mission)).**

- **C1, member law.** With one-hour trajectory members the router is false-safe (its checked route meets the withheld fire) in **11 of 2,000 cases (0.55%, Wilson 95% 0.31% to 0.98%)** at K = 4, the same as the frozen independent members (11 of 2,000), and **5 of 2,000 (0.25%, 0.11% to 0.58%)** at K = 16, which buys this by refusing one mission that had a clairvoyant route in every truth (**false-refusal 100 of 1,500, 6.67%**). Every false-safe case comes from **2 of the 20 missions** (Uiseong-Andong 2025-03-23 FX2 and Uljin 2022-03-04 12:00 FW2); 18 missions are never false-safe and never falsely refused. Unresolved: **0** in every configuration.
- **C2, forecast quality.** Doubling the forecast hazard (rate x2) cuts false-safe to **3 of 2,000 (0.15%)** at a cost of **200 of 1,500 false refusals (13.3%)**; halving it, a spatially uniform forecast with the same expected ignition count, persistence and the current-state-only policy all stay at **11 to 13 of 2,000 (0.55% to 0.65%)** with no false refusal. On this panel the Brier score barely separates the forecasts (mean 0.0032 to 0.0037), so the curve "decision quality versus forecast quality" is flat apart from the conservative x2 forecast.
- **C3, acceptance rule.** `k_of_m` with k/m = 0.9 or 0.75 removes every false refusal of K = 16 and K = 32 but returns to 11 to 13 false-safe cases out of 2,000; `all` with K = 32 gives **0 false-safe** and **200 false refusals (13.3%)**. Alpha moves cases between false-safe and false-refusal; nothing here is free.
- **C4, retrospective (reconstructed arrival, Zenodo rasters).** Against what the reconstruction says happened in the hour after each cutoff, the frozen forecast members (v1, K = 4) give **0 false-safe and 0 false-refusal on 20 missions**; the policy that ignores the forecast (current-state contact only) and persistence each take one route into reconstructed fire (**Uiseong-Andong 2025-03-24 09:00, mission FL2**: arrival 1,616 s through cells that the reconstruction burns within the hour, against the forecast-informed 2,143 s, which is also the clairvoyant optimum). Trajectory members at K = 16 refuse one mission (Uljin FW2) that had a clairvoyant route.

These are model-relative statements: holdout truths are trajectories of the same forecast model, reconstructed truths are kriged satellite reconstructions, and no result is an observed evacuation or a field validation.

## What was run

The router (the 1C decision procedure: exact contact-only relaxation by SIPP from track 1C-2, then the per-member check of dose and peak with the cheap checker of track 1C-1, then the recorded acceptance rule) sees only the forecast members. Each decision is executed against every truth of its window and scored with Contract E fields: `true_contact`, `true_peak`, `true_dose`, `arrival_s`, `clairvoyant_arrival_s` (the earliest checked journey computed with the truth itself), `false_safe` (a checked route that meets the true fire or exceeds the true peak or dose limit), `false_refusal` (no-route or unresolved while a clairvoyant route existed; the kind is kept in `refusal_kind`), `regret_s`. All false-safe cases in C1 to C4 are flame contact; no true peak or dose limit was exceeded (the source cap of 0.703 kW/m2 cannot reach the 10 kW/m2 peak limit).

| Campaign | Truth | Forecast sources | Cases | Records |
|---|---|---|---:|---|
| C1 | holdout trajectories 512..611 of the export v3 rollout (N = 1,024, seed 0) | v1_K4 (frozen packet), v1_K16 (frozen bridge law, seed 20261008), v2_K4, v2_K16 (first trajectories of 0..511), v2_K16_ordered, v2_K16_fs (forward selection on the edge-arrival distance over 0..511, extremes appended) | 6 x 2,000 | `data/C1.jsonl.gz` |
| C2 | same | rate_x0.5, rate_x1, rate_x2 (independent per-cell draws from q_c = 1 - (1 - q)^c, K = 16, common random numbers, seed 20261008), persistence, uniform, current_state_only | 6 x 2,000 | `data/C2.jsonl.gz` |
| C3 | same | v2 first K trajectories, K in {4, 8, 16, 32}, rule all and k_of_m with k/m in {0.9, 0.75} | 12 x 2,000 | `data/C3.jsonl.gz` |
| C4 | reconstructed arrival of the parent fire in the hour after the cutoff | v1_K4, v2_K16, current_state_only, persistence | 4 x 20 | `data/C4.jsonl.gz`, `data/C4_journeys.json.gz` |

At the one-hour horizon of every frozen mission a trajectory is one transition from the cutoff state, so v1 and v2 members have the same law (see `research/scenario-members/README.md`); differences between v1_K4 and v2_K4 are Monte Carlo noise, which here is zero at the decision level. rate_x1 equals v1_K16 by construction (same draws).

## Tables

C1 (member law and count):

| Forecast members | Cases | Routes / no-route / unresolved (cases) | False-safe | 95% Wilson | False-refusal | 95% Wilson | Missions with a false-safe | Missions with a false-refusal | Mean Brier |
|---|---:|---|---:|---|---:|---|---:|---:|---:|
| v1_K4 | 2000 | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00386 |
| v1_K16 | 2000 | 1500 / 500 / 0 | 17 (0.85%) | 0.53% to 1.36% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00336 |
| v2_K4 | 2000 | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00387 |
| v2_K16 | 2000 | 1400 / 600 / 0 | 5 (0.25%) | 0.11% to 0.58% | 100/1500 (6.67%) | 5.51% to 8.04% | 1 | 1 | 0.00334 |
| v2_K16_ordered | 2000 | 1400 / 600 / 0 | 5 (0.25%) | 0.11% to 0.58% | 100/1500 (6.67%) | 5.51% to 8.04% | 1 | 1 | 0.00334 |
| v2_K16_fs | 2000 | 1300 / 700 / 0 | 5 (0.25%) | 0.11% to 0.58% | 200/1500 (13.33%) | 11.71% to 15.15% | 1 | 2 | 0.00553 |

C2 (forecast quality):

| Forecast members | Cases | Routes / no-route / unresolved | False-safe | 95% Wilson | False-refusal | 95% Wilson | Missions with a false-safe | Missions with a false-refusal | Mean Brier |
|---|---:|---|---:|---|---:|---|---:|---:|---:|
| rate_x0.5 | 2000 | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00325 |
| rate_x1 | 2000 | 1500 / 500 / 0 | 17 (0.85%) | 0.53% to 1.36% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00336 |
| rate_x2 | 2000 | 1300 / 700 / 0 | 3 (0.15%) | 0.05% to 0.44% | 200/1500 (13.33%) | 11.71% to 15.15% | 1 | 2 | 0.00366 |
| persistence | 2000 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 (0.00%) | 0.00% to 0.26% | 3 | 0 | 0.00319 |
| uniform | 2000 | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 (0.00%) | 0.00% to 0.26% | 2 | 0 | 0.00339 |
| current_state_only | 2000 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 (0.00%) | 0.00% to 0.26% | 3 | 0 | 0.00319 |

C3 (acceptance rule; k = ceil(f m)):

| Members | Rule | Routes / no-route / unresolved | False-safe | 95% Wilson | False-refusal | 95% Wilson |
|---|---|---|---:|---|---:|---|
| v2_K4 | all | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 | 0.00% to 0.26% |
| v2_K4 | k_of_m 4/4 (f = 0.9) | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 | 0.00% to 0.26% |
| v2_K4 | k_of_m 3/4 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 | 0.00% to 0.26% |
| v2_K8 | all | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 | 0.00% to 0.26% |
| v2_K8 | k_of_m 8/8 (f = 0.9) | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 | 0.00% to 0.26% |
| v2_K8 | k_of_m 6/8 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 | 0.00% to 0.26% |
| v2_K16 | all | 1400 / 600 / 0 | 5 (0.25%) | 0.11% to 0.58% | 100/1500 (6.67%) | 5.51% to 8.04% |
| v2_K16 | k_of_m 15/16 | 1500 / 500 / 0 | 11 (0.55%) | 0.31% to 0.98% | 0/1500 | 0.00% to 0.26% |
| v2_K16 | k_of_m 12/16 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 | 0.00% to 0.26% |
| v2_K32 | all | 1300 / 700 / 0 | 0 (0.00%) | 0.00% to 0.19% | 200/1500 (13.33%) | 11.71% to 15.15% |
| v2_K32 | k_of_m 29/32 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 | 0.00% to 0.26% |
| v2_K32 | k_of_m 24/32 | 1500 / 500 / 0 | 13 (0.65%) | 0.38% to 1.11% | 0/1500 | 0.00% to 0.26% |

C4 (reconstructed arrival; one truth per window): per-mission rows in `C4_cases.csv`; summary in `C4_summary.csv` and above. The reconstruction burns far more cells in the hour after each cutoff than the forecast members (for example 662 new cells in the Uiseong-Andong window at 2025-03-25 17:00 against a forecast expectation of about 5 inside the window), which shows in the mean Brier score (0.081 against 0.003 to 0.004 for the holdout truths). None of this extra fire lies on a route returned with the frozen members; one route of the forecast-ignoring policies meets it.

How to read the rates. Cases share decisions: each configuration makes only 20 decisions (one per mission), each scored against 100 truths, and false-safe cases cluster in two or three missions. The Wilson intervals are over cases and therefore understate the uncertainty about missions; the mission counts are the more honest summary. The two Gyeongbuk panels (Uiseong-Andong, Yeongdeok) are one parent fire (`C1_by_parent_fire` in `RESULTS.json`). Repetitions are not used.

## Figures

- `figures/fig01_false_safe_false_refusal_by_members` (PNG 300 dpi and SVG). C1: false-safe rate over all 2,000 cases (vermillion) and false-refusal rate over the 1,500 cases that have a clairvoyant route (blue) for each forecast member set, rule `all`; whiskers are 95% Wilson intervals over cases (which understate uncertainty about the 20 missions). Truths: holdout trajectories 512..611 per window.
- `figures/fig02_decision_vs_forecast_quality`. C2: each forecast source placed at its mean Brier score against the holdout truths (x) with its false-safe rate (circles) and false-refusal rate (squares), rule `all`, K = 16 except persistence and current_state_only (one member).
- `figures/fig03_acceptance_tradeoff`. C3: false-safe rate against false-refusal rate for trajectory members K in {4, 8, 16, 32} (colour) under `all` and `k_of_m` with k/m targets 0.9 and 0.75 (marker); same truths as C1.
- `figures/fig04_retrospective_uiseong_map`. C4: executed journeys of the four forecast sources for Uiseong-Andong, cutoff 2025-03-24 09:00 UTC, mission FL2, over the reconstructed time of arrival relative to the cutoff (cells with arrival between 6 h before and 6 h after the cutoff; 0 to 1 h is the scored hour). The current-state-only and persistence routes (1,616 s) cross cells the reconstruction burns within the hour; the forecast-informed routes (2,143 s) do not. Road network in grey. This is a reconstruction, not observed flames.
- `figures/fig05_retrospective_yeongdeok_map`. Same for Yeongdeok, cutoff 2025-03-25 19:00 UTC, mission FX2 (all four sources arrive at 2,512 s and none meets reconstructed fire). The prompt asked for a Caldor map; the Caldor inputs are not on this host (below), so the second Gyeongbuk panel is shown instead.

## Truth sources and data

| Source | Status here | Identity |
|---|---|---|
| holdout_trajectory | run (C1 to C3) | export v3 replay of the 15 frozen v2 exports, N = 1,024, seed 0; v3 NPZ hashes in `research/scenario-members/data/exports_v3/INDEX.json` |
| reconstructed_arrival | run (C4) for all five Korean panels | Zenodo 10.5281/zenodo.21788344 (CC-BY-4.0), archive SHA-256 `612edf5f879d8fe874ae20e9d49d0be5de477e6f8c3101b434f1642d5b19ebad`; the KFS_01, KFS_02, KFS_05 and KFS_11 rasters are byte-identical to the `arrival_time_hours.tif` hashes in the frozen export records, and each export's cutoff state equals TOA <= cutoff (checked by `truth.reconstructed_arrival` for every window). Read by a standard-library GeoTIFF reader (`wfg_osse/toa.py`), identical to rasterio on all four rasters. |
| device_offline | implemented, tested on fixtures (schema below); no packets exist yet (track 1D) | orchestrator decision extending Contract E |
| observed_perimeters | not run | NIROPS perimeters cover U.S. fires only; none of the 20 missions is in the U.S. |
| external_simulator | loader implemented and tested; not run on the panel | FARSITE (public Unix port, github.com/mbedward/farsite at 4537d60a, built with the repository's `forecast/wildfire/farsite_build.py`, executable SHA-256 `b6ee69a2...` on this host) builds and runs its flatland example here (time-boxed attempt, under 30 minutes). A Korean scenario needs the landscape (terrain, fuel, canopy) and weather rasters of the forecast data root, which are not on this host, so no Korean FARSITE truth was produced. |
| Caldor 2021 / Rim 2013 | not run | the sealed-study packets are not on this host, and Caldor is not in the Zenodo archive |

Frozen Korean routing inputs: `tools/fetch_routing_inputs.py` (release research-final-20261015, archive SHA-256 `d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202`), used read-only at `/home/user/wfg-shared/routing-inputs` (`INPUT_FILES.json` SHA-256 `5d820b97740d879d2bc78a76d1b5854420793c927c6315f656dc1c2927b35235`).

### device_offline packet schema (`wfg.truth.device-offline/1`)

```json
{"schema": "wfg.truth.device-offline/1", "label": "...", "horizon_s": 3600,
 "observations": [{"cell": 1234, "burning": [[a, b], ...], "not_burning": [[a, b], ...]}, ...],
 "provenance": {...}}
```

`cell` is the routing graph cell index (south-up rows, as in HAZARD.json); intervals are half-open seconds after the forecast cutoff. A (cell, second) is observed burning, observed not burning, or unknown; every cell not listed is unknown for the whole horizon; a cell may not be observed burning and not burning at once. Scoring excludes unknown (cell, time) pairs: a journey span that meets an observed burning interval is true contact; a span over an unknown pair sets `unknown_exposure` and can neither cause nor clear `false_safe`; dose and peak are not observed (None). The clairvoyant treats unknown as blocked (a journey certifiable from the observations alone); when no such journey exists, `false_refusal` is None (unscorable) rather than False. Tests: `test_device_offline_unknown_cells_can_neither_cause_nor_clear_false_safe`, `test_device_offline_refusal_is_unscorable_when_only_unknown_routes_exist`, `test_device_offline_schema_is_enforced`.

### Reuse

`Sparkxt-0318/wildfireguardian-osse` (read-only clone at 69f3b7ec77aa40a69fbafeb8e39a41288f2eaceb) was read. No code was copied. Three design rules come from it and are cited here: truth never reaches the planner, outages are closed-open intervals, and missingness can be informative (correlated with the hidden fire; failure mode F-05 as described in its `observations/missingness.py`), which is why device_offline scoring never imputes unknown states. The SHA-256 of the files consulted are recorded in `experimental/synthetic-truth/SOURCE_SHA256.json`.

## Reproduce

Routing environment (Python 3.12, NumPy 1.26.4):

```sh
python3.12 -m venv .venv && . .venv/bin/activate
pip install -c constraints-routing.txt './integration[packets]' -r experimental/synthetic-truth/requirements-test.txt
python tools/fetch_routing_inputs.py                     # or set WFG_ROUTING_INPUTS to a verified copy
# export v3 (forecast environment with PyTorch): research/scenario-members/make_exports_v3.py --out EXPORTS
# Zenodo archive: download https://zenodo.org/api/records/21788344/files/wildfire_toa_dataset_and_code.zip/content,
#   check SHA-256 612edf5f..., unzip into its own directory TOA
python research/synthetic-truth/run_campaigns.py --exports EXPORTS --toa-dir TOA/rasters_kr --out research/synthetic-truth/data
python research/synthetic-truth/analyze.py
```

Seeds: export v3 trajectories seed 0 (N = 1,024, batch 32); sub-hour timing seed 20261029; v1 and C2 independent draws seed 20261008; holdout indices 512..611, member pool 0..511; k-medoids not used here. Campaign wall time 716 s for C1 to C4 on this host (`data/host.json`).

Host: Linux container, 4 vCPU, 15 GiB, no GPU, shared with two other track agents (load average 5.1 to 7.2 during the run), Python 3.12.3, NumPy 1.26.4. Decision times in the records (median 0.41 s, maximum 4.5 s per C1 decision) are host-specific Linux measurements and are not comparable with the frozen native-Mac timings.

Tests: `experimental/synthetic-truth/tests/test_harness.py` (the four required behaviours, device_offline masking, truth builders, external simulator loader). Commands and exit codes of the gate run are in `research/synthetic-truth/PROGRESS.md`.

## Scope and limits

- Truths are model or reconstruction based: holdout trajectories are draws of the same forecast model, so C1 to C3 measure how the member law, member count, forecast degradation and acceptance rule translate model uncertainty into decisions, not forecast accuracy. Reconstructed arrival rasters are kriged satellite detections inside a known final perimeter; they are not observed flames and carry their own errors (kriging standard deviation not used here). No result is an observed evacuation, and nothing here is a field validation.
- Results are conditional on the frozen road graphs, lattice (1 s, waits only at waitable nodes), one-hour horizon, destination windows, the scalar construction law (coarse-cell duration T, present-fire enclosure) and the centre-cell radiation of the inherited operator. Peak flux cannot bind on this panel (source cap 0.703 kW/m2).
- At the one-hour horizon trajectory members equal independent members in law; the member-law comparison (C1) can only show Monte Carlo differences and the effect of member count. Multi-hour coherence needs the environmental rasters, which are not on this host.
- 20 decisions per configuration; false-safe cases concentrate in two or three missions; Wilson intervals over cases understate mission-level uncertainty. The two Gyeongbuk panels are one parent fire.
- Router checks and truth scoring use the cheap checker (exact contact, dose by linear superposition of the inherited operator, conservative by at most 1e-5 relative); tests compare its pass flags with the frozen centre checker. Continuous-road radiation (the kit's whole-road checker) is not used here.
- Track 1A's radiation law v2 is not integrated: the checker's `radiation_law="v2"` raises `NotImplementedError("law v2 not available")`.
- Unresolved is its own outcome everywhere; no unfinished computation is counted as a route or a refusal (none occurred in C1 to C4).
