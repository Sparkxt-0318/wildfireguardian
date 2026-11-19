# RESULTS: published heat methods on the Gyeongbuk 2025 replay and the finals fires

Protocol: PROTOCOL.md (frozen at `aac1b282`, amendments A1-A5). Method: METHOD.md. Every number is a model output;
none is a field measurement of heat at a road.

## In short

* **The safe distance is smaller than one 375 m cell almost everywhere.** At 7 kW/m2 it is below 375 m in every
  burned cell of all four reconstructed fires (10,955 + 1,937 + 153 + 80 cells, every fuel level; largest 320 m) and in
  every road cell the replay front reaches (7,644 cell-hours; median 25 m, 90th percentile 104 m, max 255 m). At
  2.5 kW/m2 it exceeds 375 m only in crown-fire cells (9 % of Uiseong cells; 0.2 % of replay front cells).
* So the heat term mostly changes **when** a road closes, by minutes: the lead d*/R is a median 2.4 min (90 %: 5.6
  min) at 4.7 kW/m2 on the replay. Its lateral reach rarely passes into the next cell.
* **On leave-by times it changes about as much as the old law, for a different reason.** Replay, 4.7 kW/m2: 337 of
  1,134 place-hours with a leave-now window move (median 3.7 min earlier, max 28 min) and 12 lose the window; the old
  law moves 350 (7 lost). The new and the old law disagree on 344: the new one is later in 174, earlier (or loses the
  window) in 170. Most of the shift
  in both comes from the 375 m cell rule (the front is placed at a neighbouring cell's near edge), not from radiation
  physics.
* **The finals packets (1 h) change only through an artefact.** 22 of 425 place-inputs lose their leave-now window under the
  new method (old law: 0). All 22 come from cells inside the known fire area at issue, whose flat arrival field gives
  the capped 150 m/min spread rate and hence a crown flame. With those cells silent (exploratory) 1 time moves and
  none is lost.
* **Uncertainty**: over flame temperature 1090-1400 K, fuel low-high and four view factors the safe distance of a
  crown-fire cell spans 60-301 m (baseline 133 m), a surface-fire cell 7-29 m (12 m). Flame temperature matters most.
* **Checks**: Butler and Cohen's 4 H rule reproduced at 3.5 H (their 20 m front; Zárate et al. 3.8 H; Rossi et al.'s
  8 L for long fronts at 8.3 L); never below FDS (19-115x above its 1 m-cell radiometers; 1.2-1.7x a resolved propane
  burner); ICFME crown flames within a factor 1.7. The gate passed and the method is the road layer's `--heat`
  option, **left off by default** (section "Road layer").

## The table

Leave-by changes against no heat, per heat rule and threshold q* (kW/m2). Panel A: Gyeongbuk replay, 13 issue
hours 12:00-24:00 KST x 2 regions, 8 h horizon; 27,759 road cell-hours, of which 20,115 are inside the known fire at
issue and 7,644 are reached later; 1,134 place-hours with a leave-now window. Panel B: the 15 finals packets
(Uiseong-Andong, Yeongdeok 2025; Uljin, Miryang 2022; Hongseong 2023), 1 h horizon; 3,422 road cell-hours, 3,402 at
issue, 20 reached later; 425 place-inputs with a leave-now window. "Road cells closed earlier": reached road
cell-hours whose earliest road piece closes before the contact rule. "Unreached cells": road cells the fire never
reaches inside the horizon in which some piece is closed by heat. Shift: minutes, over the changed leave-by times
that keep a window. Last column: leave-by times that differ from the old law at the same threshold (how many of them
are later than the old law's).

| panel | heat rule, q* | road cells closed earlier | unreached cells partly closed | leave-by times changed | windows lost | shift median / max (min) | vs old law |
|---|---|---:|---:|---:|---:|---|---|
| A replay | old law, 7 | 7,644 | 156 | 349 | 5 | 2.1 / 20.3 | – |
| A replay | old law, 4.7 | 7,644 | 166 | 350 | 7 | 3.1 / 27.9 | – |
| A replay | old law, 2.5 | 7,644 | 173 | 352 | 19 | 5.9 / 72.5 | – |
| A replay | **new, 7** | 7,471 | 145 | 330 | 12 | 2.7 / 26.8 | 347 (165 later) |
| A replay | **new, 4.7** | 7,512 | 155 | 337 | 12 | 3.7 / 28.1 | 344 (174 later) |
| A replay | **new, 2.5** | 7,532 | 175 | 342 | 14 | 6.5 / 42.3 | 334 (163 later) |
| A replay | new 4.7, fuel low | 6,644 | 133 | 268 | 12 | 2.4 / 26.2 | 342 (271 later) |
| A replay | new 4.7, fuel high | 7,640 | 180 | 350 | 14 | 5.2 / 42.6 | 345 (144 later) |
| A replay | new 4.7, 1090 K | 7,488 | 145 | 333 | 12 | 2.7 / 26.9 | 343 (232 later) |
| A replay | new 4.7, 1400 K | 7,532 | 175 | 342 | 14 | 6.5 / 42.2 | 347 (110 later) |
| A replay | new 4.7, worst angle | 7,644 | 179 | 352 | 12 | 4.9 / 41.3 | 345 (153 later) |
| A replay | new 4.7, vertical plane | 7,644 | 179 | 352 | 12 | 4.8 / 41.2 | 345 (155 later) |
| A replay | new 4.7, Mudan cylinder | 7,644 | 175 | 352 | 12 | 3.9 / 28.7 | 345 (162 later) |
| A replay | new 4.7, no transmissivity | 7,513 | 156 | 337 | 13 | 4.7 / 29.1 | 345 (153 later) |
| A replay | new 4.7, known-fire cells silent (EXPLORATORY, not in protocol) | 7,512 | 155 | 337 | 8 | 3.7 / 28.1 | – |
| B packets | old law, 7 | 20 | 326 | 2 | 0 | 2.2 / 2.2 | – |
| B packets | old law, 4.7 | 20 | 331 | 2 | 0 | 3.2 / 3.2 | – |
| B packets | old law, 2.5 | 20 | 347 | 3 | 1 | 6.0 / 6.0 | – |
| B packets | **new, 7** | 20 | 414 | 24 | 22 | 1.4 / 2.2 | 24 (1 later) |
| B packets | **new, 4.7** | 20 | 439 | 24 | 22 | 1.9 / 3.2 | 24 (1 later) |
| B packets | **new, 2.5** | 20 | 626 | 28 | 25 | 5.7 / 22.2 | 27 (2 later) |
| B packets | new 4.7, fuel low | 20 | 420 | 22 | 20 | 1.0 / 1.6 | 22 (2 later) |
| B packets | new 4.7, fuel high | 20 | 497 | 27 | 24 | 3.8 / 22.1 | 27 (1 later) |
| B packets | new 4.7, 1090 K | 20 | 415 | 24 | 22 | 1.4 / 2.3 | 24 (2 later) |
| B packets | new 4.7, 1400 K | 20 | 624 | 28 | 25 | 5.6 / 22.2 | 28 (1 later) |
| B packets | new 4.7, worst angle | 20 | 441 | 25 | 22 | 3.3 / 22.0 | 25 (1 later) |
| B packets | new 4.7, vertical plane | 20 | 438 | 24 | 22 | 1.9 / 3.2 | 24 (1 later) |
| B packets | new 4.7, Mudan cylinder | 20 | 417 | 24 | 22 | 1.8 / 3.0 | 24 (2 later) |
| B packets | new 4.7, no transmissivity | 20 | 519 | 27 | 24 | 3.7 / 22.1 | 27 (1 later) |
| B packets | new 4.7, known-fire cells silent (EXPLORATORY, not in protocol) | 12 | 22 | 1 | 0 | 3.2 / 3.2 | – |

## Checks (step 2): gate for the road layer = C1, C2 and C3 pass

* **C1, Butler and Cohen (1998), amended A1** (20 m front, 1200 K, emissivity 1, vertical flame, no attenuation).
  Linear fit of d(7 kW/m2) on flame height for H = 1-10 m: **3.54 H** (they: 4 H, -11 %). Zárate et al. (2008), same
  geometry: 3.8 H at 7 and 4.8 H at 4.7 kW/m2; here 3.54 H (-7 %) and 4.44 H (-8 %). Long front (W/L > 50): **8.34 L**
  (Rossi et al. 2011: 8 L, +4 %). **Pass.** With a fixed 20 m width d/H falls with H (6.2 at 2 m, 4.3 at 5 m, 3.1 at
  10 m, 2.1 at 20 m), so the "4 x flame height" rule holds for fronts a few times wider than the flame is tall; a long
  front needs about 8 x flame length. Implementation: McGuire's closed form equals the numerical integral at zero tilt
  (< 1e-4), Mudan's cylinder equals direct integration (< 1 %), flux decreasing in d; 11 tests pass.
* **C2, FDS (model-to-model).** C064 grass fire (I = 4.47 MW/m, 60 m head): the solid flame is **19-115x above** FDS's
  radiometers at 1-60 m and 1.2-3.6x above the unattenuated voxel sum of the same run (1.2-1.9x beyond 5 m); the old
  closed form was 6-109x above FDS. **Pass** (never on the unsafe side). Local FDS: the plane-layer verification
  reads 2.918 vs 2.897 kW/m2 analytic (+0.7 %); a 240 kW propane strip, calm, gives 5.18 / 1.70 / 0.69 kW/m2 at
  0.6 / 1.6 / 2.6 m against 8.9-9.7 / 2.0-2.8 / 0.8-1.2 for the solid flame, **1.2-1.7x** (FDS not grid-converged).
  So the 20-100x gap appears in FDS's coarse vegetation run, not on a resolved flame.
* **C3, flame length vs observations.** ICFME crown fires (Stocks et al. 2004; 11 plots, 13,400-93,500 kW/m, flame
  fronts 25-40 m high): Thomas from the reported intensities gives 15-55 m, worst factor **1.67**; the full chain
  from the reported spread rates with this study's pine fuel (middle) gives 15-41 m, worst factor **1.65** (low fuel:
  3.1; high: 1.31). **Pass.** Surface fires, range only (A4): grass at RxCADRE spread rates 0.8-3.6 m vs observed
  heights 0.3-1.8 m; pine litter 0.6-2.3 m vs about 0.5 m (Nelson and Adkins 1986). Both high, the safe side.
* **C4, sensitivity** (Uiseong median conditions; d* at 7 kW/m2, baseline then range): pine crown fire at 30 m/min
  (L 23 m) 133 m, 60-301 m over all settings; by flame temperature 98-204, fuel 101-160, view factor 104-134,
  transmissivity 133-167. Pine surface fire at 3 m/min (L 1.6 m): 12 m, 7-29 m. Grass at 14 m/min (L 1.9 m): 14 m,
  0-40 m. On the panels the sensitivity rows of the table move the replay count between 268 and 352 of 1,134.

## The four reconstructed fires (per-cell tables in `data/fires/`)

Every burned 375 m cell of the KFS arrival reconstructions at its arrival hour, middle fuel:

* **Uiseong 2025** (10,955 cells; R median 13 m/min, 10 % at the 150 m/min cap; 34 % crown): flame length median
  3.3 m, 90 % 40 m, max 68 m; d*(7) median 24 m, 90 % 197 m, max 277 m (fuel high 320 m); lead d*(7)/R median 2.4 min.
* **Uljin 2022** (1,937 cells; R median 1.7 m/min; 20 % crown): L median 1.2 m, max 42 m; d*(7) median 9 m, max 281 m.
* **Hongseong 2023** (153 cells; 18 % crown): L median 1.1 m, max 35 m; d*(7) median 8 m, max 199 m.
* **Miryang 2022** (80 cells; 5 % crown): L median 0.8 m, max 6.7 m; d*(7) median 11 m, max 63 m.
* d*(7) < 375 m in **100 %** of cells in all four fires at every fuel level; d*(2.5) < 375 m in 91 % (Uiseong), 99 %,
  100 %, 100 %.
* **FRP cross-check** (Wooster et al. 2005, detections within 1 h of arrival): the model's intensity is above the
  FRP-implied one in most pixels; median ratio 341 (Uiseong, 1,159 detections), 7.4 (Uljin, 830), 6.1 (Hongseong,
  88), 4.2 (Miryang, 19); rank correlation -0.30 to 0.33. FRP-implied intensities are 30-285 kW/m at the median:
  a 375-750 m pixel averages flaming and smouldering parts, a front rarely fills it at the overpass, and smoke and
  saturation hide flames (Johnston et al. 2017 found FRP per front length the weakest route to Byram's intensity).
  The Uiseong ratio also reflects spread rates from a kriged arrival field that includes spotting. The check neither
  corroborates the model's intensities nor shows them too low.

## Panels: what else the runs show

* Replay front cells (7,644 cell-hours reached after issue): R 9 / 25 / 27 m/min (10 / 50 / 90 %; the MEASURED reach
  curve's speed), 46 % crown; flame length 3.6 / 21 / 60 m (50 / 90 % / max), height 3.4 / 15 / 55 m; d* at 7 / 4.7 /
  2.5 kW/m2: median 25 / 36 / 63 m, 90 % 104 / 139 / 212 m, max 255 / 319 / 445 m; share below 375 m 100 / 100 /
  99.8 %. Lead at 4.7: median 2.4 min, 90 % 5.6, max 8.5.
* Flux at the road when the earlier-burning neighbour cell is reached (front at its nearest edge; 7,644 cells with
  such a neighbour): >= 7 kW/m2 for 6,285, 4.7-7 for 157, 2.5-4.7 for 195, below 2.5 for 1,007. Median 63 kW/m2. That
  is the 375 m rule at work: a road within a few metres of a cell edge is inside the flame zone when the neighbour
  is "reached", whatever the physics.
* Why the old and the new law move about the same number of leave-by times: in both, a road piece near the edge of a
  burning neighbour closes when that neighbour is first reached, up to an hour before its own cell (median 15 min for
  either law). That shift is set by the cell size and the reach curve, not by the radiation model. The radiation
  model decides only the in-cell lead (new: d*/R, median 2.4 min at 4.7; old: T* = 3.1 min at 4.7, independent of R)
  and how far the halo reaches (new: tens to hundreds of metres; old: 11-33 m).
* Panel B, the 22 lost windows: every one is caused by cells inside the known fire area at issue (arrival 0, a flat
  field, so R = the 150 m/min cap and a crown flame of ~50 m). Their d* of ~290 m closes nearby road pieces at second 0.
  The protocol fixed this conservative reading in advance; the exploratory row shows it is the whole effect. Whether a
  long-burning area still radiates like an advancing crown front is doubtful, and the old law had no such term.

## Road layer (step 4)

The gate passed, so the method is in `product/wfg-roadlayer` as the heat option (`--heat`, `--heat-threshold
7|4.7|2.5`; settings `[heat]`), vendored byte for byte from `kcf_radiation/` (tested). Road pieces close by the rule of
PROTOCOL section 6; the certificates carry the per-piece and per-node closure seconds, and the standalone verifier
re-derives the masks from them (all certificates of a heat run verify). With heat off every output is byte-identical
to before (golden tests; only the verifier script's own hash changed). The old law was never in the road layer, so
"replacing" it means the heat option is this method and nothing else.

**Default: off.** The protocol says off unless it changes answers. It does change answers (337 of 1,134 replay
leave-by times at 4.7 kW/m2), but the changes are driven by the 375 m cell rule (the old law, with a halo of 11-33 m,
changes as many) and, in the packets, entirely by the capped spread rate of the known fire area. Switching it on by
default would ship those two artefacts as if they were radiation physics. It stays available for a
heat-margin view. Two fixes would make a default-on worth testing: an arrival grid finer than 375 m, and a rule for
the burned-out interior (for example, no radiation from cells that burned more than the flaming residence time before
issue). Neither is a published method; both would be new protocol work.

## Limits

* **Fuel data quality.** Copernicus 2019 land cover stands in for a fuel map; Korean crown-fuel values come from a
  few Gyeongbuk stands; mixed forest is an assumption. Fuel load moves a crown cell's d* by about 1.6x.
* **375 m resolution.** Arrival and spread rate are cell values, and the position of the front inside a cell is
  unknown. The safe distance is below the cell size almost everywhere, so the cell rule, not the radiation model,
  sets most of the timing change.
* **Radiation only.** No convection (Zárate et al. add 20 % to distances for it), no flame contact beyond the cell
  rule, no embers or spot fires, no smoke.
* **Spread rate** read from interpolated (KFS) or screening (replay) arrival fields, capped at 150 m/min; flat fields
  inside the known fire area get the cap.
* **Weather**: one ECMWF wind per hour at ~9 km, no gusts; slope not used.
* **Thresholds** are for people outside a vehicle (firefighters in clothing, emergency workers, skin); none is
  validated for vehicle occupants.
* **Data**: the folder named in the brief could not be reached; inputs come from an earlier release of the same
  workspace (DATA.md).
