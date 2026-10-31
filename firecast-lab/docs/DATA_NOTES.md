# Track A data notes (Phase 0 data checks)

Written 2026-10-31 on the cloud host. It uses repo metadata and code only: no arrival raster, perimeter,
weather raster or model output is on this host, and none was read. Evidence is `path:line`, relative to the
repo root. Abbreviations:

- `CHOI/` = `routing-review/routing_hybrid_road_checker_20261008_v1/candidate/mentor_runtime/wildfire_burned_area_hourly/sources/zenodo_21788344/extracted/code/`,
  the vendored Choi et al. 2026 code. Its hashes match the repo's source audit (map 04, §0).
- "methods" = `forecast/documents/wildfire_methods.tex`.
- "events.json" = `forecast/data/environment/events.json`.

## Decisions in one screen

| Topic | Decision |
|---|---|
| Headline lead | **24 h**. 12 h is secondary and diagnostic only. 1 h is an internal recursion step, never a claimed horizon. |
| Short fires | Six Korean dev fires cannot supply a 24 h window (`too_short_24h` in `SPLITS.json`); four more give only one or two. |
| NIROPS | Approximately independent truth for **timing** inside the final extent; **not** independent for **extent**. |
| Weather | Archived ECMWF IFS values (Open-Meteo archive), repeated from the cutoff hour. They are not forecasts issued at the cutoff. |
| Support | Reconstruction NoData is the complement of the final burn scar, so it is known only in hindsight. Scenario support masks use cutoff-time information only. Scoring negatives outside the scar come from the final perimeter, inside the 3 km headline ring (`METRICS.md`). |

## 1. Label timing uncertainty and the headline lead

**Korean labels.** The only timing-error figures in the repo are the publisher's spatial block-CV MAE values,
copied into `forecast/data/catalog.csv:2-6` (via `forecast/wildfire/bundle.py:196`):

| Event | MAE (h) |
|---|---:|
| KFS_01 Uiseong 2025 | 10.87 |
| KFS_02 Uljin 2022 | 10.44 |
| KFS_11 Miryang 2022 | 12.18 |
| KFS_05 Hongseong 2023 | 7.65 |

- Mean 10.29 h, range 7.65-12.18 h. The other 11 Korean events have no MAE in the repo.
- The MAE is the residual against *withheld VIIRS cell-median detection times*, with up to ten grouped folds
  in Korea (methods:334-353). It is an error against a detection summary, not against physical arrival.
  Detection latency and revisit gaps are not in it, so the error against physical arrival is plausibly larger.
- The Uljin kriging SD spans 4.40-52.96 h. The methods state: "One-hour output spacing is a thresholding
  schedule for a continuous reconstruction, not a one-hour accuracy statement" (methods:411-416).
- The bundle tags record `independently_validated_in_korea: false` and
  `timing_accuracy_is_not_one_hour: true` (`forecast/wildfire/bundle.py:147-148`). They also say the kriging SD
  "is not a calibrated interval" (`bundle.py:204`).
- No independent Korean arrival reference exists in the repo (`forecast/documents/korean_observation_availability_20261012.md:5`).
  VIIRS and Himawari built the labels, so they cannot serve as independent truth (`...:31`). The only candidate
  is MODIS MCD64A1: daily burn date at 500 m (`...:7`).

**US labels.**
- The reconstruction's timing error against NIROPS is not quantified in the repo, because the deposit's results
  tables are not here.
- The NIROPS reference itself is stepwise at survey times (methods:321-323).
- On the six test fires (`forecast/data/sources/nirops_95rj5d379g_v1/catalog/*/provenance.json`, recomputed here):
  - median survey interval 24.04-26.20 h per fire, minimum 4.38 h, maximum 122.92 h;
  - 324 consecutive pairs: 195 last 20-28 h and 273 last at most 48 h.

**Choice: 24 h headline lead.** A simple model shows the trade-off. Suppose a reconstructed arrival is shifted
by `s` hours, with `s` no longer than the lead `L`, and the true arrival falls uniformly inside an `L`-hour
window. Then the cell lands in the wrong window with probability `s / L`. The table uses the four MAE values for
`s` and counts windows with the `SPLITS.json` window rule:

| Lead | Share of new burns misassigned (s = 7.65-12.18 h; at the mean MAE) | Korean fires with at least one window: dev / test | Approximate Korean windows: dev / test |
|---|---|---|---|
| 12 h | 0.64-1.00 (0.86) | 7 of 11 / 4 of 4 | 29 / 31 |
| **24 h** | **0.32-0.51 (0.43)** | **5 of 11 / 4 of 4** | **22 / 27** |
| 48 h | 0.16-0.25 (0.21) | 2 of 11 / 3 of 4 | 14 / 19 |

- At 12 h, timing noise dominates: most Korean new burns would be counted in the wrong window.
- 24 h is the shortest lead at which a typical shift is under half the window.
- 24 h matches the NIROPS cadence: most consecutive surveys are 20-28 h apart, and none exactly 24 h.
- 24 h keeps every Korean test fire.
- 48 h would halve the noise, but it leaves only two Korean dev fires and drops KFS_13.
- Label noise hits every model equally, so paired skill differences stay valid. Absolute reliability is
  attenuated, however: a forecast that is calibrated against true arrival looks miscalibrated against noisy
  labels. Korean reliability diagrams therefore describe agreement with the reconstruction, not calibration
  against physical arrival.
- 12 h is kept as a diagnostic. It is comparable with forecast-v2's Korean 12 h secondary
  (`forecast/documents/preregistration_blind_test.md:136-147`). Claims are never made on 12 h.

**Window construction** (`SPLITS.json` `window_rule`).
- Reconstruction windows:
  - cutoffs every 12 h from `start_utc + 12 h`, with `cutoff + L < end_utc`;
  - at least one reconstructed burned cell at the cutoff. This is checked exactly with the rasters
    (`firecast_lab.data.window_cutoffs`). It is a condition on the cutoff state, never on the outcome.
- NIROPS 24 h windows:
  - consecutive survey pairs lasting 20-28 h, each forecast to its exact survey endpoint;
  - all pairs in (0, 48] h are scored only as a continuity diagnostic with the preregistered forecast-v2 cohort
    (`preregistration_blind_test.md:111`).

## 2. Fires too short for headline windows

The counts below are approximate: they apply the window rule to events.json times. Exact counts need the
rasters (§7).

- **No 24 h window** (`too_short_24h`): KFS_16 Suncheon (1 h), KFS_09 Yanggu (12 h), KFS_14 Uljin May 2022 (15 h),
  KFS_15 Gunwi (21 h), KFS_07 Geumsan (27 h), KFS_17 Hapcheon (32 h). All six are dev fires (fold Y2022_2023),
  and none has c651 rows.
- **Marginal** (one or two windows): KFS_05 Hongseong (1), KFS_12 Yeongdeok (1), KFS_11 Miryang (2), KFS_13
  Buk-gu (2; a Korean test fire on a 9x7 grid).
- **US:** all 29 fires last at least 1,112 h, so none is short.
- Korean dev signal at 24 h is about 22 windows on 5 fires. KFS_02 (14) and KFS_03 (4) dominate it.
- The grids of KFS_12, 13, 14, 15, 16 and 17 are narrower than 9 cells, so no full 9x9 context fits. Fractions
  Skill Score windows of 9 cells or more there are mostly outside the grid; masked fractions handle this
  (`METRICS.md`).

## 3. Did Choi et al. use NIROPS to build the US reconstructions, or only to evaluate them?

**Both.** NIROPS is the evaluation reference, and it is also the scaffolding of the US product. The arrival
*values* come from satellite detections only.

- **Evaluate.**
  - `CHOI/evaluate_sc.py:1-2` reads "External-reference evaluation against NIROPS surveys".
  - The reference arrival is the first survey whose cumulative union encloses the cell centre
    (`CHOI/evaluate_sc.py:23-31`; methods:321-331).
- **Build.**
  1. The US grid is the NIROPS perimeter bounds plus 2 km, at 375 m (`CHOI/evaluate_sc.py:11,15-20`).
  2. The product is computed only where the NIROPS reference arrival is finite, i.e. inside the final NIROPS
     union (`CHOI/produce_rasters.py:29-37`; "NaN outside the final perimeter", `CHOI/evaluate_sc.py:25`).
     Outside, it stores NoData = -1.0 (`CHOI/produce_rasters.py:57`).
  3. The US time origin and detection window are anchored at the first NIROPS survey minus 24 h
     (methods:206-209). The events.json US windows are the "union of NIROPS survey window, t0 and finite
     reconstructed arrival range" (`forecast/wildfire/environment.py:147`).
  4. Detections are kept only strictly inside "the perimeter" (`CHOI/preprocess.py:15-24`). The archived code
    lacks the driver, so this checkout cannot show which perimeter the US runs used. The NIROPS final union is
    likely (§7).
- **Not from NIROPS.** Arrival values are kriged from VIIRS 375 m cell summaries plus geostationary points
  (`CHOI/produce_rasters.py:18-26`; methods:260-277). Survey times are not kriging inputs.

**What this means.**
- **Timing: NIROPS is approximately independent truth.** It is an approximately independent check of *when*
  cells inside the final extent burned. US headline scores use NIROPS survey states.
- **Extent: NIROPS is not independent.** The reconstruction's support, grid and window are all NIROPS-defined:
  - comparing reconstruction extent with NIROPS extent is circular;
  - US reconstruction labels share the final extent with NIROPS;
  - a model trained on US reconstruction labels has seen the NIROPS final extent through its training mask.
- US scores computed from the reconstruction are diagnostics only.
- Korea has no NIROPS. Korean scores rest on the reconstruction alone and are never pooled with US scores.
- **Selection.** NIROPS-flown fires are "of moderate to large size", and "data collection often begins after the
  initial ignition" (`forecast/data/sources/nirops_95rj5d379g_v1/publisher_snapshot.json:5`). The US cohort
  therefore has no early growth.

## 4. Weather inputs: archived analyses, repeated from the cutoff hour

**Source.**
- Weather comes from the Open-Meteo historical archive API (`forecast/wildfire/environment.py:295`).
- `models='ecmwf_ifs'` supplies the weather variables (`environment.py:42-45,237-249`): the nearest O1280 node
  (about 9 km), hourly.
- ERA5 is used only for boundary-layer height (`environment.py:243`).
- Methods: "Archived IFS model values, roughly 9 km and hourly" (methods:445). The reference audit: "no fixed
  cycle is asserted" (`forecast/documents/project_references_audit.json:516`).
- External evidence: map 04 records that Open-Meteo's own docs list the `ecmwf_ifs` archive among "Reanalysis
  models", assembled from runs at 0z/6z/12z/18z. I did not re-verify this: GitHub access to that repository is
  not enabled in this session.

**Reading.** The values are analysis-like, short-range IFS output stitched into an hourly series.
- The lead of each hourly value (a 0 h analysis or a 1-5 h step) is unknown.
- They are **not forecasts issued at the cutoff**.
- No archived issued-at-cutoff forecast exists in the repo.

**How earlier work used them.**
- c651 consumed temperature and 10 m wind at hour t during training.
- Every evaluation repeats the cutoff-hour snapshot over the horizon (`forecast/documents/observed_evaluation.md:115-118`;
  `preregistration_blind_test.md:151-152`; "not ... a forecast weather ensemble",
  `forecast/documents/farsite_evaluation.md:152`).
- Publication latency at the cutoff is not established (methods:2732).

**Track A rules.**
1. **Default: cutoff weather repeated over the horizon.** This is the only cutoff-safe weather in the repo.
   Results call it "persistence weather".
2. **Oracle weather is hindsight.** Archived hourly values over the horizon may appear only as a labelled
   upper-bound diagnostic, never in a headline score.
3. **Issued-at-cutoff forecasts** (backlog L7) need new data (§7).

## 5. The support problem: "unknown" is defined by hindsight

**Facts.**
- **The reconstruction exists only inside the final burn scar.**
  - US: computed only at finite NIROPS reference cells (`CHOI/produce_rasters.py:29-37`), NoData -1.0
    elsewhere (`:57`).
  - Korea: computed only at cell centres properly inside the KFS final perimeter (`CHOI/produce_rasters.py:49`),
    NaN elsewhere.
- **The grids are cut from the same perimeter.**
  - Korea: the perimeter's bounding box snapped to 375 m, with **no margin** (`CHOI/produce_rasters.py:43-45`).
  - US: the perimeter bounds plus 2 km (`CHOI/evaluate_sc.py:11,18-19`).
  - Environment stacks are cut to the same grid: the loader rejects any raster off the event grid
    (`forecast/wildfire/data.py:374-377`).
- **The loader calls NoData unknown** (`burned_area_valid` = finite arrival, `data.py:475-492`). The bundle and
  methods say the same:
  - "Outside source reconstruction mask or study bbox is NoData, not unburned" (`bundle.py:148`);
  - "The raster mask does not establish absence of burning outside it" (`bundle.py:205`);
  - the arrival product supplies no "support beyond final perimeter" (methods:2731);
  - the cutoff burned state "was reconstructed using final extent and event-wide information" and is not
    "operationally available at the cutoff" (methods:98-101).
- **Consequence.** The unknown region is exactly where the fire never burned. The grid edge sits at the bounding
  box of where the fire stopped (Korea) or 2 km beyond it (US). Both are known only after the fire.

**Consequences for scoring** (`METRICS.md`, `firecast_lab.domain`).
1. **Scoring inside the scar only would leak the answer.** Every scored cell would burn eventually, so spreading
   into cells that never burn would go unpenalized. The headline domain therefore adds a 3 km ring outside the
   final perimeter. In the ring, cells count as *outside the mapped extent* (negatives), not as unknown.
2. **Ring negatives mean "outside the mapped extent", never "certified unburned".** They come from the final
   perimeter, not from the reconstruction. This is the policy of `forecast/wildfire/observed_evaluation.py:185`.
   Cells beyond the grid were never mapped; they are excluded, never padded as unburned.
3. **Korean rings are thin.** Korean grids are tight bounding boxes, so the ring exists only in concavities and
   corners inside the box. Korean headline scores contain few far negatives and stay close to within-scar
   scores, which is one more reason never to pool them with US scores.
4. **Holes are indistinguishable from outside.** Without the vector perimeter, NoData holes inside the final
   perimeter look the same as cells outside it, and Korean final perimeters are not in the deposit
   (`korean_observation_availability_20261012.md:5`). The final-perimeter mask is therefore the finite-arrival
   mask, with this limitation stated.

**Consequences for generated scenario sets (honest support masks).**
1. **Support uses cutoff-time information only.** A member's `supported` mask (hazard_contract) must be
   computable from what is known at the cutoff: the grid, completeness of the environment inputs, the cutoff
   state and the horizon. It must never be derived from the reconstruction NoData mask.
2. **What goes wrong otherwise.** Suppose c651 runs with `missing_burned_area="unknown"`. Every cell outside the
   final scar then stays unknown. Its coverage envelope shrinks every hour: `following = masks[-1] &
   (observed_burns | rate_valid)` (`forecast/wildfire/rollout.py:168`), about 4 cells per hour from every NoData
   cell under the 9x9 rule. Member support becomes an eroded copy of the *eventual* burn scar. Then:
   - (a) the scenario set leaks the future, because "supported" marks where the fire will go;
   - (b) every route outside the eventual scar becomes unsupported, hence unresolved, so clearance collapses for
     a reason unrelated to the model;
   - (c) false-safe and clearance comparisons between models become meaningless.
3. **The honest cutoff state.**
   - **Definition.** A cell is burned if its reconstructed arrival is at or before the cutoff, and not burned
     everywhere else on the grid.
   - **Why it is a fact.** Outside the final scar this follows from the final perimeter: a cell that never burned
     was not burning at the cutoff. It says nothing about where the fire goes next.
   - **Precedent.** This is what `missing_burned_area="unburned"` does, and the code records the count as
     `assumed_unburned_cells` (`forecast/wildfire/api.py:397-419`).
   - **The generator must never receive the validity mask itself.**
   - **Remaining leak.** The reconstructed cutoff state still uses event-wide detections (methods:98-101). This
     is a smaller hindsight leak that we accept and state. Real-time initial states are backlog L6.
   - **Needs approval.** This reading of ground rule 4 goes to Siyeong for confirmation (§7).
4. **Genuine unknowns stay unknown.** Missing environment inputs give `supported=False`, hence unresolved. Cells
   beyond the grid lie outside the set: hazard_contract marks any query touching the outside as unsupported.
5. **The grid edge is a hindsight wall.**
   - With `boundary="zero"`, nothing can burn beyond the final perimeter's bounding box (Korea) or 2 km past it
     (US). This truncates member spread in exactly the directions where the fire stopped.
   - Until the environment stacks are re-cut with a margin (§7), record per window the share of members that
     reach the outermost ring of grid cells ("edge contact").
   - Routes that leave the grid count as unresolved.

## 6. Other caveats noticed

- **Static vegetation is the 2019 epoch** (Copernicus land cover 2019, GEDI-Landsat canopy 2019;
  `forecast/wildfire/environment.py:430-441`; methods:448-449). Later burn scars are not reflected in fuels.
  Example: Dixie 2021 overlaps the rectangle of PNFNorthComplex 2020.
- **Overlapping rectangles across splits.** Two dev/test pairs (KFS_12 and KFS_01; Moose and RedRock) and four
  pairs across dev folds share landscape inputs. They are listed in `SPLITS.json` `spatial_overlaps`. Labels
  are separate fires.
- **Negative US arrival values are valid** (methods:212). Validity comes from the NoData tag (-1.0 in the US
  source rasters), never from the sign. `firecast_lab.data` reads the tag.

## 7. Questions that need the Mac data or blocked hosts

| # | Question | Needs | Decides |
|---|---|---|---|
| 1 | Exact 24 h and 12 h window counts per fire (at least one burned cell at the cutoff) | Mac data root: `regions/*/arrival_time_hours.tif`. Run `python -m firecast_lab.data --data-root PATH` | `too_short_24h`, the marginal fires |
| 2 | Headline-domain size per fire, and how much of the 3 km ring the grid clips | Mac data root (same command) | how far the headline and full-rectangle scores can differ |
| 3 | US reconstruction timing error against NIROPS (per-event Sorensen, block-CV MAE), and the MAE of the 11 Korean events missing from `catalog.csv` | Choi deposit `results/*.csv` (Zenodo blocked; or the Mac copy) | US label noise; whether 24 h holds for every Korean fire |
| 4 | Which perimeter filtered the US detections (`CHOI/preprocess.py:15-24`) | Choi paper or deposit README (Zenodo blocked; paper not in repo) | whether US reconstruction timing is fully independent of NIROPS |
| 5 | Kriging SD per fire | Mac data root: `kriging_std_hours.tif` | per-fire timing noise; any label weighting |
| 6 | NIROPS survey perimeters for all 29 US fires | Mac: `NIROPS_2020_2024_R1_R6.zip`, 1.39 GB (Mendeley blocked) | US timing truth for dev and test; final-perimeter rasters to find NoData holes |
| 7 | Is there a NIROPS release with 2025 surveys, and which 2025 fires qualify? | Mendeley (blocked), NIFC FTP (unreachable) | `fresh_holdout` US 2025 membership |
| 8 | A 2026 Korean reconstruction | successor of the Choi deposit (Zenodo blocked) | `fresh_holdout` KR 2026 membership |
| 9 | The lead of each archived IFS hourly value; archived issued-at-cutoff forecasts | Open-Meteo or ECMWF archives (not reachable) | analysis versus forecast inputs; backlog L7 |
| 10 | MODIS MCD64A1 daily burn dates as an independent Korean check | NASA LAADS (Earthdata login; not reachable) | any independent Korean timing truth |
| 11 | c651 inference | torch (CPU index blocked; the CUDA wheel is over 1 GB and needs approval) or the Mac | the c651 baseline |
| 12 | Environment stacks with a margin beyond the event grids | re-acquisition (Open-Meteo, Copernicus and others; blocked here) or the Mac pipeline | removing the hindsight grid-edge wall |

Questions for Siyeong (decisions, not data):
- (a) Confirm the cutoff-state rule in §5: outside the final scar, the generator input is "not burned at the
  cutoff", with the count recorded. The alternative, "unknown", leaks the final scar.
- (b) Confirm the 3 km headline buffer (`METRICS.md`).
- (c) Should US 2023 NIROPS incidents become an immediately usable fresh holdout? They need new environment
  stacks (`SPLITS.json` `fresh_holdout.not_included`).
