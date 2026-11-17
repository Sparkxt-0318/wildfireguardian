# Effect of the radiant-heat closure on leave-by times and witness routes

**Scope:** the F-3.1 deadline field rerun with the heat closure rule (C.1–C.2) and with a thermal-dose budget
enforced inside the field (C.4). It runs on the six recorded 2025 planner caches (1-hour panel) and on F-3.1's 48
multi-hour HEADLINE packets (F-DYN scenarios; "Multi-hour runs" below). These results are model-relative; they make
no physical-safety claim.

## C.1 Rule

Code: `kcf_heat/closure.py`; tests: `tests/test_closure.py`.

The rule is added to F-3.1's unchanged rules as variant **`cert_heat` = router OR closed footprint OR heat**. F-3.1's
headline variant `cert` is the baseline. A `cert_heat` deadline can only be equal to or earlier than the `cert`
deadline, so every change below is caused by heat.

For each burning router cell with flame phase [b, x) in a hazard member:

* **In-cell closure:** a road inside the cell rectangle is closed on **[b − T\*(q\*), x)**.
* **Lateral closure:** a road within **R·T\*(q\*)** of the cell rectangle is closed **while the cell flames**, on
  [b, x). The halo is applied as a square buffer, which contains the Euclidean one.

| exposure | q\* | T\* (law → used) | halo R·T\* (used) |
|---|---:|---:|---:|
| driving and vehicle waits | 10 kW/m² | 83.1 s → 84 s | 7.96 m |
| people standing: origin at the departure second; shelter stay (destination dwell) | 2.5 kW/m² | 349.6 s → 350 s | 33.16 m |

* Constants are the frozen packet values: χ = 0.30, E_A = 18,608 kJ/m², t_r = 11.52 s, R = 341 m/h.
* T\* is rounded up to the second and the halo up to the centimetre.
* Cost: building the heat blocks adds 0.1–0.7 s per packet (Yeongdeok, 111,924 edges: 1.4 → 2.1 s). The backward
  fields take the same time with and without heat (14–159 s per cache for each variant).
* Checks:
  * `cert` reproduces F-3.1's committed deadlines (`DEADLINES_per_origin.json`) for **530 / 530** origins (grid,
    exact and uncapped).
  * The heat blocks agree with an independent float sampling oracle on real-packet edges, in both directions.
  * Heat-feasible departures are always a subset of cert-feasible ones (tests).

## The table: 1-hour panel, heat off (`cert`) → heat on (`cert_heat`)

* A **leave-by** is F-3.1's exact 1 s planner deadline: the latest departure in the planner's range [0, +50 min]
  with a feasible journey. Its 10-minute grid value is given separately.
* **Witness TDU** is the unshielded thermal dose along each witness route (driving and waits), in (kW/m²)^4/3·s,
  counted while q > 1.42 kW/m², under the closed-form law (C.3).

| cache | origins (with a leave-by) | leave-by moved, 1 s | moved, 10-min grid | shift (s) | places that lose their route | witnesses (off → on) | witnesses ≥ 92 TDU pain (off → on) | ≥ 290 2nd-degree burn | ≥ 1000 dangerous dose | max witness TDU (off → on) |
|---|---|---:|---:|---|---:|---|---|---|---|---|
| Uiseong 03-23 01Z | 86 (85) | 2 | 0 | 84, 84 | 0 | 2,376 → 2,376 | 28 → 24 | 4 → 0 | 4 → 0 | 1,423 → 168 |
| Uiseong 03-24 09Z | 85 (85) | 4 | 2 | 76, 84, 84, 346 | 0 | 2,316 → 2,304 | 18 → 6 | 12 → 0 | 12 → 0 | 3,320 → 161 |
| Uiseong 03-25 17Z | 85 (73) | 0 | 0 | — | 0 | 2,097 → 2,097 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| Yeongdeok 03-25 19Z | 92 (85) | 0 | 0 | — | 0 | 2,930 → 2,930 | 0 → 0 | 0 → 0 | 0 → 0 | 9 → 9 |
| Yeongdeok 03-25 23Z | 91 (91) | 0 | 1 | — | **1** | 3,000 → 2,988 | 12 → 0 | 0 → 0 | 0 → 0 | 181 → 26 |
| Yeongdeok 03-26 08Z | 91 (89) | 0 | 0 | — | 0 | 3,032 → 3,032 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| **total, 1-hour panel** | **530 (508)** | **6** | **3** | **median 84, range 76–346** | **1** | **15,751 → 15,727** | **58 → 30** | **16 → 0** | **16 → 0** | **3,320 → 168** |

The multi-hour HEADLINE packets have their own tables in "Multi-hour runs" below.

### Reading the table

* **Few leave-by times move: 6 of 508.**
  * On this 1-hour panel the fire sets only a small share of deadlines. F-3.1 found 17 fire-set deadlines on the
    grid, and 52 that the fire moves at all at 1 s resolution. The others are set by the window or censored at
    +50 min, and heat cannot change those.
  * Four shifts equal the 84 s vehicle lead. One is 76 s, where another constraint binds first.
  * One is 346 s (Uiseong 03-24, `osm:node/415160424`), close to the 350 s person lead. Which of the origin or
    shelter-stay rules binds there was not traced.
  * Three cross a 10-minute grid line: two in Uiseong 03-24 (+40 → +30 min and +20 → +10 min) and one in Yeongdeok
    03-25 23Z (the lost route).
* **One place loses its route:** Yeongdeok 03-25 23Z, `osm:node/415158166`.
  * Its only checked route runs 4.9 m from a cell that burns from 0 to 3,830 s (present fire).
  * There the law gives about 15 kW/m², above the 10 kW/m² vehicle limit, and the 7.96 m halo closes the road for
    the whole hour.
  * Recorded leave-by +50 min (exact 3,401 s uncapped) → no feasible departure.
* **The binding is real but marginal on this panel.** With T\* = 84 s on 375 m cells, heat mostly acts where roads
  run along burning cell edges.

## C.3 Thermal dose units instead of linear kJ/m²

**Definition.** TDU = Σ q^4/3 · Δt (q in kW/m², t in s), summed only over seconds with q > q₀.

* Flux comes from the closed-form law with packet constants, read as the nearest front:
  * a flaming cell gives χE_A R / (2π(dist + R t_r/2)), where dist is the distance to its rectangle;
  * a road inside a cell before its arrival b gives χE_A / (2π(b − t + t_r/2)).
* The maximum is taken over cells and over hazard members, with 1 s midpoint quadrature.
* Code: `kcf_heat/exposure.py`, `scripts/c3_tdu_witness.py`; data: `data/routing_1h/TDU_witnesses.json`.

**Thresholds (primary source, read in full).** S. O'Sullivan and S. Jagger, *Human vulnerability to thermal radiation
offshore*, HSL/2004/04, Health and Safety Laboratory for HSE, 2004
([archived copy](http://web.archive.org/web/20220412004640/https://www.hse.gov.uk/research/hsl_pdf/2004/hsl04-04.pdf)).

* Table 1 (infrared, bare skin): pain **92** TDU (86–103); threshold first-degree burn **105** (80–130); threshold
  second-degree burn **290** (240–350); threshold third-degree burn 1000.
* Table 2: **1000** TDU = 1–5% fatality ("dangerous dose").
* Rew (1997), HSE CRR 129/1997, §4.1, gives 500 TDU as the dangerous dose for vulnerable people, citing Kinsman 1991.
  The Kinsman original is UNVERIFIED.
* The Eisenberg et al. 1975 probit (USCG CG-D-136-75), −14.9 + 2.56 ln(TDU), gives 957 TDU at 1% and 2,377 TDU at
  50% (computed). Its basis is UV/nuclear data, so it is context only.

**No-harm flux q₀ = 1.42 kW/m².** This is 450 Btu/ft²·h, the US limit for people outdoors in 24 CFR 51.203(a)(2);
Appendix II describes it as "3 minutes or longer with no serious detrimental effect".

* Sensitivities: q₀ = 1.0 kW/m² (longest exposure without pain, PGS 1 deel 1A 2003 §3.6) and 1.6 kW/m² (HSE
  SPC/Tech/OSD/30, long-term survivability).
* A cut-off is needed. Integrated unconditionally, 1.6 kW/m² for 10 min gives 1,123 TDU, which would label an
  exposure that HSE classes as survivable a dangerous dose.

**Does any witness route fail?** Yes for pain, no for burns.

* With heat on, **30 of 15,727 witness routes exceed 92 TDU** (pain) and **105 TDU** (first-degree burn). All 30 are
  in Uiseong 03-23 and 03-24; the maximum is 168 TDU.
* **None reaches 290 TDU** (second-degree burn).
* Heat off (today's F-3.1 field), 58 exceed 92 TDU and **16 exceed 1000 TDU** (dangerous dose), up to 3,320 TDU with
  peaks up to 78 kW/m².
* Shelter stays: none exceed 92 TDU at q₀ = 1.42 or 1.6 in either variant. At q₀ = 1.0, 12 do with heat off and none
  with heat on.
* Without a cut-off, heat on gives 54 above 92 TDU and still none above 290.
* The old linear metric (∫q dt under the same law) exceeds 100 kJ/m² on 148 heat-on witnesses, including routes with
  negligible TDU. Low flux over long times inflates it, which is the reason to replace it.

These are unshielded-person doses along the drive. Vehicle shielding is not modelled, so for occupants of a closed
vehicle they are upper-side numbers.

**Why this is not enough on its own.** The check above is post hoc: it tests one witness route per attempt. The
field's interval algebra assumes the full policy reduces to contact, and F-3.1 checks that precondition. Under the new
law the assumption fails, because dose can bind (30 witnesses exceed 92 TDU). With q\* = 10 kW/m² closure alone, the
pain threshold can still be reached near the halo edge: 92 TDU takes 4.3 s at 10 kW/m² and 11 s at 5 kW/m². So the
dose is now enforced inside the search (C.4).

## C.4 Dose budget enforced inside the field

Method and checks: [TDU_FIELD.md](TDU_FIELD.md). Code: `kcf_heat/dose.py`, `kcf_heat/tdu_field.py`.

* For every origin and second, the field gives the **minimum dose over all legal routes** under the `cert_heat` masks.
  A departure is feasible at budget B iff that minimum is ≤ B. This is exact for the model, not a heuristic, because
  the dose is one additive, non-negative resource.
* The dose counts the drive and the waits (TDU, q₀ = 1.42 kW/m²), with the flux bounded **above** in every second.
* **The shelter stay** (destination dwell, 120 s in every spec here) is run both ways:
  * **counted**: the router's dose span, departure to the end of the dwell, as if the stay is outdoors;
  * **excluded**: the stay is indoors.
* **Budgets:** 92 TDU (pain), 105 TDU (first-degree burn), 290 TDU (second-degree burn), from HSL/2004/04 Table 1.
* The comparison is `cert_heat` → `cert_heat` + dose ≤ B, so every change is caused by the dose limit.

**Checks, in every run.** Each per-(origin, destination, budget) deadline gets a witness route, and each witness must
pass three tests:

* it replays as a legal journey under the `cert_heat` masks, independently of both fields;
* its dose lies within independent sampled bounds (`kcf_heat/dose_check.py`) and is ≤ the budget;
* the next second is infeasible, or the planner range ends.

On top of that, `cert_heat` must reproduce the committed 1-hour results, and F-3.1's `cert` must reproduce the
multi-hour HEADLINE results.

### 1-hour panel

Scope: 530 origins, 507 with a `cert_heat` leave-by. The exact 1 s leave-by is used, under the same rule as the table
above. `cert_heat` reproduces the C.2 result for every origin; all 4,443 witnesses pass (each dwell mode).

| budget | leave-bys moved earlier | shift (s) | places that lose their route | 10-min grid value changed |
|---|---:|---|---:|---:|
| 92 TDU (pain) | 4 | Uiseong 03-23: 261, 453; Uiseong 03-24: 184, 184 | 0 | 2 |
| 105 TDU (first-degree burn) | 4 | 226, 252; 157, 157 | 0 | 1 |
| 290 TDU (second-degree burn) | 3 | 51; 21, 21 | 0 | 0 |

* **The places:**
  * Uiseong 03-23 01Z: `osm:node/415160424`, `osm:node/415160476`;
  * Uiseong 03-24 09Z: `osm:node/415160428`, `osm:node/415160434`.
* **The shelter stay makes no difference here.** Counted and excluded give identical results, so on this panel the
  limit binds only through the drive.
* **Why only 4 moves.** C.3 found 30 heat-on witnesses above 92 TDU. Two things separate those from this table:
  * C.3 tested one route per attempt, at every planner offset. The field takes the minimum over all routes.
  * A leave-by changes only if the latest feasible second changes.
* Data: `data/tdu_1h/` (one file per cache and dwell mode); script: `scripts/c4_tdu_1h.py`.

## Multi-hour runs

These are **scenarios** (F-DYN), not what happened. Roads are limited to the recorded windows.

### Inputs and reproduction

F-3.1's HEADLINE uses 48 no_reentry/2 packets from F-DYN (`MANIFEST_v3_7.json`, recorded starts): 2 regions × 3
starts × {5 h, 8 h} × 4 variants. Three variants are timing variants (`kriged_mean`, `firms_early`, `envelope`); the
fourth, `envelope_burnset`, is the static final footprint.

* **Rebuilt inputs.** F-DYN's `_data/` is gitignored. It was rebuilt from this repository's own branches with
  `scripts/fdyn_rebuild_inputs.sh`, in a scratch checkout of the F-DYN commit that F-3.1's headline batch used
  (819bcb91). The rebuild's own checks pass:
  * the kriged TOA sha256 equals build.py's `KRIGED_TOA_SHA256`;
  * `envelope_sound_counts.json` is identical to the committed file;
  * the burn set has 16,176 cells;
  * `INSTANCE.json` has 12 instances and 1,044 origin-instances.
* **Packets.** Each packet was built with its manifest command unchanged, run, then deleted
  (`scripts/c2_multihour_batch.py`, runner `scripts/c2_deadlines_multihour.py`).
* **Reproduction.** The HAZARD files' sha256 differ from F-3.1's, from float rounding across environments (F-3.1
  RESULTS row 72a records the same effect). So the inputs are checked by their output instead: **F-3.1's `cert`
  leave-by is reproduced for 4,176 / 4,176 place-runs** (48 packets × 84 or 90 places). This includes the static
  final-footprint row.
* All 96 runs (48 packets × 2 dwell modes) built and ran without failure.

### Units

* A **place** is (region, start, origin): 522 places, each run at 5 h and at 8 h. 286 of them have a `cert` leave-by
  in at least one timing variant.
* **Leave-by:** the latest second of the union, over the place's destinations, of its feasible departures, provided
  the union starts at 0 (headline.py's rule).
* Following MULTIHOUR_HEADLINE_RULE.md (2), a place's result is the **range over the three timing variants**.
  * The first table follows the range's **earliest edge**: the earliest leave-by among the variants.
  * Where the two horizons differ, it takes the larger shift.
* **Place-runs** (second table) count every packet × place separately.

### Results

**Places** (286 with a leave-by), each step against the one before it:

| step | shelter stay | earliest leave-by moves earlier | shift: range (median) | places that lose a route |
|---|---|---:|---|---:|
| heat rule: `cert` → `cert_heat` | — | 28 | 84–350 s (304.5 s) | 0 |
| then dose ≤ 92 TDU (pain) | counted | 22 | 12–529 s (301 s) | 2 |
| then dose ≤ 105 TDU (first-degree burn) | counted | 21 | 25–521 s (268 s) | 2 |
| then dose ≤ 290 TDU (second-degree burn) | counted | 16 | 27–257 s (117.5 s) | 2 |
| then dose ≤ 92 TDU (pain) | excluded | 21 | 12–529 s (307 s) | 0 |
| then dose ≤ 105 TDU (first-degree burn) | excluded | 19 | 25–521 s (268 s) | 0 |
| then dose ≤ 290 TDU (second-degree burn) | excluded | 12 | 27–245 s (116 s) | 0 |

Heat and dose together, against `cert`:

* **At 92 TDU:** with the stay counted, 26 places move 328–613 s (median 497 s) and 2 lose a route. With the stay
  excluded, 28 move 328–613 s (median 391 s).
* **At 290 TDU:** with the stay counted, 26 places move 111–478 s (median 313.5 s) and 2 lose a route. With the stay
  excluded, 28 move 111–350 s (median 319 s).

**Place-runs** (the 36 timing-variant packets: 3,132 place-runs, 1,612 with a `cert` leave-by):

| step | shelter stay | moved earlier | shift: range (median) | lose their route |
|---|---|---:|---|---:|
| heat rule: `cert` → `cert_heat` | — | 80 | 84–350 s (321.5 s) | 0 |
| then dose ≤ 92 TDU | counted | 60 | 12–529 s (285.5 s) | 8 |
| then dose ≤ 105 TDU | counted | 54 | 25–521 s (268 s) | 8 |
| then dose ≤ 290 TDU | counted | 44 | 27–257 s (118 s) | 8 |
| then dose ≤ 92 TDU | excluded | 57 | 12–529 s (295 s) | 0 |
| then dose ≤ 105 TDU | excluded | 45 | 25–521 s (288 s) | 0 |
| then dose ≤ 290 TDU | excluded | 32 | 27–245 s (117 s) | 0 |

**Static final footprint** (12 `envelope_burnset` packets; 81 places with a `cert` route): heat removes the route of
3 places (6 place-runs). The dose limit changes nothing further, at any budget, whichever way the stay is treated.

### Reading the results

* **Heat binds far more often over hours.** It moves 28 of 286 places here, against 6 of 508 leave-bys on the
  1-hour panel. This fits the earlier expectation that present-fire cells burn for hours on these horizons, so the
  lateral halo binds more often.
* **The dose limit then moves 12–22 further places**, by up to 529 s (8.8 min). The shifts shrink as the budget
  rises: the median falls from about 300 s at 92 TDU to about 117 s at 290 TDU.
* **Two places lose their route, and only when the shelter stay counts.** Both are in Uiseong with start 03-24 09Z:
  * Ibam-ri, `osm:node/415160345`: all three timing variants, both horizons;
  * Geumhak-ri, `osm:node/415160343`: `kriged_mean`, both horizons.
* **What happens at those two places:**
  * With the stay counted, no departure second at either place is under 290 TDU.
  * For Ibam-ri (5 h, `kriged_mean`), the minimum over departures is 344 TDU. Of that, 337 TDU is the 120 s stay
    and 6.6 TDU is the drive.
  * 337 TDU in 120 s equals a steady 2.2 kW/m². That is below the heat rule's 2.5 kW/m² person limit, which is why
    the heat rule alone keeps the route.
  * With the stay excluded, both keep their routes, to destination `osm:368196874`:
    * Ibam-ri's leave-by moves 33 s at 92 TDU and does not move at 105 or 290 TDU (drive dose at the leave-by
      91.9–99.8 TDU);
    * Geumhak-ri's does not move (drive dose 91.7 TDU).
  * So **the shelter stay alone removes these routes.**
  * Two things are open:
    * Whether the stay is outdoors is not known to the model. **UNVERIFIED.**
    * About 2 kW/m² held for minutes is the low-flux, long-exposure regime, where the TDU thresholds and the q₀
      cut-off are least certain (C.3).

### Checks and cost

* **Witnesses.** Every per-(origin, destination, budget) deadline witness passes all three checks in C.4:
  * 14,442 witnesses with the stay counted;
  * 14,466 witnesses with the stay excluded.
* **Early results rerun.** The first 11 packets in stay-counted mode were computed before a speed-only change: the
  issue values were vectorised, the core was reused, and the independent check got a cell prefilter.
  All 11 were rerun with the final code, and every result is identical:
  * leave-bys;
  * witnesses (deadline, arrival, dose and bounds);
  * comparisons, reproduction counts and field statistics.

  Only the count of lazily evaluated edges differs, and that measures work, not a result.
* **Cost per packet** (stay counted, 3 packets in parallel):
  * total 33–2,804 s, median 460 s;
  * TDU field 3–2,179 s (median 42 s), against 7–164 s (median 52 s) for the `cert_heat` field;
  * peak memory ≤ 4.0 GiB;
  * burning cells 554–16,176;
  * the slowest packet is Yeongdeok 03-25 19Z, 5 h, `kriged_mean`.
* **Data:** `data/multihour/summary_dwell_count.json` and `summary_dwell_exclude.json`.
  * Per packet: reproduction, witness checks, comparisons and timing.
  * Per place: the range of every field.
  * The per-packet run files (about 100 KB each) are not kept; the batch script reproduces them.
* The F-DYN halo uses the packet spread rate, not the local one (UNVERIFIED there).

## Not covered

Convection, smoke, embers and spotting, terrain shading, vehicle shielding, and crown-fire fuel load (χE_A scales T\*).
Also not covered:

* fronts other than straight and steady;
* the true front position inside a 375 m cell (the rule treats the whole flaming cell as the front);
* calibration of the packet constants.

All numbers are relative to the frozen packets, the recorded windows and the declared members.

## Reproduce

```sh
python tools/fetch_routing_inputs.py      # frozen graphs + packets (SHA-verified)
cd research/kcf-heat
python scripts/c2_deadlines_1h.py --data-root ../../data/routing --out-dir /tmp/kcf ../../planner/cache/*/*.json   # ~20 min, 3 in parallel
python scripts/c2_summarize.py /tmp/kcf/SUMMARY.json /tmp/kcf/*.summary.json
python scripts/c3_tdu_witness.py --data-root ../../data/routing /tmp/kcf/TDU.json /tmp/kcf/*.full.json
python scripts/c4_tdu_1h.py --data-root ../../data/routing --out-dir /tmp/kcf/tdu --dwell-dose count ../../planner/cache/*/*.json
python -m pytest -q -p no:cacheprovider tests
```

Multi-hour (inputs about 400 MB plus one packet at a time; 1 h 40 min per dwell mode on one machine with 3 workers,
builds included):

```sh
scripts/fdyn_rebuild_inputs.sh REPO /tmp/leo819 ../../data/routing PY_WITH_RASTERIO
python scripts/c2_multihour_batch.py --leo /tmp/leo819 --out-dir /tmp/kcf/mh --builder-python PY_WITH_RASTERIO \
    --dwell-dose count          # and again with --dwell-dose exclude into another directory
python scripts/c2_multihour_summarize.py /tmp/kcf/mh /tmp/kcf/mh_summary.json
```
