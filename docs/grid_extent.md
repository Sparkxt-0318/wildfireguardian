# The simulation canvas: why `routing_demo.npz` stopped reproducing, and why the science did not change

**Status: permanent record.** Companion to
[`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md).

## What happened

`data/processed/routing_demo.npz` (2026-07-20, sha256 `5bed5026…18da58`) holds
the forward-simulated ignition-probability field that both routing runs consume.
Re-running the pipeline on 2026-08-01 produced `d1620f9f…` instead.

The cause is fully identified.

The forward simulation took its extent from `ev.meta.bbox_wgs84` — i.e. whatever
bbox happened to be in `data/raw/firms_data/fire_manifest.json`, a **git-ignored**
file. That file was regenerated **2026-07-23 15:21**, three days *after* the npz
was committed, replacing the fire-acquisition bbox with a tighter,
detection-derived one.

| | committed npz (2026-07-20) | re-run (2026-08-01) |
|---|---|---|
| bbox (W, S, E, N) | **(128.97, 36.10, 129.77, 36.90)** | (128.95, 36.20, 129.60, 36.75) |
| source of that bbox | fire-acquisition extent — the ERA5 / WorldCover download box | `fire_manifest.json` after regeneration |
| cell size | 500 m | 500 m (**unchanged**) |
| grid | **181 × 147** | 125 × 119 |
| extent EPSG:5179 | [1130970.0, 1789870.5, 1204470.0, 1880370.5] | [1129440.4, 1800880.8, 1188940.4, 1863380.8] |
| span | 73.5 × 90.5 km | 59.5 × 62.5 km |

Feeding the fire-acquisition bbox to `build_grid` reproduces the committed
`grid_extent` **exactly, to the last decimal**, and the committed 181 × 147
shape. The diagnosis is not inferential.

## The science did not change

| | committed | re-run |
|---|---|---|
| `envelope_area_ha` (steps 0→4) | 6225 → 18225 → 25500 → 27050 → 27900 | **identical** |
| `envelope_breadth_deg` | 48.34, 52.67, 55.49, … | **identical** |
| `drift` vs observed | — | **identical** |

Every physical quantity is unchanged. The two runs differ **only in canvas
size**. The fire never came close to either edge, so nothing was clipped:

```
boundary contact, committed npz (181 × 147 @ 500 m, p_threshold 0.3)
  slice 0 (t=  0 min)  reached=False   east=0.0000 north=0.0000 south=0.0000 west=0.0000
  slice 1 (t=180 min)  reached=False   east=0.0000 north=0.0000 south=0.0000 west=0.0000
  slice 2 (t=360 min)  reached=False   east=0.0000 north=0.0000 south=0.0000 west=0.0000
  slice 3 (t=540 min)  reached=False   east=0.0000 north=0.0000 south=0.0000 west=0.0000
  slice 4 (t=720 min)  reached=False   east=0.0000 north=0.0000 south=0.0000 west=0.0000
```

**Restoring the hash for its own sake would therefore be theatre.** The fix is
not to reproduce a digest; it is to make an unnoticed canvas change impossible.

## What changed instead

### 1. The canvas is now a stated parameter

`config/default.yaml`:

```yaml
grid:
  simulation_bbox: fire_acquisition   # key into bbox:, or explicit [W, S, E, N]
```

`resolve_simulation_bbox()` (`src/wildfireguardian/spread_v2/extent.py`) resolves
it, and `scripts/run_routing_integration.py` prints both the resolved canvas and
a note when it differs from `fire_manifest.json`. The default is
`bbox.fire_acquisition` because that is the extent for which ERA5 weather and
WorldCover fuel were actually downloaded — the largest canvas on which every
input layer is real. **That is a choice, and it is now written down.**

### 2. Clipping is a loud error

`assert_envelope_within_grid()` raises `GridBoundaryError` if any forward-sim
slice reaches the outer ring of its grid at p ≥ 0.3:

```
forward simulation reached grid boundary — enlarge simulation_bbox
```

A clipped envelope under-reports area, breadth and drift, and every downstream
routing decision inherits that under-report. Previously it passed silently.

### 3. Routing clearance is checked and disclosed

Nodes outside the hazard grid read p = 0 — no hazard, no extrapolation — which is
**optimistic**. `check_routing_clearance()` warns when the routing extent is
within `grid.boundary_check.routing_clearance_km` (5 km) of the grid edge.

This is a warning, not an error: it is a limitation to disclose, not a corrupted
result.

Measured, OSM road-network bbox against each canvas:

| canvas | west | south | east | north | verdict |
|---|---:|---:|---:|---:|---|
| fire-acquisition (committed, 181 × 147) | 25.56 km | 22.96 km | **20.40 km** | 33.73 km | OK |
| `fire_manifest.json` after 2026-07-23 (125 × 119) | 27.09 km | 11.95 km | **4.87 km** | 16.74 km | **WARNS** |

So the 2026-07-23 manifest change was not merely cosmetic: it cut the eastern
clearance from 20.4 km to 4.87 km, below the 5 km threshold. On the committed
canvas the check is silent; on the narrow one it fires. The committed 459-origin
run independently records `n_nodes_outside_hazard_extent: 0`, consistent with the
wide canvas.

## Reporting rules

* `routing_demo.npz` sha256 `5bed5026…` is **verified** (the file is intact and
  the 459-origin run records the same digest) but **not reproducible** from the
  current `fire_manifest.json`. Say both.
* Do not describe the two grids as giving different results. They give the same
  physical result on different canvases.
* If `fire_manifest.json` is regenerated again, the canvas will not follow it —
  `config` wins. That is deliberate.
