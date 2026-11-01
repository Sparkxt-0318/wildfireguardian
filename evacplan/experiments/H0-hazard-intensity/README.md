# H0: hazard intensity, SYNTHETIC dev instances vs Korean router packets (dev fires)

**Type:** measurement (analysis), not a method experiment. No tuning; generators, methods and
`hazard_contract` are unchanged. **Decision:** n/a (analysis). **Data:** dev only (frozen SYNTHETIC
dev split; Korean dev fires). **Label:** every SYNTHETIC number and figure says SYNTHETIC.

## Pre-registration (written and committed 2026-11-01, before any flux, dose, contact, support or distance value was computed)

### Why

Siyeong, `program/DECISIONS.md` 2026-11-01 item 4: "Report the peak flux and cumulative dose
distributions on the synthetic instances alongside the real Korean panel (peak about 0.7 kW/m²). If
synthetic hazards are much hotter, tell me before tuning to them." E1 (ALNS with the oracle in the loop)
is not tuned until this verdict is in.

Background. The SYNTHETIC fires burn persistently: every ignited cell keeps burning at the flaming rate
for 48 h, i.e. through the horizon, with the packets' heat parameters (`evacplan/docs/ASSUMPTIONS.md`
#43, #44). In the Korean router packets a cell burns about 66 min (T = 3970 s; present fire until the
packet's `R_max`). Both use the `sheet_solid_angle_v1` flux law (`hazard_contract/README.md`) with the
same q_rad = 1.406 kW/m², so total flux never exceeds q_rad/2 = 0.703 kW/m² in either panel: peak flux
is capped the same way, while dose near burned areas can differ a lot.

### What was looked at before this pre-registration

Structural metadata only: grid shapes, K, horizons, node counts and the time per query (about 2 ms
per single-point query returning all members). No flux, dose, contact, support or distance value.

| panel | sources | K | horizon | grid (cells of 375 m) | receivers |
|---|---|---|---|---|---|
| SYNTHETIC | 10 dev instances (4 S, 4 M, 2 L) | 8 | 3 h (S), 4 h (M), 6 h (L) | roads + 2 cells, 4 km of wildland to the west | 80-475 road nodes per instance, 2,091 in total |
| Korean | 3 dev fires × 3 packets | 4 | 1 h (3600 s) | Uljin 62×58, Hongseong 18×18, Miryang 17×11 (= the graphs' grids) | graph nodes: Uljin 9,372, Hongseong 915, Miryang 1,494 (all inside their grids) |

### Panels

- **SYNTHETIC:** the 10 frozen dev instances, regenerated through `evacplan.instances` (dev only, the
  frozen fingerprints are verified), each with its K = 8 scenario set. Receivers: every road node.
- **Korean:** the router packets of the dev fires only, `uljin_2022`, `hongseong_2023` and
  `miryang_2022`, 3 packets each, under `$WFG_ROUTING_INPUTS/latest_inputs_try02/packets/`.
  Converted only through `hazard_contract.from_wfg_packet` (default `present_fire="enclosure"`, rule 4
  applied with no opt-out); evacplan code never reads a packet file. Receivers: the nodes of the
  matching router graph `$WFG_ROUTING_INPUTS/graphs/<fire>/graph.json`, read through
  `evacplan.adapters.wfg_graph`, restricted to nodes strictly inside the scenario grid (all of them).
  The script refuses any other fire name. `uiseong_andong_2025` and `yeongdeok_2025` (KR-2025 test
  season, rule 5) are never opened.

### Exposures

- A stationary receiver at a node over windows of 5, 15, 30 and 60 min, queried with
  `ScenarioSet.query` on a single-point geometry (a stationary occupancy), all members at once.
- Windows start every 10 min from the issue time (t0 = 0, 10, 20, ... min) and must end by the horizon
  (t0 + length ≤ `horizon_s`). Windows per node: Korean 6 / 5 / 4 / 1 (for 5 / 15 / 30 / 60 min);
  SYNTHETIC S 18 / 17 / 16 / 13, M 24 / 23 / 22 / 19, L 36 / 35 / 34 / 31.
- Per (node, window, member) record: contact (certain = `True`, none = `False`, unknown = `None`),
  supported, flux_lower, flux_upper (kW/m²), dose_lower, dose_upper (kJ/m²).
- **No subsampling.** Every node, window and member is queried: 565,488 Korean queries (2,261,952
  exposures, of which 565,488 are 30-min windows) and 218,952 SYNTHETIC queries (1,751,616 exposures, of
  which 437,904 are 30-min windows), plus 54,738 queries for the persistence diagnostic below. That is
  about 29 CPU-minutes, run as 4 worker processes inside one bench-lock hold (budget: 30 min of lock
  time). No randomness is used anywhere.

### Distance bands

- d = Euclidean distance from the receiver to the nearest closed cell square that is supported and
  burning at the window start t0 in that member (`ignite_s ≤ t0 < extinguish_s`, the members' burning
  intervals read from the `hazard_contract` objects); in-grid cells only; d = 0 when the receiver lies
  on or in such a cell. Unknown (unsupported) cells are not known to burn, so they never set d.
- Bands: **0-375 m** [0, 375), **375-750 m** [375, 750), **0.75-1.5 km** [750, 1500),
  **1.5-3 km** [1500, 3000]. Exposures with d > 3 km or no burning cell are counted as "beyond" and
  are not part of the rule.

### Statistics

- Distribution statistics use **contact-free, supported** exposures (`contact is False`, which implies
  `supported`). The share with certain contact (would be `model_no_route`) and the share unsupported
  (would be `unresolved`) are reported separately, per panel × band × window length and overall.
- Per panel × band × window length:
  - n, median, p90, p99 and max of flux_lower and dose_lower;
  - the same for flux_upper and dose_upper over finite values, with the share infinite;
  - the share with dose_lower ≥ 100 kJ/m² (the dose budget), and the same for dose_upper.
- Quantiles: `numpy.quantile` with its default linear method.
- Overall peak flux over **all** exposures, contact and unsupported included: max flux_lower and max
  finite flux_upper per panel (and per band), to confirm the ~0.7 kW/m² cap in both panels.

### Pre-registered rule

SYNTHETIC is **"much hotter"** if, in any distance band with at least 200 contact-free supported
exposures in both panels, for the 30-min windows, either:

1. the SYNTHETIC median or p90 of dose_lower is at least 2× the Korean value; or
2. the SYNTHETIC share of exposures with dose_lower ≥ 100 kJ/m² is at least 2× the Korean share and at
   least 1 percentage point higher.

Applied exactly as written, with these readings fixed in advance: "at least 2×" is SYNTHETIC ≥ 2 ×
Korean; if both values are 0 the criterion is not met, and a Korean 0 against a positive SYNTHETIC value
meets it; shares are fractions of the band's contact-free supported 30-min exposures and use ≥ 100. A
band where either panel has fewer than 200 contact-free supported 30-min exposures (for example because
rule 4 leaves Korean cells unsupported) cannot be judged by the rule; the report says so. If no band can
be judged, `much_hotter` is false and the report says the rule could not be applied anywhere.

**Descriptive label** per judged band, from r = √(r_median × r_p90), the geometric mean of the
SYNTHETIC/Korean ratios of the 30-min dose_lower median and p90: **much hotter** if the rule triggers;
otherwise **hotter but not much** if r ≥ 1.25, **cooler** if r ≤ 0.8, **comparable** if 0.8 < r < 1.25.
Overall label: much hotter if any band triggers; otherwise hotter but not much if some band is hotter
and none is cooler, cooler if some band is cooler and none is hotter, comparable if all judged bands
are comparable, and "comparable (mixed)" if both hotter and cooler bands occur.

### Secondary analyses (descriptive only, never part of the rule)

1. Per-source breakdown (each SYNTHETIC instance; each Korean fire and packet) of the 30-min table.
2. SYNTHETIC restricted to windows that end by 3600 s, the Korean horizon ("SYNTHETIC first hour").
3. Persistence diagnostic: the same SYNTHETIC scenario sets with every burning interval cut to the
   packets' scalar burn duration (extinguish = ignite + 3970.46 s; same ignitions, same heat law),
   30-min windows only. Built in memory with `hazard_contract.ScenarioSet`'s public constructor; the
   generator is untouched; labelled "SYNTHETIC, 66-min burning (diagnostic)". The rule's arithmetic is
   applied to it descriptively, to see whether persistent burning explains any difference.
4. Within-band distance distribution (p10, median, p90 of d) of the contact-free supported exposures,
   to show whether a band difference comes from where the receivers sit inside the band.
5. dose_upper compared with the same thresholds, because the Korean dose_lower counts unknown cells as
   not burning while the upper bounds count them as burning.

### Known biases (stated before the results)

- **Rule 4.** It leaves 32-100 % of Korean road cells unsupported, so the supported Korean exposures may
  be a biased subset (receivers whose own cells are known). The Korean dose_lower also ignores unknown
  cells, which biases it low near unknown areas.
- **Burn duration.** 48 h (SYNTHETIC, through every horizon) vs about 66 min (Korean; present fire until
  `R_max`, about 53-65 min). SYNTHETIC fires start 1 h before issue and keep everything burned so far
  burning for 3-6 h horizons; within the Korean 1 h horizon the difference is smaller.
- **Grid and fire size.** SYNTHETIC grids cover the road region plus 4 km of wildland; the Korean
  grids are fixed windows (62×58, 18×18, 17×11 cells), and sources outside a grid are not modelled.
- **Design.** The SYNTHETIC instances are built so that the fire threatens the facilities (ignition
  placed upwind, lead 30-150 min), so their roads lie in the fire's path by construction.
- **Horizon and timing.** 1 h vs 3-6 h: 30-min windows start at 0-30 min (Korean) vs 0 to horizon −
  30 min (SYNTHETIC). Secondary analysis 2 looks at the first hour only.
- **Members and receivers.** K = 4 vs 8. The Korean panel is about 80 % Uljin nodes and the SYNTHETIC
  panel about 56 % L-instance exposures. Exposures are strongly correlated (neighbouring nodes,
  overlapping windows, members), so n counts exposures, not independent observations.

### Outputs

- `h0_hazard_intensity.py`: computes everything from scratch (`compute`, then `analyze`); raw
  per-exposure records go to `evacplan/runs/H0-hazard-intensity/` (git-ignored, regenerable).
- `results.csv` (panel × band × window length, including the secondary panels), `results_by_source.csv`,
  `inventory.csv`, `peak_flux.csv`, `verdict.csv`; every row records commit, seed, config and host.
- `figures/`: CDFs of 30-min dose_lower by band, one plot per panel titled "SYNTHETIC dev instances" and
  "Korean router packets (dev fires), rule 4", the same per band with both panels overlaid, and peak
  flux by band.

## Results

Not yet computed (nothing below this heading existed at pre-registration).
