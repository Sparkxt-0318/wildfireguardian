# Effect of the radiant-heat closure on leave-by times and witness routes

**Scope:** the F-3.1 deadline field on the six recorded 2025 planner caches (1-hour panel), rerun with the heat
closure rule. These results are model-relative; they make no physical-safety claim. The multi-hour runs could not be
run here (see "Multi-hour" below).

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
| multi-hour HEADLINE (48 no_reentry/2 packets) | NOT RUN | — | — | — | — | — | — | — | — | — |

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

**Not done: enforcing TDU inside the field.** The field's interval algebra assumes the full policy reduces to contact,
and F-3.1 checks that precondition. Under the new law that assumption fails, because dose can bind (30 witnesses
exceed 92 TDU). A TDU limit inside the backward field needs a resource-constrained search, which is not implemented.

The TDU check here is a post-hoc test of witnesses. Its result: with q\* = 10 kW/m² closure alone, the pain threshold
can still be reached near the halo edge. 92 TDU takes 4.3 s at 10 kW/m² and 11 s at 5 kW/m². **Recommendation:** either a lower vehicle q\*
or a TDU budget in the search. Not tested.

## Multi-hour runs

**NOT RUN, blocked on inputs.** The HEADLINE no_reentry/2 packets (48 pairs) are built by F-DYN
(`research/harness-2026-11/F-DYN/fdyn/build.py`, branch `leo/f-c1-see-before-leave`, `MANIFEST_v3_7.json`) from
`F-DYN/_data/`. That directory holds the kriged arrival rasters, FIRMS bracket rasters, full-grid exports, regridded
graphs and `INSTANCE.json`. It is gitignored and exists only on the host that built the F-3.1 run; none of it is on any
fetched branch, on this machine, or in the attached study zip.

`scripts/c2_deadlines_multihour.py` takes the same arguments as `deadline_field/headline.py` and is ready to run there.

* Expected direction: deadlines can only move earlier.
* On multi-hour horizons T\* (84 / 350 s) is small next to horizons of 5–8 h, but present-fire cells burn for hours
  there, so the lateral halo may bind more often. **UNVERIFIED.**
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
python -m pytest -q -p no:cacheprovider tests
```
