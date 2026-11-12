# F-DYN: multi-hour dynamic routing workload from the 2025 KFS_01 arrival-time reconstruction (v2)

> **SCENARIO built from a reconstruction; not the 2025 fire; not a forecast.**
>
> - The base raster is a retrospective kriging reconstruction of arrival times: Choi, Seo & Cha 2026, Zenodo
>   10.5281/zenodo.21788344, CC-BY-4.0. It is built from VIIRS and Himawari detections inside the final perimeter.
> - Its kriging sd is 16.6–19.5 h (about 17 h median), and independent checks suggest even that is too small.
> - Absolute arrival times are therefore not identified. The workload is a realistic moving fire for testing routing.

## STATUS (read first)

- **SOUNDNESS CORRECTION (2026-11-12, orchestrator and Iris).** `firms_early` and `envelope` use the FIRMS
  **bracket-start**, "the previous overpass with ≥1 grid detection". That is **not a lower bound on arrival**:
  non-detection is not absence of fire, and documented accounts fall before it (F-C1b).
  - `firms_early` is therefore **not guaranteed early enough**, and `envelope` is **not guaranteed conservative**,
    wherever fire arrived before that overpass. Results on them keep this label and are never called conservative.
  - A sound envelope (`envelope_sound`) is defined in `SOUND_ENVELOPE_RULE.md` (with amendment 1) and computed by
    `fdyn/sound.py`. Counts are in `envelope_sound_counts.json`:
    - 1,575 of 3,228 detected cells have a confirmed-clear latest previous VIIRS view.
    - 13,514 of 16,176 burn-set cells keep the ignition time as their lower bound. 4,940 of these are only in AHI
      buffers.
  - **Outcome, as stated in advance.** The sound envelope blocks about 46–75% of road cells for whole horizons,
    including Yeongdeok starts on 23–24 Mar, before the fire reached it (`REACH_rule_envelope_sound.json`). It is
    the honest conservative envelope from these data, and it is **nearly uninformative for routing**.
  - **Effect on the build criterion.** Every start becomes built: 61 unique region-starts, with 20 newly built.
    `MANIFEST_v3.json` now lists 488 packets with 4 variants, each entry carrying a `soundness` label.
  - Only "burning by first detection" (`firms_constrained`) is a fact.

- **v1** (`3ced668`, 4 members, recorded window) and **v2-window** (`035681a`, packets under `packets_v2/`) are
  **SUPERSEDED. Do not score on them.** The hazard is the recorded routing window, which omits most of the burning and
  igniting fire. The writer's omitted-dose bound is 4,486–6,179 kJ/m² against the 100 kJ/m² limit (Nora's FAIL on v1;
  same numbers for v2-window).
- **v3** (current): the hazard is on the **full KFS_01 export grid**. The interim graph is the recorded roads
  re-indexed onto that grid (`fdyn/regrid_graph.py`: same nodes, edges, ticks and turns; 0 cell mismatches over
  167,316 segments). The writer reports `outside_sources_possible: false`, so **omitted dose = 0**.
  - Radiation margin: reconstructed fire touches the grid edge in 5 cells; the nearest routed road node is 8.6 km
    (Uiseong) / 9.0 km (Yeongdeok) from them.
  - Roads outside the recorded windows are still absent. This is a road-limited interim until the OSM-built
    un-clipped graph (blocked on the 2025-03-21 snapshot). **4,976 of 10,955 burned cells (45%) lie outside both
    recorded road windows** (Nora), so no roads exist there in v3. "Omitted dose = 0" covers hazard sources, not
    missing roads.
- **Dose binds** on F-DYN (Nora): non-flame flux about 0.012 kW/m² over 18,000 s exceeds 100 kJ/m². Contact-only
  reductions do not apply.
- **Start rule** (fixed before computing): `STARTS_RULE.md`, commits `6042132` + `89d0222`. 29 starts every 3 h
  (whole hours), both regions, 5 h and 8 h. Non-recorded starts use SYNTHETIC present-fire exports from the TOA
  (`fdyn/synthetic_export.py`), marked in the record, the identity (`checkpoint_sha256 = SYNTHETIC-…`) and hence the
  scenario ids. The generator reproduces the 6 recorded exports (test).
- **Reach for every start:** `fdyn/reach_rule.py` writes `REACH_rule_<variant>.json` (kriged_mean and firms_early,
  central, Q = 300).

## Finding: the kriged mean is late for the Yeongdeok coastal run (CORRECTED at 0950 UTC)

**Correction.** An earlier version said there was "no detection 05:06–16:09 UTC" and that the kriged mean was "up to
about 11 h late". That was wrong. An ad-hoc listing script rounded pass times and showed a MODIS pass with 335
detections as 0. `fdyn/variants.py` was not affected: it uses exact pass times.

Corrected numbers:

- **Burst.** 2,983 of 10,955 footprint cells (27%) have kriged arrival in one hour, 2025-03-25 16:24–17:24 UTC.
  There are 5,773 in the 3 h from 16:24.
- **Passes with detections on 25 March (UTC):**

  | Time | Satellite | Detections |
  |---|---|---:|
  | 03:25 | S-NPP | 26 |
  | 03:48 | NOAA-20 | 74 |
  | 05:06 | S-NPP | 154 |
  | 05:29 | NOAA-20 | 90 |
  | 05:58 | MODIS | 59 |
  | **12:25** | **MODIS** | **335** |
  | 16:09 | NOAA-20 | 735 |
  | 17:26 | S-NPP | 1,184 |
  | 17:49 | NOAA-20 | 761 |
  | 17:58 | MODIS | 40 |

  The VIIRS-only gap is 05:29–16:09.
- **Cells MODIS first detects at 12:25** (323 in the footprint): the kriged mean is a median **4.8 h after the
  detection** (p10 3.7 h, p90 7.4 h). A detection proves fire by then, so for these cells **the kriged mean is late by
  at least that**. Their bracket is (05:58, 12:25] UTC.
- **Cells NOAA-20 first detects at 16:09** (509 in the footprint): kriged minus detection has median 1.5 h (p10 0.1,
  p90 5.6). Their bracket is (12:25, 16:09].
- **Reported timeline.** Documented village accounts (Sofia; snippet-level) put fire in Yeongdeok villages at about
  09–12 UTC, which is consistent with the brackets.
- **What is solid and what is not.**
  - **Solid:** the bound for the 323 cells MODIS first detects at 12:25 UTC. The kriged mean there is late by a
    median of at least 4.8 h.
  - **Not established:** a 7–10 h lag. That is what "**AHI indicates**" (`ahi_results/README.md`), from 2 km pixels
    with a 3.75% daytime false-alarm rate, point-spread bleed and 62 left-censored pixels.
- **Implication.**
  - The kriged mean cannot time the coastal run. The defensible statement is the per-cell detection bracket. MODIS
    pixels are 1 km, so a 375 m-cell assignment from MODIS is coarse.
  - With `firms_early`, fire reaches Yeongdeok roads and places from the 2025-03-24 23:00 UTC start (8 h) onward. For
    example, at the 03-25 08:00 UTC start (5 h): 114 vs 0 road cells igniting and 13 vs 0 entry cells.
  - Envelope bracket widths for igniting cells reach 6.5 h (Yeongdeok 03-25 05:00 UTC start).

## Why

The frozen 1-hour workload is close to routing around a static obstacle: 15 of 522 deadlines are set by the fire,
and each member has 0–9 new ignitions per hour. F-DYN gives moving fire over 5 h and 8 h horizons.

New ignitions inside the recorded routing window, central member, kriged mean:

| Start (UTC) | 5 h | 8 h |
|---|---:|---:|
| Uiseong 03-23 01:00 | 82 | 131 |
| Uiseong 03-24 09:00 | 76 | 133 |
| Uiseong 03-25 17:00 | 1,099 | 1,137 |
| Yeongdeok 03-25 19:00 | 307 | 372 |
| Yeongdeok 03-25 23:00 | 109 | 150 |
| Yeongdeok 03-26 08:00 | 29 | 29 |

## Construction (the F-9.3 hazard interface: an arrival-time raster as a hazard scenario)

The **unchanged** packet writer (`integration/src/wfg_latest/packets.write_regional_packet`) is driven through the
two extension points `api/adapters/_zone_packet_child.py` also uses:

- `bridge.draw_ignitions` returns the F-DYN schedule on the full KFS_01 event grid.
- `bridge.settings_for` sets `horizon_s`, `scenario_count`, the widened burning duration and the `fdyn` metadata.

All of these enter the settings digest, and hence the construction id and the scenario ids. Present fire, radiation
operator, flame semantics, router validator and routing kit are all unchanged.

1. **Arrival raster: an explicit, swappable input.** It is in hours since t0 = 2025-03-22 02:24 UTC on the KFS_01
   export grid. Its variant label and SHA-256 are recorded in the plan and settings. `fdyn/variants.py` makes these
   variants:

   | Variant | Rule | Notes |
   |---|---|---|
   | `kriged_mean` | the published TOA | |
   | `firms_constrained` | `min(TOA, first FIRMS detection in the cell)` | A detection proves fire by then: the late bound. |
   | `firms_early` | detected cells: the previous overpass with at least one detection in the grid, before the cell's first detection | The earliest arrival consistent with a clear-sky non-detection. Cloud or smoke can hide fire, so the true arrival can be earlier still. |
   | `dilate_<d>_<lag>` | isotropic spotting envelope | Proposed shared implementation for Richard and Priya. Downwind stretching needs a wind field, and none is in the KFS_01 inputs. |

   FIRMS coverage, measured (`variants.py` stats):
   - 5,603 detections over 46 overpasses (VIIRS S-NPP, NOAA-20, MODIS; NOAA-21 and Himawari unavailable).
   - Only 2,947 of 10,955 burned cells contain a detection.
   - In those cells, first detection minus kriged TOA has median −1.8 h (p10 −9.7 h, p90 +7.3 h). **The kriged mean is
     usually later than the satellites saw fire.**
   - 281 detected cells lie outside the kriged footprint. They are not used.
2. **Start times** are the six recorded input times. At each, the recorded c651 export's present fire, burned state
   and remaining burn time equal the kriged TOA thresholded at the start, cell for cell (tested). Export-burned cells
   are never re-ignited.

   A variant can place a cell's arrival before the start although the export has it unburned:
   - Still burning (arrival within one burn duration T before the start): it **ignites at 0**.
   - Otherwise: it is taken as burned out.

   Counts are recorded as `variant_cells_before_start_not_in_export`. For example, the FIRMS variants at Yeongdeok
   03-25 23:00 have 0 catch-up cells and 129 burned-out cells.
3. **Ignition time.** A cell with arrival `a` and start `h` ignites at `floor_Q(s * (a − h) * 3600 − shift)`, clamped
   at 0, when the time is within the horizon. Default Q = 300 s.
4. **Burning duration widened to T + Q.** `consumed_fraction` is scaled by (T + Q)/T, so the emitted heat-release-rate
   density is unchanged. This is a floor-start, ceil-end construction: each contact interval
   `[floor(t), floor(t) + T + Q)` contains the exact `[t, t + T)`. Checked on Yeongdeok 03-25 23:00 against the exact
   TOA:
   - Q = 300: start ≤ exact for all cells; end margin 2.4–295.7 s.
   - Q = 60: same; end margin 0.3–60.0 s.
   - The Q = 300 intervals contain the Q = 60 intervals.

   The deadline comparison between Q = 60 and Q = 300 is pending (to be run on Richard's exact deadline field).
5. **Members** (Iris / orchestrator decision). The base workload is `central` only. The variants `faster_1.33x`
   (s = 0.75), `faster_2x` (s = 0.5) and `earlier_1h` (shift 3600 s) are each a **single-member packet**, because an
   all-members verdict collapses to the fastest member. One `all4` packet exercises the all-members code path. Members
   are never later than their raster and are not sd quantiles.
6. **Outside the footprint.**
   - Outside the final perimeter but inside the mapped domain: observed no-fire.
   - Unburned islands and perimeter mapping error are not represented.
   - Outside the mapped domain (the export grid): unknown. The packet support channel is all-true inside the grid
     (writer rule), and nothing outside the grid is in the packet.

## Domain (open item: un-clipped road graph)

The recorded graphs are clipped to the same box as their hazard packets (`grid_variant` "G2 region window"). "No
routed road in cropped fire" is therefore true by construction (Nora). v2 packets above still use the recorded
window.

**Target:** a graph on the full KFS_01 export grid (about 89 × 30 km), which contains the whole fire footprint; only 5
of 10,955 burned cells touch the grid edge. The writer requires the hazard grid to coincide with the forecast grid,
so the domain cannot extend beyond it without a new export. Fire and roads beyond it remain outside the model.

**Blocked:** no OSM-to-graph builder is in the repo, and Overpass is blocked here. Daniel has been asked for the
2025-03-21 historical snapshot. The plan is to write a builder replicating the documented rules and validate it by
rebuilding the two recorded clipped graphs exactly first. `fdyn/build.py --domain full_grid --graph G.json` is ready
for it.

## Files (large; outside git)

`fdyn/build.py` writes `packets_v2/<region>/<start>_h<H>_<variant>_<members>_q<Q>/`:

- `HAZARD.json`: `wfg.routing.edgegrid/1` with `valid_until` = 18000 or 28800.
- `NATIVE_METADATA.json`, `REPORT.json`, `constructed_arrays.npz`.
- `BUILD_SUMMARY.json`: `fdyn` plan metadata and omitted-source bounds.
- A `.plan.npz` next to the packet directory.

Single-member 5 h packets are about 13–15 MB; Q = 60 is about 27 MB; `all4` is about 56 MB.

`fdyn/instance.py` writes `INSTANCE.json` (`wfg.fdyn.instance/1`):

- 174 places at their entry nodes, each with its 3 recorded destinations and a 120 s stay.
- Departures every 30 min; destination window [0, H].
- Limits 10 kW/m² and 100 kJ/m².

## Notes on `fdyn/sample.py`

- It calls `python3` from PATH.
- The writer refuses an existing output directory, so after a failed build remove the half-built packet
  directories before re-running.

## Reproduce

```
python3 tools/fetch_routing_inputs.py
git fetch origin daniel/data-fetch
for f in KFS_01_pswt_ok_toa.tif KFS_01_pswt_ok_std.tif; do git show origin/daniel/data-fetch:research/harness-2026-11/data-fetch/small/choi2026_kfs01/$f > research/harness-2026-11/F-DYN/_data/$f; done
mkdir -p research/harness-2026-11/F-DYN/_data/firms; for f in viirs-snpp viirs-jpss1 modis; do git show origin/daniel/data-fetch:research/harness-2026-11/data-fetch/small/firms/${f}_2025_Republic_of_Korea.csv > research/harness-2026-11/F-DYN/_data/firms/$f.csv; done
pip install numpy scipy rasterio pyproj pandas
python3 research/harness-2026-11/F-DYN/fdyn/variants.py --toa research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_toa.tif --firms-dir research/harness-2026-11/F-DYN/_data/firms --out-dir research/harness-2026-11/F-DYN/_data/variants
python3 research/harness-2026-11/F-DYN/fdyn/build.py --region yeongdeok_2025 --start 20250325T230000Z --horizon-h 5 \
  --arrival research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_toa.tif --arrival-variant kriged_mean \
  --sd research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_std.tif --member-set central \
  --out research/harness-2026-11/F-DYN/_data/packets_v2/yeongdeok_2025/20250325T230000Z_h5_kriged_central_q300   # ~20 s
python3 research/harness-2026-11/F-DYN/fdyn/instance.py --out research/harness-2026-11/F-DYN/_data/INSTANCE.json
python3 -m pytest -q research/harness-2026-11/F-DYN/tests
```

## Findings so far (not timing claims)

- **Packets are consumed.** The unchanged kit (RDA_CAND) and its independent checker accept both v1 (4-member) and
  v2 (1-member) packets.
- **Memory, not time, is the limiter.** One v2 check with a 120 s budget was stopped at 23 s by the kit's **memory
  guard** (3,072 MiB; RSS 4.4 GB). It was UNRESOLVED/LATE_RESULT, and the independent checker says
  FEASIBLE_ROUTE_EXISTS. Clean timing and phase profiling are Priya's.
- **Rebuild check.** Rebuilding a recorded 1-hour packet here gives identical scenario ids, breakpoints, flame and
  support. Flux differs by at most 1.1e-15 kW/m² (numpy 2.5 here vs the pinned 1.26.4). The identity differs only in
  the absolute radiation module path. The F-9.3 regression test will compare those fields exactly and flux within a
  stated tolerance, under the pinned numpy.

## Envelope variant: reduced checking (orchestrator conditions)

Every result on `envelope` packets is labelled **"single implementation, not independently checked"**. The kit's
independent scalar-law checker **does not apply and was not run** on them. Never report it as passed.

- **Claims rest on the other variants.** `kriged_mean` and `firms_early` go through the unchanged writer and the
  independent checker; they carry the claims, and the envelope is reported beside them.
- **Substitute independent check (requested).** Thomas's O2 re-derives the integer instance independently. It would
  be extended to per-cell burning intervals, re-deriving the blocked intervals from the raw bracket arrays.
- **What exists.** A self-check in `_packet_child.py` proves the re-implemented member loop reproduces the unchanged
  writer exactly with scalar ends. The containment check shows each cell's interval covers [lo, hi + T).
- **The envelope over-includes** (Nora): this is conservative, but it is stated.
  - **Floor at 0.** On Uiseong 03-25 14Z, 7 cells burn from t = 0 although their bracket end says they were already
    out before the start. The catch-up rule uses the bracket end plus T against the start, and floors at 0.
  - **Wide brackets.** End margins reach about 21.5 h, because a wide bracket keeps a cell burning until hi + T.
- **No independent route check.** Envelope results are reported as such wherever they are scored.

## v3 scoring workload (built starts, manifest, verification sample)

- **Built starts:** `BUILT_STARTS.json`, criterion in `STARTS_RULE.md` @24bbad9 (union of three variants, inputs
  only). *(Corrected after Nora's verification.)*
  - **Three** rule starts coincide with recorded inputs: Uiseong 03-25 17Z, Yeongdeok 03-25 23Z and Yeongdeok
    03-26 08Z (the last one is not built).
  - That leaves **42 unique built region-starts: Uiseong 30, Yeongdeok 12.**
  - Uiseong: only 03-26 14Z is not built.
  - Yeongdeok: starts before 03-24 23Z and after 03-26 05Z are not built, because no fire reaches its routed roads
    within 8 h in any variant.
- **Manifest:** `MANIFEST_v3.json` lists **252 packets** (42 × {5 h, 8 h} × {kriged_mean, firms_early, envelope}) as
  exact `build.py` commands. Packets are about 63 MB each at 5 h, so consumers build what they need.
- **Reach tables:** `REACH_rule_{kriged_mean,firms_early,envelope}.json`, **128 rows each**: per region, 29 rule
  starts + that region's 3 recorded starts, × 2 horizons.
- **Verification sample:** `SAMPLE_v3.json`, from `fdyn/sample.py`: Yeongdeok 03-25 11Z (synthetic), Yeongdeok
  03-25 23Z (recorded) and Uiseong 03-25 14Z (synthetic), at 5 h × 3 variants. All 9 are **OK**:
  - Omitted analysis is `{window: None, outside_sources_possible: False}`, i.e. omitted dose 0.
  - `valid_until` = 18000.
  - The SYNTHETIC marker appears exactly on the synthetic starts.
  - The envelope law appears exactly on the envelope packets.
  - Ignitions: 353–6,425.

## v3.1 quantization (QUANT_v3_1_RULE.md; orchestrator decision after Thomas's F-3.2 O2 finding)

- **What changed.** Every floored time is now integer ms since t0. Timestamp-derived arrivals are exact; real-valued
  ones are rounded to 1 ms, so a start can be at most 0.5 ms later than the real-valued arrival. Envelope ends are
  now exactly conservative, which removes Thomas's note 4.
- **Correction 1.** T = 3,970.4642815249267 s is real-valued. Comparisons against it are unambiguous.
- **Schedule diff, all 488 manifest entries** (`DIFF_v3_v31.json`). Every change is +300 s:
  - firms_early births: 102 cells per entry.
  - envelope births: 102 cells per entry.
  - envelope hi_rel: 17 cells per entry.
  - These occur only at 20250323T230000Z (h8), 20250324T020000Z (h5, h8) and 20250324T050000Z (h5, h8), on the
    same full-grid cells in both regions.
  - kriged_mean and envelope_sound: no change.
  - No cell enters or leaves the igniting set.
  - The rule's estimate of 612 + 102 came from a rough count that ignored the burned-at-start rule.
- **Packet diff** (`PACKET_DIFF_v3_v31.json`, all 10 v3 packets on disk):
  - Constructed arrays and HAZARD channels, breakpoints, flux, flame and support are identical.
  - Only the member id and identity digests differ, because the settings now carry the quantization version.
- **Manifest.** `MANIFEST_v3_1.json` (wfg.fdyn.manifest/2) supersedes `MANIFEST_v3.json` (kept, listed as
  superseded). Packets go to `_data/packets_v31/`.
- **Nora: PASS** (ledger row 26), on the delta from her v3 PASS:
  - The commit order holds and 19/19 tests pass.
  - Her diff is byte-identical to `DIFF_v3_v31.json`.
  - On Uiseong 24T02Z h5 firms_early, v3.1 equals the exact-rational schedule on all 170 timestamp-exact cells.
  - Exact end containment holds, with T = 3,970.4642815249267 s: 0 violations in 228 cells.
  - **Correction to her v3 verdict** (row 27): her v3 end-containment check used a mistyped T, 0.18 ms short. Under v3,
    boundary-cell ends could miss by up to about 0.18 ms. v3.1 fixes this.
- **Acceptance: PASS** (Thomas, fire-next @45a8975, `results/envelope_o2_v31_{a,b,c}.json`; Mira still to verify).
  Thomas derived the schedules from the rule text only and built the packets at f40e2af. Integer equality held with
  0 mismatches:

  | Sample | Active cells | Boundary cells (birth / end) | Integer instances |
  |---|---:|---:|---:|
  | Uiseong 24T02Z h5 envelope | 275 | 102 / 17 | 10/10 |
  | Uiseong 24T02Z h5 firms_early (scalar law) | 247 | 102 / — | 10/10 |
  | Yeongdeok 25T11Z h5 envelope | 1,752 | 482 / 309 | 10/10 |

## Final scoring set (orchestrator, 2026-11-12)

- `kriged_mean`
- `firms_early` and `envelope`: both labelled bracket-start, not a lower bound.
- `envelope_sound`: **WITHDRAWN as a bound** (Nora FAIL, row 28; see `SOUND_ENVELOPE_RULE.md` status). Do not
  score it. A fix is proposed in `ENVELOPE_FOOTPRINT_RULE.md`.

All four use the v3.1 convention. `envelope_ahi_bounded` was **withdrawn** after its reach table: it applied a
pixel time per cell, which burned cells early and burned them out before arrival. See `STARTS_RULE.md` and
`ahi_results/README.md`. No fifth variant is planned.

## `envelope_footprint` (ENVELOPE_FOOTPRINT_RULE.md @3fbd229, adopted; replaces withdrawn `envelope_sound`)

- **Static law.** The final mapped burn set (16,176 cells) is burning on the whole window [0, H) at every start. No
  cell is cleared within the horizon. lo = ignition, chosen on principle: non-detections fail on both attribution and
  omission.
- **Label.** "Bound relative to the final mapped burn set". It is **pending Nora**, and the word "sound" is not used
  until she passes it.
- **Sample.** Yeongdeok 25T11Z h5. The HAZARD flame mask is a single interval [0, 18000), equal to the burn set
  (16,176 cells). Present fire (97 cells) is inside it.
- **Blocked road share** (`REACH_footprint.json`, identical for every start and horizon):

  | Region | Road cells | Blocked | Share |
  |---|---:|---:|---:|
  | Uiseong-Andong | 1,656 | 1,646 | **99.4%** |
  | Yeongdeok | 1,590 | 1,115 | **70.1%** |

  The unit is a 375 m road cell, and "blocked" means inside the burn set for the whole window. The Uiseong road
  graph window lies 99.7% inside the final burn set, so this is not a share of roads burning at once: that is 0–9%
  at any instant under the timing scenarios. See "How to read the blocked road share" in
  ENVELOPE_FOOTPRINT_RULE.md.
- **Still to come from Richard's field:** origins with a checked route, and origins with an unchanged deadline.
- **Manifest.** `MANIFEST_v3_2.json` (wfg.fdyn.manifest/3) has `envelope_footprint` in place of `envelope_sound`.
  The other three variants' entries are identical to v3.1. `MANIFEST_v3_1.json` is not edited and is listed as
  superseded.
