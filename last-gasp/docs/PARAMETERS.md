# Parameters and defaults

Every parameter lives in `configs/default.json` and can be overridden from scripts with `--set key=value` (for example `--set observe.meter_fraction=0.2`). All results are synthetic. Defaults are plausible values chosen to test the reconstruction, not calibrated estimates of the March 2025 Gyeongbuk fires. Sources are listed in `data/SOURCES.md`; "assumption" means no source was found and the value is a judgement call that the sweeps vary.

## World (`world`)

| Key | Default | Reason or source |
|---|---|---|
| `bbox_lonlat` | 129.350 to 129.385 E, 36.400 to 36.430 N | About 3.1 km by 3.3 km (10.4 km²) around Yeongdeok-eup, Yeongdeok-gun. Yeongdeok was one of the five counties hit by the March 2025 fires (Newsis 2025-03-27). The synthetic fire does not reproduce the real fire's footprint here. |
| road classes | primary to track, no footways | Feeders follow drivable roads. Source: OpenStreetMap. |
| `n_buildings_target` | 1500 | OSM maps only 59 buildings in the box. 1,441 synthetic buildings are added along real roads to reach a small-town density of about 144 per km². Assumption. |
| synthetic building road weights | residential 3, tertiary or unclassified 1.5, service 1, primary 0.6, track 0.3 | Houses cluster on local roads. Assumption. |
| offset from road | 10 to 30 m | Assumption. |
| min spacing | 9 m | Avoids overlapping buildings. Assumption. |
| cluster field | lognormal, sigma 1.0, correlation 250 m | Creates hamlets and gaps. Assumption. |

## Fire truth (`fire`)

| Key | Default | Reason or source |
|---|---|---|
| `cell_m` | 10 m | Building-scale resolution; about 104,000 cells. |
| `t_end_min` | 150 min | Long enough for the head to cross the box. |
| `wind_speed_ms`, `wind_from_deg` | 8 m/s from the west (270 deg) | The 2025 fires were driven east by dry westerlies with gusts reported near 27 m/s (Newsis 2025-03-27). The mean wind used here is lower than the reported gusts. |
| `ros_wind_fraction` | 0.10 | Head rate of spread = 10% of the 10 m wind speed (Cruz and Alexander 2019 rule of thumb for forest and shrubland), giving 48 m/min (2.9 km/h). This is below the 8.2 km/h peak and about 4.3 km/h average spread rate reported for 2025 (Money Today 2025-03-27; Newsis 2025-03-27). |
| `lb_model` | Alexander (1985) | Length-to-breadth ratio of 3.7 at 8 m/s, eccentricity 0.96. |
| fuel multiplier | lognormal, sigma 0.35, correlation 150 m | Heterogeneous fuels. Assumption. |
| ignition | line along the west edge, middle 60%, start-time jitter up to 8 min | Models an incoming front entering the town, not a point ignition. |
| spotting launch rate | 12 per km² burned, in 3 rounds | Gives roughly 15 to 20 spot ignitions per world, of which 2 to 5 lead the front by 10 min or more. Assumption. |
| spotting distance | lognormal, median 250 m, sigma 0.7, cap 2 km | Lognormal firebrand landing distributions are standard (Sardoy et al. 2008). No quantified spotting distance was found for the 2025 fires. |
| spot direction scatter | 12 deg | Assumption. |
| `p_ignite` | 0.35 | Assumption. |
| spot ignition delay | 1 to 5 min | Assumption. |
| `significant_lead_min` | 10 min | A spot counts for recall only if it ignites at least 10 min before the front would have arrived. |

## Power network (`grid`)

| Key | Default | Reason or source |
|---|---|---|
| `pole_spacing_m` | 50 m | Korean straight-line concrete pole studies use 30 to 50 m spans (Kim et al. 2008, KIEE). No official KEPCO span standard was found. |
| root | pole nearest the OSM Yeongdeok Substation | Real substation location (OSM way 888564838). Feeder routing is synthetic. |
| `n_feeders` | 6 | Root children plus the heaviest laterals become separate circuits. Assumption. |
| `recloser_spacing_m` | 1000 m on main lines with at least 20 buildings downstream | Korean 22.9 kV feeders use reclosers and sectionalizers on mains (secondary source; CIGRE Electra 2022). The spacing is an assumption. |
| fuses | at every lateral head; a transformer cutout at every pole with customers | Standard radial protection. |
| `p_span_fault_given_fire` | 0.05 per 50 m span | Probability that a span the fire reaches faults (conductor damage, flashover). Assumption, swept from 0 to 0.2. |
| `p_transformer_fault_given_fire` | 0.3 | Assumption. |
| `span_fault_delay_min` | 0 to 10 min after fire arrival | Assumption. |
| `random_fuse_rate_per_h` | 0.01 per fuse per hour | Unrelated outages (wind, trees, animals). Elevated for a windy day. Assumption. |
| `random_breaker_rate_per_h` | 0.003 | Assumption. |
| `substation_trip_min` | none | Optional sensitivity case: every feeder trips at this time. In 2025, fire-caused transmission trips and a precautionary shutoff blacked out about 95% of Yeongdeok county (Electimes 2025-04-09; Hankyung 2025-03-26). |
| `grid_failure_multiplier` | 1.0 | Scales all fault probabilities and rates for the sweep. |

## Observation model (`observe`)

| Key | Default | Reason or source |
|---|---|---|
| `meter_fraction` | 0.5 | Fraction of buildings with a reporting smart meter. KEPCO reports its own AMI rollout complete (about 20 million customers), but Gyeongbuk was the lowest region at 39% in figures reported in 2022 (Electimes 2022-09-19), and a working last-gasp path is not documented (see `docs/DESK_RESEARCH.md`). Swept from 0.05 to 1.0. |
| `p_building_burns` | 0.75 | Fraction of reached buildings that are damaged enough to kill the device. Assumption. |
| ignition delay | lognormal, median 5 min, sigma 0.8 | Time from front arrival to loss of the building's supply. Assumption, swept. |
| `timing_noise_multiplier` | 1.0 | Scales the ignition delay median, clock jitter and tag delay. |
| meter `p_deliver` | 0.8 | Swept from 0.2 to 1.0. Industry sources report that collisions can block up to 80% of last gasps in big outages, and PLC last gasps are slow or unreliable (Ketchledge 2008; Clou Global). |
| mass outage factor | 0.8 when 10 or more meters die together | Collision losses. Assumption. |
| meter clock jitter | SD 0.25 min, plus 0.05 min latency | Assumption. |
| router | delivery 0.95, ISP poll interval 5 min | Assumption. ThunderPing pinged hosts every 11 min (Padmanabhan et al. 2019), so 5 min is optimistic. |
| tag | heartbeat 30 s, 90% heard, dies 0 to 2 min after the fire arrives, 95% die | Models the ESP32 demo. Assumption. |
| random device failure | 0.001 per device per hour | Assumption. |

## Classification (`classify`)

| Key | Default | Reason |
|---|---|---|
| `window_min` | 1.0 min | Must exceed clock jitter (about 4 SD = 1 min). |
| `min_cluster` | 3 | Smallest burst called a grid event. |
| `min_fraction_of_expected` | 0.5 | Burst must contain at least half the expected delivered gasps from still-powered meters below the device. |
| `small_device_max_buildings` | 30 | A spot candidate with a simultaneous partner under a device this small is rejected as a grid event. |

## Reconstruction (`reconstruct`)

| Key | Default | Reason |
|---|---|---|
| `eval_cell_m` | 20 m | Evaluation grid. |
| `idw_power`, `idw_k` | 2, 8 nearest | Standard IDW. |
| assumed delay | equals the true median delay (5 min times the noise multiplier) | The operator is assumed to have calibrated the delay. This isolates the effect of noise spread from bias. |
| `huygens_k` | 3 | k-th smallest Huygens arrival; robust to one or two early outliers. |
| `residual_length_m` | 200 m | Range of the residual correction. |
| `spot_tolerance_min` | 12 min | A death this much earlier than any earlier death can explain is an unexplained ignition. |
| `support_tolerance_min` | 5 min | Later deaths count as support only if they are also early. |
| `spot_min_support` | 1 | At least one supporting death. |
| `corridor_width_m` | 80 m | Corridor for the surviving-node check. |
| `survivor_margin_min` | 3 min | |
| `fit_huber_min`, `fit_starts` | 5 min, 4 starts | Robust fit of spread rate, direction and length-to-breadth ratio. |

## Evaluation (`evaluate`)

| Key | Default | Reason |
|---|---|---|
| `spot_match_distance_m` | 250 m | A detection matches a true spot within 250 m and 20 min. |
| `spot_match_time_min` | 20 min | |
| `interior_margin_m` | 100 m | Grid-cell metrics exclude a 100 m border. |
