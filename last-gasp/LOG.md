# Log

Append-only. Times are Asia/Shanghai (CST, UTC+8). All results are synthetic. Entries before 23:06 were written up after the fact from command history, so their times are approximate (within about 10 min). Every number quoted in summaries here is in `results/NUMBERS.json`, except the exploratory numbers marked "exploratory", which came from code states that were later changed and are kept only as a record of decisions.

## 2026-10-14 22:37 Setup

- Goal: confirm the repository and set up `last-gasp/`.
- Commands: `git rev-parse --show-toplevel` (gave /home/user/wildfireguardian); read `README.md` (routing API package); searched the repository for FIRMS data.
- Results:
  - Repository root confirmed, on branch `claude/affectionate-dijkstra-c6zrp7`.
  - No FIRMS detections for a Korean fire exist in the repository; there is only a mention in `forecast/documents/korean_observation_availability_20261012.md`. FIRMS data were therefore not used.
- Decision: create `last-gasp/` with its own `.venv`, `requirements.txt` and `.gitignore`.
- Next step: get building footprints.

## 2026-10-14 22:40 OSM download (partial failure)

- Goal: real building footprints for a fire-hit area.
- Commands:
  - `curl` Overpass count queries against overpass-api.de, overpass.kumi.systems, overpass.private.coffee and maps.mail.ru. All failed with connection reset, timeout or 504.
  - `curl https://api.openstreetmap.org/api/0.6/map?bbox=...` for seven roughly 3 km boxes in Uiseong, Andong and Yeongdeok.
  - Downloaded the Microsoft Global ML Building Footprints index.
- Building counts per box (OSM building tags):

  | Box | Buildings |
  |---|---|
  | Yeongdeok-eup | 59 |
  | Uiseong-eup | 40 |
  | Andong city east | 373 |
  | Yeongdeok Chuksan | 3 |
  | Yeongdeok Ganggu | 5 |
  | Uiseong Anpyeong | 1 |
  | Andong Imha | 0 |

  The Microsoft index has no Korean tiles.
- Decision:
  - Use the Yeongdeok-eup box: 129.350 to 129.385 E, 36.400 to 36.430 N, 10.4 km².
  - It has a good road network (716 highway tags), 59 mapped buildings, and the mapped Yeongdeok Substation (154 kV).
  - Use real roads and substation and add 1,441 synthetic buildings along roads. This is a hybrid, not a full synthetic fallback, and is stated in every document.
- Next step: research agent for step 6 in parallel; build the fire model.

## 2026-10-14 22:45 Desk research launched

- Goal: step 6 (AMI in Korea, last-gasp logging, data holders).
- Action: background research agent with web search and fetch only; no files written.
- Next step: build the simulation meanwhile.

## 2026-10-14 22:50 Fire model test (exploratory)

- Command: inline test of `lastgasp.fire.simulate_fire` on world seed 0.
- Parameters: wind 8 m/s from the west, head spread rate 48 m/min, LB 3.68, 10 m cells (314 by 332), full west-edge line ignition.
- Results:
  - 5.0 s per world; 96% of cells burned by 150 min.
  - 17 spot ignitions, 8 with lead of 10 min or more.
- Decision: restrict the ignition line to the middle 60% of the west edge so flanks exist.

## 2026-10-14 22:55 First end-to-end run (exploratory, failure mode found)

- Command: `run_one(cfg, 0, 0)`.
- Parameters: one feeder breaker, fuses at laterals, span fault probability 0.30 per 50 m span.
- Results:
  - 99% of meters in buildings the fire reached lost power to an upstream fault first (`frac_fire_censored_by_grid` 0.988).
  - Fire-caused deaths were 0.8% of delivered messages.
  - Huygens median error 11.2 min.
- Decision:
  - The network was unrealistically fragile. Add 6 feeders, reclosers every 1 km on main lines, local transformer faults (probability 0.3), and lower the span fault probability to 0.05 (swept later).
  - Keep the censoring effect as a finding.

## 2026-10-14 23:00 Reconstruction method iteration (exploratory)

- Results after the network change (world 0):
  - 81% of fire signals censored; topology classifier balanced accuracy 0.90.
  - IDW 5.65 / 26.3 min median / 90th percentile. Plain Huygens min-plus 10.3 / 30.3. The fitted spread was nearly isotropic in the wrong direction.
- Variants tested on worlds 0, 2 and 3:
  - Huygens with the true parameters was worse (14.6 / 63.9 in world 0).
  - 3rd-order statistic: 6.9 / 18.9, 4.0 / 22.7, 7.4 / 29.6.
  - Local robust plane fit: no better than IDW.
  - 3rd-order statistic plus residual correction (L = 200 m): 5.8 / 22.9, 5.2 / 22.4, 3.9 / 16.1.
- Decision: adopt the 3rd-order statistic plus residual correction as the "better" method.
- Also tried: choosing between IDW and Huygens by leave-one-out error. It always picked IDW because leave-one-out error cannot see extrapolation error, so it was removed.
- Spot detection fixes:
  - Support must come from later deaths that are themselves early.
  - Reject candidates with a simultaneous partner under the same small protective device.
  - Precision now counts a match to any true spot; recall counts significant spots only.
- Next step: sweeps.

## 2026-10-14 23:06 Checkpoint commit 4ef08f0

- Pipeline modules committed.

## 2026-10-14 23:08 First full sweep (superseded by the 23:15 rerun)

- Command: `.venv/bin/python scripts/03_sweeps.py --fire-seeds 5 --obs-seeds 2 --workers 4`
- Runs: 410, 0 errors, 239 s. Code was uncommitted at the time (based on 4ef08f0).
- Results were identical to the 23:15 rerun below; the pipeline is deterministic given seeds.
- Figure fixes after inspection:
  - fig1: legend overlapped the axis labels, and the colorbar was detached.
  - fig2: titles overlapped; masked cells far from buildings.
  - fig3: title too wide.
  - fig4 and fig5: cluttered log tick labels.
  - fig6: x-labels overlapped.
  - fig7: category labels touched.
- Demo simulation: the first figure run had 5 of 25 tags surviving the fire. This was not a bug: the survival chance is 5% per tag and the draw was unlucky. The figure now shows the first run with at most one survivor (run 1).

## 2026-10-14 23:12 Desk research received; spot checks

- The agent's report is summarised in `docs/DESK_RESEARCH.md`, with all sources in `data/SOURCES.md`.
- Re-checked by fetching:
  - Newsis 2025-04-28: 18 transmission lines, 2 substations, about 93,000 households for about 9 hours. Confirmed.
  - Electimes 2022-09-19: 48% national and 39% Gyeongbuk AMI penetration. Confirmed, but the article gives no explicit reference year. Wording corrected.
- Four paper DOIs verified through Crossref and doi.org.

## 2026-10-14 23:15 Clean reproduction at commit 2d903ed

- Goal: tie every number to a clean commit.
- Command: `bash scripts/run_all.sh` (log in `results/run_all.log`).
- Steps run: world build, two example runs, 410-run sweep (220 s, 0 errors), figures, demo simulation (10 runs), numbers.
- Key results:

  | Setting | Result |
  |---|---|
  | Meters 50% (73 per km²), Huygens | 5.2 / 21.5 min |
  | Meters 50%, IDW after filtering | 5.4 / 26.7 min |
  | Meters 50%, naive IDW | 6.5 / 24.7 min |
  | Fire signals censored by an earlier grid outage | 75% |
  | Topology classifier balanced accuracy | 0.89 (time-only 0.51) |
  | Meter density 6.8 to 144 per km², Huygens median | 5.1 to 6.2 min |
  | No fire-caused grid faults, IDW after filtering | 2.4 / 8.5 min |
  | Substation trip at 20 min, Huygens | 27.4 / 49.9 min |
  | Tags 50%, IDW | 0.6 / 2.0 min |
  | Tags 13.5 per km², IDW | 1.2 / 6.9 min |
  | Meters plus tags 10%, IDW after filtering | 1.8 / 8.5 min |

  - Spot fires, pooled over 10 runs: precision 0.18 and recall 0.03 for meters; 0.33 and 0.17 for tags.
  - Demo analogue (25 tags in 1 km²): IoU 0.74 while the front is inside; detection latency 2.1 min median.
- Decision: write `RESULTS.md` with no-go for meter-only and conditional go for grid-independent nodes.
- Commit cfd0ed9: added spot counts and errors per scenario to the summary. Regenerated `sweep_summary.json` and `NUMBERS.json` from the 2d903ed sweep table.

## 2026-10-14 23:25 Records written

- Wrote `README.md`, `RESULTS.md`, `docs/PARAMETERS.md`, `docs/DESK_RESEARCH.md` and `data/SOURCES.md`.
- Next steps, in priority order:
  1. Improve spot detection: cluster-level evidence, a front-relative likelihood, a time-aware survivor check.
  2. Use grid bursts as coarse constraints instead of discarding them.
  3. Make the physics fit identify spread direction (fit on accepted fire deaths only, with priors from wind).
  4. Add terrain (DEM) and a second wind scenario.
  5. Build the tabletop demo software around the alive-or-dead estimator.

## 2026-10-14 23:30 Numbers file completed

- Added the exploratory numbers quoted above to `results/exploratory_numbers.json`. They appear in `results/NUMBERS.json` under `exploratory.*`, flagged as from uncommitted intermediate code.
- Added sweep wall time, run count, error count and per-world fire statistics: 14 to 20 spot ignitions per world, 2 to 5 significant, 97% to 99% of buildings burned.
- Command: `.venv/bin/python scripts/07_numbers.py` (1089 numbers).

## 2026-10-14 23:33 Phase 2 start; step 0: RESULTS.md bottom line

- Goal: state the phase 1 conclusions plainly at the top of `RESULTS.md`.
- Added a "Bottom line" section, using only numbers already in `results/NUMBERS.json` (sweep at commit 2d903ed):
  - only 24% of delivered meter last gasps are fire caused (`sweep.meter_density.0.5.frac_deaths_fire` 0.243);
  - 75% of fire signals are censored (`sweep.meter_density.0.5.frac_fire_censored_by_grid` 0.753);
  - tag errors of 0.6 / 2.0, 1.2 / 6.9 and 1.9 / 10.7 min at 73, 13.5 and 6.8 tags per km².
- Launched three background desk-research agents for phase 2:
  - radio ranges and hardware costs;
  - Korean utility trip logging and the 2025 power events;
  - novelty check.
- Next step: phase 2 item 1 (receive side).

## 2026-10-14 23:47 Phase 2 first-pass code (exploratory checks)

- New modules:
  - `lastgasp/deploy.py`: tag layouts along roads and along a forest-edge proxy (contour 100 m from the nearest building).
  - `lastgasp/receive.py`: radio links, greedy gateway placement, star / mesh / mesh-with-store-and-forward reception.
  - `lastgasp/phase2.py`: pipeline.
  - `lastgasp/trips.py`: protection-device trip logs, with energisation and precautionary shutoffs.
  - `lastgasp/economics.py`: LoRa time on air, battery life, cost per km.
  - `demo/`: booth display.
- Line lengths in the test area: 84.5 km of road; 31.9 km of forest-edge proxy.
- "Spacing" is a minimum 2D separation (greedy thinning of 5 m samples). Dense and parallel roads give fewer tags per km of road than 1000/spacing: at 200 m, 126 tags (1.5 per km of road, 12 per km²).
- Exploratory smoke tests, before the radio parameters were final (world 0, 100 m road spacing, 354 tags, 4 fire-exposed gateways). Recorded in `results/exploratory_numbers.json` when written:
  - star: 22% of fire deaths heard;
  - mesh: 84% heard;
  - BLE at 100 m: no tag-to-tag links.
- Finding: tag-side store-and-forward never helps in this model. Fire only removes nodes and links, so a fragment cut off from every gateway cannot reconnect. Store-and-forward was therefore moved to the gateway, buffering during a cellular backhaul outage.
  - Backhaul down from 40 to 100 min (exploratory, world 0): buffered gateways deliver 84% of deaths eventually but only 42% within 5 min; without a buffer, 42% are delivered and the 90th percentile error is 27.6 min (5.2 with no outage).
- Trips (exploratory, worlds 0 and 1):
  - 7 to 11 logged breaker and recloser trips per fire;
  - trips alone: 5.5 to 7.3 min median error;
  - a precautionary shutoff ahead of the fire leaves no fire-caused trips at all.
- Spot diagnosis (exploratory): with perfect reception at 100 m road spacing, the tag nearest a significant spot fire died 1 to 15 min (median about 12 min, 11 spots in 3 worlds) after the spot ignited. Recall is limited by geometry as well as by the detector.
- Demo: `python -m lastgasp_demo --sim --headless` burns 23 of 25 nodes and flags one spot fire at node 16 (605 m jump). `test_demo.py` passes.
- Novelty agent report received (`docs/NOVELTY.md`). The main session re-fetched IBM US9721458B2 and Smith US9619996B1 and confirmed the quoted text: arrival time from the last heartbeat is prior art (2014).
- Next step: set radio and cost parameters from the cited sources, commit, run the phase 2 sweeps from a clean commit.

## 2026-10-15 00:12 Phase 2 parameters pinned; first phase 2 sweep (superseded)

- Radio and cost agent report received. The main session verified two sources:
  - Boonlom et al. 2026 (RSSI = -16.62 - 32.24 log10 d at 923 MHz, gateway at 8 m);
  - LoRa Alliance RP002-1.0.3 section 2.11 (KR920: 14 dBm end-device EIRP on 922.1 to 923.3 MHz, listen-before-talk).
- Radio profiles set from cited fits (`docs/PARAMETERS_PHASE2.md`). Derived median ranges, tag-to-tag / tag-to-gateway:
  - LoRa SF7: 282 m / 1.74 km;
  - pessimistic LoRa: 245 m / 282 m;
  - BLE: 42 m / 42 m.
- Tag death delay set to 10 to 120 s after flame arrival.
- Battery life (`lastgasp/economics.py`, derived), LoRa SF7 every 30 s: 3.3 years with 2% per year self-discharge. At SF9 every 30 s: 1.0 years.
- Booth simulator metrics (`scripts/12_demo_metrics.py`, 20 runs): detection latency 2.6 s median; the simulated spot fire was flagged in 20 of 20 runs.
- First phase 2 sweep, run at commit ef0fa82: 940 runs, 0 errors, 613 s.
  - Superseded, for three reasons:
    - git state was captured at the end of the run, after other scripts had changed, so it read code_dirty true;
    - the receive-side jobs used the config default of 100 m spacing instead of the intended 200 m;
    - the trips figure crashed on scenarios with no fire trips.
  - Exploratory observations from it:
    - mesh relaying heard 93% to 100% of tag deaths, even with fire-exposed gateways;
    - star with exposed gateways heard 37% to 91%;
    - grid-powered gateways heard 60%;
    - a backhaul outage without a gateway buffer left 36%.
- Bug found and fixed: with very sparse tags, the tag-based trip check used an unreliable estimate and discarded real fire trips (classification accuracy 0.11 at 1,600 m spacing). The check now applies only within 500 m of an observed tag death.
  - Check, world 1: tags plus trips 6.5 min median, against 26.8 for tags alone.
- Added scenarios from the utility research: a reactive shutoff (lines cut after the fire reached them) and a logging blackout at 40 min.
- Fixes committed (52e5284). Rerun: `scripts/10_phase2_sweeps.py`, then 11, 12 and 07 (`results/phase2_run.log`).

## 2026-10-15 00:26 Phase 2 clean runs and write-up

- Run at 52e5284 (clean, 940 runs, 209 s), superseded the same hour. It showed a placement bug: in mesh mode, greedy coverage scored every site equal and put all gateways in one corner. That corner happened to burn late, so 95% of deaths were heard by luck.
- Placement fix and finding (exploratory, worlds 0 to 2, 4 gateways, mesh): coverage-greedy, which clusters gateways in the town, heard 56% to 57% in worlds 0 and 2, against 88% to 97% for the spread and perimeter layouts. Added `spread` (the default) and `perimeter` layouts and a placement sweep. Committed as 54f6e9a.
- Final sweep: `scripts/10_phase2_sweeps.py --fire-seeds 5 --obs-seeds 2 --workers 4` at 54f6e9a. Clean code; 1,150 runs; 0 errors; 211 s.
- Figures and economics: `scripts/11_phase2_figures.py`, `scripts/12_demo_metrics.py` and `scripts/07_numbers.py` at 46f7903 (clean), after these figure fixes:
  - fig 10 made 2x2 with a placement panel, legend moved below;
  - fig 11 bar labels overlapped, so changed to horizontal bars with legends below;
  - fig 12 log ticks were cluttered;
  - fig 9 had a clipped gateway marker.
- Key results (mesh, tags every 200 m of road, 12 per km², 10 runs; `results/NUMBERS.json` keys `p2.*`):

  | Setting | Deaths heard | Error (min) |
  |---|---|---|
  | Perfect reception | 100% | 1.5 / 4.9 |
  | 3 spread exposed gateways | 96% | 1.6 / 5.6 |
  | 4 coverage-greedy gateways | 77% | 1.8 / 11.4 |
  | Star, 6 gateways | 96% | |
  | 1 hardened gateway, mesh | 95.5% | |
  | Grid-powered gateways | 59% | |
  | Backhaul down 40 to 100 min, buffered | 96% eventually, 40% within 5 min | |
  | Backhaul down 40 to 100 min, no buffer | 39% | |
  | Pessimistic radio, 4 gateways | 69% | |
  | BLE at 200 m | 1% | |

  - Trip logs, about 9 per fire: trips alone 7.1 / 27.1 min. With tags at 1,600 m: 30.9 / 53.3 min becomes 6.6 / 17.5. With tags at 200 m: no gain. A shutoff ahead of the fire leaves 0 fire-caused entries.
  - Cost (estimate): ,049 per km² up front and 2 per year at 200 m road spacing. Tag bill of materials 6.09. Battery 3.3 years at SF7 with 30 s beacons.
  - Spot recall: 6% at 200 m; 33% at 50 m (36% with perfect reception).
  - Booth simulator: latency 2.6 s median; spot flagged in 20 of 20 runs.
- Wrote `RESULTS_PHASE2.md`, `docs/PARAMETERS_PHASE2.md`, `docs/UTILITY_LOGS.md`, `docs/NOVELTY.md` and `demo/README.md`, and updated `README.md` and `data/SOURCES.md`.
- Decisions:
  - meter last gasp: no-go;
  - independent tag mesh: conditional go for a field pilot;
  - spot detection: no-go for now;
  - trip logs: request as a coarse layer only;
  - booth demo: go;
  - real-world feasibility rated low to moderate (2 of 5).
- Next steps:
  1. 922 MHz walk test in a Gyeongbuk forest.
  2. Tag burn test.
  3. Better spot-detection method.
  4. Use grid bursts and trips as interval constraints.
  5. Flash and test the ESP32 sketch.

## 2026-10-15 10:41 Push, draft PR, booth page, freeze

- The user overrode the no-push rule for last-gasp only.
  - `git push -u origin claude/affectionate-dijkstra-c6zrp7`: 15 commits, accepted as a new remote branch. No rebase or force.
  - Draft PR opened: https://github.com/Sparkxt-0318/wildfireguardian/pull/54, titled "[last-gasp] phase 1 and 2: synthetic feasibility study", base `Main`.
- Freeze: no new experiments from here on.
- Booth figure: `scripts/13_booth_figure.py` at commit f321f08 (clean). It re-renders existing configurations for world 0:
  - left panel: phase 1 default meters (IDW after grid filtering), 81% of fire signals censored, error 5.6 / 26.3 min;
  - right panel: phase 2 tags every 200 m, mesh, 3 spread gateways, 97% heard, error 1.5 / 5.7 min.
  - Metrics: `results/booth_figure_metrics.json`; keys `booth_figure.*` in NUMBERS.json.
  - Inspection fixes: titles overlapped subtitles; panel extents differed; legend box; the suptitle now states that this is a single run.
- `BOOTH.md` written in English and Korean.
  - Every number was checked against NUMBERS.json, using 10-run medians:
    - meters: 75% censored, 24% fire-caused, 5.4 / 26.7 min;
    - 3 spread gateways: 96%, 1.6 / 5.6;
    - 3 coverage gateways: 60%, 1.9 / 18.9;
    - 4 coverage gateways: 77%, 1.8 / 11.4;
    - grid-powered gateways: 59%;
    - cost: ,049 per km² and 2 per year;
    - tag parts: 6.09;
    - battery: 3.3 years;
    - pessimistic radio: 69%.
  - States the IBM US9721458B2 prior art.
- Command: `.venv/bin/python scripts/07_numbers.py` (3,928 numbers).
