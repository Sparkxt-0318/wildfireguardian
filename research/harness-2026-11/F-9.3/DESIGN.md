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
- **Unknown cells: sound three-way rule** (Iris, adopted by the orchestrator; supersedes "support = false withholds
  every claim").

  1. **Optimistic instance** = the packet as written: unknown cells are not hazards. For existing frozen packets this
     is the frozen packet itself, so nothing frozen is rewritten and the support channel stays all-true.
  2. **Pessimistic instance** = the optimistic blocked intervals plus extra blocks on UNKNOWN cells, with the same
     cell-to-road footprint rule as flame contact.
  3. **Label:**
     - **checked**: feasible in the pessimistic instance *and* passing the unchanged checker.
     - **no-route**: infeasible in the optimistic instance (adding hazard can only remove routes).
     - **unresolved**: otherwise.
  4. **UNKNOWN for c651 packets** (two flags, both from `constructed_arrays.npz`):
     - `U_state = mask__unknown_cumulative_state`
     - `U_q = mask__policy_assigned_zero & ~mask__known_burned & ~U_state`
     - **Caution:** the masks are window-shaped in native **north-up** row order. HAZARD flame and support flat arrays
       have row 0 at the **south**, so flip rows before mapping to router cells.
     - Measured: Yeongdeok 03-25 19Z has U_state 2,570 and U_q 315 of 4,757 cells; Uiseong 03-25 17Z has 953 and 314
       of 4,745.
  5. **What unknown blocks** (both tiers reported):
     - **Tier A, strict:** every UNKNOWN cell blocked on [0, H].
     - **Tier B, speed-bounded:** let S0 = present fire ∪ U_state ∪ positive-probability cells. A U_q cell at distance
       d from S0 is blocked on [d/v, H], with v = 1.5 and 8.2 km/h stated with every result.
     - U_state cells count as possible radiation sources in the pessimistic dose and peak precondition, not in the
       optimistic one.
  6. **Arrival rasters (F-DYN).** Cells outside the final perimeter but inside the mapped grid are **observed no-fire**,
     not unknown. In the kriged TOA these are exactly the c651 `U_state` cells (NaN TOA), so the two sources disagree
     on purpose: a forecast does not know them, while a reconstruction has observed them unburned. The packet records
     which reading applies. Cells outside the grid are unknown and are not in the packet.
  7. **Report per packet:** the cell counts per flag, and the number of requests per label under each tier.
- **Envelope member for interval sources** (Iris, adopted). A cell with arrival in [lo, hi] is **one member** burning
  on [lo, hi + T). This is the default for zones, perimeter sequences and rasters with uncertainty. Sampled members
  remain an option, labelled. The envelope is conservative by construction and avoids the non-monotone burn-out case,
  where an early sample also ends early.
  - **Law.** The envelope needs per-cell burning ends. The unchanged writer and the kit's independent checker
    implement one scalar duration T per packet.
  - **F-DYN now** (`_packet_child.py`, option B): the envelope HAZARD is assembled with the writer's own member loop
    and per-cell ends. A self-check proves that loop reproduces the writer exactly with scalar ends. The packets declare
    `source_law_version = wfg.fdyn.envelope-per-cell/1`, and the kit's independent checker is not applicable to them.
  - **Proper home (option C).** A per-cell law in the writer and in the independent checker, with the scalar law as
    the special case. What option C would change:
    1. **Writer.** `bridge.construct` takes an optional per-cell end array `extinction_s[S, H, W]`, defaulting to
       `round_up_sum(ignition, T)`. Breakpoints and active sets use it unchanged otherwise. `constructed_arrays.npz`
       already stores `member<k>__extinction_breakpoint_s`. The assumptions gain
       `burning_law: scalar | per_cell` and the per-cell array's SHA-256.
    2. **Independent checker** (`kit/runner/ffi_independent_checker.py`). Today it recomputes activity from the
       scalar `burning_duration_s` and `initial_remaining_s`. It would read per-cell ends from
       `constructed_arrays.npz` when `burning_law = per_cell`, and recompute flux from the same active sets.
    3. **Regression.** Every existing packet (scalar law) must stay byte-identical, the 20 missions' verdicts
       unchanged.
    Until option C exists, option B packets carry "single implementation, not independently checked" (see the
    F-DYN README), and Thomas's O2 re-derivation is the substitute independent check.
- **Perimeter sequences** (Iris's question):
  - For the **first polygon** P_1 (time t_1, issued at t_0): `lo = t_0` (issue time); present-fire cells are kept as
    recorded.
  - **Cells in no polygon:** no fire up to t_n (the last forecast time), unknown after t_n, i.e. `known = False` for
    t > t_n.
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
   versions. Across environments (Iris), the hard checks are on what matters:
   - The **integer instance** (blocked departure seconds per edge; Thomas's format) must be identical.
   - **Verdicts and arrival seconds** on the 20 frozen missions must be identical.
   - Flux tolerance is **relative 1e-9** (Priya measured about 1e-10 relative across platforms), not 1e-12 absolute.
   Byte identity is required only within one environment.
5. **Third source:** a `perimeter_sequence` from a synthetic or archived KFS-style product is ingested with no routing
   code change. Its cells outside the declared domain carry `support = false`.

## Open questions

- **Synthetic starts.** Starts other than recorded inputs need a present-fire export that is not a c651 product (see
  the F-DYN reach finding). That is a contract-binding change for the orchestrator to decide.
- **Grid.** The writer requires the hazard grid to coincide with the forecast grid. Agency products in other CRSs or
  resolutions are rasterized onto it, conservatively, as `spread_zones` already does.
