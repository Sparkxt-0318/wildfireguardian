# Last Gasp: results of the first feasibility pass

All results in this document come from a synthetic simulation. They are not measurements of any real fire, grid or network, and must not be quoted as real-world performance. Every number below is in `results/NUMBERS.json` with the script, config and git commit that produced it. Sweep results come from commit 2d903ed with clean code: 5 synthetic fire worlds times 2 observation seeds, so 10 runs per setting.

## Short answer

- **Smart meter last gasps alone: no-go in this form.**
  - Meters are powered by the grid they report on. In the simulation, about 75% of the meters in buildings the fire reached had already lost power to an upstream fault before the fire arrived. The fire signal is censored.
  - Arrival-time error at burned buildings stays at about 5 min median and 21 to 27 min at the 90th percentile, whatever the meter density (7 to 144 per km²) or delivery probability (0.2 to 1.0).
  - The March 2025 fires had exactly this kind of upstream outage: transmission trips and a precautionary shutoff blacked out about 95% of Yeongdeok county.
- **Grid-independent battery tags: go, for the demo and further study.**
  - Tags on 50% of buildings (73 per km²) give 0.6 min median and 2.0 min 90th-percentile error.
  - Even 13.5 tags per km² give 1.2 and 6.9 min.
- **Fire versus grid classification works.** Using feeder topology raises balanced accuracy to 0.89, against 0.51 for a time-only rule.
- **Spot fire detection does not work yet.** Recall of significant spot fires is 3% with meters and 17% with dense tags. Precision is 18% and 33%.

## Setup in one paragraph

**Area and network.**
- The test area is 10.4 km² around Yeongdeok-eup, using the real OpenStreetMap road network and the real Yeongdeok Substation location.
- OSM maps only 59 of the buildings there, so 1,441 synthetic buildings were placed along the real roads, for 1,500 nodes.
- A synthetic radial 22.9 kV-style network runs along the roads: 6 feeders, 6 reclosers, 286 lateral fuses, 1,126 transformer cutouts and 3,710 poles at 50 m spacing.

**Fire.** Ground truth is a 10 m anisotropic eikonal (minimum travel time) model:
- wind of 8 m/s from the west;
- head spread rate of 48 m/min (the 10% wind rule);
- length-to-breadth ratio of 3.7;
- lognormal fuel variability;
- a lognormal spotting kernel that produces 14 to 20 spot ignitions per world. Of those, 2 to 5 lead the front by 10 min or more ("significant"). The fire reaches 97% to 99% of buildings within 150 min.

**Faults when the fire arrives.**
- A 50 m span faults with probability 0.05.
- A transformer fails with probability 0.3.
- Unrelated fuse and breaker operations also occur.

**Observation.** Death time = fire arrival + lognormal ignition delay (median 5 min) + reporting delay. Last-gasp delivery is 0.8, clock jitter is 0.25 min, and a device whose power is already gone cannot report the fire.

Full parameter list with reasons: `docs/PARAMETERS.md`. Figures: `figures/`.

## (a) Arrival-time map

Error is the absolute difference between reconstructed and true arrival time at every building the fire reached, including buildings without a device. Medians over 10 runs:

| Setting (nodes per km²) | IDW, all deaths | IDW after grid filtering | Huygens fit after grid filtering | Floor: IDW of true times |
|---|---|---|---|---|
| Meters 50% (73), default | 6.5 / 24.7 | 5.4 / 26.7 | 5.2 / 21.5 | 0.0 / 1.7 |
| Meters 50%, no grid faults | 2.2 / 8.0 | 2.4 / 8.5 | 2.9 / 10.0 | 0.0 / 1.7 |
| Routers 50% (73) | 6.8 / 25.2 | 6.7 / 33.6 | 6.6 / 29.6 | 0.0 / 1.7 |
| Meters 50% plus tags 10% (87) | 4.8 / 22.4 | 1.8 / 8.5 | 2.4 / 10.0 | 0.0 / 1.4 |
| Tags 50% (73) | 0.6 / 1.9 | 0.6 / 2.0 | 0.8 / 3.2 | 0.0 / 1.7 |

Values are median / 90th percentile error in minutes.

What the sweeps show (Figures 4 and 5):

- **Node density barely matters for meters.**
  - From 6.8 to 144 meters per km², the Huygens median error stays between 5.1 and 6.2 min and the 90th percentile between 21.5 and 25.7 min.
  - The density floor (IDW of the true times) is 1.7 / 9.6 min even at 6.8 per km².
  - Information is lost to grid censoring, not to sparse sampling.
- **Delivery probability barely matters either.** From 0.2 to 1.0, the Huygens median goes from 6.4 to 4.6 min, with a 90th percentile of 21.5 to 25.7 min.
- **Grid fault rate is the dominant control.**
  - With no fire-caused faults, error drops to 2.4 / 8.5 min (IDW after filtering).
  - At a span fault probability of 0.0125 (a quarter of the default), 44% of fire signals are already lost, and the 90th percentile rises to 15.6 to 19.5 min.
  - At 0.2, 91% are lost and the Huygens error is 12.5 / 39.6 min.
- **A substation-level trip is fatal.** If every feeder trips at 40 min, the Huygens error is 7.8 / 27.1 min. At 20 min it is 27.4 / 49.9 min, with 98% of fire signals lost. This is the closest synthetic analogue of the real 2025 Yeongdeok blackout.
- **Timing noise sets the floor once censoring is controlled.**
  - The median error follows the spread of the ignition delay: 2.4 min at a 0.5 min median delay, and 21.0 min at a 20 min median delay.
  - The delay is assumed calibrated, so this is the effect of spread, not bias.
- **Battery tags follow the density floor closely.** IDW error by tag density:

  | Tags per km² | Median / 90th percentile error (min) |
  |---|---|
  | 1.2 | 4.9 / 20.3 |
  | 6.8 | 1.9 / 10.7 |
  | 13.5 | 1.2 / 6.9 |
  | 29 | 0.8 / 4.4 |
  | 73 | 0.6 / 2.0 |

- **IDW versus the physics-based fit.** The Huygens fit is a k-th order min-plus eikonal field with a fitted elliptical spread model and a residual correction.
  - Where data are censored or sparse and it must extrapolate, it beats IDW at the 90th percentile: 21.5 against 26.7 min for meters at default settings.
  - Where data are dense and clean (tags), plain IDW is better: 0.6 / 2.0 against 0.8 / 3.2 min.
  - The fitted spread parameters are far from the truth (for example, a nearly isotropic fit with the wrong direction in world 0), so the physics method is not yet identifying the fire's behaviour. It is acting as a robust extrapolator.
  - It also cannot extrapolate upwind of the earliest observed death (Figure 2).
- **Mixing helps a lot.** Adding battery tags on 10% of buildings to the meter network cuts the error from 5.4 / 26.7 to 1.8 / 8.5 min (IDW after filtering). This only works with grid filtering; naive IDW stays at 4.8 / 22.4 min.

## (b) Spot fires

Detection rule: a death much earlier than any earlier death could explain, with at least one surviving node between it and the would-be explaining node, and at least one later death that is also early. Pooled over 10 runs, with 36 significant spot fires in total:

| Setting | Observable spots | Detections | Precision | Recall of significant spots | Median location error |
|---|---|---|---|---|---|
| Meters 50%, default | 9 | 39 | 0.18 | 0.03 | 139 m |
| Meters 50%, no grid faults | 28 | 106 | 0.27 | 0.31 | 152 m |
| Tags 50% | 27 | 39 | 0.33 | 0.17 | 47 m |

"Observable" means at least one delivered fire death inside the spot's own burn region.

Conclusions:
- With meters, most spot fires are invisible because the meters there are already dark.
- With tags, the information is there (27 of 36 observable) but the first-pass detector finds only about a fifth of the significant spots. False alarms come from unrelated grid outages that slip past the classifier, and from fingers of the main front.
- When a spot is matched, jump-distance error is about 76 m with tags.
- This is the weakest part of the pipeline and the clearest target for the next iteration.

## (c) Fire versus grid

The topology classifier looks for bursts of last gasps below one protective device, inside a 1 min window, that are large relative to the meters still powered below it.

| Setting | Topology classifier | Time-only rule |
|---|---|---|
| Meters 50%, default | 0.89 | 0.51 |
| Meter density from 6.8 to 144 per km² | 0.80 to 0.89 | 0.69 falling to 0.51 |
| Ignition delay median of 20 min | 0.60 | not reported |
| Routers 50% | 0.69 | not reported |

Values are balanced accuracy on delivered messages.

- With a 20 min median ignition delay, fire deaths spread out and grid bursts dominate.
- Routers do worse because ISP polling smears simultaneous deaths over 5 min.

Caveat: most "grid" deaths here are fire-caused upstream faults. They are not useless. A burst under a fuse tells you the fire reached that protected section at that time, but this pass discards them instead of using them as coarse constraints.

## What works, what breaks

Works (synthetic):
- Rebuilding the arrival-time map at building resolution from grid-independent nodes. With 13.5 to 73 tags per km², median error is 0.6 to 1.2 min and the 90th percentile is 2 to 7 min.
- Separating grid bursts from fire deaths with feeder topology.
- A live alive-or-dead front estimate for the demo:
  - IoU 0.74 against the true burned area while the front crosses a 1 km² village with 25 tags.
  - Median detection latency of 2.1 min after the fire arrives (3 min heartbeat timeout).

Breaks:
- Grid-powered nodes (meters, routers) under realistic fault rates. The fire cuts the lines ahead of itself, so the network goes dark before the front arrives. In world 0, no last gasps arrive after about 70 min although the fire burns on (Figure 3).
- Any substation-level or precautionary shutoff.
- Spot fire detection (low recall and precision).
- Large ignition delays (more than about 10 min median).
- Areas upwind of the first observed death, for the physics-based method.

## Conditions required for this to be useful

1. Nodes whose death is caused by local heat, not by loss of grid power. Examples: battery tags, or meters and ONUs with a battery-backed last gasp that keep reporting after the grid fails. A grid-powered last gasp is useful only before the first upstream fault.
2. A reporting path that survives the outage. The 2025 telecom outages were mostly caused by power loss.
3. Time resolution of a minute or better, and ignition delays well under 10 min. Timing noise sets the error once censoring is removed.
4. About 10 or more grid-independent nodes per km² for errors of about 1 to 2 min median and under 10 min at the 90th percentile.
5. Feeder topology, at least which meters share a fuse or transformer, to separate grid bursts from fire deaths.

## Go or no-go

- **Meter last gasps (KEPCO AMI) as the main fire-front sensor: no-go.**
  - Three reasons:
    1. Synthetic censoring is severe even at moderate fault rates.
    2. The 2025 outages in Yeongdeok were dominated by upstream trips and a precautionary shutoff.
    3. KEPCO's AMI is mostly PLC through pole DCUs. No public evidence was found that it logs timestamped meter-level last gasps; its documented monitoring flags DCU loss after 30 to 180 min (`docs/DESK_RESEARCH.md`).
  - Revisit only if real logs show timestamped meter power-fail events before feeder trips.
- **Grid-independent node network (tags, or battery-backed devices): conditional go.**
  - Continue to the tabletop demo and a second synthetic iteration focused on spot detection and on using grid bursts as constraints.
  - Then a small field trial.
- **Utility and telecom outage logs as a coarse complement: worth a data request.** Feeder fault and switch times (ADMS, DAS) and base-station power-fail alarms could bound when the fire reached sections of a feeder or cell, even at coarse resolution.

## Most useful real data to request next

1. **KEPCO, via its Data Safe Zone or a pseudonymised research request (PIPA Art. 28-2).** For the Yeongdeok and Cheongsong feeders on 2025-03-25 and 26:
   - meter power-fail and restore event logs with meter timestamps, if they exist;
   - DCU network management alarms;
   - ADMS/DAS fault, recloser and switch event logs with timestamps;
   - feeder topology down to transformer level.
   This answers the first-order question of whether last gasps exist at all and how they compare with feeder trips.
2. **Internet providers (KT, SK Broadband, LG U+).** OLT port or splitter-level ONU offline and dying-gasp times for the same area and night, aggregated so no household is identifiable, plus whether ONUs had battery backup.
3. **Mobile carriers, via MSIT.** Base station alarm logs with cause (power fail, battery exhausted, link down) and timestamps for the five counties.
4. **Ground truth for validation.**
   - The building-level damage survey for Yeongdeok and Cheongsong.
   - Fire progression products already used by the Korea Forest Service (VIIRS, Himawari, drone and aircraft infrared).

## Mapping to the tabletop demo

The demo plan has about 25 ESP32 boards broadcasting heartbeats on a village map, and the software rebuilds the front live when a node is "burned".

- **Closest synthetic analogue:** 25 battery tags in 1 km² (`scripts/06_demo_sim.py`, Figure 8). Measured with the default 30 s heartbeat and a 3-missed-heartbeat timeout:
  - live burned-area IoU of 0.74 while the front is inside the village;
  - detection latency of 2.1 min median and 3.0 min at the 90th percentile.
- **Timing:** for a table-top time scale, shorten the heartbeat to about 1 s and the timeout to about 3 s.
- **Estimator:** use the same alive-or-dead estimator.
  - Burned probability at each map point is the inverse-distance-weighted share of dead boards among the 4 nearest; the front is the 0.5 contour.
  - Overlay arrival times by IDW of the boards' death times.
  - Both run in milliseconds for 25 nodes.
- **Spot fires:** to show one, "burn" a board ahead of the front while the boards between stay alive. The rule above flags it when a second nearby board dies shortly after.
- **Grid confounder:** add a "grid outage" button that silences a group of boards wired as one "feeder" at the same instant. The topology classifier then labels the burst as grid, which shows why topology matters.
- **Be honest in the demo:** battery tags are the favourable case. Smart meters behave very differently because the grid fails first.

## Limitations of this pass

- Everything is synthetic.
  - Buildings other than 59 OSM ones are synthetic. The fire is a simple eikonal model with no terrain, and the network is synthetic.
  - Fault probabilities, ignition delays and spotting rates are assumptions, though they are swept.
- The ground-truth front is a fairly smooth west-to-east sweep, which flatters interpolation. Errors on a fire with more complex terrain-driven spread would be larger.
- Error is evaluated over all burned buildings, so it mixes interpolation inside the network with extrapolation into dark areas.
- The physics-based fit does not recover the true spread parameters. Classification balanced accuracy is undefined, and not reported, when there are almost no grid deaths.
- Only one area and one wind direction were simulated. The substation sits east of most of the town, downwind of the fire.
