# F-9.3: model-agnostic hazard interface (implementation v1)

**Design.** `DESIGN.md` @df2c797, including Iris's three-way unknown rule, the envelope default and option C. **Code:**
`hazard_iface/`. **Tests:** `tests/test_iface.py`.

## What exists

- **`ArrivalScenario`** (`hazard_iface/scenario.py`). One internal form for every source: source type, member rule,
  region, start, per-cell `arrival_lo_h` and `arrival_hi_h`, known-flags and provenance. `build()` dispatches to the
  **existing, unchanged** build paths:

  | Source | Build path |
  |---|---|
  | `c651` | `integration/src/wfg_latest/build_packet.py`, the recorded command |
  | `zones` (sampled) | `api/adapters/spread_zones.build_packet`, the API 1.8 child |
  | `arrival_raster`, `perimeter_sequence`, envelope | the F-DYN child: the unchanged writer through its injection points, on the full KFS_01 grid; the envelope uses the per-cell law, so the kit's independent checker does not apply |

- **Adapters** (`hazard_iface/adapters.py`):
  - `from_c651`: emits Iris's flags `known_burned_state`, `known_probability` and `inside_reconstruction`.
  - `from_zones_plan`: the API plan, verbatim.
  - `from_perimeter_sequence`: time-stamped polygons. A cell first inside P_k gets [t_(k−1), t_k], with t_0 the
    issue time. `known = False` outside the declared domain. Default rule: envelope.
  - Arrival rasters use F-DYN `build.py` directly.

## Acceptance tests (all pass; about 46 s; Python 3.13, numpy 2.5.3)

1. **c651 regression.** Interface build == direct `build_packet.py` build, byte-identical `HAZARD.json`, for Yeongdeok
   03-25 19Z. Against the frozen packet: ids, breakpoints, flame and support exact; flux within relative 1e-9.
   Known-flag unknown count 2,570, which equals Iris's U_state measured earlier.
2. **zones regression.** Interface build == the API adapter's own build, byte-identical `HAZARD.json`, on the
   recorded Hongseong export (the zone used in `tests/api/test_adapter.py`).
3. **Third source.**
   - A two-polygon perimeter sequence (+2 h, +4 h) is ingested and built into a valid 5 h packet; the router
     validator runs inside the writer.
   - The per-cell brackets follow the rule.
   - Cells outside the declared domain are flagged unknown.
   - `git diff origin/Main -- integration/ routing-package/ routing-api/ api/` is empty: **no routing, checker or
     API code was changed**.

## Not done (stated)

- **Unknown cells are not yet written as `support = false`.** That needs the writer's optional `support_mask`
  (DESIGN.md), a writer change not made here. Known-flags are reported in `F93_INTERFACE.json`, and the three-way
  rule (optimistic = packet as written; pessimistic = plus blocks on unknown cells) is applied downstream by Richard's
  and Thomas's tools.
- **Option C is not implemented:** the per-cell law in the writer and the independent checker.
- **Pinned numpy.** The frozen comparison ran under numpy 2.5.3, not the pinned 1.26.4. Nora ran D3 under both
  earlier, with the same outcome.
- The c651 regression covers one packet. The other recorded packets use the same command path.
