# hazard_contract v1

The interface between fire-scenario **producers** (Track A `firecast-lab`, adapters) and the
evacuation **oracle** (Track C `evacplan`). Dependencies: numpy and pydantic. The code and
tests are the definition; this page summarizes them.

```python
import hazard_contract as hc
s = hc.ScenarioSet.read("path/to/scenario_set")          # or hc.from_wfg_packet(dir), hc.synthetic(...)
hz = s.member(0).segment(geom_xy, t_in, t_out)           # one member, speed profile unknown
hz = s.member(0).segment_uniform(geom_xy, t_in, t_out)   # one member, uniform motion (router's rule)
all_k = s.query_uniform(geom_xy, t_in, t_out)            # every member at once (faster)
```

## Exchange format

A scenario set is a folder:

| file | content |
|---|---|
| `members.npz` | `ignite_s`, `extinguish_s` float `[K, H, W]`, seconds after issue time; `supported` bool `[K, H, W]` |
| `meta.json` | `ScenarioMeta`: `contract_version`, `crs_epsg`, `transform` (rasterio order, north-up), `height`, `width`, `K`, `issue_time_utc`, `horizon_s`, `source` (`model`/`packet`/`perimeter`/`drawn`/`synthetic`), `synthetic`, `model_version`, `weather_source`, `heat_source`, `provenance`, `extra` |

Cell semantics: the cell burns on the half-open interval `[ignite_s, extinguish_s)`.
`ignite_s = inf` means it does not burn within the horizon (then `extinguish_s = inf`).
`nan` means unknown, and unknown cells must have `supported = False`. Negative times are
before issue (`-inf` ignition = burning since an unknown earlier time). The set says nothing
about `t > horizon_s` or about anything outside the grid.

## Query protocol

`HazardMember.segment(geom_xy, t_in, t_out) -> SegmentHazard` for a polyline `[n, 2]` in the
grid CRS occupied during the closed interval `[t_in, t_out]`. A stationary position (waiting,
a destination stay) is a single point.

| field | meaning |
|---|---|
| `contact` | `True`: a supported touched cell burns at some instant of the occupancy (certain). `False`: none does and the query is supported. `None`: unknown |
| `supported` | `False` if a touched cell is unknown, the geometry touches the grid's outside (closed cells: even its outer edge), or `t_out > horizon_s`. **Treat as unresolved, never as safe** |
| `flux_lower`, `flux_upper` | kW/m², bounds on the peak incident flux for any speed profile (`inf` upper when unbounded) |
| `dose_lower`, `dose_upper` | kJ/m², bounds on the time-integrated flux |

Cells are **closed** squares: a road along a grid line or through a corner touches every
adjacent cell (the "whole-road" rule of the existing checker; stricter than router-cell
semantics). `segment()` applies the whole occupancy interval to every touched cell
(conservative). `segment_uniform()` assumes uniform motion along the polyline, as the router
does for edge chords: cells are checked only while actually occupied, which is the exact
closed-cell rule under that assumption.

## Reference flux model `sheet_solid_angle_v1`

The `wfg_latest` law: each burning cell is a uniformly, isotropically emitting horizontal sheet
`emission_height_m - receiver_height_m` above the receiver with radiant emission
`q_rad = χ·τ·w·f·H / T` (kW/m²); a receiver gets `q_rad·Ω/(4π)` per burning cell (`Ω` = the cell's
exact solid angle). With the repo's packet parameters `q_rad = 1.406 kW/m²`, a burning cell gives
0.686 kW/m² at its own centre and 0.00215 kW/m² at a neighbour's, and total flux never exceeds
`q_rad/2 = 0.703 kW/m²`. Bounds: exact `Ω` at probe points for the peak lower bound; a
bathtub-principle bound on `Ω` from the nearest distance for upper bounds; unknown cells count
as burning in upper bounds and not at all in lower bounds; cells beyond `near_radius_m`
(default 5 km) are bounded by count. Every bound is a function of the burning set over time, so
under the scalar duration policy adding burning can never lower any bound.

## Adapters

| adapter | source | notes |
|---|---|---|
| `from_wfg_packet(dir, present_fire="exact")` | this repo's hazard packets | Rule 4 applied: cells with missing native probability or unknown burned state become unsupported (32–100% of road cells in the Korean packets). Present fire: exact remaining time, or the router's scalar enclosure |
| `from_perimeters(series, burn_duration, ...)` | observed perimeter progression | stratified / rotated / `envelope` (the union of all possible burning intervals) members; horizon = last perimeter |
| `from_drawn_zones(polygons, spread_speed, ...)` | hand-drawn burning zones | isotropic earliest-arrival spread, one member per speed |
| `synthetic(...)` | SYNTHETIC test fires | always labeled synthetic |

## Change control

Interface changes go through the orchestrator, are recorded in `program/DECISIONS.md`, and
bump `CONTRACT_VERSION`. Run the tests with `python -m pytest hazard_contract/tests`.
