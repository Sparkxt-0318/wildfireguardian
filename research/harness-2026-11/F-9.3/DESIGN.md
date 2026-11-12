# F-9.3: model-agnostic hazard interface (design note, v1; nothing beyond F-DYN implemented yet)

**Goal.** The route checker accepts an agency's own spread prediction, or any arrival-time product, as a hazard
scenario, not only the c651 forecast. Example: Korea Forest Service 5 h and 8 h fire-line polygons with arrival
times. **Scope (orchestrator):** a superset of `api/adapters/spread_zones.py` (API 1.8), with a regression test on
existing inputs. This note says what the superset adds before it is built.

## What exists

| Input | Path | Ignition source at the writer's `bridge.draw_ignitions` |
|---|---|---|
| c651 forecast export | `packets.write_regional_packet` | independent uniform random draws from the new-burn probability |
| `spread_zones` (polygons with `arrival_h_max` bands, API 1.8) | `api/adapters/spread_zones.py` + `_zone_packet_child.py` | 4 deterministic times per band; 1 h horizon only |
| arrival-time raster (F-DYN, research) | `research/harness-2026-11/F-DYN/fdyn` | `floor_Q(s(a−h) − shift)`; multi-hour; T+Q widening |

All three use the same unchanged writer and the same two injection points: `draw_ignitions` and `settings_for`. The
settings digest, and therefore the construction id and scenario ids, identify each source.

## The superset: one internal form, `ArrivalScenario`

Every source is reduced to a per-cell arrival interval on the forecast grid, then to the existing ignition schedule.

```
ArrivalScenario {
  grid            : the export grid (EPSG:5179, 375 m), the writer's requirement
  arrival_lo_h    : earliest arrival per cell (hours since a declared t0; NaN = no fire in this scenario)
  arrival_hi_h    : latest arrival per cell (= lo for point estimates)
  known           : bool per cell; False = source says nothing (outside its domain), NOT "no fire"
  members         : rule mapping [lo, hi] to member times (point estimate, band split, speed/offset variants)
  horizon_s, quantum_s, start (a recorded input time, or a synthetic start if approved)
  provenance      : source type, product id, issuer, issued_at, file SHA-256s, adapter version, label
}
```

**Adapters** (each one small, pure, and tested on its own):

1. **`c651`**: no change. Random draws stay in the bridge. This adapter is listed only so that the regression test
   runs through the new entry point.
2. **`zones` (bands).** The `spread_zones` v4 rules, verbatim:
   - Conservative rasterization; nesting within a fire; each cell's band is (H_prev, H].
   - `lo = H_prev − margin`, `hi = H`; the 4 members are lo and the 1/3, 2/3 and 1 points of the band.
   - `known` = inside the union of zones, plus present fire.
   - Required: byte-identical packets vs the current adapter (same environment).
3. **`perimeter_sequence`** (new; KFS 5 h / 8 h style). Time-stamped polygons P_1 … P_n with times t_1 < … < t_n,
   possibly from different issues.
   - A cell first inside P_k but outside P_{k−1} gets `lo = t_{k−1}` (the earliest reading) and `hi = t_k`.
   - `known` = inside the product's stated domain if declared, else inside P_n.
   - This equals the zones rule with explicit times; the difference is that `known` is declared rather than inferred.
4. **`arrival_raster`** (new; F-DYN). `lo = hi = raster`, or `lo/hi` from a bracket pair. Variants are
   `kriged_mean`, `firms_constrained`, `firms_early` and dilations.
   - `known` = inside the raster's mapped domain.
   - Outside the final perimeter but inside the domain is observed no-fire (Iris).

## Rules that must not regress

- **Earliest reading by default** (Iris). The `lo` member is always present, and `floor(start)` / `ceil(end)` holds:
  burning duration T+Q with `consumed_fraction · (T+Q)/T`, so the contact interval contains [t, t+T) and flux density
  is unchanged (F-DYN v2, verified on one packet).
- **Present fire stays exactly as recorded.** No source re-ignites a present or burned export cell. A source that
  places a cell before the start, although the export has it unburned, ignites it at 0 if it is still burning,
  otherwise it counts as burned out. Counts are recorded.
- **Unknown stays unknown.** Cells with `known = False` must be written with `support = false`. The router
  (`routing/core.py`) then rejects any route through them (UNSUPPORTED) and withholds every global optimality or
  no-route claim (`_globally_supported`). That is the honest consequence: a packet with unknown cells can give checked
  routes but never "no route" or optimality certificates.

  **Writer change needed:** the writer currently writes support all-true. This is the one place the superset needs a
  writer change: an optional `support_mask` argument, default all-true, so existing packets are unchanged.
- **Labels.** Every packet carries the source type and a label: "agency product as supplied", "scenario built from a
  reconstruction", and so on. It never says "the fire".

## Regression test (acceptance)

1. **c651:** the 6 recorded 2025 packets plus 3 Uljin packets, rebuilt through the new entry point.
2. **zones:** the API's recorded `spread_zones` test fixtures through the new entry point, compared with the current
   adapter's packets.
3. **Comparison rule:**
   - Within one environment, byte-identical `HAZARD.json`.
   - Against the frozen packets, field by field: scenario ids, breakpoints, flame and support exactly; flux within
     |Δ| ≤ 1e-12 kW/m², where 1.1e-15 is measured for numpy 2.5 vs the macOS build. Identity is equal except
     `radiation_operator.module` (an absolute path).
4. **Environment:** the test pins numpy to `constraints-routing.txt` (1.26.4) and records the numpy and scipy
   versions in the test report. It fails, not skips, when they differ, unless run with an explicit `--cross-env` flag
   that switches to the tolerance comparison.
5. **Third source:** a `perimeter_sequence` from a synthetic or archived KFS-style product is ingested with no routing
   code change. Its cells outside the declared domain carry `support = false`.

## Open questions

- **Synthetic starts.** Starts other than recorded inputs need a present-fire export that is not a c651 product (see
  the F-DYN reach finding). That is a contract-binding change for the orchestrator to decide.
- **Grid.** The writer requires the hazard grid to coincide with the forecast grid. Agency products in other CRSs or
  resolutions are rasterized onto it, conservatively, as `spread_zones` already does.
